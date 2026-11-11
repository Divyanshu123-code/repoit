"""Evaluation harness and Stratified Cross-Validation for defect prediction (P3-02)."""

import time
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold

from packages.ml.dataset import FEATURE_NAMES, TARGET_COLUMN
from packages.ml.models import MODEL_METADATA, SUPPORTED_MODELS, build_model_pipeline


@dataclass
class ConfusionMatrixCounts:
    """Confusion matrix elements for binary classification."""

    true_negatives: int
    false_positives: int
    false_negatives: int
    true_positives: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class FoldMetrics:
    """Evaluation metrics for a single cross-validation fold."""

    fold: int
    roc_auc: float
    pr_auc: float
    f1: float
    precision: float
    recall: float
    balanced_accuracy: float
    brier_score: float
    confusion_matrix: ConfusionMatrixCounts


@dataclass
class ModelCVResult:
    """Aggregated cross-validation metrics for one model across all folds."""

    model_type: str
    display_name: str
    family: str
    folds_count: int
    roc_auc_mean: float
    roc_auc_std: float
    pr_auc_mean: float
    pr_auc_std: float
    f1_mean: float
    f1_std: float
    precision_mean: float
    precision_std: float
    recall_mean: float
    recall_std: float
    balanced_accuracy_mean: float
    brier_score_mean: float
    oof_roc_auc: float
    oof_pr_auc: float
    oof_f1: float
    oof_precision: float
    oof_recall: float
    oof_confusion: ConfusionMatrixCounts
    mean_latency_ms: float
    folds: list[FoldMetrics]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkSuiteResult:
    """Comparative benchmark results across all evaluated models on a dataset."""

    dataset_name: str
    total_samples: int
    positive_samples: int
    negative_samples: int
    imbalance_ratio: float
    results: list[ModelCVResult]
    champion_model: str
    champion_reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def format_markdown_table(self) -> str:
        """Format the comparative results into GitHub-flavored Markdown table."""
        lines = [
            f"### Cross-Validation Results: {self.dataset_name.upper()} Dataset",
            f"- **Samples**: `{self.total_samples}` (`{self.negative_samples}` clean, `{self.positive_samples}` defective | **{self.imbalance_ratio:.2f}:1** imbalance)",
            "- **Validation Strategy**: 5-Fold Stratified Cross-Validation (Leakage-free Pipelines)",
            "",
            "| Model | Family | ROC-AUC (mean±std) | PR-AUC (mean±std) | F1 (mean±std) | Recall (mean±std) | Precision (mean±std) | Latency (ms) |",
            "|---|---|---|---|---|---|---|---|",
        ]

        # Sort models by PR-AUC descending (primary ranking under imbalance)
        sorted_results = sorted(self.results, key=lambda r: r.pr_auc_mean, reverse=True)

        for res in sorted_results:
            is_champ = (
                " **(Champion)**" if res.model_type == self.champion_model else ""
            )
            lines.append(
                f"| `{res.display_name}`{is_champ} | {res.family} | "
                f"{res.roc_auc_mean:.3f} ± {res.roc_auc_std:.3f} | "
                f"**{res.pr_auc_mean:.3f} ± {res.pr_auc_std:.3f}** | "
                f"{res.f1_mean:.3f} ± {res.f1_std:.3f} | "
                f"{res.recall_mean:.3f} ± {res.recall_std:.3f} | "
                f"{res.precision_mean:.3f} ± {res.precision_std:.3f} | "
                f"{res.mean_latency_ms:.2f} |"
            )

        lines.extend(
            [
                "",
                "> [!TIP]",
                f"> **Champion Selection: `{self.champion_model}`** — {self.champion_reason}",
            ]
        )

        return "\n".join(lines)


