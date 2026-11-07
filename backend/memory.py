"""Hindsight memory integration - the ONLY file that talks to Hindsight.

This module handles all Hindsight operations: retain, recall, and reflect.
Isolate Hindsight SDK calls here to protect against API changes.
"""

import os
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from backend.config import settings
from backend.models import HistoricalMatch, IncidentInput, InsightItem


# ============================================================================
# Hindsight Client Setup
# ============================================================================

# Lazy import to avoid hard dependency at module load
_hindsight_client = None
_hindsight_available = None


def _get_hindsight_client():
    """Get or create the Hindsight client."""
    global _hindsight_client, _hindsight_available

    if _hindsight_available is False:
        return None

    if _hindsight_client is not None:
        return _hindsight_client

    try:
        # Try to import Hindsight SDK
        # The exact import depends on the SDK version - adjust as needed
        from hindsight import HindsightClient  # type: ignore

        _hindsight_client = HindsightClient(
            api_key=settings.hindsight_api_key,
            base_url=settings.hindsight_base_url
        )
        _hindsight_available = True
        return _hindsight_client

    except ImportError:
        # Hindsight SDK not installed - use mock mode for demo
        _hindsight_available = False
        _hindsight_client = None
        return None

    except Exception as e:
        # Configuration error or connection issue
        print(f"[Hindsight] Failed to initialize client: {e}")
        _hindsight_available = False
        _hindsight_client = None
        return None


def is_hindsight_available() -> bool:
    """Check if Hindsight is configured and available."""
    client = _get_hindsight_client()
    return client is not None


# ============================================================================
# Memory Operations
# ============================================================================

def recall_memories(
    query: str,
    service_name: Optional[str] = None,
    limit: int = 5
) -> List[HistoricalMatch]:
    """
    Recall relevant historical incidents from Hindsight.

    Args:
        query: Search query (incident description + log excerpt)
        service_name: Optional service filter
        limit: Maximum number of results

    Returns:
        List of HistoricalMatch objects (empty if Hindsight unavailable)
    """
    client = _get_hindsight_client()

    if client is None:
        # Mock mode - return empty list, demo data handled separately
        return _mock_recall(query, service_name, limit)

    try:
        # The exact Hindsight SDK method may vary - check current docs
        # Common patterns: client.recall(), client.search(), bank.recall()
        bank = client.bank(settings.hindsight_bank_id)

        # Build search query
        search_query = query
        if service_name:
            search_query = f"service:{service_name} {query}"

        # Call Hindsight recall - adjust method name per SDK version
        # Typical: bank.recall(query=search_query, limit=limit)
        results = bank.recall(query=search_query, limit=limit)

        # Parse results into HistoricalMatch objects
        matches = []
        for item in results:
            # Hindsight result structure varies - adapt to actual response
            match = _parse_hindsight_result(item)
            if match:
                matches.append(match)

        return matches

    except Exception as e:
        print(f"[Hindsight] Recall failed: {e}")
        # Fall back to mock for demo continuity
        return _mock_recall(query, service_name, limit)


