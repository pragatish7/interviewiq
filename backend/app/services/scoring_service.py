"""
Scoring service - combines all analysis dimensions into holistic scores.
Generates personalized coaching, improvement plans, and actionable feedback.
"""
import math
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "communication": 0.15,
    "answer_quality": 0.20,
    "clarity": 0.10,
    "fluency": 0.10,
    "speaking_pace": 0.10,
    "confidence": 0.10,
    "relevance": 0.10,
    "vocabulary": 0.05,
    "professionalism": 0.05,
    "nonverbal": 0.05,
}


def compute_speaking_pace_score(wpm: float) -> float:
    """
    Score speaking pace.
    Optimal: 120-160 WPM for interviews.
    """
    if 120 <= wpm <= 160:
        return 95
    elif 100 <= wpm <= 180:
        return 85
    elif 90 <= wpm <= 200:
        return 70
    elif 70 <= wpm <= 220:
        return 55
    else:
        return 40


def compute_communication_score(content: Dict, speech: Dict) -> float:
    """Compute communication score from content and speech analysis."""
    clarity = content.get("clarity_score", 70)
    fluency = content.get("fluency_score", 70)
    conciseness = content.get("conciseness_score", 70)
    professionalism = content.get("professionalism_score", 70)

    filler_score = speech.get("filler_words", {}).get("score", 70)
    delivery = speech.get("delivery", {}).get("score", 70)

    score = (
        clarity * 0.25 +
        fluency * 0.20 +
        conciseness * 0.20 +
        professionalism * 0.15 +
        filler_score * 0.10 +
        delivery * 0.10
    )
    return round(min(100, max(0, score)), 1)


def compute_answer_quality_score(qa_analyses: List[Dict]) -> float:
    """Compute overall answer quality from per-question analyses."""
    if not qa_analyses:
        return 60.0

    scores = []
    for qa in qa_analyses:
        if qa.get("overall_answer_score") is not None:
            scores.append(qa["overall_answer_score"])
        elif qa.get("answer") and len(qa["answer"]) > 20:
            # Compute a basic score
            answer_text = qa["answer"]
            word_count = len(answer_text.split())
            has_structure = any(w in answer_text.lower() for w in
                               ["first", "second", "then", "additionally", "however", "because"])
            word_score = min(100, word_count * 2) if word_count < 50 else max(60, 100 - (word_count - 50))
            structure_bonus = 10 if has_structure else 0
            scores.append(min(100, word_score + structure_bonus))

    if not scores:
        return 60.0
    return round(sum(scores) / len(scores), 1)


def compute_confidence_score(
    speech: Dict,
    content: Dict,
    delivery: Dict,
) -> float:
    """Compute confidence/delivery score from observable indicators."""
    filler_score = speech.get("filler_words", {}).get("score", 70)
    pause_score = speech.get("pauses", {}).get("score", 70)
    delivery_score = delivery.get("score", 70)
    pace_consistency = delivery.get("pace_consistency", 0.7)
    answer_completeness = content.get("fluency_score", 70)

    score = (
        filler_score * 0.25 +
        pause_score * 0.20 +
        delivery_score * 0.25 +
        pace_consistency * 30 +
        answer_completeness * 0.10
    )
    return round(min(100, max(0, score)), 1)


def compute_vocabulary_score(content: Dict) -> float:
    """Compute vocabulary score."""
    diversity = content.get("vocabulary_diversity", 0.5)
    repetition = content.get("repetition_rate", 0.2)
    keywords = len(content.get("keywords", []))

    diversity_score = min(100, diversity * 120)
    repetition_penalty = min(30, repetition * 100)
    keyword_bonus = min(20, keywords * 2)

    score = diversity_score - repetition_penalty + keyword_bonus + 20
    return round(min(100, max(0, score)), 1)


