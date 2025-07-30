import pytest
import asyncio
import time
import json
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os
from datetime import datetime, timedelta

# Add the parent directory to sys.path so we can import from open_webui
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from utils.maps_client import MapsClient, MapsClientError
from utils.maps_circuit_breaker import CircuitBreaker, CircuitState
from utils.maps_performance import PerformanceMonitor
from utils.maps_health import MapsHealthMonitor, GracefulDegradation
from utils.maps_security import MapsRequestLogger

class TestMapsPerformance:
    """Test performance requirements for maps functionality"""
    
    @pytest.fixture
    async def maps_client(self):
        """Create a maps client for testing"""
        with patch('utils.maps_client.GOOGLE_MAPS_API_KEY', 'test_key'):
            client = MapsClient()
            yield client
            await client.connection_pool.close()
    
    @pytest.mark.asyncio
    async def test_find_places_performance(self, maps_client):
        """Test that find_places responds within 5 seconds"""
        mock_response = [
            {
                'name': 'Test Restaurant',
                'geometry': {'location': {'lat': -6.2088, 'lng': 106.8456}},
                'formatted_address': 'Test Address',
                'place_id': 'ChIJ123',
                'rating': 4.5
            }
        ]
        
        with patch.object(maps_client.client, 'places', return_value={'results': mock_response}):
            start_time = time.time()
            
            result = await maps_client.find_places(
                location="Jakarta",
                query="restaurant"
            )
            
            duration = time.time() - start_time
            
            # Verify performance requirement
            assert duration < 5.0, f"find_places took {duration:.2f}s, should be under 5s"
            assert len(result) > 0
            assert result[0]['name'] == 'Test Restaurant'
    
    @pytest.mark.asyncio
    async def test_get_directions_performance(self, maps_client):
        """Test that get_directions responds within 5 seconds"""
        mock_response = [{
            'legs': [{
                'distance': {'text': '10 km'},
                'duration': {'text': '15 mins'},
                'start_address': 'Origin',
                'end_address': 'Destination',
                'steps': []
            }]
        }]
        
        with patch.object(maps_client.client, 'directions', return_value=mock_response):
            start_time = time.time()
            
            result = await maps_client.get_directions(
                origin="Jakarta",
                destination="Bandung"
            )
            
            duration = time.time() - start_time
            
            # Verify performance requirement
            assert duration < 5.0, f"get_directions took {duration:.2f}s, should be under 5s"
            assert result['distance'] == '10 km'
            assert result['duration'] == '15 mins'
    
    @pytest.mark.asyncio
    async def test_place_details_performance(self, maps_client):
        """Test that place_details responds within 5 seconds"""
        mock_response = {
            'result': {
                'name': 'Test Place',
                'formatted_address': 'Test Address',
                'rating': 4.5,
                'reviews': [],
                'photos': []
            }
        }
        
        with patch.object(maps_client.client, 'place', return_value=mock_response):
            start_time = time.time()
            
            result = await maps_client.get_place_details("ChIJ123")
            
            duration = time.time() - start_time
            
            # Verify performance requirement
            assert duration < 5.0, f"place_details took {duration:.2f}s, should be under 5s"
            assert result['details']['name'] == 'Test Place'
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, maps_client):
        """Test that requests timeout appropriately and return graceful responses"""
        async def slow_function(*args, **kwargs):
            await asyncio.sleep(6)  # Longer than timeout
            return {'results': []}
        
        with patch.object(maps_client.client, 'places', side_effect=slow_function):
            start_time = time.time()
            
            result = await maps_client.find_places(
                location="Jakarta",
                query="restaurant"
            )
            
            duration = time.time() - start_time
            
            # Should timeout and return fallback response quickly
            assert duration < 6.0, "Should have timed out before 6 seconds"
            assert isinstance(result, list), "Should return graceful fallback"

