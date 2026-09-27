"""
Feature extraction for the ML interview scoring pipeline.
Extracts and normalizes features from interview analysis results.
"""
import numpy as np
from typing import Dict, Any, List, Optional


FEATURE_NAMES = [
    # Speech features
    "words_per_minute",
    "filler_count",
    "filler_rate",
    "pause_count",
    "long_pause_count",
    "avg_pause_duration",
    "speech_duration",
    "pace_consistency",
    "delivery_score",

    # NLP features
    "word_count",
    "sentence_count",
    "vocabulary_diversity",
    "repetition_rate",
    "sentiment_score",
    "avg_sentence_length",
    "positive_signals",
    "negative_signals",

    # Communication features
    "clarity_score",
    "fluency_score",
    "conciseness_score",
    "professionalism_score",

    # Content features
    "answer_count",
    "avg_answer_score",
    "star_score",

    # Video features
    "face_visibility",
    "camera_presence",
    "head_movement_score",
    "framing_score",
]


def extract_features(
    speech_analysis: Dict[str, Any],
    content_analysis: Dict[str, Any],
    qa_analyses: List[Dict[str, Any]],
    video_analysis: Dict[str, Any],
) -> Dict[str, float]:
    """
    Extract a feature vector from analysis results.
    Returns a dict mapping feature names to values.
    """
    features = {}

    # Speech features
    features["words_per_minute"] = speech_analysis.get("words_per_minute", 0)
    features["filler_count"] = speech_analysis.get("filler_words", {}).get("count", 0)
    features["filler_rate"] = speech_analysis.get("filler_words", {}).get("rate_per_minute", 0)
    features["pause_count"] = speech_analysis.get("pauses", {}).get("total_pauses", 0)
    features["long_pause_count"] = speech_analysis.get("pauses", {}).get("long_pauses", 0)
    features["avg_pause_duration"] = speech_analysis.get("pauses", {}).get("average_pause_duration", 0)
    features["speech_duration"] = speech_analysis.get("duration", 0)
    features["pace_consistency"] = speech_analysis.get("delivery", {}).get("pace_consistency", 0.7)
    features["delivery_score"] = speech_analysis.get("delivery", {}).get("score", 70)

    # NLP features
    features["word_count"] = content_analysis.get("word_count", 0)
    features["sentence_count"] = content_analysis.get("sentence_count", 0)
    features["vocabulary_diversity"] = content_analysis.get("vocabulary_diversity", 0.5)
    features["repetition_rate"] = content_analysis.get("repetition_rate", 0)
    features["sentiment_score"] = content_analysis.get("sentiment", 0)
    features["avg_sentence_length"] = content_analysis.get("avg_sentence_length", 15)
    features["positive_signals"] = content_analysis.get("positive_signals", 0)
    features["negative_signals"] = content_analysis.get("negative_signals", 0)

    # Communication features
    features["clarity_score"] = content_analysis.get("clarity_score", 70)
    features["fluency_score"] = content_analysis.get("fluency_score", 70)
    features["conciseness_score"] = content_analysis.get("conciseness_score", 70)
    features["professionalism_score"] = content_analysis.get("professionalism_score", 70)

    # Content features
    features["answer_count"] = len(qa_analyses) if qa_analyses else 1
    if qa_analyses:
        answer_scores = [qa.get("overall_answer_score", 70) for qa in qa_analyses if qa.get("overall_answer_score")]
        features["avg_answer_score"] = sum(answer_scores) / len(answer_scores) if answer_scores else 70
        star_scores = [qa.get("star_score", 50) for qa in qa_analyses if qa.get("star_score") is not None]
        features["star_score"] = sum(star_scores) / len(star_scores) if star_scores else 50
    else:
        features["avg_answer_score"] = 70
        features["star_score"] = 50

    # Video features
    features["face_visibility"] = video_analysis.get("face_visibility", 70)
    features["camera_presence"] = video_analysis.get("camera_presence", 70)
    features["head_movement_score"] = video_analysis.get("head_movement_score", 70)
    features["framing_score"] = video_analysis.get("framing_score", 70)

    return features


def features_to_array(features: Dict[str, float]) -> np.ndarray:
    """Convert feature dict to numpy array in consistent order."""
    return np.array([features.get(name, 0.0) for name in FEATURE_NAMES])


def normalize_features(features_dict: Dict[str, float]) -> Dict[str, float]:
    """Normalize features to 0-100 scale where applicable."""
    normalized = {}
    for key, value in features_dict.items():
        if key in ["words_per_minute"]:
            normalized[key] = min(100, value / 2.0)
        elif key in ["filler_count", "pause_count", "long_pause_count", "negative_signals"]:
            normalized[key] = max(0, 100 - value * 5)
        elif key in ["filler_rate"]:
            normalized[key] = max(0, 100 - value * 5)
        elif key in ["avg_pause_duration"]:
            normalized[key] = max(0, 100 - value * 20)
        elif key in ["speech_duration"]:
            normalized[key] = min(100, value / 0.6)
        elif key in ["word_count", "sentence_count"]:
            normalized[key] = min(100, value * 0.5)
        elif key in ["avg_sentence_length"]:
            if 10 <= value <= 25:
                normalized[key] = 90
            elif value < 10:
                normalized[key] = 60
            else:
                normalized[key] = 65
        else:
            normalized[key] = min(100, max(0, value))
    return normalized
