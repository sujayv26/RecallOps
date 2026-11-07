"""Groq LLM integration - the ONLY file that talks to Groq.

Handles prompt construction, structured output parsing, and error handling.

IMPORTANT: Mock mode is EXPLICITLY controlled by MOCK_MODE environment variable.
Never silently fall back to mock - fail loudly if Groq is unavailable and not in mock mode.
"""

import json

from pydantic import ValidationError

from backend.config import settings
from backend.models import (
    AgentAnalysisOutput,
    HistoricalMatch,
    IncidentInput,
)

# ============================================================================
# Groq Client Setup
# ============================================================================

_groq_client = None
_groq_initialized = False


def _get_groq_client():
    """Get or create the Groq client.

    Raises:
        RuntimeError: If Groq is not configured and not in mock mode.
    """
    global _groq_client, _groq_initialized

    if _groq_initialized:
        return _groq_client

    _groq_initialized = True

    # In mock mode, return None to signal mock implementations should be used
    if settings.mock_mode:
        _groq_client = None
        return None

    try:
        from groq import Groq  # type: ignore

        _groq_client = Groq(api_key=settings.groq_api_key)
        return _groq_client

    except ImportError as e:
        raise RuntimeError(
            "Groq SDK not installed. Install with: pip install groq "
            "or set MOCK_MODE=true for development without Groq."
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to initialize Groq client: {e}. "
            f"Check GROQ_API_KEY and GROQ_MODEL. "
            f"Or set MOCK_MODE=true for development."
        ) from e


def is_groq_available() -> bool:
    """Check if Groq is configured and available (not in mock mode)."""
    if settings.mock_mode:
        return False
    try:
        client = _get_groq_client()
        return client is not None
    except RuntimeError:
        return False


# ============================================================================
# Prompt Templates
# ============================================================================

SYSTEM_PROMPT = """You are RecallOps, an AI-assisted incident response agent for SRE and DevOps teams.

Your role: Analyze the current incident using the provided historical context from team memory, and produce a structured troubleshooting assessment.

CRITICAL RULES:
1. You are ADVISORY ONLY. Never recommend running commands, restarting services, or making production changes directly.
2. Clearly distinguish between HISTORICAL FACTS (retrieved from memory) and YOUR HYPOTHESES (current analysis).
3. If historical matches exist, explain HOW they influence your assessment.
4. If no relevant history exists, state this clearly and provide a generic analysis.
5. Your confidence score is an ESTIMATE, not a guarantee.
6. Output MUST conform to the specified JSON schema exactly.

OUTPUT FORMAT (JSON only, no extra text):
{
  "severity": "Low|Medium|High|Critical",
  "likely_root_cause": "string",
  "explanation": "string",
  "recommended_actions": ["string", ...],
  "confidence": 0.0-1.0,
  "memory_influence": "string",
  "caveats": "string or null"
}"""

USER_PROMPT_TEMPLATE = """INCIDENT DETAILS:
Service: {service_name}
Error Description: {error_description}
{log_section}

HISTORICAL CONTEXT (from team memory):
{historical_context}

TASK: Analyze this incident and produce a structured assessment following the output schema.

Consider:
- Does the historical context contain relevant similar incidents?
- How do the symptoms compare to past incidents?
- What investigation steps would be most efficient given past learnings?
- What is your confidence level and why?

Remember: Historical matches are VERIFIED FACTS. Your analysis is a HYPOTHESIS."""


def _format_historical_context(matches: list[HistoricalMatch]) -> str:
    """Format historical matches for the prompt."""
    if not matches:
        return "No relevant historical incidents found in team memory."

    lines = [f"Found {len(matches)} relevant historical incident(s):\n"]
    for i, match in enumerate(matches, 1):
        score_str = f" (similarity: {match.similarity_score:.0%})" if match.similarity_score else ""
        lines.append(f"{i}. Incident {match.incident_id}{score_str}")
        lines.append(f"   Service: {match.service_name}")
        lines.append(f"   Symptom: {match.symptom}")
        lines.append(f"   Verified Root Cause: {match.root_cause}")
        lines.append(f"   Verified Resolution: {match.resolution}")
        lines.append("")

    return "\n".join(lines)


def _build_user_prompt(incident: IncidentInput, matches: list[HistoricalMatch]) -> str:
    """Build the user prompt with incident details and historical context."""
    log_section = f"Log Excerpt:\n{incident.log_excerpt}\n" if incident.log_excerpt else "Log Excerpt: (none provided)\n"
    historical_context = _format_historical_context(matches)

    return USER_PROMPT_TEMPLATE.format(
        service_name=incident.service_name,
        error_description=incident.error_description,
        log_section=log_section,
        historical_context=historical_context
    )


# ============================================================================
# Analysis Function
# ============================================================================

