import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
import tempfile

# Add the parent directory to sys.path so we can import from open_webui
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from utils.maps_tool_registration import MapsToolRegistration


class TestMapsToolRegistration:
    """Test maps tool registration functionality"""
    
    @pytest.fixture
    def registration(self):
        """Create a MapsToolRegistration instance for testing"""
        return MapsToolRegistration()
    
    @pytest.fixture
    def mock_tool_content(self):
        """Mock tool content with frontmatter"""
        return '''"""
title: Google Maps Tool
description: Find places, get directions, and retrieve place details using natural language queries
version: 1.0.0
required_open_webui_version: 0.4.0
license: MIT
requirements: aiohttp
"""

import logging
from typing import Dict, Any, Optional

class Tools:
    async def find_places(self, location: str, query: str, __user__: dict = {}, __id__: str = None) -> Dict[str, Any]:
        return {"places": [], "status": "success"}
    
    async def get_directions(self, origin: str, destination: str, __user__: dict = {}, __id__: str = None) -> Dict[str, Any]:
        return {"route": {}, "status": "success"}
        
    async def place_details(self, place_id: str, __user__: dict = {}, __id__: str = None) -> Dict[str, Any]:
        return {"details": {}, "status": "success"}
'''
    
    def test_initialization(self, registration):
        """Test MapsToolRegistration initialization"""
        assert registration.TOOL_ID == "google_maps_tool"
        assert registration.TOOL_NAME == "Google Maps Tool"
        assert hasattr(registration, 'tool_file_path')
    
    def test_load_tool_content_success(self, registration, mock_tool_content):
        """Test successful tool content loading"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(mock_tool_content)
            f.flush()
            
            registration.tool_file_path = f.name
            
            try:
                content = registration.load_tool_content()
                assert content == mock_tool_content
                assert "title: Google Maps Tool" in content
            finally:
                os.unlink(f.name)
    
    def test_load_tool_content_file_not_found(self, registration):
        """Test tool content loading when file doesn't exist"""
        registration.tool_file_path = "/nonexistent/path/maps_tool.py"
        
        with pytest.raises(FileNotFoundError):
            registration.load_tool_content()
    
    def test_extract_tool_metadata(self, registration, mock_tool_content):
        """Test metadata extraction from tool frontmatter"""
        metadata = registration.extract_tool_metadata(mock_tool_content)
        
        assert "description" in metadata
        assert "manifest" in metadata
        
        manifest = metadata["manifest"]
        assert manifest["title"] == "Google Maps Tool"
        assert manifest["version"] == "1.0.0"
        assert manifest["license"] == "MIT"
        assert manifest["requirements"] == "aiohttp"
    
    def test_extract_tool_metadata_missing_frontmatter(self, registration):
        """Test metadata extraction with missing frontmatter"""
        content_without_frontmatter = "import logging\nclass Tools:\n    pass"
        metadata = registration.extract_tool_metadata(content_without_frontmatter)
        
        # Should use defaults when frontmatter is missing
        assert metadata["description"] == "Google Maps integration tool"
        assert metadata["manifest"]["title"] == "Google Maps Tool"
        assert metadata["manifest"]["version"] == "1.0.0"
    
    @patch('open_webui.utils.maps_tool_registration.load_tool_module_by_id')
    @patch('open_webui.utils.maps_tool_registration.get_tool_specs')
    def test_generate_tool_specs_success(self, mock_get_tool_specs, mock_load_tool_module, registration):
        """Test successful tool specification generation"""
        # Mock the tool module and specs
        mock_tool_module = Mock()
        mock_load_tool_module.return_value = mock_tool_module
        
        mock_specs = [
            {"name": "find_places", "description": "Find places", "parameters": {}},
            {"name": "get_directions", "description": "Get directions", "parameters": {}}
        ]
        mock_get_tool_specs.return_value = mock_specs
        
        specs = registration.generate_tool_specs("mock_content")
        
        assert len(specs) == 2
        assert specs[0]["name"] == "find_places"
        assert specs[1]["name"] == "get_directions"
        
        mock_load_tool_module.assert_called_once_with(registration.TOOL_ID, content="mock_content")
        mock_get_tool_specs.assert_called_once_with(mock_tool_module)
    
    @patch('open_webui.utils.maps_tool_registration.load_tool_module_by_id')
    def test_generate_tool_specs_error(self, mock_load_tool_module, registration):
        """Test tool specification generation with error"""
        mock_load_tool_module.side_effect = Exception("Module loading failed")
        
        specs = registration.generate_tool_specs("mock_content")
        
        # Should return empty list on error
        assert specs == []
    
    def test_configure_access_control_public(self, registration):
        """Test public access control configuration"""
        config = registration.configure_access_control("public")
        assert config is None  # None means public access
    
    def test_configure_access_control_private(self, registration):
        """Test private access control configuration"""
        config = registration.configure_access_control("private")
        assert config == {}  # Empty dict means private access
    
    def test_configure_access_control_custom(self, registration):
        """Test custom access control configuration"""
        group_ids = ["group1", "group2"]
        user_ids = ["user1", "user2"]
        
        config = registration.configure_access_control(
            "custom", 
            group_ids=group_ids, 
            user_ids=user_ids
        )
        
        assert "read" in config
        assert config["read"]["group_ids"] == group_ids
        assert config["read"]["user_ids"] == user_ids
    
    def test_configure_access_control_invalid(self, registration):
        """Test invalid access control configuration"""
        with pytest.raises(ValueError, match="Invalid access_type"):
            registration.configure_access_control("invalid_type")


