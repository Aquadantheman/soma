"""Pytest configuration and fixtures for integration tests.

Provides authenticated and unauthenticated test clients for API testing.
"""

import os
import pytest
from fastapi.testclient import TestClient

# Set test environment variables BEFORE importing the app
# This ensures auth is configured correctly for tests
TEST_API_KEY = "test-api-key-for-integration-tests-only"
os.environ["SOMA_AUTH_MODE"] = "api_key"
os.environ["SOMA_API_KEY"] = TEST_API_KEY
os.environ["SOMA_ALLOW_API_KEY_QUERY"] = "false"

from api.main import app
from api.auth import get_auth_config, _auth_config


@pytest.fixture(scope="module")
def test_api_key() -> str:
    """Return the test API key."""
    return TEST_API_KEY


@pytest.fixture(scope="module")
def auth_headers(test_api_key: str) -> dict:
    """Return headers with valid API key authentication."""
    return {"X-API-Key": test_api_key}


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the API (unauthenticated).

    Use this to test that endpoints properly reject unauthenticated requests.
    """
    return TestClient(app)


@pytest.fixture
def authenticated_client(auth_headers: dict) -> TestClient:
    """Create an authenticated test client.

    Use this for most tests that need to access protected endpoints.
    """
    client = TestClient(app)
    client.headers.update(auth_headers)
    return client


@pytest.fixture
def invalid_auth_client() -> TestClient:
    """Create a test client with invalid authentication.

    Use this to test that endpoints properly reject invalid credentials.
    """
    client = TestClient(app)
    client.headers.update({"X-API-Key": "invalid-api-key"})
    return client


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENDPOINTS (no auth required)
# ─────────────────────────────────────────────────────────────────────────────

PUBLIC_ENDPOINTS = [
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/metrics",
]


@pytest.fixture
def public_endpoints() -> list[str]:
    """Return list of public endpoints that don't require authentication."""
    return PUBLIC_ENDPOINTS


# ─────────────────────────────────────────────────────────────────────────────
# PROTECTED ENDPOINTS (require auth)
# ─────────────────────────────────────────────────────────────────────────────

PROTECTED_GET_ENDPOINTS = [
    # Status
    "/v1/status",
    "/v1/status/ingest-history",
    "/v1/status/biomarker-coverage",
    # Biomarkers
    "/v1/biomarkers",
    "/v1/biomarkers/categories",
    "/v1/sources",
    # Signals
    "/v1/signals",
    "/v1/signals/latest",
    "/v1/signals/range",
    # Baselines
    "/v1/baselines",
    "/v1/baselines/latest",
    # Annotations
    "/v1/annotations",
    "/v1/annotations/categories",
    # Jobs
    "/v1/jobs/",
    # Analysis
    "/v1/analysis/circadian",
    "/v1/analysis/weekly",
    "/v1/analysis/hrv",
    "/v1/analysis/spo2",
    "/v1/analysis/correlations",
    "/v1/analysis/readiness",
    "/v1/analysis/stability",
    "/v1/analysis/derived",
    "/v1/analysis/holistic",
]


@pytest.fixture
def protected_get_endpoints() -> list[str]:
    """Return list of protected GET endpoints that require authentication."""
    return PROTECTED_GET_ENDPOINTS
