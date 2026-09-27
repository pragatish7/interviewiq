"""
Live AI Interview API routes.

A second, separate interview workflow: the user answers dataset questions live
via microphone; each spoken answer is transcribed in the browser (Web Speech
API) and scored server-side against the dataset's reference answer using
semantic comparison. Sessions are stored in their own table so the existing
video-upload tables/workflow remain untouched.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.database.database import get_db
from app.models.models import LiveInterviewSession
from app.services import live_dataset_service as ds
from app.services import live_eval_service as ev
from app.ml import live_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live-interviews", tags=["live-interviews"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LiveStartRequest(BaseModel):
    total_questions: int = Field(default=6, ge=1, le=40)
    categories: Optional[list] = None
    seed: Optional[int] = None


class LiveStartResponse(BaseModel):
    session_id: int
    total_questions: int
    categories: list
    questions: list


class AnswerRequest(BaseModel):
    question_id: str = Field(min_length=1)
    transcript: str = Field(min_length=0)
    duration_s: float = Field(default=0.0, ge=0)
    pause_count: int = Field(default=0, ge=0)
    pause_seconds_total: float = Field(default=0.0, ge=0)


class AnswerResponse(BaseModel):
    score: float
    score_10: float
    grade_label: str
    feedback: str
    semantic_similarity: float
    concept_coverage: float
    keywords_hit: list
    keywords_missed: list
    key_points_missing: list
    question_id: str
    ml_predicted_score: Optional[float] = None
    ml_available: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/dataset")
async def get_dataset_info():
    """Dataset metadata for the live interview start screen."""
    questions = ds.load_dataset()
    return {
        "available": len(questions) > 0,
        "total_questions": len(questions),
        "categories": ds.get_categories(),
        "source": "mock_interview_dataset_test.csv",
    }


@router.post("/start", response_model=LiveStartResponse)
async def start_session(req: LiveStartRequest, db: Session = Depends(get_db)):
    """Create a live session and return its dataset-selected questions."""
    questions = ds.select_questions(
        count=req.total_questions,
        categories=req.categories,
        seed=req.seed,
    )
    if not questions:
        raise HTTPException(status_code=503, detail="Interview question dataset not available")

    session = LiveInterviewSession(
        status="in_progress",
        total_questions=len(questions),
        categories=req.categories,
        question_ids=[q["question_id"] for q in questions],
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Questions are returned WITHOUT expected answers — the candidate should
    # hear/read the question, not the grading key. Expected answers come back
    # only in the final report.
    safe_questions = [
        {
            "question_id": q["question_id"],
            "question": q["question"],
            "category": q["category"],
            "difficulty": q["difficulty"],
        }
        for q in questions
    ]
    return LiveStartResponse(
        session_id=session.id,
        total_questions=len(questions),
        categories=sorted({q["category"] for q in questions}),
        questions=safe_questions,
    )


@router.post("/{session_id}/answer", response_model=AnswerResponse)
async def submit_answer(session_id: int, req: AnswerRequest, db: Session = Depends(get_db)):
    """Evaluate one spoken answer against its dataset reference answer."""
    session = db.query(LiveInterviewSession).filter(LiveInterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "in_progress":
        raise HTTPException(status_code=409, detail="Session is not active")

    # Find the question (with expected answer + grade scale) in the dataset.
    all_q = {q["question_id"]: q for q in ds.load_dataset()}
    question = all_q.get(req.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in dataset")
    if question["question_id"] not in (session.question_ids or []):
        raise HTTPException(status_code=400, detail="Question not part of this session")

    result = ev.evaluate_answer(
        question=question,
        candidate_answer=req.transcript,
        duration_s=req.duration_s,
        grades=question.get("grades"),
    )

    # Append the per-question result (with the frontend-measured pause meta)
    # to the running session record.
    results = list(session.results or [])
    results.append({**result, "pause_count": req.pause_count, "pause_seconds_total": req.pause_seconds_total})
    session.results = results
    session.duration_s = (session.duration_s or 0.0) + req.duration_s

    flag_modified(session, "results")
    db.commit()

    ml_pred = result.get("ml_prediction") or {}
    return AnswerResponse(
        score=result["answer_score"],
        score_10=result["answer_score_10"],
        grade_label=result["grade_label"],
        feedback=result["feedback"],
        semantic_similarity=result["semantic_similarity"],
        concept_coverage=result["concept_coverage"],
        keywords_hit=result["keywords_hit"],
        keywords_missed=result["keywords_missed"],
        key_points_missing=result["key_points_missing"],
        question_id=result["question_id"],
        ml_predicted_score=ml_pred.get("predicted_score"),
        ml_available=bool(ml_pred.get("available")),
    )


@router.post("/{session_id}/finish")
async def finish_session(session_id: int, db: Session = Depends(get_db)):
    """Complete the session and compute the final aggregated report."""
    session = db.query(LiveInterviewSession).filter(LiveInterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "completed":
        return _session_report(session)

    report = ev.aggregate_session(
        results=session.results or [],
        sessions_meta={
            "pause_count": sum(r.get("pause_count", 0) for r in (session.results or [])),
            "pause_seconds_total": sum(r.get("pause_seconds_total", 0.0) for r in (session.results or [])),
        },
    )

    session.status = "completed"
    session.overall_score = report["overall_score"]
    session.technical_score = report["technical_score"]
    session.communication_score = report["communication_score"]
    session.speech_score = report["speech_score"]
    session.words_per_minute = report["words_per_minute"]
    session.fillers_total = report["fillers_total"]
    session.pauses_total = report["pauses_total"]
    session.pause_seconds_total = report["pause_seconds_total"]
    session.results = report["question_results"]
    session.strengths = report["strengths"]
    session.areas_for_improvement = report["areas_for_improvement"]
    session.overall_feedback = report["overall_feedback"]
    session.transcript = "\n\n".join(
        f"Q{i + 1}: {r['question']}\nA: {r['candidate_answer'] or '(no answer captured)'}"
        for i, r in enumerate(report["question_results"])
    )

    flag_modified(session, "results")
    db.commit()

    return _session_report(session)


@router.get("/{session_id}/report")
async def get_report(session_id: int, db: Session = Depends(get_db)):
    """Fetch the final live-interview report."""
    session = db.query(LiveInterviewSession).filter(LiveInterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "completed":
        raise HTTPException(status_code=409, detail="Session is not completed yet")
    return _session_report(session)


@router.post("/{session_id}/abandon")
async def abandon_session(session_id: int, db: Session = Depends(get_db)):
    """Mark a session as abandoned (user ended early without finishing)."""
    session = db.query(LiveInterviewSession).filter(LiveInterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "in_progress":
        session.status = "abandoned"
        db.commit()
    return {"id": session.id, "status": session.status}


def _session_report(session: LiveInterviewSession) -> dict:
    """Shape the completed session for the results UI."""
    return {
        "id": session.id,
        "created_at": session.created_at.isoformat() if session.created_at else "",
        "status": session.status,
        "total_questions": session.total_questions,
        "categories": session.categories or [],
        "overall_score": session.overall_score,
        "technical_score": session.technical_score,
        "communication_score": session.communication_score,
        "speech_score": session.speech_score,
        "words_per_minute": session.words_per_minute,
        "fillers_total": session.fillers_total,
        "pauses_total": session.pauses_total,
        "pause_seconds_total": session.pause_seconds_total,
        "duration_s": session.duration_s,
        "strengths": session.strengths or [],
        "areas_for_improvement": session.areas_for_improvement or [],
        "overall_feedback": session.overall_feedback,
        "results": session.results or [],
    }


@router.get("/model-info")
async def get_model_info():
    """What the trained model actually is — honest metadata only.

    NOTE: must be declared before any /{session_id} routes take effect for
    GET; FastAPI matches in declaration order, and this path cannot collide
    with an integer session id, but keeping it early is safer.
    """
    return live_bridge.model_info()


@router.get("")
async def list_sessions(db: Session = Depends(get_db)):
    """List recent completed live sessions (for future history views)."""
    sessions = (
        db.query(LiveInterviewSession)
        .filter(LiveInterviewSession.status == "completed")
        .order_by(LiveInterviewSession.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "sessions": [
            {
                "id": s.id,
                "created_at": s.created_at.isoformat() if s.created_at else "",
                "overall_score": s.overall_score,
                "technical_score": s.technical_score,
                "communication_score": s.communication_score,
                "speech_score": s.speech_score,
                "total_questions": s.total_questions,
            }
            for s in sessions
        ]
    }
