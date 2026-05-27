"""
Enterprise agent manager with runtime orchestration and tooling.
"""

import logging
from pathlib import Path
from typing import Any

from src.router import MessageRouter
from src.runtimes.runtime_factory import RuntimeFactory
from src.tools.tool_registry import ToolRegistry
from src.utils.config_loader import ConfigManager
from src.utils.logging_utils import set_correlation_id, setup_structured_logging

# Setup structured logging — must happen before any logger.getLogger() calls
setup_structured_logging()
logger = logging.getLogger(__name__)


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
