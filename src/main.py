"""
Enterprise agent manager with runtime orchestration and tooling.
"""

import logging
import time
from pathlib import Path
from typing import List, Dict, Type, Callable, Any, Optional
from utils.config_loader import ConfigManager
from utils.logging_utils import setup_structured_logging, set_correlation_id
from src.runtimes.runtime_factory import RuntimeFactory
from src.router import MessageRouter
from src.tools.weather_tool import WeatherClient, WeatherInput
from src.tools.web_search_tool import WebSearchClient, WebSearchInput
from langchain_core.tools import Tool
from pydantic import BaseModel

# Setup structured logging — must happen before any logger.getLogger() calls
setup_structured_logging()
logger = logging.getLogger(__name__)


# --- Generic Tool Registry Framework ---
class ToolConfig:
    """A clean wrapper to define what a tool needs to initialize."""
    def __init__(
        self, 
        name: str, 
        description: str, 
        args_schema: Type[BaseModel], 
        factory_fn: Callable[[Any], Callable[..., Any]]
    ):
        self.name = name
        self.description = description
        self.args_schema = args_schema
        self.factory_fn = factory_fn


class ToolManager:
    """Handles registry and clean runtime initialization of external agent tools."""
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        
        # Central Registry: Adding new tools down the road happens strictly here
        self._tool_registry: List[ToolConfig] = [
            ToolConfig(
                name="weather",
                description="Get current weather for a city. Input: city name. Output: temperature, condition, humidity.",
                args_schema=WeatherInput,
                factory_fn=lambda manager: lambda *args, **kwargs: str(
                    WeatherClient(manager.config_manager).get_temperature(
                        city=kwargs.get("city") or (args[0] if args else None)
                    )
                )
            ),
            ToolConfig(
                name="web_search",
                description="Search the web. Input: query string. Output: titles, URLs, snippets.",
                args_schema=WebSearchInput,
                factory_fn=lambda manager: lambda *args, **kwargs: str(
                    WebSearchClient().search_as_dict(
                        query=kwargs.get("query") or (args[0] if args else None),
                        num_results=3,
                    )
                )
            ),
        ]

    def initialize_tools(self) -> List[Tool]:
        """Loops through registry to instantiate LangChain-compatible executable tools."""
        tools: List[Tool] = []

        for config in self._tool_registry:
            try:
                executable_func = config.factory_fn(self)
                
                tool = Tool(
                    name=config.name,
                    func=executable_func,
                    description=config.description,
                    args_schema=config.args_schema,
                )
                tools.append(tool)
                logger.info(f"Tool '{config.name}' loaded successfully")
                
            except Exception as e:
                logger.warning(f"Failed to load tool '{config.name}': {e}")

        logger.info(f"Total tools initialized generic registry: {len(tools)}")
        return tools


# --- Core Orchestrator ---

class AgentManager:
    """
    Enterprise agent manager with runtime orchestration.

    Features:
    - Config-driven runtime selection (LangChain, custom)
    - Tool initialisation and integration via generic ToolManager
    - Message routing and processing
    - Health checks and telemetry
    - Graceful error handling
    """

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = str(
                Path(__file__).parent.parent / "configs" / "config.yaml"
            )

        try:
            logger.info(f"Loading configuration from: {config_path}")
            self.config_manager = ConfigManager(config_path)
            self.config_manager.validate_startup()

            logger.info("Initialising tools via Generic ToolManager...")
            # Here is the clean integration swap:
            self.tool_manager = ToolManager(self.config_manager)
            self.tools = self.tool_manager.initialize_tools()

            runtime_type = self.config_manager.get(
                "runtime.orchestration", default="langchain"
            )
            logger.info(f"Creating runtime: {runtime_type}")
            self.runtime = RuntimeFactory.create(
                runtime_type=runtime_type,
                config_manager=self.config_manager,
                tools=self.tools,
            )

            self.router = MessageRouter()

            logger.info("AgentManager initialised successfully")
            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialise AgentManager: {e}")
            raise

    def handle(self, message: str) -> str:
        request_id = set_correlation_id()

        try:
            logger.info(
                "Handling message",
                extra={"extra_data": {
                    "request_id": request_id,
                    "message_length": len(message),
                }},
            )

            agent_name, confidence = self.router.route_message(message)
            logger.info(
                "Message routed",
                extra={"extra_data": {
                    "request_id": request_id,
                    "agent": agent_name,
                    "confidence": confidence,
                }},
            )

            response = self.runtime.invoke(message)

            if self.runtime.get_telemetry():
                telemetry = self.runtime.get_telemetry()
                logger.info(
                    "Response generated",
                    extra={"extra_data": {
                        "request_id": request_id,
                        "tokens": telemetry.total_tokens,
                        "latency_ms": telemetry.latency_ms,
                        "cache_hit": telemetry.cache_hit,
                    }},
                )

            return response

        except Exception as e:
            logger.error(
                f"Failed to handle message: {e}",
                extra={"extra_data": {"request_id": request_id}},
            )
            return f"Sorry, I encountered an error: {e}"

    def health_check(self) -> Dict[str, Any]:
        return {
            "manager": "healthy",
            "runtime": self.runtime.health_check(),
            "tools": len(self.tools),
        }

    def is_initialized(self) -> bool:
        return hasattr(self, '_initialized') and self._initialized


def run_interactive_chat():
    
    """Run interactive chat loop with agent system."""
    print("\n" + "="*50)
    print("AI Lab — Agent Orchestration System")
    print("="*50)
    print("Type 'exit' to quit, 'help' for commands\n")

    try:
        startup_start = time.perf_counter()
        manager = AgentManager()
        logger.info(
    "Application startup complete",
    extra={
        "startup_duration_sec":
            round(time.perf_counter() - startup_start, 2)
    }
)
    except Exception as e:
        print(f"Failed to initialise: {e}")
        return

    while True:
        try:
            msg = input("You: ").strip()

            if not msg:
                continue
            if msg.lower() in ("exit", "quit"):
                print("\nGoodbye!\n")
                break
            if msg.lower() == "help":
                print("\nCommands: exit/quit, health, or ask a question\n")
                continue
            if msg.lower() == "health":
                print(f"\nSystem Health: {manager.health_check()}\n")
                continue

            print(f"\nAssistant: {manager.handle(msg)}\n")

        except KeyboardInterrupt:
            print("\n\nGoodbye!\n")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            print(f"Error: {e}\n")


if __name__ == "__main__":
    run_interactive_chat()