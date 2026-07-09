#Location-name geocoding for AGENT P
from __future__ import annotations

from functools import lru_cache
from typing import Optional

import requests

from utils.telemetry import trace_tool

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "agent-p-solar-analytics/1.0 (STAI100 capstone, Stratpoint x DLSU)"
REQUEST_TIMEOUT_SECONDS = 10


@trace_tool(name="geocode_location")
@lru_cache(maxsize=256)
def geocode(location_name: str) -> Optional[dict]:
    #Resolve a free-text place description into coordinates
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
