import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

# Add the parent directory to sys.path so we can import from open_webui
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tools.maps_tool import (
    Tools, PlaceType, TravelMode, BasicValidator, MapsAPIClient, 
    NaturalLanguageProcessor
)


class TestNaturalLanguageProcessing:
    """Test natural language processing capabilities"""
    
    def test_natural_language_processor_normalize_location(self):
        """Test location normalization"""
        # Test common variations
        assert NaturalLanguageProcessor.normalize_location("near me") == "current location"
        assert NaturalLanguageProcessor.normalize_location("my location") == "current location"
        assert NaturalLanguageProcessor.normalize_location("here") == "current location"
        assert NaturalLanguageProcessor.normalize_location("where i am") == "current location"
        
        # Test regular locations
        assert NaturalLanguageProcessor.normalize_location("Jakarta") == "Jakarta"
        assert NaturalLanguageProcessor.normalize_location("Senayan City Mall") == "Senayan City Mall"
    
    def test_natural_language_processor_suggest_place_type(self):
        """Test place type suggestion"""
        # Restaurant queries
        assert NaturalLanguageProcessor.suggest_place_type("sushi restaurant") == PlaceType.restaurant
        assert NaturalLanguageProcessor.suggest_place_type("where to eat") == PlaceType.restaurant
        assert NaturalLanguageProcessor.suggest_place_type("food near me") == PlaceType.restaurant
        
        # Gas station queries
        assert NaturalLanguageProcessor.suggest_place_type("gas station") == PlaceType.gas_station
        assert NaturalLanguageProcessor.suggest_place_type("need fuel") == PlaceType.gas_station
        assert NaturalLanguageProcessor.suggest_place_type("petrol station") == PlaceType.gas_station
        
        # Hospital queries
        assert NaturalLanguageProcessor.suggest_place_type("hospital") == PlaceType.hospital
        assert NaturalLanguageProcessor.suggest_place_type("medical center") == PlaceType.hospital
        assert NaturalLanguageProcessor.suggest_place_type("need doctor") == PlaceType.hospital
        
        # No match
        assert NaturalLanguageProcessor.suggest_place_type("random stuff") is None


class TestBasicValidation:
    """Test basic validation features"""
    
    def test_basic_validator_validate_location(self):
        """Test location validation"""
        # Valid locations
        assert BasicValidator.validate_location("Jakarta") is True
        assert BasicValidator.validate_location("Senayan City Mall") is True
        assert BasicValidator.validate_location("-6.2088,106.8456") is True
        
        # Invalid locations
        assert BasicValidator.validate_location("") is False
        assert BasicValidator.validate_location("a") is False  # Too short
        assert BasicValidator.validate_location("a" * 201) is False  # Too long
        assert BasicValidator.validate_location(None) is False
    
    def test_basic_validator_validate_query(self):
        """Test query validation"""
        # Valid queries
        assert BasicValidator.validate_query("restaurant") is True
        assert BasicValidator.validate_query("gas station") is True
        
        # Invalid queries
        assert BasicValidator.validate_query("") is False
        assert BasicValidator.validate_query("a" * 201) is False  # Too long
        assert BasicValidator.validate_query(None) is False
    
    def test_basic_validator_validate_place_id(self):
        """Test place ID validation"""
        # Valid place IDs
        assert BasicValidator.validate_place_id("ChIJN1t_tDeuEmsRUsoyG83frY4") is True
        assert BasicValidator.validate_place_id("EiQyNyBDb3VsZCBTdCwgUmVkIEhpbGwsIEFDVCAyNjAzLCBBdXN0cmFsaWE") is True
        
        # Invalid place IDs
        assert BasicValidator.validate_place_id("") is False
        assert BasicValidator.validate_place_id("invalid") is False
        assert BasicValidator.validate_place_id("a" * 201) is False  # Too long
        assert BasicValidator.validate_place_id(None) is False


