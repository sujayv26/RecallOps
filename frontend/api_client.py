"""API client for Streamlit frontend - ONLY talks to FastAPI backend."""

import os
from dataclasses import dataclass
from typing import Any

import requests

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


@dataclass
class APIResponse:
    """Standardized API response wrapper."""
    success: bool
    data: Any = None
    error: str | None = None


class RecallOpsAPIClient:
    """Client for RecallOps FastAPI backend."""

    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _handle_response(self, response: requests.Response) -> APIResponse:
        """Handle API response uniformly."""
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        if response.ok:
            return APIResponse(success=True, data=data)
        else:
            error_msg = data.get("detail", f"HTTP {response.status_code}")
            return APIResponse(success=False, error=error_msg)

    # ========================================================================
    # Health
    # ========================================================================

    def health_check(self) -> APIResponse:
        """Check backend health."""
        try:
            resp = self.session.get(f"{self.base_url}/health", timeout=5)
            return self._handle_response(resp)
        except requests.RequestException as e:
            return APIResponse(success=False, error=f"Connection failed: {e}")

    # ========================================================================
    # Analysis
    # ========================================================================

    def analyze_incident(
        self,
        service_name: str,
        error_description: str,
        log_excerpt: str | None = None
    ) -> APIResponse:
        """Submit incident for analysis."""
        payload = {
            "service_name": service_name,
            "error_description": error_description,
            "log_excerpt": log_excerpt
        }

        try:
            resp = self.session.post(
                f"{self.base_url}/analyze",
                json=payload,
                timeout=60  # Longer timeout for LLM processing
            )
            return self._handle_response(resp)
        except requests.Timeout:
            return APIResponse(success=False, error="Request timed out (LLM processing)")
        except requests.RequestException as e:
            return APIResponse(success=False, error=f"Request failed: {e}")

    def get_analysis(self, incident_id: str) -> APIResponse:
        """Retrieve a previous analysis by ID."""
        try:
            resp = self.session.get(f"{self.base_url}/demo/analysis/{incident_id}", timeout=10)
            return self._handle_response(resp)
        except requests.RequestException as e:
            return APIResponse(success=False, error=f"Request failed: {e}")

    # ========================================================================
    # Resolution
    # ========================================================================

    def confirm_resolution(
        self,
        incident_id: str,
        verified_root_cause: str,
        verified_resolution: str,
        notes: str | None = None
    ) -> APIResponse:
        """Submit human-confirmed resolution."""
        payload = {
            "incident_id": incident_id,
            "verified_root_cause": verified_root_cause,
            "verified_resolution": verified_resolution,
            "notes": notes
        }

        try:
            resp = self.session.post(
                f"{self.base_url}/resolve",
                json=payload,
                timeout=30
            )
            return self._handle_response(resp)
        except requests.RequestException as e:
            return APIResponse(success=False, error=f"Request failed: {e}")

    def get_resolution(self, incident_id: str) -> APIResponse:
        """Retrieve a verified resolution by ID."""
        try:
            resp = self.session.get(f"{self.base_url}/demo/resolution/{incident_id}", timeout=10)
            return self._handle_response(resp)
        except requests.RequestException as e:
            return APIResponse(success=False, error=f"Request failed: {e}")

    # ========================================================================
    # Memory Explorer
    # ========================================================================

    def list_memories(self, limit: int = 50, offset: int = 0) -> APIResponse:
        """List retained memories."""
        try:
            resp = self.session.get(
                f"{self.base_url}/memories",
                params={"limit": limit, "offset": offset},
                timeout=10
            )
            return self._handle_response(resp)
        except requests.RequestException as e:
            return APIResponse(success=False, error=f"Request failed: {e}")

    def get_insights(self) -> APIResponse:
        """Get recurring patterns from memory reflection."""
        try:
            resp = self.session.get(f"{self.base_url}/insights", timeout=10)
            return self._handle_response(resp)
        except requests.RequestException as e:
            return APIResponse(success=False, error=f"Request failed: {e}")


# Singleton instance
_api_client: RecallOpsAPIClient | None = None


def get_api_client() -> RecallOpsAPIClient:
    """Get or create the API client singleton."""
    global _api_client
    if _api_client is None:
        _api_client = RecallOpsAPIClient()
    return _api_client
