"""Tests for memory module - Hindsight integration."""

import os
from unittest.mock import MagicMock, patch

import pytest

from backend.memory import (
    _mock_list_memories,
    _mock_recall,
    _mock_reflect,
    _mock_retain,
    _parse_hindsight_insight,
    _parse_hindsight_result,
    is_hindsight_available,
    list_memories,
    recall_memories,
    reflect_patterns,
    retain_memory,
)
from backend.models import HistoricalMatch, InsightItem

# ============================================================================
# Helper to reset module state
# ============================================================================

def _reset_memory_module():
    """Reset the memory module's global state."""
    import backend.memory
    backend.memory._hindsight_client = None
    backend.memory._hindsight_initialized = False


# ============================================================================
# Hindsight Availability Tests
# ============================================================================

@patch("backend.memory._get_hindsight_client")
def test_is_hindsight_available_true(mock_client):
    """Test Hindsight availability when client works."""
    mock_client.return_value = MagicMock()
    assert is_hindsight_available() is True


@patch("backend.memory._get_hindsight_client")
def test_is_hindsight_available_false(mock_client):
    """Test Hindsight availability when client fails."""
    mock_client.return_value = None
    assert is_hindsight_available() is False


# ============================================================================
# Mock Recall Tests
# ============================================================================

def test_mock_recall_empty():
    """Test mock recall with no matches - use truly unrelated query."""
    result = _mock_recall("xyz completely unrelated foobar abc", None, 5)
    assert result == []


def test_mock_recall_with_service_match():
    """Test mock recall matches service name."""
    # Use a query that only matches the service name, not symptoms
    result = _mock_recall("backend service", "Backend API", 5)
    assert len(result) > 0
    # At least one match should be for Backend API
    backend_matches = [m for m in result if m.service_name == "Backend API"]
    assert len(backend_matches) > 0


def test_mock_recall_with_symptom_match():
    """Test mock recall matches symptom keywords."""
    result = _mock_recall("connection pool exhausted", None, 5)
    assert len(result) > 0
    assert any("pool" in m.symptom.lower() or "memory" in m.symptom.lower() for m in result)


def test_mock_recall_limit():
    """Test mock recall respects limit."""
    result = _mock_recall("error", None, 2)
    assert len(result) <= 2


def test_mock_recall_sorting():
    """Test mock recall sorts by similarity score."""
    result = _mock_recall("backend api connection pool", "Backend API", 5)
    if len(result) > 1:
        scores = [m.similarity_score or 0 for m in result]
        assert scores == sorted(scores, reverse=True)


# ============================================================================
# Mock Retain Tests
# ============================================================================

def test_mock_retain_returns_id():
    """Test mock retain returns a memory ID."""
    memory_id = _mock_retain(
        incident_id="INC-999",
        service_name="Test Service",
        symptom="Test symptom",
        verified_root_cause="Test cause",
        verified_resolution="Test resolution"
    )
    assert memory_id.startswith("mem_mock_")
    assert len(memory_id) > 4


# ============================================================================
# Mock Reflect Tests
# ============================================================================

def test_mock_reflect_returns_insights():
    """Test mock reflect returns insight items."""
    insights = _mock_reflect(10)
    assert isinstance(insights, list)
    assert len(insights) > 0
    for insight in insights:
        assert isinstance(insight, InsightItem)
        assert insight.theme
        assert insight.description
        assert insight.incident_count > 0


def test_mock_reflect_limit():
    """Test mock reflect respects limit."""
    insights = _mock_reflect(2)
    assert len(insights) <= 2


# ============================================================================
# Mock List Memories Tests
# ============================================================================

def test_mock_list_memories():
    """Test mock list memories returns historical matches."""
    memories = _mock_list_memories(10, 0)
    assert isinstance(memories, list)
    assert len(memories) > 0
    for mem in memories:
        assert isinstance(mem, HistoricalMatch)
        assert mem.incident_id.startswith("INC-")


def test_mock_list_memories_pagination():
    """Test mock list memories pagination."""
    page1 = _mock_list_memories(2, 0)
    page2 = _mock_list_memories(2, 2)
    assert len(page1) <= 2
    assert len(page2) <= 2
    ids1 = {m.incident_id for m in page1}
    ids2 = {m.incident_id for m in page2}
    assert ids1.isdisjoint(ids2)


# ============================================================================
# Real Hindsight Integration Tests (Mocked)
# ============================================================================

