"""ML Defect Risk Inference Service (P3-07).

Loads the trained champion model pipeline and model_card.json to evaluate defect
probabilities across Python codebases, strictly adhering to:
- Hard Rule 5: Every result labelled by source: 'ml_predicted'.
- Hard Rule 6: ML predictions are risk estimates, never 'confirmed bugs', with model version.
"""

import json
import logging
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

# Ensure workspace root is in sys.path when running from apps/api
_workspace_root = str(Path(__file__).resolve().parents[4])
if _workspace_root not in sys.path:
    sys.path.insert(0, _workspace_root)

import joblib
import numpy as np
import sqlalchemy as sa
from packages.ml.dataset import FEATURE_DESCRIPTIONS, FEATURE_NAMES
from packages.ml.szz import extract_radon_features
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.models import MLPrediction
from app.ml.schemas import DefectRiskResponse, DefectRiskSummary, MLPredictionItem

logger = logging.getLogger("repopilot.ml.inference")

RULE_6_DISCLAIMER = "Predictions are risk estimates, never confirmed bugs."


def resolve_artifacts_dir() -> Path:
    """Resolve the directory holding champion_model.joblib and model_card.json."""
    env_dir = os.getenv("ML_ARTIFACTS_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)

    # Relative to this file: apps/api/app/ml/inference_service.py -> packages/ml/artifacts
    workspace_root = Path(__file__).resolve().parents[4]
    candidate = workspace_root / "packages" / "ml" / "artifacts"
    if candidate.exists():
        return candidate

    # Fallback to local package directory
    return Path(__file__).resolve().parents[2] / "packages" / "ml" / "artifacts"


class DefectInferenceService:
    """Production inference engine for ML defect risk prediction."""

    def __init__(self, artifacts_dir: Path | str | None = None) -> None:
        self.artifacts_dir = (
            Path(artifacts_dir) if artifacts_dir is not None else resolve_artifacts_dir()
        )
        self._pipeline: Any = None
        self._model_card: dict[str, Any] = {}
        self._model_version: str = "2.0.0"
        self._shap_weights: dict[str, float] = {}
        self._load_artifacts()

    def _load_artifacts(self) -> None:
        """Load serialized scikit-learn pipeline and model card."""
        model_path = self.artifacts_dir / "champion_model.joblib"
        card_path = self.artifacts_dir / "model_card.json"

        if card_path.exists():
            try:
                with open(card_path, encoding="utf-8") as f:
                    self._model_card = json.load(f)
                    self._model_version = self._model_card.get("model_version", "2.0.0")
                    # Cache mean absolute SHAP weights if available
                    for item in self._model_card.get("top_contributing_features", []):
                        feat_name = item.get("feature")
                        shap_val = item.get("mean_abs_shap")
                        if feat_name and shap_val:
                            self._shap_weights[feat_name] = float(shap_val)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to load model_card.json: %s", e)

        if model_path.exists():
            try:
                self._pipeline = joblib.load(model_path)
                logger.info(
                    "Loaded champion ML model (version=%s) from %s",
                    self._model_version,
                    model_path,
                )
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to load champion_model.joblib: %s", e)
                self._pipeline = None
        else:
            logger.warning("champion_model.joblib not found at %s", model_path)
            self._pipeline = None

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def is_model_loaded(self) -> bool:
        return self._pipeline is not None

    def predict_features(
        self,
        features: dict[str, float],
        threshold_medium: float = 0.35,
        threshold_high: float = 0.65,
    ) -> dict[str, Any]:
        """Compute defect risk probability, band, and top drivers for a feature dictionary."""
        vector = np.array([[float(features.get(k, 0.0)) for k in FEATURE_NAMES]])

        if self._pipeline is not None and hasattr(self._pipeline, "predict_proba"):
            try:
                prob = float(self._pipeline.predict_proba(vector)[0, 1])
            except Exception as e:  # noqa: BLE001
                logger.warning("Inference execution failed, using fallback heuristic: %s", e)
                prob = self._heuristic_fallback(features)
        else:
            prob = self._heuristic_fallback(features)

        # Classify risk band
        band: Literal["low", "medium", "high"]
        if prob >= threshold_high:
            band = "high"
        elif prob >= threshold_medium:
            band = "medium"
        else:
            band = "low"

        # Calculate top SHAP-weighted contributing features
        top_drivers: list[dict[str, Any]] = []
        for name in FEATURE_NAMES:
            val = float(features.get(name, 0.0))
            if val > 0:
                shap_weight = self._shap_weights.get(name, 1.0)
                score = val * shap_weight
                top_drivers.append(
                    {
                        "feature": name,
                        "value": round(val, 2),
                        "importance_score": round(score, 4),
                        "description": FEATURE_DESCRIPTIONS.get(name, name),
                    }
                )

        top_drivers.sort(key=lambda d: d["importance_score"], reverse=True)
        top_features_clean = [
            {
                "feature": d["feature"],
                "value": d["value"],
                "description": d["description"],
            }
            for d in top_drivers[:5]
        ]

        return {
            "risk_probability": round(prob, 4),
            "risk_band": band,
            "model_version": self._model_version,
            "top_features": top_features_clean,
            "source": "ml_predicted",  # Hard Rule 5
            "disclaimer": RULE_6_DISCLAIMER,  # Hard Rule 6
        }

    def _heuristic_fallback(self, features: dict[str, float]) -> float:
        """Deterministic fallback when serialized pipeline is not yet loaded."""
        loc = features.get("loc", 0.0)
        cc = features.get("v(g)", 1.0)
        hal_v = features.get("v", 0.0)

        # Baseline log-odds approximation
        score = (cc * 0.05) + (loc * 0.002) + (hal_v * 0.0001)
        prob = 1.0 / (1.0 + np.exp(-score + 2.0))
        return float(np.clip(prob, 0.02, 0.95))

    def predict_source_code(self, source_code: str) -> dict[str, Any]:
        """Extract radon features and predict defect risk for Python source code."""
        features = extract_radon_features(source_code)
        return self.predict_features(features)

    async def predict_and_store_for_modules(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        modules_code: dict[str, str],
        scan_id: uuid.UUID | None = None,
    ) -> list[MLPrediction]:
        """Compute defect predictions for multiple modules and persist to ml_predictions table."""
        # Clean existing predictions for this repository if recomputing
        await session.execute(
            delete(MLPrediction).where(MLPrediction.repository_id == repository_id)
        )

        records: list[MLPrediction] = []
        for file_path, code in modules_code.items():
            pred = self.predict_source_code(code)
            record = MLPrediction(
                repository_id=repository_id,
                scan_id=scan_id,
                file_path=file_path,
                function_name=None,
                line_start=1,
                line_end=len(code.splitlines()) if code else 1,
                risk_probability=pred["risk_probability"],
                risk_band=pred["risk_band"],
                model_version=pred["model_version"],
                top_features=pred["top_features"],
                source="ml_predicted",  # Hard Rule 5
                created_at=datetime.now(UTC),
            )
            session.add(record)
            records.append(record)

        await session.commit()
        for r in records:
            await session.refresh(r)

        logger.info(
            "Persisted %d ML defect predictions for repo %s (scan_id=%s)",
            len(records),
            repository_id,
            scan_id,
        )
        return records

    async def get_repository_defect_risk(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        risk_band: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> DefectRiskResponse:
        """Retrieve stored ML defect risk predictions and summary metrics for a repository."""
        # Query total, risk band breakdowns and average probability
        stats_query = select(
            func.count(MLPrediction.id).label("total"),
            func.sum(sa.case((MLPrediction.risk_band == "high", 1), else_=0)).label("high"),
            func.sum(sa.case((MLPrediction.risk_band == "medium", 1), else_=0)).label("medium"),
            func.sum(sa.case((MLPrediction.risk_band == "low", 1), else_=0)).label("low"),
            func.avg(MLPrediction.risk_probability).label("avg_prob"),
        ).where(MLPrediction.repository_id == repository_id)

        stats_res = await session.execute(stats_query)
        row = stats_res.first()

        total = int(row.total or 0) if row else 0
        high = int(row.high or 0) if row else 0
        medium = int(row.medium or 0) if row else 0
        low = int(row.low or 0) if row else 0
        avg_prob = float(row.avg_prob or 0.0) if row else 0.0

        summary = DefectRiskSummary(
            total_modules=total,
            high_risk_count=high,
            medium_risk_count=medium,
            low_risk_count=low,
            average_risk_probability=round(avg_prob, 4),
        )

        # Retrieve filtered predictions
        stmt = select(MLPrediction).where(MLPrediction.repository_id == repository_id)
        if risk_band in ["low", "medium", "high"]:
            stmt = stmt.where(MLPrediction.risk_band == risk_band)

        stmt = stmt.order_by(desc(MLPrediction.risk_probability)).offset(offset).limit(limit)
        items_res = await session.execute(stmt)
        records = items_res.scalars().all()

        prediction_items = [
            MLPredictionItem(
                id=str(r.id),
                file_path=r.file_path,
                function_name=r.function_name,
                line_start=r.line_start,
                line_end=r.line_end,
                risk_probability=round(r.risk_probability, 4),
                risk_band=cast(Literal["low", "medium", "high"], r.risk_band),
                model_version=r.model_version,
                top_features=r.top_features,
                source="ml_predicted",  # Hard Rule 5
                created_at=r.created_at.isoformat(),
            )
            for r in records
        ]

        return DefectRiskResponse(
            repository_id=str(repository_id),
            model_version=self._model_version,
            disclaimer=RULE_6_DISCLAIMER,  # Hard Rule 6
            source="ml_predicted",  # Hard Rule 5
            summary=summary,
            predictions=prediction_items,
        )


# Global service instance singleton
_inference_service: DefectInferenceService | None = None


def get_inference_service() -> DefectInferenceService:
    """Provide singleton instance of DefectInferenceService."""
    global _inference_service
    if _inference_service is None:
        _inference_service = DefectInferenceService()
    return _inference_service
