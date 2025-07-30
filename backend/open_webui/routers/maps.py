import logging
import time
import json
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, ValidationError

from open_webui.models.maps import (
    FindPlacesForm,
    GetDirectionsForm,
    PlaceDetailsForm,
    FindPlacesResponse,
    GetDirectionsResponse,
    PlaceDetailsResponse,
    PlaceModel,
    DirectionsModel,
    PlaceDetailsModel,
)
from open_webui.utils.auth import get_verified_user
from open_webui.utils.maps_client import get_maps_client, MapsClientError
from open_webui.utils.maps_security import (
    validate_and_sanitize_maps_input,
    log_maps_security_event,
    MapsUsageMonitor
)
from open_webui.env import SRC_LOG_LEVELS

####################
# Logging Infrastructure
####################

class MapsRequestLogger:
    """Structured logging for Maps API requests with performance monitoring"""
    
    def __init__(self):
        self.logger = logging.getLogger("open_webui.maps.api")
        self.logger.setLevel(SRC_LOG_LEVELS.get("MAPS", "INFO"))
        
        # Create structured formatter if not already configured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_request_start(self, request: Request, endpoint: str, user_id: str = None) -> str:
        """Log the start of a maps API request"""
        request_id = str(uuid.uuid4())[:8]
        
        # Extract request parameters safely
        params = {}
        if hasattr(request, 'json') and request.method == 'POST':
            try:
                # For FastAPI, we'll need to get this from the parsed body later
                params = {"method": "POST", "endpoint": endpoint}
            except:
                params = {"method": request.method, "endpoint": endpoint}
        
        log_data = {
            "event": "request_start",
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": endpoint,
            "method": request.method,
            "user_id": user_id,
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("User-Agent", ""),
            "parameters": params
        }
        
        self.logger.info(f"Maps API request started: {json.dumps(log_data)}")
        return request_id
    
    def log_request_end(self, request_id: str, endpoint: str, 
                       duration: float, status_code: int,
                       user_id: str = None, error: str = None,
                       response_data: Dict = None):
        """Log the completion of a maps API request"""
        
        log_data = {
            "event": "request_complete",
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": endpoint,
            "duration_ms": round(duration * 1000, 2),
            "status_code": status_code,
            "user_id": user_id,
            "success": status_code < 400,
        }
        
        if error:
            log_data["error"] = error
            log_data["error_type"] = self._categorize_error(error, status_code)
        
        if response_data:
            # Log summary data without sensitive information
            if "places" in response_data:
                log_data["results_count"] = len(response_data["places"])
            elif "route" in response_data:
                log_data["route_found"] = bool(response_data["route"])
            elif "details" in response_data:
                log_data["details_found"] = bool(response_data["details"])
        
        # Determine log level based on outcome
        if error or status_code >= 500:
            self.logger.error(f"Maps API request failed: {json.dumps(log_data)}")
        elif status_code >= 400:
            self.logger.warning(f"Maps API client error: {json.dumps(log_data)}")
        elif duration > 5.0:  # Slow request threshold
            self.logger.warning(f"Maps API slow request: {json.dumps(log_data)}")
        else:
            self.logger.info(f"Maps API request completed: {json.dumps(log_data)}")
    
    def log_performance_metrics(self, request_id: str, metrics: Dict[str, Any]):
        """Log detailed performance metrics for analysis"""
        log_data = {
            "event": "performance_metrics",
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            **metrics
        }
        
        self.logger.info(f"Maps API performance metrics: {json.dumps(log_data)}")
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"
    
    def _categorize_error(self, error: str, status_code: int) -> str:
        """Categorize error types for analytics"""
        error_lower = error.lower() if error else ""
        
        if status_code == 401 or "authentication" in error_lower:
            return "authentication"
        elif status_code == 403 or "permission" in error_lower:
            return "authorization"
        elif status_code == 429 or "rate limit" in error_lower:
            return "rate_limit"
        elif status_code == 400 or "validation" in error_lower:
            return "validation"
        elif "timeout" in error_lower:
            return "timeout"
        elif "quota" in error_lower or "over_query_limit" in error_lower:
            return "quota_exceeded"
        elif "network" in error_lower or "connection" in error_lower:
            return "network"
        elif "api" in error_lower:
            return "google_maps_api"
        else:
            return "general"

@asynccontextmanager
async def log_maps_request(request: Request, endpoint: str, user_id: str = None):
    """Context manager for logging maps API requests with timing"""
    logger = MapsRequestLogger()
    request_id = logger.log_request_start(request, endpoint, user_id)
    start_time = time.time()
    
    try:
        yield request_id
        # Success case
        duration = time.time() - start_time
        logger.log_request_end(request_id, endpoint, duration, 200, user_id)
        
    except HTTPException as e:
        # HTTP exception case
        duration = time.time() - start_time
        logger.log_request_end(request_id, endpoint, duration, e.status_code, user_id, str(e.detail))
        raise
        
    except Exception as e:
        # General exception case
        duration = time.time() - start_time
        logger.log_request_end(request_id, endpoint, duration, 500, user_id, str(e))
        raise

