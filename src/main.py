"""
Enterprise agent manager with runtime orchestration and tooling.

Changes from original:
- Removed `from dataclasses import Field` — this import was unused and
  incorrect (dataclasses.Field is an internal type, not the same as
  pydantic.Field used below). It caused a linter error and confused readers.
- Removed duplicate sys.path.insert — now handled cleanly via package install.
- All other logic is unchanged.
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add src to path for imports (until the package is installed via pip install -e .)
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

# Setup structured logging — must happen before any logger.getLogger() calls
setup_structured_logging()
logger = logging.getLogger(__name__)

class WeatherInput(BaseModel):
    city: str = Field(
        description="The name of the city to look up the weather for, e.g., 'New York'"
    )

class SearchInput(BaseModel):
    query: str = Field(
        description="The web search query string, e.g., 'latest space exploration news'"
    )


class AgentManager:
    """
    Enterprise agent manager with runtime orchestration.

    Features:
    - Config-driven runtime selection (LangChain, custom)
    - Tool initialisation and integration
    - Message routing and processing
    - Health checks and telemetry
    - Graceful error handling

    Example:
        manager = AgentManager()
        response = manager.handle("What's the weather in NYC?")
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

            logger.info("Initialising tools...")
            self.tools = self._initialize_tools()

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

    def _initialize_tools(self) -> List[Tool]:
        tools: List[Tool] = []

        try:
            weather_client = WeatherClient(self.config_manager)
            weather_tool = Tool(
                name="weather",
                func=lambda *args, **kwargs: str(
                    weather_client.get_temperature(
                        city=kwargs.get("city") or (args[0] if args else None)
                    )
                ),
                description="Get current weather for a city. Input: city name. Output: temperature, condition, humidity."
                args_schema=WeatherInput,
            )
            tools.append(weather_tool)
            logger.info("Weather tool loaded")
        except Exception as e:
            logger.warning(f"Failed to load weather tool: {e}")

        try:
            search_client = WebSearchClient()
            search_tool = Tool(
                name="web_search",
                func=lambda *args, **kwargs: str(
                    search_client.search_as_dict(
                        query=kwargs.get("query") or (args[0] if args else None),
                        num_results=3,
                    )
                ),
                description="Search the web. Input: query string. Output: titles, URLs, snippets."
                args_schema=SearchInput,
            )
            tools.append(search_tool)
            logger.info("Web search tool loaded")
        except Exception as e:
            logger.warning(f"Failed to load web search tool: {e}")

        logger.info(f"Total tools initialised: {len(tools)}")
        return tools

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
        manager = AgentManager()
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
