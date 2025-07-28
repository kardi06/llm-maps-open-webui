import logging
from typing import Optional

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
    Find places using Google Places API
    
    Args:
        form_data: Request containing location, query, optional type and radius
        user: Authenticated user from dependency injection
        
    Returns:
        FindPlacesResponse: List of places with name, address, coordinates, rating, etc.
        
    Raises:
        HTTPException: 400 for invalid input or API errors, 500 for server errors
    """
    try:
        log.info(f"Find places request from user {user.id}: location='{form_data.location}', "
                f"query='{form_data.query}', type='{form_data.type}', radius={form_data.radius}")
        
        # Apply security validation and input sanitization
        sanitized_input = validate_and_sanitize_maps_input(
            location=form_data.location,
            query=form_data.query
        )
        
        # Validate required parameters
        if not sanitized_input.get('location') or not sanitized_input.get('query'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Location and query are required parameters"
            )
        
        # Get maps client and perform search with sanitized input
        maps_client = get_maps_client()
        places_data = maps_client.find_places(
            location=sanitized_input['location'],
            query=sanitized_input['query'],
            place_type=form_data.type,
            radius=form_data.radius
        )
        
        # Convert to Pydantic models and validate response format
        places = []
        for place_data in places_data:
            try:
                place = PlaceModel(**place_data)
                places.append(place)
            except ValidationError as ve:
                log.warning(f"Failed to validate place data for user {user.id}: {ve}")
                continue  # Skip invalid places rather than failing entire request
        
        log.info(f"Successfully found {len(places)} valid places for user {user.id}")
        
        # Return response with places (even if empty list)
        return FindPlacesResponse(places=places)
        
    except ValidationError as e:
        log.warning(f"Input validation error in find_places for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input parameters: {str(e)}"
        )
    except MapsClientError as e:
        log.warning(f"Maps client error in find_places for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        log.exception(f"Unexpected error in find_places for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find places due to server error"
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
    Get directions using Google Directions API
    
    Args:
        form_data: Request containing origin, destination, and travel mode
        user: Authenticated user from dependency injection
        
    Returns:
        GetDirectionsResponse: Directions with steps, distance, duration, and maps URL
        
    Raises:
        HTTPException: 400 for invalid input or API errors, 500 for server errors
    """
    try:
        log.info(f"Get directions request from user {user.id}: origin='{form_data.origin}', "
                f"destination='{form_data.destination}', mode='{form_data.mode}'")
        
        # Apply security validation and input sanitization
        sanitized_input = validate_and_sanitize_maps_input(
            location=form_data.origin,  # Use location validator for origin
            query=form_data.destination,  # Use location validator for destination
            mode=form_data.mode
        )
        
        # Validate required parameters
        if not sanitized_input.get('location') or not sanitized_input.get('query'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Origin and destination are required parameters"
            )
        
        # Get maps client and get directions with sanitized input
        maps_client = get_maps_client()
        directions_data = maps_client.get_directions(
            origin=sanitized_input['location'],  # origin was stored in location
            destination=sanitized_input['query'],  # destination was stored in query
            mode=sanitized_input['mode']
        )
        
        # Convert to Pydantic model and validate response format
        try:
            directions = DirectionsModel(**directions_data)
        except ValidationError as ve:
            log.error(f"Failed to validate directions data for user {user.id}: {ve}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid directions data received from Maps API"
            )
        
        log.info(f"Successfully got directions for user {user.id}: {len(directions.steps)} steps, "
                f"distance={directions.distance}, duration={directions.duration}")
        
        return GetDirectionsResponse(directions=directions)
        
    except ValidationError as e:
        log.warning(f"Input validation error in get_directions for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input parameters: {str(e)}"
        )
    except MapsClientError as e:
        log.warning(f"Maps client error in get_directions for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        log.exception(f"Unexpected error in get_directions for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get directions due to server error"
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
    Get place details using Google Place Details API
    
    Args:
        form_data: Request containing Google Place ID
        user: Authenticated user from dependency injection
        
    Returns:
        PlaceDetailsResponse: Detailed place information including reviews, photos, and maps URL
        
    Raises:
        HTTPException: 400 for invalid input or API errors, 500 for server errors
    """
    try:
        log.info(f"Place details request from user {user.id}: place_id='{form_data.place_id}'")
        
        # Apply security validation and input sanitization
        sanitized_input = validate_and_sanitize_maps_input(
            place_id=form_data.place_id
        )
        
        # Validate required parameter
        if not sanitized_input.get('place_id'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Place ID is required"
            )
        
        # Get maps client and get place details with sanitized input
        maps_client = get_maps_client()
        place_details_data = maps_client.get_place_details(
            place_id=sanitized_input['place_id']
        )
        
        # Convert to Pydantic model and validate response format
        try:
            place_details = PlaceDetailsModel(**place_details_data)
        except ValidationError as ve:
            log.error(f"Failed to validate place details data for user {user.id}: {ve}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid place details data received from Maps API"
            )
        
        log.info(f"Successfully got place details for user {user.id}: "
                f"place='{place_details.details.get('name', 'Unknown')}', "
                f"reviews={len(place_details.reviews)}, photos={len(place_details.photos)}")
        
        return PlaceDetailsResponse(place_details=place_details)
        
    except ValidationError as e:
        log.warning(f"Input validation error in place_details for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input parameters: {str(e)}"
        )
    except MapsClientError as e:
        log.warning(f"Maps client error in place_details for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        log.exception(f"Unexpected error in place_details for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get place details due to server error"
        )

############################
# Maps Usage Monitoring
############################

@router.get("/usage/stats")
async def get_maps_usage_stats(
    user=Depends(get_verified_user)
):
    """
    Get Maps API usage statistics for monitoring
    """
    try:
        # Get user-specific stats
        client_id = f"user:{user.id}"
        user_stats = MapsUsageMonitor.get_usage_stats(client_id)
        
        # Get global stats (admin only for now - simplified)
        global_stats = MapsUsageMonitor.get_global_usage_stats()
        
        log.info(f"Maps usage stats requested by user {user.id}")
        
        return {
            "user_stats": {
                "total_requests": user_stats.get('total_requests', 0),
                "requests_today": user_stats.get('requests_today', 0),
                "last_request": user_stats.get('last_request'),
                "quota_exceeded_count": user_stats.get('quota_exceeded_count', 0)
            },
            "rate_limits": {
                "requests_per_minute": 10,
                "requests_per_hour": 100,
                "requests_per_day": 500
            },
            "global_stats": global_stats if user.role == "admin" else None
        }
        
    except Exception as e:
        log.exception(f"Error getting maps usage stats for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get usage statistics"
        ) 