class TestHTTPAPIIntegration:
    """Test HTTP API integration functionality"""
    
    @pytest.fixture
    def tools(self):
        return Tools()
    
    @pytest.fixture
    def valid_user(self):
        return {
            "id": "test_user_123",
            "role": "user",
            "is_active": True,
            "token": "test_auth_token"
        }
    
    @pytest.mark.asyncio
    async def test_find_places_http_integration(self, tools, valid_user):
        """Test find_places with HTTP API calls"""
        mock_response_data = {
            "places": [
                {
                    "name": "Sushi Restaurant",
                    "address": "123 Test St",
                    "lat": -6.2088,
                    "lng": 106.8456,
                    "place_id": "ChIJ123",
                    "rating": 4.5
                }
            ]
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            result = await tools.find_places(
                location="near me",
                query="sushi restaurant",
                __user__=valid_user,
                __id__="test_id"
            )
            
            assert result["status"] == "success"
            assert len(result["places"]) == 1
            assert result["places"][0]["name"] == "Sushi Restaurant"
            assert result["search_location"] == "current location"  # Normalized
            assert result["suggested_type"] == "restaurant"  # NLP suggested
    
    @pytest.mark.asyncio
    async def test_get_directions_http_integration(self, tools, valid_user):
        """Test get_directions with HTTP API calls"""
        mock_response_data = {
            "route": {
                "distance": "50 km",
                "duration": "1 hour",
                "steps": [
                    {"instruction": "Head north", "distance": "1 km"}
                ]
            }
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            result = await tools.get_directions(
                origin="my location",
                destination="Jakarta",
                mode=TravelMode.driving,
                __user__=valid_user
            )
            
            assert result["status"] == "success"
            assert result["route"]["distance"] == "50 km"
            assert result["travel_mode"] == "driving"
            assert result["origin"] == "current location"  # Normalized
    
    @pytest.mark.asyncio
    async def test_place_details_http_integration(self, tools, valid_user):
        """Test place_details with HTTP API calls"""
        mock_response_data = {
            "details": {
                "name": "Test Restaurant",
                "address": "123 Test Street",
                "phone": "+1234567890",
                "rating": 4.5
            }
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            result = await tools.place_details(
                place_id="ChIJN1t_tDeuEmsRUsoyG83frY4",
                __user__=valid_user
            )
            
            assert result["status"] == "success"
            assert result["details"]["name"] == "Test Restaurant"
            assert result["place_name"] == "Test Restaurant"
    
    @pytest.mark.asyncio
    async def test_http_authentication_error(self, tools, valid_user):
        """Test handling of HTTP authentication errors"""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_response.text = AsyncMock(return_value="Unauthorized")
            
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            result = await tools.find_places(
                location="Jakarta",
                query="restaurants",
                __user__=valid_user
            )
            
            assert result["status"] == "error"
            assert "authentication failed" in result["message"].lower()
            assert result["error_details"]["type"] == "auth"
    
    @pytest.mark.asyncio
    async def test_http_rate_limit_error(self, tools, valid_user):
        """Test handling of HTTP rate limit errors"""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 429
            mock_response.text = AsyncMock(return_value="Too Many Requests")
            
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            result = await tools.find_places(
                location="Jakarta",
                query="restaurants",
                __user__=valid_user
            )
            
            assert result["status"] == "error"
            assert "rate limit" in result["message"].lower()
            assert result["error_details"]["type"] == "rate_limit"
    
    @pytest.mark.asyncio
    async def test_input_validation_errors(self, tools, valid_user):
        """Test input validation error handling"""
        # Test invalid location
        result = await tools.find_places(
            location="",  # Empty location
            query="restaurants",
            __user__=valid_user
        )
        
        assert result["status"] == "error"
        assert "invalid location" in result["message"].lower()
        assert result["error_details"]["type"] == "validation"
        
        # Test invalid query  
        result = await tools.find_places(
            location="Jakarta",
            query="",  # Empty query
            __user__=valid_user
        )
        
        assert result["status"] == "error"
        assert "query must be" in result["message"].lower()
        assert result["error_details"]["type"] == "validation"
        
        # Test invalid place ID
        result = await tools.place_details(
            place_id="invalid",  # Too short
            __user__=valid_user
        )
        
        assert result["status"] == "error"
        assert "invalid place id" in result["message"].lower()
        assert result["error_details"]["type"] == "validation"


class TestNaturalLanguageExamples:
    """Test natural language query handling with real-world examples"""
    
    @pytest.fixture
    def tools(self):
        return Tools()
    
    @pytest.fixture
    def valid_user(self):
        return {
            "id": "test_user",
            "role": "user",
            "is_active": True,
            "token": "test_token"
        }
    
    @pytest.mark.asyncio
    async def test_restaurant_queries(self, tools, valid_user):
        """Test various restaurant query patterns"""
        test_cases = [
            ("near me", "sushi restaurants"),
            ("Jakarta", "italian food"),
            ("Senayan", "where to eat"),
            ("current location", "best restaurants")
        ]
        
        for location, query in test_cases:
            with patch('aiohttp.ClientSession') as mock_session:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value={"places": []})
                
                mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
                
                result = await tools.find_places(
                    location=location,
                    query=query,
                    __user__=valid_user
                )
                
                assert result["status"] == "success"
                # Should suggest restaurant type for food-related queries
                assert result.get("suggested_type") == "restaurant"
    
    @pytest.mark.asyncio
    async def test_error_response_structure(self, tools, valid_user):
        """Test that error responses include proper monitoring information"""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")
            
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            result = await tools.find_places(
                location="Jakarta",
                query="restaurants",
                __user__=valid_user
            )
            
            assert result["status"] == "error"
            assert "error_details" in result
            assert "error_id" in result["error_details"]
            assert "function" in result["error_details"]
            assert "type" in result["error_details"]
            assert "timestamp" in result["error_details"]
            assert result["error_details"]["function"] == "find_places"


class TestAPIClientDirectly:
    """Test the MapsAPIClient class directly"""
    
    @pytest.mark.asyncio
    async def test_successful_api_request(self):
        """Test successful API request"""
        test_data = {"test": "data"}
        mock_response_data = {"result": "success"}
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            result = await MapsAPIClient._make_request(
                endpoint="/test_endpoint",
                data=test_data,
                user_token="test_token"
            )
            
            assert result == mock_response_data
            
            # Verify the request was made correctly
            mock_session.return_value.__aenter__.return_value.post.assert_called_once()
            call_args = mock_session.return_value.__aenter__.return_value.post.call_args
            assert "/test_endpoint" in call_args[0][0]  # URL contains endpoint
            assert call_args[1]['json'] == test_data  # JSON data passed
            assert call_args[1]['headers']['Authorization'] == "Bearer test_token"  # Auth header
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test API error handling"""
        test_data = {"test": "data"}
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value="Bad Request")
            
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(Exception) as exc_info:
                await MapsAPIClient._make_request(
                    endpoint="/test_endpoint",
                    data=test_data
                )
            
            assert "400" in str(exc_info.value)
            assert "Bad Request" in str(exc_info.value) 