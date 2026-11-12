"""Pydantic schemas for ML defect prediction endpoints (P3-07)."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class TopFeatureItem(BaseModel):
    """Top feature contributing to a defect risk estimation."""

    feature: str
    value: float
    description: str


class MLPredictionItem(BaseModel):
    """Defect prediction for a specific file or function.

    Enforces Hard Rule 5 (source: 'ml_predicted') and Hard Rule 6 (model_version included).
    """

    id: str
    file_path: str
    function_name: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    risk_probability: float = Field(..., ge=0.0, le=1.0)
    risk_band: Literal["low", "medium", "high"]
    model_version: str
    top_features: list[dict[str, Any]] = Field(default_factory=list)
    source: Literal["ml_predicted"] = "ml_predicted"
    created_at: str


class DefectRiskSummary(BaseModel):
    """Aggregated defect risk summary statistics for a repository."""

    total_modules: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    average_risk_probability: float


class DefectRiskResponse(BaseModel):
    """Full API response for defect risk prediction query.

    Enforces Hard Rule 5 (source: 'ml_predicted') and Hard Rule 6 (mandatory disclaimer).
    """

    repository_id: str
    model_version: str
    disclaimer: str = "Predictions are risk estimates, never confirmed bugs."
    source: Literal["ml_predicted"] = "ml_predicted"
    summary: DefectRiskSummary
    predictions: list[MLPredictionItem]


class TriggerPredictionRequest(BaseModel):
    """Request payload to manually trigger or refresh defect risk predictions."""

    force_recompute: bool = False
    file_paths: list[str] | None = None
