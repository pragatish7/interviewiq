"""
Interview API routes.
"""
import os
import json
import logging
import shutil
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.database import get_db
from app.models.models import Interview, AnswerAnalysis, ProgressRecord
from app.utils.helpers import validate_video_file, secure_filename, format_duration
from app.services.analysis_service import analyze_interview
from app.services.pdf_service import generate_pdf_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interviews", tags=["interviews"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500MB


class InterviewResponse(BaseModel):
    id: int
    title: str
    filename: str
    original_filename: str
    file_size: int
    duration: float
    created_at: str
    is_demo: bool
    status: str
    interview_type: Optional[str] = None
    target_role: Optional[str] = None
    experience_level: Optional[str] = None
    job_description: Optional[str] = None
    overall_score: Optional[float] = None
    communication_score: Optional[float] = None
    answer_quality_score: Optional[float] = None
    filler_rate: Optional[float] = None
    words_per_minute: Optional[float] = None

    class Config:
        from_attributes = True


def interview_to_dict(interview: Interview) -> dict:
    return {
        "id": interview.id,
        "title": interview.title,
        "filename": interview.filename,
        "original_filename": interview.original_filename,
        "file_size": interview.file_size,
        "duration": interview.duration,
        "created_at": interview.created_at.isoformat() if interview.created_at else "",
        "is_demo": interview.is_demo,
        "status": interview.status,
        "interview_type": interview.interview_type,
        "target_role": interview.target_role,
        "experience_level": interview.experience_level,
        "job_description": interview.job_description,
        "overall_score": interview.overall_score,
        "communication_score": interview.communication_score,
        "answer_quality_score": interview.answer_quality_score,
        "clarity_score": interview.clarity_score,
        "fluency_score": interview.fluency_score,
        "speaking_pace_score": interview.speaking_pace_score,
        "confidence_score": interview.confidence_score,
        "vocabulary_score": interview.vocabulary_score,
        "relevance_score": interview.relevance_score,
        "professionalism_score": interview.professionalism_score,
        "nonverbal_score": interview.nonverbal_score,
        "star_score": interview.star_score,
        "words_per_minute": interview.words_per_minute,
        "filler_count": interview.filler_count,
        "filler_rate": interview.filler_rate,
        "pause_count": interview.pause_count,
        "avg_pause_duration": interview.avg_pause_duration,
        "total_words": interview.total_words,
        "total_sentences": interview.total_sentences,
        "vocabulary_diversity": interview.vocabulary_diversity,
        "repetition_rate": interview.repetition_rate,
        "ml_predicted_score": interview.ml_predicted_score,
        "ml_confidence": interview.ml_confidence,
    }


