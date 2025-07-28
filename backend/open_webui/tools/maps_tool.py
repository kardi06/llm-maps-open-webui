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
import re
import time
from typing import Optional, Dict, Any, Literal, List
from pydantic import BaseModel, Field, validator
from enum import Enum

log = logging.getLogger(__name__)


class MapsUsageTracker:
    """Track API usage for rate limiting and monitoring"""
    
    _usage_stats = {}
    
    @classmethod
    def track_usage(cls, user_id: str, function_name: str):
        """Track function usage for rate limiting"""
        current_time = time.time()
        key = f"{user_id}:{function_name}"
        
        if key not in cls._usage_stats:
            cls._usage_stats[key] = []
        
        # Clean old entries (older than 1 hour)
        cls._usage_stats[key] = [
            timestamp for timestamp in cls._usage_stats[key]
            if current_time - timestamp < 3600
        ]
        
        cls._usage_stats[key].append(current_time)
    
    @classmethod
    def check_rate_limit(cls, user_id: str, function_name: str, limit_per_hour: int = 100) -> bool:
        """Check if user has exceeded rate limit"""
        key = f"{user_id}:{function_name}"
        current_usage = len(cls._usage_stats.get(key, []))
        return current_usage < limit_per_hour
    
    @classmethod
    def get_usage_stats(cls, user_id: str) -> Dict[str, int]:
        """Get usage statistics for a user"""
        stats = {}
        for key, timestamps in cls._usage_stats.items():
            if key.startswith(f"{user_id}:"):
                function_name = key.split(":", 1)[1]
                stats[function_name] = len(timestamps)
        return stats


class LocationParser:
    """Helper class for parsing and validating location inputs"""
    
    @staticmethod
    def extract_coordinates(location: str) -> Optional[Dict[str, float]]:
        """Extract lat/lng coordinates from location string"""
        # Pattern for coordinates: "lat,lng" or "lat, lng"
        coord_pattern = r'^(-?\d+\.?\d*),\s*(-?\d+\.?\d*)$'
        match = re.match(coord_pattern, location.strip())
        
        if match:
            lat, lng = float(match.group(1)), float(match.group(2))
            # Basic validation for Earth coordinates
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return {"lat": lat, "lng": lng}
        
        return None
    
    @staticmethod
    def normalize_location(location: str) -> str:
        """Normalize location string for better API compatibility"""
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', location.strip())
        
        # Common replacements for better API compatibility
        replacements = {
            r'\bst\b': 'street',
            r'\brd\b': 'road',
            r'\bave\b': 'avenue',
            r'\bblvd\b': 'boulevard',
            r'\bjl\b': 'jalan',  # Indonesian
            r'\bjln\b': 'jalan'   # Indonesian
        }
        
        for pattern, replacement in replacements.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        return normalized
    
    @staticmethod
    def validate_location_input(location: str) -> bool:
        """Validate location input for security and format"""
        if not location or len(location.strip()) < 2:
            return False
        
        # Check for potentially malicious patterns
        dangerous_patterns = [
            r'<script',
            r'javascript:',
            r'data:',
            r'vbscript:',
            r'onload=',
            r'onerror='
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, location, re.IGNORECASE):
                return False
        
        # Length check
        if len(location) > 200:
            return False
        
        return True


