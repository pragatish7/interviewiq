"""
ML model training pipeline for interview performance scoring.
Trains a Gradient Boosting model to predict overall interview scores.
"""
import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# Project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODEL_DIR = os.path.join(PROJECT_ROOT, "models")

os.makedirs(MODEL_DIR, exist_ok=True)


def load_sample_data(csv_path: Optional[str] = None) -> pd.DataFrame:
    """Load interview dataset from CSV."""
    if csv_path is None:
        csv_path = os.path.join(DATA_DIR, "sample", "interview_dataset.csv")

    if not os.path.exists(csv_path):
        logger.warning(f"Dataset not found at {csv_path}. Generating synthetic data...")
        return generate_synthetic_data()

    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} records from {csv_path}")
    return df


def generate_synthetic_data(n_samples: int = 200) -> pd.DataFrame:
    """Generate synthetic training data for the ML model."""
    np.random.seed(42)

    data = {
        "interview_id": range(1, n_samples + 1),
        "speaking_rate": np.random.normal(140, 30, n_samples).clip(60, 250),
        "filler_count": np.random.poisson(8, n_samples),
        "filler_rate": np.random.normal(5, 3, n_samples).clip(0, 20),
        "pause_count": np.random.poisson(10, n_samples),
        "avg_pause_duration": np.random.exponential(0.8, n_samples).clip(0.1, 4),
        "speech_duration": np.random.normal(300, 120, n_samples).clip(60, 900),
        "word_count": np.random.normal(500, 200, n_samples).clip(100, 1500),
        "sentence_count": np.random.normal(30, 15, n_samples).clip(5, 100),
        "vocabulary_diversity": np.random.normal(0.6, 0.12, n_samples).clip(0.2, 0.95),
        "repetition_rate": np.random.normal(0.08, 0.04, n_samples).clip(0, 0.3),
        "sentiment_score": np.random.normal(0.1, 0.3, n_samples).clip(-1, 1),
        "clarity_score": np.random.normal(72, 15, n_samples).clip(20, 100),
        "fluency_score": np.random.normal(70, 15, n_samples).clip(20, 100),
        "communication_score": np.random.normal(72, 14, n_samples).clip(20, 100),
        "answer_quality": np.random.normal(70, 16, n_samples).clip(20, 100),
        "star_score": np.random.normal(55, 25, n_samples).clip(0, 100),
        "professionalism_score": np.random.normal(73, 12, n_samples).clip(20, 100),
        "confidence_delivery_score": np.random.normal(70, 14, n_samples).clip(20, 100),
        "face_visibility": np.random.normal(75, 15, n_samples).clip(10, 100),
        "camera_presence": np.random.normal(72, 14, n_samples).clip(10, 100),
        "pace_consistency": np.random.normal(0.65, 0.15, n_samples).clip(0, 1),
    }

    # Create realistic target scores based on features
    df = pd.DataFrame(data)

    # Generate overall_score as weighted combination + noise
    df["overall_score"] = (
        df["communication_score"] * 0.15 +
        df["answer_quality"] * 0.20 +
        df["clarity_score"] * 0.10 +
        df["fluency_score"] * 0.10 +
        np.clip(100 - df["filler_rate"] * 8, 30, 100) * 0.10 +
        df["confidence_delivery_score"] * 0.10 +
        df["professionalism_score"] * 0.10 +
        df["vocabulary_diversity"] * 100 * 0.05 +
        df["professionalism_score"] * 0.05 +
        df["camera_presence"] * 0.05
    )

    # Add some noise
    df["overall_score"] += np.random.normal(0, 3, n_samples)
    df["overall_score"] = df["overall_score"].clip(15, 98).round(1)

    # Save generated data
    save_path = os.path.join(DATA_DIR, "sample", "interview_dataset.csv")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    df.to_csv(save_path, index=False)
    logger.info(f"Generated synthetic dataset with {n_samples} samples")

    return df


def preprocess_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """Preprocess data for training."""
    # Target
    y = df["overall_score"].copy()

    # Features - exclude target and id columns
    exclude_cols = ["interview_id", "overall_score"]
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    X = df[feature_cols].copy()

    # Handle missing values
    X = X.fillna(X.median())

    # Ensure all numeric
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors="coerce").fillna(0)

    return X, y


def train_model(X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
    """Train the ML model and return results."""
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    import joblib

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train multiple models
    models = {
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=100, max_depth=5, learning_rate=0.1,
            min_samples_split=10, random_state=42
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=100, max_depth=8, min_samples_split=10, random_state=42
        ),
        "ridge": Ridge(alpha=1.0),
    }

    results = {}
    best_model_name = None
    best_r2 = -999

    for name, model in models.items():
        logger.info(f"Training {name}...")
        if name == "ridge":
            model.fit(X_train_scaled, y_train)
            y_pred = model.predict(X_test_scaled)
        else:
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)

        # Cross-validation
        if name == "ridge":
            cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5, scoring="r2")
        else:
            cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring="r2")

        results[name] = {
            "mae": round(mae, 3),
            "rmse": round(rmse, 3),
            "r2": round(r2, 4),
            "cv_r2_mean": round(cv_scores.mean(), 4),
            "cv_r2_std": round(cv_scores.std(), 4),
        }

        if r2 > best_r2:
            best_r2 = r2
            best_model_name = name

        logger.info(f"  {name}: MAE={mae:.3f}, RMSE={rmse:.3f}, R²={r2:.4f}")

    # Save best model
    best_model = models[best_model_name]
    model_path = os.path.join(MODEL_DIR, "model.pkl")
    scaler_path = os.path.join(MODEL_DIR, "scaler.pkl")
    feature_names_path = os.path.join(MODEL_DIR, "feature_names.json")

    joblib.dump(best_model, model_path)
    joblib.dump(scaler, scaler_path)
    with open(feature_names_path, "w") as f:
        json.dump(list(X.columns), f)

    # Feature importance
    if hasattr(best_model, "feature_importances_"):
        importance = dict(zip(X.columns, best_model.feature_importances_.tolist()))
        importance_sorted = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
    else:
        importance_sorted = {}

    return {
        "best_model": best_model_name,
        "results": results,
        "feature_importance": importance_sorted,
        "model_path": model_path,
        "scaler_path": scaler_path,
        "n_samples": len(X),
        "n_features": len(X.columns),
    }


def train_and_evaluate(csv_path: Optional[str] = None) -> Dict[str, Any]:
    """Main training pipeline."""
    logger.info("Starting ML training pipeline...")

    df = load_sample_data(csv_path)
    X, y = preprocess_data(df)
    results = train_model(X, y)

    logger.info(f"\nTraining complete! Best model: {results['best_model']}")
    logger.info(f"Results: {json.dumps(results['results'], indent=2)}")
    logger.info(f"Top features: {list(results['feature_importance'].keys())[:10]}")

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    csv_path = sys.argv[1] if len(sys.argv) > 1 else None
    train_and_evaluate(csv_path)
