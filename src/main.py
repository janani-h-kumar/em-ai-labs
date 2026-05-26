"""
Enterprise agent manager with runtime orchestration and tooling.
"""

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.router import MessageRouter
from src.runtimes.runtime_factory import RuntimeFactory
from src.tools.tool_registry import ToolRegistry
from src.utils.config_loader import ConfigManager
from src.utils.logging_utils import set_correlation_id, setup_structured_logging

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
        args_schema: type[BaseModel],
        factory_fn: Callable[[Any], Callable[..., Any]],
    ):
        self.name = name
        self.description = description
        self.args_schema = args_schema
        self.factory_fn = factory_fn


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

    def __init__(self, config_path: str | None = None):
        if config_path is None:
            config_path = str(Path(__file__).parent.parent / "configs" / "config.yaml")

        try:
            logger.info("Loading configuration from: %s", config_path)
            self.config_manager = ConfigManager(config_path)
            self.config_manager.validate_startup()

            logger.info("Initialising tools via Generic ToolManager...")
            # Here is the clean integration swap:
            tool_registry = ToolRegistry(self.config_manager)
            tool_registry.discover_tools()
            self.tools = tool_registry.get_langchain_tools()

            runtime_type = self.config_manager.get("runtime.orchestration", default="langchain")
            logger.info("Creating runtime: %s", runtime_type)
            self.runtime = RuntimeFactory.create(
                runtime_type=runtime_type,
                config_manager=self.config_manager,
                tools=self.tools,
            )

            self.router = MessageRouter()

            logger.info("AgentManager initialised successfully")
            self._initialized = True

        except Exception as e:
            logger.error("Failed to initialise AgentManager: %s", e)
            raise

    def handle(self, message: str) -> str:
        request_id = set_correlation_id()

        try:
            logger.info(
                "Handling message",
                extra={
                    "extra_data": {
                        "request_id": request_id,
                        "message_length": len(message),
                    }
                },
            )

            agent_name, confidence = self.router.route_message(message)
            logger.info(
                "Message routed",
                extra={
                    "extra_data": {
                        "request_id": request_id,
                        "agent": agent_name,
                        "confidence": confidence,
                    }
                },
            )

            response = self.runtime.invoke(message)

            if self.runtime.get_telemetry():
                telemetry = self.runtime.get_telemetry()
                logger.info(
                    "Response generated",
                    extra={
                        "extra_data": {
                            "request_id": request_id,
                            "tokens": telemetry.total_tokens,
                            "latency_ms": telemetry.latency_ms,
                            "cache_hit": telemetry.cache_hit,
                        }
                    },
                )

            return response

        except Exception as e:
            logger.error(
                "Failed to handle message: %s",
                e,
                extra={"extra_data": {"request_id": request_id}},
            )
            return f"Sorry, I encountered an error: {e}"

    def health_check(self) -> dict[str, Any]:
        return {
            "manager": "healthy",
            "runtime": self.runtime.health_check(),
            "tools": len(self.tools),
        }

    def is_initialized(self) -> bool:
        return hasattr(self, "_initialized") and self._initialized


def run_interactive_chat():
    """Run interactive chat loop with agent system."""
    print("\n" + "=" * 50)
    print("AI Lab — Agent Orchestration System")
    print("=" * 50)
    print("Type 'exit' to quit, 'help' for commands\n")

    try:
        startup_start = time.perf_counter()
        manager = AgentManager()
        logger.info(
            "Application startup complete",
            extra={"startup_duration_sec": round(time.perf_counter() - startup_start, 2)},
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
            logger.error("Unexpected error: %s", e)
            print(f"Error: {e}\n")


if __name__ == "__main__":
    run_interactive_chat()