def analyze_incident(
    incident: IncidentInput,
    historical_matches: list[HistoricalMatch]
) -> AgentAnalysisOutput:
    """
    Analyze an incident using Groq LLM with historical context.

    Args:
        incident: The incident to analyze
        historical_matches: Retrieved historical incidents from Hindsight

    Returns:
        Structured analysis output

    Raises:
        RuntimeError: If Groq is unavailable and not in mock mode, or response parsing fails
    """
    client = _get_groq_client()

    if client is None:
        if settings.mock_mode:
            return _mock_analysis(incident, historical_matches)
        raise RuntimeError("Groq client not available and MOCK_MODE=false")

    user_prompt = _build_user_prompt(incident, historical_matches)

    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Empty response from Groq")

        parsed = json.loads(content)
        return AgentAnalysisOutput(**parsed)

    except json.JSONDecodeError as e:
        raise RuntimeError(f"Groq returned invalid JSON: {e}") from e

    except ValidationError as e:
        raise RuntimeError(f"Groq response failed schema validation: {e}") from e

    except Exception as e:
        raise RuntimeError(f"Groq API error: {e}") from e


# ============================================================================
# Mock Analysis - ONLY used when MOCK_MODE=true
# ============================================================================

def _mock_analysis(
    incident: IncidentInput,
    historical_matches: list[HistoricalMatch]
) -> AgentAnalysisOutput:
    """Generate a mock analysis for demo purposes.

    ONLY called when MOCK_MODE=true. Clearly labeled as mock data.
    """
    incident.service_name.lower()
    error_desc = incident.error_description.lower()

    if any(kw in error_desc for kw in ["critical", "down", "outage", "500", "503", "timeout"]):
        severity = "High"
    elif any(kw in error_desc for kw in ["slow", "degraded", "latency", "401", "403"]):
        severity = "Medium"
    else:
        severity = "Low"

    has_memory = len(historical_matches) > 0
    top_match = historical_matches[0] if historical_matches else None

    if has_memory and top_match:
        likely_cause = f"Similar to {top_match.incident_id}: {top_match.root_cause}"
        explanation = (
            f"This incident closely matches historical incident {top_match.incident_id} "
            f"({top_match.similarity_score:.0%} similarity). The symptoms and service align "
            f"with the verified root cause: {top_match.root_cause}. "
            f"Previous resolution: {top_match.resolution}"
        )
        memory_influence = (
            f"Historical match {top_match.incident_id} directly informs the likely root cause "
            f"and recommended actions. The verified resolution from that incident provides "
            f"a proven investigation path."
        )
        confidence = 0.85
        actions = [
            f"Verify if {top_match.root_cause.lower()} applies to current incident",
            f"Apply resolution pattern: {top_match.resolution}",
            "Monitor for similar symptoms in related services",
            "Document any differences from historical incident for future learning"
        ]
    else:
        if "database" in error_desc or "connection" in error_desc or "pool" in error_desc:
            likely_cause = "Database connection pool exhaustion or connection leak"
            actions = [
                "Check database connection pool metrics (active/idle connections)",
                "Review application code for unclosed database connections",
                "Increase connection pool size as temporary mitigation",
                "Enable connection leak detection in pool configuration"
            ]
        elif "timeout" in error_desc:
            likely_cause = "Upstream service timeout or network latency"
            actions = [
                "Check upstream service health and latency metrics",
                "Review timeout configurations in service mesh/client",
                "Implement circuit breaker pattern for resilience",
                "Investigate network connectivity issues"
            ]
        elif "auth" in error_desc or "401" in error_desc or "token" in error_desc:
            likely_cause = "Authentication token expiration or misconfiguration"
            actions = [
                "Verify token expiration and refresh logic",
                "Check authentication service availability",
                "Review token configuration (issuer, audience, keys)",
                "Test authentication flow end-to-end"
            ]
        elif "memory" in error_desc or "oom" in error_desc or "503" in error_desc:
            likely_cause = "Memory exhaustion or resource starvation"
            actions = [
                "Check memory usage and garbage collection metrics",
                "Review for memory leaks in application code",
                "Increase memory limits or add replica pods",
                "Profile heap usage to identify leak sources"
            ]
        else:
            likely_cause = "Unknown - requires investigation"
            actions = [
                "Gather more detailed logs and metrics",
                "Check recent deployments or configuration changes",
                "Review service dependencies and health",
                "Escalate to service owner if unclear"
            ]

        explanation = (
            f"Based on the incident description for {incident.service_name}, "
            f"the symptoms suggest {likely_cause.lower()}. "
            f"No directly relevant historical incidents were found in team memory. "
            f"This analysis is based on general incident patterns."
        )
        memory_influence = "No relevant historical incidents found. Analysis based on general patterns only."
        confidence = 0.55
        caveats = "No historical memory matches found. Confidence is lower. Consider adding this incident to memory after resolution."

    return AgentAnalysisOutput(
        severity=severity,  # type: ignore
        likely_root_cause=likely_cause,
        explanation=explanation,
        recommended_actions=actions,
        confidence=confidence,
        memory_influence=memory_influence,
        caveats=caveats if not has_memory else None
    )
