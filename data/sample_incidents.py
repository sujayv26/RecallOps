"""Synthetic seed incidents for demo memory bank.

These are FABRICATED incidents for testing and demonstration only.
They must NOT be represented as real customer or production incidents.
"""

SAMPLE_INCIDENTS = [
    {
        "id": "INC-001",
        "service": "Backend API",
        "symptom": "Intermittent HTTP 500 errors on /api/users endpoint, ~15% error rate over 10 minutes",
        "root_cause": "Database connection pool exhausted due to connection leak in UserService",
        "resolution": "Fixed connection leak in UserService.getUserProfile() by adding try-with-resources. Increased pool size from 20 to 50 as safety margin. Deployed fix in v2.3.1.",
    },
    {
        "id": "INC-002",
        "service": "Database",
        "symptom": "Connection timeouts and slow query responses, P99 latency > 5s",
        "root_cause": "High database load from unoptimized queries in reporting module + missing indexes",
        "resolution": "Added missing indexes on user_events table. Optimized 3 slow queries in reporting module. Enabled query plan caching. Latency reduced to P99 < 200ms.",
    },
    {
        "id": "INC-003",
        "service": "Payment Service",
        "symptom": "HTTP 502 errors from payment gateway, 100% failure rate for 5 minutes",
        "root_cause": "Upstream payment provider (Stripe) regional outage in us-east-1",
        "resolution": "Verified upstream status via provider status page. Implemented circuit breaker with fallback to cached payment methods. Added alerting for upstream health checks.",
    },
    {
        "id": "INC-004",
        "service": "Auth Service",
        "symptom": "Sudden spike in HTTP 401 errors across all services, ~40% of requests failing",
        "root_cause": "JWT signing key rotation completed but old key not removed from JWKS endpoint, causing validation failures",
        "resolution": "Updated JWKS endpoint to include both old and new keys during rotation window. Fixed key rotation automation to maintain overlap period. Added integration test for key rotation.",
    },
    {
        "id": "INC-005",
        "service": "Backend API",
        "symptom": "HTTP 503 errors, pods OOMKilled, memory usage growing unbounded",
        "root_cause": "Memory leak in cache layer - Redis client not releasing connections, compounded by unbounded local cache growth",
        "resolution": "Fixed Redis client connection cleanup. Added LRU eviction with max size to local cache. Set memory limits and requests on Kubernetes deployment. Added memory profiling to CI.",
    },
]


def get_sample_incidents():
    """Get all sample incidents."""
    return SAMPLE_INCIDENTS


def get_incident_by_id(incident_id: str):
    """Get a sample incident by ID."""
    for inc in SAMPLE_INCIDENTS:
        if inc["id"] == incident_id:
            return inc
    return None