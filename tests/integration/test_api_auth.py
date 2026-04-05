"""Integration tests for API authentication.

Tests that:
1. Public endpoints work without authentication
2. Protected endpoints require authentication
3. Invalid authentication is properly rejected
4. Valid authentication grants access
"""

import pytest


class TestPublicEndpoints:
    """Test that public endpoints don't require authentication."""

    def test_root_is_public(self, client):
        """Root endpoint should be accessible without auth."""
        response = client.get("/")
        assert response.status_code == 200

    def test_health_is_public(self, client):
        """Health endpoint should be accessible without auth."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_docs_is_public(self, client):
        """Docs endpoint should be accessible without auth."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_is_public(self, client):
        """ReDoc endpoint should be accessible without auth."""
        response = client.get("/redoc")
        assert response.status_code == 200

    def test_metrics_is_public(self, client):
        """Metrics endpoint should be accessible without auth."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_openapi_is_public(self, client):
        """OpenAPI schema should be accessible without auth."""
        response = client.get("/openapi.json")
        assert response.status_code == 200


class TestProtectedEndpointsRequireAuth:
    """Test that protected endpoints reject unauthenticated requests."""

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/v1/status",
            "/v1/biomarkers",
            "/v1/signals",
            "/v1/baselines",
            "/v1/annotations",
        ],
    )
    def test_protected_endpoint_requires_auth(self, client, endpoint):
        """Protected endpoints should return 401 without auth."""
        response = client.get(endpoint)
        assert response.status_code == 401, f"{endpoint} should require auth"
        assert "API key required" in response.json().get("detail", "")


class TestInvalidAuthentication:
    """Test that invalid authentication is rejected."""

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/v1/status",
            "/v1/biomarkers",
            "/v1/signals",
        ],
    )
    def test_invalid_api_key_rejected(self, invalid_auth_client, endpoint):
        """Invalid API key should be rejected with 401."""
        response = invalid_auth_client.get(endpoint)
        assert response.status_code == 401
        assert "Invalid API key" in response.json().get("detail", "")


class TestValidAuthentication:
    """Test that valid authentication grants access."""

    def test_authenticated_status_works(self, authenticated_client):
        """Authenticated request to /v1/status should succeed."""
        response = authenticated_client.get("/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_authenticated_biomarkers_works(self, authenticated_client):
        """Authenticated request to /v1/biomarkers should succeed."""
        response = authenticated_client.get("/v1/biomarkers")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_authenticated_signals_works(self, authenticated_client):
        """Authenticated request to /v1/signals should succeed."""
        response = authenticated_client.get("/v1/signals")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_authenticated_baselines_works(self, authenticated_client):
        """Authenticated request to /v1/baselines should succeed."""
        response = authenticated_client.get("/v1/baselines")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_authenticated_annotations_works(self, authenticated_client):
        """Authenticated request to /v1/annotations should succeed."""
        response = authenticated_client.get("/v1/annotations")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestAnalysisEndpointsAuth:
    """Test authentication for analysis endpoints."""

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/v1/analysis/circadian",
            "/v1/analysis/weekly",
            "/v1/analysis/hrv",
            "/v1/analysis/correlations",
        ],
    )
    def test_analysis_requires_auth(self, client, endpoint):
        """Analysis endpoints should require authentication."""
        response = client.get(endpoint)
        assert response.status_code == 401, f"{endpoint} should require auth"

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/v1/analysis/circadian",
            "/v1/analysis/weekly",
            "/v1/analysis/hrv",
            "/v1/analysis/correlations",
        ],
    )
    def test_analysis_works_with_auth(self, authenticated_client, endpoint):
        """Analysis endpoints should work with authentication (may return 404 if no data)."""
        response = authenticated_client.get(endpoint)
        # Should not return 401 (unauthorized) or 500 (server error)
        assert response.status_code in [
            200,
            404,
            422,
        ], f"{endpoint} returned {response.status_code}"


class TestJobsEndpointAuth:
    """Test authentication for job management endpoints."""

    def test_jobs_requires_auth(self, client):
        """Jobs endpoint should require authentication."""
        response = client.get("/v1/jobs/")
        assert response.status_code == 401

    def test_jobs_works_with_auth(self, authenticated_client):
        """Jobs endpoint should work with authentication."""
        response = authenticated_client.get("/v1/jobs/")
        # May return 503 if Redis unavailable, but should not return 401
        assert response.status_code in [200, 503]


class TestWriteEndpointsAuth:
    """Test authentication for write operations."""

    def test_create_signal_requires_auth(self, client):
        """Creating a signal should require authentication."""
        response = client.post(
            "/v1/signals",
            json={
                "time": "2024-01-01T00:00:00",
                "biomarker_slug": "heart_rate",
                "value": 70,
                "source_slug": "manual",
            },
        )
        assert response.status_code == 401

    def test_create_annotation_requires_auth(self, client):
        """Creating an annotation should require authentication."""
        response = client.post(
            "/v1/annotations",
            json={
                "time": "2024-01-01T00:00:00",
                "category": "medication",
                "label": "Test",
            },
        )
        assert response.status_code == 401

    def test_compute_baselines_requires_auth(self, client):
        """Computing baselines should require authentication."""
        response = client.post(
            "/v1/baselines/compute",
            json={
                "window_days": 90,
            },
        )
        assert response.status_code == 401


class TestQueryStringApiKeyDisabled:
    """Test that API key in query string is disabled."""

    def test_query_string_api_key_rejected(self, client, test_api_key):
        """API key in query string should be rejected."""
        response = client.get(f"/v1/status?api_key={test_api_key}")
        # Should still require auth via header
        assert response.status_code == 401
