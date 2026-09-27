"""
Step 1-2 of the ML pipeline: VIDEO -> audio -> speech-to-text -> transcript.

Every video produces exactly one JSON cache file in data/processed/transcripts/:
  {
    "video": "vid_0498.mp4",
    "duration_s": 30.3,
    "has_audio": true,
    "transcript": "...",
    "words": [{"word": "...", "start": 0.0, "end": 1.2}, ...],
    "segments": [{"start": ..., "end": ..., "text": "..."}, ...],
    "language": "en",
    "method": "faster-whisper-base",
    "error": null
  }

The cache makes the whole pipeline resumable and re-runnable:
  python training/preprocess.py            # process everything not yet done
  python training/preprocess.py --limit 50 # quick smoke run
Already-processed videos are skipped, so adding new videos later just works.

This module uses the SAME transcription engine and settings as the app's
upload flow (faster-whisper 'base', int8, cpu) — train/serve parity.
"""

import os
import sys
import json
import time
import argparse
import logging

from training.common import (
    PROJECT_ROOT, PROCESSED_DIR, discover_videos,
    WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE, ensure_dirs,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("preprocess")

TRANSCRIPT_DIR = os.path.join(PROCESSED_DIR, "transcripts")

# ffmpeg via imageio-ffmpeg (no system install needed); PyAV (bundled with
# faster-whisper) decodes the audio for whisper directly from the mp4.
_ffmpeg_path = None


def ffmpeg_path() -> str:
    global _ffmpeg_path
    if _ffmpeg_path is None:
        try:
            import imageio_ffmpeg
            _ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            _ffmpeg_path = "ffmpeg"
    return _ffmpeg_path


def probe_duration_ffmpeg(video_path: str) -> float:
    """Duration via ffmpeg -i stderr parse (no ffprobe binary needed)."""
    import subprocess
    import re
    try:
        r = subprocess.run(
            [ffmpeg_path(), "-i", video_path],
            capture_output=True, text=True, errors="replace", timeout=60,
        )
        m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", r.stderr)
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return 0.0


def transcribe_video(video_path: str, model=None) -> dict:
    """Transcribe one video with faster-whisper, word timestamps on.

    `model` may be a shared WhisperModel instance (recommended for batches —
    loading takes ~40s; loading once per batch saves that per video).
    """
    from faster_whisper import WhisperModel

    own_model = model is None
    if own_model:
        model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)

    result = {
        "video": os.path.basename(video_path),
        "duration_s": 0.0,
        "has_audio": False,
        "transcript": "",
        "words": [],
        "segments": [],
        "language": None,
        "method": f"faster-whisper-{WHISPER_MODEL}",
        "error": None,
    }

    try:
        result["duration_s"] = round(probe_duration_ffmpeg(video_path), 2)
        segments_iter, info = model.transcribe(
            video_path,
            word_timestamps=True,
            language="en",
            vad_filter=True,           # skip silence — better pause metrics
            condition_on_previous_text=False,
        )
        words, segments, text_parts = [], [], []
        for s in segments_iter:
            seg_text = (s.text or "").strip()
            if seg_text:
                segments.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": seg_text})
                text_parts.append(seg_text)
            if s.words:
                for w in s.words:
                    words.append({
                        "word": (w.word or "").strip(),
                        "start": round(float(w.start), 2),
                        "end": round(float(w.end), 2),
                    })
        result["transcript"] = " ".join(text_parts).strip()
        result["segments"] = segments
        result["words"] = words
        result["language"] = info.language
        result["has_audio"] = True
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        logger.warning(f"{result['video']}: transcription error: {result['error']}")

    if own_model:
        del model
    return result


def cache_path(video_path: str) -> str:
    return os.path.join(TRANSCRIPT_DIR, os.path.splitext(os.path.basename(video_path))[0] + ".json")


def is_processed(video_path: str) -> bool:
    p = cache_path(video_path)
    if not os.path.exists(p):
        return False
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        # A cache entry counts as done when it completed without error.
        return data.get("error") is None
    except Exception:
        return False


def load_cache(video_path: str) -> dict:
    with open(cache_path(video_path), "r", encoding="utf-8") as f:
        return json.load(f)


def run_preprocess(video_dir: str = None, limit: int = None, reverse: bool = False) -> dict:
    """Process all videos not yet in the cache. Returns a summary dict."""
    ensure_dirs()
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

    videos = discover_videos(video_dir)
    if reverse:
        videos = videos[::-1]
    if limit:
        videos = videos[:limit]

    todo = [v for v in videos if not is_processed(v)]
    logger.info(f"Videos found: {len(videos)} | already processed: {len(videos) - len(todo)} | to process: {len(todo)}")
    if not todo:
        return {"found": len(videos), "processed": 0, "skipped": len(videos), "errors": 0}

    from faster_whisper import WhisperModel
    logger.info(f"Loading WhisperModel({WHISPER_MODEL}, {WHISPER_DEVICE}/{WHISPER_COMPUTE}) once for the batch...")
    t0 = time.time()
    model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)
    logger.info(f"Model loaded in {time.time() - t0:.1f}s")

    n_ok = n_err = 0
    t_start = time.time()
    for i, vid in enumerate(todo, 1):
        t0 = time.time()
        rec = transcribe_video(vid, model=model)
        with open(cache_path(vid), "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
        if rec["error"]:
            n_err += 1
        else:
            n_ok += 1
        if i % 10 == 0 or i == len(todo):
            rate = i / (time.time() - t_start)
            eta_min = (len(todo) - i) / rate / 60 if rate > 0 else 0
            logger.info(
                f"[{i}/{len(todo)}] ok={n_ok} err={n_err} "
                f"({rate:.1f} videos/s, ETA {eta_min:.0f} min) last: {rec['video']}"
            )

    del model
    return {"found": len(videos), "processed": len(todo), "skipped": len(videos) - len(todo), "errors": n_err}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Transcribe interview videos (resumable).")
    ap.add_argument("--video-dir", default=None, help="Folder containing interview videos")
    ap.add_argument("--limit", type=int, default=None, help="Only process the first N unprocessed videos")
    ap.add_argument("--reverse", action="store_true", help="Process from the end of the list")
    args = ap.parse_args()
    summary = run_preprocess(args.video_dir, args.limit, args.reverse)
    print(json.dumps(summary, indent=2))
