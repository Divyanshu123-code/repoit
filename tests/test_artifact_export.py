"""Tests for model artifact serialization, model card schema, and inference (P3-04)."""

import json
from pathlib import Path

import pytest
from sklearn.pipeline import Pipeline

from packages.ml.dataset import load_cm1
from packages.ml.export import (
    DEFAULT_ARTIFACTS_DIR,
    export_champion_artifact,
    load_model_artifact,
    predict_defect_risk,
)


class TestArtifactExportAndLoading:
    """Validate model serialization and model_card.json creation."""

    def test_export_champion_artifact_to_custom_dir(self, tmp_path: Path) -> None:
        cm1 = load_cm1()
        model_path, card_path = export_champion_artifact(
            df=cm1,
            dataset_name="cm1",
            model_type="random_forest",
            version="1.0.0-test",
            output_dir=tmp_path,
        )

        assert model_path.exists()
        assert model_path.stat().st_size > 10_000, (
            "Serialized joblib artifact should be non-trivial size"
        )
        assert card_path.exists()

        # Validate loaded card schema
        with open(card_path, encoding="utf-8") as f:
            card_dict = json.load(f)

        assert card_dict["model_name"] == "RepoPilot Defect Risk Predictor"
        assert card_dict["model_version"] == "1.0.0-test"
        assert "metrics" in card_dict
        assert "limitations" in card_dict
        assert "training_dataset" in card_dict
        assert len(card_dict["top_contributing_features"]) > 0

    def test_load_model_artifact_success(self, tmp_path: Path) -> None:
        cm1 = load_cm1()
        export_champion_artifact(
            df=cm1,
            dataset_name="cm1",
            model_type="random_forest",
            version="1.0.0-test",
            output_dir=tmp_path,
        )

        pipeline, card = load_model_artifact(tmp_path)
        assert isinstance(pipeline, Pipeline)
        assert isinstance(card, dict)
        assert card["model_version"] == "1.0.0-test"

    def test_load_model_artifact_missing_raises_file_not_found(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(FileNotFoundError):
            load_model_artifact(tmp_path)


class TestPredictDefectRisk:
    """Validate inference function, rule labels, and risk banding."""

    def test_predict_defect_risk_format_and_rules(self, tmp_path: Path) -> None:
        cm1 = load_cm1()
        export_champion_artifact(
            df=cm1,
            dataset_name="cm1",
            model_type="random_forest",
            version="1.0.0",
            output_dir=tmp_path,
        )
        pipeline, _ = load_model_artifact(tmp_path)

        sample_features = {
            "loc": 50.0,
            "v(g)": 10.0,
            "ev(g)": 5.0,
            "iv(g)": 8.0,
            "n": 160.0,
            "v": 900.0,
            "l": 0.04,
            "d": 22.0,
            "i": 40.0,
            "e": 19800.0,
            "b": 0.30,
            "t": 1100.0,
            "lOCode": 40.0,
            "lOComment": 2.0,
            "lOBlank": 8.0,
            "locCodeAndComment": 0.0,
            "uniq_Op": 20.0,
            "uniq_Opnd": 25.0,
            "total_Op": 100.0,
            "total_Opnd": 60.0,
            "branchCount": 19.0,
        }

        res = predict_defect_risk(pipeline, sample_features, model_version="1.0.0")

        # Verify Rule 5: labeled source
        assert res["source"] == "ml_predicted"

        # Verify Rule 6: risk estimate disclaimer & model version
        assert "risk estimates" in res["disclaimer"].lower()
        assert res["model_version"] == "1.0.0"

        # Verify risk probabilities and banding
        assert 0.0 <= res["risk_probability"] <= 1.0
        assert res["risk_band"] in {"low", "medium", "high"}
        assert len(res["top_features"]) > 0

    def test_predict_defect_risk_bands(self, tmp_path: Path) -> None:
        cm1 = load_cm1()
        export_champion_artifact(
            df=cm1,
            dataset_name="cm1",
            model_type="random_forest",
            version="1.0.0",
            output_dir=tmp_path,
        )
        pipeline, _ = load_model_artifact(tmp_path)

        # Zeroed clean features should yield low risk
        sample_keys = ["loc", "v(g)", "v", "e"]
        clean_features = {k: 0.0 for k in sample_keys}
        clean_res = predict_defect_risk(
            pipeline, clean_features, threshold_medium=0.5, threshold_high=0.8
        )
        assert clean_res["risk_band"] in {"low", "medium"}


class TestRepoArtifactFiles:
    """Validate persisted artifacts in packages/ml/artifacts/."""

    def test_persisted_joblib_and_model_card_exist(self) -> None:
        model_file = DEFAULT_ARTIFACTS_DIR / "champion_model.joblib"
        card_file = DEFAULT_ARTIFACTS_DIR / "model_card.json"

        assert model_file.exists(), (
            "champion_model.joblib must exist in packages/ml/artifacts/"
        )
        assert card_file.exists(), (
            "model_card.json must exist in packages/ml/artifacts/"
        )

        with open(card_file, encoding="utf-8") as f:
            card_data = json.load(f)

        assert card_data["model_version"] == "1.0.0"
        assert card_data["class_imbalance_ratio"] > 1.0
        assert "metrics" in card_data
        assert "limitations" in card_data
        assert any("Rule 6" in lim for lim in card_data["limitations"])
