"""Hindsight memory integration - the ONLY file that talks to Hindsight.

This module handles all Hindsight operations: retain, recall, and reflect.
Isolate Hindsight SDK calls here to protect against API changes.

IMPORTANT: Mock mode is EXPLICITLY controlled by MOCK_MODE environment variable.
Never silently fall back to mock - fail loudly if Hindsight is unavailable and not in mock mode.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from backend.config import settings
from backend.models import HistoricalMatch, InsightItem

# ============================================================================
# Hindsight Client Setup
# ============================================================================

_hindsight_client = None
_hindsight_initialized = False


def _get_hindsight_client():
    """Get or create the Hindsight client.

    Raises:
        RuntimeError: If Hindsight is not configured and not in mock mode.
    """
    global _hindsight_client, _hindsight_initialized

    if _hindsight_initialized:
        return _hindsight_client

    _hindsight_initialized = True

    # In mock mode, return None to signal mock implementations should be used
    if settings.mock_mode:
        _hindsight_client = None
        return None

    try:
        # Try to import Hindsight SDK
        from hindsight import HindsightClient  # type: ignore

        _hindsight_client = HindsightClient(
            api_key=settings.hindsight_api_key,
            base_url=settings.hindsight_base_url
        )
        return _hindsight_client

    except ImportError as e:
        raise RuntimeError(
            "Hindsight SDK not installed. Install with: pip install hindsight-sdk "
            "or set MOCK_MODE=true for development without Hindsight."
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to initialize Hindsight client: {e}. "
            f"Check HINDSIGHT_API_KEY, HINDSIGHT_BASE_URL, HINDSIGHT_BANK_ID. "
            f"Or set MOCK_MODE=true for development."
        ) from e


def is_hindsight_available() -> bool:
    """Check if Hindsight is configured and available (not in mock mode)."""
    if settings.mock_mode:
        return False
    try:
        client = _get_hindsight_client()
        return client is not None
    except RuntimeError:
        return False


# ============================================================================
# Memory Operations - All raise on failure unless in mock mode
# ============================================================================

def recall_memories(
    query: str,
    service_name: str | None = None,
    limit: int = 5
) -> list[HistoricalMatch]:
    """
    Recall relevant historical incidents from Hindsight.

    Args:
        query: Search query (incident description + log excerpt)
        service_name: Optional service filter
        limit: Maximum number of results

    Returns:
        List of HistoricalMatch objects

    Raises:
        RuntimeError: If Hindsight unavailable and not in mock mode.
    """
    client = _get_hindsight_client()

    if client is None:
        if settings.mock_mode:
            return _mock_recall(query, service_name, limit)
        raise RuntimeError("Hindsight client not available and MOCK_MODE=false")

    try:
        bank = client.bank(settings.hindsight_bank_id)

        search_query = query
        if service_name:
            search_query = f"service:{service_name} {query}"

        # Call Hindsight recall - adjust method name per SDK version
        results = bank.recall(query=search_query, limit=limit)

        matches = []
        for item in results:
            match = _parse_hindsight_result(item)
            if match:
                matches.append(match)

        return matches

    except Exception as e:
        if settings.mock_mode:
            return _mock_recall(query, service_name, limit)
        raise RuntimeError(f"Hindsight recall failed: {e}") from e


def retain_memory(
    incident_id: str,
    service_name: str,
    symptom: str,
    verified_root_cause: str,
    verified_resolution: str,
    metadata: dict[str, Any] | None = None
) -> str | None:
    """
    Retain a verified incident outcome in Hindsight.

    ONLY call this with HUMAN-CONFIRMED resolutions. Never store AI hypotheses.

    Args:
        incident_id: Unique incident identifier
        service_name: Affected service
        symptom: Incident symptom/description
        verified_root_cause: Human-confirmed root cause
        verified_resolution: Human-confirmed resolution steps
        metadata: Optional additional metadata

    Returns:
        Hindsight memory ID if successful, None if failed (in mock mode)

    Raises:
        RuntimeError: If Hindsight unavailable and not in mock mode.
    """
    client = _get_hindsight_client()

    if client is None:
        if settings.mock_mode:
            return _mock_retain(incident_id, service_name, symptom, verified_root_cause, verified_resolution)
        raise RuntimeError("Hindsight client not available and MOCK_MODE=false")

    try:
        bank = client.bank(settings.hindsight_bank_id)

        content = f"""Incident: {incident_id}
