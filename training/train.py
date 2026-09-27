"""
Step 5-8 of the ML pipeline: train, evaluate, save the answer-scoring model.

Label honesty rules enforced here:
  * Only rows whose `score` column is a real number are used for supervised
    training. Today that is the 750 graded answers in the mock dataset
    (final_score 0-100). Video rows (no labels) are NEVER assigned invented
    scores; they join training only after manual annotation.
  * Split is GROUPED by question_id: all 5 grade-variants of one question
    stay together in train or test. This prevents the model from memorizing
    a question's reference phrasing and inflating test metrics (leakage).
  * Metrics are reported on the held-out test group only, and reported
    as-is — no inflation, no cherry-picking.

Artifacts in models/:
  interview_model.pkl   trained regressor (whole pipeline object)
  scaler.pkl            fitted StandardScaler (identity for tree models)
  feature_config.json   feature order, version, label source, metrics

Retrain any time with:  python training/train.py
New labeled videos: fill scores in data/processed/annotation_template.csv
(zero-padded per video id, e.g. video,score rows), then rerun.
"""

import os
import sys
import json
import logging
import numpy as np
import pandas as pd

from training.common import (
    PROCESSED_CSV, VIDEO_FEATURES_CSV, MODEL_DIR, TRAINING_REPORT,
    MODEL_VERSION, ensure_dirs,
)
from backend.app.ml.answer_features import FEATURE_NAMES

logger = logging.getLogger("train")


def load_training_frame() -> pd.DataFrame:
    """Labeled rows only — union of labeled mock CSV and any annotated videos."""
    frames = []
    if os.path.exists(PROCESSED_CSV):
        df = pd.read_csv(PROCESSED_CSV)
        df = df[pd.to_numeric(df["score"], errors="coerce").notna()]
        frames.append(df)
    if os.path.exists(VIDEO_FEATURES_CSV):
        dv = pd.read_csv(VIDEO_FEATURES_CSV)
        dv = dv[pd.to_numeric(dv["score"], errors="coerce").notna()]
        if len(dv):
            logger.info(f"Including {len(dv)} manually annotated video rows")
            frames.append(dv)
    if not frames:
        raise SystemExit(
            "No labeled rows found. Run training/extract_features.py first, "
            "and note the video dataset ships without labels — fill "
            "data/processed/annotation_template.csv to use videos for training."
        )
    df = pd.concat(frames, ignore_index=True)
    logger.info(f"Training rows with real labels: {len(df)}")
    return df


def make_splits(df: pd.DataFrame, seed: int = 42):
    """Group-aware 70/15/15 split by question_id (fallback: row-wise when a
    group column is missing). Returns (train_df, val_df, test_df)."""
    from sklearn.model_selection import GroupShuffleSplit

    groups = df["question_id"].astype(str) if "question_id" in df.columns else None
    if groups is None or groups.nunique() < 10:
        logger.warning("Few/no question groups — falling back to a random split")
        from sklearn.model_selection import train_test_split
        train_df, temp = train_test_split(df, test_size=0.30, random_state=seed)
        val_df, test_df = train_test_split(temp, test_size=0.50, random_state=seed)
        return train_df, val_df, test_df

    gss1 = GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=seed)
    train_idx, temp_idx = next(gss1.split(df, groups=groups))
    train_df = df.iloc[train_idx]
    temp_df = df.iloc[temp_idx]

    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.50, random_state=seed)
    val_idx, test_idx = next(gss2.split(temp_df, groups=temp_df["question_id"].astype(str)))
    val_df = temp_df.iloc[val_idx]
    test_df = temp_df.iloc[test_idx]

    logger.info(
        f"Group split by question_id: train={len(train_df)} val={len(val_df)} "
        f"test={len(test_df)} (groups: {train_df['question_id'].nunique()}/"
        f"{val_df['question_id'].nunique()}/{test_df['question_id'].nunique()})"
    )
    return train_df, val_df, test_df


def regression_metrics(y_true, y_pred) -> dict:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 3),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 3),
        "r2": round(float(r2_score(y_true, y_pred)), 4),
    }


def _candidates():
    from sklearn.linear_model import Ridge
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    return {
        "ridge": Ridge(alpha=1.0),
        "random_forest": RandomForestRegressor(
            n_estimators=300, max_depth=None, min_samples_leaf=2,
            n_jobs=-1, random_state=42,
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=3,
            subsample=0.9, random_state=42,
        ),
    }


