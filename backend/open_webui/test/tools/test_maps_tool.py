import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from open_webui.utils.plugin import load_tool_module_by_id


class TestMapsToolModule:
    """Test suite for the Google Maps Tool module"""

    @pytest.fixture
    def maps_tool_content(self):
        """Load the maps tool content for testing"""
        tool_file_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'tools', 'maps_tool.py'
        )
        with open(tool_file_path, 'r', encoding='utf-8') as f:
            return f.read()

    @pytest.fixture
    def mock_user(self):
        """Mock user object with authentication token"""
        return {
            "id": "test_user_123",
            "name": "Test User",
            "token": {
                "credentials": "test_bearer_token_123"
            }
        }

    @pytest.fixture
    def sample_places_response(self):
        """Sample response from maps/find_places endpoint"""
        return {
            "places": [
                {
                    "name": "Sushi Tei Senayan",
                    "address": "Senayan City, Jakarta",
                    "lat": -6.2251,
                    "lng": 106.7982,
                    "place_id": "ChIJ123sushi",
                    "rating": 4.5,
                    "open_now": True,
                    "maps_url": "https://maps.google.com/place123",
                    "distance": "500m",
                    "price_level": 2
                }
            ]
        }

    @pytest.fixture
    def sample_directions_response(self):
        """Sample response from maps/get_directions endpoint"""
        return {
            "directions": {
                "origin": "Jakarta",
                "destination": "Bandung",
                "distance": "150 km",
                "duration": "3 hours 30 minutes",
                "steps": [
                    {"instruction": "Head north on Jl. Sudirman", "distance": "2 km"},
                    {"instruction": "Take the toll road to Bandung", "distance": "148 km"}
                ],
                "maps_url": "https://maps.google.com/directions123",
                "warnings": []
            }
        }

    @pytest.fixture
    def sample_place_details_response(self):
        """Sample response from maps/place_details endpoint"""
        return {
            "place_details": {
                "details": {
                    "name": "Sushi Tei Senayan",
                    "formatted_address": "Senayan City, Lt. 3, Jakarta",
                    "phone": "+62-21-12345678",
                    "website": "https://sushitei.com",
                    "rating": 4.5,
                    "user_ratings_total": 150,
                    "lat": -6.2251,
                    "lng": 106.7982,
                    "opening_hours": {"open_now": True},
                    "price_level": 2,
                    "types": ["restaurant", "food", "establishment"]
                },
                "reviews": [
                    {"author": "John D.", "rating": 5, "text": "Great sushi!"}
                ],
                "photos": ["photo1.jpg", "photo2.jpg"],
                "maps_url": "https://maps.google.com/place123"
            }
        }

    def test_tool_module_loading(self, maps_tool_content):
        """Test that the tool module can be loaded and has proper structure"""
        # Load the tool module
        tool_instance, frontmatter = load_tool_module_by_id("test_maps_tool", maps_tool_content)
        
        # Verify frontmatter
        assert frontmatter["title"] == "Google Maps Tool"
        assert frontmatter["description"].startswith("Find places, get directions")
        assert frontmatter["version"] == "1.0.0"
        assert "aiohttp" in frontmatter["requirements"]
        
        # Verify tool instance
        assert hasattr(tool_instance, 'find_places')
        assert hasattr(tool_instance, 'get_directions') 
        assert hasattr(tool_instance, 'place_details')
        assert hasattr(tool_instance, '_make_request')

    @pytest.mark.asyncio
    async def test_find_places_success(self, maps_tool_content, mock_user, sample_places_response):
        """Test successful find_places function call"""
        tool_instance, _ = load_tool_module_by_id("test_maps_tool", maps_tool_content)
        
        # Mock the HTTP request
        with patch.object(tool_instance, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_places_response
            
            result = await tool_instance.find_places(
                location="Senayan",
                query="sushi restaurants",
                type="restaurant",
                __user__=mock_user
            )
            
            # Verify request was made correctly
            mock_request.assert_called_once_with(
                "/maps/find_places",
                {
                    "location": "Senayan",
                    "query": "sushi restaurants", 
                    "radius": 5000,
                    "type": "restaurant"
                },
                "test_bearer_token_123"
            )
            
            # Verify response format
            assert result["status"] == "success"
            assert len(result["places"]) == 1
            assert result["places"][0]["name"] == "Sushi Tei Senayan"
            assert "coordinates" in result["places"][0]
            assert result["message"].startswith("Found 1 places")

    @pytest.mark.asyncio
    async def test_find_places_missing_parameters(self, maps_tool_content, mock_user):
        """Test find_places with missing required parameters"""
        tool_instance, _ = load_tool_module_by_id("test_maps_tool", maps_tool_content)
        
        # Test missing location
        result = await tool_instance.find_places(
            location="",
            query="restaurants",
            __user__=mock_user
        )
        assert result["status"] == "error"
        assert "required parameters" in result["message"]
        
        # Test missing query
        result = await tool_instance.find_places(
            location="Jakarta",
            query="",
            __user__=mock_user
        )
        assert result["status"] == "error"
        assert "required parameters" in result["message"]

    @pytest.mark.asyncio
    async def test_find_places_missing_auth(self, maps_tool_content):
        """Test find_places without authentication"""
        tool_instance, _ = load_tool_module_by_id("test_maps_tool", maps_tool_content)
        
        result = await tool_instance.find_places(
            location="Jakarta",
            query="restaurants",
            __user__={}  # No token
        )
        
        assert result["status"] == "error"
        assert "authentication required" in result["message"]

    @pytest.mark.asyncio
    async def test_get_directions_success(self, maps_tool_content, mock_user, sample_directions_response):
        """Test successful get_directions function call"""
        tool_instance, _ = load_tool_module_by_id("test_maps_tool", maps_tool_content)
        
        with patch.object(tool_instance, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_directions_response
            
            result = await tool_instance.get_directions(
                origin="Jakarta",
                destination="Bandung",
                mode="driving",
                __user__=mock_user
            )
            
            # Verify request
            mock_request.assert_called_once_with(
                "/maps/get_directions",
                {
                    "origin": "Jakarta",
                    "destination": "Bandung",
                    "mode": "driving"
                },
                "test_bearer_token_123"
            )
            
            # Verify response
            assert result["status"] == "success"
            assert result["directions"]["summary"]["distance"] == "150 km"
            assert len(result["directions"]["steps"]) == 2

    @pytest.mark.asyncio
    async def test_get_directions_invalid_mode(self, maps_tool_content, mock_user, sample_directions_response):
        """Test get_directions with invalid travel mode defaults to driving"""
        tool_instance, _ = load_tool_module_by_id("test_maps_tool", maps_tool_content)
        
        with patch.object(tool_instance, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_directions_response
            
            result = await tool_instance.get_directions(
                origin="Jakarta",
                destination="Bandung", 
                mode="flying",  # Invalid mode
                __user__=mock_user
            )
            
            # Should default to driving
            mock_request.assert_called_once()
            call_args = mock_request.call_args[0]
            assert call_args[1]["mode"] == "driving"

    @pytest.mark.asyncio
    async def test_place_details_success(self, maps_tool_content, mock_user, sample_place_details_response):
        """Test successful place_details function call"""
        tool_instance, _ = load_tool_module_by_id("test_maps_tool", maps_tool_content)
        
        with patch.object(tool_instance, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_place_details_response
            
            result = await tool_instance.place_details(
                place_id="ChIJ123sushi",
                __user__=mock_user
            )
            
            # Verify request
            mock_request.assert_called_once_with(
                "/maps/place_details",
                {"place_id": "ChIJ123sushi"},
                "test_bearer_token_123"
            )
            
            # Verify response structure
            assert result["status"] == "success"
            details = result["place_details"]
            assert "basic_info" in details
            assert "location" in details
            assert "business_info" in details
            assert details["basic_info"]["name"] == "Sushi Tei Senayan"
            assert len(details["reviews"]) <= 5  # Limited reviews
            assert len(details["photos"]) <= 3   # Limited photos

    @pytest.mark.asyncio
    async def test_place_details_missing_place_id(self, maps_tool_content, mock_user):
        """Test place_details with missing place_id"""
        tool_instance, _ = load_tool_module_by_id("test_maps_tool", maps_tool_content)
        
        result = await tool_instance.place_details(
            place_id="",
            __user__=mock_user
        )
        
        assert result["status"] == "error"
        assert "Place ID is required" in result["message"]

    @pytest.mark.asyncio
    async def test_make_request_http_error(self, maps_tool_content, mock_user):
        """Test _make_request method handling HTTP errors"""
        tool_instance, _ = load_tool_module_by_id("test_maps_tool", maps_tool_content)
        
        # Mock aiohttp session
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad Request")
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with pytest.raises(Exception) as exc_info:
                await tool_instance._make_request("/maps/test", {}, "token")
            
            assert "Maps API error (400)" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_radius_validation(self, maps_tool_content, mock_user, sample_places_response):
        """Test that radius parameter is properly clamped"""
        tool_instance, _ = load_tool_module_by_id("test_maps_tool", maps_tool_content)
        
        with patch.object(tool_instance, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_places_response
            
            # Test radius too small (should be clamped to 100)
            await tool_instance.find_places(
                location="Jakarta",
                query="restaurants",
                radius=50,
                __user__=mock_user
            )
            
            call_args = mock_request.call_args[0]
            assert call_args[1]["radius"] == 100
            
            # Test radius too large (should be clamped to 50000)
            await tool_instance.find_places(
                location="Jakarta", 
                query="restaurants",
                radius=100000,
                __user__=mock_user
            )
            
            call_args = mock_request.call_args[0]
            assert call_args[1]["radius"] == 50000

    def test_tool_function_signatures(self, maps_tool_content):
        """Test that all tool functions have the required __user__ and __id__ parameters"""
        tool_instance, _ = load_tool_module_by_id("test_maps_tool", maps_tool_content)
        
        import inspect
        
        # Check find_places signature
        sig = inspect.signature(tool_instance.find_places)
        assert '__user__' in sig.parameters
        assert '__id__' in sig.parameters
        assert sig.parameters['__user__'].default == {}
        assert sig.parameters['__id__'].default is None
        
        # Check get_directions signature
        sig = inspect.signature(tool_instance.get_directions)
        assert '__user__' in sig.parameters
        assert '__id__' in sig.parameters
        
        # Check place_details signature
        sig = inspect.signature(tool_instance.place_details)
        assert '__user__' in sig.parameters
        assert '__id__' in sig.parameters 