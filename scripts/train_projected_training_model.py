"""Script to train and save the core ProjectedTrainingModel on real dataset."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engines.ml.projected_training_model import ProjectedTrainingModel, DEFAULT_DATA_PATH, DEFAULT_MODEL_PATH


def main():
    print(f"[1/3] Loading real MSSDS intelligence dataset from: {DEFAULT_DATA_PATH}")
    model = ProjectedTrainingModel(
        n_estimators=100,
        random_state=42,
        max_depth=10,
    )

    print("[2/3] Training ProjectedTrainingModel on valid projected_training records...")
    metrics = model.train(data_path=DEFAULT_DATA_PATH, test_size=0.2)

    print("\n--- Training & Evaluation Results ---")
    print(f"Training Samples : {metrics['train_samples']}")
    print(f"Testing Samples  : {metrics['test_samples']}")
    print(f"MAE             : {metrics['mae']:.4f}")
    print(f"RMSE            : {metrics['rmse']:.4f}")
    print(f"R² Score        : {metrics['r2']:.4f}")
    print(f"Baseline MAE    : {metrics['baseline_mae']:.4f}")
    print(f"Baseline RMSE   : {metrics['baseline_rmse']:.4f}")
    print(f"Note            : {metrics['note']}")

    print(f"\n[3/3] Saving model to: {DEFAULT_MODEL_PATH}")
    saved_path = model.save(DEFAULT_MODEL_PATH)
    print(f"Model saved successfully to: {saved_path}")

    importance = model.get_feature_importance()
    top_5 = importance.get("feature_importances", [])[:5]
    print("\nTop 5 Important Features:")
    for idx, f in enumerate(top_5, 1):
        print(f"  {idx}. {f['feature']}: {f['importance']:.4f}")


if __name__ == "__main__":
    main()
