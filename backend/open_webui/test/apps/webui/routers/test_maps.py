import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

from open_webui.models.maps import (
    FindPlacesForm, PlaceModel, FindPlacesResponse,
    GetDirectionsForm, DirectionsModel, GetDirectionsResponse, DirectionStepModel
)
from open_webui.routers.maps import find_places, get_directions
from open_webui.utils.maps_client import MapsClientError


class TestFindPlacesEndpoint:
    """Test suite for find_places endpoint - Task 3 verification"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_user = Mock()
        self.mock_user.id = "test_user_123"
        
        self.valid_form_data = FindPlacesForm(
            location="New York, NY",
            query="pizza restaurants",
            type="restaurant",
            radius=1000
        )
        
        self.mock_place_data = {
            'name': 'Joe\'s Pizza',
            'address': '123 Main St, New York, NY',
            'lat': 40.7128,
            'lng': -74.0060,
            'place_id': 'ChIJN1t_tDeuEmsRUsoyG83frY4',
            'rating': 4.5,
            'open_now': True,
            'maps_url': 'https://www.google.com/maps/place/?q=place_id:ChIJN1t_tDeuEmsRUsoyG83frY4'
        }

    @patch('open_webui.routers.maps.get_maps_client')
    @pytest.mark.asyncio
    async def test_find_places_success(self, mock_get_client):
        """Test successful find_places request"""
        # Setup mock
        mock_client = Mock()
        mock_client.find_places.return_value = [self.mock_place_data]
        mock_get_client.return_value = mock_client
        
        # Execute
        result = await find_places(self.valid_form_data, self.mock_user)
        
        # Verify
        assert isinstance(result, FindPlacesResponse)
        assert len(result.places) == 1
        
        place = result.places[0]
        assert place.name == "Joe's Pizza"
        assert place.address == "123 Main St, New York, NY"
        assert place.lat == 40.7128
        assert place.lng == -74.0060
        assert place.rating == 4.5
        assert place.open_now is True
        
        # Verify client was called correctly
        mock_client.find_places.assert_called_once_with(
            location="New York, NY",
            query="pizza restaurants",
            place_type="restaurant",
            radius=1000
        )

    @patch('open_webui.routers.maps.get_maps_client')
    @pytest.mark.asyncio
    async def test_find_places_empty_results(self, mock_get_client):
        """Test find_places with no results"""
        # Setup mock
        mock_client = Mock()
        mock_client.find_places.return_value = []
        mock_get_client.return_value = mock_client
        
        # Execute
        result = await find_places(self.valid_form_data, self.mock_user)
        
        # Verify
        assert isinstance(result, FindPlacesResponse)
        assert len(result.places) == 0

    @patch('open_webui.routers.maps.get_maps_client')
    @pytest.mark.asyncio
    async def test_find_places_maps_client_error(self, mock_get_client):
        """Test find_places with Maps client error"""
        # Setup mock
        mock_client = Mock()
        mock_client.find_places.side_effect = MapsClientError("API quota exceeded")
        mock_get_client.return_value = mock_client
        
        # Execute and verify exception
        with pytest.raises(HTTPException) as exc_info:
            await find_places(self.valid_form_data, self.mock_user)
        
        assert exc_info.value.status_code == 400
        assert "API quota exceeded" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_find_places_empty_location(self):
        """Test input validation - empty location"""
        form_data = FindPlacesForm(
            location="",
            query="pizza restaurants"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await find_places(form_data, self.mock_user)
        
        assert exc_info.value.status_code == 400
        assert "Location and query are required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_find_places_empty_query(self):
        """Test input validation - empty query"""
        form_data = FindPlacesForm(
            location="New York, NY",
            query=""
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await find_places(form_data, self.mock_user)
        
        assert exc_info.value.status_code == 400
        assert "Location and query are required" in str(exc_info.value.detail)

    def test_find_places_form_validation(self):
        """Test Pydantic validation for FindPlacesForm"""
        # Test valid form
        valid_form = FindPlacesForm(
            location="New York, NY",
            query="restaurants",
            type="restaurant",
            radius=5000
        )
        assert valid_form.location == "New York, NY"
        assert valid_form.query == "restaurants"
        assert valid_form.type == "restaurant"
        assert valid_form.radius == 5000

        # Test radius validation
        with pytest.raises(ValueError):
            FindPlacesForm(
                location="New York, NY",
                query="restaurants",
                radius=100000  # Exceeds max limit
            )

        # Test minimum radius
        with pytest.raises(ValueError):
            FindPlacesForm(
                location="New York, NY",
                query="restaurants",
                radius=0  # Below minimum
            )

    @patch('open_webui.routers.maps.get_maps_client')
    @pytest.mark.asyncio
    async def test_find_places_partial_invalid_data(self, mock_get_client):
        """Test find_places with some invalid place data"""
        # Setup mock with mixed valid/invalid data
        valid_place = self.mock_place_data.copy()
        invalid_place = {'name': 'Invalid Place'}  # Missing required fields
        
        mock_client = Mock()
        mock_client.find_places.return_value = [valid_place, invalid_place]
        mock_get_client.return_value = mock_client
        
        # Execute
        result = await find_places(self.valid_form_data, self.mock_user)
        
        # Verify - should return only valid places
        assert isinstance(result, FindPlacesResponse)
        assert len(result.places) == 1  # Only the valid place
        assert result.places[0].name == "Joe's Pizza"

    def test_place_model_validation(self):
        """Test PlaceModel validation requirements"""
        # Test valid place model
        place = PlaceModel(**self.mock_place_data)
        assert place.name == "Joe's Pizza"
        assert place.rating == 4.5
        
        # Test with missing required fields
        with pytest.raises(ValueError):
            PlaceModel(name="Test", address="123 Main St")  # Missing required fields

    @patch('open_webui.routers.maps.get_maps_client')
    @pytest.mark.asyncio
    async def test_find_places_with_optional_parameters(self, mock_get_client):
        """Test find_places with all optional parameters"""
        # Setup form with all parameters
        form_data = FindPlacesForm(
            location="San Francisco, CA",
            query="coffee shops",
            type="cafe",
            radius=2000
        )
        
        mock_client = Mock()
        mock_client.find_places.return_value = [self.mock_place_data]
        mock_get_client.return_value = mock_client
        
        # Execute
        result = await find_places(form_data, self.mock_user)
        
        # Verify
        assert isinstance(result, FindPlacesResponse)
        assert len(result.places) == 1
        
        # Verify client was called with all parameters
        mock_client.find_places.assert_called_once_with(
            location="San Francisco, CA",
            query="coffee shops",
            place_type="cafe",
            radius=2000
        )

    @patch('open_webui.routers.maps.get_maps_client')
    @pytest.mark.asyncio
    async def test_find_places_without_optional_parameters(self, mock_get_client):
        """Test find_places with only required parameters"""
        # Setup form with minimal parameters
        form_data = FindPlacesForm(
            location="Boston, MA",
            query="museums"
        )
        
        mock_client = Mock()
        mock_client.find_places.return_value = [self.mock_place_data]
        mock_get_client.return_value = mock_client
        
        # Execute
        result = await find_places(form_data, self.mock_user)
        
        # Verify
        assert isinstance(result, FindPlacesResponse)
        assert len(result.places) == 1
        
        # Verify client was called with None for optional parameters
        mock_client.find_places.assert_called_once_with(
            location="Boston, MA",
            query="museums",
            place_type=None,
            radius=None
        )


class TestGetDirectionsEndpoint:
    """Test suite for get_directions endpoint - Task 4 verification"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_user = Mock()
        self.mock_user.id = "test_user_456"
        
        self.valid_form_data = GetDirectionsForm(
            origin="Times Square, New York",
            destination="Central Park, New York",
            mode="walking"
        )
        
        self.mock_directions_data = {
            'steps': [
                {
                    'instruction': 'Head north on Broadway toward W 43rd St',
                    'distance': '0.2 mi',
                    'duration': '3 mins'
                },
                {
                    'instruction': 'Turn right onto W 59th St',
                    'distance': '0.5 mi',
                    'duration': '8 mins'
                }
            ],
            'distance': '0.7 mi',
            'duration': '11 mins',
            'maps_url': 'https://www.google.com/maps/dir/?saddr=Times%20Square&daddr=Central%20Park'
        }

    @patch('open_webui.routers.maps.get_maps_client')
    @pytest.mark.asyncio
    async def test_get_directions_success(self, mock_get_client):
        """Test successful get_directions request"""
        # Setup mock
        mock_client = Mock()
        mock_client.get_directions.return_value = self.mock_directions_data
        mock_get_client.return_value = mock_client
        
        # Execute
        result = await get_directions(self.valid_form_data, self.mock_user)
        
        # Verify
        assert isinstance(result, GetDirectionsResponse)
        assert isinstance(result.directions, DirectionsModel)
        
        directions = result.directions
        assert len(directions.steps) == 2
        assert directions.distance == "0.7 mi"
        assert directions.duration == "11 mins"
        assert "google.com/maps" in directions.maps_url
        
        # Verify first step
        step1 = directions.steps[0]
        assert step1.instruction == "Head north on Broadway toward W 43rd St"
        assert step1.distance == "0.2 mi"
        assert step1.duration == "3 mins"
        
        # Verify client was called correctly
        mock_client.get_directions.assert_called_once_with(
            origin="Times Square, New York",
            destination="Central Park, New York",
            mode="walking"
        )

    @patch('open_webui.routers.maps.get_maps_client')
    @pytest.mark.asyncio
    async def test_get_directions_driving_mode(self, mock_get_client):
        """Test get_directions with driving mode"""
        # Setup form with driving mode
        form_data = GetDirectionsForm(
            origin="Los Angeles, CA",
            destination="San Francisco, CA",
            mode="driving"
        )
        
        mock_client = Mock()
        mock_client.get_directions.return_value = self.mock_directions_data
        mock_get_client.return_value = mock_client
        
        # Execute
        result = await get_directions(form_data, self.mock_user)
        
        # Verify
        assert isinstance(result, GetDirectionsResponse)
        
        # Verify client was called with driving mode
        mock_client.get_directions.assert_called_once_with(
            origin="Los Angeles, CA",
            destination="San Francisco, CA",
            mode="driving"
        )

    @patch('open_webui.routers.maps.get_maps_client')
    @pytest.mark.asyncio
    async def test_get_directions_maps_client_error(self, mock_get_client):
        """Test get_directions with Maps client error"""
        # Setup mock
        mock_client = Mock()
        mock_client.get_directions.side_effect = MapsClientError("No route found")
        mock_get_client.return_value = mock_client
        
        # Execute and verify exception
        with pytest.raises(HTTPException) as exc_info:
            await get_directions(self.valid_form_data, self.mock_user)
        
        assert exc_info.value.status_code == 400
        assert "No route found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_directions_empty_origin(self):
        """Test input validation - empty origin"""
        form_data = GetDirectionsForm(
            origin="",
            destination="Central Park, New York"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_directions(form_data, self.mock_user)
        
        assert exc_info.value.status_code == 400
        assert "Origin and destination are required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_directions_empty_destination(self):
        """Test input validation - empty destination"""
        form_data = GetDirectionsForm(
            origin="Times Square, New York",
            destination=""
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_directions(form_data, self.mock_user)
        
        assert exc_info.value.status_code == 400
        assert "Origin and destination are required" in str(exc_info.value.detail)

    def test_get_directions_form_validation(self):
        """Test Pydantic validation for GetDirectionsForm"""
        # Test valid form with all modes
        for mode in ['driving', 'walking', 'bicycling', 'transit']:
            valid_form = GetDirectionsForm(
                origin="New York, NY",
                destination="Boston, MA",
                mode=mode
            )
            assert valid_form.origin == "New York, NY"
            assert valid_form.destination == "Boston, MA"
            assert valid_form.mode == mode

        # Test invalid mode
        with pytest.raises(ValueError) as exc_info:
            GetDirectionsForm(
                origin="New York, NY",
                destination="Boston, MA",
                mode="flying"  # Invalid mode
            )
        assert "Mode must be one of" in str(exc_info.value)

        # Test default mode
        form = GetDirectionsForm(
            origin="NYC",
            destination="Boston"
        )
        assert form.mode == "driving"  # Default value

    def test_directions_model_validation(self):
        """Test DirectionsModel validation requirements"""
        # Test valid directions model
        directions = DirectionsModel(**self.mock_directions_data)
        assert len(directions.steps) == 2
        assert directions.distance == "0.7 mi"
        assert directions.duration == "11 mins"
        
        # Test with missing required fields
        with pytest.raises(ValueError):
            DirectionsModel(steps=[], distance="1 mi")  # Missing duration and maps_url

    @patch('open_webui.routers.maps.get_maps_client')
    @pytest.mark.asyncio
    async def test_get_directions_with_whitespace_trimming(self, mock_get_client):
        """Test get_directions with whitespace in inputs"""
        # Setup form with whitespace
        form_data = GetDirectionsForm(
            origin="  Times Square, NY  ",
            destination="  Central Park  ",
            mode="  walking  "
        )
        
        mock_client = Mock()
        mock_client.get_directions.return_value = self.mock_directions_data
        mock_get_client.return_value = mock_client
        
        # Execute
        result = await get_directions(form_data, self.mock_user)
        
        # Verify
        assert isinstance(result, GetDirectionsResponse)
        
        # Verify client was called with trimmed values
        mock_client.get_directions.assert_called_once_with(
            origin="Times Square, NY",  # Trimmed
            destination="Central Park",  # Trimmed
            mode="walking"  # Trimmed
        )

    @patch('open_webui.routers.maps.get_maps_client')
    @pytest.mark.asyncio
    async def test_get_directions_transit_mode(self, mock_get_client):
        """Test get_directions with transit mode"""
        # Setup form with transit mode
        form_data = GetDirectionsForm(
            origin="Brooklyn, NY",
            destination="Manhattan, NY",
            mode="transit"
        )
        
        mock_client = Mock()
        mock_client.get_directions.return_value = self.mock_directions_data
        mock_get_client.return_value = mock_client
        
        # Execute
        result = await get_directions(form_data, self.mock_user)
        
        # Verify
        assert isinstance(result, GetDirectionsResponse)
        
        # Verify client was called with transit mode
        mock_client.get_directions.assert_called_once_with(
            origin="Brooklyn, NY",
            destination="Manhattan, NY",
            mode="transit"
        )


# Integration test data for manual testing
INTEGRATION_TEST_CASES = [
    {
        "name": "Basic restaurant search",
        "request": {
            "location": "Times Square, New York",
            "query": "pizza restaurants"
        },
        "expected_fields": ["name", "address", "lat", "lng", "place_id", "maps_url"]
    },
    {
        "name": "Typed search with radius",
        "request": {
            "location": "San Francisco, CA",
            "query": "coffee",
            "type": "cafe",
            "radius": 1000
        },
        "expected_fields": ["name", "address", "lat", "lng", "rating"]
    },
    {
        "name": "Generic search",
        "request": {
            "location": "London, UK",
            "query": "tourist attractions"
        },
        "expected_min_results": 1
    }
]

DIRECTIONS_INTEGRATION_TEST_CASES = [
    {
        "name": "Driving directions",
        "request": {
            "origin": "Los Angeles, CA",
            "destination": "San Francisco, CA",
            "mode": "driving"
        },
        "expected_fields": ["steps", "distance", "duration", "maps_url"]
    },
    {
        "name": "Walking directions",
        "request": {
            "origin": "Times Square, New York",
            "destination": "Central Park, New York",
            "mode": "walking"
        },
        "expected_fields": ["steps", "distance", "duration"]
    },
    {
        "name": "Transit directions",
        "request": {
            "origin": "Brooklyn, NY",
            "destination": "Manhattan, NY",
            "mode": "transit"
        },
        "expected_min_steps": 1
    }
] 