class TestToolRegistrationIntegration:
    """Test integration with OpenWebUI Tools model"""
    
    @pytest.fixture
    def registration(self):
        return MapsToolRegistration()
    
    @patch('open_webui.utils.maps_tool_registration.Tools')
    def test_register_tool_new(self, mock_tools_class, registration):
        """Test registering a new tool"""
        # Mock Tools model methods
        mock_tools_class.get_tool_by_id.return_value = None  # Tool doesn't exist
        mock_tools_class.insert_new_tool.return_value = Mock()  # Successful insertion
        
        # Mock other dependencies
        with patch.object(registration, 'load_tool_content', return_value="mock_content"), \
             patch.object(registration, 'extract_tool_metadata', return_value={"description": "test"}), \
             patch.object(registration, 'generate_tool_specs', return_value=[]):
            
            success = registration.register_tool("test_user_id")
            
            assert success is True
            mock_tools_class.get_tool_by_id.assert_called_once_with(registration.TOOL_ID)
            mock_tools_class.insert_new_tool.assert_called_once()
    
    @patch('open_webui.utils.maps_tool_registration.Tools')
    def test_register_tool_existing_no_overwrite(self, mock_tools_class, registration):
        """Test registering a tool that already exists without overwrite"""
        # Mock existing tool
        mock_existing_tool = Mock()
        mock_tools_class.get_tool_by_id.return_value = mock_existing_tool
        
        success = registration.register_tool("test_user_id", overwrite=False)
        
        assert success is False
        mock_tools_class.get_tool_by_id.assert_called_once_with(registration.TOOL_ID)
        mock_tools_class.insert_new_tool.assert_not_called()
    
    @patch('open_webui.utils.maps_tool_registration.Tools')
    def test_register_tool_existing_with_overwrite(self, mock_tools_class, registration):
        """Test registering a tool that already exists with overwrite"""
        # Mock existing tool
        mock_existing_tool = Mock()
        mock_tools_class.get_tool_by_id.return_value = mock_existing_tool
        mock_tools_class.update_tool_by_id.return_value = Mock()  # Successful update
        
        # Mock other dependencies
        with patch.object(registration, 'load_tool_content', return_value="mock_content"), \
             patch.object(registration, 'extract_tool_metadata', return_value={"description": "test"}), \
             patch.object(registration, 'generate_tool_specs', return_value=[]):
            
            success = registration.register_tool("test_user_id", overwrite=True)
            
            assert success is True
            mock_tools_class.update_tool_by_id.assert_called_once()
            mock_tools_class.insert_new_tool.assert_not_called()
    
    @patch('open_webui.utils.maps_tool_registration.Tools')
    def test_unregister_tool_success(self, mock_tools_class, registration):
        """Test successful tool unregistration"""
        mock_existing_tool = Mock()
        mock_tools_class.get_tool_by_id.return_value = mock_existing_tool
        mock_tools_class.delete_tool_by_id.return_value = True
        
        success = registration.unregister_tool()
        
        assert success is True
        mock_tools_class.delete_tool_by_id.assert_called_once_with(registration.TOOL_ID)
    
    @patch('open_webui.utils.maps_tool_registration.Tools')
    def test_unregister_tool_not_found(self, mock_tools_class, registration):
        """Test unregistering a tool that doesn't exist"""
        mock_tools_class.get_tool_by_id.return_value = None
        
        success = registration.unregister_tool()
        
        assert success is True  # Should succeed if tool doesn't exist
        mock_tools_class.delete_tool_by_id.assert_not_called()
    
    @patch('open_webui.utils.maps_tool_registration.Tools')
    def test_get_tool_status_registered(self, mock_tools_class, registration):
        """Test getting status of a registered tool"""
        mock_tool = Mock()
        mock_tool.name = "Google Maps Tool"
        mock_tool.user_id = "test_user"
        mock_tool.created_at = 1234567890
        mock_tool.updated_at = 1234567891
        mock_tool.access_control = None
        mock_tool.specs = [{"name": "find_places"}, {"name": "get_directions"}]
        
        mock_tools_class.get_tool_by_id.return_value = mock_tool
        
        status = registration.get_tool_status()
        
        assert status["registered"] is True
        assert status["tool_id"] == registration.TOOL_ID
        assert status["name"] == "Google Maps Tool"
        assert status["user_id"] == "test_user"
        assert status["specs_count"] == 2
    
    @patch('open_webui.utils.maps_tool_registration.Tools')
    def test_get_tool_status_not_registered(self, mock_tools_class, registration):
        """Test getting status of an unregistered tool"""
        mock_tools_class.get_tool_by_id.return_value = None
        
        status = registration.get_tool_status()
        
        assert status["registered"] is False
        assert status["tool_id"] == registration.TOOL_ID
        assert "not registered" in status["message"]
    
    @patch('open_webui.utils.maps_tool_registration.Tools')
    def test_registration_error_handling(self, mock_tools_class, registration):
        """Test error handling during tool registration"""
        mock_tools_class.get_tool_by_id.side_effect = Exception("Database error")
        
        success = registration.register_tool("test_user_id")
        
        assert success is False


