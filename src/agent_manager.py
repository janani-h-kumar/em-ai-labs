"""
Enterprise Agent Manager.

Responsibilities:
- Bootstrap application components
- Load configuration
- Initialise orchestration system
- Handle top-level request lifecycle
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from src.agents.agent_registry import AgentRegistry
from src.core.container import ServiceContainer
from src.orchestration.orchestrator import Orchestrator
from src.router import MessageRouter
from src.utils.config_loader import ConfigManager
from src.utils.logging_utils import (
    set_correlation_id,
    setup_structured_logging,
)

# Structured logging setup
setup_structured_logging()

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Enterprise application manager for orchestration lifecycle.
    """

    def __init__(
        self,
        config_path: str | None = None,
    ):

        if config_path is None:
            config_path = str(Path(__file__).parent.parent / "configs" / "config.yaml")

        try:
            logger.info(
                "Loading configuration from: %s",
                config_path,
            )

            self.container = ServiceContainer(ConfigManager(config_path))
            self.container.config_manager.validate_startup()

            # -------------------------------------------------
            # Agent Discovery
            # -------------------------------------------------

            logger.info("Initialising agent registry...")

            self.agent_registry = AgentRegistry(container=self.container)

            # -------------------------------------------------
            # Router
            # -------------------------------------------------

            self.router = MessageRouter()

            # -------------------------------------------------
            # Orchestrator
            # -------------------------------------------------

            logger.info("Initialising orchestrator...")

            self.orchestrator = Orchestrator(
                agent_registry=self.agent_registry,
                router=self.router,
            )

            logger.info("AgentManager initialised successfully")

            self._initialized = True

        except Exception as e:
            logger.exception("Failed to initialise AgentManager")

            raise e

    async def handle(
        self,
        message: str,
    ) -> str:
        """
        Top-level async request handler.
        """

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

            response = await self.orchestrator.run(
                goal=message,
                session_id=request_id,
            )

            logger.info(
                "Request completed successfully",
                extra={
                    "extra_data": {
                        "request_id": request_id,
                    }
                },
            )

            return response

        except Exception:
            logger.exception(
                "Failed to handle message",
                extra={
                    "extra_data": {
                        "request_id": request_id,
                    }
                },
            )

            return "Sorry, I encountered an error while processing your request."

    async def health_check(self) -> dict[str, Any]:
        """
        Application health status.
        """

        return {
            "manager": "healthy",
            "orchestrator": "healthy",
            "agents": self.agent_registry.list_agents(),
            "tools": len(self.tool_registry.get_langchain_tools()),
        }

    def is_initialized(self) -> bool:
        """
        Check manager initialization status.
        """

        return hasattr(self, "_initialized") and self._initialized


# ---------------------------------------------------------
# Optional Local Runner
# ---------------------------------------------------------


async def _main():

    manager = AgentManager()

    response = await manager.handle("What is the weather in Seattle?")

    print(response)


if __name__ == "__main__":
    asyncio.run(_main())
