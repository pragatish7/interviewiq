"""
ML prediction service - loads trained model and predicts interview scores.
"""
import os
import json
import logging
import numpy as np
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
MODEL_DIR = os.path.join(PROJECT_ROOT, "models")

_model = None
_scaler = None
_feature_names = None


def load_model():
    """Load the trained ML model, scaler, and feature names."""
    global _model, _scaler, _feature_names

    if _model is not None:
        return True

    try:
        import joblib
        model_path = os.path.join(MODEL_DIR, "model.pkl")
        scaler_path = os.path.join(MODEL_DIR, "scaler.pkl")
        features_path = os.path.join(MODEL_DIR, "feature_names.json")

        if not all(os.path.exists(p) for p in [model_path, scaler_path, features_path]):
            logger.warning("ML model files not found. Training default model...")
            from app.ml.train import train_and_evaluate
            train_and_evaluate()

        _model = joblib.load(model_path)
        _scaler = joblib.load(scaler_path)
        with open(features_path, "r") as f:
            _feature_names = json.load(f)

        logger.info("ML model loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to load ML model: {e}")
        return False


def predict(features: Dict[str, float]) -> Dict[str, Any]:
    """
    Predict overall interview score from features.
    Returns prediction with confidence.
    """
    if not load_model():
        return {
            "predicted_score": None,
            "confidence": 0.0,
            "method": "fallback",
            "feature_importance": {},
        }

    try:
        # Create feature array in correct order
        feature_array = np.array([
            [features.get(name, 0.0) for name in _feature_names]
        ])

        # Scale if needed
        if _scaler is not None:
            try:
                feature_array = _scaler.transform(feature_array)
            except Exception:
                pass

        # Predict
        prediction = _model.predict(feature_array)[0]
        predicted_score = round(float(np.clip(prediction, 0, 100)), 1)

        # Feature importance
        importance = {}
        if hasattr(_model, "feature_importances_"):
            imp_dict = dict(zip(_feature_names, _model.feature_importances_.tolist()))
            importance = dict(sorted(imp_dict.items(), key=lambda x: x[1], reverse=True)[:10])

        # Confidence estimation based on model properties
        confidence = 0.75
        if hasattr(_model, "estimators_"):
            # For ensemble methods, estimate via variance of estimators
            try:
                preds = np.array([est.predict(feature_array)[0]
                                  for est in _model.estimators_.flatten()[:50]])
                std = preds.std()
                confidence = max(0.5, min(0.95, 1 - std / 30))
            except Exception:
                confidence = 0.75

        return {
            "predicted_score": predicted_score,
            "confidence": round(confidence, 3),
            "method": "ml_model",
            "feature_importance": importance,
        }
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        return {
            "predicted_score": None,
            "confidence": 0.0,
            "method": "error",
            "feature_importance": {},
            "error": str(e),
        }


def get_model_info() -> Dict[str, Any]:
    """Get information about the loaded model."""
    load_model()
    if _model is None:
        return {"status": "not_loaded"}

    return {
        "status": "loaded",
        "model_type": type(_model).__name__,
        "n_features": len(_feature_names) if _feature_names else 0,
        "feature_names": _feature_names[:10] if _feature_names else [],
    }
