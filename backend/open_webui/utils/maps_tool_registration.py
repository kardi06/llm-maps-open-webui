#!/usr/bin/env python3
"""
Maps Tool Registration Utility

This module handles registration of the Google Maps tool with OpenWebUI's tool system.
It stores the tool content in the database and makes it available through the admin interface.
"""

import logging
import os
import sys
from typing import Optional, Dict, Any

# Add the backend directory to the Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from open_webui.models.tools import Tools, ToolForm, ToolMeta
from open_webui.utils.plugin import load_tool_module_by_id
from open_webui.utils.tools import get_tool_specs

log = logging.getLogger(__name__)


class MapsToolRegistration:
    """Handles registration and management of the Google Maps tool"""
    
    TOOL_ID = "google_maps_tool"
    TOOL_NAME = "Google Maps Integration"
    
    @classmethod
    def get_tool_content(cls) -> str:
        """Load the maps tool content from file"""
        tool_file_path = os.path.join(
            os.path.dirname(__file__), '..', 'tools', 'maps_tool.py'
        )
        
        if not os.path.exists(tool_file_path):
            raise FileNotFoundError(f"Maps tool file not found at: {tool_file_path}")
        
        with open(tool_file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @classmethod
    def register_tool(cls, user_id: str, access_control: Optional[Dict] = None) -> bool:
        """
        Register the maps tool with OpenWebUI tool system
        
        Args:
            user_id: ID of the user registering the tool (usually admin)
            access_control: Optional access control settings
            
        Returns:
            bool: True if registration successful, False otherwise
        """
        try:
            # Load tool content
            tool_content = cls.get_tool_content()
            
            # Load tool module to extract frontmatter and validate
            tool_instance, frontmatter = load_tool_module_by_id(cls.TOOL_ID, tool_content)
            
            # Generate tool specifications
            specs = get_tool_specs(tool_instance)
            
            log.info(f"Generated {len(specs)} function specifications for maps tool")
            
            # Create tool metadata
            tool_meta = ToolMeta(
                description=frontmatter.get('description', 'Google Maps integration for finding places, directions, and place details'),
                manifest={
                    'title': frontmatter.get('title', cls.TOOL_NAME),
                    'author': frontmatter.get('author', 'open-webui'),
                    'author_url': frontmatter.get('author_url', 'https://github.com/open-webui/open-webui'),
                    'version': frontmatter.get('version', '1.0.0'),
                    'license': frontmatter.get('license', 'MIT'),
                    'requirements': frontmatter.get('requirements', 'aiohttp, pydantic'),
                    'funding_url': frontmatter.get('funding_url', ''),
                    'functions': [spec['name'] for spec in specs]
                }
            )
            
            # Create tool form data
            tool_form = ToolForm(
                id=cls.TOOL_ID,
                name=cls.TOOL_NAME,
                content=tool_content,
                meta=tool_meta,
                access_control=access_control or {}  # Public access by default
            )
            
            # Check if tool already exists
            existing_tool = Tools.get_tool_by_id(cls.TOOL_ID)
            if existing_tool:
                log.warning(f"Tool {cls.TOOL_ID} already exists. Updating...")
                # Update existing tool
                updated_tool = Tools.update_tool_by_id(
                    cls.TOOL_ID,
                    {
                        'name': tool_form.name,
                        'content': tool_form.content,
                        'meta': tool_form.meta.model_dump(),
                        'specs': specs,
                        'access_control': tool_form.access_control
                    }
                )
                success = updated_tool is not None
            else:
                # Insert new tool
                new_tool = Tools.insert_new_tool(user_id, tool_form, specs)
                success = new_tool is not None
            
            if success:
                log.info(f"Successfully registered/updated maps tool with ID: {cls.TOOL_ID}")
                log.info(f"Tool functions: {[spec['name'] for spec in specs]}")
                return True
            else:
                log.error("Failed to register/update maps tool")
                return False
                
        except Exception as e:
            log.exception(f"Error registering maps tool: {e}")
            return False
    
    @classmethod
    def unregister_tool(cls) -> bool:
        """
        Unregister the maps tool from OpenWebUI tool system
        
        Returns:
            bool: True if unregistration successful, False otherwise
        """
        try:
            success = Tools.delete_tool_by_id(cls.TOOL_ID)
            if success:
                log.info(f"Successfully unregistered maps tool with ID: {cls.TOOL_ID}")
            else:
                log.warning(f"Failed to unregister maps tool or tool not found: {cls.TOOL_ID}")
            return success
        except Exception as e:
            log.exception(f"Error unregistering maps tool: {e}")
            return False
    
    @classmethod
    def is_registered(cls) -> bool:
        """
        Check if the maps tool is currently registered
        
        Returns:
            bool: True if tool is registered, False otherwise
        """
        try:
            tool = Tools.get_tool_by_id(cls.TOOL_ID)
            return tool is not None
        except Exception as e:
            log.exception(f"Error checking maps tool registration: {e}")
            return False
    
    @classmethod
    def get_tool_info(cls) -> Optional[Dict[str, Any]]:
        """
        Get information about the registered maps tool
        
        Returns:
            Dict with tool information or None if not registered
        """
        try:
            tool = Tools.get_tool_by_id(cls.TOOL_ID)
            if tool:
                return {
                    'id': tool.id,
                    'name': tool.name,
                    'user_id': tool.user_id,
                    'specs': tool.specs,
                    'meta': tool.meta,
                    'access_control': tool.access_control,
                    'created_at': tool.created_at,
                    'updated_at': tool.updated_at,
                    'functions': [spec['name'] for spec in tool.specs] if tool.specs else []
                }
            return None
        except Exception as e:
            log.exception(f"Error getting maps tool info: {e}")
            return None


def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Register Google Maps tool with OpenWebUI")
    parser.add_argument('--user-id', required=True, help='User ID to register the tool under (usually admin)')
    parser.add_argument('--action', choices=['register', 'unregister', 'status'], default='register', help='Action to perform')
    parser.add_argument('--public', action='store_true', help='Make tool publicly accessible')
    parser.add_argument('--private', action='store_true', help='Make tool private to user only')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    if args.action == 'status':
        if MapsToolRegistration.is_registered():
            print("✅ Maps tool is registered")
            tool_info = MapsToolRegistration.get_tool_info()
            if tool_info:
                print(f"   ID: {tool_info['id']}")
                print(f"   Name: {tool_info['name']}")
                print(f"   Functions: {', '.join(tool_info['functions'])}")
                print(f"   Created: {tool_info['created_at']}")
        else:
            print("❌ Maps tool is not registered")
    
    elif args.action == 'unregister':
        if MapsToolRegistration.unregister_tool():
            print("✅ Maps tool unregistered successfully")
        else:
            print("❌ Failed to unregister maps tool")
    
    elif args.action == 'register':
        # Set access control based on flags
        access_control = None
        if args.private:
            access_control = {}  # Private to user only
        elif args.public:
            access_control = None  # Public access
        
        if MapsToolRegistration.register_tool(args.user_id, access_control):
            print("✅ Maps tool registered successfully")
            tool_info = MapsToolRegistration.get_tool_info()
            if tool_info:
                print(f"   Tool ID: {tool_info['id']}")
                print(f"   Functions: {', '.join(tool_info['functions'])}")
        else:
            print("❌ Failed to register maps tool")


if __name__ == '__main__':
    main() 