def compute_relevance_score(qa_analyses: List[Dict], content: Dict) -> float:
    """Compute content relevance score."""
    if qa_analyses:
        relevance_scores = [qa.get("relevance_score", 70) for qa in qa_analyses if qa.get("relevance_score")]
        if relevance_scores:
            avg_relevance = sum(relevance_scores) / len(relevance_scores)
            return round(avg_relevance, 1)

    # Fallback estimation
    sentiment = content.get("sentiment", 0)
    prof_score = content.get("professionalism_score", 70)
    return round(min(100, prof_score + sentiment * 10), 1)


def compute_nonverbal_score(video_analysis: Dict) -> float:
    """Compute non-verbal/visual presentation score."""
    face_vis = video_analysis.get("face_visibility", 70)
    camera_pres = video_analysis.get("camera_presence", 70)
    head_mov = video_analysis.get("head_movement_score", 70)
    framing = video_analysis.get("framing_score", 70)

    score = (
        face_vis * 0.30 +
        camera_pres * 0.30 +
        head_mov * 0.20 +
        framing * 0.20
    )
    return round(min(100, max(0, score)), 1)


def compute_overall_score(scores: Dict[str, float], weights: Optional[Dict[str, float]] = None) -> float:
    """Compute weighted overall score."""
    w = weights or DEFAULT_WEIGHTS
    total = 0.0
    weight_sum = 0.0

    key_mapping = {
        "communication": "communication_score",
        "answer_quality": "answer_quality_score",
        "clarity": "clarity_score",
        "fluency": "fluency_score",
        "speaking_pace": "speaking_pace_score",
        "confidence": "confidence_score",
        "relevance": "relevance_score",
        "vocabulary": "vocabulary_score",
        "professionalism": "professionalism_score",
        "nonverbal": "nonverbal_score",
    }

    for key, weight in w.items():
        score_key = key_mapping.get(key, key)
        if score_key in scores and scores[score_key] is not None:
            total += scores[score_key] * weight
            weight_sum += weight

    if weight_sum == 0:
        return 50.0
    return round(total / weight_sum, 1)


