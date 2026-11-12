"""Unit and integration tests for ML defect risk inference and API endpoints (P3-07)."""

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.main import app
from app.ml.inference_service import (
    RULE_6_DISCLAIMER,
    DefectInferenceService,
    get_inference_service,
)
from app.ml.models import MLPrediction
from app.ml.schemas import DefectRiskResponse
from app.repos.models import Repository


@pytest.fixture
def sample_features() -> dict[str, float]:
    """Sample metric features representing a moderately complex module."""
    return {
        "loc": 45.0,
        "v(g)": 8.0,
        "ev(g)": 4.0,
        "iv(g)": 3.0,
        "n": 120.0,
        "v": 650.0,
        "l": 0.08,
        "d": 12.5,
        "i": 52.0,
        "e": 8125.0,
        "b": 0.22,
        "t": 451.0,
        "lOCode": 35.0,
        "lOComment": 5.0,
        "lOBlank": 5.0,
        "locCodeAndComment": 2.0,
        "uniq_Op": 14.0,
        "uniq_Opnd": 22.0,
        "total_Op": 70.0,
        "total_Opnd": 50.0,
        "branchCount": 7.0,
    }


def test_inference_service_initialization() -> None:
    """Test that DefectInferenceService initializes and loads artifact metadata."""
    service = get_inference_service()
    assert service.model_version in ["1.0.0", "2.0.0"]
    assert service.artifacts_dir.exists()


def test_predict_features_rule_5_and_rule_6(sample_features: dict[str, float]) -> None:
    """Test defect prediction conforms to Hard Rule 5 (source: ml_predicted) and Rule 6 (risk estimates)."""
    service = get_inference_service()
    res = service.predict_features(sample_features)

    # Core risk metrics
    assert 0.0 <= res["risk_probability"] <= 1.0
    assert res["risk_band"] in ["low", "medium", "high"]

    # Hard Rule 5: Source labelled strictly as 'ml_predicted'
    assert res["source"] == "ml_predicted"

    # Hard Rule 6: Predictions are risk estimates, never confirmed bugs; model version included
    assert res["model_version"] in ["1.0.0", "2.0.0"]
    assert "risk estimates" in res["disclaimer"].lower()
    assert "never confirmed bugs" in res["disclaimer"].lower()

    # Top contributing features
    assert isinstance(res["top_features"], list)
    if res["top_features"]:
        top = res["top_features"][0]
        assert "feature" in top
        assert "value" in top
        assert "description" in top


def test_predict_risk_bands_quantization() -> None:
    """Test quantization of probabilities into 'low', 'medium', 'high' bands."""
    service = DefectInferenceService()
    # Force fallback to test risk band threshold logic deterministically
    service._pipeline = None

    # Low risk (< 0.35)
    with patch.object(service, "_heuristic_fallback", return_value=0.20):
        low_res = service.predict_features({}, threshold_medium=0.35, threshold_high=0.65)
        assert low_res["risk_band"] == "low"

    # Medium risk (0.35 <= p < 0.65)
    with patch.object(service, "_heuristic_fallback", return_value=0.50):
        med_res = service.predict_features({}, threshold_medium=0.35, threshold_high=0.65)
        assert med_res["risk_band"] == "medium"

    # High risk (>= 0.65)
    with patch.object(service, "_heuristic_fallback", return_value=0.75):
        high_res = service.predict_features({}, threshold_medium=0.35, threshold_high=0.65)
        assert high_res["risk_band"] == "high"


def test_predict_source_code_clean_vs_complex() -> None:
    """Test that deeply nested, high-cyclomatic code yields higher risk than simple code."""
    service = get_inference_service()

    simple_code = """
def add(a: int, b: int) -> int:
    return a + b
"""

    complex_code = (
        "def complex_fn(a: int, b: int) -> int:\n"
        + "".join(f"    if a > {i}:\n        b += {i}\n" for i in range(25))
        + "    return b\n"
    )

    simple_pred = service.predict_source_code(simple_code)
    complex_pred = service.predict_source_code(complex_code)

    assert simple_pred["source"] == "ml_predicted"
    assert complex_pred["source"] == "ml_predicted"
    assert complex_pred["risk_probability"] > simple_pred["risk_probability"]


