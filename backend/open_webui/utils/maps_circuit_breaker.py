import logging
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

####################
# Circuit Breaker Pattern
####################

class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Service unavailable, failing fast
    HALF_OPEN = "half_open" # Testing if service is back

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5      # Number of failures before opening
    recovery_timeout: int = 60      # Seconds to wait before trying again
    success_threshold: int = 2      # Successful calls needed to close circuit
    timeout_threshold: int = 30     # Seconds after which a call is considered timeout

class CircuitBreaker:
    """Circuit breaker implementation for external service calls"""
    
    def __init__(self, config: CircuitBreakerConfig = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_call_time: Optional[datetime] = None
        
    def can_execute(self) -> bool:
        """Check if the circuit allows execution"""
        now = datetime.utcnow()
        self.last_call_time = now
        
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if (self.last_failure_time and 
                now - self.last_failure_time >= timedelta(seconds=self.config.recovery_timeout)):
                self.state = CircuitState.HALF_OPEN
                log.info("Circuit breaker transitioning to HALF_OPEN state")
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self):
        """Record a successful operation"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                log.info("Circuit breaker closed - service recovered")
        else:
            self.failure_count = 0  # Reset failure count on success
    
    def record_failure(self):
        """Record a failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.success_count = 0
            log.warning("Circuit breaker opened - service still failing")
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                log.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get current circuit breaker state information"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "time_until_retry": self._get_time_until_retry()
        }
    
    def _get_time_until_retry(self) -> Optional[int]:
        """Get seconds until next retry attempt"""
        if self.state == CircuitState.OPEN and self.last_failure_time:
            now = datetime.utcnow()
            retry_time = self.last_failure_time + timedelta(seconds=self.config.recovery_timeout)
            if retry_time > now:
                return int((retry_time - now).total_seconds())
        return None 