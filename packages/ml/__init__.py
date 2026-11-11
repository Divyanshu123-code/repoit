"""RepoPilot AI Machine Learning Package (packages/ml)."""

from packages.ml.dataset import (
    FEATURE_NAMES,
    TARGET_COLUMN,
    load_cm1,
    load_dataset,
    load_kc1,
)
from packages.ml.evaluator import (
    BenchmarkSuiteResult,
    ConfusionMatrixCounts,
    FoldMetrics,
    ModelCVResult,
    evaluate_model_cv,
    run_benchmark_suite,
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
    "ConfusionMatrixCounts",
    "DatasetInspectionReport",
    "FoldMetrics",
    "ModelCVResult",
    "build_model_pipeline",
    "evaluate_model_cv",
    "inspect_dataset",
    "load_cm1",
    "load_dataset",
    "load_kc1",
    "run_benchmark_suite",
]