def evaluate_model_cv(
    model_type: str,
    df: pd.DataFrame,
    n_splits: int = 5,
    random_state: int = 42,
) -> ModelCVResult:
    """Evaluate a model using Stratified K-Fold Cross-Validation with strict train-only fitting.

    Args:
        model_type: One of 'dummy', 'logreg', 'decision_tree', 'random_forest', 'xgboost'.
        df: Input dataframe containing features and binary defects target.
        n_splits: Number of cross-validation folds (default 5).
        random_state: Seed for fold shuffling and classifier initialization.

    Returns:
        ModelCVResult containing fold metrics, out-of-fold metrics, and latencies.
    """
    clean_type = model_type.strip().lower()
    features = [c for c in FEATURE_NAMES if c in df.columns]
    x_mat = df[features].to_numpy(dtype=float)
    y_vec = df[TARGET_COLUMN].to_numpy(dtype=int)

    negative_count = int(np.sum(y_vec == 0))
    positive_count = int(np.sum(y_vec == 1))
    scale_pos_weight = (negative_count / positive_count) if positive_count > 0 else 1.0

    meta = MODEL_METADATA.get(
        clean_type,
        {"display_name": clean_type, "family": "Unknown"},
    )

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)

    fold_metrics_list: list[FoldMetrics] = []
    oof_predictions = np.zeros(len(y_vec), dtype=int)
    oof_probabilities = np.zeros(len(y_vec), dtype=float)
    latencies: list[float] = []

    for fold_idx, (train_idx, val_idx) in enumerate(skf.split(x_mat, y_vec), start=1):
        x_train, y_train = x_mat[train_idx], y_vec[train_idx]
        x_val, y_val = x_mat[val_idx], y_vec[val_idx]

        # Pipeline is constructed and fitted strictly on training fold
        pipeline = build_model_pipeline(
            clean_type,
            scale_pos_weight=scale_pos_weight,
            random_state=random_state + fold_idx,
        )
        pipeline.fit(x_train, y_train)

        # Measure inference latency on validation fold
        start_time = time.perf_counter()
        if hasattr(pipeline, "predict_proba"):
            probs = pipeline.predict_proba(x_val)[:, 1]
        else:
            probs = pipeline.predict(x_val).astype(float)
        latency_ms = ((time.perf_counter() - start_time) * 1000.0) / len(x_val)
        latencies.append(latency_ms)

        preds = (probs >= 0.5).astype(int)

        oof_probabilities[val_idx] = probs
        oof_predictions[val_idx] = preds

        # Compute fold-level metrics
        roc = float(roc_auc_score(y_val, probs))
        pr = float(average_precision_score(y_val, probs))
        f1 = float(f1_score(y_val, preds, zero_division=0))
        prec = float(precision_score(y_val, preds, zero_division=0))
        rec = float(recall_score(y_val, preds, zero_division=0))
        bal_acc = float(balanced_accuracy_score(y_val, preds))
        brier = float(brier_score_loss(y_val, probs))

        tn, fp, fn, tp = confusion_matrix(y_val, preds, labels=[0, 1]).ravel()
        cm_counts = ConfusionMatrixCounts(
            true_negatives=int(tn),
            false_positives=int(fp),
            false_negatives=int(fn),
            true_positives=int(tp),
        )

        fold_metrics_list.append(
            FoldMetrics(
                fold=fold_idx,
                roc_auc=roc,
                pr_auc=pr,
                f1=f1,
                precision=prec,
                recall=rec,
                balanced_accuracy=bal_acc,
                brier_score=brier,
                confusion_matrix=cm_counts,
            )
        )

    # Compute overall Out-Of-Fold (OOF) metrics
    oof_roc = float(roc_auc_score(y_vec, oof_probabilities))
    oof_pr = float(average_precision_score(y_vec, oof_probabilities))
    oof_f1 = float(f1_score(y_vec, oof_predictions, zero_division=0))
    oof_prec = float(precision_score(y_vec, oof_predictions, zero_division=0))
    oof_rec = float(recall_score(y_vec, oof_predictions, zero_division=0))

    tn_oof, fp_oof, fn_oof, tp_oof = confusion_matrix(
        y_vec, oof_predictions, labels=[0, 1]
    ).ravel()
    oof_cm = ConfusionMatrixCounts(
        true_negatives=int(tn_oof),
        false_positives=int(fp_oof),
        false_negatives=int(fn_oof),
        true_positives=int(tp_oof),
    )

    return ModelCVResult(
        model_type=clean_type,
        display_name=meta["display_name"],
        family=meta["family"],
        folds_count=n_splits,
        roc_auc_mean=float(np.mean([f.roc_auc for f in fold_metrics_list])),
        roc_auc_std=float(np.std([f.roc_auc for f in fold_metrics_list])),
        pr_auc_mean=float(np.mean([f.pr_auc for f in fold_metrics_list])),
        pr_auc_std=float(np.std([f.pr_auc for f in fold_metrics_list])),
        f1_mean=float(np.mean([f.f1 for f in fold_metrics_list])),
        f1_std=float(np.std([f.f1 for f in fold_metrics_list])),
        precision_mean=float(np.mean([f.precision for f in fold_metrics_list])),
        precision_std=float(np.std([f.precision for f in fold_metrics_list])),
        recall_mean=float(np.mean([f.recall for f in fold_metrics_list])),
        recall_std=float(np.std([f.recall for f in fold_metrics_list])),
        balanced_accuracy_mean=float(
            np.mean([f.balanced_accuracy for f in fold_metrics_list])
        ),
        brier_score_mean=float(np.mean([f.brier_score for f in fold_metrics_list])),
        oof_roc_auc=oof_roc,
        oof_pr_auc=oof_pr,
        oof_f1=oof_f1,
        oof_precision=oof_prec,
        oof_recall=oof_rec,
        oof_confusion=oof_cm,
        mean_latency_ms=float(np.mean(latencies)),
        folds=fold_metrics_list,
    )