# Create global logger instance
maps_logger = MapsRequestLogger()

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()

############################
# Find Places
############################

@router.post("/find_places", response_model=FindPlacesResponse)
async def find_places(
    form_data: FindPlacesForm,
    request: Request,
    user=Depends(get_verified_user)
):
    """
    Find places using Google Places API with comprehensive logging
    
    Args:
        form_data: Request containing location, query, optional type and radius
        user: Authenticated user from dependency injection
        
    Returns:
        FindPlacesResponse: List of places with name, address, coordinates, rating, etc.
    
    Raises:
        HTTPException: If validation fails, API errors occur, or service is unavailable
    """
    user_id = user.id if user else None
    
    async with log_maps_request(request, "/api/v1/maps/find_places", user_id) as request_id:
        try:
            # Log request parameters
            maps_logger.logger.info(f"Find places request [{request_id}]: location='{form_data.location}', "
                                   f"query='{form_data.query}', type={form_data.type}, radius={form_data.radius}")
            
            # Validate and sanitize input
            sanitized_input = validate_and_sanitize_maps_input(
                location=form_data.location,
                query=form_data.query
            )
            
            # Get maps client and execute search
            maps_client = await get_maps_client()
            
            # Track performance metrics
            api_start_time = time.time()
            places_data = await maps_client.find_places(
                location=sanitized_input['location'],
                query=sanitized_input['query'],
                place_type=form_data.type.value if form_data.type else None,
                radius=form_data.radius
            )
            api_duration = time.time() - api_start_time
            
            # Log performance metrics
            maps_logger.log_performance_metrics(request_id, {
                "google_maps_api_duration_ms": round(api_duration * 1000, 2),
                "results_count": len(places_data),
                "search_type": "find_places"
            })
            
            # Transform to API response format
            places = [
                PlaceModel(
                    name=place.get("name", ""),
                    address=place.get("address", ""),
                    lat=place.get("lat", 0.0),
                    lng=place.get("lng", 0.0),
                    place_id=place.get("place_id", ""),
                    rating=place.get("rating"),
                    open_now=place.get("open_now"),
                    maps_url=place.get("maps_url", "")
                )
                for place in places_data
            ]
            
            response = FindPlacesResponse(places=places)
            
            # Log successful response
            maps_logger.log_request_end(request_id, "/api/v1/maps/find_places", 
                                       time.time() - api_start_time, 200, user_id, 
                                       response_data={"places": places_data})
            
            return response
            
        except ValidationError as e:
            error_msg = f"Validation error: {str(e)}"
            log_maps_security_event("VALIDATION_ERROR", user_id, {
                "endpoint": "/api/v1/maps/find_places",
                "error": error_msg,
                "request_id": request_id
            })
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
            
        except MapsClientError as e:
            error_msg = f"Maps API error: {str(e)}"
            maps_logger.logger.error(f"Maps client error [{request_id}]: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=error_msg
            )
            
        except Exception as e:
            error_msg = f"Internal server error: {str(e)}"
            maps_logger.logger.error(f"Unexpected error [{request_id}]: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while processing your request"
            )

############################
# Get Directions
############################

