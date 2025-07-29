import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

# Add the parent directory to sys.path so we can import from open_webui
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tools.maps_tool import (
    Tools, PlaceType, TravelMode, LocationValidator, MapsUsageTracker, 
    SecurityValidator, LocationParser, QueryEnhancer, NaturalLanguageProcessor
)


class TestNaturalLanguageProcessing:
    """Test natural language processing capabilities"""
    
    def test_location_parser_normalize_location(self):
        """Test location normalization"""
        # Test common variations
        assert LocationParser.normalize_location("near me") == "current location"
        assert LocationParser.normalize_location("my location") == "current location"
        assert LocationParser.normalize_location("here") == "current location"
        assert LocationParser.normalize_location("where i am") == "current location"
        
        # Test regular locations
        assert LocationParser.normalize_location("Jakarta") == "Jakarta"
        assert LocationParser.normalize_location("Senayan City Mall") == "Senayan City Mall"
    
    def test_location_parser_extract_coordinates(self):
        """Test coordinate extraction"""
        # Valid coordinates
        coords = LocationParser.extract_coordinates("-6.2088,106.8456")
        assert coords == {"lat": -6.2088, "lng": 106.8456}
        
        coords = LocationParser.extract_coordinates("40.7128, -74.0060")
        assert coords == {"lat": 40.7128, "lng": -74.0060}
        
        # Invalid coordinates
        assert LocationParser.extract_coordinates("invalid") is None
        assert LocationParser.extract_coordinates("200,300") is None  # Out of range
        assert LocationParser.extract_coordinates("Jakarta") is None
    
    def test_query_enhancer_suggest_place_type(self):
        """Test place type suggestion"""
        # Restaurant queries
        assert QueryEnhancer.suggest_place_type("sushi restaurant") == PlaceType.restaurant
        assert QueryEnhancer.suggest_place_type("where to eat") == PlaceType.restaurant
        assert QueryEnhancer.suggest_place_type("food near me") == PlaceType.restaurant
        
        # Gas station queries
        assert QueryEnhancer.suggest_place_type("gas station") == PlaceType.gas_station
        assert QueryEnhancer.suggest_place_type("need fuel") == PlaceType.gas_station
        assert QueryEnhancer.suggest_place_type("petrol station") == PlaceType.gas_station
        
        # Hospital queries
        assert QueryEnhancer.suggest_place_type("hospital") == PlaceType.hospital
        assert QueryEnhancer.suggest_place_type("medical center") == PlaceType.hospital
        assert QueryEnhancer.suggest_place_type("need doctor") == PlaceType.hospital
        
        # No match
        assert QueryEnhancer.suggest_place_type("random stuff") is None
    
    def test_query_enhancer_enhance_query(self):
        """Test query enhancement"""
        # Test removing redundant type keywords
        enhanced = QueryEnhancer.enhance_query("sushi restaurant", PlaceType.restaurant)
        assert "restaurant" not in enhanced  # Should remove redundant keyword
        assert "sushi" in enhanced
        
        # Test preserving non-redundant words
        enhanced = QueryEnhancer.enhance_query("italian food", PlaceType.restaurant)
        assert "italian" in enhanced
    
    def test_query_enhancer_extract_travel_preferences(self):
        """Test travel preference extraction"""
        # Test mode detection
        prefs = QueryEnhancer.extract_travel_preferences("drive to the mall")
        assert prefs['preferred_mode'] == 'driving'
        
        prefs = QueryEnhancer.extract_travel_preferences("walk to the park")
        assert prefs['preferred_mode'] == 'walking'
        
        prefs = QueryEnhancer.extract_travel_preferences("take the bus")
        assert prefs['preferred_mode'] == 'transit'
        
        prefs = QueryEnhancer.extract_travel_preferences("bike to work")
        assert prefs['preferred_mode'] == 'bicycling'
        
        # Test priority detection
        prefs = QueryEnhancer.extract_travel_preferences("fastest route")
        assert prefs['priority'] == 'speed'
        
        prefs = QueryEnhancer.extract_travel_preferences("scenic route")
        assert prefs['priority'] == 'scenic'
    
    def test_natural_language_processor_enhance_find_places(self):
        """Test find places parameter enhancement"""
        enhanced = NaturalLanguageProcessor.enhance_find_places_parameters(
            "near me", "sushi restaurant", None
        )
        
        assert enhanced['location'] == "current location"
        assert enhanced['type'] == PlaceType.restaurant
        assert 'suggested_type' in enhanced['enhancements']
        assert enhanced['enhancements']['suggested_type'] == 'restaurant'
    
    def test_natural_language_processor_enhance_directions(self):
        """Test directions parameter enhancement"""
        enhanced = NaturalLanguageProcessor.enhance_directions_parameters(
            "my location", "drive to the mall", None
        )
        
        assert enhanced['origin'] == "current location"
        assert enhanced['mode'] == TravelMode.driving
        assert 'suggested_mode' in enhanced['enhancements']
        assert enhanced['enhancements']['suggested_mode'] == 'driving'


