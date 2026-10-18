"""
AI Coach API routes.

A third, fully separate workflow: a free-form conversational coach backed by
the existing ML/NLP analysis infrastructure. Sessions live in their own table
so video-upload and live-interview features remain untouched.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.models import Interview, LiveInterviewSession, CoachSession
from app.services import coach_service as cs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/coach", tags=["ai-coach"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TalkRequest(BaseModel):
    message: str = Field(min_length=0, max_length=8000)


class TalkResponse(BaseModel):
    session_id: int
    reply: str
    intent: Optional[str] = None
    practice_active: bool = False
    evaluation: Optional[dict] = None


class NewSessionResponse(BaseModel):
    session_id: int
    title: str


class SessionSummary(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int


class AttachRequest(BaseModel):
    kind: str = Field(pattern="^(video|live)$")
    id: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_msgs(session: CoachSession) -> list:
    return list(session.messages or [])


def _session_dict(session: CoachSession, with_messages: bool = False) -> dict:
    msgs = session.messages or []
    d = {
        "session_id": session.id,
        "title": session.title or "New chat",
        "created_at": session.created_at.isoformat() if session.created_at else "",
        "updated_at": session.updated_at.isoformat() if session.updated_at else "",
        "message_count": len(msgs),
        "practice_active": bool(session.active_practice),
        "target_role": session.target_role,
        "snapshot": session.snapshot,
        "snapshot_source_kind": session.snapshot_source_kind,
        "snapshot_source_id": session.snapshot_source_id,
    }
    if with_messages:
        d["messages"] = msgs
    return d


def _derive_title(session: CoachSession):
    if session.title and session.title != "New chat":
        return
    for m in session.messages or []:
        if m.get("role") == "user" and m.get("content", "").strip():
            words = m["content"].strip()[:60]
            session.title = (words[:57] + "...") if len(words) > 60 else words
            return


def _attach_snapshot(session: CoachSession, kind: str, ref_id: int, db: Session):
    """Load a completed analysis into the coach's context (read-only)."""
    if kind == "video":
        it = db.query(Interview).filter(Interview.id == ref_id).first()
        if not it:
            raise HTTPException(status_code=404, detail="Interview not found")
        if it.status != "completed":
            raise HTTPException(status_code=409, detail="That analysis isn't completed yet")
        session.snapshot = {
            "id": it.id,
            "title": it.title,
            "overall_score": it.overall_score,
            "communication_score": it.communication_score,
            "answer_quality_score": it.answer_quality_score,
            "words_per_minute": it.words_per_minute,
            "filler_rate": it.filler_rate,
            "detailed_scores": it.detailed_scores,
            "improvement_plan": it.improvement_plan,
            "areas": None,
        }
        session.snapshot_source_kind = "video"
        session.snapshot_source_id = it.id
        return f"Attached video analysis \"{it.title}\" ({it.id})."
    # live
    rep = db.query(LiveInterviewSession).filter(LiveInterviewSession.id == ref_id).first()
    if not rep:
        raise HTTPException(status_code=404, detail="Live session not found")
    if rep.status != "completed":
        raise HTTPException(status_code=409, detail="That live session isn't completed yet")
    session.snapshot = {
        "id": rep.id,
        "overall_score": rep.overall_score,
        "technical_score": rep.technical_score,
        "communication_score": rep.communication_score,
        "speech_score": rep.speech_score,
        "words_per_minute": rep.words_per_minute,
        "fillers_total": rep.fillers_total,
        "strengths": rep.strengths,
        "areas_for_improvement": rep.areas_for_improvement,
        "results": rep.results,
    }
    session.snapshot_source_kind = "live"
    session.snapshot_source_id = rep.id
    return f"Attached live interview report ({rep.id})."


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=NewSessionResponse)
async def create_session(db: Session = Depends(get_db)):
    session = CoachSession(title="New chat", messages=[], mode="coaching", tone="friendly")
    db.add(session)
    db.commit()
    db.refresh(session)
    return NewSessionResponse(session_id=session.id, title=session.title)


@router.get("/sessions")
async def list_sessions(db: Session = Depends(get_db)):
    sessions = (
        db.query(CoachSession)
        .order_by(CoachSession.updated_at.desc())
        .limit(50)
        .all()
    )
    return {"sessions": [
        {
            "id": s.id,
            "title": (s.title or "New chat"),
            "created_at": s.created_at.isoformat() if s.created_at else "",
            "updated_at": s.updated_at.isoformat() if s.updated_at else "",
            "message_count": len(s.messages or []),
        }
        for s in sessions
    ]}


