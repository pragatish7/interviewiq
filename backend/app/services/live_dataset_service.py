"""
Live Interview dataset service.

Loads question/answer pairs from the shipped mock-interview dataset CSV
(data/mock_interview_dataset_test.csv). Each question in the dataset has five
reference answers graded Very Poor -> Very Good. For the live interview we use
the "Very Good" reference answer as the expected answer (with its graded score
available as an anchoring ceiling), and keep a couple of weaker grades so the
evaluator can calibrate "how far along the scale" a candidate's answer sits.
"""
import os
import logging
import random
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# data/ lives at the project root (same place as the SQLite DB).
_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data",
    "mock_interview_dataset_test.csv",
)

# Dataset quality grades, from worst to best reference answer.
GRADE_ORDER = ["Very Poor", "Poor", "Average", "Good", "Very Good"]

_cache: Optional[List[Dict[str, Any]]] = None


def dataset_path() -> str:
    return _DATA_PATH


def load_dataset() -> List[Dict[str, Any]]:
    """Load and group the dataset into one entry per question.

    Returns a list of dicts:
      question_id, category, difficulty, question,
      expected_answer (Very Good reference), expected_score (its final_score),
      feedback_template (evaluator-style feedback for the top grade),
      grades: {label: {answer_text, final_score, feedback}}
    """
    global _cache
    if _cache is not None:
        return _cache

    if not os.path.exists(_DATA_PATH):
        logger.warning(f"Live interview dataset not found at {_DATA_PATH}")
        _cache = []
        return _cache

    import csv

    grouped: Dict[str, Dict[str, Any]] = {}
    with open(_DATA_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = (row.get("question_id") or "").strip()
            if not qid:
                continue
            entry = grouped.get(qid)
            if entry is None:
                entry = {
                    "question_id": qid,
                    "category": (row.get("category") or "").strip(),
                    "difficulty": (row.get("difficulty") or "").strip(),
                    "question": (row.get("question") or "").strip(),
                    "grades": {},
                }
                grouped[qid] = entry
            label = (row.get("quality_label") or "").strip()
            try:
                score = float(row.get("final_score") or 0)
            except (TypeError, ValueError):
                score = 0.0
            entry["grades"][label] = {
                "answer_text": (row.get("answer_text") or "").strip(),
                "final_score": score,
                "relevance": _to_float(row.get("relevance")),
                "correctness": _to_float(row.get("correctness")),
                "clarity": _to_float(row.get("clarity")),
                "completeness": _to_float(row.get("completeness")),
                "feedback": (row.get("feedback") or "").strip(),
            }

    questions: List[Dict[str, Any]] = []
    for entry in grouped.values():
        if not entry["question"]:
            continue
        best = entry["grades"].get("Very Good") or entry["grades"].get("Good")
        if not best:
            continue
        entry["expected_answer"] = best["answer_text"]
        entry["expected_score"] = best["final_score"]
        entry["expected_feedback"] = best["feedback"]
        questions.append(entry)

    _cache = questions
    logger.info(f"Loaded {len(questions)} live interview questions from dataset")
    return _cache


def _to_float(v) -> Optional[float]:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def get_categories() -> List[str]:
    return sorted({q["category"] for q in load_dataset()})


# ---------------------------------------------------------------------------
# Tokenizer + corpus IDF (used by the evaluator to weight concepts)
# ---------------------------------------------------------------------------

def content_tokens(text: str) -> List[str]:
    """Lower-cased alphanumeric tokens with stop-words removed."""
    import re
    raw = re.split(r"[^a-z0-9+#]+", (text or "").lower())
    return [t for t in raw if t and len(t) > 1 and t not in _STOP_TOKENS]


def norm(t: str) -> str:
    """Light normalization so 'methods'/'method' and 'classes'/'class' count
    as the same concept."""
    if len(t) > 4 and t.endswith("sses"):  # classes -> class, processes -> process
        return t[:-2]
    if len(t) > 4 and t.endswith("ies"):  # entities -> entity
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def normed_set(text: str) -> set:
    return {norm(t) for t in content_tokens(text)}


_STOP_TOKENS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "can", "this", "that", "these",
    "those", "it", "its", "there", "their", "not", "when", "where", "how",
    "what", "which", "while", "about", "into", "through", "during", "also",
    "very", "just", "other", "such", "own", "some", "more", "most",
}

_idf_cache = None


def term_idf() -> Dict[str, float]:
    """IDF over the dataset's questions + reference answers.

    The dataset's graded answers share a lot of template boilerplate ('this is
    a fundamental concept...', 'widely adopted in practice...'). IDF lets the
    evaluator weight question-specific concepts (e.g. 'overloading',
    'parameter') far above that boilerplate when judging an answer.
    """
    global _idf_cache
    if _idf_cache is not None:
        return _idf_cache

    import math
    docs = []
    for q in load_dataset():
        docs.append(normed_set(f"{q['question']} {q['expected_answer']}"))
    n = max(1, len(docs))
    df: Dict[str, int] = {}
    for d in docs:
        for t in d:
            df[t] = df.get(t, 0) + 1
    _idf_cache = {t: math.log((1 + n) / (1 + f)) + 0.5 for t, f in df.items()}
    return _idf_cache


def select_questions(
    count: int = 6,
    categories: Optional[List[str]] = None,
    seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Pick `count` questions, spread across the dataset's categories.

    This mirrors a real interview: mixed topics rather than 10 of the same kind.
    """
    pool = load_dataset()
    if not pool:
        return []

    if categories:
        wanted = {c.strip().lower() for c in categories if c.strip()}
        filtered = [q for q in pool if q["category"].lower() in wanted]
        if filtered:
            pool = filtered

    rng = random.Random(seed)
    shuffled = pool[:]
    rng.shuffle(shuffled)

    # Spread across categories: round-robin one question per category.
    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for q in shuffled:
        by_cat.setdefault(q["category"], []).append(q)

    picked: List[Dict[str, Any]] = []
    cats = list(by_cat.keys())
    i = 0
    while len(picked) < min(count, len(shuffled)):
        progressed = False
        for cat in cats:
            bucket = by_cat.get(cat)
            if bucket:
                picked.append(bucket.pop(0))
                progressed = True
                if len(picked) >= min(count, len(shuffled)):
                    break
        if not progressed:
            break
        i += 1
    return picked