@patch("backend.memory._get_hindsight_client")
def test_recall_memories_hindsight_unavailable_raises(mock_client):
    """Test recall raises when Hindsight unavailable and not in mock mode."""
    _reset_memory_module()
    mock_client.return_value = None

    with pytest.raises(RuntimeError, match="Hindsight client not available"):
        recall_memories("test query", "Test Service", 5)


@patch("backend.memory._get_hindsight_client")
def test_retain_memory_hindsight_unavailable_raises(mock_client):
    """Test retain raises when Hindsight unavailable and not in mock mode."""
    _reset_memory_module()
    mock_client.return_value = None

    with pytest.raises(RuntimeError, match="Hindsight client not available"):
        retain_memory(
            incident_id="INC-999",
            service_name="Test Service",
            symptom="Test symptom",
            verified_root_cause="Test cause",
            verified_resolution="Test resolution"
        )


@patch("backend.memory._get_hindsight_client")
def test_reflect_patterns_hindsight_unavailable_raises(mock_client):
    """Test reflect raises when Hindsight unavailable and not in mock mode."""
    _reset_memory_module()
    mock_client.return_value = None

    with pytest.raises(RuntimeError, match="Hindsight client not available"):
        reflect_patterns(5)


@patch("backend.memory._get_hindsight_client")
def test_list_memories_hindsight_unavailable_raises(mock_client):
    """Test list_memories raises when Hindsight unavailable and not in mock mode."""
    _reset_memory_module()
    mock_client.return_value = None

    with pytest.raises(RuntimeError, match="Hindsight client not available"):
        list_memories(10, 0)


# ============================================================================
# Mock Mode Tests
# ============================================================================

@patch.dict(os.environ, {"MOCK_MODE": "true"})
def test_mock_mode_recall_works():
    """Test recall works in mock mode."""
    _reset_memory_module()
    from importlib import reload

    import backend.config
    reload(backend.config)
    import backend.memory
    reload(backend.memory)
    from backend.memory import recall_memories

    result = recall_memories("connection pool", "Backend API", 5)
    assert isinstance(result, list)
    assert len(result) > 0


@patch.dict(os.environ, {"MOCK_MODE": "true"})
def test_mock_mode_retain_works():
    """Test retain works in mock mode."""
    _reset_memory_module()
    from importlib import reload

    import backend.config
    reload(backend.config)
    import backend.memory
    reload(backend.memory)
    from backend.memory import retain_memory

    result = retain_memory(
        incident_id="INC-999",
        service_name="Test Service",
        symptom="Test symptom",
        verified_root_cause="Test cause",
        verified_resolution="Test resolution"
    )
    assert result is not None
    assert result.startswith("mem_mock_")


@patch.dict(os.environ, {"MOCK_MODE": "true"})
def test_mock_mode_reflect_works():
    """Test reflect works in mock mode."""
    _reset_memory_module()
    from importlib import reload

    import backend.config
    reload(backend.config)
    import backend.memory
    reload(backend.memory)
    from backend.memory import reflect_patterns

    result = reflect_patterns(5)
    assert isinstance(result, list)
    assert len(result) > 0


@patch.dict(os.environ, {"MOCK_MODE": "true"})
def test_mock_mode_list_works():
    """Test list_memories works in mock mode."""
    _reset_memory_module()
    from importlib import reload

    import backend.config
    reload(backend.config)
    import backend.memory
    reload(backend.memory)
    from backend.memory import list_memories

    result = list_memories(10, 0)
    assert isinstance(result, list)
    assert len(result) > 0


# ============================================================================
# Hindsight Client Error Handling Tests (Mock Mode)
# ============================================================================

@patch.dict(os.environ, {"MOCK_MODE": "true"})
@patch("backend.memory._get_hindsight_client")
def test_recall_memories_hindsight_error_uses_mock(mock_client):
    """Test recall uses mock on Hindsight errors when in mock mode."""
    _reset_memory_module()
    mock_bank = MagicMock()
    mock_bank.recall.side_effect = Exception("Hindsight API error")
    mock_client.return_value = MagicMock()
    mock_client.return_value.bank.return_value = mock_bank

    from importlib import reload

    import backend.config
    reload(backend.config)
    import backend.memory
    reload(backend.memory)
    from backend.memory import recall_memories

    result = recall_memories("test query", "Test Service", 5)
    assert isinstance(result, list)