@router.get("/sessions/{session_id}")
async def get_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(CoachSession).filter(CoachSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Coach session not found")
    return _session_dict(session, with_messages=True)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(CoachSession).filter(CoachSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Coach session not found")
    db.delete(session)
    db.commit()
    return {"deleted": session_id}


@router.post("/sessions/{session_id}/attach")
async def attach_analysis(session_id: int, req: AttachRequest, db: Session = Depends(get_db)):
    """Give the coach a completed analysis (video or live) to discuss."""
    session = db.query(CoachSession).filter(CoachSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Coach session not found")
    msg = _attach_snapshot(session, req.kind, req.id, db)
    msgs = _session_msgs(session)
    msgs.append({"role": "coach", "content": f"{msg} I'll keep it in mind while we talk — ask me anything about it, or say \"what should I fix first?\""})
    session.messages = msgs
    _derive_title(session)
    session.updated_at = datetime.utcnow()
    db.commit()
    return _session_dict(session, with_messages=True)


@router.post("/sessions/{session_id}/talk", response_model=TalkResponse)
async def talk(session_id: int, req: TalkRequest, db: Session = Depends(get_db)):
    """Send one user message; get the coach's contextual reply."""
    session = db.query(CoachSession).filter(CoachSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Coach session not found")

    text = (req.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is empty")

    history = _session_msgs(session)

    # active_practice doubles as asked-question storage (asked_ids_track); the
    # engine must only see a REAL active question, not bookkeeping leftovers.
    raw_ap = session.active_practice if isinstance(session.active_practice, dict) else None
    live_ap = {k: v for k, v in (raw_ap or {}).items() if k != "asked_ids_track"} or None
    if live_ap is not None and not live_ap.get("q"):
        live_ap = None

    session_fields = {
        "id": session.id,
        "mode": session.mode or "coaching",
        "tone": session.tone or "friendly",
        "target_role": session.target_role,
        "active_practice": live_ap,
        "asked_ids": list((raw_ap or {}).get("asked_ids_track") or []),
        "snapshot": session.snapshot,
        "snapshot_source_kind": session.snapshot_source_kind,
    }

    if not session_fields["asked_ids"]:
        # reconstruct recent asked questions from history so we don't repeat
        recent_qs = set()
        for m in history:
            if m.get("role") == "coach" and isinstance(m.get("meta_asked"), str):
                recent_qs.add(m["meta_asked"])
        session_fields["asked_ids"] = list(recent_qs)

    try:
        reply, updates, meta = cs.generate_reply(text, history, session_fields)
    except Exception:
        logger.exception("coach generate_reply failed")
        raise HTTPException(status_code=500, detail="The coach hit an internal snag — please try again.")

    msgs = history + [{"role": "user", "content": text}]
    if reply:
        coach_msg = {"role": "coach", "content": reply}
        if meta.get("question_id"):
            coach_msg["meta_asked"] = meta["question_id"]
        msgs.append(coach_msg)

    # Apply engine updates to the persisted session.
    asked_ids = list(session_fields.get("asked_ids") or [])
    for key, value in (updates or {}).items():
        if key == "asked_ids":
            asked_ids = list(value)
        elif hasattr(session, key):
            setattr(session, key, value)
    if asked_ids:
        # Persist asked-question tracking inside active_practice JSON (kept
        # even when practice is inactive so follow-ups don't repeat).
        ap = dict(raw_ap) if raw_ap else {}
        if updates and "active_practice" in updates:
            ap = dict(updates["active_practice"]) if updates["active_practice"] else {}
        ap["asked_ids_track"] = asked_ids[-20:]
        session.active_practice = ap

    if updates and updates.get("title") is None:
        session.title = "New chat"
        _derive_title(session)
    else:
        _derive_title(session)

    session.messages = msgs[-80:]
    session.updated_at = datetime.utcnow()
    db.commit()

    final_ap = session.active_practice if isinstance(session.active_practice, dict) else None
    return TalkResponse(
        session_id=session.id,
        reply=reply,
        intent=meta.get("intent"),
        practice_active=bool(final_ap and final_ap.get("q")),
        evaluation=meta.get("evaluation"),
    )


@router.get("/context")
async def coach_context(db: Session = Depends(get_db)):
    """Completed analyses the coach can attach (newest first)."""
    videos = (
        db.query(Interview)
        .filter(Interview.status == "completed")
        .order_by(Interview.created_at.desc())
        .limit(15)
        .all()
    )
    lives = (
        db.query(LiveInterviewSession)
        .filter(LiveInterviewSession.status == "completed")
        .order_by(LiveInterviewSession.created_at.desc())
        .limit(15)
        .all()
    )
    return {
        "video": [
            {"id": v.id, "title": v.title, "overall_score": v.overall_score,
             "created_at": v.created_at.isoformat() if v.created_at else ""}
            for v in videos
        ],
        "live": [
            {"id": l.id, "overall_score": l.overall_score,
             "created_at": l.created_at.isoformat() if l.created_at else ""}
            for l in lives
        ],
    }
