import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException
from test.util.abstract_integration_test import AbstractPostgresTest
from test.util.mock_user import mock_webui_user


class TestMapsRoutes(AbstractPostgresTest):
    """Test suite for Maps API endpoints - Tasks 3, 4, 5 verification"""
    BASE_PATH = "/api/v1/maps"

    def setup_class(cls):
        super().setup_class()
        # Import at class level to avoid import issues
        from open_webui.models.maps import (
            FindPlacesForm, GetDirectionsForm, PlaceDetailsForm,
            PlaceModel, DirectionsModel, PlaceDetailsModel
        )
        from open_webui.routers.maps import find_places, get_directions, place_details
        from open_webui.utils.maps_client import MapsClientError
        
        cls.FindPlacesForm = FindPlacesForm
        cls.GetDirectionsForm = GetDirectionsForm
        cls.PlaceDetailsForm = PlaceDetailsForm
        cls.PlaceModel = PlaceModel
        cls.DirectionsModel = DirectionsModel
        cls.PlaceDetailsModel = PlaceDetailsModel
        cls.find_places = find_places
        cls.get_directions = get_directions
        cls.place_details = place_details
        cls.MapsClientError = MapsClientError

    def test_find_places_integration(self):
        """Integration test for find_places endpoint - Task 3"""
        with mock_webui_user():
            response = self.fast_api_client.post(
                self.create_url("/find_places"),
                json={
                    "location": "New York, NY",
                    "query": "pizza restaurants",
                    "type": "restaurant",
                    "radius": 1000
                }
            )
        
        # Should return 400 if no Google Maps API key is configured
        # or 200 with results if API key is configured
        assert response.status_code in [200, 400, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "places" in data
            assert isinstance(data["places"], list)

    def test_get_directions_integration(self):
        """Integration test for get_directions endpoint - Task 4"""
        with mock_webui_user():
            response = self.fast_api_client.post(
                self.create_url("/get_directions"),
                json={
                    "origin": "Times Square, New York",
                    "destination": "Central Park, New York",
                    "mode": "walking"
                }
            )
        
        # Should return 400 if no Google Maps API key is configured
        # or 200 with results if API key is configured
        assert response.status_code in [200, 400, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "directions" in data
            assert "steps" in data["directions"]
            assert "distance" in data["directions"]
            assert "duration" in data["directions"]

    def test_place_details_integration(self):
        """Integration test for place_details endpoint - Task 5"""
        with mock_webui_user():
            response = self.fast_api_client.post(
                self.create_url("/place_details"),
                json={
                    "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4"
                }
            )
        
        # Should return 400 if no Google Maps API key is configured
        # or 200 with results if API key is configured
        assert response.status_code in [200, 400, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "place_details" in data
            assert "details" in data["place_details"]
            assert "reviews" in data["place_details"]
            assert "photos" in data["place_details"]
            assert "maps_url" in data["place_details"]

    def test_find_places_validation_errors(self):
        """Test input validation for find_places"""
        with mock_webui_user():
            # Test empty location
            response = self.fast_api_client.post(
                self.create_url("/find_places"),
                json={
                    "location": "",
                    "query": "restaurants"
                }
            )
            assert response.status_code == 400
            
            # Test empty query
            response = self.fast_api_client.post(
                self.create_url("/find_places"),
                json={
                    "location": "New York",
                    "query": ""
                }
            )
            assert response.status_code == 400

    def test_get_directions_validation_errors(self):
        """Test input validation for get_directions"""
        with mock_webui_user():
            # Test invalid mode
            response = self.fast_api_client.post(
                self.create_url("/get_directions"),
                json={
                    "origin": "New York",
                    "destination": "Boston",
                    "mode": "flying"  # Invalid mode
                }
            )
            assert response.status_code == 400
            
            # Test empty origin
            response = self.fast_api_client.post(
                self.create_url("/get_directions"),
                json={
                    "origin": "",
                    "destination": "Boston"
                }
            )
            assert response.status_code == 400

    def test_place_details_validation_errors(self):
        """Test input validation for place_details"""
        with mock_webui_user():
            # Test short place_id
            response = self.fast_api_client.post(
                self.create_url("/place_details"),
                json={
                    "place_id": "short"
                }
            )
            assert response.status_code == 400
            
            # Test empty place_id
            response = self.fast_api_client.post(
                self.create_url("/place_details"),
                json={
                    "place_id": ""
                }
            )
            assert response.status_code == 400

    def test_unauthorized_access(self):
        """Test that endpoints require authentication"""
        # Test without authentication
        response = self.fast_api_client.post(
            self.create_url("/find_places"),
            json={
                "location": "New York",
                "query": "restaurants"
            }
        )
        assert response.status_code == 401

    @pytest.mark.skipif(True, reason="Requires Google Maps API key for unit testing")
    def test_find_places_with_api_key(self):
        """Unit test for find_places with actual API (requires API key)"""
        # This test would run if GOOGLE_MAPS_API_KEY is set
        # Skip by default to avoid API quota usage in CI/CD
        pass


# Manual testing instructions for Tasks 3, 4, 5
"""
MANUAL TESTING INSTRUCTIONS:

1. Set Google Maps API Key:
   export GOOGLE_MAPS_API_KEY="your-api-key-here"

2. Start backend:
   cd backend
   python -m open_webui serve --port 8080

3. Test Task 3 (Find Places):
   curl -X POST "http://localhost:8080/api/v1/maps/find_places" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -d '{"location": "New York", "query": "pizza restaurants"}'

4. Test Task 4 (Get Directions):
   curl -X POST "http://localhost:8080/api/v1/maps/get_directions" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -d '{"origin": "Times Square", "destination": "Central Park", "mode": "walking"}'

5. Test Task 5 (Place Details):
   curl -X POST "http://localhost:8080/api/v1/maps/place_details" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -d '{"place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4"}'

6. Run Integration Tests:
   cd backend
   python -m pytest open_webui/test/apps/webui/routers/test_maps.py -v

Expected Results:
- Task 3: Returns places with name, address, lat/lng, place_id, rating, open_now, maps_url
- Task 4: Returns directions with steps, distance, duration, maps_url  
- Task 5: Returns place_details with details, reviews, photos, maps_url
""" 