class TestSecurityAndValidation:
    """Test security and validation features"""
    
    def test_location_validator_validate_location(self):
        """Test location validation"""
        # Valid locations
        assert LocationValidator.validate_location("Jakarta") is True
        assert LocationValidator.validate_location("Senayan City Mall") is True
        assert LocationValidator.validate_location("-6.2088,106.8456") is True
        
        # Invalid locations
        assert LocationValidator.validate_location("") is False
        assert LocationValidator.validate_location("a") is False  # Too short
        assert LocationValidator.validate_location("a" * 201) is False  # Too long
        assert LocationValidator.validate_location("<script>alert('xss')</script>") is False
        assert LocationValidator.validate_location("javascript:alert(1)") is False
    
    def test_location_validator_sanitize_location(self):
        """Test location sanitization"""
        # Test dangerous character removal
        sanitized = LocationValidator.sanitize_location("Jakarta<script>")
        assert "<script>" not in sanitized
        assert "Jakarta" in sanitized
        
        # Test whitespace normalization
        sanitized = LocationValidator.sanitize_location("  Jakarta   City  ")
        assert sanitized == "Jakarta City"
        
        # Test length enforcement
        long_input = "a" * 300
        sanitized = LocationValidator.sanitize_location(long_input)
        assert len(sanitized) <= 200
    
    def test_location_validator_validate_place_id(self):
        """Test place ID validation"""
        # Valid place IDs
        assert LocationValidator.validate_place_id("ChIJN1t_tDeuEmsRUsoyG83frY4") is True
        assert LocationValidator.validate_place_id("EiQyNyBDb3VsZCBTdCwgUmVkIEhpbGwsIEFDVCAyNjAzLCBBdXN0cmFsaWE") is True
        
        # Invalid place IDs
        assert LocationValidator.validate_place_id("") is False
        assert LocationValidator.validate_place_id("invalid") is False
        assert LocationValidator.validate_place_id("a" * 201) is False  # Too long
        assert LocationValidator.validate_place_id("XYZ123") is False  # Wrong format
    
    def test_maps_usage_tracker_rate_limiting(self):
        """Test rate limiting functionality"""
        # Reset usage data
        MapsUsageTracker._usage_data = {}
        
        user_id = "test_user"
        function_name = "find_places"
        
        # Should allow initial requests up to limit
        for i in range(MapsUsageTracker.RATE_LIMITS[function_name]):
            assert MapsUsageTracker.check_rate_limit(user_id, function_name) is True
        
        # Should deny request over limit
        assert MapsUsageTracker.check_rate_limit(user_id, function_name) is False
        
        # Should allow different user
        assert MapsUsageTracker.check_rate_limit("other_user", function_name) is True
        
        # Should allow different function
        assert MapsUsageTracker.check_rate_limit(user_id, "get_directions") is True
    
    def test_maps_usage_tracker_get_usage_stats(self):
        """Test usage statistics"""
        # Reset usage data
        MapsUsageTracker._usage_data = {}
        
        user_id = "test_user"
        
        # Make some requests
        MapsUsageTracker.check_rate_limit(user_id, "find_places")
        MapsUsageTracker.check_rate_limit(user_id, "find_places")
        
        stats = MapsUsageTracker.get_usage_stats(user_id)
        
        assert stats["find_places"]["used"] == 2
        assert stats["find_places"]["limit"] == 100
        assert stats["find_places"]["remaining"] == 98
        
        assert stats["get_directions"]["used"] == 0
        assert stats["get_directions"]["remaining"] == 50
    
    def test_security_validator_validate_user_permissions(self):
        """Test user permission validation"""
        # Valid user
        valid_user = {"id": "user123", "role": "user", "is_active": True}
        assert SecurityValidator.validate_user_permissions(valid_user, "find_places") is True
        
        # Admin user
        admin_user = {"id": "admin123", "role": "admin", "is_active": True}
        assert SecurityValidator.validate_user_permissions(admin_user, "find_places") is True
        
        # Invalid role
        invalid_user = {"id": "user123", "role": "invalid", "is_active": True}
        assert SecurityValidator.validate_user_permissions(invalid_user, "find_places") is False
        
        # Inactive user
        inactive_user = {"id": "user123", "role": "user", "is_active": False}
        assert SecurityValidator.validate_user_permissions(inactive_user, "find_places") is False
        
        # No user
        assert SecurityValidator.validate_user_permissions(None, "find_places") is False