class TestPerformanceMonitoring:
    """Test the performance monitoring system"""
    
    def test_performance_monitor_basic_functionality(self):
        """Test basic performance monitoring functionality"""
        monitor = PerformanceMonitor()
        
        # Start a request
        request_id = monitor.start_request("test_operation")
        assert request_id in monitor.active_requests
        
        # End the request
        time.sleep(0.1)  # Simulate some work
        monitor.end_request(request_id, success=True)
        
        assert request_id not in monitor.active_requests
        assert len(monitor.metrics_history) == 1
        
        # Check metrics
        stats = monitor.get_performance_stats()
        assert stats['total_requests'] == 1
        assert stats['successful_requests'] == 1
        assert stats['success_rate'] == 100.0
        assert stats['avg_duration_ms'] > 0
    
    def test_performance_monitor_failure_tracking(self):
        """Test that performance monitor tracks failures correctly"""
        monitor = PerformanceMonitor()
        
        # Record a failure
        request_id = monitor.start_request("test_operation")
        time.sleep(0.05)
        monitor.end_request(request_id, success=False, error_type="timeout")
        
        stats = monitor.get_performance_stats()
        assert stats['total_requests'] == 1
        assert stats['failed_requests'] == 1
        assert stats['success_rate'] == 0.0

class TestCircuitBreaker:
    """Test the circuit breaker implementation"""
    
    def test_circuit_breaker_normal_operation(self):
        """Test circuit breaker in normal operation"""
        circuit = CircuitBreaker()
        
        # Should allow execution in CLOSED state
        assert circuit.can_execute() == True
        assert circuit.state == CircuitState.CLOSED
        
        # Record some successes
        circuit.record_success()
        assert circuit.failure_count == 0
        assert circuit.state == CircuitState.CLOSED
    
    def test_circuit_breaker_failure_threshold(self):
        """Test circuit breaker opens after failure threshold"""
        circuit = CircuitBreaker()
        
        # Record failures up to threshold
        for i in range(5):  # Default threshold is 5
            circuit.record_failure()
        
        # Circuit should now be OPEN
        assert circuit.state == CircuitState.OPEN
        assert circuit.can_execute() == False
    
    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery mechanism"""
        circuit = CircuitBreaker()
        circuit.config.recovery_timeout = 1  # 1 second for testing
        
        # Open the circuit
        for i in range(5):
            circuit.record_failure()
        assert circuit.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        # Should transition to HALF_OPEN
        assert circuit.can_execute() == True
        assert circuit.state == CircuitState.HALF_OPEN
        
        # Record successes to close circuit
        circuit.record_success()
        circuit.record_success()  # Default success threshold is 2
        
        assert circuit.state == CircuitState.CLOSED

class TestHealthMonitoring:
    """Test the health monitoring system"""
    
    @pytest.mark.asyncio
    async def test_health_monitor_success(self):
        """Test health monitor with successful health check"""
        monitor = MapsHealthMonitor()
        
        mock_result = [{'formatted_address': 'Test Address'}]
        
        with patch('googlemaps.Client') as mock_client:
            mock_client.return_value.geocode.return_value = mock_result
            
            health = await monitor.check_google_maps_health()
            
            assert health.is_healthy == True
            assert health.consecutive_failures == 0
            assert health.response_time_ms is not None
    
    @pytest.mark.asyncio
    async def test_health_monitor_failure(self):
        """Test health monitor with failed health check"""
        monitor = MapsHealthMonitor()
        
        with patch('googlemaps.Client') as mock_client:
            mock_client.return_value.geocode.side_effect = Exception("Connection failed")
            
            health = await monitor.check_google_maps_health()
            
            assert health.is_healthy == False
            assert health.consecutive_failures > 0
            assert health.error_message == "Connection failed"

class TestGracefulDegradation:
    """Test graceful degradation functionality"""
    
    def test_create_fallback_response_find_places(self):
        """Test fallback response for find_places"""
        response = GracefulDegradation.create_fallback_response(
            "find_places", 
            "Service unavailable",
            "Custom message"
        )
        
        assert response['status'] == 'degraded'
        assert response['message'] == 'Custom message'
        assert response['fallback_provided'] == True
        assert response['places'] == []
        assert 'suggested_actions' in response
    
    def test_create_fallback_response_directions(self):
        """Test fallback response for get_directions"""
        response = GracefulDegradation.create_fallback_response(
            "get_directions",
            "API timeout"
        )
        
        assert response['status'] == 'degraded'
        assert response['fallback_provided'] == True
        assert response['route'] == {}
        assert 'suggested_actions' in response

class TestLoggingIntegration:
    """Test the logging system integration"""
    
    def test_maps_request_logger_initialization(self):
        """Test that maps request logger initializes correctly"""
        logger = MapsRequestLogger()
        assert logger.logger is not None
        assert logger.logger.name == "open_webui.maps.api"
    
    def test_performance_logging_structure(self):
        """Test that performance logs have correct structure"""
        monitor = PerformanceMonitor()
        
        # Mock the logger to capture log output
        with patch.object(monitor.metrics_history[0] if monitor.metrics_history else None, 'append') as mock_log:
            request_id = monitor.start_request("test_operation")
            time.sleep(0.1)
            monitor.end_request(request_id, success=True)
        
        # Verify metrics were recorded
        assert len(monitor.metrics_history) > 0
        metrics = monitor.metrics_history[-1]
        assert metrics.operation == "test_operation"
        assert metrics.success == True
        assert metrics.duration is not None

class TestIntegrationScenarios:
    """Test complete integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_complete_failure_recovery_scenario(self):
        """Test complete failure and recovery scenario"""
        with patch('utils.maps_client.GOOGLE_MAPS_API_KEY', 'test_key'):
            maps_client = MapsClient()
            
            # Simulate repeated failures to open circuit
            with patch.object(maps_client.client, 'places', side_effect=Exception("Service down")):
                for i in range(6):  # More than failure threshold
                    try:
                        await maps_client.find_places("Jakarta", "restaurant")
                    except:
                        pass  # Expected failures
            
            # Circuit should be open
            assert maps_client.circuit_breaker.state == CircuitState.OPEN
            
            # Next call should return fallback
            result = await maps_client.find_places("Jakarta", "restaurant")
            assert isinstance(result, list)  # Fallback response
            
            # Simulate service recovery
            maps_client.circuit_breaker.config.recovery_timeout = 0.1
            await asyncio.sleep(0.2)
            
            mock_response = [{'name': 'Test', 'geometry': {'location': {'lat': 1, 'lng': 1}}}]
            with patch.object(maps_client.client, 'places', return_value={'results': mock_response}):
                # Should transition to HALF_OPEN and eventually CLOSED
                result1 = await maps_client.find_places("Jakarta", "restaurant")
                result2 = await maps_client.find_places("Jakarta", "restaurant")
                
                # Circuit should be closed after successful calls
                assert maps_client.circuit_breaker.state == CircuitState.CLOSED
                assert len(result2) > 0
    
    @pytest.mark.asyncio 
    async def test_coordinate_validation_in_performance_context(self):
        """Test coordinate validation doesn't impact performance significantly"""
        with patch('utils.maps_client.GOOGLE_MAPS_API_KEY', 'test_key'):
            maps_client = MapsClient()
            
            # Mock response with invalid coordinates
            mock_response = [
                {
                    'name': 'Valid Place',
                    'geometry': {'location': {'lat': -6.2088, 'lng': 106.8456}},
                    'formatted_address': 'Valid Address',
                    'place_id': 'ChIJ123'
                },
                {
                    'name': 'Invalid Place',
                    'geometry': {'location': {'lat': 0, 'lng': 0}},  # Invalid
                    'formatted_address': 'Invalid Address',
                    'place_id': 'ChIJ456'
                }
            ]
            
            with patch.object(maps_client.client, 'places', return_value={'results': mock_response}):
                start_time = time.time()
                result = await maps_client.find_places("Jakarta", "restaurant")
                duration = time.time() - start_time
                
                # Should still be fast even with validation
                assert duration < 5.0
                
                # Should filter out invalid coordinates
                valid_places = [p for p in result if p.get('lat') is not None and p.get('lng') is not None]
                assert len(valid_places) == 1
                assert valid_places[0]['name'] == 'Valid Place'

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 