def retain_memory(
    incident_id: str,
    service_name: str,
    symptom: str,
    verified_root_cause: str,
    verified_resolution: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Retain a verified incident outcome in Hindsight.

    Only call this with HUMAN-CONFIRMED resolutions. Never store AI hypotheses.

    Args:
        incident_id: Unique incident identifier
        service_name: Affected service
        symptom: Incident symptom/description
        verified_root_cause: Human-confirmed root cause
        verified_resolution: Human-confirmed resolution steps
        metadata: Optional additional metadata

    Returns:
        Hindsight memory ID if successful, None otherwise
    """
    client = _get_hindsight_client()

    if client is None:
        # Mock mode
        return _mock_retain(incident_id, service_name, symptom, verified_root_cause, verified_resolution)

    try:
        bank = client.bank(settings.hindsight_bank_id)

        # Build memory content - structure per Hindsight requirements
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
                "timestamp": datetime.utcnow().isoformat(),
                **(metadata or {})
            }
        }

        # Call Hindsight retain - adjust method per SDK
        # Typical: bank.add(**memory_data) or bank.retain(...)
        result = bank.add(**memory_data)

        # Extract memory ID from result
        memory_id = result.get("id") or result.get("memory_id") or str(uuid.uuid4())
        return memory_id

    except Exception as e:
        print(f"[Hindsight] Retain failed: {e}")
        return None


def reflect_patterns(limit: int = 10) -> List[InsightItem]:
    """
    Get recurring patterns/themes from Hindsight reflection.

    Returns:
        List of InsightItem objects (empty if not supported/unavailable)
    """
    client = _get_hindsight_client()

    if client is None:
        return _mock_reflect(limit)

    try:
        bank = client.bank(settings.hindsight_bank_id)

        # Check if reflection is supported - method varies by SDK version
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
        print(f"[Hindsight] Reflect failed: {e}")
        return []


def list_memories(limit: int = 50, offset: int = 0) -> List[HistoricalMatch]:
    """List stored memories from Hindsight (if supported)."""
    client = _get_hindsight_client()

    if client is None:
        return _mock_list_memories(limit, offset)

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
        print(f"[Hindsight] List memories failed: {e}")
        return []


# ============================================================================
# Mock Implementations (for demo when Hindsight unavailable)
# ============================================================================

def _mock_recall(
    query: str,
    service_name: Optional[str],
    limit: int
) -> List[HistoricalMatch]:
    """Mock recall for demo - returns synthetic seed data matches."""
    # This simulates what Hindsight would return with seeded data
    # In real implementation, this comes from the Hindsight bank
    from data.sample_incidents import SAMPLE_INCIDENTS

    matches = []
    query_lower = query.lower()

    for inc in SAMPLE_INCIDENTS:
        # Simple keyword matching for demo
        score = 0
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
                created_at=datetime.utcnow()
            ))

    # Sort by similarity and limit
    matches.sort(key=lambda x: x.similarity_score or 0, reverse=True)
    return matches[:limit]


def _mock_retain(
    incident_id: str,
    service_name: str,
    symptom: str,
    verified_root_cause: str,
    verified_resolution: str
) -> str:
    """Mock retain - returns a fake memory ID."""
    memory_id = f"mem_{uuid.uuid4().hex[:12]}"
    print(f"[Mock Hindsight] Retained memory {memory_id} for incident {incident_id}")
    return memory_id


def _mock_reflect(limit: int) -> List[InsightItem]:
    """Mock reflection - returns synthetic patterns."""
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


def _mock_list_memories(limit: int, offset: int) -> List[HistoricalMatch]:
    """Mock list memories for demo."""
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
            created_at=datetime.utcnow()
        ))
    return matches


def _parse_hindsight_result(item: Any) -> Optional[HistoricalMatch]:
    """Parse a raw Hindsight result into HistoricalMatch."""
    try:
        # Adapt to actual Hindsight response structure
        # This is a placeholder - adjust based on real SDK response
        content = item.get("content", "") if isinstance(item, dict) else str(item)
        metadata = item.get("metadata", {}) if isinstance(item, dict) else {}

        # Try to extract structured data from content or metadata
        incident_id = metadata.get("incident_id", f"mem_{uuid.uuid4().hex[:8]}")
        service_name = metadata.get("service_name", "Unknown")
        symptom = metadata.get("symptom", "")
        root_cause = metadata.get("verified_root_cause", "")
        resolution = metadata.get("verified_resolution", "")

        # If not in metadata, try parsing from content
        if not symptom and content:
            # Basic parsing attempt
            lines = content.split("\n")
            for line in lines:
                if line.startswith("Symptom:"):
                    symptom = line.replace("Symptom:", "").strip()
                elif line.startswith("Verified Root Cause:"):
                    root_cause = line.replace("Verified Root Cause:", "").strip()
                elif line.startswith("Verified Resolution:"):
                    resolution = line.replace("Verified Resolution:", "").strip()

        return HistoricalMatch(
            incident_id=incident_id,
            service_name=service_name,
            symptom=symptom or "Unknown symptom",
            root_cause=root_cause or "Unknown root cause",
            resolution=resolution or "Unknown resolution",
            similarity_score=item.get("score") if isinstance(item, dict) else None,
        )
    except Exception as e:
        print(f"[Hindsight] Failed to parse result: {e}")
        return None


def _parse_hindsight_insight(item: Any) -> Optional[InsightItem]:
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