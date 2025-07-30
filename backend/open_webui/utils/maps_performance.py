import logging
import time
import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import aiohttp

log = logging.getLogger(__name__)

####################
# Performance Monitoring and Configuration
####################

@dataclass
class PerformanceConfig:
    """Configuration for performance optimization"""
    # Timeout configurations (in seconds)
    geocoding_timeout: float = 3.0
    places_search_timeout: float = 5.0
    directions_timeout: float = 7.0
    place_details_timeout: float = 4.0
    photo_timeout: float = 2.0
    
    # Connection pooling
    max_connections: int = 20
    max_connections_per_host: int = 10
    connection_timeout: float = 10.0
    
    # Retry configuration
    max_retries: int = 2
    retry_delay: float = 0.5
    
    # Performance thresholds
    slow_request_threshold: float = 3.0  # Log if request takes longer than 3s
    critical_timeout_threshold: float = 5.0  # Alert if approaching 5s target

@dataclass
class RequestMetrics:
    """Performance metrics for a single request"""
    request_id: str
    operation: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = True
    error_type: Optional[str] = None
    retry_count: int = 0
    cache_hit: bool = False

class PerformanceMonitor:
    """Monitor and track performance metrics for maps operations"""
    
    def __init__(self):
        self.metrics_history: List[RequestMetrics] = []
        self.active_requests: Dict[str, RequestMetrics] = {}
        
    def start_request(self, operation: str) -> str:
        """Start tracking a new request"""
        request_id = str(uuid.uuid4())[:8]
        metrics = RequestMetrics(
            request_id=request_id,
            operation=operation,
            start_time=time.time()
        )
        self.active_requests[request_id] = metrics
        return request_id
    
    def end_request(self, request_id: str, success: bool = True, error_type: Optional[str] = None):
        """End tracking a request and log performance metrics"""
        if request_id not in self.active_requests:
            return
            
        metrics = self.active_requests[request_id]
        metrics.end_time = time.time()
        metrics.duration = metrics.end_time - metrics.start_time
        metrics.success = success
        metrics.error_type = error_type
        
        # Log performance metrics
        self._log_performance_metrics(metrics)
        
        # Move to history
        self.metrics_history.append(metrics)
        del self.active_requests[request_id]
        
        # Keep only last 1000 metrics
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-1000:]
    
    def _log_performance_metrics(self, metrics: RequestMetrics):
        """Log structured performance metrics"""
        if metrics.duration is None:
            return
            
        perf_config = PerformanceConfig()
        
        # Structured logging data
        log_data = {
            "request_id": metrics.request_id,
            "operation": metrics.operation,
            "duration_ms": round(metrics.duration * 1000, 2),
            "success": metrics.success,
            "retry_count": metrics.retry_count,
            "cache_hit": metrics.cache_hit
        }
        
        if metrics.error_type:
            log_data["error_type"] = metrics.error_type
        
        # Determine log level based on performance
        if not metrics.success:
            log.error(f"Maps API request failed: {json.dumps(log_data)}")
        elif metrics.duration >= perf_config.critical_timeout_threshold:
            log.warning(f"Maps API request approaching timeout: {json.dumps(log_data)}")
        elif metrics.duration >= perf_config.slow_request_threshold:
            log.warning(f"Maps API slow request: {json.dumps(log_data)}")
        else:
            log.info(f"Maps API request completed: {json.dumps(log_data)}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get aggregated performance statistics"""
        if not self.metrics_history:
            return {"total_requests": 0}
            
        successful_requests = [m for m in self.metrics_history if m.success]
        failed_requests = [m for m in self.metrics_history if not m.success]
        
        durations = [m.duration for m in successful_requests if m.duration is not None]
        
        if not durations:
            return {"total_requests": len(self.metrics_history), "success_rate": 0}
        
        return {
            "total_requests": len(self.metrics_history),
            "successful_requests": len(successful_requests),
            "failed_requests": len(failed_requests),
            "success_rate": len(successful_requests) / len(self.metrics_history) * 100,
            "avg_duration_ms": round(sum(durations) / len(durations) * 1000, 2),
            "min_duration_ms": round(min(durations) * 1000, 2),
            "max_duration_ms": round(max(durations) * 1000, 2),
            "slow_requests": len([d for d in durations if d >= PerformanceConfig().slow_request_threshold]),
            "critical_requests": len([d for d in durations if d >= PerformanceConfig().critical_timeout_threshold])
        }

####################
# Connection Pool Manager
####################

class ConnectionPoolManager:
    """Manages HTTP connection pooling for optimal performance"""
    
    def __init__(self, config: PerformanceConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with connection pooling"""
        if self._session is None or self._session.closed:
            self._connector = aiohttp.TCPConnector(
                limit=self.config.max_connections,
                limit_per_host=self.config.max_connections_per_host,
                ttl_dns_cache=300,  # DNS cache for 5 minutes
                use_dns_cache=True,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(
                total=self.config.connection_timeout,
                connect=3.0
            )
            
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout,
                headers={"User-Agent": "OpenWebUI-Maps/1.0"}
            )
            
        return self._session
    
    async def close(self):
        """Close connection pool"""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._connector:
            await self._connector.close() 