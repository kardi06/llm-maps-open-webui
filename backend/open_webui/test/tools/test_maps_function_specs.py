import pytest
import json
import sys
import os
from typing import Dict, Any

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from open_webui.utils.plugin import load_tool_module_by_id
from open_webui.utils.tools import get_tool_specs


class TestMapsToolFunctionSpecs:
    """Test suite for Task 2: Maps Function Specifications"""

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
        """Load tool instance"""
        tool_instance, _ = load_tool_module_by_id("test_maps_tool", maps_tool_content)
        return tool_instance

    @pytest.fixture
    def function_specs(self, tool_instance):
        """Generate function specifications"""
        return get_tool_specs(tool_instance)

    def test_all_functions_have_specs(self, function_specs):
        """Test that all three functions have specifications generated"""
        function_names = [spec["name"] for spec in function_specs]
        
        assert "find_places" in function_names
        assert "get_directions" in function_names
        assert "place_details" in function_names
        assert len(function_specs) == 3

    def test_openai_function_calling_format(self, function_specs):
        """Test that all specs follow OpenAI function calling format"""
        for spec in function_specs:
            # Required top-level fields
            assert spec["type"] == "function"
            assert "name" in spec
            assert "description" in spec
            assert "parameters" in spec
            
            # Parameters must follow JSON Schema format
            params = spec["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params
            
            # Properties must have proper types
            for prop_name, prop_info in params["properties"].items():
                assert "type" in prop_info
                assert prop_info["type"] in ["string", "integer", "number", "boolean", "array", "object"]
                assert "description" in prop_info

    def test_find_places_spec_details(self, function_specs):
        """Test find_places function specification details"""
        spec = next(s for s in function_specs if s["name"] == "find_places")
        
        # Check description quality
        description = spec["description"]
        assert len(description) > 50  # Should be detailed
        assert "find places" in description.lower()
        assert "natural language" in description.lower()
        
        # Check parameters
        params = spec["parameters"]
        properties = params["properties"]
        required = params["required"]
        
        # Required parameters
        assert "location" in required
        assert "query" in required
        
        # Optional parameters (should not be in required)
        assert "type" not in required
        assert "radius" not in required
        
        # Parameter details
        assert properties["location"]["type"] == "string"
        assert properties["query"]["type"] == "string"
        assert properties["radius"]["type"] == "integer"
        
        # Check for enum values in type parameter
        if "type" in properties:
            type_param = properties["type"]
            # Should have enum values for place types
            if "enum" in type_param:
                enum_values = type_param["enum"]
                assert "restaurant" in enum_values
                assert "hospital" in enum_values
                assert "gas_station" in enum_values

    def test_get_directions_spec_details(self, function_specs):
        """Test get_directions function specification details"""
        spec = next(s for s in function_specs if s["name"] == "get_directions")
        
        # Check description
        description = spec["description"]
        assert "directions" in description.lower()
        assert "step-by-step" in description.lower()
        
        # Check parameters
        params = spec["parameters"]
        properties = params["properties"]
        required = params["required"]
        
        # Required parameters
        assert "origin" in required
        assert "destination" in required
        
        # Optional parameter
        assert "mode" not in required  # Has default value
        
        # Check for enum values in mode parameter
        if "mode" in properties:
            mode_param = properties["mode"]
            # Should have enum values for travel modes
            if "enum" in mode_param:
                enum_values = mode_param["enum"]
                assert "driving" in enum_values
                assert "walking" in enum_values
                assert "transit" in enum_values
                assert "bicycling" in enum_values

    def test_place_details_spec_details(self, function_specs):
        """Test place_details function specification details"""
        spec = next(s for s in function_specs if s["name"] == "place_details")
        
        # Check description
        description = spec["description"]
        assert "detailed information" in description.lower()
        assert "place" in description.lower()
        
        # Check parameters
        params = spec["parameters"]
        properties = params["properties"]
        required = params["required"]
        
        # Required parameter
        assert "place_id" in required
        assert len(required) == 1  # Only place_id is required
        
        # Parameter details
        assert properties["place_id"]["type"] == "string"
        place_id_desc = properties["place_id"]["description"].lower()
        assert "place id" in place_id_desc or "place_id" in place_id_desc

    def test_parameter_descriptions_quality(self, function_specs):
        """Test that parameter descriptions are helpful for LLM understanding"""
        for spec in function_specs:
            properties = spec["parameters"]["properties"]
            
            for param_name, param_info in properties.items():
                description = param_info["description"]
                
                # Should be descriptive (more than just the parameter name)
                assert len(description) > len(param_name) + 5
                
                # Should include examples or guidance where appropriate
                if param_name in ["location", "origin", "destination"]:
                    # Should mention examples or formats
                    assert "e.g." in description or "example" in description.lower()
                
                if param_name == "radius":
                    # Should mention units and limits
                    assert "meters" in description.lower()
                    assert "km" in description.lower() or "maximum" in description.lower()

    def test_spec_json_serialization(self, function_specs):
        """Test that specs can be serialized to JSON for API use"""
        try:
            json_str = json.dumps(function_specs, indent=2)
            parsed_specs = json.loads(json_str)
            assert len(parsed_specs) == len(function_specs)
        except (TypeError, ValueError) as e:
            pytest.fail(f"Function specs are not JSON serializable: {e}")

    def test_llm_function_calling_examples(self, function_specs):
        """Test specs against realistic LLM function calling scenarios"""
        
        # Example 1: Find restaurants
        find_places_spec = next(s for s in function_specs if s["name"] == "find_places")
        
        # Simulate LLM function call
        example_call = {
            "name": "find_places",
            "arguments": {
                "location": "Senayan",
                "query": "sushi restaurants",
                "type": "restaurant"
            }
        }
        
        # Validate against spec
        params = find_places_spec["parameters"]
        for arg_name, arg_value in example_call["arguments"].items():
            assert arg_name in params["properties"]
            
        # Example 2: Get directions
        directions_spec = next(s for s in function_specs if s["name"] == "get_directions")
        
        example_call_2 = {
            "name": "get_directions", 
            "arguments": {
                "origin": "Jakarta",
                "destination": "Bandung",
                "mode": "driving"
            }
        }
        
        params_2 = directions_spec["parameters"]
        for arg_name, arg_value in example_call_2["arguments"].items():
            assert arg_name in params_2["properties"]

    def test_enum_parameter_handling(self, tool_instance):
        """Test that enum parameters are properly handled in the tool implementation"""
        # This tests the actual function signatures support enum types
        import inspect
        
        # Check find_places signature
        sig = inspect.signature(tool_instance.find_places)
        type_param = sig.parameters.get('type')
        assert type_param is not None
        
        # Check get_directions signature
        sig_directions = inspect.signature(tool_instance.get_directions)
        mode_param = sig_directions.parameters.get('mode')
        assert mode_param is not None

    def test_comprehensive_spec_validation(self, function_specs):
        """Comprehensive validation of all specifications"""
        validation_results = []
        
        for spec in function_specs:
            func_name = spec["name"]
            issues = []
            
            # Check description length and quality
            if len(spec.get("description", "")) < 30:
                issues.append("Description too short")
            
            # Check parameters structure
            params = spec.get("parameters", {})
            if "properties" not in params:
                issues.append("Missing properties")
            
            if "required" not in params:
                issues.append("Missing required array")
            
            # Check each parameter has description
            properties = params.get("properties", {})
            for param_name, param_info in properties.items():
                if "description" not in param_info:
                    issues.append(f"Parameter {param_name} missing description")
                
                if len(param_info.get("description", "")) < 10:
                    issues.append(f"Parameter {param_name} description too short")
            
            validation_results.append({
                "function": func_name,
                "issues": issues,
                "valid": len(issues) == 0
            })
        
        # Report any issues
        for result in validation_results:
            if not result["valid"]:
                pytest.fail(f"Function {result['function']} has issues: {result['issues']}")
        
        # All functions should be valid
        assert all(result["valid"] for result in validation_results) 