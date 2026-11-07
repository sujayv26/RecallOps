"""PostgreSQL audit history for local demo metadata.

This is NOT a replacement for Hindsight. It provides a local audit trail
of analyses and resolutions for demo purposes.
Uses async SQLAlchemy with asyncpg driver.
"""

import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

# mypy: disable-error-code="valid-type,no-any-return,misc"
from sqlalchemy import Column, DateTime, Index, String, Text, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import settings

# ============================================================================
# Database Setup
# ============================================================================

# Convert postgresql:// to postgresql+asyncpg:// for async engine
def _get_async_database_url() -> str:
    url = settings.database_url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    raise ValueError(
        f"DATABASE_URL must be a PostgreSQL URL (postgresql://...), got: {url}"
    )


# Async engine for FastAPI
async_engine = create_async_engine(
    _get_async_database_url(),
    echo=settings.environment == "development",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Sync engine for Alembic migrations
sync_engine = create_engine(
    settings.database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if settings.database_url.startswith("postgresql://")
    else settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)  # type: ignore[valid-type,assignment]

Base = declarative_base()  # type: ignore[misc,valid-type]


# ============================================================================
# Models
# ============================================================================

class AnalysisRecord(Base):
    """Audit record for incident analysis."""
    __tablename__ = "analyses"

    id = Column(String(32), primary_key=True)
    incident_id = Column(String(32), nullable=False, index=True)
    service_name = Column(String(100), nullable=False)
    error_description = Column(Text, nullable=False)
    log_excerpt = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False)
    likely_root_cause = Column(Text, nullable=False)
    explanation = Column(Text, nullable=False)
    recommended_actions = Column(Text, nullable=False)  # JSON array
    confidence = Column(String(20), nullable=False)
    historical_matches = Column(Text, nullable=False)  # JSON array
    memory_influence = Column(Text, nullable=True)
    caveats = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "service_name": self.service_name,
            "error_description": self.error_description,
            "log_excerpt": self.log_excerpt,
            "severity": self.severity,
            "likely_root_cause": self.likely_root_cause,
            "explanation": self.explanation,
            "recommended_actions": json.loads(self.recommended_actions),
            "confidence": float(self.confidence),
            "historical_matches": json.loads(self.historical_matches),
            "memory_influence": self.memory_influence,
            "caveats": self.caveats,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ResolutionRecord(Base):
    """Audit record for verified resolution."""
    __tablename__ = "resolutions"

    id = Column(String(32), primary_key=True)
    analysis_id = Column(String(32), nullable=False, index=True)
    incident_id = Column(String(32), nullable=False, index=True)
    verified_root_cause = Column(Text, nullable=False)
    verified_resolution = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)
    memory_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "incident_id": self.incident_id,
            "verified_root_cause": self.verified_root_cause,
            "verified_resolution": self.verified_resolution,
            "notes": self.notes,
            "memory_id": self.memory_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Indexes
Index("idx_analyses_incident_id", AnalysisRecord.incident_id)
Index("idx_analyses_created_at", AnalysisRecord.created_at)
Index("idx_resolutions_incident_id", ResolutionRecord.incident_id)
Index("idx_resolutions_analysis_id", ResolutionRecord.analysis_id)


# ============================================================================
# Database Operations
# ============================================================================

async def init_db() -> None:
    """Initialize database tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await async_engine.dispose()


@asynccontextmanager
async def get_async_session() -> AsyncSession:
    """Get async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_session() -> SessionLocal:  # type: ignore[return-value]
    """Get sync database session (for Alembic/migrations)."""
    return SessionLocal()


# ============================================================================
# Analysis CRUD (Async)
# ============================================================================

async def create_analysis_record(
    incident_id: str,
    service_name: str,
    error_description: str,
    log_excerpt: str | None,
    severity: str,
    likely_root_cause: str,
    explanation: str,
    recommended_actions: list[str],
    confidence: float,
    historical_matches: list[dict[str, Any]],
    memory_influence: str,
    caveats: str | None
) -> str:
    """Store an analysis record. Returns the analysis ID."""
    analysis_id = f"ana_{uuid.uuid4().hex[:12]}"
    created_at = datetime.utcnow()

    record = AnalysisRecord(
        id=analysis_id,
        incident_id=incident_id,
        service_name=service_name,
        error_description=error_description,
        log_excerpt=log_excerpt,
        severity=severity,
        likely_root_cause=likely_root_cause,
        explanation=explanation,
        recommended_actions=json.dumps(recommended_actions),
        confidence=str(confidence),
        historical_matches=json.dumps(historical_matches),
        memory_influence=memory_influence,
        caveats=caveats,
        created_at=created_at,
    )

    async with get_async_session() as session:
        session.add(record)
        await session.flush()

    return analysis_id


async def get_analysis_by_incident_id(incident_id: str) -> dict[str, Any] | None:
    """Get the most recent analysis for an incident ID."""
    from sqlalchemy import select

    async with get_async_session() as session:
        result = await session.execute(
            select(AnalysisRecord)
            .where(AnalysisRecord.incident_id == incident_id)
            .order_by(AnalysisRecord.created_at.desc())
            .limit(1)
        )
        record = result.scalar_one_or_none()

    if record:
        return record.to_dict()
    return None  # type: ignore[return-value]


async def get_recent_analyses(limit: int = 20) -> list[dict[str, Any]]:
    """Get recent analyses for demo/history view."""
    from sqlalchemy import select

    async with get_async_session() as session:
        result = await session.execute(
            select(AnalysisRecord)
            .order_by(AnalysisRecord.created_at.desc())
            .limit(limit)
        )
        records = result.scalars().all()

    return [r.to_dict() for r in records]


# ============================================================================
# Resolution CRUD (Async)
# ============================================================================

async def create_resolution_record(
    analysis_id: str,
    incident_id: str,
    verified_root_cause: str,
    verified_resolution: str,
    notes: str | None,
    memory_id: str | None
) -> str:
    """Store a verified resolution record. Returns the resolution ID."""
    resolution_id = f"res_{uuid.uuid4().hex[:12]}"
    created_at = datetime.utcnow()

    record = ResolutionRecord(
        id=resolution_id,
        analysis_id=analysis_id,
        incident_id=incident_id,
        verified_root_cause=verified_root_cause,
        verified_resolution=verified_resolution,
        notes=notes,
        memory_id=memory_id,
        created_at=created_at,
    )

    async with get_async_session() as session:
        session.add(record)
        await session.flush()

    return resolution_id


async def get_resolution_by_incident_id(incident_id: str) -> dict[str, Any] | None:
    """Get the verified resolution for an incident ID."""
    from sqlalchemy import select

    async with get_async_session() as session:
        result = await session.execute(
            select(ResolutionRecord)
            .where(ResolutionRecord.incident_id == incident_id)
            .order_by(ResolutionRecord.created_at.desc())
            .limit(1)
        )
        record = result.scalar_one_or_none()

    if record:
        return record.to_dict()
    return None  # type: ignore[return-value]


async def get_all_resolutions(limit: int = 50) -> list[dict[str, Any]]:
    """Get all verified resolutions for memory explorer."""
    from sqlalchemy import select

    async with get_async_session() as session:
        result = await session.execute(
            select(ResolutionRecord)
            .order_by(ResolutionRecord.created_at.desc())
            .limit(limit)
        )
        records = result.scalars().all()

    return [r.to_dict() for r in records]  # type: ignore[return-value]
