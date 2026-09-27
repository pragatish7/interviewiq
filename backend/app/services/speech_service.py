"""
Speech recognition and voice analysis service.
Uses Whisper for transcription with fallback to basic audio analysis.
"""
import os
import re
import json
import logging
import subprocess
import math
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter

logger = logging.getLogger(__name__)

# Filler words to detect
FILLER_WORDS = [
    "um", "uh", "umm", "uhh", "err", "erm",
    "like", "basically", "actually", "you know",
    "i mean", "so", "right", "well",
]

# Common hedging phrases
HEDGE_PHRASES = [
    "i think", "i guess", "maybe", "sort of",
    "kind of", "i suppose", "probably",
]


def transcribe_with_whisper(audio_path: str) -> Dict[str, Any]:
    """
    Transcribe audio using Whisper or faster-whisper.
    Returns dict with text, segments, duration.
    """
    result = {
        "text": "",
        "segments": [],
        "words": [],
        "duration": 0.0,
        "method": "none",
    }

    # Try faster-whisper first (use the best model already downloaded locally)
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(_best_cached_whisper_model(), device="cpu", compute_type="int8")
        segments_iter, info = model.transcribe(audio_path, word_timestamps=True)
        all_segments = []
        all_words = []
        full_text = []

        for segment in segments_iter:
            seg_dict = {
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
            }
            all_segments.append(seg_dict)
            full_text.append(segment.text.strip())

            if segment.words:
                for word in segment.words:
                    all_words.append({
                        "word": word.word.strip(),
                        "start": round(word.start, 2),
                        "end": round(word.end, 2),
                    })

        result["text"] = " ".join(full_text)
        result["segments"] = all_segments
        result["words"] = all_words
        result["duration"] = info.duration if info.duration else 0.0
        result["method"] = "faster-whisper"
        logger.info("Transcribed with faster-whisper")
        return result
    except ImportError:
        logger.info("faster-whisper not available, trying openai-whisper")
    except Exception as e:
        logger.warning(f"faster-whisper failed: {e}")

    # Try openai-whisper
    try:
        import whisper
        model = whisper.load_model("base")
        result_whisper = model.transcribe(audio_path, word_timestamps=True)

        all_words = []
        for segment in result_whisper.get("segments", []):
            if "words" in segment:
                for w in segment["words"]:
                    all_words.append({
                        "word": w.get("word", "").strip(),
                        "start": round(w.get("start", 0), 2),
                        "end": round(w.get("end", 0), 2),
                    })

        result["text"] = result_whisper.get("text", "")
        result["segments"] = [
            {
                "start": round(s.get("start", 0), 2),
                "end": round(s.get("end", 0), 2),
                "text": s.get("text", "").strip(),
            }
            for s in result_whisper.get("segments", [])
        ]
        result["words"] = all_words
        result["method"] = "whisper"
        logger.info("Transcribed with openai-whisper")
        return result
    except ImportError:
        logger.info("openai-whisper not available")
    except Exception as e:
        logger.warning(f"openai-whisper failed: {e}")

    # Fallback: try speech_recognition library
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data)
        result["text"] = text
        result["method"] = "google-speech"
        logger.info("Transcribed with Google Speech Recognition")
        return result
    except ImportError:
        logger.info("speech_recognition not available")
    except Exception as e:
        logger.warning(f"speech_recognition failed: {e}")

    # Last resort: no usable transcript (caller falls back to a clearly-labeled demo)
    result["method"] = "none"
    return result


def _best_cached_whisper_model(default: str = "base") -> str:
    """Pick the largest faster-whisper model already present in the HF cache.
    Avoids forcing a network download when a local model exists."""
    import glob
    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
    available = set()
    for p in glob.glob(os.path.join(cache_dir, "models--Systran--faster-whisper-*")):
        size = os.path.basename(p).rsplit("--", 1)[-1]
        available.add(size)
    for preferred in ("small", "base", "medium", "tiny", "large-v3"):
        if preferred in available:
            return preferred
    return default


