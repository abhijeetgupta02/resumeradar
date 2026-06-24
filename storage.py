"""
Opt-in submission storage for the public resume scorer.

Writes a record per consented scan to a Supabase table via its auto-generated
REST API (uses `requests`, already a project dependency — no extra package).

Storage is OFF unless BOTH of these env vars / Streamlit secrets are set:
    SUPABASE_URL   e.g. https://xxxx.supabase.co
    SUPABASE_KEY   the service_role key (kept server-side only, never in the repo)
Optional:
    SUPABASE_TABLE defaults to "submissions"

If the creds are absent, save_submission() is a no-op and returns False, so the
app runs fine before storage is configured.

One-time table setup (run in the Supabase SQL editor):

    create table submissions (
      id bigint generated always as identity primary key,
      created_at timestamptz default now(),
      name text,
      email text
    );
"""

import os
import logging

import requests

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))


def save_submission(record: dict) -> bool:
    """Insert one consented submission. Returns True on success, False otherwise."""
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_KEY", "")
    table = os.getenv("SUPABASE_TABLE", "submissions")
    if not url or not key:
        return False
    try:
        resp = requests.post(
            f"{url}/rest/v1/{table}",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=record,
            timeout=10,
        )
        if resp.status_code in (200, 201, 204):
            return True
        logger.warning("Supabase insert failed: %s %s", resp.status_code, resp.text[:300])
        return False
    except Exception as e:
        logger.warning("Supabase insert error: %s", e)
        return False
