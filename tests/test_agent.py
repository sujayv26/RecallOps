"""Tests for agent module - Groq integration and prompt handling."""

import os
from unittest.mock import MagicMock, patch

import pytest

from backend.agent import (
    _build_user_prompt,
    _format_historical_context,
    _mock_analysis,
    analyze_incident,
    is_groq_available,
)
from backend.models import AgentAnalysisOutput, HistoricalMatch, IncidentInput

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_incident():
    return IncidentInput(
        service_name="Backend API",
        error_description="HTTP 500 errors on /api/users endpoint",
        log_excerpt="ERROR: Connection pool exhausted"
    )


@pytest.fixture
def sample_matches():
    return [
        HistoricalMatch(
            incident_id="INC-001",
            service_name="Backend API",
            symptom="HTTP 500 errors",
            root_cause="Database connection pool exhausted",
            resolution="Increase pool size; fix connection leak",
            similarity_score=0.92
        )
    ]


# ============================================================================
# Format Historical Context Tests
# ============================================================================

def test_format_historical_context_empty():
    """Test formatting with no historical matches."""
    result = _format_historical_context([])
    assert "No relevant historical incidents found" in result


def test_format_historical_context_with_matches(sample_matches):
    """Test formatting with historical matches."""
    result = _format_historical_context(sample_matches)
    assert "INC-001" in result
    assert "Backend API" in result
    assert "Database connection pool exhausted" in result
    assert "92%" in result or "0.92" in result


# ============================================================================
# Build User Prompt Tests
# ============================================================================

def test_build_user_prompt_with_logs(sample_incident, sample_matches):
    """Test prompt building with log excerpt."""
    prompt = _build_user_prompt(sample_incident, sample_matches)
    assert "Backend API" in prompt
    assert "HTTP 500 errors" in prompt
    assert "Connection pool exhausted" in prompt
    assert "Log Excerpt:" in prompt
    assert "ERROR: Connection pool exhausted" in prompt


def test_build_user_prompt_without_logs(sample_matches):
    """Test prompt building without log excerpt."""
    incident = IncidentInput(
        service_name="Auth Service",
        error_description="401 errors",
        log_excerpt=None
    )
    prompt = _build_user_prompt(incident, sample_matches)
    assert "Auth Service" in prompt
    assert "Log Excerpt: (none provided)" in prompt


# ============================================================================
# Mock Analysis Tests
# ============================================================================

def test_mock_analysis_with_memory(sample_incident, sample_matches):
    """Test mock analysis when historical matches exist."""
    result = _mock_analysis(sample_incident, sample_matches)

    assert isinstance(result, AgentAnalysisOutput)
    assert result.severity in ["Low", "Medium", "High", "Critical"]
    assert "INC-001" in result.likely_root_cause
    assert result.confidence > 0.8
    assert "Historical match" in result.memory_influence
    assert result.caveats is None


def test_mock_analysis_without_memory(sample_incident):
    """Test mock analysis when no historical matches exist."""
    result = _mock_analysis(sample_incident, [])

    assert isinstance(result, AgentAnalysisOutput)
    assert result.confidence < 0.7
    assert "No relevant historical incidents found" in result.memory_influence
    assert result.caveats is not None


def test_mock_analysis_database_keywords():
    """Test mock analysis detects database-related keywords."""
    incident = IncidentInput(
        service_name="Database",
        error_description="Connection timeout and pool exhausted",
        log_excerpt=None
    )
    result = _mock_analysis(incident, [])
    assert "connection" in result.likely_root_cause.lower() or "pool" in result.likely_root_cause.lower()


# ============================================================================
# Groq Availability Tests
# ============================================================================

@patch("backend.agent._get_groq_client")
def test_is_groq_available_true(mock_client):
    """Test Groq availability when client works."""
    mock_client.return_value = MagicMock()
    assert is_groq_available() is True


@patch("backend.agent._get_groq_client")
def test_is_groq_available_false(mock_client):
    """Test Groq availability when client fails."""
    mock_client.return_value = None
    assert is_groq_available() is False


# ============================================================================
# Mock Mode Tests (with proper cache invalidation)
# ============================================================================

def _reset_agent_module():
    """Reset the agent module's global state."""
    from importlib import reload

    import backend.agent
    import backend.config

    # Reload config first to pick up new env vars
    reload(backend.config)
    # Clear settings cache
    backend.config.get_settings.cache_clear()

    # Reload agent to pick up new settings
    reload(backend.agent)

    # Reset agent state
    backend.agent._groq_client = None
    backend.agent._groq_initialized = False


@patch.dict(os.environ, {"MOCK_MODE": "true"})
def test_analyze_incident_mock_mode(sample_incident, sample_matches):
    """Test analyze_incident uses mock when MOCK_MODE=true."""
    _reset_agent_module()

    result = analyze_incident(sample_incident, sample_matches)

    assert isinstance(result, AgentAnalysisOutput)
    assert "INC-001" in result.likely_root_cause


@patch.dict(os.environ, {"MOCK_MODE": "true"})
def test_mock_mode_enabled(sample_incident, sample_matches):
    """Test that mock mode works when enabled via env."""
    _reset_agent_module()

    result = analyze_incident(sample_incident, sample_matches)
    assert isinstance(result, AgentAnalysisOutput)


@patch.dict(os.environ, {"MOCK_MODE": "false"})
def test_mock_mode_disabled_requires_groq(sample_incident, sample_matches):
    """Test that mock mode disabled requires real Groq."""
    _reset_agent_module()
    from importlib import reload

    import backend.config
    reload(backend.config)
    from backend.config import settings

    assert settings.mock_mode is False

    # Should raise because no real Groq client (invalid API key)
    with pytest.raises(RuntimeError):
        analyze_incident(sample_incident, sample_matches)


# ============================================================================
# Integration-style Tests (require actual Groq)
# ============================================================================

@pytest.mark.integration
@pytest.mark.skipif(True, reason="Requires real Groq credentials")
def test_analyze_incident_real_groq(sample_incident, sample_matches):
    """Integration test with real Groq API (requires credentials)."""
    result = analyze_incident(sample_incident, sample_matches)

    assert isinstance(result, AgentAnalysisOutput)
    assert result.severity in ["Low", "Medium", "High", "Critical"]
    assert 0 <= result.confidence <= 1
    assert len(result.recommended_actions) > 0
