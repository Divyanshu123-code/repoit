"""RepoPilot AI Machine Learning Package (packages/ml)."""

from packages.ml.dataset import (
    FEATURE_NAMES,
    TARGET_COLUMN,
    load_cm1,
    load_dataset,
    load_kc1,
)
from packages.ml.error_analysis import (
    CohortFeatureProfile,
    ErrorAnalysisReport,
    ThresholdMetricPoint,
    perform_error_analysis,
)
from packages.ml.evaluator import (
    BenchmarkSuiteResult,
    ConfusionMatrixCounts,
    FoldMetrics,
    ModelCVResult,
    evaluate_model_cv,
    run_benchmark_suite,
)
from packages.ml.explainability import (
    ShapExplanationResult,
    ShapFeatureImportance,
    compute_shap_explanations,
)
from packages.ml.inspector import DatasetInspectionReport, inspect_dataset
from packages.ml.models import (
    MODEL_METADATA,
    SUPPORTED_MODELS,
    build_model_pipeline,
)

__all__ = [
    "FEATURE_NAMES",
    "MODEL_METADATA",
    "SUPPORTED_MODELS",
    "TARGET_COLUMN",
    "BenchmarkSuiteResult",
    "CohortFeatureProfile",
    "ConfusionMatrixCounts",
    "DatasetInspectionReport",
    "ErrorAnalysisReport",
    "FoldMetrics",
    "ModelCVResult",
    "ShapExplanationResult",
    "ShapFeatureImportance",
    "ThresholdMetricPoint",
    "build_model_pipeline",
    "compute_shap_explanations",
    "evaluate_model_cv",
    "inspect_dataset",
    "load_cm1",
    "load_dataset",
    "load_kc1",
    "perform_error_analysis",
    "run_benchmark_suite",
]
