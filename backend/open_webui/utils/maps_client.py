import logging
import time
import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlencode
from dataclasses import dataclass
from contextlib import asynccontextmanager
import uuid

import googlemaps
from googlemaps.exceptions import ApiError, HTTPError, Timeout, TransportError

from open_webui.env import GOOGLE_MAPS_API_KEY, SRC_LOG_LEVELS
from open_webui.constants import ERROR_MESSAGES

# Import from the new modular components
from .maps_circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .maps_performance import PerformanceConfig, PerformanceMonitor, ConnectionPoolManager
from .maps_health import MapsHealthMonitor, GracefulDegradation

####################
# Google Maps Client
####################

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

class MapsClientError(Exception):
    """Custom exception for Maps client errors"""
    pass

class MapsClient:
    """Google Maps API client with performance optimization and monitoring"""
    
    def __init__(self):
        """Initialize Google Maps client with performance optimizations and resilience features"""
        if not GOOGLE_MAPS_API_KEY:
            raise MapsClientError("Google Maps API key not configured. Set GOOGLE_MAPS_API_KEY environment variable.")
        
        try:
            # Initialize synchronous client for compatibility
            self.client = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
            
            # Initialize performance components
            self.performance_config = PerformanceConfig()
            self.performance_monitor = PerformanceMonitor()
            self.connection_pool = ConnectionPoolManager(self.performance_config)
            
            # Initialize resilience components
            self.circuit_breaker = CircuitBreaker()
            self.health_monitor = MapsHealthMonitor()
            
            log.info("Google Maps client initialized with performance optimization and resilience features")
        except Exception as e:
            log.error(f"Failed to initialize Google Maps client: {e}")
            raise MapsClientError(f"Failed to initialize Google Maps client: {e}")

    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.connection_pool.close()

    def _handle_api_error(self, e: Exception, operation: str) -> None:
        """Handle Google Maps API errors with proper logging"""
        if isinstance(e, ApiError):
            log.error(f"Google Maps API error in {operation}: {e}")
            if "INVALID_REQUEST" in str(e):
                raise MapsClientError("Invalid request parameters")
            elif "ZERO_RESULTS" in str(e):
                raise MapsClientError("No results found")
            elif "OVER_QUERY_LIMIT" in str(e):
                raise MapsClientError("API quota exceeded")
            elif "REQUEST_DENIED" in str(e):
                raise MapsClientError("API request denied - check API key and permissions")
            else:
                raise MapsClientError(f"Google Maps API error: {e}")
        elif isinstance(e, (HTTPError, Timeout, TransportError)):
            log.error(f"Google Maps transport error in {operation}: {e}")
            raise MapsClientError(f"Google Maps service unavailable: {e}")
        else:
            log.error(f"Unexpected error in {operation}: {e}")
            raise MapsClientError(f"Unexpected error: {e}")

    async def _execute_with_timeout_and_retry(self, operation: str, func, timeout: float, *args, **kwargs):
        """Execute operation with circuit breaker, timeout and retry logic"""
        request_id = self.performance_monitor.start_request(operation)
        
        # Check circuit breaker before attempting operation
        if not self.circuit_breaker.can_execute():
            circuit_info = self.circuit_breaker.get_state_info()
            error_msg = f"Circuit breaker is {circuit_info['state']} for Maps API"
            self.performance_monitor.end_request(request_id, success=False, error_type="circuit_breaker")
            
            # Return graceful degradation response
            fallback_response = GracefulDegradation.create_fallback_response(
                operation, error_msg, 
                f"Maps service is temporarily unavailable. Please try again in {circuit_info.get('time_until_retry', 60)} seconds."
            )
            return self._handle_fallback_response(operation, fallback_response)
        
        for attempt in range(self.performance_config.max_retries + 1):
            try:
                # Check health periodically
                if self.health_monitor.should_check_health():
                    await self.health_monitor.check_google_maps_health()
                
                # Run in thread pool since googlemaps client is synchronous
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, func, *args, **kwargs),
                    timeout=timeout
                )
                
                # Record success in circuit breaker and performance monitor
                self.circuit_breaker.record_success()
                self.performance_monitor.end_request(request_id, success=True)
                return result
                
            except asyncio.TimeoutError:
                error_type = "timeout"
                if attempt < self.performance_config.max_retries:
                    log.warning(f"Maps API {operation} timed out (attempt {attempt + 1}), retrying...")
                    await asyncio.sleep(self.performance_config.retry_delay * (attempt + 1))
                    continue
                else:
                    log.error(f"Maps API {operation} failed after {attempt + 1} attempts - timeout")
                    self.circuit_breaker.record_failure()
                    self.performance_monitor.end_request(request_id, success=False, error_type=error_type)
                    
                    # Return graceful degradation response for timeout
                    fallback_response = GracefulDegradation.create_fallback_response(
                        operation, f"Timeout after {timeout}s",
                        "The request took too long to complete. Please try again."
                    )
                    return self._handle_fallback_response(operation, fallback_response)
                    
            except Exception as e:
                error_type = type(e).__name__
                
                if attempt < self.performance_config.max_retries and isinstance(e, (HTTPError, TransportError)):
                    log.warning(f"Maps API {operation} failed (attempt {attempt + 1}), retrying: {e}")
                    await asyncio.sleep(self.performance_config.retry_delay * (attempt + 1))
                    continue
                else:
                    # Record failure in circuit breaker
                    self.circuit_breaker.record_failure()
                    self.performance_monitor.end_request(request_id, success=False, error_type=error_type)
                    
                    # Check if this is a service availability issue
                    if isinstance(e, (HTTPError, TransportError, ConnectionError)):
                        fallback_response = GracefulDegradation.create_fallback_response(
                            operation, str(e),
                            "Maps service is currently unavailable. Please try again later."
                        )
                        return self._handle_fallback_response(operation, fallback_response)
                    else:
                        # For other errors, use original error handling
                        self._handle_api_error(e, operation)
    
    def _handle_fallback_response(self, operation: str, fallback_response: Dict[str, Any]) -> Any:
        """Convert fallback response to appropriate format for each operation"""
        if operation == "find_places":
            return []  # Return empty list for places
        elif operation == "get_directions":
            return {}  # Return empty dict for directions
        elif operation == "get_place_details":
            return {}  # Return empty dict for place details
        else:
            return fallback_response

    def _build_maps_url(self, place_id: Optional[str] = None, query: Optional[str] = None, 
                        origin: Optional[str] = None, destination: Optional[str] = None) -> str:
        """Build Google Maps URL for sharing"""
        base_url = "https://www.google.com/maps"
        
        if place_id:
            return f"{base_url}/place/?q=place_id:{place_id}"
        elif origin and destination:
            params = urlencode({
                'saddr': origin,
                'daddr': destination
            })
            return f"{base_url}/dir/?{params}"
        elif query:
            params = urlencode({'q': query})
            return f"{base_url}/search/?{params}"
        else:
            return base_url

    async def find_places(self, location: str, query: str, place_type: Optional[str] = None, 
                   radius: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Find places using Google Places API with performance optimization
        
        Args:
            location: Location to search around
            query: Search query
            place_type: Type of place (restaurant, hospital, etc.)
            radius: Search radius in meters
            
        Returns:
            List of place dictionaries with standardized format
        """
        log.info(f"Finding places for query: {query} near {location}")
        
        def _find_places_sync():
            # Use text search for broad queries
            if place_type or radius:
                # Use nearby search if type or radius specified
                geocode_result = self.client.geocode(location)
                if not geocode_result:
                    raise MapsClientError(f"Could not geocode location: {location}")
                
                location_coords = geocode_result[0]['geometry']['location']
                
                results = self.client.places_nearby(
                    location=location_coords,
                    radius=radius or 5000,  # Default 5km
                    keyword=query,
                    type=place_type
                )
            else:
                # Use text search for general queries
                results = self.client.places(
                    query=f"{query} near {location}",
                    type=place_type
                )
            
            places = []
            for place in results.get('results', []):
                parsed_place = self._parse_place_result(place)
                if parsed_place:
                    places.append(parsed_place)
            
            return places
        
        places = await self._execute_with_timeout_and_retry(
            "find_places", 
            _find_places_sync, 
            self.performance_config.places_search_timeout
        )
        
        log.info(f"Found {len(places)} places")
        return places

    async def get_directions(self, origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
        """
        Get directions using Google Directions API with performance optimization
        
        Args:
            origin: Starting location
            destination: Ending location  
            mode: Travel mode (driving, walking, bicycling, transit)
            
        Returns:
            Directions dictionary with standardized format
        """
        log.info(f"Getting directions from {origin} to {destination} via {mode}")
        
        def _get_directions_sync():
            results = self.client.directions(
                origin=origin,
                destination=destination,
                mode=mode,
                departure_time=int(time.time())  # Current time for traffic
            )
            
            if not results:
                raise MapsClientError("No directions found")
            
            return self._parse_directions_result(results[0], origin, destination)
        
        return await self._execute_with_timeout_and_retry(
            "get_directions",
            _get_directions_sync,
            self.performance_config.directions_timeout
        )

    async def get_place_details(self, place_id: str) -> Dict[str, Any]:
        """
        Get detailed place information using Google Place Details API with performance optimization
        
        Args:
            place_id: Google Place ID
            
        Returns:
            Place details dictionary with standardized format
        """
        log.info(f"Getting place details for place_id: {place_id}")
        
        def _get_place_details_sync():
            results = self.client.place(
                place_id=place_id,
                fields=['name', 'rating', 'reviews', 'formatted_address', 'geometry', 
                       'photos', 'formatted_phone_number', 'website', 'opening_hours',
                       'price_level', 'types', 'user_ratings_total']
            )
            
            if not results or 'result' not in results:
                raise MapsClientError("Place details not found")
            
            return self._parse_place_details_result(results['result'])
        
        return await self._execute_with_timeout_and_retry(
            "get_place_details",
            _get_place_details_sync,
            self.performance_config.place_details_timeout
        )

    def _parse_place_result(self, place: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a place result into standardized format with coordinate validation"""
        try:
            geometry = place.get('geometry', {})
            location = geometry.get('location', {})
            
            lat = location.get('lat', 0.0)
            lng = location.get('lng', 0.0)
            
            # Validate coordinates
            if not self._validate_coordinates(lat, lng):
                log.warning(f"Invalid coordinates for place {place.get('name', 'Unknown')}: lat={lat}, lng={lng}")
                # Set to None to indicate invalid coordinates
                lat, lng = None, None
            
            return {
                'name': place.get('name', 'Unknown'),
                'address': place.get('formatted_address', place.get('vicinity', 'Address not available')),
                'lat': lat,
                'lng': lng,
                'place_id': place.get('place_id', ''),
                'rating': place.get('rating'),
                'open_now': self._get_open_now_status(place),
                'maps_url': self._build_maps_url(place_id=place.get('place_id'))
            }
        except Exception as e:
            log.warning(f"Failed to parse place result: {e}")
            return None

    def _validate_coordinates(self, lat: float, lng: float) -> bool:
        """Validate latitude and longitude coordinates"""
        try:
            if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
                return False
            
            # Check if coordinates are within valid ranges
            if lat < -90 or lat > 90:
                return False
            
            if lng < -180 or lng > 180:
                return False
            
            # Check for obviously invalid values (e.g., 0,0 which is in the Gulf of Guinea)
            if lat == 0 and lng == 0:
                return False
            
            return True
        except (TypeError, ValueError):
            return False

    def _parse_directions_result(self, route: Dict[str, Any], origin: str, destination: str) -> Dict[str, Any]:
        """Parse directions result into standardized format"""
        try:
            leg = route['legs'][0]  # Take first leg
            steps = []
            
            for step in leg.get('steps', []):
                steps.append({
                    'instruction': self._clean_html_instructions(step.get('html_instructions', '')),
                    'distance': step.get('distance', {}).get('text', ''),
                    'duration': step.get('duration', {}).get('text', '')
                })
            
            return {
                'steps': steps,
                'distance': leg.get('distance', {}).get('text', ''),
                'duration': leg.get('duration', {}).get('text', ''),
                'maps_url': self._build_maps_url(origin=origin, destination=destination)
            }
        except Exception as e:
            log.error(f"Failed to parse directions result: {e}")
            raise MapsClientError("Failed to parse directions response")

    def _parse_place_details_result(self, place: Dict[str, Any]) -> Dict[str, Any]:
        """Parse place details result into standardized format"""
        try:
            reviews = []
            for review in place.get('reviews', [])[:5]:  # Limit to 5 reviews
                reviews.append({
                    'author': review.get('author_name', 'Anonymous'),
                    'rating': review.get('rating', 0),
                    'text': review.get('text', ''),
                    'time': review.get('relative_time_description', '')
                })
            
            photos = []
            for photo in place.get('photos', [])[:10]:  # Limit to 10 photos
                photo_url = self.get_photo_url(photo.get('photo_reference', ''))
                if photo_url:
                    photos.append(photo_url)
            
            return {
                'details': {
                    'name': place.get('name', 'Unknown'),
                    'address': place.get('formatted_address', ''),
                    'phone': place.get('formatted_phone_number', ''),
                    'website': place.get('website', ''),
                    'rating': place.get('rating'),
                    'rating_count': place.get('user_ratings_total', 0),
                    'price_level': place.get('price_level'),
                    'types': place.get('types', []),
                    'opening_hours': self._parse_opening_hours(place.get('opening_hours', {}))
                },
                'reviews': reviews,
                'photos': photos,
                'maps_url': self._build_maps_url(place_id=place.get('place_id', ''))
            }
        except Exception as e:
            log.error(f"Failed to parse place details result: {e}")
            raise MapsClientError("Failed to parse place details response")

    def _get_open_now_status(self, place: Dict[str, Any]) -> Optional[bool]:
        """Extract open_now status from place data"""
        opening_hours = place.get('opening_hours', {})
        return opening_hours.get('open_now')

    def _clean_html_instructions(self, html_instructions: str) -> str:
        """Remove HTML tags from step instructions"""
        import re
        clean = re.compile('<.*?>')
        return re.sub(clean, '', html_instructions)

    def get_photo_url(self, photo_reference: str, max_width: int = 400) -> Optional[str]:
        """Get photo URL from photo reference"""
        if not photo_reference:
            return None
        return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth={max_width}&photoreference={photo_reference}&key={GOOGLE_MAPS_API_KEY}"

    def _parse_opening_hours(self, opening_hours: Dict[str, Any]) -> Dict[str, Any]:
        """Parse opening hours information"""
        return {
            'open_now': opening_hours.get('open_now', False),
            'weekday_text': opening_hours.get('weekday_text', [])
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance and health statistics"""
        perf_stats = self.performance_monitor.get_performance_stats()
        
        # Add circuit breaker and health information
        perf_stats.update({
            "circuit_breaker": self.circuit_breaker.get_state_info(),
            "health_status": self.health_monitor.get_health_summary(),
            "resilience_features": {
                "circuit_breaker_enabled": True,
                "health_monitoring_enabled": True,
                "graceful_degradation_enabled": True
            }
        })
        
        return perf_stats
    
    async def force_health_check(self) -> Dict[str, Any]:
        """Force a health check and return results"""
        health_status = await self.health_monitor.check_google_maps_health()
        return {
            "timestamp": health_status.last_check.isoformat(),
            "healthy": health_status.is_healthy,
            "response_time_ms": health_status.response_time_ms,
            "error": health_status.error_message,
            "consecutive_failures": health_status.consecutive_failures
        }

# Global client instance with performance optimization
_maps_client = None

async def get_maps_client() -> MapsClient:
    """Get or create Google Maps client instance (singleton pattern) with async support"""
    global _maps_client
    if _maps_client is None:
        _maps_client = MapsClient()
    return _maps_client

def get_maps_client_sync() -> MapsClient:
    """Get or create Google Maps client instance (synchronous version for backward compatibility)"""
    global _maps_client
    if _maps_client is None:
        _maps_client = MapsClient()
    return _maps_client

def validate_maps_config() -> bool:
    """Validate Google Maps configuration"""
    try:
        if not GOOGLE_MAPS_API_KEY:
            log.error("Google Maps API key not configured")
            return False
        
        # Test client initialization
        # Note: We can't use await here, so we'll do basic validation
        if len(GOOGLE_MAPS_API_KEY) < 20:  # Basic key format check
            log.error("Google Maps API key appears to be invalid")
            return False
            
        log.info("Google Maps configuration validated successfully")
        return True
    except Exception as e:
        log.error(f"Google Maps configuration validation failed: {e}")
        return False 