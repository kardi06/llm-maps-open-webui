"""
title: Google Maps Tool
description: Find places, get directions, and retrieve place details using natural language queries
version: 1.0.0
required_open_webui_version: 0.4.0
license: MIT
requirements: aiohttp
"""

import logging
import os
import aiohttp
import json
import uuid
import time
from typing import Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field, validator

log = logging.getLogger(__name__)


# Error handling and monitoring utilities
class MapsToolError:
    """Utility class for generating structured error responses with monitoring support"""
    
    @staticmethod
    def create_error_response(
        function_name: str,
        error_message: str,
        error_type: str = "general",
        status_code: Optional[int] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a structured error response with logging and monitoring support
        
        Args:
            function_name: Name of the function where error occurred
            error_message: Description of the error
            error_type: Category of error (auth, rate_limit, validation, api, network, general)
            status_code: HTTP status code if applicable
            user_id: User ID for audit logging
            
        Returns:
            Structured error response for LLM consumption
        """
        error_id = str(uuid.uuid4())[:8]  # Short error ID for reference
        timestamp = int(time.time())
        
        # Create user-friendly error message based on type
        user_message = MapsToolError._get_user_friendly_message(error_type, error_message, status_code)
        
        # Log error for monitoring
        log.error(
            f"Maps tool error in {function_name} [ID: {error_id}] "
            f"Type: {error_type}, Status: {status_code}, User: {user_id}, "
            f"Error: {error_message}"
        )
        
        # Return structured error response
        return {
            "status": "error",
            "message": user_message,
            "error_details": {
                "error_id": error_id,
                "function": function_name,
                "type": error_type,
                "timestamp": timestamp,
                "original_error": error_message
            }
        }
    
    @staticmethod
    def _get_user_friendly_message(error_type: str, error_message: str, status_code: Optional[int]) -> str:
        """Generate user-friendly error messages based on error type"""
        if error_type == "auth":
            return "Authentication failed. Please check your credentials and try again."
        elif error_type == "rate_limit":
            return "Too many requests. Please wait a moment and try again."
        elif error_type == "validation":
            return f"Invalid input: {error_message}"
        elif error_type == "api" and status_code == 404:
            return "The requested location or place could not be found."
        elif error_type == "api" and status_code == 400:
            return "Invalid request. Please check your input and try again."
        elif error_type == "network":
            return "Network connection failed. Please check your internet connection and try again."
        else:
            return f"An error occurred while processing your request: {error_message}"
    
    @staticmethod
    def create_success_response(
        function_name: str,
        data: Dict[str, Any],
        message: str,
        additional_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create a structured success response optimized for LLM consumption
        
        Args:
            function_name: Name of the function
            data: Main response data
            message: Human-readable success message
            additional_info: Additional context information
            
        Returns:
            Structured success response
        """
        response = {
            "status": "success",
            "message": message,
            **data  # Merge main data into response
        }
        
        if additional_info:
            response.update(additional_info)
        
        # Log successful operation for monitoring
        log.info(f"Maps tool success in {function_name}: {message}")
        
        return response


# Pydantic Models for Parameter Validation
class PlaceType(str, Enum):
    """Enumeration of supported place types for filtering searches"""
    restaurant = "restaurant"
    gas_station = "gas_station" 
    hospital = "hospital"
    school = "school"
    bank = "bank"
    pharmacy = "pharmacy"
    grocery_store = "grocery_store"
    tourist_attraction = "tourist_attraction"


class TravelMode(str, Enum):
    """Enumeration of supported travel modes for directions"""
    driving = "driving"
    walking = "walking"
    transit = "transit"
    bicycling = "bicycling"


# Security and validation utilities
class LocationValidator:
    """Input validation and sanitization for location data"""
    
    @staticmethod
    def validate_location(location: str) -> bool:
        """Validate location string for security and format"""
        if not location or not isinstance(location, str):
            return False
        
        # Check length constraints
        if len(location.strip()) < 2 or len(location) > 200:
            return False
        
        # Check for malicious patterns
        dangerous_patterns = [
            '<script', '</script>', 'javascript:', 'data:', 'vbscript:',
            'onload=', 'onerror=', 'onclick=', '<iframe', '</iframe>',
            'eval(', 'alert(', 'document.', 'window.'
        ]
        
        location_lower = location.lower()
        for pattern in dangerous_patterns:
            if pattern in location_lower:
                return False
        
        return True
    
    @staticmethod
    def sanitize_location(location: str) -> str:
        """Sanitize location string"""
        if not isinstance(location, str):
            return ""
        
        # Remove dangerous characters and normalize whitespace
        import re
        sanitized = re.sub(r'[<>"\'\`]', '', location)
        sanitized = re.sub(r'\s+', ' ', sanitized.strip())
        return sanitized[:200]  # Enforce length limit
    
    @staticmethod
    def validate_place_id(place_id: str) -> bool:
        """Validate Google Places ID format"""
        if not place_id or not isinstance(place_id, str):
            return False
        
        # Google Place IDs typically start with ChIJ and are alphanumeric + special chars
        if len(place_id) < 10 or len(place_id) > 200:
            return False
        
        # Basic format check (starts with known prefixes)
        valid_prefixes = ['ChIJ', 'EiQ', 'EkQ', 'EmQ']
        if not any(place_id.startswith(prefix) for prefix in valid_prefixes):
            return False
        
        return True


class MapsUsageTracker:
    """Rate limiting and usage monitoring for maps functions"""
    
    # Class-level storage for usage tracking (in production, use Redis or database)
    _usage_data = {}
    
    # Rate limits per function per hour
    RATE_LIMITS = {
        "find_places": 100,     # 100 searches per hour
        "get_directions": 50,   # 50 direction requests per hour
        "place_details": 200    # 200 detail requests per hour (lighter operation)
    }
    
    @classmethod
    def check_rate_limit(cls, user_id: str, function_name: str) -> bool:
        """
        Check if user has exceeded rate limit for function
        
        Args:
            user_id: User identifier
            function_name: Name of the function being called
            
        Returns:
            True if within limit, False if exceeded
        """
        if not user_id or function_name not in cls.RATE_LIMITS:
            return True  # Allow if no user ID or unknown function
        
        current_time = time.time()
        key = f"{user_id}:{function_name}"
        
        # Initialize if not exists
        if key not in cls._usage_data:
            cls._usage_data[key] = []
        
        # Remove old entries (older than 1 hour)
        cls._usage_data[key] = [
            timestamp for timestamp in cls._usage_data[key] 
            if current_time - timestamp < 3600
        ]
        
        # Check if under limit
        current_usage = len(cls._usage_data[key])
        limit = cls.RATE_LIMITS[function_name]
        
        if current_usage >= limit:
            log.warning(f"Rate limit exceeded for user {user_id} on {function_name}: {current_usage}/{limit}")
            return False
        
        # Record this usage
        cls._usage_data[key].append(current_time)
        return True
    
    @classmethod
    def get_usage_stats(cls, user_id: str) -> Dict[str, Any]:
        """Get current usage statistics for a user"""
        current_time = time.time()
        stats = {}
        
        for function_name in cls.RATE_LIMITS:
            key = f"{user_id}:{function_name}"
            if key in cls._usage_data:
                # Count recent usage
                recent_usage = len([
                    t for t in cls._usage_data[key] 
                    if current_time - t < 3600
                ])
                stats[function_name] = {
                    "used": recent_usage,
                    "limit": cls.RATE_LIMITS[function_name],
                    "remaining": max(0, cls.RATE_LIMITS[function_name] - recent_usage)
                }
            else:
                stats[function_name] = {
                    "used": 0,
                    "limit": cls.RATE_LIMITS[function_name],
                    "remaining": cls.RATE_LIMITS[function_name]
                }
        
        return stats


class SecurityValidator:
    """Security validation for maps tool access"""
    
    @staticmethod
    def validate_user_permissions(user: Dict[str, Any], function_name: str) -> bool:
        """
        Validate user permissions for maps functionality
        
        Args:
            user: User context from OpenWebUI
            function_name: Name of the function being called
            
        Returns:
            True if user has permission, False otherwise
        """
        if not user:
            log.warning(f"No user context provided for {function_name}")
            return False
        
        # Check if user has required role (basic user role should be sufficient)
        user_role = user.get("role", "user")
        if user_role not in ["user", "admin"]:
            log.warning(f"Invalid user role {user_role} for maps access")
            return False
        
        # Check if user account is active
        if user.get("is_active") is False:
            log.warning(f"Inactive user {user.get('id')} attempted maps access")
            return False
        
        return True
    
    @staticmethod
    def log_security_event(
        event_type: str, 
        user_id: Optional[str], 
        function_name: str, 
        details: str
    ) -> None:
        """Log security-related events for audit purposes"""
        log.warning(
            f"SECURITY EVENT - Type: {event_type}, Function: {function_name}, "
            f"User: {user_id}, Details: {details}"
        )


# Natural Language Processing utilities
class LocationParser:
    """Enhanced location parsing and normalization for natural language queries"""
    
    @staticmethod
    def normalize_location(location: str) -> str:
        """Normalize location strings for better API compatibility"""
        if not isinstance(location, str):
            return ""
        
        # Handle common variations
        location = location.strip()
        
        # Normalize common location expressions
        normalizations = {
            'current location': 'current location',
            'my location': 'current location',
            'here': 'current location',
            'near me': 'current location',
            'where i am': 'current location',
        }
        
        location_lower = location.lower()
        for phrase, normalized in normalizations.items():
            if phrase in location_lower:
                return normalized
        
        return location
    
    @staticmethod
    def extract_coordinates(location: str) -> Optional[Dict[str, float]]:
        """Extract coordinates if location string contains them"""
        import re
        
        # Pattern for latitude,longitude (e.g., "-6.2088,106.8456")
        coord_pattern = r'(-?\d+\.?\d*),\s*(-?\d+\.?\d*)'
        match = re.search(coord_pattern, location)
        
        if match:
            try:
                lat, lng = float(match.group(1)), float(match.group(2))
                # Basic validation for reasonable coordinate ranges
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    return {"lat": lat, "lng": lng}
            except ValueError:
                pass
        
        return None


class QueryEnhancer:
    """Enhance search queries based on natural language patterns"""
    
    # Common place type keywords and their mappings
    PLACE_TYPE_KEYWORDS = {
        'restaurant': ['restaurant', 'food', 'eat', 'dining', 'cafe', 'eatery', 'bistro'],
        'gas_station': ['gas', 'petrol', 'fuel', 'gasoline', 'station'],
        'hospital': ['hospital', 'medical', 'clinic', 'health', 'doctor', 'emergency'],
        'school': ['school', 'education', 'university', 'college', 'academy'],
        'bank': ['bank', 'atm', 'banking', 'financial'],
        'pharmacy': ['pharmacy', 'drugstore', 'medicine', 'drugs'],
        'grocery_store': ['grocery', 'supermarket', 'market', 'store'],
        'tourist_attraction': ['tourist', 'attraction', 'monument', 'museum', 'park']
    }
    
    @staticmethod
    def suggest_place_type(query: str) -> Optional[PlaceType]:
        """Suggest appropriate place type based on query content"""
        if not query:
            return None
        
        query_lower = query.lower()
        
        for place_type, keywords in QueryEnhancer.PLACE_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    try:
                        return PlaceType(place_type)
                    except ValueError:
                        continue
        
        return None
    
    @staticmethod
    def enhance_query(query: str, suggested_type: Optional[PlaceType] = None) -> str:
        """Enhance query for better search results"""
        if not query:
            return ""
        
        # Basic query cleanup
        query = query.strip()
        
        # Remove redundant words if place type is specified
        if suggested_type:
            type_keywords = QueryEnhancer.PLACE_TYPE_KEYWORDS.get(suggested_type.value, [])
            query_words = query.lower().split()
            
            # Remove type keywords from query to avoid redundancy
            filtered_words = [word for word in query_words if word not in type_keywords]
            if filtered_words:  # Only update if we have remaining words
                query = ' '.join(filtered_words)
        
        return query
    
    @staticmethod
    def extract_travel_preferences(query: str) -> Dict[str, Any]:
        """Extract travel preferences from natural language"""
        preferences = {}
        query_lower = query.lower()
        
        # Extract travel mode preferences
        mode_indicators = {
            'driving': ['drive', 'driving', 'car', 'vehicle'],
            'walking': ['walk', 'walking', 'foot', 'pedestrian'],
            'transit': ['transit', 'public', 'bus', 'train', 'metro'],
            'bicycling': ['bike', 'bicycle', 'cycling', 'biking']
        }
        
        for mode, indicators in mode_indicators.items():
            if any(indicator in query_lower for indicator in indicators):
                preferences['preferred_mode'] = mode
                break
        
        # Extract urgency/speed preferences
        if any(word in query_lower for word in ['fast', 'quick', 'fastest', 'shortest']):
            preferences['priority'] = 'speed'
        elif any(word in query_lower for word in ['scenic', 'beautiful', 'avoid highway']):
            preferences['priority'] = 'scenic'
        
        return preferences


class NaturalLanguageProcessor:
    """Main class for processing natural language requests"""
    
    @staticmethod
    def enhance_find_places_parameters(
        location: str, 
        query: str, 
        type_hint: Optional[PlaceType] = None
    ) -> Dict[str, Any]:
        """
        Enhance find_places parameters based on natural language analysis
        
        Returns enhanced parameters with suggestions
        """
        enhanced = {
            'location': LocationParser.normalize_location(location),
            'query': query,
            'type': type_hint,
            'enhancements': {}
        }
        
        # Suggest place type if not provided
        if not type_hint:
            suggested_type = QueryEnhancer.suggest_place_type(query)
            if suggested_type:
                enhanced['type'] = suggested_type
                enhanced['enhancements']['suggested_type'] = suggested_type.value
        
        # Enhance query
        enhanced['query'] = QueryEnhancer.enhance_query(query, enhanced['type'])
        
        # Extract coordinates if present
        coords = LocationParser.extract_coordinates(location)
        if coords:
            enhanced['enhancements']['coordinates'] = coords
        
        return enhanced
    
    @staticmethod
    def enhance_directions_parameters(
        origin: str, 
        destination: str, 
        mode_hint: Optional[TravelMode] = None
    ) -> Dict[str, Any]:
        """
        Enhance get_directions parameters based on natural language analysis
        
        Returns enhanced parameters with suggestions
        """
        enhanced = {
            'origin': LocationParser.normalize_location(origin),
            'destination': LocationParser.normalize_location(destination),
            'mode': mode_hint or TravelMode.driving,
            'enhancements': {}
        }
        
        # Extract travel preferences from the request context
        combined_text = f"{origin} {destination}"
        preferences = QueryEnhancer.extract_travel_preferences(combined_text)
        
        if 'preferred_mode' in preferences and not mode_hint:
            try:
                enhanced['mode'] = TravelMode(preferences['preferred_mode'])
                enhanced['enhancements']['suggested_mode'] = preferences['preferred_mode']
            except ValueError:
                pass
        
        if 'priority' in preferences:
            enhanced['enhancements']['travel_priority'] = preferences['priority']
        
        return enhanced


class Tools:
    """
    Google Maps Tool for finding places, getting directions, and retrieving place details.
    
    This tool integrates with the OpenWebUI maps router endpoints to provide
    natural language access to Google Maps functionality. It follows OpenWebUI
    tool calling patterns and integrates seamlessly with the existing middleware.
    
    The tool functions are automatically discovered by OpenWebUI's get_functions_from_tool()
    and converted to OpenAI function specifications via get_tool_specs().
    """
    
    def __init__(self):
        # Get backend URL from environment or use default
        backend_url = os.getenv("OPENWEBUI_BACKEND_URL", "http://localhost:8080")
        self.base_url = f"{backend_url}/api/v1/maps"
        self.timeout = aiohttp.ClientTimeout(total=30)
        log.info(f"Maps tool initialized with base URL: {self.base_url}")
    
    async def find_places(
        self,
        location: str,
        query: str,
        type: Optional[PlaceType] = None,
        radius: int = Field(default=5000, ge=100, le=50000),
        __user__: dict = {},
        __id__: str = None
    ) -> Dict[str, Any]:
        """
        Find places of interest using natural language search queries.
        
        This function helps users discover nearby places by searching for specific types of businesses,
        services, or points of interest. It's ideal for queries like "Find sushi restaurants near me",
        "Show gas stations within 2km", or "Where are the hospitals in Jakarta".
        
        Args:
            location (str): The location to search around. Can be:
                - Address: "123 Main Street, Jakarta"
                - Landmark: "Senayan City Mall"
                - City/Area: "Jakarta", "Kemang"
                - Coordinates: "-6.2088,106.8456"
                - Relative: "near me", "current location"
            query (str): What you're looking for. Examples:
                - "restaurants" or "sushi restaurants"
                - "gas stations" or "petrol stations"
                - "hospitals" or "medical centers"
                - "coffee shops" or "Starbucks"
            type (PlaceType, optional): Filter by specific place category:
                - restaurant: Food establishments
                - gas_station: Fuel stations
                - hospital: Medical facilities  
                - school: Educational institutions
                - bank: Financial institutions
                - pharmacy: Drug stores
                - grocery_store: Supermarkets
                - tourist_attraction: Points of interest
            radius (int): Search radius in meters (100-50000, default: 5000)
            
        Returns:
            Dict with:
                - places: List of found places with name, address, coordinates, rating
                - status: "success" or "error"
                - message: Human-readable result description
                - search_query: What was searched for
                - search_location: Where the search was centered
                
        Examples:
            - find_places("Jakarta", "sushi restaurants", type="restaurant")
            - find_places("Senayan", "gas stations", radius=2000)
            - find_places("-6.2088,106.8456", "hospitals")
        """
        try:
            # Security and validation checks
            user_id = __user__.get("id") if __user__ else None
            
            # Validate user permissions
            if not SecurityValidator.validate_user_permissions(__user__, "find_places"):
                SecurityValidator.log_security_event(
                    "PERMISSION_DENIED", user_id, "find_places", "User lacks required permissions"
                )
                error_response = MapsToolError.create_error_response(
                    "find_places", "Access denied: insufficient permissions", 
                    "auth", user_id=user_id
                )
                error_response["places"] = []
                return error_response
            
            # Check rate limiting
            if not MapsUsageTracker.check_rate_limit(user_id, "find_places"):
                error_response = MapsToolError.create_error_response(
                    "find_places", "Rate limit exceeded: too many requests", 
                    "rate_limit", user_id=user_id
                )
                error_response["places"] = []
                return error_response
            
            # Validate and sanitize input parameters
            if not LocationValidator.validate_location(location):
                SecurityValidator.log_security_event(
                    "INVALID_INPUT", user_id, "find_places", f"Invalid location: {location}"
                )
                error_response = MapsToolError.create_error_response(
                    "find_places", "Invalid location format", 
                    "validation", user_id=user_id
                )
                error_response["places"] = []
                return error_response
            
            if not query or len(query.strip()) < 1 or len(query) > 200:
                error_response = MapsToolError.create_error_response(
                    "find_places", "Query must be between 1 and 200 characters", 
                    "validation", user_id=user_id
                )
                error_response["places"] = []
                return error_response
            
            # Sanitize inputs
            location = LocationValidator.sanitize_location(location)
            query = LocationValidator.sanitize_location(query)  # Apply same sanitization
            
            # Apply natural language processing enhancements
            enhanced_params = NaturalLanguageProcessor.enhance_find_places_parameters(
                location, query, type
            )
            
            # Use enhanced parameters
            location = enhanced_params['location']
            query = enhanced_params['query']
            if not type and enhanced_params['type']:  # Use suggested type if none provided
                type = enhanced_params['type']
            
            # Extract user token for authentication (OpenWebUI middleware integration)
            user_token = __user__.get("token") if __user__ else None
            
            # Map LLM function call parameters to maps API parameters
            request_data = {
                "location": location,  # Sanitized parameter mapping
                "query": query,        # Sanitized parameter mapping
                "radius": radius       # Validated integer parameter
            }
            
            # Handle enum parameter mapping (PlaceType -> string)
            if type:
                request_data["type"] = type.value if isinstance(type, PlaceType) else type
            
            # Set up headers with authentication
            headers = {"Content-Type": "application/json"}
            if user_token:
                headers["Authorization"] = f"Bearer {user_token}"
            
            # Make request to maps router
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/find_places",
                    json=request_data,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        places = result.get("places", [])
                        
                        # Create enhanced success response for LLM consumption
                        additional_info = {
                            "search_query": query,
                            "search_location": location,
                            "search_radius": f"{radius}m"
                        }
                        
                        # Include natural language processing insights
                        if enhanced_params.get('enhancements'):
                            additional_info['nlp_enhancements'] = enhanced_params['enhancements']
                        
                        return MapsToolError.create_success_response(
                            function_name="find_places",
                            data={"places": places},
                            message=f"Found {len(places)} places matching your search for '{query}' near {location}",
                            additional_info=additional_info
                        )
                    else:
                        error_detail = await response.text()
                        error_type = "auth" if response.status == 401 else \
                                   "rate_limit" if response.status == 429 else \
                                   "api"
                        
                        error_response = MapsToolError.create_error_response(
                            function_name="find_places",
                            error_message=error_detail,
                            error_type=error_type,
                            status_code=response.status,
                            user_id=__user__.get("id") if __user__ else None
                        )
                        error_response["places"] = []  # Add expected field for consistency
                        return error_response
                        
        except aiohttp.ClientError as e:
            # Network/connection errors
            error_response = MapsToolError.create_error_response(
                function_name="find_places",
                error_message=str(e),
                error_type="network",
                user_id=__user__.get("id") if __user__ else None
            )
            error_response["places"] = []
            return error_response
        except Exception as e:
            # General errors
            error_response = MapsToolError.create_error_response(
                function_name="find_places",
                error_message=str(e),
                error_type="general",
                user_id=__user__.get("id") if __user__ else None
            )
            error_response["places"] = []
            return error_response
    
    async def get_directions(
        self,
        origin: str,
        destination: str,
        mode: TravelMode = TravelMode.driving,
        __user__: dict = {},
        __id__: str = None
    ) -> Dict[str, Any]:
        """
        Get turn-by-turn directions and route information between two locations.
        
        This function provides detailed navigation instructions for traveling from one location 
        to another. It's perfect for queries like "How do I get from Jakarta to Bandung?",
        "Show me walking directions to the nearest hospital", or "What's the best route by car?"
        
        Args:
            origin (str): Starting point for the journey. Can be:
                - Full address: "Jalan Sudirman 123, Jakarta Pusat"
                - Landmark: "Monas", "Senayan City"
                - City: "Jakarta", "Bandung"
                - Coordinates: "-6.2088,106.8456"
                - Relative: "current location", "my location"
            destination (str): Ending point for the journey. Same format as origin:
                - Address, landmark, city, or coordinates
                - Business name: "Starbucks Senayan City"
            mode (TravelMode): How you want to travel:
                - driving: By car (default) - fastest routes, highways allowed
                - walking: On foot - pedestrian paths, shorter distances
                - transit: Public transport - buses, trains, metro
                - bicycling: By bicycle - bike-friendly routes
                
        Returns:
            Dict with:
                - route: Detailed route information including:
                    - steps: Turn-by-turn instructions
                    - distance: Total travel distance
                    - duration: Estimated travel time
                    - overview_polyline: Route geometry
                - status: "success" or "error"
                - message: Human-readable result description
                - travel_mode: The mode of transportation used
                - summary: Quick overview with distance and duration
                
        Examples:
            - get_directions("Jakarta", "Bandung", mode="driving")
            - get_directions("Senayan City", "Monas", mode="walking")
            - get_directions("current location", "nearest hospital", mode="transit")
        """
        try:
            # Security and validation checks
            user_id = __user__.get("id") if __user__ else None
            
            # Validate user permissions
            if not SecurityValidator.validate_user_permissions(__user__, "get_directions"):
                SecurityValidator.log_security_event(
                    "PERMISSION_DENIED", user_id, "get_directions", "User lacks required permissions"
                )
                error_response = MapsToolError.create_error_response(
                    "get_directions", "Access denied: insufficient permissions", 
                    "auth", user_id=user_id
                )
                error_response["route"] = {}
                return error_response
            
            # Check rate limiting
            if not MapsUsageTracker.check_rate_limit(user_id, "get_directions"):
                error_response = MapsToolError.create_error_response(
                    "get_directions", "Rate limit exceeded: too many requests", 
                    "rate_limit", user_id=user_id
                )
                error_response["route"] = {}
                return error_response
            
            # Validate and sanitize input parameters
            if not LocationValidator.validate_location(origin):
                SecurityValidator.log_security_event(
                    "INVALID_INPUT", user_id, "get_directions", f"Invalid origin: {origin}"
                )
                error_response = MapsToolError.create_error_response(
                    "get_directions", "Invalid origin location format", 
                    "validation", user_id=user_id
                )
                error_response["route"] = {}
                return error_response
            
            if not LocationValidator.validate_location(destination):
                SecurityValidator.log_security_event(
                    "INVALID_INPUT", user_id, "get_directions", f"Invalid destination: {destination}"
                )
                error_response = MapsToolError.create_error_response(
                    "get_directions", "Invalid destination location format", 
                    "validation", user_id=user_id
                )
                error_response["route"] = {}
                return error_response
            
            # Sanitize inputs
            origin = LocationValidator.sanitize_location(origin)
            destination = LocationValidator.sanitize_location(destination)
            
            # Apply natural language processing enhancements
            enhanced_params = NaturalLanguageProcessor.enhance_directions_parameters(
                origin, destination, mode
            )
            
            # Use enhanced parameters
            origin = enhanced_params['origin']
            destination = enhanced_params['destination']
            if enhanced_params['mode'] != mode:  # Use suggested mode if different
                mode = enhanced_params['mode']
            
            # Extract user token for authentication (OpenWebUI middleware integration)
            user_token = __user__.get("token") if __user__ else None
            
            # Map LLM function call parameters to maps API parameters
            request_data = {
                "origin": origin,           # Sanitized parameter mapping
                "destination": destination, # Sanitized parameter mapping
                "mode": mode.value if isinstance(mode, TravelMode) else mode  # Enum mapping
            }
            
            # Set up headers with authentication
            headers = {"Content-Type": "application/json"}
            if user_token:
                headers["Authorization"] = f"Bearer {user_token}"
            
            # Make request to maps router
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/get_directions",
                    json=request_data,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        route = result.get("route", {})
                        
                        # Create enhanced success response for LLM consumption
                        additional_info = {
                            "travel_mode": mode.value if hasattr(mode, 'value') else mode,
                            "origin": origin,
                            "destination": destination,
                            "summary": {
                                "distance": route.get("distance", "Unknown"),
                                "duration": route.get("duration", "Unknown")
                            }
                        }
                        
                        # Include natural language processing insights
                        if enhanced_params.get('enhancements'):
                            additional_info['nlp_enhancements'] = enhanced_params['enhancements']
                        
                        return MapsToolError.create_success_response(
                            function_name="get_directions",
                            data={"route": route},
                            message=f"Route from {origin} to {destination} found via {mode.value if hasattr(mode, 'value') else mode}",
                            additional_info=additional_info
                        )
                    else:
                        error_detail = await response.text()
                        error_type = "auth" if response.status == 401 else \
                                   "rate_limit" if response.status == 429 else \
                                   "api"
                        
                        error_response = MapsToolError.create_error_response(
                            function_name="get_directions",
                            error_message=error_detail,
                            error_type=error_type,
                            status_code=response.status,
                            user_id=__user__.get("id") if __user__ else None
                        )
                        error_response["route"] = {}  # Add expected field for consistency
                        return error_response
                        
        except aiohttp.ClientError as e:
            # Network/connection errors
            error_response = MapsToolError.create_error_response(
                function_name="get_directions",
                error_message=str(e),
                error_type="network",
                user_id=__user__.get("id") if __user__ else None
            )
            error_response["route"] = {}
            return error_response
        except Exception as e:
            # General errors
            error_response = MapsToolError.create_error_response(
                function_name="get_directions",
                error_message=str(e),
                error_type="general",
                user_id=__user__.get("id") if __user__ else None
            )
            error_response["route"] = {}
            return error_response
    
    async def place_details(
        self,
        place_id: str,
        __user__: dict = {},
        __id__: str = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive information about a specific place using its Google Places ID.
        
        This function retrieves detailed information about a business or location, including
        contact details, operating hours, reviews, photos, and more. It's useful for 
        follow-up queries like "Tell me more about this restaurant" or "What are the hours
        for this hospital?"
        
        Args:
            place_id (str): The unique Google Places identifier for the location.
                This is typically obtained from a previous find_places search result.
                Format: "ChIJ..." (starts with ChIJ for most places)
                Examples:
                - "ChIJN1t_tDeuEmsRUsoyG83frY4" (Google Sydney office)
                - "ChIJrTLr-GyuEmsRBfy61i59si0" (Opera House)
                
        Returns:
            Dict with:
                - details: Comprehensive place information including:
                    - name: Official business/place name
                    - address: Full formatted address
                    - phone: Contact phone number
                    - website: Official website URL
                    - hours: Operating hours for each day
                    - rating: Average user rating
                    - reviews: Sample user reviews
                    - photos: URLs to place photos
                    - price_level: Cost indicator ($ to $$$$)
                - status: "success" or "error"
                - message: Human-readable result description
                - place_name: Quick reference to the place name
                
        Examples:
            - place_details("ChIJN1t_tDeuEmsRUsoyG83frY4")
            - Used after: find_places("Jakarta", "restaurants") → get place_id → place_details(place_id)
            
        Note:
            The place_id parameter is usually obtained from the results of a find_places call.
            Each place in the search results includes its unique place_id.
        """
        try:
            # Security and validation checks
            user_id = __user__.get("id") if __user__ else None
            
            # Validate user permissions
            if not SecurityValidator.validate_user_permissions(__user__, "place_details"):
                SecurityValidator.log_security_event(
                    "PERMISSION_DENIED", user_id, "place_details", "User lacks required permissions"
                )
                error_response = MapsToolError.create_error_response(
                    "place_details", "Access denied: insufficient permissions", 
                    "auth", user_id=user_id
                )
                error_response["details"] = {}
                return error_response
            
            # Check rate limiting
            if not MapsUsageTracker.check_rate_limit(user_id, "place_details"):
                error_response = MapsToolError.create_error_response(
                    "place_details", "Rate limit exceeded: too many requests", 
                    "rate_limit", user_id=user_id
                )
                error_response["details"] = {}
                return error_response
            
            # Validate place_id format
            if not LocationValidator.validate_place_id(place_id):
                SecurityValidator.log_security_event(
                    "INVALID_INPUT", user_id, "place_details", f"Invalid place_id: {place_id}"
                )
                error_response = MapsToolError.create_error_response(
                    "place_details", "Invalid place ID format", 
                    "validation", user_id=user_id
                )
                error_response["details"] = {}
                return error_response
            
            # Extract user token for authentication (OpenWebUI middleware integration)
            user_token = __user__.get("token") if __user__ else None
            
            # Map LLM function call parameters to maps API parameters
            request_data = {
                "place_id": place_id  # Validated parameter mapping
            }
            
            # Set up headers with authentication
            headers = {"Content-Type": "application/json"}
            if user_token:
                headers["Authorization"] = f"Bearer {user_token}"
            
            # Make request to maps router
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/place_details",
                    json=request_data,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        details = result.get("details", {})
                        place_name = details.get("name", "Unknown Place")
                        
                        # Create enhanced success response for LLM consumption
                        return MapsToolError.create_success_response(
                            function_name="place_details",
                            data={"details": details},
                            message=f"Retrieved detailed information for {place_name}",
                            additional_info={
                                "place_id": place_id,
                                "place_name": place_name,
                                "has_rating": "rating" in details,
                                "has_hours": "hours" in details,
                                "has_contact": any(key in details for key in ["phone", "website"])
                            }
                        )
                    else:
                        error_detail = await response.text()
                        error_type = "auth" if response.status == 401 else \
                                   "rate_limit" if response.status == 429 else \
                                   "api"
                        
                        error_response = MapsToolError.create_error_response(
                            function_name="place_details",
                            error_message=error_detail,
                            error_type=error_type,
                            status_code=response.status,
                            user_id=__user__.get("id") if __user__ else None
                        )
                        error_response["details"] = {}  # Add expected field for consistency
                        return error_response
                        
        except aiohttp.ClientError as e:
            # Network/connection errors
            error_response = MapsToolError.create_error_response(
                function_name="place_details",
                error_message=str(e),
                error_type="network",
                user_id=__user__.get("id") if __user__ else None
            )
            error_response["details"] = {}
            return error_response
        except Exception as e:
            # General errors
            error_response = MapsToolError.create_error_response(
                function_name="place_details",
                error_message=str(e),
                error_type="general",
                user_id=__user__.get("id") if __user__ else None
            )
            error_response["details"] = {}
            return error_response 