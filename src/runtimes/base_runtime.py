"""
Abstract base class for orchestration runtimes.

All runtimes must implement this interface to provide consistent
orchestration capabilities for agents.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RuntimeTelemetry:
    """
    Execution telemetry for monitoring and optimization.
    
    Attributes:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        total_tokens: Total tokens (input + output)
        latency_ms: Execution latency in milliseconds
        cache_hit: Whether result was from cache
        model: Model name used for execution
    """
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    cache_hit: bool = False
    model: str = ""


class BaseRuntime(ABC):
    """
    Abstract base class for orchestration runtimes.
    
    All runtimes must implement invoke() to process messages.
    Optional helper methods for tool management and telemetry.
    
    Example:
        class MyRuntime(BaseRuntime):
            def invoke(self, message: str) -> str:
                # Process message and return response
                return "response"
    """
    
    def __init__(self, name: str = "BaseRuntime"):
        """
        Initialize runtime.
        
        Args:
            name: Name of runtime for logging
        """
        self.name = name
        self.telemetry: Optional[RuntimeTelemetry] = None
        self.tools: List[Any] = []
        logger.info(f"Initializing {name}")
    
    @abstractmethod
    def invoke(self, message: str) -> str:
        """
        Process a message and return response.
        
        Args:
            message: Input message/query
        
        Returns:
            Response string
        
        Raises:
            RuntimeError: If execution fails
        """
        pass
    
    def set_tools(self, tools: List[Any]) -> None:
        """
        Inject tools into runtime (optional).
        
        Allows tools to be set after initialization.
        
        Args:
            tools: List of Tool objects or clients
        """
        self.tools = tools
        tool_names = [
            t.name if hasattr(t, 'name') else str(t)
            for t in tools
        ]
        logger.debug(f"Tools injected: {tool_names}")
    
    def get_telemetry(self) -> Optional[RuntimeTelemetry]:
        """
        Return telemetry from last execution.
        
        Returns:
            RuntimeTelemetry object or None if not available
        """
        return self.telemetry
    
    def health_check(self) -> Dict[str, Any]:
        """
        Return runtime health status for monitoring.
        
        Returns:
            Dict with status, dependencies, etc.
            
        Example:
            {
                "runtime": "LangChainRuntime",
                "status": "healthy",
                "ollama": "up",
                "tools": 2
            }
        """
        return {
            "runtime": self.name,
            "status": "healthy",
            "timestamp": None,
        }