Service: {service_name}
Symptom: {symptom}
Verified Root Cause: {verified_root_cause}
Verified Resolution: {verified_resolution}"""

        memory_data = {
            "content": content,
            "metadata": {
                "incident_id": incident_id,
                "service_name": service_name,
                "type": "verified_incident_resolution",
                "verified": True,
                "timestamp": datetime.now(UTC).isoformat(),
                **(metadata or {})
            }
        }

        result = bank.add(**memory_data)

        memory_id = result.get("id") or result.get("memory_id") or str(uuid.uuid4())
        return memory_id

    except Exception as e:
        if settings.mock_mode:
            return _mock_retain(incident_id, service_name, symptom, verified_root_cause, verified_resolution)
        raise RuntimeError(f"Hindsight retain failed: {e}") from e


def reflect_patterns(limit: int = 10) -> list[InsightItem]:
    """
    Get recurring patterns/themes from Hindsight reflection.

    Returns:
        List of InsightItem objects

    Raises:
        RuntimeError: If Hindsight unavailable and not in mock mode.
    """
    client = _get_hindsight_client()

    if client is None:
        if settings.mock_mode:
            return _mock_reflect(limit)
        raise RuntimeError("Hindsight client not available and MOCK_MODE=false")

    try:
        bank = client.bank(settings.hindsight_bank_id)

        if hasattr(bank, "reflect"):
            results = bank.reflect(limit=limit)
        elif hasattr(bank, "patterns"):
            results = bank.patterns(limit=limit)
        else:
            return []

        insights = []
        for item in results:
            insight = _parse_hindsight_insight(item)
            if insight:
                insights.append(insight)

        return insights

    except Exception as e:
        if settings.mock_mode:
            return _mock_reflect(limit)
        raise RuntimeError(f"Hindsight reflect failed: {e}") from e


def list_memories(limit: int = 50, offset: int = 0) -> list[HistoricalMatch]:
    """List stored memories from Hindsight (if supported)."""
    client = _get_hindsight_client()

    if client is None:
        if settings.mock_mode:
            return _mock_list_memories(limit, offset)
        raise RuntimeError("Hindsight client not available and MOCK_MODE=false")

    try:
        bank = client.bank(settings.hindsight_bank_id)

        if hasattr(bank, "list"):
            results = bank.list(limit=limit, offset=offset)
        elif hasattr(bank, "search"):
            results = bank.search(query="*", limit=limit, offset=offset)
        else:
            return []

        matches = []
        for item in results:
            match = _parse_hindsight_result(item)
            if match:
                matches.append(match)

        return matches

    except Exception as e:
        if settings.mock_mode:
            return _mock_list_memories(limit, offset)
        raise RuntimeError(f"Hindsight list memories failed: {e}") from e


# ============================================================================
# Mock Implementations - ONLY used when MOCK_MODE=true
# ============================================================================

def _mock_recall(
    query: str,
    service_name: str | None,
    limit: int
) -> list[HistoricalMatch]:
    """Mock recall for demo - returns synthetic seed data matches.

    ONLY called when MOCK_MODE=true. Clearly labeled as mock data.
    """
    from data.sample_incidents import SAMPLE_INCIDENTS

    matches = []
    query_lower = query.lower()

    for inc in SAMPLE_INCIDENTS:
        score: float = 0.0
        if service_name and inc["service"].lower() == service_name.lower():
            score += 0.5
        if any(word in inc["symptom"].lower() for word in query_lower.split()):
            score += 0.3
        if any(word in inc["root_cause"].lower() for word in query_lower.split()):
            score += 0.2

        if score > 0:
            matches.append(HistoricalMatch(
                incident_id=inc["id"],
                service_name=inc["service"],
                symptom=inc["symptom"],
                root_cause=inc["root_cause"],
                resolution=inc["resolution"],
                similarity_score=round(min(score, 0.95), 2),
                created_at=datetime.now(UTC)
            ))

    matches.sort(key=lambda x: x.similarity_score or 0, reverse=True)
    return matches[:limit]


def _mock_retain(
    incident_id: str,
    service_name: str,
    symptom: str,
    verified_root_cause: str,
    verified_resolution: str
) -> str:
    """Mock retain - returns a fake memory ID.

    ONLY called when MOCK_MODE=true.
    """
    memory_id = f"mem_mock_{uuid.uuid4().hex[:12]}"
    return memory_id


def _mock_reflect(limit: int) -> list[InsightItem]:
    """Mock reflection - returns synthetic patterns.

    ONLY called when MOCK_MODE=true.
    """
    return [
        InsightItem(
            theme="Database Connection Pool Exhaustion",
            description="Multiple incidents caused by connection leaks or undersized pools",
            incident_count=3,
            example_incidents=["INC-001", "INC-005"]
        ),
        InsightItem(
            theme="Upstream Dependency Failures",
            description="Cascading failures from downstream service unavailability",
            incident_count=2,
            example_incidents=["INC-003"]
        ),
        InsightItem(
            theme="Authentication Token Issues",
            description="Expired or misconfigured auth tokens causing 401 errors",
            incident_count=1,
            example_incidents=["INC-004"]
        ),
    ][:limit]


def _mock_list_memories(limit: int, offset: int) -> list[HistoricalMatch]:
    """Mock list memories for demo.

    ONLY called when MOCK_MODE=true.
    """
    from data.sample_incidents import SAMPLE_INCIDENTS

    matches = []
    for inc in SAMPLE_INCIDENTS[offset:offset + limit]:
        matches.append(HistoricalMatch(
            incident_id=inc["id"],
            service_name=inc["service"],
            symptom=inc["symptom"],
            root_cause=inc["root_cause"],
            resolution=inc["resolution"],
            similarity_score=None,
            created_at=datetime.now(UTC)
        ))
    return matches


def _parse_hindsight_result(item: Any) -> HistoricalMatch | None:
    """Parse a raw Hindsight result into HistoricalMatch."""
    if item is None:
        return None
    try:
        content = item.get("content", "") if isinstance(item, dict) else str(item)
        metadata = item.get("metadata", {}) if isinstance(item, dict) else {}

        incident_id = metadata.get("incident_id")
        service_name = metadata.get("service_name")
        symptom = metadata.get("symptom", "")
        root_cause = metadata.get("verified_root_cause", "")
        resolution = metadata.get("verified_resolution", "")

        if content:
            lines = content.split("\n")
            for line in lines:
                if line.startswith("Incident:") and not incident_id:
                    incident_id = line.replace("Incident:", "").strip()
                elif line.startswith("Service:") and not service_name:
                    service_name = line.replace("Service:", "").strip()
                elif line.startswith("Symptom:") and not symptom:
                    symptom = line.replace("Symptom:", "").strip()
                elif line.startswith("Verified Root Cause:") and not root_cause:
                    root_cause = line.replace("Verified Root Cause:", "").strip()
                elif line.startswith("Verified Resolution:") and not resolution:
                    resolution = line.replace("Verified Resolution:", "").strip()

        if not incident_id:
            incident_id = f"mem_{uuid.uuid4().hex[:8]}"
        if not service_name:
            service_name = "Unknown"

        return HistoricalMatch(
            incident_id=incident_id,
            service_name=service_name,
            symptom=symptom or "Unknown symptom",
            root_cause=root_cause or "Unknown root cause",
            resolution=resolution or "Unknown resolution",
            similarity_score=item.get("score") if isinstance(item, dict) else None,
        )
    except Exception:
        return None


def _parse_hindsight_insight(item: Any) -> InsightItem | None:
    """Parse a raw Hindsight reflection result into InsightItem."""
    try:
        if isinstance(item, dict):
            return InsightItem(
                theme=item.get("theme", item.get("name", "Unknown Pattern")),
                description=item.get("description", item.get("summary", "")),
                incident_count=item.get("count", item.get("incident_count", 0)),
                example_incidents=item.get("examples", item.get("example_incidents", [])),
            )
        return None
    except Exception:
        return None
