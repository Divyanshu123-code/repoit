# Empirical Dataset Inspection Report: NASA PROMISE CM1 & KC1

> **Evaluation Track**: Track A (NASA MDP Baseline Defect Prediction)
> **Source**: NASA Metrics Data Program (MDP) / PROMISE Software Engineering Repository
> **License**: Public Domain (Open Science Research / CC0-compatible)

## Executive Summary

This report documents the empirical exploration of the NASA PROMISE **CM1** and **KC1** software defect datasets, evaluating schema structure, class imbalance, duplication rates, and label consistency. These findings establish the foundational constraints for the ML training pipeline in `P3-02`.

### Comparative Overview

| Metric | CM1 (Spacecraft Instrument) | KC1 (Ground Receiving System) |
|---|---|---|
| Language | C | C++ |
| Total Modules (Rows) | `498` | `2109` |
| Static Metric Features | `21` | `21` |
| Non-defective (0) | `449` (90.16%) | `1783` (84.54%) |
| Defective (1) | `49` (9.84%) | `326` (15.46%) |
| Imbalance Ratio | **9.16:1** | **5.47:1** |
| Exact Duplicates | `56` (11.24%) | `897` (42.53%) |
| Contradictory Duplicates | `2` | `253` |
| Missing / NaN Values | `0` | `0` |

# Dataset Inspection: NASA Metrics Data Program CM1 (Spacecraft Instrument)

## 1. Provenance & License
- **Dataset**: `CM1`
- **Title**: NASA Metrics Data Program CM1 (Spacecraft Instrument)
- **Source**: NASA MDP / PROMISE Software Engineering Repository
- **License**: Public Domain (NASA Metrics Data Program / PROMISE Repository)

## 2. Dimensions & Schema
- **Total Rows (Modules)**: `498`
- **Total Columns**: `22` (`21` static metric features + 1 target)
- **Target Column**: `defects`
- **Missing / Null Values**: `0`

## 3. Label Distribution & Class Imbalance
| Class | Count | Percentage | Description |
|---|---|---|---|
| Non-defective (0) | 449 | 90.16% | Clean / no defect reported |
| Defective (1) | 49 | 9.84% | Defect / post-release bug detected |

> [!WARNING]
> Severe class imbalance detected: **9.16:1** negative-to-positive ratio.
> Models evaluated on raw accuracy will produce deceptively high scores by predicting the majority class.
> Training must use stratified splits, and primary evaluation metrics must be **ROC-AUC** and **PR-AUC**.

## 4. Duplicate & Data Quality Analysis
| Metric | Value | Proportion | Implications |
|---|---|---|---|
| Exact Duplicates (identical features + label) | `56` | 11.24% | Artificial weight on identical modules; risk of train-test leakage |
| Feature Duplicates (identical features) | `57` | 11.45% | Multiple identical method signatures/bodies in project |
| Contradictory Duplicates (identical features, opposite labels) | `2` | 0.40% | Inconsistent ground-truth labelling noise |

## 5. Feature Dictionary & Summary Statistics
| Feature | Description | Min | Median | Mean | Std | Max |
|---|---|---|---|---|---|---|
| `loc` | McCabe's line count of code | 1.00 | 17.00 | 29.64 | 42.75 | 423.00 |
| `v(g)` | McCabe's cyclomatic complexity | 1.00 | 3.00 | 5.38 | 8.35 | 96.00 |
| `ev(g)` | McCabe's essential complexity | 1.00 | 1.00 | 2.49 | 3.66 | 30.00 |
| `iv(g)` | McCabe's design complexity | 1.00 | 2.00 | 3.53 | 5.46 | 63.00 |
| `n` | Halstead total operators and operands (length N) | 1.00 | 67.50 | 143.96 | 221.05 | 2075.00 |
| `v` | Halstead program volume V | 0.00 | 329.82 | 900.18 | 1690.81 | 17124.28 |
| `l` | Halstead program length level L | 0.00 | 0.09 | 0.15 | 0.16 | 1.30 |
| `d` | Halstead difficulty level D | 0.00 | 11.64 | 15.83 | 15.33 | 125.77 |
| `i` | Halstead intelligence content I | 0.00 | 27.40 | 38.46 | 37.00 | 293.68 |
| `e` | Halstead effort E | 0.00 | 3677.62 | 34884.93 | 134164.67 | 2153690.63 |
| `b` | Halstead delivered bugs estimator B | 0.00 | 0.11 | 0.30 | 0.57 | 5.71 |
| `t` | Halstead time to implement T (seconds) | 0.00 | 204.31 | 1938.06 | 7453.59 | 119649.48 |
| `lOCode` | Lines of executable code | 0.00 | 1.00 | 3.79 | 8.51 | 80.00 |
| `lOComment` | Lines of comments | 0.00 | 4.00 | 12.28 | 25.83 | 339.00 |
| `lOBlank` | Lines of blank space | 0.00 | 5.00 | 11.53 | 19.98 | 164.00 |
| `locCodeAndComment` | Lines containing both code and comments | 0.00 | 0.00 | 0.01 | 0.10 | 2.00 |
| `uniq_Op` | Unique operators (mu1) | 1.00 | 14.00 | 15.20 | 9.62 | 72.00 |
| `uniq_Opnd` | Unique operands (mu2) | 0.00 | 15.00 | 25.45 | 33.93 | 314.00 |
| `total_Op` | Total operators (N1) | 1.00 | 42.00 | 88.39 | 134.92 | 1261.00 |
| `total_Opnd` | Total operands (N2) | 0.00 | 26.00 | 55.57 | 86.97 | 814.00 |
| `branchCount` | Branch count of the control flow graph | 1.00 | 5.00 | 9.35 | 15.07 | 162.00 |

