import logging
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, validator

from open_webui.env import SRC_LOG_LEVELS

####################
# Maps API Models
####################

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

# Request Models

class FindPlacesForm(BaseModel):
    location: str = Field(..., min_length=1, max_length=200, description="Location to search around")
    query: str = Field(..., min_length=1, max_length=100, description="Search query for places")
    type: Optional[str] = Field(None, max_length=50, description="Type of place (e.g., restaurant, hospital)")
    radius: Optional[int] = Field(None, ge=1, le=50000, description="Search radius in meters (1-50000)")
    
    @validator('location')
    def validate_location(cls, v):
        if not v.strip():
            raise ValueError('Location cannot be empty or whitespace only')
        return v.strip()
    
    @validator('query')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty or whitespace only')
        return v.strip()
    
    @validator('type')
    def validate_type(cls, v):
        if v is not None:
            v = v.strip().lower()
            # Common Google Places API types
            valid_types = {
                'restaurant', 'food', 'meal_takeaway', 'cafe', 'bar',
                'hospital', 'doctor', 'pharmacy', 'health',
                'gas_station', 'car_repair', 'parking',
                'bank', 'atm', 'finance',
                'lodging', 'hotel', 'motel',
                'shopping_mall', 'store', 'supermarket',
                'school', 'university', 'library',
                'tourist_attraction', 'museum', 'park',
                'gym', 'spa', 'beauty_salon'
            }
            if v and v not in valid_types:
                # Allow any type but log a warning for unknown types
                pass
        return v

class GetDirectionsForm(BaseModel):
    origin: str
    destination: str
    mode: Optional[str] = "driving"

class PlaceDetailsForm(BaseModel):
    place_id: str

# Response Models

class PlaceModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    name: str
    address: str
    lat: float
    lng: float
    place_id: str
    rating: Optional[float] = None
    open_now: Optional[bool] = None
    maps_url: str

class DirectionStepModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    instruction: str
    distance: str
    duration: str

class DirectionsModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    steps: List[DirectionStepModel]
    distance: str
    duration: str
    maps_url: str

class PlaceReviewModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    author: str
    rating: float
    text: str
    time: str

class PlaceDetailsModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    details: dict
    reviews: List[PlaceReviewModel]
    photos: List[str]
    maps_url: str

# Response Lists

class FindPlacesResponse(BaseModel):
    places: List[PlaceModel]

class GetDirectionsResponse(BaseModel):
    directions: DirectionsModel

class PlaceDetailsResponse(BaseModel):
    place_details: PlaceDetailsModel 