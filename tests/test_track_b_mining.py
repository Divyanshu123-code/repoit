"""Tests for Track B repository mining, SZZ labeling, and Dataset v1 (P3-05)."""

from pathlib import Path

import pandas as pd
import pytest

from packages.ml.dataset import FEATURE_NAMES, TARGET_COLUMN
from packages.ml.szz import (
    extract_radon_features,
    is_cosmetic_diff,
    is_fix_commit,
)
from packages.ml.track_b import (
    generate_track_b_dataset,
    load_track_b_dataset,
)


class TestSZZCommitAndDiffAnalysis:
    """Validate SZZ heuristics and cosmetic noise filtering."""

    @pytest.mark.parametrize(
        "msg,expected",
        [
            ("Fix null pointer exception in parser", True),
            ("Resolve issue #42: division by zero crash", True),
            ("Patch defect in session authentication", True),
            ("Bugfix for query parameter encoding", True),
            ("Fixed error when loading corrupted zip", True),
            ("Update README with install instructions", False),
            ("Bump version to 1.0.4", False),
            ("Format code with black and ruff", False),
            ("Fix typo in docstring", False),
            ("Refactor folder structure", False),
        ],
    )
    def test_is_fix_commit_classification(self, msg: str, expected: bool) -> None:
        assert is_fix_commit(msg) == expected

    def test_is_cosmetic_diff_detection(self) -> None:
        # Cosmetic: only comments and blank lines
        cosmetic_diff = """
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
+# Added comment
 # Another comment
 
"""
        assert is_cosmetic_diff(cosmetic_diff) is True

        # Non-cosmetic: substantive code change
        code_diff = """
--- a/test.py
+++ b/test.py
@@ -5,2 +5,3 @@
-    return x
+    if x is None:
+        return 0
+    return x + 1
"""
        assert is_cosmetic_diff(code_diff) is False


class TestRadonFeatureExtraction:
    """Validate Radon static metrics extraction for Track B Python sources."""

    def test_extract_radon_features_valid_code(self) -> None:
        code = """
def calculate_metrics(items: list[int]) -> int:
    total = 0
    for item in items:
        if item > 0:
            total += item
        else:
            total -= 1
    return total
"""
        features = extract_radon_features(code)
        for col in FEATURE_NAMES:
            assert col in features
            assert isinstance(features[col], (int, float))

        # Check positive metrics
        assert features["loc"] > 5.0
        assert features["v(g)"] >= 3.0  # function + loop + if
        assert features["n"] > 0.0

    def test_extract_radon_features_handles_empty_and_syntax_error(self) -> None:
        empty_res = extract_radon_features("")
        assert len(empty_res) == len(FEATURE_NAMES)
        assert empty_res["loc"] == 0.0

        syntax_error_res = extract_radon_features("def invalid_syntax(:")
        assert len(syntax_error_res) == len(FEATURE_NAMES)


class TestTrackBDatasetV1:
    """Validate Track B Dataset v1 generation, schema, and datasheet."""

    def test_load_track_b_dataset_structure(self) -> None:
        df = load_track_b_dataset()

        assert len(df) >= 500, "Dataset v1 should contain at least 500 mined instances"
        assert "project" in df.columns
        assert TARGET_COLUMN in df.columns
        assert set(df[TARGET_COLUMN].unique()).issubset({0, 1})

        # Ensure all 21 features present
        for feat in FEATURE_NAMES:
            assert feat in df.columns
            assert pd.api.types.is_numeric_dtype(df[feat])

        # Verify multi-project representation for project-wise splitting
        projects = df["project"].unique()
        assert len(projects) >= 3, (
            "Dataset v1 must span multiple projects for cross-project evaluation"
        )

    def test_generate_track_b_dataset_custom_path(self, tmp_path: Path) -> None:
        out_csv = tmp_path / "custom_v1.csv"
        df = generate_track_b_dataset(output_path=out_csv, include_current_repo=False)

        assert out_csv.exists()
        assert len(df) > 100
        assert "project" in df.columns

    def test_dataset_v1_datasheet_exists_and_covers_noise(self) -> None:
        sheet_path = Path("docs/eval/dataset_v1_datasheet.md")
        assert sheet_path.exists(), (
            "docs/eval/dataset_v1_datasheet.md must exist per AC"
        )

        content = sheet_path.read_text(encoding="utf-8")
        assert "Datasheet for Dataset v1" in content
        assert "Composition" in content
        assert "Collection & SZZ Labelling Process" in content
        assert "Labelling Noise & Threats to Validity" in content
        assert "Cosmetic Commit Noise" in content
        assert "Keyword Heuristic False Positives" in content
        assert "Project-Wise Splitting" in content
