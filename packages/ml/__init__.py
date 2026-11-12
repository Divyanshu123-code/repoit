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
from packages.ml.export import (
    DEFAULT_ARTIFACTS_DIR,
    ModelCard,
    export_champion_artifact,
    load_model_artifact,
    predict_defect_risk,
)
from packages.ml.inspector import DatasetInspectionReport, inspect_dataset
from packages.ml.models import (
    MODEL_METADATA,
    SUPPORTED_MODELS,
    build_model_pipeline,
)
from packages.ml.szz import (
    PythonDefectRecord,
    extract_radon_features,
    is_cosmetic_diff,
    is_fix_commit,
    mine_repository_szz,
)
from packages.ml.track_b import (
    DATASET_V1_PATH,
    generate_track_b_dataset,
    load_track_b_dataset,
)

__all__ = [
    "DATASET_V1_PATH",
    "DEFAULT_ARTIFACTS_DIR",
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
    "ModelCard",
    "PythonDefectRecord",
    "ShapExplanationResult",
    "ShapFeatureImportance",
    "ThresholdMetricPoint",
    "build_model_pipeline",
    "compute_shap_explanations",
    "evaluate_model_cv",
    "export_champion_artifact",
    "extract_radon_features",
    "generate_track_b_dataset",
    "inspect_dataset",
    "is_cosmetic_diff",
    "is_fix_commit",
    "load_cm1",
    "load_dataset",
    "load_kc1",
    "load_model_artifact",
    "load_track_b_dataset",
    "mine_repository_szz",
    "perform_error_analysis",
    "predict_defect_risk",
    "run_benchmark_suite",
]
