"""
Answer-level feature extraction — SINGLE SOURCE OF TRUTH.

The exact same feature functions are used by:
  * the training pipeline (training/extract_features.py) on the labeled
    mock-interview dataset (and on annotated video transcripts), and
  * the Live Interview evaluator (live_eval_service) at prediction time.

This guarantees train/serve feature parity: the model is never trained on one
feature set and served another.

Design note — the core feature vector is deliberately text+timing only.
Video-only signals (face visibility, framing, ...) cannot exist for the Live
Interview path (browser mic audio, no uploadable recording), so they are
excluded from the learned model. The full-video upload flow keeps its own
richer rule-based scoring on top; the trained model blends in additively.
"""

import re
import math
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Filler words — the same list the existing speech pipeline uses
# (speech_service.FILLER_WORDS / live_eval_service.FILLER_WORDS).
FILLER_WORDS = [
    "um", "uh", "umm", "uhh", "err", "erm",
    "like", "basically", "actually", "you know",
    "i mean", "so", "right", "well",
]

_HEDGE_PHRASES = [
    "i think", "i guess", "maybe", "sort of", "kind of",
    "i suppose", "probably", "not sure", "not confident",
]

_STOP_TOKENS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "can", "this", "that", "these",
    "those", "it", "its", "there", "their", "not", "when", "where", "how",
    "what", "which", "while", "about", "into", "through", "during", "also",
    "very", "just", "other", "such", "own", "some", "more", "most",
}

# Ordered feature vector. Anything reordered here breaks old pickles —
# bump MODEL_VERSION in training/train.py when this list changes.
#
# Grade-similarity features: the dataset (and the live interview) provide 5
# graded reference answers per question (Very Poor -> Very Good). Similarity
# of the candidate to each grade is a real, computable-everywhere semantic
# signal — "which grade does this answer most resemble?" — instead of the
# degenerate answer-vs-own-reference similarity that is always 1.0 for
# reference rows. When grade texts are unavailable the features are 0.0 for
# ALL rows of that source consistently (never partially fabricated).
FEATURE_NAMES = [
    "word_count",
    "speech_duration_s",
    "words_per_minute",
    "filler_count",
    "filler_rate_per_min",
    "unique_word_ratio",
    "avg_sentence_length",
    "question_term_coverage",
    "ref_bigram_coverage",
    "semantic_similarity",
    "question_similarity",
    "structure_score",
    "hedge_count",
    "sim_very_good",
    "sim_good",
    "sim_average",
    "sim_poor",
    "sim_very_poor",
    "grade_margin",  # sim_very_good - sim_very_poor
]

_WORD_RE = re.compile(r"[a-z0-9+#]+")


def tokens(text: str) -> List[str]:
    return _WORD_RE.findall((text or "").lower())


def content_tokens(text: str) -> List[str]:
    return [t for t in tokens(text) if t not in _STOP_TOKENS and len(t) > 1]


def norm(t: str) -> str:
    """Light stemming so 'methods'/'method' and 'classes'/'class' match."""
    if len(t) > 4 and t.endswith("sses"):
        return t[:-2]
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def normed_set(text: str) -> set:
    return {norm(t) for t in content_tokens(text)}


def bigrams(text: str) -> set:
    toks = tokens(text)
    return {f"{toks[i]}_{toks[i+1]}" for i in range(len(toks) - 1)}


def semantic_similarity(candidate: str, reference: str) -> Tuple[float, str]:
    """TF-IDF (word + char n-gram) cosine similarity, 0..1.

    Returns (score, method). Method records which analyzer produced the
    score ('tfidf', 'char_ngram', 'token_cosine', 'empty') so results are
    never silently fabricated when an analyzer is unavailable.
    """
    cand, ref = (candidate or "").strip(), (reference or "").strip()
    if not cand or not ref:
        return 0.0, "empty"

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except Exception:
        return _token_cosine(cand, ref), "token_cosine"

    # Word-level unigram+bigram TF-IDF first.
    try:
        vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        m = vec.fit_transform([cand, ref])
        return float(max(0.0, min(1.0, cosine_similarity(m[0], m[1])[0][0]))), "tfidf"
    except ValueError:
        pass

    # Character n-grams are robust to ASR misspellings ("polymorfism").
    try:
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        m = vec.fit_transform([cand, ref])
        return float(max(0.0, min(1.0, cosine_similarity(m[0], m[1])[0][0]))), "char_ngram"
    except Exception:
        return _token_cosine(cand, ref), "token_cosine"


def _token_cosine(cand: str, ref: str) -> float:
    a, b = content_tokens(cand), content_tokens(ref)
    if not a or not b:
        return 0.0
    from collections import Counter
    ca, cb = Counter(a), Counter(b)
    dot = sum(ca[w] * cb.get(w, 0) for w in ca)
    na = math.sqrt(sum(v * v for v in ca.values()))
    nb = math.sqrt(sum(v * v for v in cb.values()))
    return dot / (na * nb) if na and nb else 0.0


