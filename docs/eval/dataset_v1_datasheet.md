# Datasheet for Dataset v1: Python Defect Benchmark (P3-05)

> **Standard**: Based on Gebru et al., *Datasheets for Datasets* (CACM 2021)
> **Dataset File**: [`packages/ml/data/python_defects_v1.csv`](../../packages/ml/data/python_defects_v1.csv)
> **Track**: Track B (Self-Mined Modern Python Repositories)

## 1. Motivation

- **Why was the dataset created?**
  Legacy software defect benchmarks (NASA MDP CM1/KC1) are written in C and C++ from the early 2000s. Track B was created to provide authentic, modern Python function and module defect data with radon complexity metrics to train RepoPilot AI's production defect risk predictor.
- **Who created the dataset?** RepoPilot AI Engineering Team.

## 2. Composition

- **Total Instances**: `978` Python modules/snapshots.
- **Target Attribute**: `defects` (Binary: `0` = non-defective, `1` = defect-inducing).
- **Overall Defect Rate**: `11.7%` (114 defective, 864 clean).
- **Class Imbalance Ratio**: **7.58:1** negative-to-positive ratio.
- **Missing Data**: 0 missing/null values across all metric attributes.

### Multi-Project Distribution

| Project | Total Instances | Defective (1) | Clean (0) | Defect Rate (%) |
|---|---|---|---|---|
| `fastapi` | 210 | 22 | 188 | 10.5% |
| `flask` | 220 | 27 | 193 | 12.3% |
| `repoit` | 108 | 23 | 85 | 21.3% |
| `requests` | 200 | 17 | 183 | 8.5% |
| `urllib3` | 240 | 25 | 215 | 10.4% |

### Feature Schema (21 Radon & Complexity Metrics)

All instances contain the identical 21 McCabe & Halstead features extracted via Radon:
- **Size**: `loc`, `lOCode`, `lOComment`, `lOBlank`, `locCodeAndComment`
- **McCabe Complexity**: `v(g)` (Cyclomatic Complexity), `ev(g)` (Essential Complexity), `iv(g)` (Design Complexity), `branchCount`
- **Halstead Software Science**: `n` (length), `v` (volume), `l` (level), `d` (difficulty), `i` (intelligence), `e` (effort), `b` (bugs), `t` (time), `uniq_Op`, `uniq_Opnd`, `total_Op`, `total_Opnd`
- **Change Metadata**: `churn_added`, `churn_deleted`, `commit_hash`, `file_path`, `project`

## 3. Collection & SZZ Labelling Process

1. **Git Mining via PyDriller**: Mined commit logs and diff histories from active Python repositories.
2. **Fix Commit Detection**: Identified defect-fixing commits using regular expression patterns on commit messages:
   `r'(?i)\b(fix(e[ds])?|bug(s)?|patch(e[ds])?|resolv(e[ds])?|close[ds]?|defect(s)?|crash(e[ds])?)\b'`
3. **SZZ Attribution**: Traced modifying commits using diff parsing and git history tracking.
4. **Feature Extraction**: Extracted radon AST metrics directly from each snapshot without code execution.

## 4. Labelling Noise & Threats to Validity

> [!IMPORTANT]
> SZZ-based defect labeling carries well-documented empirical noise. The following noise modes and mitigations apply to Dataset v1:

### 4.1 Cosmetic Commit Noise
- **Threat**: Commits that reformat code (Black, autopep8), rename variables, or alter comments are falsely blamed as bug-introducing by naive git blame.
- **Mitigation**: Implemented `is_cosmetic_diff()` which inspects modified lines and rejects diffs that only touch whitespace, blank lines, or comments.

### 4.2 Keyword Heuristic False Positives
- **Threat**: Commits with messages like *'fixed typo in README'* or *'fixed test docstring'* triggered by naive 'fix' keyword matching.
- **Mitigation**: Applied `NOISE_COMMIT_PATTERN` filtering out doc, typo, and version bump commits unless explicit bug/issue tracking IDs are referenced.

### 4.3 Tangled Commits
- **Threat**: Commits that combine architectural refactoring with a minor defect fix. Lines modified during the refactoring might be wrongly blamed as introducing defects.
- **Mitigation**: Granular per-file filtering and AST block verification.

### 4.4 Ghost / Dormant Defects
- **Threat**: A module may harbor latent bugs that were never discovered or fixed during the mined commit window.
- **Mitigation**: Evaluated under probabilistic risk estimation rather than absolute defect labels (Hard Rule 6).

## 5. Recommended Usage & Splitting Protocol

- **Project-Wise Splitting (P3-06)**: Never perform random row-level splitting across projects! Random splitting causes intra-repository leakage because modules from the same repository share common coding styles and naming conventions. Always split strictly by `project` (e.g. train on `flask`, `requests`, `urllib3`; test on `fastapi`, `repoit`).
