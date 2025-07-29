"""
title: Google Maps Search
description: Cari tempat & arah menggunakan Google Maps API
version: 1.0.0
required_open_webui_version: 0.4.0
license: MIT
requirements: aiohttp
"""

import os
import asyncio
import aiohttp
from typing import List, Dict

class Tools:
    def __init__(self):
        # Pastikan backend Anda expose endpoint /api/google-maps/search
        self.base_url = os.getenv("GOOGLE_MAPS_BACKEND_URL", "http://localhost:8080/api/google-maps")

    def find_places(self, query: str) -> List[Dict]:
        """
        Cari tempat berdasarkan query (misal "cafe di Jakarta").
        Ini memanggil async helper di bawah dan mengembalikan list dict.
        """
        return asyncio.run(self._find_places_async(query))

    async def _find_places_async(self, query: str) -> List[Dict]:
        """
        Helper async untuk melakukan request ke backend Google Maps API custom.
        """
        url = f"{self.base_url}/search"
        params = {"query": query}
        # Jika Anda butuh Authentication, bisa sisipkan header di sini
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()
        # Asumsikan backend mengembalikan JSON berupa list objek:
        # [{ "name": ..., "lat": ..., "lng": ..., "place_id": ... }, ...]
        return data