def structure_score(text: str) -> float:
    """0..100 — connectors, definitional openings, hedging penalty.

    Mirrors live_eval_service._structure_score semantics.
    """
    lower = (text or "").lower()
    words = tokens(lower)
    if not words:
        return 40.0
    connectors = sum(
        1 for w in words
        if w in {"because", "however", "therefore", "first", "second", "then",
                 "finally", "additionally", "moreover", "whereas", "while",
                 "for", "example", "instance", "in", "practice"}
    )
    definition_bonus = 15 if re.search(r"\b(is|are|means|refers|allows|enables|works by)\b", lower) else 0
    hedge_penalty = sum(lower.count(p) * 6 for p in _HEDGE_PHRASES)
    length_score = min(25.0, len(words) / 2.0)
    return max(0.0, min(100.0, 40 + connectors * 4 + definition_bonus + length_score - hedge_penalty))


GRADE_KEYS = ["Very Good", "Good", "Average", "Poor", "Very Poor"]


def extract_features_from_answer(
    answer: str,
    question: str,
    reference: str,
    duration_s: float = 0.0,
    grade_texts: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Extract the full feature dict for one answer.

    `duration_s`: spoken duration when known (video/audio pipeline). When 0,
    duration is estimated from word count at ~140 WPM — realistic for reading
    a transcribed answer and consistent across every sample, so the WPM /
    rate features stay comparable instead of random.
    """
    answer = (answer or "").strip()
    question = (question or "").strip()
    reference = (reference or "").strip()

    words = tokens(answer)
    word_count = len(words)
    sentences = [s for s in re.split(r"[.!?]+", answer) if s.strip()]

    if duration_s and duration_s > 0:
        dur = duration_s
        duration_estimated = False
    else:
        dur = word_count / 140.0 * 60.0
        duration_estimated = True
    minutes = max(dur, 1.0) / 60.0

    filler_count = 0
    for w in words:
        for f in FILLER_WORDS:
            if w == f or (w == f + "s" and f != "s"):
                filler_count += 1
                break

    sim, sim_method = semantic_similarity(answer, reference)

    # Answer-vs-question similarity: topical relevance, computable identically
    # for reference rows and live answers (real variance in both).
    q_sim, _ = semantic_similarity(answer, question)

    # Similarity to each available grade reference (see FEATURE_NAMES note).
    grade_sims: Dict[str, float] = {}
    if grade_texts:
        for label in GRADE_KEYS:
            g_text = (grade_texts.get(label) or "").strip()
            if g_text:
                grade_sims[label] = semantic_similarity(answer, g_text)[0]
            else:
                grade_sims[label] = 0.0

    # Question term coverage — share of the question's normalized content
    # terms the answer engages with (the primary relevance signal).
    q_terms = normed_set(question)
    a_terms = normed_set(answer)
    question_term_coverage = (len(q_terms & a_terms) / len(q_terms)) if q_terms else 0.0

    # Reference bigram coverage — how much of the reference's phrasing the
    # answer shares (semantic_similarity's complement, catches detail depth).
    ref_bigrams = bigrams(reference)
    a_bigrams = bigrams(answer)
    ref_bigram_coverage = (len(ref_bigrams & a_bigrams) / len(ref_bigrams)) if ref_bigrams else 0.0

    features = {
        "word_count": word_count,
        "speech_duration_s": round(dur, 2),
        "words_per_minute": round(word_count / minutes) if minutes > 0 else 0,
        "filler_count": filler_count,
        "filler_rate_per_min": round(filler_count / minutes, 2) if minutes > 0 else 0.0,
        "unique_word_ratio": round(len(set(words)) / word_count, 4) if word_count else 0.0,
        "avg_sentence_length": round(word_count / len(sentences), 2) if sentences else 0.0,
        "question_term_coverage": round(question_term_coverage, 4),
        "ref_bigram_coverage": round(ref_bigram_coverage, 4),
        "semantic_similarity": round(sim, 4),
        "question_similarity": round(q_sim, 4),
        "structure_score": round(structure_score(answer), 2),
        "hedge_count": sum((answer or "").lower().count(p) for p in _HEDGE_PHRASES),
        "sim_very_good": round(grade_sims.get("Very Good", 0.0), 4),
        "sim_good": round(grade_sims.get("Good", 0.0), 4),
        "sim_average": round(grade_sims.get("Average", 0.0), 4),
        "sim_poor": round(grade_sims.get("Poor", 0.0), 4),
        "sim_very_poor": round(grade_sims.get("Very Poor", 0.0), 4),
        "grade_margin": round(
            grade_sims.get("Very Good", 0.0) - grade_sims.get("Very Poor", 0.0), 4
        ) if grade_sims else 0.0,
    }

    meta = {
        "similarity_method": sim_method,
        "duration_estimated": duration_estimated,
        "sentence_count": len(sentences),
    }
    return {"features": features, "meta": meta}


def vector_list(features: Dict[str, float]) -> List[float]:
    """Feature dict -> ordered list matching FEATURE_NAMES."""
    return [float(features.get(name, 0.0) or 0.0) for name in FEATURE_NAMES]
