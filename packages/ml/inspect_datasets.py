#!/usr/bin/env python3
"""CLI script to inspect CM1 and KC1 defect datasets and generate report (P3-01).

Usage:
    python packages/ml/inspect_datasets.py
"""

from pathlib import Path

from packages.ml.dataset import load_cm1, load_kc1
from packages.ml.inspector import find_contradictory_instances, inspect_dataset

REPORT_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "eval" / "dataset_inspection.md"
)


def main() -> None:
    print("=" * 80)
    print("RepoPilot AI — Defect Dataset Inspection (CM1 & KC1)")
    print("=" * 80)

    cm1 = load_cm1()
    kc1 = load_kc1()

    cm1_report = inspect_dataset(cm1, "cm1")
    kc1_report = inspect_dataset(kc1, "kc1")

    print("\n[CM1 Dataset]")
    print(f"  Shape: {cm1_report.rows} rows x {cm1_report.columns} cols")
    print(
        f"  Target: {cm1_report.negative_count} clean ({100 - cm1_report.positive_percentage:.2f}%), {cm1_report.positive_count} defective ({cm1_report.positive_percentage:.2f}%)"
    )
    print(f"  Imbalance Ratio: {cm1_report.imbalance_ratio:.2f}:1")
    print(
        f"  Duplicates: {cm1_report.exact_duplicates_count} exact ({cm1_report.exact_duplicates_pct:.2f}%), {cm1_report.contradictory_instances_count} contradictory"
    )
    print(f"  Missing Values: {cm1_report.missing_values_total}")

    print("\n[KC1 Dataset]")
    print(f"  Shape: {kc1_report.rows} rows x {kc1_report.columns} cols")
    print(
        f"  Target: {kc1_report.negative_count} clean ({100 - kc1_report.positive_percentage:.2f}%), {kc1_report.positive_count} defective ({kc1_report.positive_percentage:.2f}%)"
    )
    print(f"  Imbalance Ratio: {kc1_report.imbalance_ratio:.2f}:1")
    print(
        f"  Duplicates: {kc1_report.exact_duplicates_count} exact ({kc1_report.exact_duplicates_pct:.2f}%), {kc1_report.contradictory_instances_count} contradictory"
    )
    print(f"  Missing Values: {kc1_report.missing_values_total}")

    cm1_contra = find_contradictory_instances(cm1)
    kc1_contra = find_contradictory_instances(kc1)
    print("\nContradictory Instances Found:")
    print(f"  CM1: {len(cm1_contra)} rows")
    print(f"  KC1: {len(kc1_contra)} rows")

    # Generate comprehensive markdown document
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Empirical Dataset Inspection Report: NASA PROMISE CM1 & KC1\n\n")
        f.write(
            "> **Evaluation Track**: Track A (NASA MDP Baseline Defect Prediction)\n"
        )
        f.write(
            "> **Source**: NASA Metrics Data Program (MDP) / PROMISE Software Engineering Repository\n"
        )
        f.write(
            "> **License**: Public Domain (Open Science Research / CC0-compatible)\n\n"
        )

        f.write("## Executive Summary\n\n")
        f.write(
            "This report documents the empirical exploration of the NASA PROMISE **CM1** and **KC1** software defect datasets, "
            "evaluating schema structure, class imbalance, duplication rates, and label consistency. "
            "These findings establish the foundational constraints for the ML training pipeline in `P3-02`.\n\n"
        )

        f.write("### Comparative Overview\n\n")
        f.write(
            "| Metric | CM1 (Spacecraft Instrument) | KC1 (Ground Receiving System) |\n"
        )
        f.write("|---|---|---|\n")
        f.write("| Language | C | C++ |\n")
        f.write(
            f"| Total Modules (Rows) | `{cm1_report.rows}` | `{kc1_report.rows}` |\n"
        )
        f.write(
            f"| Static Metric Features | `{cm1_report.feature_count}` | `{kc1_report.feature_count}` |\n"
        )
        f.write(
            f"| Non-defective (0) | `{cm1_report.negative_count}` ({100 - cm1_report.positive_percentage:.2f}%) | `{kc1_report.negative_count}` ({100 - kc1_report.positive_percentage:.2f}%) |\n"
        )
        f.write(
            f"| Defective (1) | `{cm1_report.positive_count}` ({cm1_report.positive_percentage:.2f}%) | `{kc1_report.positive_count}` ({kc1_report.positive_percentage:.2f}%) |\n"
        )
        f.write(
            f"| Imbalance Ratio | **{cm1_report.imbalance_ratio:.2f}:1** | **{kc1_report.imbalance_ratio:.2f}:1** |\n"
        )
        f.write(
            f"| Exact Duplicates | `{cm1_report.exact_duplicates_count}` ({cm1_report.exact_duplicates_pct:.2f}%) | `{kc1_report.exact_duplicates_count}` ({kc1_report.exact_duplicates_pct:.2f}%) |\n"
        )
        f.write(
            f"| Contradictory Duplicates | `{cm1_report.contradictory_instances_count}` | `{kc1_report.contradictory_instances_count}` |\n"
        )
        f.write(
            f"| Missing / NaN Values | `{cm1_report.missing_values_total}` | `{kc1_report.missing_values_total}` |\n\n"
        )

        f.write(cm1_report.format_markdown())
        f.write("\n\n---\n\n")
        f.write(kc1_report.format_markdown())

    print(f"\nComprehensive report written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
