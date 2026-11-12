"""Unit and integration tests for Track B model training and cross-project evaluation (P3-06)."""

import json

import joblib
import numpy as np
import pandas as pd
import pytest

from packages.ml.dataset import FEATURE_NAMES, TARGET_COLUMN
from packages.ml.export import DEFAULT_ARTIFACTS_DIR
from packages.ml.train_track_b import (
    COMPARISON_DOC_PATH,
    TRACK_B_DOC_PATH,
    evaluate_held_out_projects,
    evaluate_model_project_wise_cv,
    run_track_b_benchmark,
)


@pytest.fixture
def mock_multi_project_df() -> pd.DataFrame:
    """Create a synthetic dataset across 3 distinct projects for testing project-wise CV."""
    rng = np.random.default_rng(42)
    n_per_proj = 30
    projects = ["proj_alpha", "proj_beta", "proj_gamma"]

    rows = []
    for proj in projects:
        for i in range(n_per_proj):
            row_data: dict[str, object] = {
                "project": proj,
                "file_path": f"{proj}/module_{i}.py",
                "commit_hash": f"hash_{proj}_{i}",
            }
            # Generate features
            for feat in FEATURE_NAMES:
                val = float(rng.uniform(1.0, 50.0))
                row_data[feat] = val

            # High LOC and cyclomatic complexity correlate with defects
            loc = float(row_data.get("loc", 10.0))
            is_defective = 1 if (loc > 35.0 or rng.random() > 0.8) else 0
            row_data[TARGET_COLUMN] = is_defective
            rows.append(row_data)

    df = pd.DataFrame(rows)
    # Ensure both classes exist in all projects
    for proj in projects:
        proj_slice = df[df["project"] == proj]
        if proj_slice[TARGET_COLUMN].nunique() < 2:
            df.loc[df[df["project"] == proj].index[0], TARGET_COLUMN] = 1
            df.loc[df[df["project"] == proj].index[1], TARGET_COLUMN] = 0
    return df


def test_evaluate_model_project_wise_cv(mock_multi_project_df: pd.DataFrame) -> None:
    """Test that Leave-One-Project-Out CV creates exactly one fold per project and accumulates metrics."""
    result = evaluate_model_project_wise_cv(
        model_type="logistic_regression",
        df=mock_multi_project_df,
        random_state=42,
    )

    assert result.model_type == "logistic_regression"
    assert result.folds_count == 3  # 3 distinct projects
    assert 0.0 <= result.roc_auc_mean <= 1.0
    assert 0.0 <= result.pr_auc_mean <= 1.0
    assert result.mean_latency_ms >= 0.0

    # Verify confusion matrix sums to total samples
    total_samples = len(mock_multi_project_df)
    cm = result.oof_confusion
    assert (
        cm.true_negatives + cm.false_positives + cm.false_negatives + cm.true_positives
        == total_samples
    )


def test_run_track_b_benchmark(mock_multi_project_df: pd.DataFrame) -> None:
    """Test running the full benchmark suite across all candidate models under project-wise CV."""
    suite = run_track_b_benchmark(mock_multi_project_df)

    assert suite.dataset_name == "track_b_python_v1"
    assert suite.total_samples == len(mock_multi_project_df)
    assert suite.positive_samples > 0
    assert suite.negative_samples > 0
    assert (
        len(suite.results) >= 4
    )  # dummy, logistic_regression, decision_tree, random_forest, xgboost/hist
    assert suite.champion_model in [
        "logistic_regression",
        "decision_tree",
        "random_forest",
        "xgboost",
    ]
    assert len(suite.champion_reason) > 20

    md_table = suite.format_markdown_table()
    assert "| Model |" in md_table
    assert "ROC-AUC" in md_table
    assert "PR-AUC" in md_table


def test_evaluate_held_out_projects(mock_multi_project_df: pd.DataFrame) -> None:
    """Test training on a subset of projects and evaluating strictly on held-out projects."""
    train_projects = ["proj_alpha", "proj_beta"]
    test_projects = ["proj_gamma"]

    metrics, cm, shap_res, err_rep = evaluate_held_out_projects(
        df=mock_multi_project_df,
        train_projects=train_projects,
        test_projects=test_projects,
        model_type="random_forest",
        random_state=42,
    )

    assert "roc_auc" in metrics
    assert "pr_auc" in metrics
    assert "recall" in metrics
    assert 0.0 <= metrics["roc_auc"] <= 1.0
    assert 0.0 <= metrics["pr_auc"] <= 1.0

    expected_test_count = len(
        mock_multi_project_df[mock_multi_project_df["project"] == "proj_gamma"]
    )
    assert cm["tn"] + cm["fp"] + cm["fn"] + cm["tp"] == expected_test_count

    # SHAP and error analysis verification
    assert shap_res is not None
    assert len(shap_res.feature_importances) > 0
    assert err_rep is not None
    assert err_rep.total_test_samples == expected_test_count


def test_track_b_documentation_artifacts() -> None:
    """Verify that Track B reports exist and include required comparative and evaluation sections."""
    assert TRACK_B_DOC_PATH.exists(), f"Missing {TRACK_B_DOC_PATH}"
    content = TRACK_B_DOC_PATH.read_text(encoding="utf-8")

    assert "Track B Training & Cross-Project Evaluation Report" in content
    assert "Leave-One-Project-Out" in content
    assert "Held-Out Projects Evaluation" in content
    assert "Track B (Modern Python) vs Track A (NASA Legacy C/C++)" in content
    assert "SHAP Feature Attribution" in content
    assert "Error Analysis" in content

    # Check comparison document
    assert COMPARISON_DOC_PATH.exists()
    comp_content = COMPARISON_DOC_PATH.read_text(encoding="utf-8")
    assert "Track B: Modern Python Mined Repositories" in comp_content


def test_track_b_exported_model_card() -> None:
    """Verify that the exported champion model card reflects Track B v2.0.0 per Hard Rules 5 and 6."""
    card_path = DEFAULT_ARTIFACTS_DIR / "model_card.json"
    assert card_path.exists(), f"Missing {card_path}"

    with open(card_path, "r", encoding="utf-8") as f:
        card = json.load(f)

    assert card["model_version"] == "2.0.0"
    assert "track_b" in card["training_dataset"].lower()
    assert "metrics" in card
    assert "roc_auc" in card["metrics"]
    assert "pr_auc" in card["metrics"]
    assert "risk_bands" in card

    # Hard Rule 6 compliance check
    limitations = " ".join(card.get("limitations", []))
    assert "risk estimates" in limitations.lower()
    assert (
        "never 'confirmed bugs'" in limitations.lower()
        or "never confirmed bugs" in limitations.lower()
    )

    # Model artifact check
    model_path = DEFAULT_ARTIFACTS_DIR / "champion_model.joblib"
    assert model_path.exists()
    pipeline = joblib.load(model_path)
    assert hasattr(pipeline, "predict_proba")
