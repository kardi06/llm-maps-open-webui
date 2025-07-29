"""
title: Google Maps Tool
description: Find places, directions, and place details via custom Google-Maps API
version: 1.0.0
required_open_webui_version: 0.4.0
license: MIT
requirements: aiohttp
"""

import os, re, time, logging, aiohttp
from enum import Enum
from typing import Dict, List, Any, Optional

log = logging.getLogger(__name__)

# ── Enums ──────────────────────────────────────────────────────────────
class PlaceType(str, Enum):
    restaurant = "restaurant"
    gas_station = "gas_station"
    hospital = "hospital"

class TravelMode(str, Enum):
    driving = "driving"
    walking = "walking"
    transit = "transit"
    bicycling = "bicycling"

# ── Helper util ─────────────────────────────────────────────────────────
class MapsUsageTracker:
    _stats: Dict[str, List[float]] = {}
    @classmethod
    def allow(cls, uid: str, fn: str, limit: int) -> bool:
        now = time.time()
        key = f"{uid}:{fn}"
        cls._stats.setdefault(key, [])
        cls._stats[key] = [t for t in cls._stats[key] if now - t < 3600]
        if len(cls._stats[key]) >= limit:
            return False
        cls._stats[key].append(now)
        return True

class LocationParser:
    @staticmethod
    def normalize(text: str) -> str:
        return re.sub(r'\s+', ' ', text.strip())
    @staticmethod
    def valid(text: str) -> bool:
        return 1 < len(text.strip()) < 200 and "<script" not in text.lower()

# ── Main toolkit class ─────────────────────────────────────────────────
class Tools:
    def __init__(self):
        backend = os.getenv("OPENWEBUI_BACKEND_URL", "http://localhost:8080")
        self.base_url = f"{backend}/api/v1/maps"
        self.http_timeout = aiohttp.ClientTimeout(total=25)

    # ---------- FIND PLACES ----------
    async def find_places(
        self,
        location: str,
        query: str,
        type: Optional[PlaceType] = None,
        radius: int = 5000,
        __user__: Optional[Dict[str, Any]] = None,
        __id__: Optional[str] = None
    ) -> Dict[str, Any]:

        __user__ = __user__ or {}
        uid = __user__.get("id", "anon")
        token = (__user__.get("token") or {}).get("credentials", "")

        # basic guards
        if not token:
            return {"status": "error", "message": "Authentication required", "places": []}
        if not MapsUsageTracker.allow(uid, "find_places", 100):
            return {"status": "error", "message": "Rate limit exceeded", "places": []}
        if not LocationParser.valid(location):
            return {"status": "error", "message": "Invalid location", "places": []}

        payload = {
            "location": LocationParser.normalize(location),
            "query": query.strip(),
            "type": type.value if type else None,
            "radius": max(100, min(radius, 50000))
        }

        async with aiohttp.ClientSession(timeout=self.http_timeout) as s:
            async with s.post(
                f"{self.base_url}/search",
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            ) as r:
                if r.status != 200:
                    text = await r.text()
                    return {"status": "error", "message": f"Maps API error: {text}", "places": []}
                data = await r.json()

        return {
            "type": "maps_response",
            "action": "find_places",
            "data": {
                "places": data.get("places", []),
                "query": query,
                "total_results": len(data.get("places", [])),
                "location": location
            }
        }

    # Tambahkan `get_directions` dan `place_details` dengan pola serupa
