"""
Shared constants and helpers for the training pipeline.
"""

import os
import sys
import glob

# training/ lives at <project_root>/training
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

VIDEO_DIR_DEFAULT = r"C:\Users\HP\Desktop\videos"
VIDEO_DIR_LOCAL = os.path.join(PROJECT_ROOT, "data", "raw", "videos")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
TRAINING_DIR = os.path.join(PROJECT_ROOT, "training")
MODEL_DIR = os.path.join(PROJECT_ROOT, "models")

LABELED_CSV = os.path.join(DATA_DIR, "mock_interview_dataset_test.csv")
PROCESSED_CSV = os.path.join(PROCESSED_DIR, "processed_interview_data.csv")
VIDEO_FEATURES_CSV = os.path.join(PROCESSED_DIR, "video_transcript_features.csv")
ANNOTATION_TEMPLATE = os.path.join(PROCESSED_DIR, "annotation_template.csv")
TRAINING_REPORT = os.path.join(MODEL_DIR, "training_report.json")

# Whisper settings — identical at training and live/serve time (parity).
WHISPER_MODEL = "base"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE = "int8"

# Feature-version marker stored with the model. Bump when FEATURE_NAMES or
# any feature semantics change.
MODEL_VERSION = "2.0.0-video-labeled"

# Heuristic filler-word duration when a filler has no timing (pause proxy).
FILLER_PAUSE_S = 0.35


def discover_videos(video_dir: str = None):
    """Find interview videos. Prefers the local data/raw/videos copy, falls
    back to the Desktop dataset folder. Returns sorted list of paths."""
    candidates = [video_dir] if video_dir else [VIDEO_DIR_LOCAL, VIDEO_DIR_DEFAULT]
    for d in candidates:
        if d and os.path.isdir(d):
            vids = sorted(
                glob.glob(os.path.join(d, "*.mp4"))
                + glob.glob(os.path.join(d, "*.avi"))
                + glob.glob(os.path.join(d, "*.mov"))
                + glob.glob(os.path.join(d, "*.mkv"))
                + glob.glob(os.path.join(d, "*.webm"))
            )
            if vids:
                return vids
    return []


def ensure_dirs():
    for d in (PROCESSED_DIR, MODEL_DIR):
        os.makedirs(d, exist_ok=True)
