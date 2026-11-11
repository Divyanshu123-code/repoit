"""Dataset inspection and exploratory quality analysis for defect prediction (P3-01)."""

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from packages.ml.dataset import (
    DATASET_METADATA,
    FEATURE_DESCRIPTIONS,
    FEATURE_NAMES,
    TARGET_COLUMN,
)


@dataclass
class DatasetInspectionReport:
    """Structured inspection summary for a defect dataset."""

    name: str
    title: str
    provenance: str
    license: str
    rows: int
    columns: int
    feature_count: int
    target_column: str
    positive_count: int
    negative_count: int
    positive_percentage: float
    imbalance_ratio: float
    exact_duplicates_count: int
    exact_duplicates_pct: float
    feature_duplicates_count: int
    contradictory_instances_count: int
    missing_values_total: int
    feature_summaries: dict[str, dict[str, float]]

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary."""
        return asdict(self)

    def format_markdown(self) -> str:
        """Format the report into GitHub-flavored Markdown."""
        lines = [
            f"# Dataset Inspection: {self.title}",
            "",
            "## 1. Provenance & License",
            f"- **Dataset**: `{self.name.upper()}`",
            f"- **Title**: {self.title}",
            f"- **Source**: {self.provenance}",
            f"- **License**: {self.license}",
            "",
            "## 2. Dimensions & Schema",
            f"- **Total Rows (Modules)**: `{self.rows}`",
            f"- **Total Columns**: `{self.columns}` (`{self.feature_count}` static metric features + 1 target)",
            f"- **Target Column**: `{self.target_column}`",
            f"- **Missing / Null Values**: `{self.missing_values_total}`",
            "",
            "## 3. Label Distribution & Class Imbalance",
            "| Class | Count | Percentage | Description |",
            "|---|---|---|---|",
            f"| Non-defective (0) | {self.negative_count} | {100.0 - self.positive_percentage:.2f}% | Clean / no defect reported |",
            f"| Defective (1) | {self.positive_count} | {self.positive_percentage:.2f}% | Defect / post-release bug detected |",
            "",
            "> [!WARNING]",
            f"> Severe class imbalance detected: **{self.imbalance_ratio:.2f}:1** negative-to-positive ratio.",
            "> Models evaluated on raw accuracy will produce deceptively high scores by predicting the majority class.",
            "> Training must use stratified splits, and primary evaluation metrics must be **ROC-AUC** and **PR-AUC**.",
            "",
            "## 4. Duplicate & Data Quality Analysis",
            "| Metric | Value | Proportion | Implications |",
            "|---|---|---|---|",
            f"| Exact Duplicates (identical features + label) | `{self.exact_duplicates_count}` | {self.exact_duplicates_pct:.2f}% | Artificial weight on identical modules; risk of train-test leakage |",
            f"| Feature Duplicates (identical features) | `{self.feature_duplicates_count}` | {(self.feature_duplicates_count / self.rows) * 100:.2f}% | Multiple identical method signatures/bodies in project |",
            f"| Contradictory Duplicates (identical features, opposite labels) | `{self.contradictory_instances_count}` | {(self.contradictory_instances_count / self.rows) * 100:.2f}% | Inconsistent ground-truth labelling noise |",
            "",
            "## 5. Feature Dictionary & Summary Statistics",
            "| Feature | Description | Min | Median | Mean | Std | Max |",
            "|---|---|---|---|---|---|---|",
        ]

        for feat in FEATURE_NAMES:
            stats = self.feature_summaries.get(feat, {})
            desc = FEATURE_DESCRIPTIONS.get(feat, feat)
            lines.append(
                f"| `{feat}` | {desc} | {stats.get('min', 0):.2f} | {stats.get('median', 0):.2f} | {stats.get('mean', 0):.2f} | {stats.get('std', 0):.2f} | {stats.get('max', 0):.2f} |"
            )

        lines.extend(
            [
                "",
                "## 6. Recommendations for P3-02 Training Pipeline",
                "1. **Stratified Splitting**: Use `StratifiedKFold` (5 folds) to preserve defect class proportion across validation splits.",
                "2. **Metric Priority**: Optimize for PR-AUC and ROC-AUC rather than raw classification accuracy.",
                "3. **Feature Scaling**: RobustScaler or StandardScaler inside pipeline to handle high-skew Halstead volume/effort metrics.",
                "4. **Class Weighting / Resampling**: Apply balanced class weights or SMOTE/oversampling to counter the imbalance.",
                "5. **Deduplication Strategy**: Document impact of exact duplicates on cross-validation variance.",
            ]
        )

        return "\n".join(lines)


def inspect_dataset(df: pd.DataFrame, name: str) -> DatasetInspectionReport:
    """Perform thorough inspection of a defect dataset dataframe.

    Args:
        df: Input dataframe containing features and defects target.
        name: Short name of the dataset ("cm1" or "kc1").

    Returns:
        DatasetInspectionReport instance with all computed statistics.
    """
    clean_name = name.strip().lower()
    meta = DATASET_METADATA.get(
        clean_name,
        {
            "title": f"Dataset {name.upper()}",
            "source": "PROMISE Repository",
            "license": "Public Domain",
        },
    )

    rows, cols = df.shape
    features = [c for c in FEATURE_NAMES if c in df.columns]

    target_series = df[TARGET_COLUMN]
    positive_count = int((target_series == 1).sum())
    negative_count = int((target_series == 0).sum())
    pos_pct = (positive_count / rows) * 100.0 if rows > 0 else 0.0
    imbalance_ratio = (negative_count / positive_count) if positive_count > 0 else 0.0

    # Duplicate analysis
    exact_dups = int(df.duplicated().sum())
    exact_dup_pct = (exact_dups / rows) * 100.0 if rows > 0 else 0.0
    feature_dups = int(df.duplicated(subset=features).sum())

    # Contradictory instances: identical features, different label
    grouped = df.groupby(features)[TARGET_COLUMN].nunique()
    contradictory_groups = grouped[grouped > 1]
    contradictory_count = int(
        df[df.set_index(features).index.isin(contradictory_groups.index)].shape[0]
    )

    # Missing values
    missing_total = int(df.isnull().sum().sum())

    # Summary statistics for features
    summaries: dict[str, dict[str, float]] = {}
    for feat in features:
        series = df[feat]
        summaries[feat] = {
            "min": float(series.min()),
            "median": float(series.median()),
            "mean": float(series.mean()),
            "std": float(series.std()),
            "max": float(series.max()),
        }

    return DatasetInspectionReport(
        name=clean_name,
        title=meta["title"],
        provenance=meta["source"],
        license=meta["license"],
        rows=rows,
        columns=cols,
        feature_count=len(features),
        target_column=TARGET_COLUMN,
        positive_count=positive_count,
        negative_count=negative_count,
        positive_percentage=pos_pct,
        imbalance_ratio=imbalance_ratio,
        exact_duplicates_count=exact_dups,
        exact_duplicates_pct=exact_dup_pct,
        feature_duplicates_count=feature_dups,
        contradictory_instances_count=contradictory_count,
        missing_values_total=missing_total,
        feature_summaries=summaries,
    )


def find_contradictory_instances(df: pd.DataFrame) -> pd.DataFrame:
    """Return all rows that share identical features but have conflicting defect labels."""
    features = [c for c in FEATURE_NAMES if c in df.columns]
    grouped = df.groupby(features)[TARGET_COLUMN].nunique()
    contradictory_idx = grouped[grouped > 1].index
    return df[df.set_index(features).index.isin(contradictory_idx)].sort_values(
        by=features
    )
