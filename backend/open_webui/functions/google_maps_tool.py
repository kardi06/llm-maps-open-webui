"""
title: Google Maps Tool
description: Find places, get directions, and place details using Google Maps
version: 1.0.0
required_open_webui_version: 0.6.0
license: MIT
requirements: aiohttp
"""

import os
import aiohttp
import logging
import re
import time

from enum import Enum
from typing import Optional, Dict, Any, List

log = logging.getLogger(__name__)


# ─── Helper Classes & Enums ────────────────────────────────────────────

class PlaceType(str, Enum):
    restaurant      = "restaurant"
    gas_station     = "gas_station"
    hospital        = "hospital"
    shopping_mall   = "shopping_mall"
    tourist_attraction = "tourist_attraction"


class TravelMode(str, Enum):
    driving   = "driving"
    walking   = "walking"
    transit   = "transit"
    bicycling = "bicycling"


class LocationParser:
    @staticmethod
    def normalize(location: str) -> str:
        s = re.sub(r'\s+', ' ', location.strip())
        return re.sub(r'\bst\b', 'street', s, flags=re.IGNORECASE)

    @staticmethod
    def validate(location: str) -> bool:
        return bool(location and 2 <= len(location) <= 200 and not re.search(r'<script|javascript:', location, re.IGNORECASE))


# ─── The Required Class `Function` ─────────────────────────────────────

class Function:
    def __init__(self):
        backend = os.getenv("OPENWEBUI_BACKEND_URL", "http://localhost:8080")
        self.base_url = f"{backend}/api/v1/maps"
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def _call_api(self, endpoint: str, payload: Dict[str, Any], token: str) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            resp = await session.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return await resp.json()

    async def find_places(
        self,
        location: str,
        query: str,
        type: Optional[PlaceType] = None,
        radius: int = 5000,
        __user__: Optional[Dict[str,Any]] = None,
        __id__: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Find places near a location.

        :param location: Address or coordinates (e.g. "Jakarta" or "6.2,106.8")
        :param query: Search term (e.g. "coffee shop")
        :param type: Optional filter by place type
        :param radius: Radius in meters (100–50000)
        """
        __user__ = __user__ or {}
        token = __user__.get("token", {}).get("credentials")
        if not token:
            return {"status":"error","message":"Authentication required","places":[]}

        if not LocationParser.validate(location):
            return {"status":"error","message":"Invalid location","places":[]}

        payload = {
            "location": LocationParser.normalize(location),
            "query": query.strip(),
            "type": type.value if type else None,
            "radius": max(100, min(radius, 50000))
        }

        data = await self._call_api("/search", payload, token)
        places = data.get("places", [])
        return {
            "type": "maps_response",
            "action": "find_places",
            "data": {
                "places": places,
                "query": query,
                "total_results": len(places),
                "location": location
            }
        }

    async def get_directions(
        self,
        origin: str,
        destination: str,
        mode: TravelMode = TravelMode.driving,
        __user__: Optional[Dict[str,Any]] = None,
        __id__: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get directions between two places.

        :param origin: Starting point
        :param destination: Ending point
        :param mode: Travel mode
        """
        __user__ = __user__ or {}
        token = __user__.get("token", {}).get("credentials")
        if not token:
            return {"status":"error","message":"Authentication required","directions":None}

        payload = {
            "origin": origin,
            "destination": destination,
            "mode": mode.value
        }
        data = await self._call_api("/directions", payload, token)
        return {
            "type": "maps_response",
            "action": "get_directions",
            "data": data.get("directions", {})
        }

    async def place_details(
        self,
        place_id: str,
        __user__: Optional[Dict[str,Any]] = None,
        __id__: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get details for a specific place ID.
        """
        __user__ = __user__ or {}
        token = __user__.get("token", {}).get("credentials")
        if not token:
            return {"status":"error","message":"Authentication required","place_details":None}

        data = await self._call_api("/place_details", {"place_id": place_id}, token)
        return {
            "type": "maps_response",
            "action": "place_details",
            "data": data.get("place_details", {})
        }
