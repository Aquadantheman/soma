"""Integration tests for API health and structure."""

import pytest


class TestAPIHealth:
    """Test API health and basic endpoints (public, no auth required)."""

    def test_root_returns_api_info(self, client):
        """Root endpoint should return API information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data

    def test_health_check(self, client):
        """Health endpoint should return OK status."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_docs_available(self, client):
        """OpenAPI docs should be available."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_available(self, client):
        """ReDoc should be available."""
        response = client.get("/redoc")
        assert response.status_code == 200


class TestAnalysisRouterStructure:
    """Test that analysis routers are properly mounted."""

    def test_analysis_endpoints_exist(self, authenticated_client):
        """Analysis endpoints should be accessible (even if they return 404 for no data)."""
        endpoints = [
            "/analysis/circadian",
            "/analysis/weekly",
            "/analysis/hrv",
            "/analysis/spo2",
            "/analysis/correlations",
            "/analysis/readiness",
            "/analysis/stability",
            "/analysis/derived",
        ]

        for endpoint in endpoints:
            response = authenticated_client.get(endpoint)
            # Should not return 500 (server error), 405 (method not allowed), or 401 (unauthorized)
            assert response.status_code in [200, 404], f"Endpoint {endpoint} returned {response.status_code}"
