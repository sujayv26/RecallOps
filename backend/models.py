"""Pydantic request/response schemas - the shared API contract."""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Request/Response Models
# ============================================================================

class IncidentInput(BaseModel):
    """Input for incident analysis request."""
    service_name: str = Field(..., min_length=1, max_length=100, description="Name of the affected service")
    error_description: str = Field(..., min_length=10, max_length=5000, description="Description of the incident/error")
    log_excerpt: Optional[str] = Field(default=None, max_length=10000, description="Optional log excerpt or context")


class HistoricalMatch(BaseModel):
    """A recalled historical incident from Hindsight memory."""
    incident_id: str = Field(..., description="Unique identifier of the historical incident")
    service_name: str = Field(..., description="Service name from the historical incident")
    symptom: str = Field(..., description="Symptom/description of the historical incident")
    root_cause: str = Field(..., description="Verified root cause of the historical incident")
    resolution: str = Field(..., description="Verified resolution steps")
    similarity_score: Optional[float] = Field(default=None, description="Semantic similarity score if available")
    created_at: Optional[datetime] = Field(default=None, description="When this memory was stored")


class AnalysisResponse(BaseModel):
    """Structured analysis response from the AI agent."""
    incident_id: str = Field(..., description="Unique identifier for this analysis")
    severity: Literal["Low", "Medium", "High", "Critical"] = Field(..., description="Assessed severity level")
    likely_root_cause: str = Field(..., description="AI's hypothesized root cause")
    explanation: str = Field(..., description="Detailed explanation of the analysis")
    recommended_actions: List[str] = Field(..., min_length=1, description="Ordered list of recommended investigation/remediation steps")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model-estimated confidence (0-1), not a guarantee")
    historical_matches: List[HistoricalMatch] = Field(default_factory=list, description="Actual retrieved historical incidents from Hindsight")
    memory_influence: str = Field(default="", description="How retrieved memory influenced this analysis")
    caveats: Optional[str] = Field(default=None, description="Missing information or limitations in the analysis")
    analyzed_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of analysis")


class ResolutionInput(BaseModel):
    """Human-confirmed resolution for an incident."""
    incident_id: str = Field(..., description="The incident ID from the analysis response")
    verified_root_cause: str = Field(..., min_length=5, max_length=2000, description="Human-confirmed actual root cause")
    verified_resolution: str = Field(..., min_length=5, max_length=5000, description="Human-confirmed actual resolution steps")
    notes: Optional[str] = Field(default=None, max_length=2000, description="Additional notes from the responder")


class ResolutionResponse(BaseModel):
    """Response after storing verified resolution."""
    success: bool = Field(..., description="Whether the resolution was stored successfully")
    memory_id: Optional[str] = Field(default=None, description="Hindsight memory ID if available")
    message: str = Field(..., description="Status message")


class MemoryListItem(BaseModel):
    """Item in memory explorer list."""
    memory_id: str = Field(..., description="Unique memory identifier")
    incident_id: str = Field(..., description="Incident identifier")
    service_name: str = Field(..., description="Affected service")
    symptom: str = Field(..., description="Incident symptom")
    verified_root_cause: str = Field(..., description="Confirmed root cause")
    verified_resolution: str = Field(..., description="Confirmed resolution")
    created_at: datetime = Field(..., description="When this was stored")
    is_verified: bool = Field(default=True, description="Whether this is a verified outcome")


class MemoryListResponse(BaseModel):
    """Response for memory listing."""
    memories: List[MemoryListItem] = Field(default_factory=list)
    total: int = Field(default=0)


class InsightItem(BaseModel):
    """A recurring pattern or theme from Hindsight reflection."""
    theme: str = Field(..., description="Pattern/theme name")
    description: str = Field(..., description="Description of the pattern")
    incident_count: int = Field(..., description="Number of related incidents")
    example_incidents: List[str] = Field(default_factory=list, description="Example incident IDs")


class InsightsResponse(BaseModel):
    """Response for insights endpoint."""
    insights: List[InsightItem] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""
    status: Literal["healthy", "degraded", "unhealthy"] = Field(..., description="Service health status")
    version: str = Field(default="0.1.0", description="Application version")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    dependencies: dict = Field(default_factory=dict, description="Status of external dependencies")


# ============================================================================
# Internal Models (for agent/memory layer)
# ============================================================================

class AgentAnalysisInput(BaseModel):
    """Internal input to the agent analysis function."""
    incident: IncidentInput
    historical_context: List[HistoricalMatch]


class AgentAnalysisOutput(BaseModel):
    """Internal output from the agent analysis function."""
    severity: Literal["Low", "Medium", "High", "Critical"]
    likely_root_cause: str
    explanation: str
    recommended_actions: List[str]
    confidence: float
    memory_influence: str
    caveats: Optional[str] = None


# ============================================================================
# Configuration for API documentation
# ============================================================================

# Example values for OpenAPI docs
INCIDENT_INPUT_EXAMPLE = {
    "service_name": "Backend API",
    "error_description": "Intermittent HTTP 500 errors on /api/users endpoint, ~15% error rate over last 10 minutes",
    "log_excerpt": "2026-11-07 10:15:23 ERROR [pool-2-thread-1] HikariPool-1 - Connection is not available, request timed out after 30000ms\n2026-11-07 10:15:24 ERROR [http-nio-8080-exec-5] SQLException: Connection is not available"
}

ANALYSIS_RESPONSE_EXAMPLE = {
    "incident_id": "inc_abc123",
    "severity": "High",
    "likely_root_cause": "Database connection pool exhausted due to connection leak in user service",
    "explanation": "The error logs show HikariCP connection timeout. Historical incident INC-001 had identical symptoms - connection pool exhaustion from unclosed connections in the user service module.",
    "recommended_actions": [
        "Check current connection pool usage via HikariCP metrics",
        "Review user service code for unclosed database connections",
        "Increase connection pool size as temporary mitigation",
        "Deploy fix for connection leak"
    ],
    "confidence": 0.87,
    "historical_matches": [
        {
            "incident_id": "INC-001",
            "service_name": "Backend API",
            "symptom": "HTTP 500 errors",
            "root_cause": "Database connection pool exhausted",
            "resolution": "Increase/configure pool capacity; investigate connection usage.",
            "similarity_score": 0.92
        }
    ],
    "memory_influence": "Historical match INC-001 (92% similarity) directly informed the likely root cause and recommended actions.",
    "caveats": "Log excerpt limited to 2 minutes; full timeline needed to confirm leak pattern.",
    "analyzed_at": "2026-11-07T10:20:00Z"
}

RESOLUTION_INPUT_EXAMPLE = {
    "incident_id": "inc_abc123",
    "verified_root_cause": "Connection leak in UserService.getUserProfile() - missing try-with-resources",
    "verified_resolution": "Added try-with-resources to database connection handling in UserService. Increased pool size from 20 to 50 as safety margin. Deployed fix in v2.3.1.",
    "notes": "Confirmed via code review and load test. Error rate dropped to 0% post-deploy."
}