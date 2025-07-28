"""
title: Google Maps Tool  
description: Find places, get directions, and place details using Google Maps
author: open-webui
author_url: https://github.com/open-webui/open-webui
funding_url: https://github.com/open-webui/open-webui
version: 1.0.0
license: MIT
requirements: aiohttp, pydantic
"""

import asyncio
import aiohttp
import json
import logging
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum

log = logging.getLogger(__name__)


class PlaceType(str, Enum):
    """Enumeration of supported place types for filtering"""
    restaurant = "restaurant"
    gas_station = "gas_station"
    hospital = "hospital"
    school = "school"
    bank = "bank"
    atm = "atm"
    pharmacy = "pharmacy"
    shopping_mall = "shopping_mall"
    hotel = "hotel"
    tourist_attraction = "tourist_attraction"


class TravelMode(str, Enum):
    """Enumeration of supported travel modes for directions"""
    driving = "driving"
    walking = "walking"
    transit = "transit"
    bicycling = "bicycling"


class Tools:
    """
    Google Maps Tool for finding places, getting directions, and place details
    """

    def __init__(self):
        self.base_url = "http://localhost:8080"  # OpenWebUI backend URL
        self.timeout = aiohttp.ClientTimeout(total=30)

    async def _make_request(self, endpoint: str, data: Dict[str, Any], user_token: str) -> Dict[str, Any]:
        """
        Make authenticated request to OpenWebUI maps router
        
        Args:
            endpoint: Maps API endpoint (e.g., '/maps/find_places')
            data: Request payload
            user_token: User authentication token
            
        Returns:
            API response data
            
        Raises:
            Exception: If request fails or returns error
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        raise Exception(f"Maps API error ({response.status}): {error_text}")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error calling maps API: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to call maps API: {str(e)}")

    async def find_places(
        self,
        location: str,
        query: str,
        type: Optional[PlaceType] = None,
        radius: int = 5000,
        __user__: dict = {},
        __id__: str = None
    ) -> dict:
        """
        Find places of interest using natural language search. Use this when users ask to find restaurants, shops, services, or any type of place near a location.
        
        :param location: Current location or search center. Can be an address, landmark, city name, or coordinates (e.g., "Jakarta", "Senayan City", "Jl. Sudirman No. 1")
        :param query: What to search for using natural language. Be specific about what the user wants (e.g., "sushi restaurants", "gas stations", "ATM", "coffee shops", "hospitals")
        :param type: Optional place type to filter results. Valid values: restaurant, gas_station, hospital, school, bank, atm, pharmacy, shopping_mall, hotel, tourist_attraction
        :param radius: Search radius in meters. Default is 5000m (5km). Minimum: 100m, Maximum: 50000m (50km)
        :return: Dictionary containing list of places with details including name, address, coordinates, rating, and status message
        """
        try:
            # Validate parameters
            if not location or not query:
                return {
                    "places": [],
                    "status": "error",
                    "message": "Location and query are required parameters"
                }
            
            # Prepare request data
            request_data = {
                "location": location,
                "query": query,
                "radius": min(max(radius, 100), 50000)  # Clamp radius between 100-50000m
            }
            
            if type:
                request_data["type"] = type.value if isinstance(type, PlaceType) else type
            
            # Get user token for authentication
            user_token = __user__.get("token", {}).get("credentials", "")
            if not user_token:
                return {
                    "places": [],
                    "status": "error", 
                    "message": "User authentication required"
                }
            
            # Make request to maps router
            response = await self._make_request("/maps/find_places", request_data, user_token)
            
            # Format response for LLM consumption
            places = response.get("places", [])
            
            # Add helpful context for LLM
            formatted_places = []
            for place in places:
                formatted_place = {
                    "name": place.get("name", "Unknown"),
                    "address": place.get("address", ""),
                    "coordinates": {
                        "lat": place.get("lat"),
                        "lng": place.get("lng")
                    },
                    "place_id": place.get("place_id", ""),
                    "rating": place.get("rating"),
                    "open_now": place.get("open_now"),
                    "maps_url": place.get("maps_url", ""),
                    "distance": place.get("distance", ""),
                    "price_level": place.get("price_level")
                }
                formatted_places.append(formatted_place)
            
            return {
                "places": formatted_places,
                "status": "success",
                "message": f"Found {len(formatted_places)} places matching '{query}' near {location}",
                "search_info": {
                    "location": location,
                    "query": query,
                    "type": type,
                    "radius": radius
                }
            }
            
        except Exception as e:
            log.error(f"Error in find_places: {str(e)}")
            return {
                "places": [],
                "status": "error",
                "message": f"Failed to find places: {str(e)}"
            }

    async def get_directions(
        self,
        origin: str,
        destination: str,
        mode: TravelMode = TravelMode.driving,
        __user__: dict = {},
        __id__: str = None
    ) -> dict:
        """
        Get step-by-step directions between two locations. Use this when users ask how to get from one place to another, need navigation instructions, or want to know travel time and distance.
        
        :param origin: Starting location. Can be an address, landmark, city name, or place name (e.g., "Jakarta", "Jl. Sudirman No. 1", "Soekarno-Hatta Airport")
        :param destination: Destination location. Can be an address, landmark, city name, or place name (e.g., "Bandung", "Senayan City", "Bogor Station")
        :param mode: Travel mode for directions. Valid values: driving (default), walking, transit (public transport), bicycling. Choose based on user preference or context
        :return: Dictionary containing directions with step-by-step instructions, distance, duration, travel mode, and maps URL
        """
        try:
            # Validate parameters
            if not origin or not destination:
                return {
                    "directions": None,
                    "status": "error",
                    "message": "Origin and destination are required parameters"
                }
            
            # Handle travel mode (convert enum to string if needed)
            mode_value = mode.value if isinstance(mode, TravelMode) else mode
            
            # Validate travel mode
            valid_modes = ["driving", "walking", "transit", "bicycling"]
            if mode_value not in valid_modes:
                mode_value = "driving"
            
            # Prepare request data
            request_data = {
                "origin": origin,
                "destination": destination,
                "mode": mode_value
            }
            
            # Get user token for authentication
            user_token = __user__.get("token", {}).get("credentials", "")
            if not user_token:
                return {
                    "directions": None,
                    "status": "error",
                    "message": "User authentication required"
                }
            
            # Make request to maps router
            response = await self._make_request("/maps/get_directions", request_data, user_token)
            
            # Format response for LLM consumption
            directions_data = response.get("directions", {})
            
            formatted_directions = {
                "summary": {
                    "origin": directions_data.get("origin", origin),
                    "destination": directions_data.get("destination", destination), 
                    "distance": directions_data.get("distance", ""),
                    "duration": directions_data.get("duration", ""),
                    "travel_mode": mode_value.title()
                },
                "steps": directions_data.get("steps", []),
                "maps_url": directions_data.get("maps_url", ""),
                "warnings": directions_data.get("warnings", [])
            }
            
            return {
                "directions": formatted_directions,
                "status": "success", 
                "message": f"Directions from {origin} to {destination} via {mode_value}"
            }
            
        except Exception as e:
            log.error(f"Error in get_directions: {str(e)}")
            return {
                "directions": None,
                "status": "error",
                "message": f"Failed to get directions: {str(e)}"
            }

    async def place_details(
        self,
        place_id: str,
        __user__: dict = {},
        __id__: str = None
    ) -> dict:
        """
        Get detailed information about a specific place including business hours, contact information, reviews, and photos. Use this when users want more details about a specific place they found or when they ask about opening hours, phone numbers, or reviews.
        
        :param place_id: Google Place ID from a previous find_places search result. This is a unique identifier starting with "ChIJ" (e.g., "ChIJN1t_tDeuEmsRUsoyG83frY4")
        :return: Dictionary containing detailed place information including basic info (name, address, phone, website), location coordinates, business info (hours, price level), reviews, photos, and maps URL
        """
        try:
            # Validate parameters
            if not place_id:
                return {
                    "place_details": None,
                    "status": "error",
                    "message": "Place ID is required"
                }
            
            # Prepare request data
            request_data = {
                "place_id": place_id
            }
            
            # Get user token for authentication
            user_token = __user__.get("token", {}).get("credentials", "")
            if not user_token:
                return {
                    "place_details": None,
                    "status": "error",
                    "message": "User authentication required"
                }
            
            # Make request to maps router
            response = await self._make_request("/maps/place_details", request_data, user_token)
            
            # Format response for LLM consumption
            place_data = response.get("place_details", {})
            details = place_data.get("details", {})
            
            formatted_details = {
                "basic_info": {
                    "name": details.get("name", "Unknown"),
                    "address": details.get("formatted_address", ""),
                    "phone": details.get("phone", ""),
                    "website": details.get("website", ""),
                    "rating": details.get("rating"),
                    "user_ratings_total": details.get("user_ratings_total", 0)
                },
                "location": {
                    "lat": details.get("lat"),
                    "lng": details.get("lng"),
                    "place_id": place_id
                },
                "business_info": {
                    "opening_hours": details.get("opening_hours", {}),
                    "price_level": details.get("price_level"),
                    "types": details.get("types", [])
                },
                "reviews": place_data.get("reviews", [])[:5],  # Limit to 5 most recent reviews
                "photos": place_data.get("photos", [])[:3],     # Limit to 3 photos
                "maps_url": place_data.get("maps_url", "")
            }
            
            return {
                "place_details": formatted_details,
                "status": "success",
                "message": f"Retrieved details for {details.get('name', 'place')}"
            }
            
        except Exception as e:
            log.error(f"Error in place_details: {str(e)}")
            return {
                "place_details": None,
                "status": "error", 
                "message": f"Failed to get place details: {str(e)}"
            } 