def generate_coaching_feedback(
    scores: Dict[str, float],
    speech: Dict,
    content: Dict,
    qa_analyses: List[Dict],
    video_analysis: Dict,
) -> Dict[str, Any]:
    """Generate personalized coaching feedback."""
    strengths = []
    improvements = []

    # Communication strengths/improvements
    if scores.get("communication_score", 0) >= 80:
        strengths.append("Strong overall communication with clear expression")
    elif scores.get("communication_score", 0) >= 60:
        strengths.append("Solid communication foundation")
    else:
        improvements.append("Focus on clearer expression and more structured responses")

    # Filler words
    filler_count = speech.get("filler_words", {}).get("count", 0)
    filler_rate = speech.get("filler_words", {}).get("rate_per_minute", 0)
    if filler_rate == 0:
        strengths.append("Excellent control - no filler words detected")
    elif filler_rate < 3:
        strengths.append(f"Low filler word usage ({filler_count} total, {filler_rate}/min)")
    elif filler_rate < 8:
        improvements.append(f"Reduce filler words ({filler_count} detected, {filler_rate}/min). Practice pausing instead of saying 'um' or 'uh'")
    else:
        improvements.append(f"Significant filler word usage ({filler_count} total, {filler_rate}/min). Practice replacing fillers with brief pauses")

    # Speaking pace
    wpm = speech.get("words_per_minute", 0)
    if 120 <= wpm <= 160:
        strengths.append(f"Good speaking pace ({wpm} WPM, optimal range)")
    elif wpm < 120:
        improvements.append(f"Speaking pace is slightly slow ({wpm} WPM). Try to speak a bit more fluidly (target: 120-160 WPM)")
    else:
        improvements.append(f"Speaking pace is fast ({wpm} WPM). Slowing down slightly improves comprehension (target: 120-160 WPM)")

    # Answer quality
    if qa_analyses:
        avg_quality = sum(
            qa.get("overall_answer_score", 70) for qa in qa_analyses
        ) / len(qa_analyses)
        if avg_quality >= 80:
            strengths.append("Strong answer quality with well-structured responses")
        elif avg_quality >= 65:
            strengths.append("Good answer foundation with room for more depth")
        else:
            improvements.append("Focus on providing more detailed, structured answers with specific examples")

    # STAR analysis
    star_scores = [qa.get("star_score", 0) for qa in qa_analyses if qa.get("star_score") is not None]
    if star_scores:
        avg_star = sum(star_scores) / len(star_scores)
        if avg_star < 50:
            improvements.append("Use the STAR framework (Situation, Task, Action, Result) for behavioral questions")
        elif avg_star >= 80:
            strengths.append("Good use of STAR framework in behavioral responses")

    # Vocabulary
    vocab_diversity = content.get("vocabulary_diversity", 0.5)
    if vocab_diversity >= 0.7:
        strengths.append("Excellent vocabulary diversity showing strong language skills")
    elif vocab_diversity < 0.4:
        improvements.append("Expand vocabulary variety to demonstrate stronger communication skills")

    # Repetition
    repetition = content.get("repetition_rate", 0)
    if repetition > 0.15:
        improvements.append("Reduce repeated words/phrases. Try using synonyms and varied sentence structures")

    # Pauses
    long_pauses = speech.get("pauses", {}).get("long_pauses", 0)
    if long_pauses > 5:
        improvements.append("Work on reducing long pauses (>2s) during responses")
    elif long_pauses == 0:
        strengths.append("No significant pauses - speech flows naturally")

    # Non-verbal
    if video_analysis.get("face_visibility", 0) < 50:
        improvements.append("Ensure face is visible and well-lit on camera")

    if video_analysis.get("excessive_movement", False):
        improvements.append("Minimize excessive head/body movement for better camera presence")

    # Ensure minimum feedback
    if len(strengths) < 3:
        default_strengths = [
            "Completed the interview session",
            "Demonstrated willingness to practice",
            "Provided substantive responses",
        ]
        strengths.extend(default_strengths[:3 - len(strengths)])

    if len(improvements) < 3:
        default_improvements = [
            "Practice answering behavioral questions with STAR method",
            "Record yourself and review for pacing and clarity",
            "Prepare more specific examples with measurable outcomes",
        ]
        improvements.extend(default_improvements[:3 - len(improvements)])

    return {
        "strengths": strengths[:5],
        "improvements": improvements[:5],
        "overall_assessment": generate_overall_assessment(scores),
    }


def generate_overall_assessment(scores: Dict[str, float]) -> str:
    """Generate overall assessment text."""
    overall = scores.get("communication_score", 70)
    if overall >= 90:
        return ("Excellent interview performance! Your communication is clear and confident, "
                "answers are well-structured, and you demonstrate strong professional presence.")
    elif overall >= 80:
        return ("Strong interview performance. You communicate well with good structure. "
                "Focus on reducing filler words and adding more specific examples to reach the next level.")
    elif overall >= 70:
        return ("Good interview foundation. You show solid communication skills. "
                "Work on answer structure, pace consistency, and incorporating STAR responses for behavioral questions.")
    elif overall >= 60:
        return ("Fair interview performance with room for improvement. "
                "Focus on reducing fillers, maintaining steady pace, and structuring answers with clear examples.")
    else:
        return ("Your interview skills need practice. Focus on basic communication fundamentals: "
                "speaking pace, reducing fillers, and structuring answers clearly.")


