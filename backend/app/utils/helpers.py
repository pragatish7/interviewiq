import os
import re
import math
import unicodedata
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB


def validate_video_file(filename: str, file_size: int = 0) -> Tuple[bool, str]:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File type '{ext}' not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    if file_size > MAX_FILE_SIZE:
        return False, f"File size ({file_size / (1024 * 1024):.1f}MB) exceeds limit ({MAX_FILE_SIZE / (1024 * 1024):.0f}MB)"
    return True, "Valid"


def secure_filename(filename: str) -> str:
    filename = unicodedata.normalize("NFKD", filename)
    filename = re.sub(r"[^\w\s\-\.]", "", filename, flags=re.UNICODE)
    filename = re.sub(r"\s+", "_", filename)
    return filename[:200]


def calculate_overall_score(scores: Dict[str, float], weights: Optional[Dict[str, float]] = None) -> float:
    default_weights = {
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
    w = weights or default_weights
    total = 0.0
    weight_sum = 0.0
    for key, weight in w.items():
        if key in scores and scores[key] is not None:
            total += scores[key] * weight
            weight_sum += weight
    if weight_sum == 0:
        return 0.0
    return round(total / weight_sum, 1)


def get_score_category(score: float) -> str:
    if score >= 90:
        return "Excellent"
    elif score >= 80:
        return "Strong"
    elif score >= 70:
        return "Good"
    elif score >= 60:
        return "Needs Improvement"
    else:
        return "Requires Practice"


def get_score_color(score: float) -> str:
    if score >= 80:
        return "#22c55e"
    elif score >= 60:
        return "#f59e0b"
    else:
        return "#ef4444"


def clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    return max(min_val, min(max_val, value))


def format_duration(seconds: float) -> str:
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    if mins >= 60:
        hours = mins // 60
        mins = mins % 60
        return f"{hours}h {mins}m {secs}s"
    return f"{mins}m {secs}s"


def safe_divide(a: float, b: float, default: float = 0.0) -> float:
    if b == 0:
        return default
    return a / b


def compute_vocabulary_diversity(words: List[str]) -> float:
    if not words:
        return 0.0
    unique = set(w.lower() for w in words)
    return round(len(unique) / len(words), 4)


def compute_repetition_rate(words: List[str]) -> float:
    if len(words) < 2:
        return 0.0
    word_counts: Dict[str, int] = {}
    for w in words:
        wl = w.lower()
        word_counts[wl] = word_counts.get(wl, 0) + 1
    repeated = sum(c - 1 for c in word_counts.values() if c > 1)
    return round(repeated / len(words), 4)


def chunk_list(lst: list, n: int) -> List[list]:
    return [lst[i:i + n] for i in range(0, len(lst), n)]