class TestIntegratedFunctionality:
    """Test integrated functionality with all enhancements"""
    
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
    async def test_find_places_with_natural_language_processing(self, tools, valid_user):
        """Test find_places with full natural language processing"""
        # Reset rate limiting
        MapsUsageTracker._usage_data = {}
        
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
            assert "nlp_enhancements" in result
            assert result["nlp_enhancements"]["suggested_type"] == "restaurant"
    
    @pytest.mark.asyncio
    async def test_find_places_rate_limiting(self, tools, valid_user):
        """Test rate limiting enforcement"""
        # Reset rate limiting and set low limit for testing
        MapsUsageTracker._usage_data = {}
        original_limit = MapsUsageTracker.RATE_LIMITS["find_places"]
        MapsUsageTracker.RATE_LIMITS["find_places"] = 2  # Set low limit for testing
        
        try:
            # First two requests should succeed
            for i in range(2):
                with patch('aiohttp.ClientSession') as mock_session:
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(return_value={"places": []})
                    
                    mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
                    
                    result = await tools.find_places(
                        location="Jakarta",
                        query="restaurants",
                        __user__=valid_user
                    )
                    
                    assert result["status"] == "success"
            
            # Third request should be rate limited
            result = await tools.find_places(
                location="Jakarta",
                query="restaurants",
                __user__=valid_user
            )
            
            assert result["status"] == "error"
            assert "rate limit" in result["message"].lower()
            
        finally:
            # Restore original limit
            MapsUsageTracker.RATE_LIMITS["find_places"] = original_limit
    
    @pytest.mark.asyncio
    async def test_find_places_security_validation(self, tools):
        """Test security validation"""
        # Reset rate limiting
        MapsUsageTracker._usage_data = {}
        
        # Test with invalid user
        invalid_user = {"id": "user123", "role": "invalid", "is_active": True}
        
        result = await tools.find_places(
            location="Jakarta",
            query="restaurants",
            __user__=invalid_user
        )
        
        assert result["status"] == "error"
        assert "access denied" in result["message"].lower()
        assert result["places"] == []
    
    @pytest.mark.asyncio
    async def test_find_places_input_validation(self, tools, valid_user):
        """Test input validation"""
        # Reset rate limiting
        MapsUsageTracker._usage_data = {}
        
        # Test with malicious location
        result = await tools.find_places(
            location="<script>alert('xss')</script>",
            query="restaurants",
            __user__=valid_user
        )
        
        assert result["status"] == "error"
        assert "invalid location" in result["message"].lower()
        assert result["places"] == []
        
        # Test with empty query
        result = await tools.find_places(
            location="Jakarta",
            query="",
            __user__=valid_user
        )
        
        assert result["status"] == "error"
        assert "query must be" in result["message"].lower()
        assert result["places"] == []
    
    @pytest.mark.asyncio
    async def test_get_directions_with_nlp(self, tools, valid_user):
        """Test get_directions with natural language processing"""
        # Reset rate limiting
        MapsUsageTracker._usage_data = {}
        
        mock_response_data = {
            "route": {
                "distance": "50 km",
                "duration": "1 hour",
                "steps": []
            }
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            result = await tools.get_directions(
                origin="my location",
                destination="drive to the mall",
                __user__=valid_user
            )
            
            assert result["status"] == "success"
            assert result["travel_mode"] == "driving"
            assert "nlp_enhancements" in result
            assert result["nlp_enhancements"]["suggested_mode"] == "driving"
    
    @pytest.mark.asyncio
    async def test_place_details_validation(self, tools, valid_user):
        """Test place_details with validation"""
        # Reset rate limiting
        MapsUsageTracker._usage_data = {}
        
        # Test with invalid place ID
        result = await tools.place_details(
            place_id="invalid_place_id",
            __user__=valid_user
        )
        
        assert result["status"] == "error"
        assert "invalid place id" in result["message"].lower()
        assert result["details"] == {}
    
    @pytest.mark.asyncio
    async def test_error_handling_with_monitoring(self, tools, valid_user):
        """Test error handling includes proper monitoring information"""
        # Reset rate limiting
        MapsUsageTracker._usage_data = {}
        
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
            assert "error_details" in result
            assert "error_id" in result["error_details"]
            assert "function" in result["error_details"]
            assert "type" in result["error_details"]
            assert "timestamp" in result["error_details"]
            assert result["error_details"]["type"] == "auth"


class TestToolRegistrationIntegration:
    """Test tool registration and OpenWebUI integration"""
    
    @patch('open_webui.utils.tools.get_tool_specs')
    @patch('open_webui.utils.tools.get_functions_from_tool')
    def test_tool_specs_generation_with_enhancements(self, mock_get_functions, mock_get_specs):
        """Test that enhanced tool generates proper specs"""
        tools_instance = Tools()
        
        # Mock the functions discovery
        mock_functions = [tools_instance.find_places, tools_instance.get_directions, tools_instance.place_details]
        mock_get_functions.return_value = mock_functions
        
        # Mock the specs generation
        mock_specs = [
            {
                "name": "find_places",
                "description": "Find places of interest using natural language search queries.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                        "query": {"type": "string"},
                        "type": {"type": "string", "enum": ["restaurant", "gas_station", "hospital"]},
                        "radius": {"type": "integer"}
                    },
                    "required": ["location", "query"]
                }
            }
        ]
        mock_get_specs.return_value = mock_specs
        
        # Import and test the actual function
        from utils.tools import get_tool_specs
        specs = get_tool_specs(tools_instance)
        
        assert len(specs) >= 1
        assert any(spec["name"] == "find_places" for spec in specs)
        
        # Verify the function was called with our tools instance
        mock_get_functions.assert_called_once_with(tools_instance)


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
        # Reset rate limiting
        MapsUsageTracker._usage_data = {}
        
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
                if "nlp_enhancements" in result:
                    assert result["nlp_enhancements"].get("suggested_type") == "restaurant"
    
    @pytest.mark.asyncio
    async def test_direction_queries(self, tools, valid_user):
        """Test various direction query patterns"""
        # Reset rate limiting
        MapsUsageTracker._usage_data = {}
        
        test_cases = [
            ("my location", "drive to the mall", "driving"),
            ("home", "walk to the park", "walking"),
            ("office", "bike to gym", "bicycling"),
            ("Jakarta", "take bus to Bandung", "transit")
        ]
        
        for origin, destination, expected_mode in test_cases:
            with patch('aiohttp.ClientSession') as mock_session:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value={"route": {}})
                
                mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
                
                result = await tools.get_directions(
                    origin=origin,
                    destination=destination,
                    __user__=valid_user
                )
                
                assert result["status"] == "success"
                assert result["travel_mode"] == expected_mode
                
                # Should detect travel mode from natural language
                if "nlp_enhancements" in result:
                    assert result["nlp_enhancements"].get("suggested_mode") == expected_mode 