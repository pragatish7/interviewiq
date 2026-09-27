"""
Step 3-4 of the ML pipeline: transcript + metadata -> feature dataset.

Two sources, one feature extractor (backend/app/ml/answer_features.py):

1. The labeled mock-interview CSV (750 graded answers, final_score 0-100,
   5 quality grades x 150 questions). These rows carry REAL labels — they
   become the supervised training set.

2. The video transcripts (training/preprocess.py output). The videos ship
   with NO scores/questions/metadata, so these rows get features + transcript
   only and an EMPTY score column — they are exported as the processed video
   dataset + annotation template. The training script excludes them until
   someone fills real scores in (never fabricated).

Outputs (data/processed/):
  processed_interview_data.csv   labeled rows, features + final_score (trainable)
  video_transcript_features.csv  video rows, features + transcript, score blank
  annotation_template.csv        video,question,candidate_answer,score template
"""

import os
import csv
import json
import logging
from typing import Dict, Any, List

from training.common import (
    LABELED_CSV, PROCESSED_CSV, VIDEO_FEATURES_CSV, ANNOTATION_TEMPLATE,
    PROCESSED_DIR, ensure_dirs,
)
from training.preprocess import TRANSCRIPT_DIR

logger = logging.getLogger("extract_features")

# Human-readable names for the CSV export of the feature dict.
FEATURE_ORDER = [
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
    "structure_score",
    "hedge_count",
]


def load_labeled_rows() -> List[Dict[str, Any]]:
    """Read the graded mock-interview dataset and compute features per row.

    Each question has 5 graded reference answers; every row's features include
    its similarity to each grade text of ITS question. Grade texts are part of
    the question bank and are equally available at live-prediction time, so
    this is not label leakage (and the grouped split keeps a question's rows
    on one side of the split anyway).
    """
    from backend.app.ml.answer_features import extract_features_from_answer

    rows = []
    if not os.path.exists(LABELED_CSV):
        logger.warning(f"Labeled dataset not found: {LABELED_CSV}")
        return rows

    # Pass 1: collect each question's grade texts.
    raw_rows = []
    grade_texts_by_q: Dict[str, Dict[str, str]] = {}
    with open(LABELED_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            qid = (r.get("question_id") or "").strip()
            label = (r.get("quality_label") or "").strip()
            text = (r.get("answer_text") or "").strip()
            raw_rows.append(r)
            if qid and label and text:
                grade_texts_by_q.setdefault(qid, {})[label] = text

    # Pass 2: features per graded row.
    for r in raw_rows:
        q = (r.get("question") or "").strip()
        ref = (r.get("answer_text") or "").strip()
        label_raw = (r.get("final_score") or "").strip()
        qid = (r.get("question_id") or "").strip()
        if not q or not ref or not label_raw:
            continue
        try:
            label = float(label_raw)
        except ValueError:
            continue
        # The graded answer text doubles as the "candidate answer" for
        # labeled rows: the dataset scores these reference responses.
        feats = extract_features_from_answer(
            ref, q, ref, duration_s=0.0,
            grade_texts=grade_texts_by_q.get(qid),
        )
        row = {
            "source": "mock_labeled",
            "sample_id": r.get("answer_id", ""),
            "question_id": qid,
            "category": r.get("category", ""),
            "difficulty": r.get("difficulty", ""),
            "quality_label": r.get("quality_label", ""),
            "question": q,
            "expected_answer": ref,
            "candidate_answer": ref,
        }
        row.update(feats["features"])
        row["score"] = label
        rows.append(row)
    logger.info(f"Labeled rows with features: {len(rows)}")
    return rows


def load_video_rows(annotation_csv: str = None) -> List[Dict[str, Any]]:
    """Build feature rows from cached video transcripts.

    Scores come ONLY from an annotation CSV if provided
    (columns: video,score). Videos without annotations get score='' and are
    excluded from training.
    """
    from backend.app.ml.answer_features import extract_features_from_answer

    scores = {}
    if annotation_csv and os.path.exists(annotation_csv):
        with open(annotation_csv, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                vid = (r.get("video") or "").strip()
                s = (r.get("score") or "").strip()
                if vid and s:
                    try:
                        scores[vid] = float(s)
                    except ValueError:
                        pass
        logger.info(f"Loaded {len(scores)} manual annotations from {annotation_csv}")

    rows = []
    if not os.path.isdir(TRANSCRIPT_DIR):
        logger.warning(f"No transcript cache at {TRANSCRIPT_DIR}")
        return rows

    for fn in sorted(os.listdir(TRANSCRIPT_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(TRANSCRIPT_DIR, fn), "r", encoding="utf-8") as f:
            rec = json.load(f)
        if rec.get("error") or not (rec.get("transcript") or "").strip():
            continue
        vid = rec["video"]
        transcript = rec["transcript"]
        feats = extract_features_from_answer(
            transcript, question="", reference="", duration_s=rec.get("duration_s") or 0.0,
        )
        row = {
            "source": "video",
            "sample_id": os.path.splitext(vid)[0],
            "question_id": "",
            "category": "",
            "difficulty": "",
            "quality_label": "",
            "question": "",
            "expected_answer": "",
            "candidate_answer": transcript,
        }
        row.update(feats["features"])
        row["score"] = scores.get(vid, "")
        rows.append(row)

    annotated = sum(1 for r in rows if r["score"] != "")
    logger.info(f"Video rows: {len(rows)} (annotated: {annotated})")
    return rows


def write_csv(path: str, rows: List[Dict[str, Any]]):
    if not rows:
        logger.warning(f"No rows to write for {path}")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    logger.info(f"Wrote {len(rows)} rows -> {path}")


def run_extract(annotation_csv: str = None) -> dict:
    ensure_dirs()
    labeled = load_labeled_rows()
    videos = load_video_rows(annotation_csv)

    write_csv(PROCESSED_CSV, labeled)
    write_csv(VIDEO_FEATURES_CSV, videos)

    # Annotation template for the video dataset (only unannotated videos).
    todo = [r for r in videos if r["score"] == ""]
    with open(ANNOTATION_TEMPLATE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["video", "question", "candidate_answer", "score"])
        for r in todo:
            w.writerow([r["sample_id"] + ".mp4", "", (r["candidate_answer"] or "")[:300], ""])
    logger.info(f"Annotation template: {len(todo)} videos awaiting scores -> {ANNOTATION_TEMPLATE}")

    return {
        "labeled_rows": len(labeled),
        "video_rows": len(videos),
        "video_annotated": sum(1 for r in videos if r["score"] != ""),
        "processed_csv": PROCESSED_CSV,
        "video_csv": VIDEO_FEATURES_CSV,
        "annotation_template": ANNOTATION_TEMPLATE,
    }


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Extract features into processed CSVs.")
    ap.add_argument("--annotations", default=None, help="CSV with video,score manual annotations")
    args = ap.parse_args()
    import json as _json
    print(_json.dumps(run_extract(args.annotations), indent=2))
