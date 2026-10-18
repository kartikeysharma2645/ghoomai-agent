"""Asynchronous HTTP client for the GhoomAI agent endpoint.

Calls the existing GhoomAI backend at ``POST /api/agent`` with a JSON body
containing ``session`` and ``message``. Returns the parsed response data
along with the updated ``data.session`` value.

Designed for dependency injection: pass an :class:`httpx.AsyncClient`
instance (or a test double) to the constructor so tests can mock network
behavior without making real HTTP calls.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

# Documented initial session structure for a new GhoomAI conversation.
INITIAL_SESSION: dict = {
    "sessionVersion": 1,
    "transcript": [],
    "tripStatus": "DRAFT",
}


class GhoomAIClientError(Exception):
    """Base exception for GhoomAI client errors."""


class GhoomAITimeoutError(GhoomAIClientError):
    """Raised when the GhoomAI request times out."""


class GhoomAIConnectionError(GhoomAIClientError):
    """Raised when the GhoomAI endpoint cannot be reached."""


class GhoomAIHTTPError(GhoomAIClientError):
    """Raised when the GhoomAI endpoint returns an error HTTP status."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"GhoomAI API returned HTTP {status_code}: {message}")


class GhoomAIResponseError(GhoomAIClientError):
    """Raised when the GhoomAI response is invalid or indicates failure."""


class GhoomAIClient:
    """Client for interacting with the GhoomAI /api/agent endpoint."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Caller may supply an AsyncClient for testing/mocking.
        # If none is supplied, one is created per request (safe but less
        # efficient; for production use, pass a shared client).
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=self.timeout)

    async def send_message(
        self, message: str, session: Optional[dict] = None
    ) -> Dict[str, Any]:
        """Send a message to the GhoomAI agent endpoint.

        Args:
            message: The user's message text.
            session: The current session state. If None or missing fields,
                the documented initial session structure is used.

        Returns:
            A dict with the parsed response data and the updated session
            under the ``session`` key.

        Raises:
            GhoomAITimeoutError: If the request times out.
            GhoomAIConnectionError: If the endpoint cannot be reached.
            GhoomAIHTTPError: If the endpoint returns an error status.
            GhoomAIResponseError: If the response is invalid JSON or
                indicates an unsuccessful application response.
        """
        # Build the request body, falling back to the initial session.
        request_session = dict(session) if session else {}
        for key, value in INITIAL_SESSION.items():
            request_session.setdefault(key, value)

        payload: Dict[str, Any] = {
            "session": request_session,
            "message": message,
        }

        url = f"{self.base_url}/api/agent"
        client = await self._get_client()
        owns_client = self._client is None

        try:
            response = await client.post(url, json=payload, timeout=self.timeout)
        except httpx.TimeoutException as exc:
            if owns_client:
                await client.aclose()
            raise GhoomAITimeoutError(
                "Request to GhoomAI API timed out"
            ) from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            if owns_client:
                await client.aclose()
            raise GhoomAIConnectionError(
                "Unable to connect to GhoomAI API"
            ) from exc
        except httpx.RequestError as exc:
            if owns_client:
                await client.aclose()
            raise GhoomAIConnectionError(
                "Request to GhoomAI API failed"
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        # Check HTTP status code.
        if response.status_code >= 400:
            raise GhoomAIHTTPError(
                response.status_code,
                response.text[:200],
            )

        # Parse JSON.
        try:
            data = response.json()
        except ValueError as exc:
            raise GhoomAIResponseError(
                "Invalid JSON response from GhoomAI API"
            ) from exc

        # Validate the expected response contract.
        if not isinstance(data, dict):
            raise GhoomAIResponseError(
                "GhoomAI API response is not a JSON object"
            )

        # Do not assume every successful HTTP response is a successful
        # GhoomAI operation. Check for application-level error indicators.
        if data.get("error") or data.get("status") == "error":
            raise GhoomAIResponseError(
                "GhoomAI API returned an application error"
            )

        updated_session = data.get("session")
        if updated_session is None:
            raise GhoomAIResponseError(
                "GhoomAI API response missing expected 'session' field"
            )

        return {
            "data": data,
            "session": updated_session,
        }