class TestAccessControlIntegration:
    """Test access control integration with OpenWebUI"""
    
    @pytest.fixture
    def registration(self):
        return MapsToolRegistration()
    
    @patch('open_webui.utils.maps_tool_registration.Tools')
    def test_register_with_public_access(self, mock_tools_class, registration):
        """Test tool registration with public access control"""
        mock_tools_class.get_tool_by_id.return_value = None
        mock_tools_class.insert_new_tool.return_value = Mock()
        
        with patch.object(registration, 'load_tool_content', return_value="mock_content"), \
             patch.object(registration, 'extract_tool_metadata', return_value={"description": "test"}), \
             patch.object(registration, 'generate_tool_specs', return_value=[]):
            
            access_control = registration.configure_access_control("public")
            success = registration.register_tool("test_user_id", access_control=access_control)
            
            assert success is True
            
            # Verify the tool was registered with None access_control (public)
            call_args = mock_tools_class.insert_new_tool.call_args[1]
            assert call_args["form_data"].access_control is None
    
    @patch('open_webui.utils.maps_tool_registration.Tools')
    def test_register_with_private_access(self, mock_tools_class, registration):
        """Test tool registration with private access control"""
        mock_tools_class.get_tool_by_id.return_value = None
        mock_tools_class.insert_new_tool.return_value = Mock()
        
        with patch.object(registration, 'load_tool_content', return_value="mock_content"), \
             patch.object(registration, 'extract_tool_metadata', return_value={"description": "test"}), \
             patch.object(registration, 'generate_tool_specs', return_value=[]):
            
            access_control = registration.configure_access_control("private")
            success = registration.register_tool("test_user_id", access_control=access_control)
            
            assert success is True
            
            # Verify the tool was registered with {} access_control (private)
            call_args = mock_tools_class.insert_new_tool.call_args[1]
            assert call_args["form_data"].access_control == {}
    
    @patch('open_webui.utils.maps_tool_registration.Tools')
    def test_register_with_custom_access(self, mock_tools_class, registration):
        """Test tool registration with custom access control"""
        mock_tools_class.get_tool_by_id.return_value = None
        mock_tools_class.insert_new_tool.return_value = Mock()
        
        with patch.object(registration, 'load_tool_content', return_value="mock_content"), \
             patch.object(registration, 'extract_tool_metadata', return_value={"description": "test"}), \
             patch.object(registration, 'generate_tool_specs', return_value=[]):
            
            access_control = registration.configure_access_control(
                "custom", 
                group_ids=["group1"], 
                user_ids=["user1"]
            )
            success = registration.register_tool("test_user_id", access_control=access_control)
            
            assert success is True
            
            # Verify the tool was registered with custom access_control
            call_args = mock_tools_class.insert_new_tool.call_args[1]
            tool_access = call_args["form_data"].access_control
            assert "read" in tool_access
            assert tool_access["read"]["group_ids"] == ["group1"]
            assert tool_access["read"]["user_ids"] == ["user1"] 