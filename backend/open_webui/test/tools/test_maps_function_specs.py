import pytest
import json
import sys
import os

# Add the parent directory to sys.path so we can import from open_webui  
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tools.maps_tool import Tools, PlaceType, TravelMode
from utils.tools import get_tool_specs


class TestMapsToolFunctionSpecs:
    """Test OpenAI function specification generation for maps tool"""
    
    @pytest.fixture
    def tools_instance(self):
        """Create a Tools instance for testing"""
        return Tools()
    
    def test_enum_models_exist(self):
        """Test that Pydantic enum models are properly defined"""
        # Test PlaceType enum
        assert hasattr(PlaceType, 'restaurant')
        assert hasattr(PlaceType, 'gas_station')
        assert hasattr(PlaceType, 'hospital')
        assert hasattr(PlaceType, 'school')
        
        # Test enum values
        assert PlaceType.restaurant.value == "restaurant"
        assert PlaceType.gas_station.value == "gas_station"
        
        # Test TravelMode enum
        assert hasattr(TravelMode, 'driving')
        assert hasattr(TravelMode, 'walking')
        assert hasattr(TravelMode, 'transit')
        assert hasattr(TravelMode, 'bicycling')
        
        # Test enum values
        assert TravelMode.driving.value == "driving"
        assert TravelMode.walking.value == "walking"
    
    def test_tool_specs_generation(self, tools_instance):
        """Test that tool specifications can be generated"""
        specs = get_tool_specs(tools_instance)
        
        # Should have exactly 3 function specs
        assert len(specs) == 3
        
        # Extract function names
        function_names = [spec['name'] for spec in specs]
        assert 'find_places' in function_names
        assert 'get_directions' in function_names
        assert 'place_details' in function_names
    
    def test_find_places_spec(self, tools_instance):
        """Test find_places function specification"""
        specs = get_tool_specs(tools_instance)
        find_places_spec = next(spec for spec in specs if spec['name'] == 'find_places')
        
        # Check basic structure
        assert 'name' in find_places_spec
        assert 'description' in find_places_spec
        assert 'parameters' in find_places_spec
        
        # Check parameters structure
        params = find_places_spec['parameters']
        assert params['type'] == 'object'
        assert 'properties' in params
        assert 'required' in params
        
        # Check required parameters
        required = params['required']
        assert 'location' in required
        assert 'query' in required
        
        # Check parameter properties
        properties = params['properties']
        assert 'location' in properties
        assert 'query' in properties
        assert 'type' in properties
        assert 'radius' in properties
        
        # Check location parameter
        location_param = properties['location']
        assert location_param['type'] == 'string'
        assert 'description' in location_param
        
        # Check query parameter
        query_param = properties['query']
        assert query_param['type'] == 'string'
        assert 'description' in query_param
        
        # Check type parameter (should have enum values)
        type_param = properties['type']
        if 'enum' in type_param:
            # Verify PlaceType enum values are included
            enum_values = type_param['enum']
            assert 'restaurant' in enum_values
            assert 'gas_station' in enum_values
            assert 'hospital' in enum_values
        
        # Check radius parameter
        radius_param = properties['radius']
        assert radius_param['type'] == 'integer'
        assert 'description' in radius_param
    
    def test_get_directions_spec(self, tools_instance):
        """Test get_directions function specification"""
        specs = get_tool_specs(tools_instance)
        get_directions_spec = next(spec for spec in specs if spec['name'] == 'get_directions')
        
        # Check basic structure
        assert 'name' in get_directions_spec
        assert 'description' in get_directions_spec
        assert 'parameters' in get_directions_spec
        
        # Check parameters
        params = get_directions_spec['parameters']
        properties = params['properties']
        required = params['required']
        
        # Check required parameters
        assert 'origin' in required
        assert 'destination' in required
        
        # Check parameter properties
        assert 'origin' in properties
        assert 'destination' in properties
        assert 'mode' in properties
        
        # Check mode parameter (should have enum values for TravelMode)
        mode_param = properties['mode']
        if 'enum' in mode_param:
            enum_values = mode_param['enum']
            assert 'driving' in enum_values
            assert 'walking' in enum_values
            assert 'transit' in enum_values
            assert 'bicycling' in enum_values
    
    def test_place_details_spec(self, tools_instance):
        """Test place_details function specification"""
        specs = get_tool_specs(tools_instance)
        place_details_spec = next(spec for spec in specs if spec['name'] == 'place_details')
        
        # Check basic structure
        assert 'name' in place_details_spec
        assert 'description' in place_details_spec
        assert 'parameters' in place_details_spec
        
        # Check parameters
        params = place_details_spec['parameters']
        properties = params['properties']
        required = params['required']
        
        # Check required parameters
        assert 'place_id' in required
        
        # Check place_id parameter
        assert 'place_id' in properties
        place_id_param = properties['place_id']
        assert place_id_param['type'] == 'string'
        assert 'description' in place_id_param
    
    def test_function_descriptions_quality(self, tools_instance):
        """Test that function descriptions provide good guidance for LLM"""
        specs = get_tool_specs(tools_instance)
        
        for spec in specs:
            description = spec['description']
            
            # Description should be substantial (not just a single line)
            assert len(description) > 50, f"Description for {spec['name']} is too short"
            
            # Should contain examples or use cases
            assert any(word in description.lower() for word in ['example', 'like', 'such as', 'perfect for']), \
                f"Description for {spec['name']} lacks examples"
    
    def test_parameter_descriptions_quality(self, tools_instance):
        """Test that parameter descriptions provide clear guidance"""
        specs = get_tool_specs(tools_instance)
        
        for spec in specs:
            properties = spec['parameters']['properties']
            
            for param_name, param_info in properties.items():
                if param_name not in ['__user__', '__id__']:  # Skip internal params
                    assert 'description' in param_info, f"Parameter {param_name} in {spec['name']} lacks description"
                    description = param_info['description']
                    assert len(description) > 20, f"Description for {param_name} in {spec['name']} is too short"
    
    def test_enum_integration(self):
        """Test that enum values work correctly in function calls"""
        # Test PlaceType enum usage
        place_type = PlaceType.restaurant
        assert place_type.value == "restaurant"
        assert str(place_type) == "restaurant"
        
        # Test TravelMode enum usage
        travel_mode = TravelMode.driving
        assert travel_mode.value == "driving"
        assert str(travel_mode) == "driving"
    
    def test_json_serialization_compatibility(self, tools_instance):
        """Test that function specs can be JSON serialized (required for API usage)"""
        specs = get_tool_specs(tools_instance)
        
        try:
            # Should be able to serialize to JSON without errors
            json_str = json.dumps(specs, indent=2)
            assert len(json_str) > 0
            
            # Should be able to deserialize back
            deserialized = json.loads(json_str)
            assert len(deserialized) == len(specs)
            
        except (TypeError, ValueError) as e:
            pytest.fail(f"Function specs are not JSON serializable: {e}")
    
    def test_openai_function_calling_format(self, tools_instance):
        """Test that specs follow OpenAI function calling format"""
        specs = get_tool_specs(tools_instance)
        
        for spec in specs:
            # Must have required top-level fields
            assert 'name' in spec
            assert 'description' in spec
            assert 'parameters' in spec
            
            # Name should be valid function name
            name = spec['name']
            assert name.isidentifier(), f"Function name '{name}' is not a valid identifier"
            
            # Parameters should follow JSON Schema format
            parameters = spec['parameters']
            assert parameters['type'] == 'object'
            assert 'properties' in parameters
            
            # Properties should be well-formed
            properties = parameters['properties']
            for prop_name, prop_info in properties.items():
                assert 'type' in prop_info, f"Property {prop_name} missing type"
                assert prop_info['type'] in ['string', 'integer', 'number', 'boolean', 'array', 'object'], \
                    f"Invalid type for property {prop_name}: {prop_info['type']}"


