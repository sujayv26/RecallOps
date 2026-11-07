"""Tests for FastAPI endpoints."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app

# ============================================================================
# Test Client Fixture
# ============================================================================

@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_incident():
    """Sample incident input."""
    return {
        "service_name": "Backend API",
        "error_description": "HTTP 500 errors on /api/users endpoint",
        "log_excerpt": "ERROR: Connection pool exhausted"
    }


@pytest.fixture
def sample_resolution():
    """Sample resolution input."""
    return {
        "incident_id": "inc_test123",
        "verified_root_cause": "Connection leak in UserService",
        "verified_resolution": "Fixed leak, increased pool size",
        "notes": "Verified via load test"
    }


# ============================================================================
# Health Check Tests
# ============================================================================

def test_health_check(client):
    """Test health endpoint returns proper structure."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
    assert "dependencies" in data
    assert "timestamp" in data
    assert "mock_mode" in data["dependencies"]


# ============================================================================
# Analyze Endpoint Tests
# ============================================================================

@patch("backend.main.recall_memories")
@patch("backend.main.analyze_incident")
@patch("backend.main.create_analysis_record", new_callable=AsyncMock)
def test_analyze_incident_success(mock_create, mock_analyze, mock_recall, client, sample_incident):
    """Test successful incident analysis."""
    mock_recall.return_value = []
    mock_analyze.return_value = MagicMock(
        severity="High",
        likely_root_cause="Test cause",
        explanation="Test explanation",
        recommended_actions=["Action 1", "Action 2"],
        confidence=0.85,
        memory_influence="Test influence",
        caveats=None
    )
    mock_create.return_value = "ana_test123"

    response = client.post("/analyze", json=sample_incident)

    assert response.status_code == 200
    data = response.json()
    assert "incident_id" in data
    assert data["severity"] == "High"
    assert data["confidence"] == 0.85
    assert len(data["recommended_actions"]) == 2


def test_analyze_incident_validation_error(client):
    """Test validation error for missing required fields."""
    # Missing service_name
    response = client.post("/analyze", json={
        "error_description": "Some error"
    })
    assert response.status_code == 422

    # Missing error_description
    response = client.post("/analyze", json={
        "service_name": "Test Service"
    })
    assert response.status_code == 422


def test_analyze_incident_empty_strings(client):
    """Test validation error for empty strings."""
    response = client.post("/analyze", json={
        "service_name": "",
        "error_description": "Valid description"
    })
    assert response.status_code == 422


@patch("backend.main.recall_memories")
@patch("backend.main.analyze_incident")
def test_analyze_incident_groq_error(mock_analyze, mock_recall, client, sample_incident):
    """Test handling of Groq API errors."""
    mock_recall.return_value = []
    mock_analyze.side_effect = RuntimeError("Groq API error")

    response = client.post("/analyze", json=sample_incident)

    assert response.status_code == 502
    assert "Analysis failed" in response.json()["detail"]


# ============================================================================
# Resolve Endpoint Tests
# ============================================================================

@patch("backend.main.get_analysis_by_incident_id", new_callable=AsyncMock)
@patch("backend.main.retain_memory")
@patch("backend.main.create_resolution_record", new_callable=AsyncMock)
def test_confirm_resolution_success(mock_create_res, mock_retain, mock_get_analysis, client, sample_resolution):
    """Test successful resolution confirmation."""
    mock_get_analysis.return_value = {
        "id": "ana_test123",
        "service_name": "Backend API",
        "error_description": "HTTP 500 errors",
        "confidence": 0.85,
        "historical_matches": []
    }
    mock_retain.return_value = "mem_test123"
    mock_create_res.return_value = "res_test123"

    response = client.post("/resolve", json=sample_resolution)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["memory_id"] == "mem_test123"
    assert "stored" in data["message"].lower()


