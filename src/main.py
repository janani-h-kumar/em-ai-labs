"""
Enterprise agent manager with runtime orchestration and tooling.

Features:
- Config-driven runtime selection (LangChain, custom)
- Tool integration (weather, web search)
- Telemetry and monitoring
- Health checks and graceful degradation
"""

from dataclasses import Field
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config_loader import ConfigManager
from src.utils.logging_utils import setup_structured_logging, set_correlation_id
from src.runtimes.runtime_factory import RuntimeFactory
from src.runtimes.base_runtime import BaseRuntime
from src.router import MessageRouter
from src.tools.weather_tool import WeatherClient
from src.tools.web_search_tool import WebSearchClient
from langchain_core.tools import Tool
from pydantic import BaseModel, Field

# Setup structured logging
setup_structured_logging()
logger = logging.getLogger(__name__)

class WeatherInput(BaseModel):
    city: str = Field(description="The name of the city to look up the weather for, e.g., 'New York'")

class SearchInput(BaseModel):
    query: str = Field(description="The web search query string, e.g., 'latest space exploration news'")
    
class AgentManager:
    """
    Enterprise agent manager with runtime orchestration.
    
    Features:
    - Config-driven runtime selection (LangChain, custom)
    - Tool initialization and integration
    - Message routing and processing
    - Health checks and telemetry
    - Graceful error handling
    
    Example:
        manager = AgentManager()
        response = manager.handle("What's the weather in NYC?")
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize agent manager with config and runtime.
        
        Args:
            config_path: Path to configuration file. 
                        If None, uses default: configs/config.yaml
        
        Raises:
            ConfigValidationError: If required config missing
            RuntimeError: If runtime initialization fails
        """
        if config_path is None:
            config_path = str(Path(__file__).parent.parent / "configs" / "config.yaml")
        
        try:
            # Load and validate configuration
            logger.info(f"Loading configuration from: {config_path}")
            self.config_manager = ConfigManager(config_path)
            self.config_manager.validate_startup()
            
            # Initialize tools
            logger.info("Initializing tools...")
            self.tools = self._initialize_tools()
            
            # Initialize runtime (config-driven)
            runtime_type = self.config_manager.get(
                "runtime.orchestration",
                default="langchain"
            )
            logger.info(f"Creating runtime: {runtime_type}")
            self.runtime = RuntimeFactory.create(
                runtime_type=runtime_type,
                config_manager=self.config_manager,
                tools=self.tools
            )
            
            # Initialize message router
            self.router = MessageRouter()
            
            logger.info("✅ AgentManager initialized successfully")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize AgentManager: {e}")
            raise
    
    def _initialize_tools(self) -> List[Tool]:
        """
        Initialize and wrap tools for LangChain.
        
        Returns:
            List of LangChain Tool objects
        """
        tools: List[Tool] = []
        
        # Weather tool
        try:
            weather_client = WeatherClient(self.config_manager)
            weather_tool = Tool(
                name="weather",                
                func=lambda *args, **kwargs: str(
                    weather_client.get_temperature(
                        city=kwargs.get("city") or (args[0] if args else None)
                    )
                ),
                description=(
                    "Get current weather for a city. "
                    "Input: city name (e.g., 'New York'). "
                    "Output: temperature, condition, humidity, pressure."
                ),
                args_schema=WeatherInput,               
            )            
            tools.append(weather_tool)
            logger.info("✅ Weather tool loaded")
        except Exception as e:
            logger.warning(f"⚠️  Failed to load weather tool: {e}")
        
        # Web search tool
        try:
            search_client = WebSearchClient()
            search_tool = Tool(
                name="web_search",
                func=lambda *args, **kwargs: str(
                    search_client.search_as_dict(
                        query=kwargs.get("query") or (args[0] if args else None), 
                        num_results=3
                    )
                ),                
                description=(
                    "Search the web for information. "
                    "Input: search query. "
                    "Output: list of results with title, URL, and snippet."
                ),
                args_schema=SearchInput
            )
            tools.append(search_tool)
            logger.info("✅ Web search tool loaded")
        except Exception as e:
            logger.warning(f"⚠️  Failed to load web search tool: {e}")
        
        logger.info(f"Total tools initialized: {len(tools)}")
        return tools
    
    def handle(self, message: str) -> str:
        """
        Handle user message through runtime.
        
        Args:
            message: User input
        
        Returns:
            Response from runtime
        """
        request_id = set_correlation_id()
        
        try:
            logger.info(
                f"Handling message",
                extra={"extra_data": {
                    "request_id": request_id,
                    "message_length": len(message)
                }}
            )
            
            # Route message to determine agent (for future multi-agent support)
            agent_name, confidence = self.router.route_message(message)
            logger.info(
                f"Message routed",
                extra={"extra_data": {
                    "request_id": request_id,
                    "agent": agent_name,
                    "confidence": confidence
                }}
            )
            
            # Process through runtime
            response = self.runtime.invoke(message)
            
            # Log telemetry if available
            if self.runtime.get_telemetry():
                telemetry = self.runtime.get_telemetry()
                logger.info(
                    f"Response generated",
                    extra={"extra_data": {
                        "request_id": request_id,
                        "tokens": telemetry.total_tokens,
                        "latency_ms": telemetry.latency_ms,
                        "cache_hit": telemetry.cache_hit
                    }}
                )
            
            return response
        
        except Exception as e:
            logger.error(f"Failed to handle message: {e}", extra={"extra_data": {"request_id": request_id}})
            return f"Sorry, I encountered an error: {e}"
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on runtime and dependencies.
        
        Returns:
            Dict with health status
        """
        return {
            "manager": "healthy",
            "runtime": self.runtime.health_check(),
            "tools": len(self.tools),
        }
    
    def is_initialized(self) -> bool:
        """Check if manager is properly initialized."""
        return hasattr(self, '_initialized') and self._initialized


def run_interactive_chat():
    """Run interactive chat loop with agent system."""
    print("\n" + "="*50)
    print("🤖 AI Lab - Agent Orchestration System")
    print("="*50)
    print("Available agents: weather, web search, and more")
    print("Type 'exit' to quit, 'help' for commands\n")
    
    # Initialize agent manager
    try:
        manager = AgentManager()
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return
    
    while True:
        try:
            msg = input("You: ").strip()
            
            if not msg:
                continue
            
            if msg.lower() in ["exit", "quit"]:
                print("\nGoodbye! 👋\n")
                break
            
            if msg.lower() == "help":
                print("\n" + "="*50)
                print("Commands:")
                print("  exit/quit  - Exit the chat")
                print("  health     - Show system health")
                print("  help       - Show this help")
                print("\nOr just ask a question!")
                print("="*50 + "\n")
                continue
            
            if msg.lower() == "health":
                health = manager.health_check()
                print(f"\n✅ System Health: {health}\n")
                continue
            
            # Process user message
            print(f"\nAssistant: {manager.handle(msg)}\n")
        
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋\n")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    run_interactive_chat()