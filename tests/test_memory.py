"""Tests for memory module - Hindsight integration."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from backend.memory import (
    recall_memories,
    retain_memory,
    reflect_patterns,
    list_memories,
    is_hindsight_available,
    _mock_recall,
    _mock_retain,
    _mock_reflect,
    _mock_list_memories,
)
from backend.models import HistoricalMatch, InsightItem, IncidentInput


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
    """Test mock recall with no matches."""
    result = _mock_recall("unrelated query", None, 5)
    assert result == []


def test_mock_recall_with_service_match():
    """Test mock recall matches service name."""
    result = _mock_recall("backend api error", "Backend API", 5)
    assert len(result) > 0
    for match in result:
        assert match.service_name == "Backend API"


def test_mock_recall_with_symptom_match():
    """Test mock recall matches symptom keywords."""
    result = _mock_recall("connection pool exhausted", None, 5)
    assert len(result) > 0
    # Should match INC-001 (pool exhausted) or INC-005 (memory exhaustion)
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
    assert memory_id.startswith("mem_")
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
    # Different pages should have different items
    ids1 = {m.incident_id for m in page1}
    ids2 = {m.incident_id for m in page2}
    assert ids1.isdisjoint(ids2)


# ============================================================================
# Real Hindsight Integration Tests (Mocked)
# ============================================================================

@patch("backend.memory._get_hindsight_client")
def test_recall_memories_hindsight_unavailable(mock_client):
    """Test recall falls back to mock when Hindsight unavailable."""
    mock_client.return_value = None

    result = recall_memories("test query", "Test Service", 5)

    assert isinstance(result, list)
    # Should use mock implementation


@patch("backend.memory._get_hindsight_client")
def test_retain_memory_hindsight_unavailable(mock_client):
    """Test retain falls back to mock when Hindsight unavailable."""
    mock_client.return_value = None

    result = retain_memory(
        incident_id="INC-999",
        service_name="Test Service",
        symptom="Test symptom",
        verified_root_cause="Test cause",
        verified_resolution="Test resolution"
    )

    assert result is not None
    assert result.startswith("mem_")


@patch("backend.memory._get_hindsight_client")
def test_reflect_patterns_hindsight_unavailable(mock_client):
    """Test reflect falls back to mock when Hindsight unavailable."""
    mock_client.return_value = None

    result = reflect_patterns(5)

    assert isinstance(result, list)
    assert len(result) > 0


@patch("backend.memory._get_hindsight_client")
def test_list_memories_hindsight_unavailable(mock_client):
    """Test list_memories falls back to mock when Hindsight unavailable."""
    mock_client.return_value = None

    result = list_memories(10, 0)

    assert isinstance(result, list)
    assert len(result) > 0


# ============================================================================
# Hindsight Client Error Handling Tests
# ============================================================================

@patch("backend.memory._get_hindsight_client")
def test_recall_memories_hindsight_error(mock_client):
    """Test recall handles Hindsight errors gracefully."""
    mock_bank = MagicMock()
    mock_bank.recall.side_effect = Exception("Hindsight API error")
    mock_client.return_value = MagicMock()
    mock_client.return_value.bank.return_value = mock_bank

    result = recall_memories("test query", "Test Service", 5)

    # Should fall back to mock and not raise
    assert isinstance(result, list)


@patch("backend.memory._get_hindsight_client")
def test_retain_memory_hindsight_error(mock_client):
    """Test retain handles Hindsight errors gracefully."""
    mock_bank = MagicMock()
    mock_bank.add.side_effect = Exception("Hindsight API error")
    mock_client.return_value = MagicMock()
    mock_client.return_value.bank.return_value = mock_bank

    result = retain_memory(
        incident_id="INC-999",
        service_name="Test Service",
        symptom="Test symptom",
        verified_root_cause="Test cause",
        verified_resolution="Test resolution"
    )

    # Should return None on error, not raise
    assert result is None


# ============================================================================
# Parse Functions Tests
# ============================================================================

def test_parse_hindsight_result_with_metadata():
    """Test parsing Hindsight result with metadata."""
    from backend.memory import _parse_hindsight_result

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
    from backend.memory import _parse_hindsight_result

    item = {
        "content": "Incident: INC-456\nService: Auth Service\nSymptom: 401 errors\nVerified Root Cause: Expired token\nVerified Resolution: Refresh token",
        "metadata": {}
    }

    result = _parse_hindsight_result(item)

    assert result is not None
    assert result.incident_id == "INC-456"
    assert result.service_name == "Auth Service"


def test_parse_hindsight_result_invalid():
    """Test parsing invalid Hindsight result returns None."""
    from backend.memory import _parse_hindsight_result

    result = _parse_hindsight_result("invalid string")
    assert result is None

    result = _parse_hindsight_result(None)
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
    # Retain a test memory
    memory_id = retain_memory(
        incident_id="INC-TEST-ROUNDTRIP",
        service_name="Test Service",
        symptom="Test symptom for roundtrip",
        verified_root_cause="Test cause",
        verified_resolution="Test resolution"
    )
    assert memory_id is not None

    # Recall it
    results = recall_memories("roundtrip", "Test Service", 5)
    assert len(results) > 0
    assert any("ROUNDTRIP" in r.incident_id for r in results)