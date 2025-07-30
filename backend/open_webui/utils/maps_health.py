import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

import googlemaps
from open_webui.env import GOOGLE_MAPS_API_KEY

log = logging.getLogger(__name__)

####################
# Health Check System
####################

@dataclass
class HealthStatus:
    """Health status for map services"""
    is_healthy: bool
    last_check: datetime
    error_message: Optional[str] = None
    response_time_ms: Optional[float] = None
    consecutive_failures: int = 0

class MapsHealthMonitor:
    """Monitor health of maps services"""
    
    def __init__(self):
        self.google_maps_health = HealthStatus(
            is_healthy=True,
            last_check=datetime.utcnow()
        )
        self.last_health_check = datetime.utcnow()
        self.health_check_interval = 300  # 5 minutes
        
    async def check_google_maps_health(self) -> HealthStatus:
        """Perform health check on Google Maps service"""
        start_time = time.time()
        
        try:
            # Simple geocoding test
            client = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
            result = client.geocode("1600 Amphitheatre Parkway, Mountain View, CA")
            
            response_time = (time.time() - start_time) * 1000
            
            if result:
                self.google_maps_health = HealthStatus(
                    is_healthy=True,
                    last_check=datetime.utcnow(),
                    response_time_ms=response_time,
                    consecutive_failures=0
                )
            else:
                raise Exception("No results returned from health check")
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.google_maps_health = HealthStatus(
                is_healthy=False,
                last_check=datetime.utcnow(),
                error_message=str(e),
                response_time_ms=response_time,
                consecutive_failures=self.google_maps_health.consecutive_failures + 1
            )
            
        return self.google_maps_health
    
    def should_check_health(self) -> bool:
        """Check if it's time for a health check"""
        return (datetime.utcnow() - self.last_health_check).seconds >= self.health_check_interval
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary"""
        return {
            "google_maps": {
                "healthy": self.google_maps_health.is_healthy,
                "last_check": self.google_maps_health.last_check.isoformat(),
                "response_time_ms": self.google_maps_health.response_time_ms,
                "consecutive_failures": self.google_maps_health.consecutive_failures,
                "error": self.google_maps_health.error_message
            },
            "overall_healthy": self.google_maps_health.is_healthy
        }

####################
# Resilient Error Handling
####################

class GracefulDegradation:
    """Provide fallback functionality when services are unavailable"""
    
    @staticmethod
    def create_fallback_response(operation: str, error: str, user_message: str = None) -> Dict[str, Any]:
        """Create a graceful fallback response"""
        fallback_message = user_message or GracefulDegradation._get_fallback_message(operation)
        
        base_response = {
            "status": "degraded",
            "message": fallback_message,
            "service_status": "unavailable",
            "fallback_provided": True,
            "error_details": {
                "operation": operation,
                "error": error,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        # Add operation-specific fallback data
        if operation == "find_places":
            base_response["places"] = []
            base_response["suggested_actions"] = [
                "Try again in a few minutes",
                "Check your internet connection",
                "Use Google Maps directly in your browser"
            ]
        elif operation == "get_directions":
            base_response["route"] = {}
            base_response["suggested_actions"] = [
                "Try again in a few minutes", 
                "Use Google Maps app for navigation",
                "Check traffic conditions manually"
            ]
        elif operation == "place_details":
            base_response["details"] = {}
            base_response["suggested_actions"] = [
                "Try again in a few minutes",
                "Search for the place directly on Google Maps",
                "Contact the business directly if you have their information"
            ]
            
        return base_response
    
    @staticmethod
    def _get_fallback_message(operation: str) -> str:
        """Get user-friendly fallback message for each operation"""
        messages = {
            "find_places": "Maps search is temporarily unavailable. Please try again in a few minutes or use Google Maps directly.",
            "get_directions": "Directions service is temporarily unavailable. Please try again in a few minutes or use a navigation app.",
            "place_details": "Place details are temporarily unavailable. Please try again in a few minutes."
        }
        return messages.get(operation, "Maps service is temporarily unavailable. Please try again later.") 