@router.post("/upload")
async def upload_interview(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    interview_type: Optional[str] = Form(None),
    target_role: Optional[str] = Form(None),
    experience_level: Optional[str] = Form(None),
    job_description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Upload an interview video file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    is_valid, msg = validate_video_file(file.filename)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)

    # Read file to check size
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 500MB)")

    # Save file
    safe_name = secure_filename(file.filename)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{safe_name}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    # Create database record
    interview = Interview(
        title=title or os.path.splitext(file.filename)[0],
        filename=filename,
        original_filename=file.filename,
        file_size=len(contents),
        status="uploaded",
        interview_type=interview_type or "General",
        target_role=target_role or "",
        experience_level=experience_level or "",
        job_description=job_description or "",
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    return {
        "id": interview.id,
        "filename": filename,
        "original_filename": file.filename,
        "file_size": len(contents),
        "title": interview.title,
        "interview_type": interview.interview_type,
        "target_role": interview.target_role,
        "experience_level": interview.experience_level,
        "status": "uploaded",
    }


@router.post("/{interview_id}/analyze")
async def analyze(interview_id: int, db: Session = Depends(get_db)):
    """Run full analysis on an uploaded interview."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    filepath = os.path.join(UPLOAD_DIR, interview.filename)

    if not os.path.exists(filepath):
        # Check demo mode
        if interview.is_demo:
            return await _run_demo_analysis(interview, db)
        raise HTTPException(status_code=404, detail="Video file not found")

    interview.status = "processing"
    db.commit()

    try:
        context = {
            "interview_type": interview.interview_type or "General",
            "target_role": interview.target_role or "",
            "experience_level": interview.experience_level or "",
            "job_description": interview.job_description or "",
        }
        analysis = analyze_interview(filepath, is_demo=False, context=context)
        # If speech recognition could not run on the real audio (missing ffmpeg/
        # whisper), the pipeline falls back to sample text. Label it honestly.
        method = analysis.get("transcription", {}).get("method", "")
        if method in ("none", "demo"):
            interview.is_demo = True
        _update_interview_from_analysis(interview, analysis, db)

        # Save QA analyses
        for qa in analysis.get("qa_analysis", []):
            answer = AnswerAnalysis(
                interview_id=interview.id,
                question_index=qa.get("question_index", 0),
                question_text=qa.get("question", ""),
                question_category=qa.get("category", "general"),
                answer_text=qa.get("answer", ""),
                timestamp_start=qa.get("start", 0),
                timestamp_end=qa.get("end", 0),
                relevance_score=qa.get("relevance_score"),
                completeness_score=qa.get("completeness_score"),
                clarity_score=qa.get("clarity_score"),
                conciseness_score=qa.get("conciseness_score"),
                overall_answer_score=qa.get("overall_answer_score"),
                star_score=qa.get("star_score"),
                has_situation=qa.get("star", {}).get("situation", False),
                has_task=qa.get("star", {}).get("task", False),
                has_action=qa.get("star", {}).get("action", False),
                has_result=qa.get("star", {}).get("result", False),
                strengths=qa.get("strengths"),
                missing_elements=qa.get("missing"),
                suggested_improvement=qa.get("improvement"),
            )
            db.add(answer)

        # Add progress record
        progress = ProgressRecord(
            interview_id=interview.id,
            overall_score=interview.overall_score,
            communication_score=interview.communication_score,
            filler_rate=interview.filler_rate,
            pace=interview.words_per_minute,
            answer_quality_score=interview.answer_quality_score,
            confidence_score=interview.confidence_score,
        )
        db.add(progress)

        db.commit()
        db.refresh(interview)

        return {
            "status": "completed",
            "interview_id": interview.id,
            "overall_score": interview.overall_score,
            "message": "Analysis complete",
        }

    except Exception as e:
        interview.status = "failed"
        interview.error_message = str(e)
        db.commit()
        logger.error(f"Analysis failed for interview {interview_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


def _update_interview_from_analysis(interview: Interview, analysis: dict, db: Session):
    """Update interview record with analysis results."""
    scores = analysis.get("scores", {})
    speech = analysis.get("speech_analysis", {})
    video = analysis.get("video_analysis", {})
    ml = analysis.get("ml_prediction", {})
    content = analysis.get("content_analysis", {})

    interview.status = "completed"
    interview.overall_score = scores.get("overall_score")
    interview.communication_score = scores.get("communication_score")
    interview.answer_quality_score = scores.get("answer_quality_score")
    interview.clarity_score = scores.get("clarity_score")
    interview.fluency_score = scores.get("fluency_score")
    interview.speaking_pace_score = scores.get("speaking_pace_score")
    interview.confidence_score = scores.get("confidence_score")
    interview.vocabulary_score = scores.get("vocabulary_score")
    interview.relevance_score = scores.get("relevance_score")
    interview.professionalism_score = scores.get("professionalism_score")
    interview.nonverbal_score = scores.get("nonverbal_score")
    interview.star_score = scores.get("star_score")
    interview.words_per_minute = speech.get("words_per_minute")
    interview.filler_count = speech.get("filler_words", {}).get("count")
    interview.filler_rate = speech.get("filler_words", {}).get("rate_per_minute")
    interview.pause_count = speech.get("pauses", {}).get("total_pauses")
    interview.avg_pause_duration = speech.get("pauses", {}).get("average_pause_duration")
    interview.speech_duration = speech.get("duration")
    interview.total_words = speech.get("total_words")
    interview.total_sentences = speech.get("sentence_count")
    interview.vocabulary_diversity = content.get("vocabulary_diversity")
    interview.repetition_rate = content.get("repetition_rate")
    interview.sentiment_score = content.get("sentiment")
    interview.face_visibility = video.get("face_visibility")
    interview.camera_presence = video.get("camera_presence")
    interview.head_movement_score = video.get("head_movement_score")
    interview.framing_score = video.get("framing_score")
    interview.ml_predicted_score = ml.get("predicted_score")
    interview.ml_confidence = ml.get("confidence")
    interview.transcript = analysis.get("transcription", {}).get("text", "")
    interview.detailed_scores = scores
    interview.timeline_events = analysis.get("timeline_events")
    interview.qa_analysis = analysis.get("qa_analysis")
    interview.coaching_feedback = analysis.get("coaching")
    interview.filler_words_detail = speech.get("filler_words")
    interview.improvement_plan = analysis.get("improvement_plan")
    interview.ml_feature_importance = ml.get("feature_importance")
    interview.question_categories = analysis.get("question_categories")
    interview.nonverbal_detail = video
    interview.speech_segments = speech.get("segments", [])
    interview.nlp_features = content

    interview.duration = speech.get("duration") or interview.duration


async def _run_demo_analysis(interview: Interview, db: Session):
    """Run analysis with demo/fallback data."""
    analysis = analyze_interview("", is_demo=True, context={
        "interview_type": interview.interview_type or "General",
        "target_role": interview.target_role or "",
        "job_description": interview.job_description or "",
    })
    _update_interview_from_analysis(interview, analysis, db)
    db.commit()
    db.refresh(interview)

    return {
        "status": "completed",
        "interview_id": interview.id,
        "overall_score": interview.overall_score,
        "message": "Demo analysis complete",
    }


@router.get("")
async def list_interviews(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """List all interviews."""
    interviews = db.query(Interview).order_by(Interview.created_at.desc()).offset(skip).limit(limit).all()
    total = db.query(Interview).count()
    return {
        "interviews": [interview_to_dict(i) for i in interviews],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{interview_id}")
async def get_interview(interview_id: int, db: Session = Depends(get_db)):
    """Get full interview details."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    data = interview_to_dict(interview)
    data.update({
        "transcript": interview.transcript,
        "detailed_scores": interview.detailed_scores,
        "timeline_events": interview.timeline_events,
        "qa_analysis": interview.qa_analysis,
        "coaching_feedback": interview.coaching_feedback,
        "filler_words_detail": interview.filler_words_detail,
        "improvement_plan": interview.improvement_plan,
        "ml_feature_importance": interview.ml_feature_importance,
        "question_categories": interview.question_categories,
        "nonverbal_detail": interview.nonverbal_detail,
        "speech_segments": interview.speech_segments,
        "nlp_features": interview.nlp_features,
        "ml_predicted_score": interview.ml_predicted_score,
        "ml_confidence": interview.ml_confidence,
    })
    return data


@router.get("/{interview_id}/video")
async def stream_video(interview_id: int, db: Session = Depends(get_db)):
    """Stream the uploaded video back to the owner for playback."""
    from fastapi.responses import FileResponse

    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    filepath = os.path.join(UPLOAD_DIR, interview.filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Video file not found")
    media = {
        ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
    }.get(os.path.splitext(interview.filename)[1].lower(), "video/mp4")
    return FileResponse(filepath, media_type=media)


@router.get("/{interview_id}/report")
async def get_report(interview_id: int, db: Session = Depends(get_db)):
    """Get formatted interview report."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    return {
        "interview": interview_to_dict(interview),
        "transcript": interview.transcript,
        "detailed_scores": interview.detailed_scores,
        "qa_analysis": interview.qa_analysis,
        "coaching": interview.coaching_feedback,
        "improvement_plan": interview.improvement_plan,
        "timeline_events": interview.timeline_events,
        "keywords": interview.nlp_features.get("keywords", []) if interview.nlp_features else [],
        "question_categories": interview.question_categories,
        "ml_prediction": {
            "predicted_score": interview.ml_predicted_score,
            "confidence": interview.ml_confidence,
            "feature_importance": interview.ml_feature_importance,
        },
    }


@router.get("/{interview_id}/transcript")
async def get_transcript(interview_id: int, db: Session = Depends(get_db)):
    """Get transcript with annotations."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    return {
        "transcript": interview.transcript,
        "segments": interview.speech_segments,
        "filler_words": interview.filler_words_detail,
        "timeline_events": interview.timeline_events,
    }


@router.get("/{interview_id}/timeline")
async def get_timeline(interview_id: int, db: Session = Depends(get_db)):
    """Get timeline events."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    return {"events": interview.timeline_events or []}


@router.get("/{interview_id}/pdf")
async def download_pdf(interview_id: int, db: Session = Depends(get_db)):
    """Generate and download a PDF report."""
    from fastapi.responses import FileResponse

    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    report_data = {
        "interview": interview_to_dict(interview),
        "coaching": interview.coaching_feedback,
        "improvement_plan": interview.improvement_plan,
        "qa_analysis": interview.qa_analysis,
        "timeline_events": interview.timeline_events,
    }

    pdf_dir = os.path.join(os.path.dirname(UPLOAD_DIR), "reports")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, f"report_{interview_id}.pdf")

    result = generate_pdf_report(report_data, pdf_path)
    if result and os.path.exists(result):
        return FileResponse(
            result,
            media_type="application/pdf",
            filename=f"InterviewIQ_Report_{interview_id}.pdf",
        )
    raise HTTPException(status_code=500, detail="PDF generation failed")


@router.delete("/{interview_id}")
async def delete_interview(interview_id: int, db: Session = Depends(get_db)):
    """Delete an interview."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    filepath = os.path.join(UPLOAD_DIR, interview.filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    db.query(AnswerAnalysis).filter(AnswerAnalysis.interview_id == interview_id).delete()
    db.query(ProgressRecord).filter(ProgressRecord.interview_id == interview_id).delete()
    db.delete(interview)
    db.commit()

    return {"message": "Interview deleted", "id": interview_id}