@patch.dict(os.environ, {"MOCK_MODE": "true"})
@patch("backend.memory._get_hindsight_client")
def test_retain_memory_hindsight_error_uses_mock(mock_client):
    """Test retain uses mock on Hindsight errors when in mock mode."""
    _reset_memory_module()
    mock_bank = MagicMock()
    mock_bank.add.side_effect = Exception("Hindsight API error")
    mock_client.return_value = MagicMock()
    mock_client.return_value.bank.return_value = mock_bank

    from importlib import reload

    import backend.config
    reload(backend.config)
    import backend.memory
    reload(backend.memory)
    from backend.memory import retain_memory

    result = retain_memory(
        incident_id="INC-999",
        service_name="Test Service",
        symptom="Test symptom",
        verified_root_cause="Test cause",
        verified_resolution="Test resolution"
    )
    assert result is not None
    assert result.startswith("mem_mock_")


# ============================================================================
# Parse Functions Tests
# ============================================================================

def test_parse_hindsight_result_with_metadata():
    """Test parsing Hindsight result with metadata."""
    item = {
        "content": "test content",
        "metadata": {
            "incident_id": "INC-123",
            "service_name": "Test Service",
            "symptom": "Test symptom",
            "verified_root_cause": "Test cause",
            "verified_resolution": "Test resolution"
        },
        "score": 0.95
    }

    result = _parse_hindsight_result(item)

    assert result is not None
    assert result.incident_id == "INC-123"
    assert result.service_name == "Test Service"
    assert result.symptom == "Test symptom"
    assert result.root_cause == "Test cause"
    assert result.resolution == "Test resolution"
    assert result.similarity_score == 0.95


def test_parse_hindsight_result_without_metadata():
    """Test parsing Hindsight result without metadata (falls back to content parsing)."""
    item = {
        "content": "Incident: INC-456\nService: Auth Service\nSymptom: 401 errors\nVerified Root Cause: Expired token\nVerified Resolution: Refresh token",
        "metadata": {}
    }

    result = _parse_hindsight_result(item)

    assert result is not None
    assert result.incident_id == "INC-456"
    assert result.service_name == "Auth Service"
    assert result.symptom == "401 errors"
    assert result.root_cause == "Expired token"
    assert result.resolution == "Refresh token"


def test_parse_hindsight_result_invalid():
    """Test parsing invalid Hindsight result returns None for non-dict input."""
    # String input - will be converted to str and parsed, but returns a match with defaults
    result = _parse_hindsight_result("invalid string")
    # The function tries to parse even strings, so it returns a match with defaults
    assert result is not None
    assert result.incident_id.startswith("mem_")
    assert result.service_name == "Unknown"

    # None input - will fail and return None
    result = _parse_hindsight_result(None)
    assert result is None


def test_parse_hindsight_insight():
    """Test parsing Hindsight insight."""
    item = {
        "theme": "Test Theme",
        "description": "Test Description",
        "count": 5,
        "examples": ["INC-001", "INC-002"]
    }

    result = _parse_hindsight_insight(item)

    assert result is not None
    assert result.theme == "Test Theme"
    assert result.description == "Test Description"
    assert result.incident_count == 5
    assert result.example_incidents == ["INC-001", "INC-002"]


def test_parse_hindsight_insight_invalid():
    """Test parsing invalid Hindsight insight returns None."""
    result = _parse_hindsight_insight("invalid string")
    assert result is None

    result = _parse_hindsight_insight(None)
    assert result is None


# ============================================================================
# Integration Tests (require actual Hindsight)
# ============================================================================

@pytest.mark.integration
@pytest.mark.skipif(not is_hindsight_available(), reason="Hindsight not configured")
def test_recall_memories_real():
    """Integration test with real Hindsight (requires credentials)."""
    result = recall_memories("connection pool", "Backend API", 5)
    assert isinstance(result, list)


@pytest.mark.integration
@pytest.mark.skipif(not is_hindsight_available(), reason="Hindsight not configured")
def test_retain_and_recall_roundtrip():
    """Integration test: retain then recall (requires credentials)."""
    memory_id = retain_memory(
        incident_id="INC-TEST-ROUNDTRIP",
        service_name="Test Service",
        symptom="Test symptom for roundtrip",
        verified_root_cause="Test cause",
        verified_resolution="Test resolution"
    )
    assert memory_id is not None

    results = recall_memories("roundtrip", "Test Service", 5)
    assert len(results) > 0
    assert any("ROUNDTRIP" in r.incident_id for r in results)
