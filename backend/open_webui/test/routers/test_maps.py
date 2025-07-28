import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

from open_webui.models.maps import FindPlacesForm, PlaceModel, FindPlacesResponse
from open_webui.routers.maps import find_places
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