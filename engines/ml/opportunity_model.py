"""ML Opportunity Estimation Model using RandomForestRegressor on MSSDS Intelligence data."""

from pathlib import Path
from typing import Tuple, Dict, Any, Union, Optional
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "outputs" / "mssds_district_sector_intelligence.csv"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "opportunity_model.joblib"

NUMERIC_FEATURES = [
    "industry_size",
    "organization_count",
    "candidate_aspiration",
    "mssds_trained_2022_23",
    "dsdp_training",
    "projected_training",
    "evidence_confidence",
]
CATEGORICAL_FEATURES = ["district", "sector"]
BOOLEAN_FEATURES = ["projection_available"]
TARGET_COL = "industry_opportunity_score"


class OpportunityModel:
    """RandomForestRegressor pipeline predicting industry_opportunity_score."""

    def __init__(self, random_state: int = 42, n_estimators: int = 100):
        self.random_state = random_state
        self.n_estimators = n_estimators

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
        """Ensure required feature columns exist in DataFrame."""
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
    ) -> Dict[str, float]:
        """Train the RandomForestRegressor model and evaluate on test set."""
        if df is None:
            path = Path(data_path) if data_path else DEFAULT_DATA_PATH
            if not path.exists():
                raise FileNotFoundError(f"Training dataset not found at {path}")
            df = pd.read_csv(path)

        # Drop rows where target is NaN
        valid_df = df.dropna(subset=[TARGET_COL]).copy()
        if valid_df.empty:
            raise ValueError(f"No valid rows found with target column '{TARGET_COL}'.")

        X = self._prepare_data(valid_df)
        y = valid_df[TARGET_COL].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.random_state
        )

        self.pipeline.fit(X_train, y_train)
        self.is_fitted = True

        y_pred = self.pipeline.predict(X_test)
        mae = float(mean_absolute_error(y_test, y_pred))
        r2 = float(r2_score(y_test, y_pred))

        return {"mae": mae, "r2": r2, "train_samples": len(X_train), "test_samples": len(X_test)}

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Predict opportunity scores for given features DataFrame."""
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted. Call train() or load() before predict().")

        X = self._prepare_data(df)
        return self.pipeline.predict(X)

    def evaluate(self, df: pd.DataFrame) -> Dict[str, float]:
        """Evaluate the fitted model on a dataset returning MAE and R2."""
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted. Call train() or load() before evaluate().")

        valid_df = df.dropna(subset=[TARGET_COL]).copy()
        if valid_df.empty:
            raise ValueError(f"No valid rows found with target column '{TARGET_COL}'.")

        X = self._prepare_data(valid_df)
        y_true = valid_df[TARGET_COL].values

        y_pred = self.pipeline.predict(X)
        mae = float(mean_absolute_error(y_true, y_pred))
        r2 = float(r2_score(y_true, y_pred))

        return {"mae": mae, "r2": r2, "eval_samples": len(valid_df)}

    def save(self, model_path: Optional[Union[str, Path]] = None) -> Path:
        """Save the trained pipeline to disk using joblib."""
        if not self.is_fitted:
            raise RuntimeError("Cannot save an unfitted model.")
        path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.pipeline, path)
        return path

    def load(self, model_path: Optional[Union[str, Path]] = None) -> "OpportunityModel":
        """Load a trained pipeline from disk."""
        path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        if not path.exists():
            raise FileNotFoundError(f"Model file not found at {path}")
        self.pipeline = joblib.load(path)
        self.is_fitted = True
        return self

    def get_feature_importance(self) -> Dict[str, Any]:
        """Return feature importances for the trained RandomForest in a JSON-serializable format."""
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

