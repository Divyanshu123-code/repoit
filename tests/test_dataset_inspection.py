"""Tests for dataset loading, inspection, and exploratory analysis (P3-01)."""

from pathlib import Path

import pandas as pd
import pytest

from packages.ml.dataset import (
    FEATURE_NAMES,
    TARGET_COLUMN,
    load_cm1,
    load_dataset,
    load_kc1,
)
from packages.ml.inspector import (
    DatasetInspectionReport,
    find_contradictory_instances,
    inspect_dataset,
)


class TestDatasetLoading:
    """Validate loading of NASA PROMISE defect datasets."""

    def test_load_cm1_shape_and_features(self) -> None:
        df = load_cm1()
        assert df.shape == (498, 22)
        for col in FEATURE_NAMES:
            assert col in df.columns
            assert pd.api.types.is_numeric_dtype(df[col])
        assert TARGET_COLUMN in df.columns
        assert set(df[TARGET_COLUMN].unique()).issubset({0, 1})

    def test_load_kc1_shape_and_features(self) -> None:
        df = load_kc1()
        assert df.shape == (2109, 22)
        for col in FEATURE_NAMES:
            assert col in df.columns
            assert pd.api.types.is_numeric_dtype(df[col])
        assert TARGET_COLUMN in df.columns
        assert set(df[TARGET_COLUMN].unique()).issubset({0, 1})

    def test_unknown_dataset_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown dataset 'invalid'"):
            load_dataset("invalid")

    def test_nonexistent_dir_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_dataset("cm1", data_dir=tmp_path)


class TestDatasetInspection:
    """Validate dataset health, imbalance, and duplicate detection."""

    def test_cm1_inspection_metrics(self) -> None:
        df = load_cm1()
        report = inspect_dataset(df, "cm1")

        assert isinstance(report, DatasetInspectionReport)
        assert report.name == "cm1"
        assert report.rows == 498
        assert report.columns == 22
        assert report.feature_count == 21
        assert report.positive_count == 49
        assert report.negative_count == 449
        assert pytest.approx(report.positive_percentage, rel=1e-2) == 9.84
        assert pytest.approx(report.imbalance_ratio, rel=1e-2) == 9.16
        assert report.exact_duplicates_count == 56
        assert report.missing_values_total == 0

    def test_kc1_inspection_metrics(self) -> None:
        df = load_kc1()
        report = inspect_dataset(df, "kc1")

        assert report.name == "kc1"
        assert report.rows == 2109
        assert report.positive_count == 326
        assert report.negative_count == 1783
        assert pytest.approx(report.positive_percentage, rel=1e-2) == 15.46
        assert report.exact_duplicates_count == 897
        assert report.missing_values_total == 0

    def test_find_contradictory_instances(self) -> None:
        cm1 = load_cm1()
        contra = find_contradictory_instances(cm1)
        assert len(contra) == 2  # 1 contradictory pair (2 rows)

        # Create synthetic fixture to verify contradiction logic
        synthetic = pd.DataFrame(
            {
                "loc": [10.0, 10.0, 20.0],
                "v(g)": [2.0, 2.0, 5.0],
                "defects": [0, 1, 0],
            }
        )
        for feat in FEATURE_NAMES:
            if feat not in synthetic.columns:
                synthetic[feat] = 1.0

        synth_contra = find_contradictory_instances(synthetic)
        assert len(synth_contra) == 2
        assert synth_contra["loc"].tolist() == [10.0, 10.0]

    def test_report_serialization_and_markdown(self) -> None:
        df = load_cm1()
        report = inspect_dataset(df, "cm1")

        as_dict = report.to_dict()
        assert as_dict["name"] == "cm1"
        assert as_dict["rows"] == 498

        md = report.format_markdown()
        assert "# Dataset Inspection" in md
        assert "NASA MDP" in md
        assert "Class Imbalance" in md
        assert "Duplicate & Data Quality" in md

    def test_dataset_inspection_report_file_exists(self) -> None:
        report_file = Path("docs/eval/dataset_inspection.md")
        assert report_file.exists(), "docs/eval/dataset_inspection.md must exist"
        content = report_file.read_text(encoding="utf-8")
        assert "NASA PROMISE CM1 & KC1" in content
        assert "Imbalance Ratio" in content
        assert "Public Domain" in content