def main(seed: int = 42) -> dict:
    ensure_dirs()
    df = load_training_frame()
    train_df, val_df, test_df = make_splits(df, seed)

    X_train = train_df[FEATURE_NAMES].astype(float)
    y_train = train_df["score"].astype(float)
    X_val = val_df[FEATURE_NAMES].astype(float)
    y_val = val_df["score"].astype(float)
    X_test = test_df[FEATURE_NAMES].astype(float)
    y_test = test_df["score"].astype(float)

    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler().fit(X_train)

    results = {}
    best_name, best_r2, best_model = None, -1e9, None
    for name, model in _candidates().items():
        Xtr = scaler.transform(X_train)
        Xva = scaler.transform(X_val)
        model.fit(Xtr, y_train)
        val_pred = model.predict(Xva)
        m = regression_metrics(y_val, val_pred)
        results[name] = {"validation": m}
        logger.info(f"{name}: val MAE={m['mae']:.2f} RMSE={m['rmse']:.2f} R2={m['r2']:.4f}")
        if m["r2"] > best_r2:
            best_name, best_r2, best_model = name, m["r2"], model

    # Final honest evaluation on the untouched test group.
    test_pred = best_model.predict(scaler.transform(X_test))
    test_metrics = regression_metrics(y_test, test_pred)
    results[best_name]["test"] = test_metrics
    logger.info(
        f"BEST={best_name}  TEST MAE={test_metrics['mae']:.2f} "
        f"RMSE={test_metrics['rmse']:.2f} R2={test_metrics['r2']:.4f}"
    )

    # Refit the chosen model on train+val so it ships with maximum data; the
    # test numbers above remain the honest held-out estimate.
    X_full = pd.concat([X_train, X_val])
    y_full = pd.concat([y_train, y_val])
    best_model.fit(scaler.transform(X_full), y_full)

    # Per-grade sanity check on the test set.
    test_out = test_df.copy()
    test_out["pred"] = test_pred
    by_grade = (
        test_out.groupby("quality_label")["pred"].mean().round(1).to_dict()
        if "quality_label" in test_out.columns else {}
    )

    importance = {}
    if hasattr(best_model, "feature_importances_"):
        importance = dict(sorted(
            zip(FEATURE_NAMES, [round(float(v), 4) for v in best_model.feature_importances_]),
            key=lambda kv: kv[1], reverse=True,
        ))
    elif hasattr(best_model, "coef_"):
        importance = dict(sorted(
            zip(FEATURE_NAMES, [round(float(v), 4) for v in best_model.coef_]),
            key=lambda kv: abs(kv[1]), reverse=True,
        ))

    # Label provenance string built from what actually contributed labels.
    label_sources = ["mock_interview_dataset_test.csv final_score (750 graded answers)"]
    if "source" in df.columns and (df["source"].astype(str) == "video").any():
        label_sources.append("manual video annotations (annotation_template.csv)")

    import joblib
    model_path = os.path.join(MODEL_DIR, "interview_model.pkl")
    scaler_path = os.path.join(MODEL_DIR, "interview_scaler.pkl")
    config_path = os.path.join(MODEL_DIR, "feature_config.json")
    joblib.dump(best_model, model_path)
    joblib.dump(scaler, scaler_path)
    config = {
        "model_version": MODEL_VERSION,
        "model_type": type(best_model).__name__,
        "feature_names": FEATURE_NAMES,
        "label_source": " + ".join(label_sources),
        "trained_rows": int(len(df)),
        "split": "GroupShuffleSplit by question_id (70/15/15), grouped to avoid leakage",
        "metrics": results,
        "test_metrics": test_metrics,
        "by_grade_mean_prediction": by_grade,
        "feature_importance": importance,
        "model_path": model_path,
        "scaler_path": scaler_path,
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    with open(TRAINING_REPORT, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    logger.info(f"Saved {model_path}, {scaler_path}, {config_path}")
    return config


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = main()
    print(json.dumps({
        "best_model": cfg["model_type"],
        "test_metrics": cfg["test_metrics"],
        "validation": cfg["metrics"],
        "feature_importance": cfg["feature_importance"],
    }, indent=2))
