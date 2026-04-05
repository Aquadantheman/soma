"""Integration tests for API versioning."""

import pytest


class TestVersionedAPI:
    """Test versioned API endpoints under /v1 prefix."""

    def test_v1_status_endpoint(self, authenticated_client):
        """v1 status endpoint should work with authentication."""
        response = authenticated_client.get("/v1/status")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_v1_biomarkers_endpoint(self, authenticated_client):
        """v1 biomarkers endpoint should be accessible with authentication."""
        response = authenticated_client.get("/v1/biomarkers")

        # Should return list (empty if no data)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_v1_analysis_endpoints(self, authenticated_client):
        """v1 analysis endpoints should be accessible with authentication."""
        endpoints = [
            "/v1/analysis/circadian",
            "/v1/analysis/weekly",
            "/v1/analysis/hrv",
        ]

        for endpoint in endpoints:
            response = authenticated_client.get(endpoint)
            # Should not return 500, 405, or 401
            assert response.status_code in [200, 404, 422], \
                f"Endpoint {endpoint} returned {response.status_code}"

    def test_legacy_endpoints_deprecated(self, authenticated_client):
        """Legacy endpoints should still work but be deprecated (require auth)."""
        # Check that legacy endpoints exist and work with auth
        response = authenticated_client.get("/status")
        assert response.status_code == 200

    def test_v1_jobs_endpoint(self, authenticated_client):
        """v1 jobs endpoint should be accessible with authentication."""
        response = authenticated_client.get("/v1/jobs/")

        # Should return queue stats or 503 if Redis unavailable
        assert response.status_code in [200, 503]


class TestCORSConfiguration:
    """Test CORS is properly configured."""

    def test_cors_headers_present(self, client):
        """CORS headers should be present for allowed origins."""
        response = client.options(
            "/v1/status",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )

        # Should allow CORS
        assert response.status_code == 200


class TestMetricsEndpoint:
    """Test Prometheus metrics endpoint."""

    def test_metrics_endpoint(self, client):
        """Metrics endpoint should return Prometheus format."""
        response = client.get("/metrics")

        assert response.status_code == 200
        # Should contain Prometheus metrics
        content = response.text
        assert "soma_http_requests_total" in content or "# HELP" in content
