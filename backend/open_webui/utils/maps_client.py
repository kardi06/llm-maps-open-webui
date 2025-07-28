import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlencode

import googlemaps
from googlemaps.exceptions import ApiError, HTTPError, Timeout, TransportError

from open_webui.env import GOOGLE_MAPS_API_KEY, SRC_LOG_LEVELS
from open_webui.constants import ERROR_MESSAGES

####################
# Google Maps Client
####################

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

class MapsClientError(Exception):
    """Custom exception for Maps client errors"""
    pass

class MapsClient:
    """Google Maps API client with error handling and response parsing"""
    
    def __init__(self):
        """Initialize Google Maps client with API key validation"""
        if not GOOGLE_MAPS_API_KEY:
            raise MapsClientError("Google Maps API key not configured. Set GOOGLE_MAPS_API_KEY environment variable.")
        
        try:
            self.client = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
            log.info("Google Maps client initialized successfully")
        except Exception as e:
            log.error(f"Failed to initialize Google Maps client: {e}")
            raise MapsClientError(f"Failed to initialize Google Maps client: {e}")

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

    def find_places(self, location: str, query: str, place_type: Optional[str] = None, 
                   radius: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Find places using Google Places API
        
        Args:
            location: Location to search around
            query: Search query
            place_type: Type of place (restaurant, hospital, etc.)
            radius: Search radius in meters
            
        Returns:
            List of place dictionaries with standardized format
        """
        try:
            log.info(f"Finding places for query: {query} near {location}")
            
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
            
            log.info(f"Found {len(places)} places")
            return places
            
        except Exception as e:
            self._handle_api_error(e, "find_places")

    def get_directions(self, origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
        """
        Get directions using Google Directions API
        
        Args:
            origin: Starting location
            destination: Ending location  
            mode: Travel mode (driving, walking, bicycling, transit)
            
        Returns:
            Directions dictionary with standardized format
        """
        try:
            log.info(f"Getting directions from {origin} to {destination} via {mode}")
            
            results = self.client.directions(
                origin=origin,
                destination=destination,
                mode=mode,
                departure_time=int(time.time())  # Current time for traffic
            )
            
            if not results:
                raise MapsClientError("No directions found")
            
            return self._parse_directions_result(results[0], origin, destination)
            
        except Exception as e:
            self._handle_api_error(e, "get_directions")

    def get_place_details(self, place_id: str) -> Dict[str, Any]:
        """
        Get detailed place information using Google Place Details API
        
        Args:
            place_id: Google Place ID
            
        Returns:
            Place details dictionary with standardized format
        """
        try:
            log.info(f"Getting place details for place_id: {place_id}")
            
            results = self.client.place(
                place_id=place_id,
                fields=['name', 'rating', 'reviews', 'formatted_address', 'geometry', 
                       'photos', 'formatted_phone_number', 'website', 'opening_hours',
                       'price_level', 'types', 'user_ratings_total']
            )
            
            if not results or 'result' not in results:
                raise MapsClientError("Place details not found")
            
            return self._parse_place_details_result(results['result'])
            
        except Exception as e:
            self._handle_api_error(e, "get_place_details")

    def _parse_place_result(self, place: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a place result into standardized format"""
        try:
            geometry = place.get('geometry', {})
            location = geometry.get('location', {})
            
            return {
                'name': place.get('name', 'Unknown'),
                'address': place.get('formatted_address', place.get('vicinity', 'Address not available')),
                'lat': location.get('lat', 0.0),
                'lng': location.get('lng', 0.0),
                'place_id': place.get('place_id', ''),
                'rating': place.get('rating'),
                'open_now': self._get_open_now_status(place),
                'maps_url': self._build_maps_url(place_id=place.get('place_id'))
            }
        except Exception as e:
            log.warning(f"Failed to parse place result: {e}")
            return None

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
                photo_url = self._get_photo_url(photo.get('photo_reference', ''))
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

    def _get_photo_url(self, photo_reference: str, max_width: int = 400) -> Optional[str]:
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

# Global client instance
_maps_client = None

def get_maps_client() -> MapsClient:
    """Get or create Google Maps client instance (singleton pattern)"""
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
        client = get_maps_client()
        log.info("Google Maps configuration validated successfully")
        return True
    except Exception as e:
        log.error(f"Google Maps configuration validation failed: {e}")
        return False 