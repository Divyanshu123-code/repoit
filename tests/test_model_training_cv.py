"""Tests for leakage-safe ML Pipeline, model training, and Cross-Validation (P3-02)."""

from pathlib import Path

import pytest
from sklearn.pipeline import Pipeline

from packages.ml.dataset import load_cm1, load_kc1
from packages.ml.evaluator import (
    BenchmarkSuiteResult,
    ConfusionMatrixCounts,
    ModelCVResult,
    evaluate_model_cv,
    run_benchmark_suite,
)
from packages.ml.models import (
    SUPPORTED_MODELS,
    build_model_pipeline,
)


class TestModelPipelines:
    """Validate construction and configuration of leakage-safe scikit-learn Pipelines."""

    @pytest.mark.parametrize("model_type", SUPPORTED_MODELS)
    def test_pipeline_construction_for_all_supported_models(
        self, model_type: str
    ) -> None:
        pipe = build_model_pipeline(model_type, scale_pos_weight=5.0, random_state=42)
        assert isinstance(pipe, Pipeline)
        assert "classifier" in pipe.named_steps

    def test_scaling_included_for_linear_models_only(self) -> None:
        logreg_pipe = build_model_pipeline("logreg")
        assert "scaler" in logreg_pipe.named_steps

        rf_pipe = build_model_pipeline("random_forest")
        assert "scaler" not in rf_pipe.named_steps

        dt_pipe = build_model_pipeline("decision_tree")
        assert "scaler" not in dt_pipe.named_steps

    def test_unknown_model_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown model type 'invalid'"):
            build_model_pipeline("invalid")


class TestCrossValidationEvaluation:
    """Validate Stratified K-Fold Cross-Validation execution and metric aggregation."""

    def test_evaluate_dummy_baseline_cv(self) -> None:
        cm1 = load_cm1()
        res = evaluate_model_cv("dummy", cm1, n_splits=5, random_state=42)

        assert isinstance(res, ModelCVResult)
        assert res.model_type == "dummy"
        assert res.folds_count == 5
        assert len(res.folds) == 5
        # Stratified dummy should yield near chance ROC-AUC (~0.5)
        assert 0.35 <= res.roc_auc_mean <= 0.65
        assert isinstance(res.oof_confusion, ConfusionMatrixCounts)
        assert (
            res.oof_confusion.true_negatives
            + res.oof_confusion.false_positives
            + res.oof_confusion.false_negatives
            + res.oof_confusion.true_positives
        ) == len(cm1)

    def test_evaluate_logreg_cv_on_cm1(self) -> None:
        cm1 = load_cm1()
        res = evaluate_model_cv("logreg", cm1, n_splits=5, random_state=42)

        assert res.roc_auc_mean > 0.70, (
            "Logistic Regression should achieve ROC-AUC > 0.70 on CM1"
        )
        assert res.pr_auc_mean > 0.20, (
            "PR-AUC should outperform dummy baseline (~0.098)"
        )
        assert res.recall_mean > 0.50, (
            "Recall should capture at least 50% of defects with class_weight='balanced'"
        )
        assert res.mean_latency_ms >= 0.0

    def test_evaluate_random_forest_cv_on_kc1(self) -> None:
        kc1 = load_kc1()
        # Fast 3-split test on KC1
        res = evaluate_model_cv("random_forest", kc1, n_splits=3, random_state=42)

        assert res.roc_auc_mean > 0.75, (
            "Random Forest should achieve ROC-AUC > 0.75 on KC1"
        )
        assert res.pr_auc_mean > 0.35, "PR-AUC on KC1 should exceed 0.35"
        assert res.folds_count == 3


class TestBenchmarkSuite:
    """Validate full 5-model benchmark runner and champion selection."""

    def test_run_benchmark_suite_on_cm1_subset(self) -> None:
        cm1 = load_cm1()
        # Run suite with 3 candidate models
        suite = run_benchmark_suite(
            cm1,
            dataset_name="cm1",
            models=["dummy", "logreg", "decision_tree"],
            n_splits=3,
            random_state=42,
        )

        assert isinstance(suite, BenchmarkSuiteResult)
        assert suite.dataset_name == "cm1"
        assert len(suite.results) == 3
        assert suite.champion_model in {"logreg", "decision_tree"}
        assert "highest composite ranking" in suite.champion_reason

        md_table = suite.format_markdown_table()
        assert "| Model | Family | ROC-AUC" in md_table
        assert "Champion Selection" in md_table

    def test_model_comparison_documentation_exists_and_covers_requirements(
        self,
    ) -> None:
        doc_path = Path("docs/eval/ml_model_comparison.md")
        assert doc_path.exists(), (
            "docs/eval/ml_model_comparison.md must exist per Rule 11"
        )

        content = doc_path.read_text(encoding="utf-8")
        # Rule 11 required sections:
        assert "Evaluated Models: Architecture & Functional Role" in content
        assert "Training Methodology & Experimental Setup" in content
        assert "Benchmark Evaluation Results Across All Models" in content
        assert "Champion Model Selection & Architectural Rationale" in content
        assert "ROC-AUC" in content
        assert "PR-AUC" in content
        assert "Confusion Matrices" in content
        assert "Latency" in content
