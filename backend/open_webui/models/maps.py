import logging
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from open_webui.env import SRC_LOG_LEVELS

####################
# Maps API Models
####################

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

# Request Models

class FindPlacesForm(BaseModel):
    location: str
    query: str
    type: Optional[str] = None
    radius: Optional[int] = None

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