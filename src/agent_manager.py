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
import time
from pathlib import Path
from typing import Any

from src.agents.agent_registry import AgentDescriptor, AgentRegistry
from src.core.container import ServiceContainer
from src.observability.tracing import create_span, increment_request_count
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

            # Ensure agent_capabilities is typed as dict[str, list[str]]
            agent_capabilities: dict[str, list[str]] = {}
            for name, descriptor in self.agent_registry.agents.items():
                if isinstance(descriptor, AgentDescriptor):
                    caps = descriptor.capabilities or []
                else:
                    caps = getattr(descriptor, "capabilities", []) or []
                agent_capabilities[name] = caps

            logger.info(
                "Building router from agent metadata",
                extra={"extra_data": {"agent_capabilities": agent_capabilities}},
            )

            self.router = MessageRouter(
                agent_capabilities=agent_capabilities,
            )

            # -------------------------------------------------
            # Orchestrator
            # -------------------------------------------------

            logger.info("Initialising orchestrator...")

            self.orchestrator = Orchestrator(
                agent_registry=self.agent_registry,
                router=self.router,
                provider=self.container.provider,
                memory=self.container.memory,
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
            current_request = increment_request_count()
            start_time = time.perf_counter()
            with create_span(
                "agent_manager.handle",
                request_id=request_id,
                session_id=request_id,
                request_count=current_request,
                message_length=len(message),
            ) as span:
                logger.info(
                    "Handling message",
                    extra={
                        "extra_data": {
                            "request_id": request_id,
                            "message_length": len(message),
                            "request_count": current_request,
                        }
                    },
                )

                response = await self.orchestrator.run(
                    goal=message,
                    session_id=request_id,
                )

                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("request_latency_ms", duration_ms)
                logger.info(
                    "Request completed successfully",
                    extra={
                        "extra_data": {
                            "request_id": request_id,
                            "request_latency_ms": duration_ms,
                            "request_count": current_request,
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
            "tools": len(self.container.tool_registry.get_langchain_tools()),
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

    # Example: handle a generic request — routing decides the appropriate agent.
    response = await manager.handle("Provide a short summary about today's events.")

    print(response)


if __name__ == "__main__":
    asyncio.run(_main())
