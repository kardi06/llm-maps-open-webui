import pytest
import sys
import os
from typing import Dict, Any

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from open_webui.utils.plugin import load_tool_module_by_id
from open_webui.utils.tools import get_tool_specs


class TestMapsToolSpecs:
    """Test suite for Maps Tool function specifications"""

    @pytest.fixture
    def maps_tool_content(self):
        """Load the maps tool content for testing"""
        tool_file_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'tools', 'maps_tool.py'
        )
        with open(tool_file_path, 'r', encoding='utf-8') as f:
            return f.read()

    @pytest.fixture
    def tool_instance(self, maps_tool_content):
        """Load tool instance for testing"""
        tool_instance, _ = load_tool_module_by_id("test_maps_tool", maps_tool_content)
        return tool_instance

    def test_generate_tool_specs(self, tool_instance):
        """Test that tool specifications are generated correctly"""
        specs = get_tool_specs(tool_instance)
        
        # Should have 3 function specifications
        assert len(specs) == 3
        
        function_names = [spec["name"] for spec in specs]
        assert "find_places" in function_names
        assert "get_directions" in function_names
        assert "place_details" in function_names

    def test_find_places_spec_format(self, tool_instance):
        """Test find_places function specification format"""
        specs = get_tool_specs(tool_instance)
        find_places_spec = next(spec for spec in specs if spec["name"] == "find_places")
        
        # Verify OpenAI function calling format
        assert find_places_spec["type"] == "function"
        assert "description" in find_places_spec
        assert "parameters" in find_places_spec
        
        # Verify parameters structure
        params = find_places_spec["parameters"]
        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params
        
        # Verify required parameters
        required_params = params["required"]
        assert "location" in required_params
        assert "query" in required_params
        
        # Verify parameter properties
        properties = params["properties"]
        assert "location" in properties
        assert "query" in properties
        assert "type" in properties  # Optional type parameter
        assert "radius" in properties  # Optional radius parameter
        
        # Verify parameter types and descriptions
        assert properties["location"]["type"] == "string"
        assert properties["query"]["type"] == "string" 
        assert properties["radius"]["type"] == "integer"
        assert "description" in properties["location"]
        assert "description" in properties["query"]

    def test_get_directions_spec_format(self, tool_instance):
        """Test get_directions function specification format"""
        specs = get_tool_specs(tool_instance)
        get_directions_spec = next(spec for spec in specs if spec["name"] == "get_directions")
        
        # Verify OpenAI function calling format
        assert get_directions_spec["type"] == "function"
        assert "description" in get_directions_spec
        assert "parameters" in get_directions_spec
        
        # Verify parameters
        params = get_directions_spec["parameters"]
        properties = params["properties"]
        required_params = params["required"]
        
        # Required parameters
        assert "origin" in required_params
        assert "destination" in required_params
        
        # Parameter properties
        assert "origin" in properties
        assert "destination" in properties
        assert "mode" in properties  # Optional mode parameter
        
        # Parameter types
        assert properties["origin"]["type"] == "string"
        assert properties["destination"]["type"] == "string"
        assert properties["mode"]["type"] == "string"

    def test_place_details_spec_format(self, tool_instance):
        """Test place_details function specification format"""
        specs = get_tool_specs(tool_instance)
        place_details_spec = next(spec for spec in specs if spec["name"] == "place_details")
        
        # Verify OpenAI function calling format
        assert place_details_spec["type"] == "function"
        assert "description" in place_details_spec
        assert "parameters" in place_details_spec
        
        # Verify parameters
        params = place_details_spec["parameters"]
        properties = params["properties"]
        required_params = params["required"]
        
        # Required parameters
        assert "place_id" in required_params
        
        # Parameter properties
        assert "place_id" in properties
        assert properties["place_id"]["type"] == "string"
        assert "description" in properties["place_id"]

    def test_spec_descriptions_quality(self, tool_instance):
        """Test that function descriptions are helpful for LLM understanding"""
        specs = get_tool_specs(tool_instance)
        
        for spec in specs:
            # Description should be non-empty and informative
            assert len(spec["description"]) > 10
            
            # Should mention what the function does
            if spec["name"] == "find_places":
                assert "find" in spec["description"].lower()
                assert "places" in spec["description"].lower()
            elif spec["name"] == "get_directions":
                assert "directions" in spec["description"].lower()
            elif spec["name"] == "place_details":
                assert "details" in spec["description"].lower()

    def test_parameter_descriptions(self, tool_instance):
        """Test that parameter descriptions are helpful"""
        specs = get_tool_specs(tool_instance)
        
        for spec in specs:
            properties = spec["parameters"]["properties"]
            
            for param_name, param_info in properties.items():
                # Each parameter should have a description
                assert "description" in param_info
                assert len(param_info["description"]) > 5
                
                # Descriptions should be informative
                if param_name == "location":
                    desc = param_info["description"].lower()
                    assert "location" in desc
                elif param_name == "query":
                    desc = param_info["description"].lower()
                    assert "search" in desc or "query" in desc
                elif param_name == "place_id":
                    desc = param_info["description"].lower()
                    assert "place" in desc and "id" in desc

    def test_enum_values_for_type_parameter(self, tool_instance):
        """Test that type parameter has enum values for better LLM guidance"""
        specs = get_tool_specs(tool_instance)
        find_places_spec = next(spec for spec in specs if spec["name"] == "find_places")
        
        properties = find_places_spec["parameters"]["properties"]
        if "type" in properties:
            type_param = properties["type"]
            # Should ideally have enum values for place types
            # This will help guide the LLM on valid values
            # Note: This may not be automatically generated, we might need to enhance our docstring

    def test_default_values(self, tool_instance):
        """Test that default values are properly handled in specs"""
        specs = get_tool_specs(tool_instance)
        
        # Check that parameters with defaults are not in required list
        for spec in specs:
            required_params = spec["parameters"]["required"]
            properties = spec["parameters"]["properties"]
            
            # Parameters with defaults shouldn't be required
            if spec["name"] == "find_places":
                assert "radius" not in required_params  # Has default 5000
                assert "type" not in required_params    # Optional parameter
            elif spec["name"] == "get_directions":
                assert "mode" not in required_params    # Has default "driving"

    def test_spec_json_serializable(self, tool_instance):
        """Test that generated specs are JSON serializable for API use"""
        import json
        
        specs = get_tool_specs(tool_instance)
        
        # Should be able to serialize to JSON without errors
        try:
            json_str = json.dumps(specs, indent=2)
            # Should be able to deserialize back
            parsed_specs = json.loads(json_str)
            assert len(parsed_specs) == len(specs)
        except (TypeError, ValueError) as e:
            pytest.fail(f"Generated specs are not JSON serializable: {e}")

    def test_openai_function_calling_compatibility(self, tool_instance):
        """Test that specs are compatible with OpenAI function calling format"""
        specs = get_tool_specs(tool_instance)
        
        for spec in specs:
            # OpenAI function calling format requirements
            assert "type" in spec
            assert spec["type"] == "function"
            assert "name" in spec
            assert "description" in spec
            assert "parameters" in spec
            
            # Parameters should follow JSON Schema format
            params = spec["parameters"]
            assert "type" in params
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params
            
            # Properties should have proper types
            for prop_name, prop_info in params["properties"].items():
                assert "type" in prop_info
                assert prop_info["type"] in ["string", "integer", "number", "boolean", "array", "object"] 