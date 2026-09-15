"""Supervised ML Model predicting projected_training from government economic & skill indicators using log1p transformation."""

from pathlib import Path
from typing import Dict, Any, Union, Optional, List
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "outputs" / "mssds_district_sector_intelligence.csv"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "projected_training_model.joblib"

NUMERIC_FEATURES = [
    "industry_size",
    "organization_count",
    "candidate_aspiration",
    "mssds_trained_2022_23",
    "dsdp_training",
    "evidence_confidence",
]
CATEGORICAL_FEATURES = ["district", "sector"]
BOOLEAN_FEATURES = ["projection_available"]
TARGET_COL = "projected_training"

EXCLUDED_COLS = [
    "industry_opportunity_score",
    "training_pressure_score",
    "projected_training",
]


class ProjectedTrainingModel:
    """RandomForestRegressor pipeline predicting projected_training using log1p internal target transform."""

    def __init__(self, random_state: int = 42, n_estimators: int = 100, max_depth: int = 10):
        self.random_state = random_state
        self.n_estimators = n_estimators
        self.max_depth = max_depth

        numeric_transformer = SimpleImputer(strategy="median")
        categorical_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]
        )
        boolean_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
            ]
        )

        self.preprocessor = ColumnTransformer(
            transformers=[
                ("num", numeric_transformer, NUMERIC_FEATURES),
                ("cat", categorical_transformer, CATEGORICAL_FEATURES),
                ("bool", boolean_transformer, BOOLEAN_FEATURES),
            ]
        )

        self.model = RandomForestRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            random_state=self.random_state,
        )

        self.pipeline = Pipeline(
            steps=[
                ("preprocessor", self.preprocessor),
                ("regressor", self.model),
            ]
        )
        self.is_fitted = False

    def _prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare feature matrix ensuring exact required schema."""
        df = df.copy()

        for col in NUMERIC_FEATURES:
            if col not in df.columns:
                df[col] = np.nan

        for col in CATEGORICAL_FEATURES:
            if col not in df.columns:
                df[col] = "Unknown"

        for col in BOOLEAN_FEATURES:
            if col not in df.columns:
                df[col] = 0
            else:
                df[col] = df[col].astype(int)

        return df

    def train(
        self,
        df: Optional[pd.DataFrame] = None,
        data_path: Optional[Union[str, Path]] = None,
        test_size: float = 0.2,
    ) -> Dict[str, Any]:
        """Train model on non-null projected_training rows using log1p target and evaluate in original scale."""
        if df is None:
            path = Path(data_path) if data_path else DEFAULT_DATA_PATH
            if not path.exists():
                raise FileNotFoundError(f"Training dataset not found at {path}")
            df = pd.read_csv(path)

        # Filter strictly for valid non-null target rows
        valid_df = df.dropna(subset=[TARGET_COL]).copy()
        if valid_df.empty:
            raise ValueError(f"No valid rows found with target column '{TARGET_COL}'.")

        X = self._prepare_data(valid_df)
        y_raw = valid_df[TARGET_COL].values

        X_train, X_test, y_train_raw, y_test_raw = train_test_split(
            X, y_raw, test_size=test_size, random_state=self.random_state
        )

        # Log1p internal target transform
        y_train_log = np.log1p(np.maximum(0, y_train_raw))

        self.pipeline.fit(X_train, y_train_log)
        self.is_fitted = True

        # Predict and inverse transform expm1 clipped to 0
        y_pred = self.predict(X_test)

        mae = float(mean_absolute_error(y_test_raw, y_pred))
        rmse = float(root_mean_squared_error(y_test_raw, y_pred))
        r2 = float(r2_score(y_test_raw, y_pred))

        # Baseline evaluation (predicting median of y_train_raw)
        baseline_pred = np.full_like(y_test_raw, fill_value=np.median(y_train_raw))
        baseline_mae = float(mean_absolute_error(y_test_raw, baseline_pred))
        baseline_rmse = float(root_mean_squared_error(y_test_raw, baseline_pred))

        return {
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "baseline_mae": baseline_mae,
            "baseline_rmse": baseline_rmse,
            "note": "Trained internally on log1p(projected_training); predictions inverse-transformed via expm1() clipped to 0.",
        }

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Predict projected_training values in original scale (expm1 clipped to 0)."""
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted. Call train() or load() before predict().")

        X = self._prepare_data(df)
        log_preds = self.pipeline.predict(X)
        raw_preds = np.expm1(log_preds)
        return np.maximum(0.0, raw_preds)

    def evaluate(self, df: pd.DataFrame) -> Dict[str, float]:
        """Evaluate fitted model on a dataset returning MAE, RMSE, and R2 in original scale."""
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted. Call train() or load() before evaluate().")

        valid_df = df.dropna(subset=[TARGET_COL]).copy()
        if valid_df.empty:
            raise ValueError(f"No valid rows found with target column '{TARGET_COL}'.")

        y_true = valid_df[TARGET_COL].values
        y_pred = self.predict(valid_df)

        mae = float(mean_absolute_error(y_true, y_pred))
        rmse = float(root_mean_squared_error(y_true, y_pred))
        r2 = float(r2_score(y_true, y_pred))

        return {
            "eval_samples": len(valid_df),
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
        }

    def save(self, model_path: Optional[Union[str, Path]] = None) -> Path:
        """Save fitted pipeline model to disk."""
        if not self.is_fitted:
            raise RuntimeError("Cannot save an unfitted model.")
        path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.pipeline, path)
        return path

    def load(self, model_path: Optional[Union[str, Path]] = None) -> "ProjectedTrainingModel":
        """Load fitted pipeline model from disk."""
        path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        if not path.exists():
            raise FileNotFoundError(f"Model file not found at {path}")
        self.pipeline = joblib.load(path)
        self.is_fitted = True
        return self

    def get_feature_importance(self) -> Dict[str, Any]:
        """Return feature importances formatted with original feature names."""
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted. Call train() or load() before get_feature_importance().")

        preprocessor = self.pipeline.named_steps["preprocessor"]
        regressor = self.pipeline.named_steps["regressor"]

        feature_names = list(preprocessor.get_feature_names_out())
        importances = regressor.feature_importances_

        feature_importance_list = [
            {"feature": name, "importance": float(imp)}
            for name, imp in zip(feature_names, importances)
        ]
        feature_importance_list.sort(key=lambda x: x["importance"], reverse=True)

        return {
            "total_features": len(feature_importance_list),
            "feature_importances": feature_importance_list,
        }
