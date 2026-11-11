"""Tests for final test evaluation, SHAP explainability, and error analysis (P3-03)."""

from pathlib import Path

import numpy as np
import pandas as pd

from packages.ml.dataset import FEATURE_NAMES, TARGET_COLUMN, load_cm1
from packages.ml.error_analysis import (
    ErrorAnalysisReport,
    perform_error_analysis,
)
from packages.ml.evaluate_track_a import evaluate_held_out_test
from packages.ml.explainability import (
    ShapExplanationResult,
    compute_shap_explanations,
)
from packages.ml.models import build_model_pipeline


class TestShapExplainability:
    """Validate SHAP value computation and global feature attribution."""

    def test_compute_shap_on_random_forest(self) -> None:
        cm1 = load_cm1()
        features = [c for c in FEATURE_NAMES if c in cm1.columns]
        x_mat = cm1[features].to_numpy(dtype=float)[:60]
        y_vec = cm1[TARGET_COLUMN].to_numpy(dtype=int)[:60]

        pipe = build_model_pipeline("random_forest", random_state=42)
        pipe.fit(x_mat, y_vec)

        res = compute_shap_explanations(
            pipeline=pipe,
            x_train=x_mat,
            x_test=x_mat[:20],
            feature_names=features,
            model_name="Random Forest",
        )

        assert isinstance(res, ShapExplanationResult)
        assert res.model_name == "Random Forest"
        assert len(res.feature_importances) == len(features)
        assert res.feature_importances[0].rank == 1
        assert (
            res.feature_importances[0].mean_abs_shap
            >= res.feature_importances[-1].mean_abs_shap
        )

        as_dict = res.to_dict()
        assert "mean_abs_shap" in as_dict
        assert len(as_dict["feature_importances"]) == len(features)

        md = res.format_markdown_table(top_n=5)
        assert "Global Feature Importance" in md
        assert "Mean |SHAP|" in md

    def test_compute_shap_on_logistic_regression(self) -> None:
        cm1 = load_cm1()
        features = [c for c in FEATURE_NAMES if c in cm1.columns]
        x_mat = cm1[features].to_numpy(dtype=float)[:60]
        y_vec = cm1[TARGET_COLUMN].to_numpy(dtype=int)[:60]

        pipe = build_model_pipeline("logreg", random_state=42)
        pipe.fit(x_mat, y_vec)

        res = compute_shap_explanations(
            pipeline=pipe,
            x_train=x_mat,
            x_test=x_mat[:20],
            feature_names=features,
            model_name="Logistic Regression",
        )

        assert isinstance(res, ShapExplanationResult)
        assert len(res.feature_importances) == len(features)


class TestErrorAnalysis:
    """Validate prediction failure mode decomposition and threshold curves."""

    def test_perform_error_analysis_quadrants_and_thresholds(self) -> None:
        y_true = np.array([0, 0, 0, 1, 1, 0, 1, 0, 1, 0])
        y_prob = np.array([0.1, 0.2, 0.6, 0.8, 0.4, 0.05, 0.7, 0.3, 0.9, 0.15])
        df_dummy = pd.DataFrame(
            {
                "loc": [5.0, 10.0, 30.0, 50.0, 15.0, 3.0, 45.0, 12.0, 60.0, 8.0],
                "v(g)": [1.0, 2.0, 5.0, 8.0, 2.0, 1.0, 7.0, 2.0, 10.0, 1.0],
                "v": [20.0, 50.0, 300.0, 800.0, 100.0, 10.0, 600.0, 80.0, 1200.0, 40.0],
            }
        )

        report = perform_error_analysis(
            y_true=y_true,
            y_prob=y_prob,
            x_test_df=df_dummy,
            dataset_name="dummy",
            model_name="TestModel",
            default_threshold=0.5,
        )

        assert isinstance(report, ErrorAnalysisReport)
        assert (
            report.true_positives_count
            + report.false_positives_count
            + report.false_negatives_count
            + report.true_negatives_count
        ) == len(y_true)

        assert len(report.threshold_curve) == 9  # 0.1 to 0.9
        assert len(report.fn_insights) > 0
        assert len(report.fp_insights) > 0

        md = report.format_markdown()
        assert "Error Analysis & Failure Mode Inspection" in md
        assert "Prediction Quadrant Breakdown" in md
        assert "Decision Threshold Tuning Curve" in md


class TestTrackAEvaluationRunner:
    """Validate end-to-end evaluation runner and documentation generation."""

    def test_evaluate_held_out_test_execution(self) -> None:
        cm1 = load_cm1()
        metrics, cm, shap_res, err_rep, _x_test, y_test, _probs = (
            evaluate_held_out_test(
                cm1,
                dataset_name="cm1",
                model_type="random_forest",
                test_size=0.25,
                random_state=42,
            )
        )

        assert "roc_auc" in metrics
        assert "pr_auc" in metrics
        assert "recall" in metrics
        assert cm["tp"] + cm["fp"] + cm["fn"] + cm["tn"] == len(y_test)
        assert isinstance(shap_res, ShapExplanationResult)
        assert isinstance(err_rep, ErrorAnalysisReport)

    def test_track_a_report_file_exists_and_valid(self) -> None:
        doc = Path("docs/eval/ml_trackA.md")
        assert doc.exists(), "docs/eval/ml_trackA.md must exist per AC"

        content = doc.read_text(encoding="utf-8")
        assert "Track A Final Evaluation Report" in content
        assert "Held-Out Test Evaluation Summary" in content
        assert "SHAP (SHapley Additive exPlanations)" in content
        assert "Detailed Error Analysis & Failure Mode Inspection" in content
        assert "Decision Threshold Tuning Curve" in content

    def test_model_comparison_file_updated_with_held_out_results(self) -> None:
        doc = Path("docs/eval/ml_model_comparison.md")
        assert doc.exists()
        content = doc.read_text(encoding="utf-8")
        assert "Held-Out Test Evaluation & SHAP Feature Attribution" in content
        assert "0.820" in content
        assert "ml_trackA.md" in content