def analyze_transcription(transcription: Dict[str, Any], duration: float) -> Dict[str, Any]:
    """
    Comprehensive speech analysis from transcription data.
    """
    text = transcription.get("text", "")
    segments = transcription.get("segments", [])
    words_data = transcription.get("words", [])

    words = [w.strip() for w in re.split(r'\s+', text) if w.strip()]
    word_list_lower = [w.lower().strip(".,!?;:\"'") for w in words]
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]

    effective_duration = max(duration, transcription.get("duration", 0), 1.0)

    # Filler word analysis
    filler_detail = detect_filler_words(words_data, word_list_lower, segments)

    # Pause analysis
    pause_analysis = analyze_pauses(segments, words_data, effective_duration)

    # Speaking pace
    total_words = len([w for w in word_list_lower if len(w) > 0])
    wpm = round(total_words / (effective_duration / 60), 1) if effective_duration > 0 else 0

    pace_consistency = compute_pace_consistency(segments, effective_duration)

    # Voice delivery (from segment analysis)
    delivery = analyze_delivery(segments, pause_analysis, filler_detail)

    return {
        "total_words": total_words,
        "word_count": total_words,
        "sentence_count": len(sentences),
        "duration": round(effective_duration, 2),
        "words_per_minute": wpm,
        "speaking_rate": wpm,
        "pace_consistency": pace_consistency,
        "filler_words": filler_detail,
        "pauses": pause_analysis,
        "delivery": delivery,
        "speech_segments_count": len(segments),
        "segments": segments,
    }


def detect_filler_words(words_data: list, word_list_lower: list, segments: list) -> Dict[str, Any]:
    """Detect and analyze filler words in the transcript."""
    fillers_found = []
    filler_counts = Counter()

    # Check word-level timestamps for fillers
    for word_info in words_data:
        word = word_info.get("word", "").lower().strip(".,!?;:\"'")
        for filler in FILLER_WORDS:
            if word == filler or word.rstrip("s") == filler.rstrip("s"):
                fillers_found.append({
                    "word": word,
                    "start": word_info.get("start", 0),
                    "end": word_info.get("end", 0),
                    "type": "filler",
                })
                filler_counts[word] += 1
                break

    # Fallback: scan without timestamps
    if not fillers_found:
        for i, w in enumerate(word_list_lower):
            for filler in FILLER_WORDS:
                if w == filler or w.rstrip("s") == filler.rstrip("s"):
                    filler_counts[filler] += 1
                    fillers_found.append({
                        "word": filler,
                        "start": 0,
                        "end": 0,
                        "type": "filler",
                        "estimated_index": i,
                    })
                    break

    total_fillers = len(fillers_found)
    duration_minutes = max(1, (segments[-1]["end"] - segments[0]["start"]) / 60) if segments else 1
    filler_rate = round(total_fillers / duration_minutes, 2) if duration_minutes > 0 else 0
    total_words = sum(1 for w in word_list_lower if w)
    filler_percentage = round((total_fillers / total_words * 100), 2) if total_words > 0 else 0

    # Score: fewer fillers = higher score
    if filler_rate == 0:
        score = 100
    elif filler_rate < 2:
        score = 90
    elif filler_rate < 5:
        score = 75
    elif filler_rate < 10:
        score = 60
    elif filler_rate < 15:
        score = 45
    else:
        score = 30

    return {
        "count": total_fillers,
        "rate_per_minute": filler_rate,
        "percentage": filler_percentage,
        "most_frequent": dict(filler_counts.most_common(5)),
        "instances": fillers_found,
        "score": score,
    }


