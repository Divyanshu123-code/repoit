"""Model registry and leakage-safe Pipeline factory for defect prediction (P3-02)."""

import logging
from typing import Any, Final

from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler
from sklearn.tree import DecisionTreeClassifier

logger = logging.getLogger(__name__)

# Check if native XGBoost with OpenMP is loadable
_XGB_AVAILABLE = False
try:
    from xgboost import XGBClassifier

    # Test initialization
    _test_xgb = XGBClassifier(n_estimators=1)
    _XGB_AVAILABLE = True
except Exception:  # noqa: BLE001 - catch platform C-library errors (e.g. XGBoostError on macOS without libomp)
    _XGB_AVAILABLE = False
    logger.info(
        "Native XGBoost library unavailable; falling back to HistGradientBoostingClassifier."
    )

MODEL_METADATA: Final[dict[str, dict[str, str]]] = {
    "dummy": {
        "display_name": "Dummy Baseline",
        "family": "Baseline",
        "description": "Stratified random chance baseline matching class frequencies. Provides floor benchmark for evaluation.",
        "scaling_required": "No",
    },
    "logreg": {
        "display_name": "Logistic Regression",
        "family": "Linear",
        "description": "L2-regularized logistic regression with balanced class weights to compensate for severe defect imbalance.",
        "scaling_required": "Yes (RobustScaler)",
    },
    "decision_tree": {
        "display_name": "Decision Tree",
        "family": "Tree",
        "description": "CART decision tree with balanced class weights and depth restriction (max_depth=5) to prevent overfitting.",
        "scaling_required": "No (invariant to monotonic scaling)",
    },
    "random_forest": {
        "display_name": "Random Forest",
        "family": "Bagging Ensemble",
        "description": "Ensemble of 100 de-correlated decision trees with balanced subsample weights for robust defect risk estimation.",
        "scaling_required": "No",
    },
    "xgboost": {
        "display_name": "XGBoost / Gradient Boosting",
        "family": "Boosting Ensemble",
        "description": "Gradient Boosted decision trees optimizing binary cross-entropy with class reweighting, depth limit (4), and shrinkage (0.05).",
        "scaling_required": "No",
    },
}

SUPPORTED_MODELS: Final[list[str]] = list(MODEL_METADATA.keys())


def build_model_pipeline(
    model_type: str,
    scale_pos_weight: float = 1.0,
    random_state: int = 42,
) -> Pipeline:
    """Build a leakage-safe scikit-learn Pipeline with preprocessing and classifier.

    All transformations (e.g. RobustScaler) are encapsulated inside the Pipeline,
    ensuring fit/transform is strictly executed on training folds with zero leakage
    into validation or test splits.

    Args:
        model_type: One of 'dummy', 'logreg', 'decision_tree', 'random_forest', 'xgboost'.
        scale_pos_weight: Ratio of negative to positive samples, used for gradient boosting.
        random_state: Seed for deterministic reproducibility.

    Returns:
        Configured sklearn.pipeline.Pipeline.
    """
    clean_type = model_type.strip().lower()
    if clean_type not in MODEL_METADATA:
        msg = f"Unknown model type '{model_type}'. Expected one of {SUPPORTED_MODELS}."
        raise ValueError(msg)

    steps: list[tuple[str, Any]] = []

    if clean_type == "dummy":
        classifier = DummyClassifier(strategy="stratified", random_state=random_state)
    elif clean_type == "logreg":
        steps.append(("scaler", RobustScaler()))
        classifier = LogisticRegression(
            C=1.0,
            class_weight="balanced",
            solver="liblinear",
            max_iter=1000,
            random_state=random_state,
        )
    elif clean_type == "decision_tree":
        classifier = DecisionTreeClassifier(
            criterion="gini",
            max_depth=5,
            min_samples_split=10,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=random_state,
        )
    elif clean_type == "random_forest":
        classifier = RandomForestClassifier(
            n_estimators=100,
            criterion="gini",
            max_depth=8,
            min_samples_split=6,
            min_samples_leaf=3,
            class_weight="balanced",
            random_state=random_state,
            n_jobs=1,
        )
    elif clean_type in {"xgboost", "gradient_boosting"}:
        if _XGB_AVAILABLE:
            from xgboost import XGBClassifier

            classifier = XGBClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=max(1.0, scale_pos_weight),
                eval_metric="logloss",
                random_state=random_state,
                n_jobs=1,
            )
        else:
            classifier = HistGradientBoostingClassifier(
                max_iter=100,
                max_depth=4,
                learning_rate=0.05,
                class_weight="balanced",
                random_state=random_state,
            )
    else:
        msg = f"Unsupported model type: {clean_type}"
        raise ValueError(msg)

    steps.append(("classifier", classifier))
    return Pipeline(steps=steps)
