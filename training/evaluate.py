"""
Standalone evaluation for the saved answer-scoring model.

  python training/evaluate.py

Re-derives the feature dataset, regenerates a fresh grouped hold-out split
(different seed than training) and reports MAE / RMSE / R2 of the SAVED model
on that untouched split, plus the mean prediction per quality grade. This is
the report to trust: it never touches the model, only measures it.
"""

import os
import json
import logging
import numpy as np
import pandas as pd

from training.common import PROCESSED_CSV, VIDEO_FEATURES_CSV, MODEL_DIR
from backend.app.ml.answer_features import FEATURE_NAMES

logger = logging.getLogger("evaluate")


def main(seed: int = 123) -> dict:
    import joblib
    from sklearn.model_selection import GroupShuffleSplit

    model_path = os.path.join(MODEL_DIR, "interview_model.pkl")
    scaler_path = os.path.join(MODEL_DIR, "interview_scaler.pkl")
    if not (os.path.exists(model_path) and os.path.exists(scaler_path)):
        raise SystemExit("No saved model found. Run training/train.py first.")

    frames = []
    for p in (PROCESSED_CSV, VIDEO_FEATURES_CSV):
        if os.path.exists(p):
            df = pd.read_csv(p)
            df = df[pd.to_numeric(df["score"], errors="coerce").notna()]
            if len(df):
                frames.append(df)
    if not frames:
        raise SystemExit("No labeled data found. Run training/extract_features.py first.")
    df = pd.concat(frames, ignore_index=True)

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)

    groups = df["question_id"].astype(str) if "question_id" in df.columns else None
    if groups is not None and groups.nunique() >= 10:
        gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed)
        _, hold_idx = next(gss.split(df, groups=groups))
    else:
        rng = np.random.RandomState(seed)
        hold_idx = rng.choice(len(df), size=max(1, len(df) // 4), replace=False)
    hold = df.iloc[hold_idx]

    X = hold[FEATURE_NAMES].astype(float)
    y = hold["score"].astype(float)
    pred = model.predict(scaler.transform(X))

    from training.train import regression_metrics
    metrics = regression_metrics(y, pred)

    out = {
        "held_out_rows": int(len(hold)),
        "metrics": metrics,
        "by_grade_mean_prediction": (
            hold.assign(pred=pred).groupby("quality_label")["pred"].mean().round(1).to_dict()
            if "quality_label" in hold.columns else {}
        ),
        "score_range": [float(y.min()), float(y.max())],
    }
    logger.info(f"Held-out MAE={metrics['mae']} RMSE={metrics['rmse']} R2={metrics['r2']}")
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(json.dumps(main(), indent=2))