def analyze_pauses(segments: list, words_data: list, duration: float) -> Dict[str, Any]:
    """Analyze pause patterns in speech."""
    pauses = []

    if len(segments) >= 2:
        for i in range(1, len(segments)):
            gap = segments[i]["start"] - segments[i - 1]["end"]
            if gap > 0.3:
                pauses.append({
                    "start": round(segments[i - 1]["end"], 2),
                    "end": round(segments[i]["start"], 2),
                    "duration": round(gap, 2),
                    "type": "long_pause" if gap > 1.5 else "pause",
                })

    if words_data and len(words_data) >= 2:
        word_pauses = []
        for i in range(1, len(words_data)):
            gap = words_data[i]["start"] - words_data[i - 1]["end"]
            if gap > 0.5:
                word_pauses.append({
                    "start": round(words_data[i - 1]["end"], 2),
                    "end": round(words_data[i]["start"], 2),
                    "duration": round(gap, 2),
                })
        # Merge with segment pauses, removing duplicates
        existing_starts = {p["start"] for p in pauses}
        for wp in word_pauses:
            if wp["start"] not in existing_starts and wp["duration"] > 1.0:
                wp["type"] = "long_pause" if wp["duration"] > 2.0 else "pause"
                pauses.append(wp)

    pauses.sort(key=lambda x: x["start"])
    long_pauses = [p for p in pauses if p.get("duration", 0) > 1.5]
    avg_pause = round(sum(p["duration"] for p in pauses) / len(pauses), 2) if pauses else 0.0

    # Score
    if len(long_pauses) == 0:
        score = 95
    elif len(long_pauses) <= 2:
        score = 80
    elif len(long_pauses) <= 5:
        score = 65
    else:
        score = 45

    return {
        "total_pauses": len(pauses),
        "long_pauses": len(long_pauses),
        "average_pause_duration": avg_pause,
        "pause_events": pauses,
        "score": score,
    }


def compute_pace_consistency(segments: list, duration: float) -> float:
    """Compute pace consistency (0-1, 1 = perfectly consistent)."""
    if len(segments) < 3:
        return 0.7

    segment_wpm = []
    for seg in segments:
        text = seg.get("text", "")
        seg_duration = seg.get("end", 0) - seg.get("start", 0)
        if seg_duration > 0:
            w = len(text.split())
            segment_wpm.append(w / (seg_duration / 60))

    if len(segment_wpm) < 2:
        return 0.7

    mean_wpm = sum(segment_wpm) / len(segment_wpm)
    variance = sum((x - mean_wpm) ** 2 for x in segment_wpm) / len(segment_wpm)
    cv = math.sqrt(variance) / mean_wpm if mean_wpm > 0 else 1

    consistency = max(0, 1 - cv)
    return round(consistency, 3)


def analyze_delivery(segments: list, pause_analysis: Dict, filler_detail: Dict) -> Dict[str, Any]:
    """Analyze voice delivery characteristics."""
    filler_rate = filler_detail.get("rate_per_minute", 0)
    long_pauses = pause_analysis.get("long_pauses", 0)
    total_pauses = pause_analysis.get("total_pauses", 0)
    pace_consistency = 0.7  # default

    if segments:
        durations = [s["end"] - s["start"] for s in segments if s.get("end", 0) > s.get("start", 0)]
        if durations:
            mean_dur = sum(durations) / len(durations)
            variance = sum((d - mean_dur) ** 2 for d in durations) / len(durations)
            cv = math.sqrt(variance) / mean_dur if mean_dur > 0 else 1
            pace_consistency = max(0, 1 - cv)

    # Delivery score
    delivery_score = 70.0
    delivery_score += max(0, 20 - filler_rate * 2)
    delivery_score -= long_pauses * 3
    delivery_score += pace_consistency * 15
    delivery_score = max(20, min(100, delivery_score))

    features = []
    if filler_rate < 3:
        features.append("Low filler word usage indicates fluent delivery")
    elif filler_rate > 10:
        features.append("High filler word rate may reduce perceived confidence")

    if long_pauses <= 2:
        features.append("Speech flows naturally with minimal long pauses")
    elif long_pauses > 5:
        features.append("Frequent long pauses may affect communication flow")

    return {
        "score": round(delivery_score, 1),
        "pace_consistency": round(pace_consistency, 3),
        "features": features,
    }
