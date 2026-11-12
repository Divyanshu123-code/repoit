"""Tests verifying frontend Defect Risk UI and Hard Rule 5/6 compliance (P3-07)."""

from pathlib import Path


class TestWebDefectRiskUI:
    """Verifies React defect risk components, routes, API clients, and rule labels."""

    def test_defect_risk_page_file_exists(self) -> None:
        """Verify that DefectRiskPage.tsx exists in apps/web/src/pages/."""
        page_path = Path("apps/web/src/pages/DefectRiskPage.tsx")
        assert page_path.exists(), "DefectRiskPage.tsx must exist"
        content = page_path.read_text(encoding="utf-8")

        # Verify key UI components
        assert "DefectRiskPage" in content
        assert "fetchDefectRisk" in content
        assert "triggerDefectRiskPrediction" in content
        assert "Total Modules" in content
        assert "High Risk" in content
        assert "Medium Risk" in content
        assert "Low Risk" in content

    def test_routing_in_app(self) -> None:
        """Verify that /repositories/:id/defect-risk route is mounted in App.tsx."""
        app_path = Path("apps/web/src/App.tsx")
        assert app_path.exists()
        content = app_path.read_text(encoding="utf-8")

        assert 'path="/repositories/:id/defect-risk"' in content
        assert "DefectRiskPage" in content

    def test_overview_page_has_defect_risk_navigation(self) -> None:
        """Verify that RepoOverviewPage has a navigation link to the Defect Risk page."""
        overview_path = Path("apps/web/src/pages/RepoOverviewPage.tsx")
        assert overview_path.exists()
        content = overview_path.read_text(encoding="utf-8")

        assert "/defect-risk" in content
        assert "Defect Risk" in content

    def test_api_client_defect_risk_methods_and_types(self) -> None:
        """Verify that client.ts exports typed defect risk models and fetch methods."""
        client_path = Path("apps/web/src/api/client.ts")
        assert client_path.exists()
        content = client_path.read_text(encoding="utf-8")

        assert "export interface MLPredictionItem" in content
        assert "export interface DefectRiskResponse" in content
        assert "export async function fetchDefectRisk" in content
        assert "export async function triggerDefectRiskPrediction" in content

    def test_rule_5_source_labelling_in_ui(self) -> None:
        """Hard Rule 5: UI displays source: ml_predicted badge."""
        page_path = Path("apps/web/src/pages/DefectRiskPage.tsx")
        content = page_path.read_text(encoding="utf-8")

        assert "ml_predicted" in content
        assert 'data-testid="rule-5-source-badge"' in content

    def test_rule_6_disclaimer_and_model_version_in_ui(self) -> None:
        """Hard Rule 6: UI displays probabilistic risk estimate notice and model version."""
        page_path = Path("apps/web/src/pages/DefectRiskPage.tsx")
        content = page_path.read_text(encoding="utf-8")

        assert 'data-testid="rule-6-disclaimer-banner"' in content
        assert 'data-testid="model-version-badge"' in content
        assert "Predictions are risk estimates, never confirmed bugs" in content