def run_benchmark_suite(
    df: pd.DataFrame,
    dataset_name: str,
    models: list[str] | None = None,
    n_splits: int = 5,
    random_state: int = 42,
) -> BenchmarkSuiteResult:
    """Run full comparative cross-validation benchmark across all candidate models.

    Args:
        df: Dataset dataframe.
        dataset_name: Identifier for the dataset ("cm1" or "kc1").
        models: Subset of models to run, defaults to all 5 supported models.
        n_splits: Cross-validation splits (default 5).
        random_state: Seed for reproducibility.

    Returns:
        BenchmarkSuiteResult with comparative tables and champion selection.
    """
    model_list = models if models is not None else SUPPORTED_MODELS
    results: list[ModelCVResult] = []

    for m in model_list:
        cv_result = evaluate_model_cv(
            model_type=m,
            df=df,
            n_splits=n_splits,
            random_state=random_state,
        )
        results.append(cv_result)

    total_samples = len(df)
    positive_samples = int((df[TARGET_COLUMN] == 1).sum())
    negative_samples = int((df[TARGET_COLUMN] == 0).sum())
    imbalance_ratio = (
        (negative_samples / positive_samples) if positive_samples > 0 else 1.0
    )

    # Determine champion model:
    # Under severe class imbalance, PR-AUC and ROC-AUC are the primary discriminators.
    # Exclude dummy baseline from champion consideration.
    non_dummy_results = [r for r in results if r.model_type != "dummy"]
    champion = max(non_dummy_results, key=lambda r: r.pr_auc_mean + r.roc_auc_mean)

    # Construct formal justification
    champ_reason = (
        f"Achieves highest composite ranking with PR-AUC of {champion.pr_auc_mean:.3f} "
        f"and ROC-AUC of {champion.roc_auc_mean:.3f} (Recall: {champion.recall_mean:.3f}, "
        f"Latency: {champion.mean_latency_ms:.2f}ms). It effectively balances sensitivity "
        f"for defect detection against false alarm rates while maintaining sub-millisecond inference."
    )

    return BenchmarkSuiteResult(
        dataset_name=dataset_name,
        total_samples=total_samples,
        positive_samples=positive_samples,
        negative_samples=negative_samples,
        imbalance_ratio=imbalance_ratio,
        results=results,
        champion_model=champion.model_type,
        champion_reason=champ_reason,
    )