def test_confirm_resolution_missing_analysis(client, sample_resolution):
    """Test resolution for non-existent analysis."""
    with patch("backend.main.get_analysis_by_incident_id", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        response = client.post("/resolve", json=sample_resolution)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_confirm_resolution_validation_error(client):
    """Test validation error for missing resolution fields."""
    response = client.post("/resolve", json={
        "incident_id": "inc_test123",
        "verified_root_cause": "Cause",
        # Missing verified_resolution
    })
    assert response.status_code == 422


# ============================================================================
# Memory Explorer Tests
# ============================================================================

@patch("backend.main.list_memories")
@patch("backend.main.get_all_resolutions", new_callable=AsyncMock)
def test_get_memories(mock_get_res, mock_list_mem, client):
    """Test memory listing endpoint."""

    from backend.models import HistoricalMatch

    mock_list_mem.return_value = [
        HistoricalMatch(
            incident_id="INC-001",
            service_name="Backend API",
            symptom="HTTP 500",
            root_cause="Pool exhausted",
            resolution="Fixed leak",
            similarity_score=0.9
        )
    ]
    mock_get_res.return_value = []

    response = client.get("/memories")

    assert response.status_code == 200
    data = response.json()
    assert "memories" in data
    assert "total" in data


@patch("backend.main.reflect_patterns")
def test_get_insights(mock_reflect, client):
    """Test insights endpoint."""
    from backend.models import InsightItem

    mock_reflect.return_value = [
        InsightItem(
            theme="Connection Pool Issues",
            description="Multiple pool exhaustion incidents",
            incident_count=3,
            example_incidents=["INC-001", "INC-005"]
        )
    ]

    response = client.get("/insights")

    assert response.status_code == 200
    data = response.json()
    assert "insights" in data
    assert len(data["insights"]) == 1
    assert data["insights"][0]["theme"] == "Connection Pool Issues"


# ============================================================================
# Demo Endpoints Tests
# ============================================================================

@patch("backend.main.get_analysis_by_incident_id", new_callable=AsyncMock)
def test_get_analysis_by_id(mock_get, client):
    """Test retrieving analysis by ID."""
    mock_get.return_value = {
        "id": "ana_test123",
        "incident_id": "inc_test123",
        "service_name": "Backend API",
        "error_description": "HTTP 500",
        "log_excerpt": None,
        "severity": "High",
        "likely_root_cause": "Pool exhausted",
        "explanation": "Connection pool issue",
        "recommended_actions": ["Fix leak"],
        "confidence": 0.85,
        "historical_matches": [],
        "memory_influence": "None",
        "caveats": None,
        "created_at": "2026-11-07T10:00:00"
    }

    response = client.get("/demo/analysis/inc_test123")

    assert response.status_code == 200
    data = response.json()
    assert data["incident_id"] == "inc_test123"
    assert data["severity"] == "High"


@patch("backend.main.get_analysis_by_incident_id", new_callable=AsyncMock)
def test_get_analysis_by_id_not_found(mock_get, client):
    """Test 404 for non-existent analysis."""
    mock_get.return_value = None

    response = client.get("/demo/analysis/inc_nonexistent")

    assert response.status_code == 404


# ============================================================================
# Input Validation Tests
# ============================================================================

@pytest.mark.parametrize("payload,expected_status", [
    ({"service_name": "Backend API", "error_description": "Valid error description"}, 200),  # Minimal valid
    ({"service_name": "A" * 101, "error_description": "B"}, 422),  # service_name too long
    ({"service_name": "A", "error_description": "B" * 5001}, 422),  # error_description too long
    ({"service_name": "A", "error_description": "B", "log_excerpt": "C" * 10001}, 422),  # log_excerpt too long
])
@patch("backend.main.recall_memories")
@patch("backend.main.analyze_incident")
@patch("backend.main.create_analysis_record", new_callable=AsyncMock)
def test_input_validation(mock_create, mock_analyze, mock_recall, client, payload, expected_status):
    """Test various input validation scenarios."""
    mock_recall.return_value = []
    mock_analyze.return_value = MagicMock(
        severity="High",
        likely_root_cause="Test cause",
        explanation="Test explanation",
        recommended_actions=["Action 1"],
        confidence=0.85,
        memory_influence="Test influence",
        caveats=None
    )
    mock_create.return_value = "ana_test123"

    response = client.post("/analyze", json=payload)
    assert response.status_code == expected_status


# ============================================================================
# Mock Mode Tests
# ============================================================================

@patch.dict(os.environ, {"MOCK_MODE": "true"})
def test_health_check_shows_mock_mode():
    """Test health check shows mock_mode=true when enabled."""
    from importlib import reload

    import backend.config
    reload(backend.config)
    import backend.main
    reload(backend.main)
    from fastapi.testclient import TestClient

    test_client = TestClient(backend.main.app)
    response = test_client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["dependencies"]["mock_mode"] is True
