"""
Live-interview ML scoring bridge.

Loads the model trained by training/train.py (models/interview_model.pkl +
interview_scaler.pkl + feature_config.json) and predicts an answer score from
the SAME feature vector used in training (backend/app/ml/answer_features.py —
single source of truth, guaranteeing train/serve parity).

Graceful by design: when the artifacts are missing or incompatible, the
caller gets {"available": False, ...} and the existing rule-based score
remains the sole source of truth. The ML prediction is additive
transparency — it never replaces or silently overrides the rule score.
"""

import os
import json
import logging
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(
    # backend/app/ml/live_bridge.py -> project root/models
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "models",
)

_lock = threading.Lock()
_state: Optional[Dict[str, Any]] = None


def _load() -> Optional[Dict[str, Any]]:
    global _state
    if _state is not None:
        return _state

    with _lock:
        if _state is not None:
            return _state
        try:
            import joblib
            model_path = os.path.join(MODEL_DIR, "interview_model.pkl")
            scaler_path = os.path.join(MODEL_DIR, "interview_scaler.pkl")
            config_path = os.path.join(MODEL_DIR, "feature_config.json")

            if not all(os.path.exists(p) for p in (model_path, scaler_path, config_path)):
                logger.info("Live ML bridge: trained model artifacts not found — disabled")
                _state = {"available": False, "reason": "artifacts_missing"}
                return _state

            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            feature_names = config.get("feature_names") or []
            if not feature_names:
                _state = {"available": False, "reason": "feature_config_empty"}
                return _state

            model = joblib.load(model_path)
            scaler = joblib.load(scaler_path)
            _state = {
                "available": True,
                "model": model,
                "scaler": scaler,
                "feature_names": feature_names,
                "config": config,
            }
            logger.info(
                "Live ML bridge ready: %s (v%s, trained on %s rows)"
                % (config.get("model_type"), config.get("model_version"), config.get("trained_rows"))
            )
        except Exception as e:
            logger.warning(f"Live ML bridge failed to load: {e}")
            _state = {"available": False, "reason": str(e)}
    return _state


def predict_answer_score(
    features: Dict[str, float],
) -> Dict[str, Any]:
    """Predict a 0-100 score from the shared answer feature dict.

    Returns {"available": bool, "predicted_score": float|None, "model_version":
    str|None, "model_type": str|None}. Never raises.
    """
    state = _load()
    if not state.get("available"):
        return {"available": False, "predicted_score": None, "model_version": None, "model_type": None}

    try:
        import pandas as pd
        names = state["feature_names"]
        # Named DataFrame avoids sklearn's "feature names" warning and pins
        # column order to the trained config.
        X = pd.DataFrame(
            [[float(features.get(n, 0.0) or 0.0) for n in names]],
            columns=names,
        )
        Xs = state["scaler"].transform(X)
        raw = float(state["model"].predict(Xs)[0])
        return {
            "available": True,
            "predicted_score": round(max(0.0, min(100.0, raw)), 1),
            "model_version": state["config"].get("model_version"),
            "model_type": state["config"].get("model_type"),
        }
    except Exception as e:
        logger.warning(f"Live ML bridge prediction failed: {e}")
        return {"available": False, "predicted_score": None, "model_version": None, "model_type": None}


def model_info() -> Dict[str, Any]:
    """Public summary for a /model-info style endpoint (honest metadata)."""
    state = _load()
    if not state.get("available"):
        return {"available": False, "reason": state.get("reason")}
    cfg = state["config"]
    return {
        "available": True,
        "model_type": cfg.get("model_type"),
        "model_version": cfg.get("model_version"),
        "trained_rows": cfg.get("trained_rows"),
        "label_source": cfg.get("label_source"),
        "test_metrics": cfg.get("test_metrics"),
        "split": cfg.get("split"),
        "feature_names": cfg.get("feature_names"),
        "feature_importance": cfg.get("feature_importance", {}),
    }