@router.post("/get_directions", response_model=GetDirectionsResponse)
async def get_directions(
    form_data: GetDirectionsForm,
    request: Request,
    user=Depends(get_verified_user)
):
    """
    Get directions between two locations using Google Directions API with comprehensive logging
    
    Args:
        form_data: Request containing origin, destination, and travel mode
        user: Authenticated user from dependency injection
        
    Returns:
        GetDirectionsResponse: Route information with steps, distance, duration
    
    Raises:
        HTTPException: If validation fails, API errors occur, or service is unavailable
    """
    user_id = user.id if user else None
    
    async with log_maps_request(request, "/api/v1/maps/get_directions", user_id) as request_id:
        try:
            # Log request parameters
            maps_logger.logger.info(f"Get directions request [{request_id}]: origin='{form_data.origin}', "
                                   f"destination='{form_data.destination}', mode={form_data.mode}")
            
            # Validate and sanitize input
            sanitized_input = validate_and_sanitize_maps_input(
                location=form_data.origin,
                query=form_data.destination,
                mode=form_data.mode
            )
            
            # Get maps client and execute directions request
            maps_client = await get_maps_client()
            
            # Track performance metrics
            api_start_time = time.time()
            route_data = await maps_client.get_directions(
                origin=sanitized_input['location'],
                destination=sanitized_input['query'],
                mode=sanitized_input['mode']
            )
            api_duration = time.time() - api_start_time
            
            # Log performance metrics
            maps_logger.log_performance_metrics(request_id, {
                "google_maps_api_duration_ms": round(api_duration * 1000, 2),
                "route_found": bool(route_data),
                "search_type": "get_directions",
                "travel_mode": sanitized_input['mode']
            })
            
            # Transform to API response format
            route = DirectionsModel(
                steps=route_data.get("steps", []),
                distance=route_data.get("distance", ""),
                duration=route_data.get("duration", ""),
                maps_url=route_data.get("maps_url", "")
            )
            
            response = GetDirectionsResponse(route=route)
            
            # Log successful response
            maps_logger.log_request_end(request_id, "/api/v1/maps/get_directions", 
                                       api_duration, 200, user_id, 
                                       response_data={"route": route_data})
            
            return response
            
        except ValidationError as e:
            error_msg = f"Validation error: {str(e)}"
            log_maps_security_event("VALIDATION_ERROR", user_id, {
                "endpoint": "/api/v1/maps/get_directions",
                "error": error_msg,
                "request_id": request_id
            })
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
            
        except MapsClientError as e:
            error_msg = f"Maps API error: {str(e)}"
            maps_logger.logger.error(f"Maps client error [{request_id}]: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=error_msg
            )
            
        except Exception as e:
            error_msg = f"Internal server error: {str(e)}"
            maps_logger.logger.error(f"Unexpected error [{request_id}]: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while processing your request"
            )

############################
# Place Details
############################

@router.post("/place_details", response_model=PlaceDetailsResponse)
async def place_details(
    form_data: PlaceDetailsForm,
    request: Request,
    user=Depends(get_verified_user)
):
    """
    Get detailed information about a specific place using Google Place Details API with comprehensive logging
    
    Args:
        form_data: Request containing place_id
        user: Authenticated user from dependency injection
        
    Returns:
        PlaceDetailsResponse: Detailed place information including reviews, photos, hours
    
    Raises:
        HTTPException: If validation fails, API errors occur, or service is unavailable
    """
    user_id = user.id if user else None
    
    async with log_maps_request(request, "/api/v1/maps/place_details", user_id) as request_id:
        try:
            # Log request parameters (place_id partially masked for privacy)
            masked_place_id = form_data.place_id[:10] + "..." if len(form_data.place_id) > 10 else form_data.place_id
            maps_logger.logger.info(f"Place details request [{request_id}]: place_id='{masked_place_id}'")
            
            # Validate and sanitize input
            sanitized_input = validate_and_sanitize_maps_input(
                place_id=form_data.place_id
            )
            
            # Get maps client and execute place details request
            maps_client = await get_maps_client()
            
            # Track performance metrics
            api_start_time = time.time()
            place_data = await maps_client.get_place_details(
                place_id=sanitized_input['place_id']
            )
            api_duration = time.time() - api_start_time
            
            # Log performance metrics
            maps_logger.log_performance_metrics(request_id, {
                "google_maps_api_duration_ms": round(api_duration * 1000, 2),
                "details_found": bool(place_data.get("details")),
                "search_type": "place_details",
                "reviews_count": len(place_data.get("reviews", [])),
                "photos_count": len(place_data.get("photos", []))
            })
            
            # Transform to API response format
            place_details = PlaceDetailsModel(
                details=place_data.get("details", {}),
                reviews=place_data.get("reviews", []),
                photos=place_data.get("photos", []),
                maps_url=place_data.get("maps_url", "")
            )
            
            response = PlaceDetailsResponse(place_details=place_details)
            
            # Log successful response
            maps_logger.log_request_end(request_id, "/api/v1/maps/place_details", 
                                       api_duration, 200, user_id, 
                                       response_data={"details": place_data.get("details", {})})
            
            return response
            
        except ValidationError as e:
            error_msg = f"Validation error: {str(e)}"
            log_maps_security_event("VALIDATION_ERROR", user_id, {
                "endpoint": "/api/v1/maps/place_details",
                "error": error_msg,
                "request_id": request_id
            })
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
            
        except MapsClientError as e:
            error_msg = f"Maps API error: {str(e)}"
            maps_logger.logger.error(f"Maps client error [{request_id}]: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=error_msg
            )
            
        except Exception as e:
            error_msg = f"Internal server error: {str(e)}"
            maps_logger.logger.error(f"Unexpected error [{request_id}]: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while processing your request"
            )

############################
# Health Check and Analytics
############################

@router.get("/health")
async def maps_health_check(user=Depends(get_verified_user)):
    """
    Health check endpoint for maps service with performance metrics
    """
    try:
        maps_client = await get_maps_client()
        performance_stats = maps_client.get_performance_stats()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "performance_stats": performance_stats,
            "google_maps_configured": bool(maps_client)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        } 