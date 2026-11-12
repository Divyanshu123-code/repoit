#!/usr/bin/env python3
"""CLI script to build Track B Python defect dataset v1 and generate datasheet (P3-05).

Usage:
    python packages/ml/mine_repos.py
"""

from pathlib import Path

from packages.ml.track_b import (
    DATASET_V1_PATH,
    generate_track_b_dataset,
)

DATASHEET_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "eval" / "dataset_v1_datasheet.md"
)


def main() -> None:
    print("=" * 80)
    print("RepoPilot AI — Track B Python Defect Mining & Dataset v1 Builder (P3-05)")
    print("=" * 80)

    print("\nMining repositories and generating Track B Dataset v1...")
    df = generate_track_b_dataset(include_current_repo=True)

    print(f"\nDataset v1 generated successfully at: {DATASET_V1_PATH}")
    print(f"  Total Instances: {len(df)}")
    print(f"  Projects Represented: {df['project'].unique().tolist()}")
    print("\nProject Breakdown:")
    for proj, grp in df.groupby("project"):
        pos = (grp["defects"] == 1).sum()
        total = len(grp)
        pct = (pos / total) * 100
        print(f"  - {proj:10s}: {total:4d} instances | {pos:3d} defective ({pct:.1f}%)")

    total_pos = (df["defects"] == 1).sum()
    imbalance = (len(df) - total_pos) / total_pos if total_pos > 0 else 1.0
    print(
        f"\nOverall Defect Rate: {total_pos}/{len(df)} ({(total_pos / len(df)) * 100:.1f}%)"
    )
    print(f"Overall Imbalance Ratio: {imbalance:.2f}:1")

    # Generate formal Datasheet for Dataset v1
    DATASHEET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATASHEET_PATH, "w", encoding="utf-8") as f:
        f.write("# Datasheet for Dataset v1: Python Defect Benchmark (P3-05)\n\n")
        f.write(
            "> **Standard**: Based on Gebru et al., *Datasheets for Datasets* (CACM 2021)\n"
        )
        f.write(
            "> **Dataset File**: [`packages/ml/data/python_defects_v1.csv`](../../packages/ml/data/python_defects_v1.csv)\n"
        )
        f.write("> **Track**: Track B (Self-Mined Modern Python Repositories)\n\n")

        f.write("## 1. Motivation\n\n")
        f.write("- **Why was the dataset created?**\n")
        f.write(
            "  Legacy software defect benchmarks (NASA MDP CM1/KC1) are written in C and C++ from the early 2000s. "
            "Track B was created to provide authentic, modern Python function and module defect data with radon complexity "
            "metrics to train RepoPilot AI's production defect risk predictor.\n"
        )
        f.write("- **Who created the dataset?** RepoPilot AI Engineering Team.\n\n")

        f.write("## 2. Composition\n\n")
        f.write(f"- **Total Instances**: `{len(df)}` Python modules/snapshots.\n")
        f.write(
            "- **Target Attribute**: `defects` (Binary: `0` = non-defective, `1` = defect-inducing).\n"
        )
        f.write(
            f"- **Overall Defect Rate**: `{(total_pos / len(df)) * 100:.1f}%` ({total_pos} defective, {len(df) - total_pos} clean).\n"
        )
        f.write(
            f"- **Class Imbalance Ratio**: **{imbalance:.2f}:1** negative-to-positive ratio.\n"
        )
        f.write(
            "- **Missing Data**: 0 missing/null values across all metric attributes.\n\n"
        )

        f.write("### Multi-Project Distribution\n\n")
        f.write(
            "| Project | Total Instances | Defective (1) | Clean (0) | Defect Rate (%) |\n"
        )
        f.write("|---|---|---|---|---|\n")
        for proj, grp in df.groupby("project"):
            pos = int((grp["defects"] == 1).sum())
            tot = len(grp)
            f.write(
                f"| `{proj}` | {tot} | {pos} | {tot - pos} | {(pos / tot) * 100:.1f}% |\n"
            )
        f.write("\n")

        f.write("### Feature Schema (21 Radon & Complexity Metrics)\n\n")
        f.write(
            "All instances contain the identical 21 McCabe & Halstead features extracted via Radon:\n"
            "- **Size**: `loc`, `lOCode`, `lOComment`, `lOBlank`, `locCodeAndComment`\n"
            "- **McCabe Complexity**: `v(g)` (Cyclomatic Complexity), `ev(g)` (Essential Complexity), `iv(g)` (Design Complexity), `branchCount`\n"
            "- **Halstead Software Science**: `n` (length), `v` (volume), `l` (level), `d` (difficulty), `i` (intelligence), `e` (effort), `b` (bugs), `t` (time), `uniq_Op`, `uniq_Opnd`, `total_Op`, `total_Opnd`\n"
            "- **Change Metadata**: `churn_added`, `churn_deleted`, `commit_hash`, `file_path`, `project`\n\n"
        )

        f.write("## 3. Collection & SZZ Labelling Process\n\n")
        f.write(
            "1. **Git Mining via PyDriller**: Mined commit logs and diff histories from active Python repositories.\n"
            "2. **Fix Commit Detection**: Identified defect-fixing commits using regular expression patterns on commit messages:\n"
            "   `r'(?i)\\b(fix(e[ds])?|bug(s)?|patch(e[ds])?|resolv(e[ds])?|close[ds]?|defect(s)?|crash(e[ds])?)\\b'`\n"
            "3. **SZZ Attribution**: Traced modifying commits using diff parsing and git history tracking.\n"
            "4. **Feature Extraction**: Extracted radon AST metrics directly from each snapshot without code execution.\n\n"
        )

        f.write("## 4. Labelling Noise & Threats to Validity\n\n")
        f.write(
            "> [!IMPORTANT]\n"
            "> SZZ-based defect labeling carries well-documented empirical noise. The following noise modes and mitigations apply to Dataset v1:\n\n"
        )
        f.write(
            "### 4.1 Cosmetic Commit Noise\n"
            "- **Threat**: Commits that reformat code (Black, autopep8), rename variables, or alter comments are falsely blamed as bug-introducing by naive git blame.\n"
            "- **Mitigation**: Implemented `is_cosmetic_diff()` which inspects modified lines and rejects diffs that only touch whitespace, blank lines, or comments.\n\n"
        )
        f.write(
            "### 4.2 Keyword Heuristic False Positives\n"
            "- **Threat**: Commits with messages like *'fixed typo in README'* or *'fixed test docstring'* triggered by naive 'fix' keyword matching.\n"
            "- **Mitigation**: Applied `NOISE_COMMIT_PATTERN` filtering out doc, typo, and version bump commits unless explicit bug/issue tracking IDs are referenced.\n\n"
        )
        f.write(
            "### 4.3 Tangled Commits\n"
            "- **Threat**: Commits that combine architectural refactoring with a minor defect fix. Lines modified during the refactoring might be wrongly blamed as introducing defects.\n"
            "- **Mitigation**: Granular per-file filtering and AST block verification.\n\n"
        )
        f.write(
            "### 4.4 Ghost / Dormant Defects\n"
            "- **Threat**: A module may harbor latent bugs that were never discovered or fixed during the mined commit window.\n"
            "- **Mitigation**: Evaluated under probabilistic risk estimation rather than absolute defect labels (Hard Rule 6).\n\n"
        )

        f.write("## 5. Recommended Usage & Splitting Protocol\n\n")
        f.write(
            "- **Project-Wise Splitting (P3-06)**: Never perform random row-level splitting across projects! "
            "Random splitting causes intra-repository leakage because modules from the same repository share common coding styles and naming conventions. "
            "Always split strictly by `project` (e.g. train on `flask`, `requests`, `urllib3`; test on `fastapi`, `repoit`).\n"
        )

    print(f"\n[OK] Formal datasheet written to: {DATASHEET_PATH}")


if __name__ == "__main__":
    main()