def test_ml_prediction_model_to_dict() -> None:
    """Test MLPrediction SQLAlchemy entity to_dict helper."""
    repo_id = uuid.uuid4()
    pred = MLPrediction(
        repository_id=repo_id,
        file_path="app/core.py",
        function_name="process_batch",
        line_start=10,
        line_end=45,
        risk_probability=0.785,
        risk_band="high",
        model_version="2.0.0",
        top_features=[{"feature": "lOCode", "value": 35.0, "description": "Executable LOC"}],
        source="ml_predicted",
    )

    data = pred.to_dict()
    assert data["file_path"] == "app/core.py"
    assert data["function_name"] == "process_batch"
    assert data["risk_band"] == "high"
    assert data["risk_probability"] == 0.785
    assert data["source"] == "ml_predicted"
    assert data["model_version"] == "2.0.0"


@pytest.mark.asyncio
async def test_api_get_defect_risk_repo_not_found() -> None:
    """GET /repositories/{id}/defect-risk returns 404 for nonexistent repository."""
    nonexistent_id = uuid.uuid4()

    mock_db = MagicMock(spec=AsyncSession)
    mock_db.get.return_value = None

    async def override_get_db_session() -> Any:
        yield mock_db

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/repositories/{nonexistent_id}/defect-risk")
            assert resp.status_code == 404
            assert "not found" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_get_defect_risk_success() -> None:
    """GET /repositories/{id}/defect-risk returns valid DefectRiskResponse with summary and items."""
    repo_id = uuid.uuid4()
    mock_repo = Repository(
        id=repo_id,
        full_name="test/repo",
        source="github",
        default_branch="main",
        status="ready",
    )

    mock_db = MagicMock(spec=AsyncSession)
    mock_db.get.return_value = mock_repo

    mock_service = MagicMock(spec=DefectInferenceService)
    mock_response = DefectRiskResponse(
        repository_id=str(repo_id),
        model_version="2.0.0",
        disclaimer=RULE_6_DISCLAIMER,
        source="ml_predicted",
        summary={
            "total_modules": 2,
            "high_risk_count": 1,
            "medium_risk_count": 1,
            "low_risk_count": 0,
            "average_risk_probability": 0.58,
        },
        predictions=[
            {
                "id": str(uuid.uuid4()),
                "file_path": "app/main.py",
                "function_name": None,
                "line_start": 1,
                "line_end": 100,
                "risk_probability": 0.75,
                "risk_band": "high",
                "model_version": "2.0.0",
                "top_features": [
                    {"feature": "lOCode", "value": 80.0, "description": "Lines of Code"}
                ],
                "source": "ml_predicted",
                "created_at": "2026-11-12T12:00:00Z",
            }
        ],
    )
    mock_service.get_repository_defect_risk.return_value = mock_response

    async def override_get_db_session() -> Any:
        yield mock_db

    def override_get_inference_service() -> DefectInferenceService:
        return mock_service

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_inference_service] = override_get_inference_service
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/repositories/{repo_id}/defect-risk")
            assert resp.status_code == 200
            data = resp.json()
            assert data["repository_id"] == str(repo_id)
            assert data["model_version"] == "2.0.0"
            assert data["source"] == "ml_predicted"  # Rule 5
            assert "never confirmed bugs" in data["disclaimer"]  # Rule 6
            assert data["summary"]["total_modules"] == 2
            assert data["summary"]["high_risk_count"] == 1
            assert len(data["predictions"]) == 1
            assert data["predictions"][0]["risk_band"] == "high"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_trigger_defect_risk_prediction() -> None:
    """POST /repositories/{id}/defect-risk/predict triggers and returns updated defect predictions."""
    repo_id = uuid.uuid4()
    mock_repo = Repository(
        id=repo_id,
        full_name="test/repo",
        source="github",
        default_branch="main",
        status="ready",
    )

    mock_db = MagicMock(spec=AsyncSession)
    mock_db.get.return_value = mock_repo
    mock_scan_res = MagicMock()
    mock_scan_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_scan_res

    mock_service = MagicMock(spec=DefectInferenceService)
    mock_service.predict_and_store_for_modules.return_value = []
    mock_response = DefectRiskResponse(
        repository_id=str(repo_id),
        model_version="2.0.0",
        disclaimer=RULE_6_DISCLAIMER,
        source="ml_predicted",
        summary={
            "total_modules": 1,
            "high_risk_count": 0,
            "medium_risk_count": 0,
            "low_risk_count": 1,
            "average_risk_probability": 0.12,
        },
        predictions=[],
    )
    mock_service.get_repository_defect_risk.return_value = mock_response

    async def override_get_db_session() -> Any:
        yield mock_db

    def override_get_inference_service() -> DefectInferenceService:
        return mock_service

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_inference_service] = override_get_inference_service
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/repositories/{repo_id}/defect-risk/predict")
            assert resp.status_code == 200
            data = resp.json()
            assert data["source"] == "ml_predicted"
            assert data["summary"]["total_modules"] == 1
    finally:
        app.dependency_overrides.clear()
