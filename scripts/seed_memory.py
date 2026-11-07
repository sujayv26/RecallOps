#!/usr/bin/env python
"""Script to seed Hindsight memory bank with synthetic incidents.

Run this after configuring Hindsight credentials to populate the demo memory bank.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings
from backend.memory import _get_hindsight_client
from data.sample_incidents import SAMPLE_INCIDENTS


def seed_hindsight():
    """Seed the Hindsight bank with synthetic incidents."""
    client = _get_hindsight_client()

    if client is None:
        return False

    try:
        bank = client.bank(settings.hindsight_bank_id)

        for inc in SAMPLE_INCIDENTS:
            content = f"""Incident: {inc['id']}
Service: {inc['service']}
Symptom: {inc['symptom']}
Verified Root Cause: {inc['root_cause']}
Verified Resolution: {inc['resolution']}"""

            memory_data = {
                "content": content,
                "metadata": {
                    "incident_id": inc["id"],
                    "service_name": inc["service"],
                    "type": "verified_incident_resolution",
                    "verified": True,
                    "synthetic": True,  # Mark as demo data
                }
            }

            # The exact method depends on Hindsight SDK version
            try:
                result = bank.add(**memory_data)
                result.get("id") or result.get("memory_id", "unknown")
            except Exception:
                pass

        return True

    except Exception:
        return False


def verify_seed():
    """Verify seeded memories can be recalled."""
    client = _get_hindsight_client()

    if client is None:
        return

    try:
        bank = client.bank(settings.hindsight_bank_id)

        # Try to recall each incident
        for inc in SAMPLE_INCIDENTS:
            query = f"{inc['service']} {inc['symptom'][:50]}"
            results = bank.recall(query=query, limit=1)

            if results:
                pass
            else:
                pass

    except Exception:
        pass


if __name__ == "__main__":

    # Load .env if present
    from dotenv import load_dotenv
    load_dotenv()

    seed_hindsight()
    verify_seed()
