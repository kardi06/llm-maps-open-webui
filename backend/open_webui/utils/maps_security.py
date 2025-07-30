import time
import logging
import hashlib
import re
from typing import Dict, Any, Optional
from collections import defaultdict, deque
from datetime import datetime, timedelta
from dataclasses import dataclass

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from open_webui.env import SRC_LOG_LEVELS
from open_webui.constants import ERROR_MESSAGES

####################
# Maps Security & Rate Limiting
####################

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

# Rate limiting storage (in production, use Redis or database)
_rate_limit_storage: Dict[str, deque] = defaultdict(lambda: deque())
_api_usage_storage: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
    'total_requests': 0,
    'requests_today': 0,
    'last_request': None,
    'quota_exceeded_count': 0
})

@dataclass
class RateLimitConfig:
    """Rate limit configuration for different endpoints"""
    requests_per_minute: int = 10
    requests_per_hour: int = 100
    requests_per_day: int = 1000
    burst_limit: int = 5  # Allow small bursts

class MapsSecurityError(Exception):
    """Custom exception for Maps security violations"""
    pass

class MapsRateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware specifically for Maps API endpoints"""
    
    def __init__(self, app, config: Optional[RateLimitConfig] = None):
        super().__init__(app)
        self.config = config or RateLimitConfig()
        
    async def dispatch(self, request: Request, call_next):
        # Only apply rate limiting to maps endpoints
        if not request.url.path.startswith("/api/v1/maps"):
            return await call_next(request)
        
        try:
            # Check rate limits
            await self._check_rate_limits(request)
            
            # Proceed with request
            start_time = time.time()
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Log successful request
            await self._log_api_usage(request, response.status_code, duration)
            
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions (like rate limit exceeded)
            raise
        except Exception as e:
            log.error(f"Maps security middleware error: {e}")
            # Don't block requests on middleware errors
            return await call_next(request)

    async def _check_rate_limits(self, request: Request):
        """Check if request exceeds rate limits"""
        client_id = self._get_client_identifier(request)
        endpoint = request.url.path
        current_time = time.time()
        
        # Get or create rate limit storage for this client
        client_requests = _rate_limit_storage[f"{client_id}:{endpoint}"]
        
        # Clean old requests (older than 1 hour)
        while client_requests and client_requests[0] < current_time - 3600:
            client_requests.popleft()
        
        # Check minute rate limit
        minute_requests = [t for t in client_requests if t > current_time - 60]
        if len(minute_requests) >= self.config.requests_per_minute:
            await self._handle_rate_limit_exceeded(request, "per_minute")
            
        # Check hour rate limit
        hour_requests = [t for t in client_requests if t > current_time - 3600]
        if len(hour_requests) >= self.config.requests_per_hour:
            await self._handle_rate_limit_exceeded(request, "per_hour")
            
        # Check daily rate limit
        daily_requests = [t for t in client_requests if t > current_time - 86400]
        if len(daily_requests) >= self.config.requests_per_day:
            await self._handle_rate_limit_exceeded(request, "per_day")
        
        # Add current request
        client_requests.append(current_time)
        
        log.info(f"Maps API rate limit check passed for {client_id}: "
                f"minute={len(minute_requests)}/{self.config.requests_per_minute}, "
                f"hour={len(hour_requests)}/{self.config.requests_per_hour}, "
                f"daily={len(daily_requests)}/{self.config.requests_per_day}")

    async def _handle_rate_limit_exceeded(self, request: Request, limit_type: str):
        """Handle rate limit exceeded scenarios"""
        client_id = self._get_client_identifier(request)
        
        # Update quota exceeded count
        _api_usage_storage[client_id]['quota_exceeded_count'] += 1
        
        log.warning(f"Maps API rate limit exceeded for {client_id}: {limit_type}")
        
        # Return appropriate rate limit error
        retry_after = self._get_retry_after_seconds(limit_type)
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Maps API rate limit exceeded ({limit_type}). Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
        )

    async def _log_api_usage(self, request: Request, status_code: int, duration: float):
        """Log API usage for monitoring and analytics"""
        client_id = self._get_client_identifier(request)
        endpoint = request.url.path
        
        # Update usage statistics
        usage = _api_usage_storage[client_id]
        usage['total_requests'] += 1
        usage['last_request'] = datetime.now()
        
        # Reset daily counter if it's a new day
        today = datetime.now().date()
        if usage.get('last_date') != today:
            usage['requests_today'] = 0
            usage['last_date'] = today
        
        usage['requests_today'] += 1
        
        # Log request details
        log.info(f"Maps API usage: client={client_id}, endpoint={endpoint}, "
                f"status={status_code}, duration={duration:.2f}s, "
                f"daily_count={usage['requests_today']}")

    def _get_client_identifier(self, request: Request) -> str:
        """Get unique identifier for rate limiting (user ID or IP)"""
        # Try to get user ID from auth
        user = getattr(request.state, 'user', None)
        if user and hasattr(user, 'id'):
            return f"user:{user.id}"
        
        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        return f"ip:{client_ip}"

    def _get_retry_after_seconds(self, limit_type: str) -> int:
        """Get appropriate retry-after seconds based on limit type"""
        if limit_type == "per_minute":
            return 60
        elif limit_type == "per_hour":
            return 3600
        elif limit_type == "per_day":
            return 86400
        return 60

class MapsInputSanitizer:
    """Input sanitization utilities for Maps API endpoints"""
    
    # Regex patterns for validation
    PLACE_ID_PATTERN = re.compile(r'^[A-Za-z0-9_-]{10,100}$')
    LOCATION_PATTERN = re.compile(r'^[A-Za-z0-9\s,.\-()\']{1,200}$')
    QUERY_PATTERN = re.compile(r'^[A-Za-z0-9\s,.\-()&\'\":]{1,100}$')
    
    # Dangerous patterns to block
    DANGEROUS_PATTERNS = [
        re.compile(r'<script', re.IGNORECASE),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'vbscript:', re.IGNORECASE),
        re.compile(r'onload=', re.IGNORECASE),
        re.compile(r'onerror=', re.IGNORECASE),
        re.compile(r'eval\(', re.IGNORECASE),
        re.compile(r'exec\(', re.IGNORECASE),
    ]
    
    @classmethod
    def sanitize_location(cls, location: str) -> str:
        """Sanitize location input"""
        if not location:
            raise MapsSecurityError("Location cannot be empty")
        
        location = location.strip()
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(location):
                raise MapsSecurityError("Invalid characters detected in location")
        
        # Validate format
        if not cls.LOCATION_PATTERN.match(location):
            raise MapsSecurityError("Location contains invalid characters")
        
        # Remove excessive whitespace
        location = re.sub(r'\s+', ' ', location)
        
        return location

    @classmethod
    def sanitize_query(cls, query: str) -> str:
        """Sanitize search query input"""
        if not query:
            raise MapsSecurityError("Query cannot be empty")
        
        query = query.strip()
        
        # Debug logging to help identify validation issues
        log.debug(f"Sanitizing query: {repr(query)} (length: {len(query)})")
        
        # Check for dangerous patterns
        for i, pattern in enumerate(cls.DANGEROUS_PATTERNS):
            if pattern.search(query):
                log.warning(f"Query failed dangerous pattern check {i}: {pattern.pattern}")
                raise MapsSecurityError("Invalid characters detected in query")
        
        # Validate format
        if not cls.QUERY_PATTERN.match(query):
            log.warning(f"Query failed pattern validation: {repr(query)} against {cls.QUERY_PATTERN.pattern}")
            # Log each character for debugging
            invalid_chars = []
            for char in query:
                if not re.match(r'[A-Za-z0-9\s,.\-()&\'\":=+@#/]', char):
                    invalid_chars.append(f"'{char}' (ord: {ord(char)})")
            if invalid_chars:
                log.warning(f"Invalid characters found: {', '.join(invalid_chars)}")
                
            # For legitimate business searches, be more permissive
            # Only block queries with clearly dangerous patterns
            if any(dangerous_char in query.lower() for dangerous_char in ['<script', 'javascript:', 'eval(', 'exec(']):
                raise MapsSecurityError("Query contains invalid characters")
            else:
                # Log but allow the query through with basic sanitization
                log.info(f"Allowing query with non-standard characters after safety check: {repr(query)}")
                # Basic sanitization - remove only truly dangerous characters
                query = re.sub(r'[<>]', '', query)  # Remove angle brackets
        
        # Remove excessive whitespace
        query = re.sub(r'\s+', ' ', query)
        
        return query

    @classmethod
    def sanitize_place_id(cls, place_id: str) -> str:
        """Sanitize Google Place ID input"""
        if not place_id:
            raise MapsSecurityError("Place ID cannot be empty")
        
        place_id = place_id.strip()
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(place_id):
                raise MapsSecurityError("Invalid characters detected in place ID")
        
        # Validate format
        if not cls.PLACE_ID_PATTERN.match(place_id):
            raise MapsSecurityError("Place ID format is invalid")
        
        return place_id

    @classmethod
    def sanitize_travel_mode(cls, mode: str) -> str:
        """Sanitize travel mode input"""
        if not mode:
            return "driving"  # Default mode
        
        mode = mode.strip().lower()
        
        # Whitelist valid modes
        valid_modes = {'driving', 'walking', 'bicycling', 'transit'}
        if mode not in valid_modes:
            raise MapsSecurityError(f"Invalid travel mode. Must be one of: {', '.join(valid_modes)}")
        
        return mode

class MapsUsageMonitor:
    """Monitor and track Maps API usage for analytics and quota management"""
    
    @staticmethod
    def get_usage_stats(client_id: str) -> Dict[str, Any]:
        """Get usage statistics for a client"""
        return _api_usage_storage.get(client_id, {
            'total_requests': 0,
            'requests_today': 0,
            'last_request': None,
            'quota_exceeded_count': 0
        })
    
    @staticmethod
    def get_global_usage_stats() -> Dict[str, Any]:
        """Get global usage statistics across all clients"""
        total_requests = sum(stats.get('total_requests', 0) for stats in _api_usage_storage.values())
        total_clients = len(_api_usage_storage)
        total_quota_exceeded = sum(stats.get('quota_exceeded_count', 0) for stats in _api_usage_storage.values())
        
        return {
            'total_requests': total_requests,
            'total_clients': total_clients,
            'total_quota_exceeded': total_quota_exceeded,
            'active_clients': len([s for s in _api_usage_storage.values() 
                                 if s.get('last_request') and 
                                 s['last_request'] > datetime.now() - timedelta(hours=1)])
        }
    
    @staticmethod
    def reset_usage_stats(client_id: Optional[str] = None):
        """Reset usage statistics (for testing or admin purposes)"""
        if client_id:
            if client_id in _api_usage_storage:
                del _api_usage_storage[client_id]
            if f"{client_id}:find_places" in _rate_limit_storage:
                del _rate_limit_storage[f"{client_id}:find_places"]
            if f"{client_id}:get_directions" in _rate_limit_storage:
                del _rate_limit_storage[f"{client_id}:get_directions"]
            if f"{client_id}:place_details" in _rate_limit_storage:
                del _rate_limit_storage[f"{client_id}:place_details"]
        else:
            _api_usage_storage.clear()
            _rate_limit_storage.clear()

# Utility functions for easy integration

def validate_and_sanitize_maps_input(location: str = None, query: str = None, 
                                   place_id: str = None, mode: str = None) -> Dict[str, str]:
    """Validate and sanitize all maps input parameters"""
    result = {}
    
    try:
        if location is not None:
            result['location'] = MapsInputSanitizer.sanitize_location(location)
        
        if query is not None:
            result['query'] = MapsInputSanitizer.sanitize_query(query)
        
        if place_id is not None:
            result['place_id'] = MapsInputSanitizer.sanitize_place_id(place_id)
        
        if mode is not None:
            result['mode'] = MapsInputSanitizer.sanitize_travel_mode(mode)
        
        return result
        
    except MapsSecurityError as e:
        log.warning(f"Maps input validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input validation failed: {str(e)}"
        )

def log_maps_security_event(event_type: str, client_id: str, details: Dict[str, Any]):
    """Log security events for audit purposes"""
    log.warning(f"Maps security event: type={event_type}, client={client_id}, details={details}")

# Default rate limit configuration
DEFAULT_MAPS_RATE_LIMIT_CONFIG = RateLimitConfig(
    requests_per_minute=10,  # Conservative limit for Maps API
    requests_per_hour=100,   # Reasonable for typical usage
    requests_per_day=500,    # Daily quota to prevent abuse
    burst_limit=5
) 