#!/usr/bin/env python
"""Script to seed Hindsight memory bank with synthetic incidents.

Run this after configuring Hindsight credentials to populate the demo memory bank.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings
from backend.memory import _get_hindsight_client, is_hindsight_available
from data.sample_incidents import SAMPLE_INCIDENTS


def seed_hindsight():
    """Seed the Hindsight bank with synthetic incidents."""
    client = _get_hindsight_client()

    if client is None:
        print("[Seed] Hindsight client not available. Check credentials and SDK installation.")
        print("[Seed] Required environment variables:")
        print(f"  HINDSIGHT_API_KEY={settings.hindsight_api_key or '(not set)'}")
        print(f"  HINDSIGHT_BASE_URL={settings.hindsight_base_url}")
        print(f"  HINDSIGHT_BANK_ID={settings.hindsight_bank_id or '(not set)'}")
        return False

    try:
        bank = client.bank(settings.hindsight_bank_id)
        print(f"[Seed] Connected to Hindsight bank: {settings.hindsight_bank_id}")

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
                memory_id = result.get("id") or result.get("memory_id", "unknown")
                print(f"[Seed] ✓ Stored {inc['id']} as memory {memory_id}")
            except Exception as e:
                print(f"[Seed] ✗ Failed to store {inc['id']}: {e}")

        print("[Seed] Done!")
        return True

    except Exception as e:
        print(f"[Seed] Error: {e}")
        return False


def verify_seed():
    """Verify seeded memories can be recalled."""
    client = _get_hindsight_client()

    if client is None:
        print("[Verify] Hindsight not available")
        return

    try:
        bank = client.bank(settings.hindsight_bank_id)

        # Try to recall each incident
        for inc in SAMPLE_INCIDENTS:
            query = f"{inc['service']} {inc['symptom'][:50]}"
            results = bank.recall(query=query, limit=1)

            if results:
                print(f"[Verify] ✓ {inc['id']} - recallable")
            else:
                print(f"[Verify] ✗ {inc['id']} - NOT FOUND")

    except Exception as e:
        print(f"[Verify] Error: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("RecallOps - Hindsight Memory Seeding")
    print("=" * 50)

    # Load .env if present
    from dotenv import load_dotenv
    load_dotenv()

    seed_hindsight()
    print()
    verify_seed()