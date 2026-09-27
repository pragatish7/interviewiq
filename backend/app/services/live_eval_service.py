"""
Live Interview answer evaluation service.

Scores a candidate's spoken answer against the dataset's reference answer using
semantic/NLP comparison (TF-IDF + cosine similarity, keyword-concept overlap,
completeness) — NOT exact string matching. Speech delivery metrics reuse the
same helpers the video-analysis pipeline uses (filler words, pauses, pace).
"""
import re
import math
import logging
from typing import Dict, Any, List, Optional

from app.ml.answer_features import extract_features_from_answer
from app.ml import live_bridge

logger = logging.getLogger(__name__)

# Filler words — same list the existing speech pipeline uses.
FILLER_WORDS = [
    "um", "uh", "umm", "uhh", "err", "erm",
    "like", "basically", "actually", "you know",
    "i mean", "so", "right", "well",
]

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "dare",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
    "us", "them", "my", "your", "his", "its", "our", "their", "this",
    "that", "these", "those", "am", "so", "if", "then", "than", "too",
    "very", "just", "about", "also", "how", "what", "when", "where",
    "why", "who", "which", "while", "into", "through", "during", "before",
    "after", "above", "below", "between", "same", "such", "own", "other",
    "regarding", "regards", "overall", "there", "their", "here",
}

_HEDGE_PHRASES = ["i think", "i guess", "maybe", "sort of", "kind of", "i suppose", "probably", "not sure", "not confident"]
_IMPORTANT_MISSING_NOTE = "Try to touch on the core idea even if briefly."


def _tokens(text: str) -> List[str]:
    return [w for w in re.split(r"[^a-z0-9+#]+", (text or "").lower()) if w]


def _content_tokens(text: str) -> List[str]:
    return [t for t in _tokens(text) if t not in STOP_WORDS and len(t) > 1]


def _trigrams(text: str) -> set:
    toks = _tokens(text)
    if len(toks) < 3:
        return set()
    return {" ".join(toks[i:i + 3]) for i in range(len(toks) - 2)}


