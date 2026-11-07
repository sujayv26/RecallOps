"""Optional SQLite audit history for local demo metadata.

This is NOT a replacement for Hindsight. It provides a local audit trail
of analyses and resolutions for demo purposes.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
import uuid

from backend.config import settings


# Database file path
DB_PATH = Path(settings.database_url.replace("sqlite:///", ""))


def get_db_path() -> Path:
    """Get the database file path, creating parent directories if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH


def init_db() -> None:
    """Initialize the SQLite database with required tables."""
    with get_db_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                service_name TEXT NOT NULL,
                error_description TEXT NOT NULL,
                log_excerpt TEXT,
                severity TEXT NOT NULL,
                likely_root_cause TEXT NOT NULL,
                explanation TEXT NOT NULL,
                recommended_actions TEXT NOT NULL,  -- JSON array
                confidence REAL NOT NULL,
                historical_matches TEXT NOT NULL,  -- JSON array
                memory_influence TEXT,
                caveats TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS resolutions (
                id TEXT PRIMARY KEY,
                analysis_id TEXT NOT NULL,
                incident_id TEXT NOT NULL,
                verified_root_cause TEXT NOT NULL,
                verified_resolution TEXT NOT NULL,
                notes TEXT,
                memory_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (analysis_id) REFERENCES analyses (id)
            );

            CREATE INDEX IF NOT EXISTS idx_analyses_incident_id ON analyses (incident_id);
            CREATE INDEX IF NOT EXISTS idx_resolutions_incident_id ON resolutions (incident_id);
            CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses (created_at);
        """)


@contextmanager
def get_db_connection():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================================
# Analysis CRUD
# ============================================================================

def create_analysis_record(
    incident_id: str,
    service_name: str,
    error_description: str,
    log_excerpt: Optional[str],
    severity: str,
    likely_root_cause: str,
    explanation: str,
    recommended_actions: List[str],
    confidence: float,
    historical_matches: List[Dict[str, Any]],
    memory_influence: str,
    caveats: Optional[str]
) -> str:
    """Store an analysis record. Returns the analysis ID."""
    analysis_id = f"ana_{uuid.uuid4().hex[:12]}"
    created_at = datetime.utcnow().isoformat()

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO analyses (
                id, incident_id, service_name, error_description, log_excerpt,
                severity, likely_root_cause, explanation, recommended_actions,
                confidence, historical_matches, memory_influence, caveats, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            analysis_id, incident_id, service_name, error_description, log_excerpt,
            severity, likely_root_cause, explanation, json.dumps(recommended_actions),
            confidence, json.dumps(historical_matches), memory_influence, caveats, created_at
        ))

    return analysis_id


def get_analysis_by_incident_id(incident_id: str) -> Optional[Dict[str, Any]]:
    """Get the most recent analysis for an incident ID."""
    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT * FROM analyses WHERE incident_id = ? ORDER BY created_at DESC LIMIT 1
        """, (incident_id,)).fetchone()

    if row:
        return _parse_analysis_row(row)
    return None


def get_recent_analyses(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent analyses for demo/history view."""
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM analyses ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()

    return [_parse_analysis_row(row) for row in rows]


def _parse_analysis_row(row: sqlite3.Row) -> Dict[str, Any]:
    """Parse a database row into a dict with proper JSON decoding."""
    return {
        "id": row["id"],
        "incident_id": row["incident_id"],
        "service_name": row["service_name"],
        "error_description": row["error_description"],
        "log_excerpt": row["log_excerpt"],
        "severity": row["severity"],
        "likely_root_cause": row["likely_root_cause"],
        "explanation": row["explanation"],
        "recommended_actions": json.loads(row["recommended_actions"]),
        "confidence": row["confidence"],
        "historical_matches": json.loads(row["historical_matches"]),
        "memory_influence": row["memory_influence"],
        "caveats": row["caveats"],
        "created_at": row["created_at"],
    }


# ============================================================================
# Resolution CRUD
# ============================================================================

def create_resolution_record(
    analysis_id: str,
    incident_id: str,
    verified_root_cause: str,
    verified_resolution: str,
    notes: Optional[str],
    memory_id: Optional[str]
) -> str:
    """Store a verified resolution record. Returns the resolution ID."""
    resolution_id = f"res_{uuid.uuid4().hex[:12]}"
    created_at = datetime.utcnow().isoformat()

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO resolutions (
                id, analysis_id, incident_id, verified_root_cause,
                verified_resolution, notes, memory_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            resolution_id, analysis_id, incident_id, verified_root_cause,
            verified_resolution, notes, memory_id, created_at
        ))

    return resolution_id


def get_resolution_by_incident_id(incident_id: str) -> Optional[Dict[str, Any]]:
    """Get the verified resolution for an incident ID."""
    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT * FROM resolutions WHERE incident_id = ? ORDER BY created_at DESC LIMIT 1
        """, (incident_id,)).fetchone()

    if row:
        return dict(row)
    return None


def get_all_resolutions(limit: int = 50) -> List[Dict[str, Any]]:
    """Get all verified resolutions for memory explorer."""
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM resolutions ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()

    return [dict(row) for row in rows]