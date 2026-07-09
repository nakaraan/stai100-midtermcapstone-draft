"""Location-name geocoding for AGENT P.

Resolves a free-text place description (e.g. "our warehouse in Caloocan")
into real latitude/longitude via OpenStreetMap's Nominatim API — free, no
API key required. Exists so the agent doesn't have to rely on an LLM's own
memorized geography for coordinates, which is unreliable and inconsistent
across models — see config/prompts.yaml's intent_parser prompt, which now
leaves lat/lon null for a named place and lets this module resolve them
deterministically instead, the same way aggregate_monthly keeps arithmetic
out of the LLM's hands.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

import requests

from utils.telemetry import trace_tool

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy requires a descriptive User-Agent identifying the
# calling application — a missing or generic one risks being blocked.
USER_AGENT = "agent-p-solar-analytics/1.0 (STAI100 capstone, Stratpoint x DLSU)"
REQUEST_TIMEOUT_SECONDS = 10


@trace_tool(name="geocode_location")
@lru_cache(maxsize=256)
def geocode(location_name: str) -> Optional[dict]:
    """Resolve a free-text place description into coordinates.

    Returns {"latitude": float, "longitude": float, "display_name": str} for
    the best match, or None if nothing resolved (a typo, a nonexistent place,
    or a description too vague to be a real place at all). Cached per unique
    location_name for the life of the process — repeat questions about the
    same place (common across one demo/testing session) don't re-hit
    Nominatim, which also helps stay under its 1-request/second usage policy.
    """
    stripped = location_name.strip()
    if not stripped:
        return None

    response = requests.get(
        NOMINATIM_URL,
        params={"q": stripped, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    results = response.json()
    if not results:
        return None

    best = results[0]
    try:
        return {
            "latitude": float(best["lat"]),
            "longitude": float(best["lon"]),
            "display_name": best.get("display_name", stripped),
        }
    except (KeyError, ValueError, TypeError):
        return None
