"""Whoop API client.

Handles OAuth2 token management and API requests to Whoop's REST API.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx

from .schemas import (
    TokenResponse,
    UserProfile,
    BodyMeasurement,
    SleepResponse,
    RecoveryResponse,
    CycleResponse,
    WorkoutResponse,
    Sleep,
    Recovery,
    Cycle,
    Workout,
)

logger = logging.getLogger(__name__)


class WhoopAPIError(Exception):
    """Error from Whoop API."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Whoop API error {status_code}: {message}")


class WhoopRateLimitError(WhoopAPIError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after or 60
        super().__init__(429, f"Rate limited. Retry after {self.retry_after}s")


class WhoopClient:
    """Async client for Whoop API v1.

    Handles:
    - OAuth2 authorization code flow
    - Token refresh
    - Paginated data fetching
    - Rate limit handling with exponential backoff
    """

    BASE_URL = "https://api.prod.whoop.com/developer"
    AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
    TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"

    # Default scopes for full data access
    DEFAULT_SCOPES = [
        "read:recovery",
        "read:cycles",
        "read:sleep",
        "read:workout",
        "read:profile",
        "read:body_measurement",
    ]

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._http_client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http_client is None:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")
        return self._http_client

    # ─────────────────────────────────────────────────────────────────────────
    # OAuth2 Flow
    # ─────────────────────────────────────────────────────────────────────────

    def get_authorization_url(self, state: str, scopes: Optional[list[str]] = None) -> str:
        """Generate OAuth2 authorization URL.

        Args:
            state: Random state parameter for CSRF protection
            scopes: List of scopes to request (defaults to all)

        Returns:
            URL to redirect user to for authorization
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes or self.DEFAULT_SCOPES),
            "state": state,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> TokenResponse:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response with access_token, refresh_token, expires_in
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        response = await self.http.post(self.TOKEN_URL, data=data)

        if response.status_code != 200:
            raise WhoopAPIError(response.status_code, response.text)

        token_data = response.json()
        self.access_token = token_data["access_token"]
        self.refresh_token = token_data.get("refresh_token")

        return TokenResponse(**token_data)

    async def refresh_access_token(self) -> TokenResponse:
        """Refresh the access token using refresh token.

        Returns:
            New token response
        """
        if not self.refresh_token:
            raise WhoopAPIError(401, "No refresh token available")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        response = await self.http.post(self.TOKEN_URL, data=data)

        if response.status_code != 200:
            raise WhoopAPIError(response.status_code, response.text)

        token_data = response.json()
        self.access_token = token_data["access_token"]
        self.refresh_token = token_data.get("refresh_token", self.refresh_token)

        return TokenResponse(**token_data)

    # ─────────────────────────────────────────────────────────────────────────
    # API Requests
    # ─────────────────────────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> dict:
        """Make authenticated API request with retry logic.

        Handles:
        - Bearer token authentication
        - Rate limit retries with exponential backoff
        - Token refresh on 401
        """
        if not self.access_token:
            raise WhoopAPIError(401, "No access token. Complete OAuth flow first.")

        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = f"{self.BASE_URL}{endpoint}"

        response = await self.http.request(method, url, headers=headers, params=params)

        # Handle rate limiting
        if response.status_code == 429:
            if retry_count >= max_retries:
                raise WhoopRateLimitError()

            retry_after = int(response.headers.get("Retry-After", 60))
            wait_time = min(retry_after, 2 ** retry_count * 30)  # Exponential backoff, max from header
            logger.warning(f"Rate limited. Waiting {wait_time}s before retry {retry_count + 1}")
            await asyncio.sleep(wait_time)
            return await self._request(method, endpoint, params, retry_count + 1, max_retries)

        # Handle expired token
        if response.status_code == 401 and self.refresh_token and retry_count == 0:
            logger.info("Access token expired. Refreshing...")
            await self.refresh_access_token()
            return await self._request(method, endpoint, params, retry_count + 1, max_retries)

        if response.status_code >= 400:
            raise WhoopAPIError(response.status_code, response.text)

        return response.json()

    async def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make GET request."""
        return await self._request("GET", endpoint, params)

    # ─────────────────────────────────────────────────────────────────────────
    # User Data
    # ─────────────────────────────────────────────────────────────────────────

    async def get_profile(self) -> UserProfile:
        """Get user profile."""
        data = await self._get("/v2/user/profile/basic")
        return UserProfile(**data)

    async def get_body_measurement(self) -> BodyMeasurement:
        """Get user body measurements."""
        data = await self._get("/v2/user/measurement/body")
        return BodyMeasurement(**data)

    # ─────────────────────────────────────────────────────────────────────────
    # Sleep Data
    # ─────────────────────────────────────────────────────────────────────────

    async def get_sleep(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        next_token: Optional[str] = None,
    ) -> SleepResponse:
        """Get sleep records.

        Args:
            start: Start of date range (default: 30 days ago)
            end: End of date range (default: now)
            next_token: Pagination token for next page

        Returns:
            Paginated sleep response
        """
        params = {}
        if start:
            params["start"] = start.isoformat()
        if end:
            params["end"] = end.isoformat()
        if next_token:
            params["nextToken"] = next_token

        data = await self._get("/v2/activity/sleep", params)
        return SleepResponse(**data)

    async def get_all_sleep(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[Sleep]:
        """Get all sleep records, handling pagination.

        Args:
            start: Start of date range
            end: End of date range

        Returns:
            List of all sleep records in range
        """
        records = []
        next_token = None

        while True:
            response = await self.get_sleep(start, end, next_token)
            records.extend(response.records)

            if not response.next_token:
                break
            next_token = response.next_token

        return records

    # ─────────────────────────────────────────────────────────────────────────
    # Recovery Data
    # ─────────────────────────────────────────────────────────────────────────

    async def get_recovery(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        next_token: Optional[str] = None,
    ) -> RecoveryResponse:
        """Get recovery records."""
        params = {}
        if start:
            params["start"] = start.isoformat()
        if end:
            params["end"] = end.isoformat()
        if next_token:
            params["nextToken"] = next_token

        data = await self._get("/v2/recovery", params)
        return RecoveryResponse(**data)

    async def get_all_recovery(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[Recovery]:
        """Get all recovery records, handling pagination."""
        records = []
        next_token = None

        while True:
            response = await self.get_recovery(start, end, next_token)
            records.extend(response.records)

            if not response.next_token:
                break
            next_token = response.next_token

        return records

    # ─────────────────────────────────────────────────────────────────────────
    # Cycle (Strain) Data
    # ─────────────────────────────────────────────────────────────────────────

    async def get_cycles(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        next_token: Optional[str] = None,
    ) -> CycleResponse:
        """Get cycle (strain) records."""
        params = {}
        if start:
            params["start"] = start.isoformat()
        if end:
            params["end"] = end.isoformat()
        if next_token:
            params["nextToken"] = next_token

        data = await self._get("/v2/cycle", params)
        return CycleResponse(**data)

    async def get_all_cycles(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[Cycle]:
        """Get all cycle records, handling pagination."""
        records = []
        next_token = None

        while True:
            response = await self.get_cycles(start, end, next_token)
            records.extend(response.records)

            if not response.next_token:
                break
            next_token = response.next_token

        return records

    # ─────────────────────────────────────────────────────────────────────────
    # Workout Data
    # ─────────────────────────────────────────────────────────────────────────

    async def get_workouts(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        next_token: Optional[str] = None,
    ) -> WorkoutResponse:
        """Get workout records."""
        params = {}
        if start:
            params["start"] = start.isoformat()
        if end:
            params["end"] = end.isoformat()
        if next_token:
            params["nextToken"] = next_token

        data = await self._get("/v2/activity/workout", params)
        return WorkoutResponse(**data)

    async def get_all_workouts(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[Workout]:
        """Get all workout records, handling pagination."""
        records = []
        next_token = None

        while True:
            response = await self.get_workouts(start, end, next_token)
            records.extend(response.records)

            if not response.next_token:
                break
            next_token = response.next_token

        return records
