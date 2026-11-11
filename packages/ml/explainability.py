"""Model interpretability and SHAP feature attribution for defect prediction (P3-03)."""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import shap
from sklearn.pipeline import Pipeline

from packages.ml.dataset import FEATURE_DESCRIPTIONS, FEATURE_NAMES


@dataclass
class ShapFeatureImportance:
    """Individual feature importance derived from mean absolute SHAP values."""

    feature: str
    mean_abs_shap: float
    rank: int
    description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ShapExplanationResult:
    """Aggregated SHAP explanations across a dataset evaluation partition."""

    model_name: str
    feature_importances: list[ShapFeatureImportance]
    mean_abs_shap: dict[str, float]
    base_value: float
    feature_names: list[str]
    raw_shap_values: list[list[float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "feature_importances": [f.to_dict() for f in self.feature_importances],
            "mean_abs_shap": self.mean_abs_shap,
            "base_value": self.base_value,
            "feature_names": self.feature_names,
        }

    def format_markdown_table(self, top_n: int = 10) -> str:
        """Format the top feature importances into Markdown."""
        lines = [
            f"### Global Feature Importance: `{self.model_name}` (Top {top_n} Features via SHAP)",
            "",
            "| Rank | Feature | Mean |SHAP| | Metric Category | Description |",
            "|---|---|---|---|---|",
        ]
        for f in self.feature_importances[:top_n]:
            category = (
                "McCabe Complexity"
                if "(g)" in f.feature or f.feature in {"loc", "branchCount"}
                else "Halstead Suite"
            )
            lines.append(
                f"| {f.rank} | `{f.feature}` | **{f.mean_abs_shap:.4f}** | {category} | {f.description} |"
            )
        return "\n".join(lines)


def compute_shap_explanations(
    pipeline: Pipeline,
    x_train: np.ndarray,
    x_test: np.ndarray,
    feature_names: list[str] | None = None,
    model_name: str = "Model",
) -> ShapExplanationResult:
    """Compute SHAP feature attribution values for a trained scikit-learn Pipeline.

    Args:
        pipeline: Fitted Pipeline containing optional transformers and final classifier.
        x_train: Training feature matrix.
        x_test: Test feature matrix to explain.
        feature_names: List of feature names matching columns in matrices.
        model_name: Descriptive name of the model.

    Returns:
        ShapExplanationResult containing feature rankings and explanations.
    """
    feats = feature_names if feature_names is not None else FEATURE_NAMES
    classifier = pipeline.named_steps["classifier"]

    # If pipeline includes transformers (e.g. RobustScaler), transform matrices first
    if len(pipeline.steps) > 1:
        transformer_steps = pipeline.steps[:-1]
        x_train_trans = x_train
        x_test_trans = x_test
        for _, step in transformer_steps:
            x_train_trans = step.transform(x_train_trans)
            x_test_trans = step.transform(x_test_trans)
    else:
        x_train_trans = x_train
        x_test_trans = x_test

    # Select appropriate SHAP Explainer
    try:
        explainer = shap.TreeExplainer(classifier)
        shap_out = explainer.shap_values(x_test_trans)
    except (TypeError, ValueError, AttributeError, RuntimeError):
        # Fall back to LinearExplainer or generic Explainer
        try:
            explainer = shap.LinearExplainer(classifier, x_train_trans)
            shap_out = explainer.shap_values(x_test_trans)
        except (TypeError, ValueError, AttributeError, RuntimeError):
            explainer = shap.Explainer(classifier, x_train_trans)
            shap_out = explainer(x_test_trans).values

    # Normalize shap_out to 2D numpy array for the positive (defective) class
    if isinstance(shap_out, list):
        # Multi-class output [class_0, class_1] -> take class_1
        positive_shap = np.asarray(shap_out[1] if len(shap_out) > 1 else shap_out[0])
    elif isinstance(shap_out, np.ndarray):
        if shap_out.ndim == 3:
            # Shape (samples, features, classes) -> take positive class 1
            positive_shap = (
                shap_out[:, :, 1] if shap_out.shape[2] > 1 else shap_out[:, :, 0]
            )
        else:
            positive_shap = shap_out
    else:
        positive_shap = np.asarray(shap_out)

    # Compute mean absolute SHAP value per feature
    mean_abs = np.mean(np.abs(positive_shap), axis=0)

    # Sort descending by importance
    sorted_indices = np.argsort(mean_abs)[::-1]

    importances: list[ShapFeatureImportance] = []
    mean_abs_dict: dict[str, float] = {}

    for rank, idx in enumerate(sorted_indices, start=1):
        feat = feats[idx]
        val = float(mean_abs[idx])
        desc = FEATURE_DESCRIPTIONS.get(feat, feat)
        mean_abs_dict[feat] = val
        importances.append(
            ShapFeatureImportance(
                feature=feat,
                mean_abs_shap=val,
                rank=rank,
                description=desc,
            )
        )

    base_val = float(
        getattr(explainer, "expected_value", 0.0)
        if not isinstance(getattr(explainer, "expected_value", 0.0), (list, np.ndarray))
        else explainer.expected_value[1]
        if len(getattr(explainer, "expected_value", [])) > 1
        else explainer.expected_value[0]
    )

    return ShapExplanationResult(
        model_name=model_name,
        feature_importances=importances,
        mean_abs_shap=mean_abs_dict,
        base_value=base_val,
        feature_names=feats,
        raw_shap_values=positive_shap.tolist(),
    )
