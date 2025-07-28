import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from open_webui.utils.plugin import load_tool_module_by_id
from open_webui.utils.maps_tool_registration import MapsToolRegistration


class TestMapsToolIntegration:
    """Integration tests for Tasks 3-7: Enhanced maps tool functionality"""

    @pytest.fixture
    def maps_tool_content(self):
        """Load the enhanced maps tool content"""
        tool_file_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'tools', 'maps_tool.py'
        )
        with open(tool_file_path, 'r', encoding='utf-8') as f:
            return f.read()

    @pytest.fixture
    def tool_instance(self, maps_tool_content):
        """Load enhanced tool instance"""
        tool_instance, _ = load_tool_module_by_id("test_maps_tool", maps_tool_content)
        return tool_instance

    @pytest.fixture
    def mock_user_with_rate_limit(self):
        """Mock user for rate limiting tests"""
        return {
            "id": "rate_limit_user",
            "name": "Rate Limit Test User",
            "token": {
                "credentials": "test_bearer_token_123"
            }
        }

    @pytest.fixture
    def sample_success_response(self):
        """Sample successful API response"""
        return {
            "places": [
                {
                    "name": "Test Restaurant",
                    "address": "123 Test Street",
                    "lat": -6.2088,
                    "lng": 106.8456,
                    "place_id": "ChIJtest123",
                    "rating": 4.5,
                    "open_now": True,
                    "maps_url": "https://maps.google.com/test",
                    "distance": "500m",
                    "price_level": 2
                }
            ]
        }

    def test_tool_registration_functionality(self):
        """Test Task 3: Tool Registration Integration"""
        # Test registration helper class
        assert hasattr(MapsToolRegistration, 'register_tool')
        assert hasattr(MapsToolRegistration, 'unregister_tool')
        assert hasattr(MapsToolRegistration, 'is_registered')
        assert hasattr(MapsToolRegistration, 'get_tool_info')
        
        # Test tool ID and name constants
        assert MapsToolRegistration.TOOL_ID == "google_maps_tool"
        assert MapsToolRegistration.TOOL_NAME == "Google Maps Integration"

    @pytest.mark.asyncio
    async def test_rate_limiting_functionality(self, tool_instance, mock_user_with_rate_limit):
        """Test Task 6: Rate limiting and usage tracking"""
        # Test rate limit validation
        user_access = tool_instance._validate_user_access(mock_user_with_rate_limit, 'find_places')
        assert user_access is True  # First call should be allowed
        
        # Test usage tracking
        from open_webui.tools.maps_tool import MapsUsageTracker
        
        user_id = mock_user_with_rate_limit['id']
        MapsUsageTracker.track_usage(user_id, 'find_places')
        
        stats = MapsUsageTracker.get_usage_stats(user_id)
        assert 'find_places' in stats
        assert stats['find_places'] >= 1

    @pytest.mark.asyncio
    async def test_input_validation_security(self, tool_instance, mock_user_with_rate_limit):
        """Test Task 6: Input validation and security"""
        # Test location validation
        from open_webui.tools.maps_tool import LocationParser
        
        # Valid locations
        assert LocationParser.validate_location_input("Jakarta") is True
        assert LocationParser.validate_location_input("123 Main Street") is True
        
        # Invalid locations
        assert LocationParser.validate_location_input("") is False
        assert LocationParser.validate_location_input("<script>alert('xss')</script>") is False
        assert LocationParser.validate_location_input("javascript:alert(1)") is False
        assert LocationParser.validate_location_input("a" * 250) is False  # Too long
        
        # Test parameter validation through tool functions
        with patch.object(tool_instance, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"places": []}
            
            # Test malicious input
            result = await tool_instance.find_places(
                location="<script>alert('xss')</script>",
                query="restaurants",
                __user__=mock_user_with_rate_limit
            )
            
            assert result["status"] == "error"
            assert "Invalid location input" in result["message"]

    @pytest.mark.asyncio
    async def test_natural_language_processing(self, tool_instance, mock_user_with_rate_limit):
        """Test Task 7: Natural Language Processing and query enhancement"""
        from open_webui.tools.maps_tool import QueryEnhancer, LocationParser
        
        # Test place type suggestion
        suggestions = [
            ("sushi restaurants", "restaurant"),
            ("gas stations", "gas_station"),
            ("hospitals nearby", "hospital"),
            ("find ATM", "bank"),
            ("shopping mall", "shopping_mall")
        ]
        
        for query, expected_type in suggestions:
            suggested = QueryEnhancer.suggest_place_type(query)
            assert suggested == expected_type
        
        # Test location normalization
        normalized = LocationParser.normalize_location("jl. sudirman no. 1")
        assert "jalan" in normalized.lower()
        assert "no. 1" in normalized
        
        # Test coordinate extraction
        coords = LocationParser.extract_coordinates("-6.2088, 106.8456")
        assert coords is not None
        assert coords["lat"] == -6.2088
        assert coords["lng"] == 106.8456
        
        # Test invalid coordinates
        invalid_coords = LocationParser.extract_coordinates("invalid coordinates")
        assert invalid_coords is None

    @pytest.mark.asyncio
    async def test_enhanced_error_handling(self, tool_instance, mock_user_with_rate_limit):
        """Test Task 5: Enhanced error handling and formatting"""
        # Test error response formatting
        test_error = ValueError("Test validation error")
        error_response = tool_instance._format_error_response('find_places', test_error, 'test_user')
        
        assert error_response["status"] == "error"
        assert "error_id" in error_response
        assert "places" in error_response  # Function-specific structure
        assert error_response["places"] == []
        
        # Test different error types
        auth_error = Exception("Authentication failed - invalid token")
        auth_response = tool_instance._format_error_response('find_places', auth_error, 'test_user')
        assert "Authentication failed" in auth_response["message"]
        
        rate_limit_error = Exception("Rate limit exceeded")
        rate_response = tool_instance._format_error_response('find_places', rate_limit_error, 'test_user')
        assert "Too many requests" in rate_response["message"]

    @pytest.mark.asyncio
    async def test_parameter_enhancement_integration(self, tool_instance, mock_user_with_rate_limit, sample_success_response):
        """Test Task 4 & 7: Parameter mapping and NLP enhancement integration"""
        with patch.object(tool_instance, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_success_response
            
            # Test enhanced find_places call
            result = await tool_instance.find_places(
                location="jl sudirman",  # Should be normalized
                query="sushi restaurant",  # Should suggest restaurant type
                radius=10000,
                __user__=mock_user_with_rate_limit
            )
            
            assert result["status"] == "success"
            assert "search_info" in result
            
            search_info = result["search_info"]
            assert "original_location" in search_info
            assert "normalized_location" in search_info
            assert "suggested_type" in search_info
            assert search_info["suggested_type"] == "restaurant"

    @pytest.mark.asyncio
    async def test_comprehensive_validation_workflow(self, tool_instance, mock_user_with_rate_limit):
        """Test complete validation workflow from Tasks 4-7"""
        # Test parameter validation and enhancement
        validated_params = tool_instance._validate_and_enhance_parameters(
            'find_places',
            location="Jakarta",
            query="sushi restaurants",
            radius=2000
        )
        
        assert validated_params['location'] == "Jakarta"
        assert validated_params['query'] == "sushi restaurants"
        assert validated_params['radius'] == 2000
        assert validated_params['type'] == "restaurant"  # Should be suggested
        assert '_enhancements' in validated_params

    @pytest.mark.asyncio
    async def test_function_calling_middleware_compatibility(self, tool_instance):
        """Test Task 4: LLM Function Calling Implementation compatibility"""
        import inspect
        
        # Test that all functions have required middleware parameters
        functions = ['find_places', 'get_directions', 'place_details']
        
        for func_name in functions:
            func = getattr(tool_instance, func_name)
            sig = inspect.signature(func)
            
            # Required for OpenWebUI tool middleware
            assert '__user__' in sig.parameters
            assert '__id__' in sig.parameters
            
            # Should be async for proper middleware integration
            assert inspect.iscoroutinefunction(func)

    @pytest.mark.asyncio
    async def test_error_propagation_and_logging(self, tool_instance, mock_user_with_rate_limit):
        """Test Task 5: Error handling and logging integration"""
        with patch.object(tool_instance, '_make_request', new_callable=AsyncMock) as mock_request:
            # Simulate different types of API errors
            mock_request.side_effect = Exception("Network error - unable to connect")
            
            result = await tool_instance.find_places(
                location="Jakarta",
                query="restaurants",
                __user__=mock_user_with_rate_limit
            )
            
            assert result["status"] == "error"
            assert "error_id" in result
            assert "Network error occurred" in result["message"]

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, tool_instance):
        """Test Task 6: Rate limiting enforcement"""
        from open_webui.tools.maps_tool import MapsUsageTracker
        
        user_id = "heavy_user"
        function_name = "find_places"
        
        # Simulate usage up to limit
        for i in range(100):  # Default limit per hour
            MapsUsageTracker.track_usage(user_id, function_name)
        
        # Should still be under limit
        assert MapsUsageTracker.check_rate_limit(user_id, function_name, 100) is True
        
        # Add one more to exceed
        MapsUsageTracker.track_usage(user_id, function_name)
        
        # Should now be over limit
        assert MapsUsageTracker.check_rate_limit(user_id, function_name, 100) is False

    @pytest.mark.asyncio
    async def test_enhanced_response_formatting(self, tool_instance, mock_user_with_rate_limit, sample_success_response):
        """Test Task 4 & 5: Enhanced response formatting for LLM consumption"""
        with patch.object(tool_instance, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_success_response
            
            result = await tool_instance.find_places(
                location="Jakarta",
                query="restaurants",
                __user__=mock_user_with_rate_limit
            )
            
            # Test enhanced response structure
            assert "search_info" in result
            assert "places" in result
            assert "status" in result
            assert "message" in result
            
            # Test place formatting
            place = result["places"][0]
            assert "coordinates" in place
            assert "lat" in place["coordinates"]
            assert "lng" in place["coordinates"]
            
            # Test search info details
            search_info = result["search_info"]
            assert "original_location" in search_info
            assert "normalized_location" in search_info
            assert "radius_meters" in search_info

    def test_tool_specs_with_enhancements(self, tool_instance):
        """Test that enhanced tool generates proper specifications"""
        from open_webui.utils.tools import get_tool_specs
        
        specs = get_tool_specs(tool_instance)
        
        # Should have all three functions
        assert len(specs) == 3
        function_names = [spec["name"] for spec in specs]
        assert "find_places" in function_names
        assert "get_directions" in function_names
        assert "place_details" in function_names
        
        # Test enhanced descriptions
        for spec in specs:
            assert len(spec["description"]) > 50  # Should be detailed
            
            # Should have proper OpenAI format
            assert spec["type"] == "function"
            assert "parameters" in spec
            assert "properties" in spec["parameters"]
            assert "required" in spec["parameters"] 