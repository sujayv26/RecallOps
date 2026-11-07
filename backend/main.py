"""FastAPI application - main entry point and API routes."""

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.agent import analyze_incident, is_groq_available
from backend.config import settings
from backend.database import (
    close_db,
    create_analysis_record,
    create_resolution_record,
    get_all_resolutions,
    get_analysis_by_incident_id,
    get_resolution_by_incident_id,
    init_db,
)
from backend.memory import (
    is_hindsight_available,
    list_memories,
    recall_memories,
    reflect_patterns,
    retain_memory,
)
from backend.models import (
    AnalysisResponse,
    HealthResponse,
    HistoricalMatch,
    IncidentInput,
    InsightsResponse,
    MemoryListItem,
    MemoryListResponse,
    ResolutionInput,
    ResolutionResponse,
)

# ============================================================================
# Lifespan Handler
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    await init_db()
    # Check dependencies
    is_hindsight_available()
    is_groq_available()
    yield
    # Shutdown
    await close_db()


# ============================================================================
# FastAPI App Setup
# ============================================================================

app = FastAPI(
    title="RecallOps API",
    description="AI-assisted incident response agent with persistent memory",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Dependency Injection
# ============================================================================

def get_current_timestamp() -> str:
    return datetime.now(UTC).isoformat()


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Service health check with dependency status."""
    hindsight_status = "connected" if is_hindsight_available() else ("mock_mode" if settings.mock_mode else "unavailable")
    groq_status = "connected" if is_groq_available() else ("mock_mode" if settings.mock_mode else "unavailable")
    db_status = "connected"

    overall = "healthy"
    if hindsight_status != "connected" or groq_status != "connected":
        overall = "degraded"

    return HealthResponse(
        status=overall,  # type: ignore
        version="0.1.0",
        timestamp=datetime.now(UTC),
        dependencies={
            "hindsight": hindsight_status,
            "groq": groq_status,
            "database": db_status,
            "mock_mode": settings.mock_mode,
        }
    )


# ============================================================================
# Incident Analysis Endpoint
# ============================================================================

@app.post(
    "/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    tags=["Analysis"],
    summary="Analyze an incident with memory recall",
    description="""
    Accepts an incident description, recalls relevant historical incidents from Hindsight,
    and returns a structured AI analysis with recommendations.
    """
)
async def analyze_incident_endpoint(incident: IncidentInput):
    """
    Analyze an incident:
    1. Validate input
    2. Recall relevant memories from Hindsight
    3. Generate AI analysis with Groq
    4. Return structured response with historical matches
    """
    # Generate incident ID
    incident_id = f"inc_{uuid.uuid4().hex[:12]}"

    try:
        # Step 1: Recall memories from Hindsight
        query = f"{incident.service_name} {incident.error_description}"
        if incident.log_excerpt:
            query += f" {incident.log_excerpt[:500]}"

        historical_matches = recall_memories(
            query=query,
            service_name=incident.service_name,
            limit=5
        )

        # Step 2: Analyze with AI agent
        analysis = analyze_incident(incident, historical_matches)

        # Step 3: Build response
        response = AnalysisResponse(
            incident_id=incident_id,
            severity=analysis.severity,
            likely_root_cause=analysis.likely_root_cause,
            explanation=analysis.explanation,
            recommended_actions=analysis.recommended_actions,
            confidence=analysis.confidence,
            historical_matches=historical_matches,
            memory_influence=analysis.memory_influence,
            caveats=analysis.caveats,
        )

        # Step 4: Store analysis in local audit DB
        await create_analysis_record(
            incident_id=incident_id,
            service_name=incident.service_name,
            error_description=incident.error_description,
            log_excerpt=incident.log_excerpt,
            severity=analysis.severity,
            likely_root_cause=analysis.likely_root_cause,
            explanation=analysis.explanation,
            recommended_actions=analysis.recommended_actions,
            confidence=analysis.confidence,
            historical_matches=[m.model_dump() for m in historical_matches],
            memory_influence=analysis.memory_influence,
            caveats=analysis.caveats,
        )

        return response

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {e}"
        ) from e
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Analysis failed: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {e}"
        ) from e


# ============================================================================
# Resolution Confirmation Endpoint
# ============================================================================

@app.post(
    "/resolve",
    response_model=ResolutionResponse,
    status_code=status.HTTP_200_OK,
    tags=["Resolution"],
    summary="Confirm and store verified resolution",
    description="""
    Accepts a human-confirmed root cause and resolution for an incident.
    Only verified outcomes are retained in Hindsight memory.
    """
)
async def confirm_resolution(resolution: ResolutionInput):
    """
    Store a verified resolution:
    1. Validate the resolution input
    2. Retain in Hindsight as verified learning
    3. Store in local audit database
    4. Return confirmation
    """
    # Verify the analysis exists
    analysis = await get_analysis_by_incident_id(resolution.incident_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis for incident {resolution.incident_id} not found"
        )

    try:
        # Retain in Hindsight (only verified outcomes!)
        memory_id = retain_memory(
            incident_id=resolution.incident_id,
            service_name=analysis["service_name"],
            symptom=analysis["error_description"],
            verified_root_cause=resolution.verified_root_cause,
            verified_resolution=resolution.verified_resolution,
            metadata={
                "confidence": analysis["confidence"],
                "historical_matches_count": len(analysis["historical_matches"]),
            }
        )

        # Store in local audit DB
        await create_resolution_record(
            analysis_id=analysis["id"],
            incident_id=resolution.incident_id,
            verified_root_cause=resolution.verified_root_cause,
            verified_resolution=resolution.verified_resolution,
            notes=resolution.notes,
            memory_id=memory_id,
        )

        return ResolutionResponse(
            success=True,
            memory_id=memory_id,
            message="Verified resolution stored in team memory" if memory_id else "Resolution recorded locally (Hindsight unavailable)"
        )

    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to store resolution: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store resolution: {e}"
        ) from e


# ============================================================================
# Memory Explorer Endpoints
# ============================================================================

@app.get(
    "/memories",
    response_model=MemoryListResponse,
    tags=["Memory"],
    summary="List retained incident memories",
)
async def get_memories(limit: int = 50, offset: int = 0):
    """List verified incident memories from Hindsight and local DB."""
    try:
        # Get from Hindsight
        hindsight_memories = list_memories(limit=limit, offset=offset)

        # Get from local DB (verified resolutions)
        local_resolutions = await get_all_resolutions(limit=limit)

        # Combine and format as MemoryListItem objects
        memories = []

        # Add Hindsight memories
        for m in hindsight_memories:
            memories.append(MemoryListItem(
                memory_id=f"hindsight_{m.incident_id}",
                incident_id=m.incident_id,
                service_name=m.service_name,
                symptom=m.symptom,
                verified_root_cause=m.root_cause,
                verified_resolution=m.resolution,
                created_at=m.created_at or datetime.now(UTC),
                is_verified=True,
            ))

        # Add local resolutions
        for r in local_resolutions:
            memories.append(MemoryListItem(
                memory_id=r.get("memory_id", f"local_{r['id']}"),
                incident_id=r["incident_id"],
                service_name="Unknown",
                symptom="See analysis",
                verified_root_cause=r["verified_root_cause"],
                verified_resolution=r["verified_resolution"],
                created_at=r["created_at"],
                is_verified=True,
            ))

        return MemoryListResponse(
            memories=memories[:limit],
            total=len(memories)
        )

    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to retrieve memories: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve memories: {e}"
        ) from e


@app.get(
    "/insights",
    response_model=InsightsResponse,
    tags=["Memory"],
    summary="Get recurring patterns from memory reflection",
)
async def get_insights():
    """Get recurring themes/patterns from Hindsight reflection."""
    try:
        insights = reflect_patterns(limit=10)
        return InsightsResponse(insights=insights)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to retrieve insights: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve insights: {e}"
        ) from e


# ============================================================================
# Demo/Utility Endpoints
# ============================================================================

@app.get("/demo/analysis/{incident_id}", response_model=AnalysisResponse, tags=["Demo"])
async def get_analysis_by_id(incident_id: str):
    """Retrieve a previous analysis by incident ID (for demo comparison)."""
    analysis = await get_analysis_by_incident_id(incident_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis {incident_id} not found"
        )

    historical_matches = [
        HistoricalMatch(**m) for m in analysis["historical_matches"]
    ]

    return AnalysisResponse(
        incident_id=incident_id,
        severity=analysis["severity"],  # type: ignore
        likely_root_cause=analysis["likely_root_cause"],
        explanation=analysis["explanation"],
        recommended_actions=analysis["recommended_actions"],
        confidence=analysis["confidence"],
        historical_matches=historical_matches,
        memory_influence=analysis["memory_influence"],
        caveats=analysis["caveats"],
    )


@app.get("/demo/resolution/{incident_id}", tags=["Demo"])
async def get_resolution_by_id(incident_id: str):
    """Retrieve a verified resolution by incident ID."""
    resolution = await get_resolution_by_incident_id(incident_id)
    if not resolution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resolution for {incident_id} not found"
        )
    return resolution


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": f"Validation error: {exc}"}
    )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.environment == "development"
    )