## 6. Recommendations for P3-02 Training Pipeline
1. **Stratified Splitting**: Use `StratifiedKFold` (5 folds) to preserve defect class proportion across validation splits.
2. **Metric Priority**: Optimize for PR-AUC and ROC-AUC rather than raw classification accuracy.
3. **Feature Scaling**: RobustScaler or StandardScaler inside pipeline to handle high-skew Halstead volume/effort metrics.
4. **Class Weighting / Resampling**: Apply balanced class weights or SMOTE/oversampling to counter the imbalance.
5. **Deduplication Strategy**: Document impact of exact duplicates on cross-validation variance.

---

# Dataset Inspection: NASA Metrics Data Program KC1 (Satellite Ground Receiving System)

## 1. Provenance & License
- **Dataset**: `KC1`
- **Title**: NASA Metrics Data Program KC1 (Satellite Ground Receiving System)
- **Source**: NASA MDP / PROMISE Software Engineering Repository
- **License**: Public Domain (NASA Metrics Data Program / PROMISE Repository)

## 2. Dimensions & Schema
- **Total Rows (Modules)**: `2109`
- **Total Columns**: `22` (`21` static metric features + 1 target)
- **Target Column**: `defects`
- **Missing / Null Values**: `0`

## 3. Label Distribution & Class Imbalance
| Class | Count | Percentage | Description |
|---|---|---|---|
| Non-defective (0) | 1783 | 84.54% | Clean / no defect reported |
| Defective (1) | 326 | 15.46% | Defect / post-release bug detected |

> [!WARNING]
> Severe class imbalance detected: **5.47:1** negative-to-positive ratio.
> Models evaluated on raw accuracy will produce deceptively high scores by predicting the majority class.
> Training must use stratified splits, and primary evaluation metrics must be **ROC-AUC** and **PR-AUC**.

## 4. Duplicate & Data Quality Analysis
| Metric | Value | Proportion | Implications |
|---|---|---|---|
| Exact Duplicates (identical features + label) | `897` | 42.53% | Artificial weight on identical modules; risk of train-test leakage |
| Feature Duplicates (identical features) | `917` | 43.48% | Multiple identical method signatures/bodies in project |
| Contradictory Duplicates (identical features, opposite labels) | `253` | 12.00% | Inconsistent ground-truth labelling noise |

## 5. Feature Dictionary & Summary Statistics
| Feature | Description | Min | Median | Mean | Std | Max |
|---|---|---|---|---|---|---|
| `loc` | McCabe's line count of code | 1.00 | 9.00 | 20.37 | 29.75 | 288.00 |
| `v(g)` | McCabe's cyclomatic complexity | 1.00 | 1.00 | 2.84 | 3.90 | 45.00 |
| `ev(g)` | McCabe's essential complexity | 1.00 | 1.00 | 1.67 | 2.20 | 26.00 |
| `iv(g)` | McCabe's design complexity | 1.00 | 1.00 | 2.55 | 3.38 | 45.00 |
| `n` | Halstead total operators and operands (length N) | 0.00 | 16.00 | 49.83 | 83.60 | 1106.00 |
| `v` | Halstead program volume V | 0.00 | 57.06 | 258.70 | 516.32 | 7918.82 |
| `l` | Halstead program length level L | 0.00 | 0.20 | 0.32 | 0.32 | 2.00 |
| `d` | Halstead difficulty level D | 0.00 | 3.50 | 6.77 | 7.86 | 53.75 |
| `i` | Halstead intelligence content I | 0.00 | 14.40 | 21.24 | 21.50 | 193.06 |
| `e` | Halstead effort E | 0.00 | 213.97 | 5242.39 | 17444.98 | 324803.51 |
| `b` | Halstead delivered bugs estimator B | 0.00 | 0.02 | 0.09 | 0.18 | 2.64 |
| `t` | Halstead time to implement T (seconds) | 0.00 | 11.89 | 291.25 | 969.17 | 18044.64 |
| `lOCode` | Lines of executable code | 0.00 | 5.00 | 14.53 | 24.19 | 262.00 |
| `lOComment` | Lines of comments | 0.00 | 0.00 | 0.95 | 3.09 | 44.00 |
| `lOBlank` | Lines of blank space | 0.00 | 0.00 | 1.76 | 3.86 | 58.00 |
| `locCodeAndComment` | Lines containing both code and comments | 0.00 | 0.00 | 0.13 | 0.70 | 12.00 |
| `uniq_Op` | Unique operators (mu1) | 0.00 | 6.00 | 7.63 | 5.73 | 37.00 |
| `uniq_Opnd` | Unique operands (mu2) | 0.00 | 5.00 | 9.54 | 12.20 | 120.00 |
| `total_Op` | Total operators (N1) | 0.00 | 10.00 | 31.04 | 51.78 | 678.00 |
| `total_Opnd` | Total operands (N2) | 0.00 | 6.00 | 18.79 | 32.07 | 428.00 |
| `branchCount` | Branch count of the control flow graph | 1.00 | 1.00 | 4.67 | 7.79 | 89.00 |

## 6. Recommendations for P3-02 Training Pipeline
1. **Stratified Splitting**: Use `StratifiedKFold` (5 folds) to preserve defect class proportion across validation splits.
2. **Metric Priority**: Optimize for PR-AUC and ROC-AUC rather than raw classification accuracy.
3. **Feature Scaling**: RobustScaler or StandardScaler inside pipeline to handle high-skew Halstead volume/effort metrics.
4. **Class Weighting / Resampling**: Apply balanced class weights or SMOTE/oversampling to counter the imbalance.
5. **Deduplication Strategy**: Document impact of exact duplicates on cross-validation variance.