def _overlap(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = a & b
    return len(inter) / min(len(a), len(b))


# ---------------------------------------------------------------------------
# Semantic similarity (graceful: TF-IDF+cosine when sklearn is available,
# token-set cosine otherwise).
# ---------------------------------------------------------------------------

def semantic_similarity(candidate: str, reference: str) -> float:
    """0..1 semantic similarity between the spoken answer and the reference."""
    cand, ref = (candidate or "").strip(), (reference or "").strip()
    if not cand or not ref:
        return 0.0
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        try:
            vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
            m = vec.fit_transform([cand, ref])
            return float(max(0.0, min(1.0, cosine_similarity(m[0], m[1])[0][0])))
        except ValueError:
            return 0.0
    except Exception:
        # Degraded mode: token-set cosine without sklearn.
        a, b = _content_tokens(cand), _content_tokens(ref)
        if not a or not b:
            return 0.0
        from collections import Counter
        ca, cb = Counter(a), Counter(b)
        dot = sum(ca[w] * cb.get(w, 0) for w in ca)
        na = math.sqrt(sum(v * v for v in ca.values()))
        nb = math.sqrt(sum(v * v for v in cb.values()))
        return dot / (na * nb) if na and nb else 0.0


from app.services import live_dataset_service as ds

_QUESTION_WEIGHT = 2.5  # question terms name the topic — they matter most


def concept_space(question_text: str, reference: str) -> Dict[str, float]:
    """IDF-weighted concept space for a question: its topic terms (from the
    question) plus the reference answer's terms.

    IDF comes from the dataset corpus, so template boilerplate that repeats in
    every graded answer ('this is a fundamental concept...') is down-weighted,
    while question-specific concepts ('overloading', 'parameter', 'compile')
    dominate. Returns {concept: weight}.
    """
    idf = ds.term_idf()
    space: Dict[str, float] = {}
    for t in ds.normed_set(question_text):
        space[t] = space.get(t, 0.0) + _QUESTION_WEIGHT * idf.get(t, 1.0)
    for t in ds.normed_set(reference):
        space[t] = space.get(t, 0.0) + 1.0 * idf.get(t, 1.0)
    return space


def space_coverage(text: str, space: Dict[str, float]) -> float:
    """Weighted share of the concept space covered by `text` (0..1)."""
    if not space:
        return 0.0
    have = ds.normed_set(text)
    hit = sum(w for k, w in space.items() if k in have)
    total = sum(space.values())
    return hit / total if total else 0.0


def top_concepts(space: Dict[str, float], n: int = 8) -> List[str]:
    """The most informative concepts of a question, weight-descending."""
    return [k for k, _ in sorted(space.items(), key=lambda kv: kv[1], reverse=True)[:n]]


def concept_coverage(candidate: str, reference: str) -> float:
    """Share of the reference's meaningful concepts present in the answer."""
    ref_terms = [t for t in _content_tokens(reference) if len(t) > 2]
    if not ref_terms:
        return 0.0
    cand_set = ds.normed_set(candidate)
    hit = sum(1 for t in ref_terms if ds.norm(t) in cand_set)
    return hit / len(ref_terms)


def keyword_hits(candidate: str, reference: str, top_n: int = 8) -> List[str]:
    """Reference keywords the candidate did and didn't cover."""
    from collections import Counter
    ref_terms = [t for t in _content_tokens(reference) if len(t) > 2]
    top = [t for t, _ in Counter(ref_terms).most_common(top_n * 2)]
    seen, ordered = set(), []
    for t in top:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    cand_set = set(_content_tokens(candidate))
    return [t for t in ordered[:top_n]]


def split_hits_misses(candidate: str, reference: str, top_n: int = 8):
    keywords = keyword_hits(candidate, reference, top_n)
    cand_set = set(_content_tokens(candidate))
    hits = [k for k in keywords if k in cand_set]
    misses = [k for k in keywords if k not in cand_set]
    return hits, misses


# ---------------------------------------------------------------------------
# Speech metrics — reuse existing pipeline helpers where possible.
# ---------------------------------------------------------------------------

def _filler_analysis(text: str, duration_s: float) -> Dict[str, Any]:
    words = _tokens(text)
    total = len(words)
    counts: Dict[str, int] = {}
    filler_count = 0
    for w in words:
        for f in FILLER_WORDS:
            if w == f or (w == f + "s" and f != "s"):
                counts[w] = counts.get(w, 0) + 1
                filler_count += 1
                break
    minutes = max(duration_s, 1.0) / 60.0
    rate = filler_count / minutes if minutes > 0 else 0.0
    # Same scoring band as the existing pipeline.
    if rate == 0:
        score = 100
    elif rate < 2:
        score = 90
    elif rate < 5:
        score = 75
    elif rate < 10:
        score = 60
    elif rate < 15:
        score = 45
    else:
        score = 30
    wpm = round(total / minutes) if minutes > 0 else 0
    # Same pace band as scoring_service.compute_speaking_pace_score.
    if 120 <= wpm <= 160:
        pace_score = 95
    elif 100 <= wpm <= 180:
        pace_score = 85
    elif 90 <= wpm <= 200:
        pace_score = 70
    elif 70 <= wpm <= 219:
        pace_score = 55
    else:
        pace_score = 40
    return {
        "count": filler_count,
        "most_frequent": counts,
        "rate_per_minute": round(rate, 2),
        "percentage": round(filler_count / total * 100, 2) if total else 0.0,
        "score": score,
        "words_per_minute": wpm,
        "pace_score": pace_score,
        "word_count": total,
    }


def _structure_score(text: str) -> float:
    """0..100 — connectors, definitional openings, hedging penalty."""
    lower = (text or "").lower()
    words = _tokens(lower)
    if not words:
        return 40.0
    connectors = sum(1 for w in words if w in {"because", "however", "therefore", "first", "second", "then", "finally", "additionally", "moreover", "whereas", "while", "for", "example", "instance", "in", "practice"})
    definition_bonus = 15 if re.search(r"\b(is|are|means|refers|allows|enables|works by)\b", lower) else 0
    hedge_penalty = sum(lower.count(p) * 6 for p in _HEDGE_PHRASES)
    length_score = min(25.0, len(words) / 2.0)
    return max(0.0, min(100.0, 40 + connectors * 4 + definition_bonus + length_score - hedge_penalty))


def _score_feedback_text(sim: float, coverage: float, word_count: int) -> str:
    """Mirror the dataset feedback tone, based on where the answer lands."""
    if sim >= 0.55 and coverage >= 0.55:
        return "The answer is comprehensive, accurate, clearly articulated, and demonstrates strong conceptual understanding."
    if sim >= 0.35 or coverage >= 0.4:
        return "The answer is mostly accurate and well-structured, with only minor gaps in completeness or clarity."
    if sim >= 0.2 or coverage >= 0.25:
        return "The answer covers the basics correctly but misses finer details, could be more precise, and lacks depth in explanation."
    if word_count < 8 or sim < 0.08:
        return "The answer is largely irrelevant or incorrect, shows little to no understanding of the core concept, and needs significant improvement."
    return "The answer shows partial understanding but contains factual errors, is poorly structured, and lacks sufficient detail."


def _grade_label(final_score: float) -> str:
    if final_score >= 85:
        return "Very Good"
    if final_score >= 70:
        return "Good"
    if final_score >= 55:
        return "Average"
    if final_score >= 35:
        return "Poor"
    return "Very Poor"


def evaluate_answer(
    question: Dict[str, Any],
    candidate_answer: str,
    duration_s: float = 0.0,
    grades: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Score one spoken answer against its dataset reference.

    Returns the full per-question result dict stored in the session.
    """
    reference = (question.get("expected_answer") or "").strip()
    cand = (candidate_answer or "").strip()
    grades = grades or question.get("grades") or {}

    sim = semantic_similarity(cand, reference)
    space = concept_space(question.get("question", ""), reference)
    words = _tokens(cand)
    word_count = len(words)
    duration = max(duration_s, 0.5)
    completeness_raw = min(1.0, word_count / 50.0)  # ~50 words ≈ a full spoken answer

    # Must-hit concepts: the question's own (IDF-weighted) terms are the
    # ground truth of what's being asked. This dataset's graded reference
    # answers are largely template boilerplate, so the question text — not the
    # reference — is the reliable anchor. Distinctive reference terms top it
    # up when the question alone is thin.
    q_terms = list(ds.normed_set(question.get("question", "")))
    idf = ds.term_idf()
    q_terms.sort(key=lambda t: -(2.5 * idf.get(t, 1.0)))
    must_terms = q_terms[:12]
    if len(must_terms) < 8:
        ref_terms = sorted(
            ds.normed_set(reference),
            key=lambda t: -idf.get(t, 1.0),
        )
        for t in ref_terms:
            if t not in must_terms:
                must_terms.append(t)
            if len(must_terms) >= 10:
                break
    must = {t: (2.5 if t in q_terms else 1.0) * idf.get(t, 1.0) for t in must_terms}

    relevance_raw = space_coverage(cand, must)

    # Self-calibration: the reference's own coverage of the must-set sets the
    # scale. When a reference is template boilerplate that barely echoes the
    # question, matching IT counts as full relevance instead of being punished
    # by an unreachable denominator.
    ref_cov = space_coverage(reference, must)
    denom = max(0.5, ref_cov)
    relevance = min(1.0, relevance_raw / denom)

    # Topical gate: the answer must engage with the question's key term(s) —
    # unless the reference itself doesn't (boilerplate references can't be
    # held against the candidate).
    key_terms = must_terms[:3]
    have = ds.normed_set(cand)
    ref_have = ds.normed_set(reference)
    topical = any(k in have for k in key_terms) or not any(k in ref_have for k in key_terms)

    # Length gate: an ultra-short or silent answer cannot score well even if
    # a couple of tokens collide with the reference.
    if word_count < 3:
        length_gate = 0.25
    elif word_count < 10:
        length_gate = 0.6
    elif word_count < 20:
        length_gate = 0.85
    else:
        length_gate = 1.0

    structure = _structure_score(cand)
    base = 100.0 * (
        relevance * 0.40
        + sim * 0.20
        + completeness_raw * 0.25
        + min(1.0, structure / 85.0) * 0.15
    )
    if topical:
        base = min(100.0, base + 8.0)  # reward engaging with the asked topic
    else:
        base = min(base, 35.0)  # answering a different question
    score = base * length_gate
    coverage = relevance_raw

    final = max(0.0, min(100.0, round(score, 1)))
    hits, misses = split_hits_misses(cand, f"{question.get('question', '')} {reference}", 6)

    filler = _filler_analysis(cand, duration)
    per_min = word_count / (duration / 60.0)
    clarity = round(min(100.0, 45 + structure * 0.35 + (15 if per_min >= 90 else 0) - (8 if filler["count"] > 6 else 0)), 1)

    # ML cross-check: the trained model (see training/) scores the SAME
    # features it was trained on. Purely additive transparency — the
    # rule-based `final` above remains the authoritative score.
    grade_texts = {
        label: (g or {}).get("answer_text", "")
        for label, g in (grades or {}).items()
    } if grades else None
    feats = extract_features_from_answer(
        cand, question.get("question", ""), reference,
        duration_s=duration_s, grade_texts=grade_texts,
    )
    ml = live_bridge.predict_answer_score(feats["features"])

    return {
        "question_id": question.get("question_id", ""),
        "question": question.get("question", ""),
        "category": question.get("category", ""),
        "difficulty": question.get("difficulty", ""),
        "candidate_answer": cand,
        "expected_answer": reference,
        "answer_score": final,
        "answer_score_10": round(final / 10, 1),
        "grade_label": _grade_label(final),
        "semantic_similarity": round(sim, 3),
        "concept_coverage": round(coverage, 3),
        "completeness": round(completeness_raw, 3),
        "duration_s": round(duration_s, 1),
        "words": word_count,
        "keywords_hit": hits,
        "keywords_missed": misses,
        "structure": round(structure, 1),
        "speech": filler,
        "clarity": clarity,
        "hedges": sum((cand or "").lower().count(p) for p in _HEDGE_PHRASES),
        "feedback": _score_feedback_text(sim, coverage, word_count),
        "key_points_missing": [f"Explain: {m}" for m in misses[:3]] or [_IMPORTANT_MISSING_NOTE],
        "ml_prediction": {
            "available": ml.get("available", False),
            "predicted_score": ml.get("predicted_score"),
            "model_version": ml.get("model_version"),
            "model_type": ml.get("model_type"),
        },
    }


# ---------------------------------------------------------------------------
# Session-level aggregation
# ---------------------------------------------------------------------------

def aggregate_session(results: List[Dict[str, Any]], sessions_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Aggregate per-question results into the final live-interview report."""
    results = results or []
    meta = sessions_meta or {}

    n = len(results)
    if n == 0:
        return {
            "question_results": [],
            "overall_score": 0.0,
            "technical_score": 0.0,
            "communication_score": 0.0,
            "speech_score": 0.0,
            "strengths": ["No questions were answered in this session."],
            "areas_for_improvement": ["Complete a full session to get meaningful feedback."],
            "overall_feedback": "The session ended without any recorded answers.",
            "fillers_total": 0,
            "words_per_minute": 0.0,
            "pauses_total": 0,
            "pause_seconds_total": 0.0,
            "categories": [],
        }

    answer_scores = [r["answer_score"] for r in results]
    overall = sum(answer_scores) / n

    # Communication from structure + clarity + low hedging across answers.
    structure = sum(r["structure"] for r in results) / n
    clarity = sum(r["clarity"] for r in results) / n
    hedges = sum(r["hedges"] for r in results) / n
    communication = 0.5 * structure + 0.3 * clarity + max(0.0, 100 - hedges * 8) * 0.2

    # Speech score from fillers + pace (same bands as the video pipeline).
    filler_scores = [r["speech"]["score"] for r in results]
    pace_scores = [r["speech"]["pace_score"] for r in results]
    speech_score = (sum(filler_scores) / n) * 0.6 + (sum(pace_scores) / n) * 0.4

    # Technical answer quality — the content dimension only.
    technical = overall * 0.85 + min(20.0, sum(r["semantic_similarity"] for r in results) / n * 20) * 0.75

    # Pauses: user-marked silent gaps between answers (frontend-timed).
    pauses_total = int(meta.get("pause_count") or 0)
    pause_seconds = float(meta.get("pause_seconds_total") or 0.0)

    total_words = sum(r["words"] for r in results)
    total_duration = sum(r["duration_s"] for r in results) or 1.0
    session_wpm = round(total_words / (total_duration / 60.0)) if total_duration > 0 else 0

    strengths, improvements = [], []
    avg_sim = sum(r["semantic_similarity"] for r in results) / n
    avg_cov = sum(r["concept_coverage"] for r in results) / n
    filler_total = sum(r["speech"]["count"] for r in results)
    filler_rate = sum(r["speech"]["rate_per_minute"] for r in results) / n

    if avg_sim >= 0.45:
        answers_strength = f"Answers align closely with expected technical content (avg. similarity {avg_sim:.0%})"
        strengths.append(answers_strength)
    elif avg_sim < 0.2:
        improvements.append("Deepen conceptual understanding — answers diverged from expected technical content")

    if avg_cov >= 0.5:
        strengths.append(f"Consistently covered the key concepts interviewers look for ({avg_cov:.0%} concept coverage)")
    else:
        improvements.append("Hit the core concepts of each question more directly before elaborating")

    if 120 <= session_wpm <= 160:
        strengths.append(f"Excellent speaking pace ({session_wpm} WPM — in the ideal 120–160 range)")
    elif session_wpm < 120:
        improvements.append(f"Speaking pace is slow ({session_wpm} WPM). Aim for 120–160 WPM")
    elif session_wpm > 180:
        improvements.append(f"Speaking pace is fast ({session_wpm} WPM). Slow down for clarity")

    if filler_total == 0:
        strengths.append("Zero filler words across the whole session")
    elif filler_rate < 3:
        strengths.append(f"Low filler-word usage ({filler_total} total, ~{filler_rate:.1f}/min)")
    elif filler_rate < 8:
        improvements.append(f"Reduce filler words ({filler_total} total, ~{filler_rate:.1f}/min) — pause silently instead")
    else:
        improvements.append(f"High filler-word usage ({filler_total} total, ~{filler_rate:.1f}/min) — practice replacing them with pauses")

    if hedges <= 1:
        strengths.append("Confident, decisive phrasing with minimal hedging")
    elif hedges >= 4:
        improvements.append("Reduce hedging phrases like 'I think' or 'maybe' — state what you know")

    if pauses_total > 6:
        improvements.append(f"Long silent gaps between answers ({pauses_total} pauses totalling {pause_seconds:.0f}s) — start speaking sooner")

    # Weak questions → targeted improvement items.
    weak = sorted(results, key=lambda r: r["answer_score"])[:2]
    for r in weak:
        if r["answer_score"] < 65:
            improvements.append(f"Review '{r['category']}' — '{r['question'][:60]}...' scored {r['answer_score']:.0f}/100")

    if len(strengths) < 2:
        strengths.append("Completed a live, timed interview session")
    if len(improvements) < 2:
        improvements.append("Practice explaining core concepts aloud with a timer")

    # Overall feedback mirrors the dataset feedback style.
    if overall >= 85:
        overall_fb = "Comprehensive, accurate, clearly articulated performance demonstrating strong conceptual understanding across topics."
    elif overall >= 70:
        overall_fb = "Mostly accurate and well-structured performance with only minor gaps in completeness or clarity."
    elif overall >= 55:
        overall_fb = "Covers the basics correctly but misses finer details; more precision and depth are needed."
    elif overall >= 35:
        overall_fb = "Shows partial understanding but answers were poorly structured and lacked sufficient detail."
    else:
        overall_fb = "Largely irrelevant or incorrect responses showing little understanding of the core concepts — significant practice needed."

    return {
        "question_results": results,
        "overall_score": round(overall, 1),
        "technical_score": round(max(0.0, min(100.0, technical)), 1),
        "communication_score": round(max(0.0, min(100.0, communication)), 1),
        "speech_score": round(max(0.0, min(100.0, speech_score)), 1),
        "fillers_total": filler_total,
        "words_per_minute": session_wpm,
        "pauses_total": pauses_total,
        "pause_seconds_total": round(pause_seconds, 1),
        "total_words": total_words,
        "total_duration_s": round(total_duration, 1),
        "categories": sorted({r["category"] for r in results}),
        "strengths": strengths[:5],
        "areas_for_improvement": improvements[:5],
        "overall_feedback": overall_fb,
    }