class QueryEnhancer:
    """Helper class for enhancing and parsing natural language queries"""
    
    PLACE_TYPE_KEYWORDS = {
        'restaurant': ['restaurant', 'food', 'eat', 'dining', 'cuisine', 'sushi', 'pizza', 'burger'],
        'gas_station': ['gas', 'fuel', 'petrol', 'gasoline', 'station'],
        'hospital': ['hospital', 'medical', 'clinic', 'doctor', 'emergency'],
        'school': ['school', 'university', 'college', 'education'],
        'bank': ['bank', 'banking', 'atm', 'finance'],
        'pharmacy': ['pharmacy', 'medicine', 'drug', 'medication'],
        'shopping_mall': ['mall', 'shopping', 'store', 'retail'],
        'hotel': ['hotel', 'accommodation', 'stay', 'lodge'],
        'tourist_attraction': ['tourist', 'attraction', 'museum', 'park', 'monument']
    }
    
    @classmethod
    def suggest_place_type(cls, query: str) -> Optional[str]:
        """Suggest place type based on query keywords"""
        query_lower = query.lower()
        
        for place_type, keywords in cls.PLACE_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return place_type
        
        return None
    
    @classmethod
    def enhance_query(cls, query: str, location: str) -> Dict[str, Any]:
        """Enhance query with suggestions and extracted information"""
        return {
            'original_query': query,
            'suggested_type': cls.suggest_place_type(query),
            'enhanced_query': cls._enhance_query_text(query),
            'location_normalized': LocationParser.normalize_location(location)
        }
    
    @classmethod
    def _enhance_query_text(cls, query: str) -> str:
        """Enhance query text for better search results"""
        # Add common search modifiers for better results
        enhanced = query.strip()
        
        # If query is very short, don't enhance to avoid changing meaning
        if len(enhanced.split()) < 2:
            return enhanced
        
        return enhanced


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
    
    Enhanced with comprehensive error handling, rate limiting, input validation,
    and natural language processing capabilities.
    """

    def __init__(self):
        self.base_url = "http://localhost:8080"  # OpenWebUI backend URL
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.rate_limits = {
            'find_places': 100,  # per hour
            'get_directions': 50,  # per hour
            'place_details': 200  # per hour
        }

    def _validate_user_access(self, user: dict, function_name: str) -> bool:
        """
        Validate user access and rate limits
        
        Args:
            user: User information dictionary
            function_name: Name of the function being called
            
        Returns:
            bool: True if access is allowed, False otherwise
        """
        user_id = user.get('id', 'anonymous')
        
        # Check rate limits
        if not MapsUsageTracker.check_rate_limit(user_id, function_name, self.rate_limits[function_name]):
            log.warning(f"Rate limit exceeded for user {user_id} on function {function_name}")
            return False
        
        # Track usage
        MapsUsageTracker.track_usage(user_id, function_name)
        
        return True
    
    def _validate_and_enhance_parameters(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """
        Validate and enhance function parameters with security checks and NLP
        
        Args:
            function_name: Name of the function
            **kwargs: Function parameters
            
        Returns:
            Enhanced and validated parameters
            
        Raises:
            ValueError: If validation fails
        """
        if function_name == 'find_places':
            location = kwargs.get('location', '')
            query = kwargs.get('query', '')
            
            # Validate inputs
            if not LocationParser.validate_location_input(location):
                raise ValueError("Invalid location input")
            
            if not query or len(query.strip()) < 1:
                raise ValueError("Query cannot be empty")
            
            if len(query) > 200:
                raise ValueError("Query too long (max 200 characters)")
            
            # Enhance with NLP
            enhanced = QueryEnhancer.enhance_query(query, location)
            
            return {
                'location': enhanced['location_normalized'],
                'query': enhanced['enhanced_query'],
                'type': kwargs.get('type') or enhanced['suggested_type'],
                'radius': max(100, min(kwargs.get('radius', 5000), 50000)),
                '_enhancements': enhanced
            }
        
        elif function_name == 'get_directions':
            origin = kwargs.get('origin', '')
            destination = kwargs.get('destination', '')
            
            # Validate inputs
            if not LocationParser.validate_location_input(origin):
                raise ValueError("Invalid origin location")
            
            if not LocationParser.validate_location_input(destination):
                raise ValueError("Invalid destination location")
            
            return {
                'origin': LocationParser.normalize_location(origin),
                'destination': LocationParser.normalize_location(destination),
                'mode': kwargs.get('mode', TravelMode.driving)
            }
        
        elif function_name == 'place_details':
            place_id = kwargs.get('place_id', '')
            
            # Validate place_id format
            if not place_id or not isinstance(place_id, str):
                raise ValueError("Place ID is required and must be a string")
            
            if len(place_id) > 200:
                raise ValueError("Place ID too long")
            
            # Basic format check for Google Place IDs
            if not re.match(r'^[A-Za-z0-9_-]+$', place_id):
                raise ValueError("Invalid place ID format")
            
            return {'place_id': place_id}
        
        return kwargs
    
    def _format_error_response(self, function_name: str, error: Exception, user_id: str = None) -> dict:
        """
        Format error response with proper logging and user-friendly messages
        
        Args:
            function_name: Name of the function that failed
            error: The exception that occurred
            user_id: User ID for logging
            
        Returns:
            Formatted error response
        """
        error_id = f"{function_name}_{int(time.time())}"
        
        # Log the full error for debugging
        log.error(f"Error {error_id} in {function_name} for user {user_id}: {str(error)}", exc_info=True)
        
        # Determine user-friendly message
        error_str = str(error).lower()
        if 'rate limit' in error_str:
            message = "Too many requests. Please wait a moment before trying again."
        elif 'authentication' in error_str or 'unauthorized' in error_str:
            message = "Authentication failed. Please check your access permissions."
        elif 'invalid' in error_str and 'input' in error_str:
            message = "Invalid input provided. Please check your parameters and try again."
        elif 'network' in error_str or 'timeout' in error_str:
            message = "Network error occurred. Please try again in a moment."
        else:
            message = f"An error occurred while processing your request. Error ID: {error_id}"
        
        base_response = {
            "status": "error",
            "message": message,
            "error_id": error_id
        }
        
        # Add function-specific empty data structure
        if function_name == 'find_places':
            base_response["places"] = []
        elif function_name == 'get_directions':
            base_response["directions"] = None
        elif function_name == 'place_details':
            base_response["place_details"] = None
        
        return base_response

    async def _make_request(self, endpoint: str, data: Dict[str, Any], user_token: str) -> Dict[str, Any]:
        """
        Make authenticated request to OpenWebUI maps router with enhanced error handling
        
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
            "Content-Type": "application/json",
            "User-Agent": "OpenWebUI-Maps-Tool/1.0"
        }
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 401:
                        raise Exception("Authentication failed - invalid or expired token")
                    elif response.status == 403:
                        raise Exception("Access forbidden - insufficient permissions")
                    elif response.status == 429:
                        raise Exception("Rate limit exceeded - too many requests")
                    else:
                        error_text = await response.text()
                        raise Exception(f"Maps API error ({response.status}): {error_text}")
        except aiohttp.ClientTimeoutError:
            raise Exception("Request timeout - maps service is taking too long to respond")
        except aiohttp.ClientConnectorError:
            raise Exception("Network error - unable to connect to maps service")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error calling maps API: {str(e)}")
        except Exception as e:
            if "Maps API error" in str(e) or "Authentication" in str(e):
                raise  # Re-raise API-specific errors
            raise Exception(f"Unexpected error calling maps API: {str(e)}")

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
        user_id = __user__.get('id', 'anonymous')
        
        try:
            # Validate user access and rate limits
            if not self._validate_user_access(__user__, 'find_places'):
                return self._format_error_response('find_places', Exception("Rate limit exceeded"), user_id)
            
            # Validate and enhance parameters
            validated_params = self._validate_and_enhance_parameters(
                'find_places',
                location=location,
                query=query,
                type=type,
                radius=radius
            )
            
            # Get user token for authentication
            user_token = __user__.get("token", {}).get("credentials", "")
            if not user_token:
                return self._format_error_response('find_places', Exception("User authentication required"), user_id)
            
            # Prepare request data (remove internal enhancements)
            request_data = {k: v for k, v in validated_params.items() if not k.startswith('_')}
            
            # Convert enum to string if needed
            if request_data.get('type') and hasattr(request_data['type'], 'value'):
                request_data['type'] = request_data['type'].value
            
            log.info(f"find_places request for user {user_id}: {request_data}")
            
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
            
            # Build success response with enhanced information
            result = {
                "places": formatted_places,
                "status": "success",
                "message": f"Found {len(formatted_places)} places matching '{query}' near {location}",
                "search_info": {
                    "original_location": location,
                    "normalized_location": validated_params.get('location', location),
                    "original_query": query,
                    "enhanced_query": validated_params.get('_enhancements', {}).get('enhanced_query', query),
                    "suggested_type": validated_params.get('_enhancements', {}).get('suggested_type'),
                    "used_type": validated_params.get('type'),
                    "radius_meters": validated_params.get('radius', radius)
                }
            }
            
            log.info(f"find_places success for user {user_id}: found {len(formatted_places)} places")
            return result
            
        except ValueError as e:
            # Input validation errors
            return self._format_error_response('find_places', e, user_id)
        except Exception as e:
            # All other errors
            return self._format_error_response('find_places', e, user_id)

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
        user_id = __user__.get('id', 'anonymous')
        
        try:
            # Validate user access and rate limits
            if not self._validate_user_access(__user__, 'get_directions'):
                return self._format_error_response('get_directions', Exception("Rate limit exceeded"), user_id)
            
            # Validate and enhance parameters
            validated_params = self._validate_and_enhance_parameters(
                'get_directions',
                origin=origin,
                destination=destination,
                mode=mode
            )
            
            # Get user token for authentication
            user_token = __user__.get("token", {}).get("credentials", "")
            if not user_token:
                return self._format_error_response('get_directions', Exception("User authentication required"), user_id)
            
            # Handle travel mode (convert enum to string if needed)
            mode_value = validated_params['mode']
            if isinstance(mode_value, TravelMode):
                mode_value = mode_value.value
            
            # Prepare request data
            request_data = {
                "origin": validated_params['origin'],
                "destination": validated_params['destination'],
                "mode": mode_value
            }
            
            log.info(f"get_directions request for user {user_id}: {request_data}")
            
            # Make request to maps router
            response = await self._make_request("/maps/get_directions", request_data, user_token)
            
            # Format response for LLM consumption
            directions_data = response.get("directions", {})
            
            formatted_directions = {
                "summary": {
                    "origin": directions_data.get("origin", validated_params['origin']),
                    "destination": directions_data.get("destination", validated_params['destination']), 
                    "distance": directions_data.get("distance", ""),
                    "duration": directions_data.get("duration", ""),
                    "travel_mode": mode_value.title()
                },
                "steps": directions_data.get("steps", []),
                "maps_url": directions_data.get("maps_url", ""),
                "warnings": directions_data.get("warnings", [])
            }
            
            result = {
                "directions": formatted_directions,
                "status": "success", 
                "message": f"Directions from {origin} to {destination} via {mode_value}",
                "route_info": {
                    "original_origin": origin,
                    "normalized_origin": validated_params['origin'],
                    "original_destination": destination,
                    "normalized_destination": validated_params['destination'],
                    "travel_mode": mode_value,
                    "step_count": len(formatted_directions.get("steps", []))
                }
            }
            
            log.info(f"get_directions success for user {user_id}: {len(formatted_directions.get('steps', []))} steps")
            return result
            
        except ValueError as e:
            # Input validation errors
            return self._format_error_response('get_directions', e, user_id)
        except Exception as e:
            # All other errors
            return self._format_error_response('get_directions', e, user_id)

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
        user_id = __user__.get('id', 'anonymous')
        
        try:
            # Validate user access and rate limits
            if not self._validate_user_access(__user__, 'place_details'):
                return self._format_error_response('place_details', Exception("Rate limit exceeded"), user_id)
            
            # Validate and enhance parameters
            validated_params = self._validate_and_enhance_parameters(
                'place_details',
                place_id=place_id
            )
            
            # Get user token for authentication
            user_token = __user__.get("token", {}).get("credentials", "")
            if not user_token:
                return self._format_error_response('place_details', Exception("User authentication required"), user_id)
            
            # Prepare request data
            request_data = {
                "place_id": validated_params['place_id']
            }
            
            log.info(f"place_details request for user {user_id}: {request_data}")
            
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
                    "place_id": validated_params['place_id']
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
            
            result = {
                "place_details": formatted_details,
                "status": "success",
                "message": f"Retrieved details for {details.get('name', 'place')}",
                "detail_info": {
                    "place_id": validated_params['place_id'],
                    "place_name": details.get('name', 'Unknown'),
                    "review_count": len(place_data.get("reviews", [])),
                    "photo_count": len(place_data.get("photos", [])),
                    "has_phone": bool(details.get("phone")),
                    "has_website": bool(details.get("website")),
                    "has_hours": bool(details.get("opening_hours"))
                }
            }
            
            log.info(f"place_details success for user {user_id}: {details.get('name', 'Unknown')}")
            return result
            
        except ValueError as e:
            # Input validation errors
            return self._format_error_response('place_details', e, user_id)
        except Exception as e:
            # All other errors
            return self._format_error_response('place_details', e, user_id) 