class TestParameterValidation:
    """Test parameter validation with Pydantic models"""
    
    def test_place_type_validation(self):
        """Test PlaceType enum validation"""
        # Valid values should work
        valid_types = ['restaurant', 'gas_station', 'hospital', 'school']
        for valid_type in valid_types:
            place_type = PlaceType(valid_type)
            assert place_type.value == valid_type
        
        # Invalid values should raise error
        with pytest.raises(ValueError):
            PlaceType('invalid_type')
    
    def test_travel_mode_validation(self):
        """Test TravelMode enum validation"""
        # Valid values should work
        valid_modes = ['driving', 'walking', 'transit', 'bicycling']
        for valid_mode in valid_modes:
            travel_mode = TravelMode(valid_mode)
            assert travel_mode.value == valid_mode
        
        # Invalid values should raise error
        with pytest.raises(ValueError):
            TravelMode('invalid_mode')
    
    def test_enum_in_function_signatures(self):
        """Test that enums are properly used in function signatures"""
        tools = Tools()
        
        # Check function signatures contain enum types
        import inspect
        
        # find_places should use PlaceType
        sig = inspect.signature(tools.find_places)
        type_param = sig.parameters.get('type')
        if type_param and hasattr(type_param.annotation, '__origin__'):
            # Handle Optional[PlaceType] case
            args = getattr(type_param.annotation, '__args__', ())
            assert any(arg == PlaceType for arg in args if arg != type(None))
        
        # get_directions should use TravelMode
        sig = inspect.signature(tools.get_directions)
        mode_param = sig.parameters.get('mode')
        assert mode_param.annotation == TravelMode or \
               (hasattr(mode_param.annotation, '__args__') and TravelMode in mode_param.annotation.__args__) 