def generate_improvement_plan(scores: Dict[str, float], speech: Dict, content: Dict) -> List[Dict[str, Any]]:
    """Generate a 7-day improvement plan."""
    filler_rate = speech.get("filler_words", {}).get("rate_per_minute", 5)
    wpm = speech.get("words_per_minute", 140)
    star_scores = content.get("avg_star_score", 50)

    plan = [
        {
            "day": 1,
            "title": "Reduce Filler Words",
            "focus": f"Current rate: {filler_rate}/min",
            "exercise": "Practice answering 10 common interview questions. "
                       "When you feel 'um' or 'uh' coming, take a 1-second pause instead. "
                       "Record yourself and count fillers.",
            "target": "Reduce filler rate by 50%",
            "duration": "30 minutes",
        },
        {
            "day": 2,
            "title": "Practice Concise Answers",
            "focus": "Answer clarity and structure",
            "exercise": "Answer each question in under 2 minutes. "
                       "Use the format: Direct answer → Evidence → Takeaway. "
                       "Review recordings for unnecessary tangents.",
            "target": "Average answer length 60-90 seconds",
            "duration": "45 minutes",
        },
        {
            "day": 3,
            "title": "STAR Responses",
            "focus": "Behavioral interview mastery",
            "exercise": "Prepare 5 STAR stories covering: leadership, conflict resolution, "
                       "failure, teamwork, and achievement. Write them out, then practice verbally.",
            "target": "Include all 4 STAR components in every behavioral answer",
            "duration": "60 minutes",
        },
        {
            "day": 4,
            "title": "Speaking Pace Control",
            "focus": f"Current pace: {wpm} WPM (target: 120-160)",
            "exercise": "Read a passage aloud at 140 WPM using a metronome app. "
                       "Then practice answering questions at this pace. "
                       "Focus on consistent rhythm.",
            "target": "Maintain 120-160 WPM consistently",
            "duration": "30 minutes",
        },
        {
            "day": 5,
            "title": "Technical & Domain Explanations",
            "focus": "Clear technical communication",
            "exercise": "Practice explaining 3 technical concepts as if to a non-technical person. "
                       "Focus on clarity, structure, and avoiding jargon overload.",
            "target": "Clear, accessible technical explanations",
            "duration": "45 minutes",
        },
        {
            "day": 6,
            "title": "Full Mock Interview",
            "focus": "Integrated practice",
            "exercise": "Record a complete 30-minute mock interview answering 8-10 questions. "
                       "Include behavioral, technical, and general questions.",
            "target": "Apply all skills from Days 1-5",
            "duration": "60 minutes",
        },
        {
            "day": 7,
            "title": "Re-analysis & Review",
            "focus": "Measure progress",
            "exercise": "Upload your Day 6 recording to InterviewIQ. "
                       "Compare scores with your original analysis. "
                       "Identify remaining areas for improvement.",
            "target": "Score improvement of 10+ points",
            "duration": "30 minutes",
        },
    ]
    return plan


def generate_timeline_events(
    speech: Dict,
    qa_analyses: List[Dict],
    content: Dict,
) -> List[Dict[str, Any]]:
    """Generate timestamped timeline events."""
    events = []

    # Add filler word events
    for filler in speech.get("filler_words", {}).get("instances", [])[:20]:
        events.append({
            "timestamp": filler.get("start", 0),
            "type": "filler",
            "severity": "warning",
            "description": f"Filler word: \"{filler['word']}\"",
            "icon": "alert-circle",
        })

    # Add long pause events
    for pause in speech.get("pauses", {}).get("pause_events", []):
        if pause.get("duration", 0) > 2.0:
            events.append({
                "timestamp": pause.get("start", 0),
                "type": "pause",
                "severity": "info",
                "description": f"Long pause ({pause['duration']}s)",
                "icon": "pause-circle",
            })

    # Add QA score events
    for qa in qa_analyses:
        if qa.get("overall_answer_score"):
            score = qa["overall_answer_score"]
            events.append({
                "timestamp": qa.get("start", 0),
                "type": "answer",
                "severity": "success" if score >= 75 else ("warning" if score >= 55 else "error"),
                "description": f"Answer quality: {score}/100 - {qa.get('question_category', 'general')}",
                "icon": "check-circle" if score >= 75 else "alert-triangle",
            })

    events.sort(key=lambda x: x.get("timestamp", 0))
    return events[:50]
