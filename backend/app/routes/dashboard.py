"""
Dashboard and progress API routes.
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.database import get_db
from app.models.models import Interview, ProgressRecord

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
async def get_dashboard(db: Session = Depends(get_db)):
    """Get dashboard summary data."""
    total_interviews = db.query(Interview).filter(Interview.status == "completed").count()
    recent_interviews = (
        db.query(Interview)
        .filter(Interview.status == "completed")
        .order_by(Interview.created_at.desc())
        .limit(5)
        .all()
    )

    avg_score = (
        db.query(func.avg(Interview.overall_score))
        .filter(Interview.status == "completed")
        .scalar()
    )

    latest_score = recent_interviews[0].overall_score if recent_interviews else None

    # Improvement calculation
    improvement = 0
    if len(recent_interviews) >= 2:
        scores = [i.overall_score for i in recent_interviews if i.overall_score]
        if len(scores) >= 2:
            improvement = round(scores[0] - scores[-1], 1)

    # Average metrics
    avg_comm = db.query(func.avg(Interview.communication_score)).filter(Interview.status == "completed").scalar()
    avg_fillers = db.query(func.avg(Interview.filler_rate)).filter(Interview.status == "completed").scalar()
    avg_pace = db.query(func.avg(Interview.words_per_minute)).filter(Interview.status == "completed").scalar()
    avg_answer = db.query(func.avg(Interview.answer_quality_score)).filter(Interview.status == "completed").scalar()

    return {
        "total_interviews": total_interviews,
        "average_score": round(avg_score, 1) if avg_score else None,
        "latest_score": latest_score,
        "improvement": improvement,
        "average_communication": round(avg_comm, 1) if avg_comm else None,
        "average_filler_rate": round(avg_fillers, 2) if avg_fillers else None,
        "average_pace": round(avg_pace, 1) if avg_pace else None,
        "average_answer_quality": round(avg_answer, 1) if avg_answer else None,
        "recent_interviews": [
            {
                "id": i.id,
                "title": i.title,
                "overall_score": i.overall_score,
                "communication_score": i.communication_score,
                "created_at": i.created_at.isoformat() if i.created_at else "",
                "filler_rate": i.filler_rate,
                "words_per_minute": i.words_per_minute,
            }
            for i in recent_interviews
        ],
    }


@router.get("/progress")
async def get_progress(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    """Get progress tracking data."""
    records = (
        db.query(Interview)
        .filter(Interview.status == "completed")
        .order_by(Interview.created_at.asc())
        .limit(limit)
        .all()
    )

    if not records:
        return {
            "interviews": [],
            "trends": {},
            "summary": {},
        }

    scores = [r.overall_score for r in records if r.overall_score]
    comm_scores = [r.communication_score for r in records if r.communication_score]
    filler_rates = [r.filler_rate for r in records if r.filler_rate is not None]
    answer_scores = [r.answer_quality_score for r in records if r.answer_quality_score]

    # Trends
    overall_trend = _compute_trend(scores)
    comm_trend = _compute_trend(comm_scores)
    filler_trend = _compute_trend_inv(filler_rates)  # Lower is better
    answer_trend = _compute_trend(answer_scores)

    return {
        "interviews": [
            {
                "id": r.id,
                "title": r.title,
                "overall_score": r.overall_score,
                "communication_score": r.communication_score,
                "answer_quality_score": r.answer_quality_score,
                "filler_rate": r.filler_rate,
                "words_per_minute": r.words_per_minute,
                "confidence_score": r.confidence_score,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in records
        ],
        "trends": {
            "overall": overall_trend,
            "communication": comm_trend,
            "filler_rate": filler_trend,
            "answer_quality": answer_trend,
        },
        "summary": {
            "total_interviews": len(records),
            "first_score": scores[0] if scores else None,
            "latest_score": scores[-1] if scores else None,
            "best_score": max(scores) if scores else None,
            "improvement": round(scores[-1] - scores[0], 1) if len(scores) >= 2 else 0,
        },
    }


def _compute_trend(values):
    if len(values) < 2:
        return {"direction": "stable", "change": 0, "percentage": 0}
    first_half = sum(values[:len(values) // 2]) / max(len(values) // 2, 1)
    second_half = sum(values[len(values) // 2:]) / max(len(values) - len(values) // 2, 1)
    change = second_half - first_half
    pct = (change / first_half * 100) if first_half > 0 else 0
    direction = "improving" if change > 1 else ("declining" if change < -1 else "stable")
    return {"direction": direction, "change": round(change, 1), "percentage": round(pct, 1)}


def _compute_trend_inv(values):
    """Trend where lower is better."""
    if len(values) < 2:
        return {"direction": "stable", "change": 0, "percentage": 0}
    first_half = sum(values[:len(values) // 2]) / max(len(values) // 2, 1)
    second_half = sum(values[len(values) // 2:]) / max(len(values) - len(values) // 2, 1)
    change = second_half - first_half
    direction = "improving" if change < -0.5 else ("declining" if change > 0.5 else "stable")
    return {"direction": direction, "change": round(change, 2), "percentage": 0}


@router.get("/interviews/compare")
async def compare_interviews(
    id1: int = Query(...),
    id2: int = Query(...),
    db: Session = Depends(get_db),
):
    """Compare two interviews."""
    i1 = db.query(Interview).filter(Interview.id == id1).first()
    i2 = db.query(Interview).filter(Interview.id == id2).first()

    if not i1 or not i2:
        raise HTTPException(status_code=404, detail="One or both interviews not found")

    metrics = [
        ("overall_score", "Overall Score"),
        ("communication_score", "Communication"),
        ("answer_quality_score", "Answer Quality"),
        ("clarity_score", "Clarity"),
        ("fluency_score", "Fluency"),
        ("speaking_pace_score", "Speaking Pace"),
        ("confidence_score", "Confidence"),
        ("vocabulary_score", "Vocabulary"),
        ("relevance_score", "Relevance"),
        ("professionalism_score", "Professionalism"),
        ("nonverbal_score", "Visual Presentation"),
        ("filler_rate", "Filler Rate"),
        ("words_per_minute", "Speaking Pace (WPM)"),
        ("star_score", "STAR Score"),
    ]

    comparison = []
    for key, label in metrics:
        v1 = getattr(i1, key, None)
        v2 = getattr(i2, key, None)
        if v1 is not None and v2 is not None:
            diff = round(v2 - v1, 2)
            improved = diff > 0 if key != "filler_rate" else diff < 0
            comparison.append({
                "metric": label,
                "key": key,
                "interview_1": v1,
                "interview_2": v2,
                "difference": diff,
                "improved": improved,
            })

    return {
        "interview_1": {"id": i1.id, "title": i1.title, "created_at": i1.created_at.isoformat() if i1.created_at else ""},
        "interview_2": {"id": i2.id, "title": i2.title, "created_at": i2.created_at.isoformat() if i2.created_at else ""},
        "comparison": comparison,
    }
