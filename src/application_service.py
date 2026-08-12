"""
Enterprise ApplicationService.

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

from src.agents.agent_registry import AgentRegistry
from src.core.container import ServiceContainer
from src.guardrails import InputGuardrail, load_guardrail_config, mark_guardrail_violation
from src.guardrails.exceptions import GuardrailViolationError
from src.observability.tracing import create_span, increment_request_count
from src.orchestration.orchestrator import Orchestrator
from src.router import MessageRouter
from src.utils.config_loader import ConfigManager
from src.utils.logging_utils import (
    reset_correlation_id,
    set_correlation_id,
    setup_structured_logging,
)

setup_structured_logging()
logger = logging.getLogger(__name__)


class ApplicationService:
    """Enterprise application manager for orchestration lifecycle."""

    def __init__(self, config_path: str | None = None) -> None:
        if config_path is None:
            config_path = str(Path(__file__).parent.parent / "configs" / "config.yaml")

        try:
            logger.info("Loading configuration from: %s", config_path)
            self.container = ServiceContainer(ConfigManager(config_path))
            self.container.config_manager.validate_startup()
            self.guardrail_config = load_guardrail_config(self.container.config_manager)
            self.input_guardrail = InputGuardrail(self.guardrail_config)

            # Agent discovery
            logger.info("Initialising agent registry...")
            self.agent_registry = AgentRegistry(container=self.container)

            # Router — pass descriptors directly so the router has full metadata.
            # When AgentDescriptor grows new fields (embedding, tags, version),
            # the router gets them automatically without changes here.
            descriptors = self.agent_registry.descriptors()
            logger.info(
                "Building router from agent metadata",
                extra={
                    "extra_data": {
                        "agent_capabilities": {d.name: d.capabilities for d in descriptors}
                    }
                },
            )
            self.router = MessageRouter(descriptors=descriptors)

            # Orchestrator
            logger.info("Initialising orchestrator...")
            self.orchestrator = Orchestrator(
                agent_registry=self.agent_registry,
                router=self.router,
                provider=self.container.provider,
                memory=self.container.memory,
                guardrail_config=self.guardrail_config,
                config_manager=self.container.config_manager,
            )

            logger.info("ApplicationService initialised successfully")
            self._initialized = True

        except Exception as e:
            logger.exception("Failed to initialise ApplicationService")
            raise e

    async def handle(self, message: str) -> str:
        """Top-level async request handler."""
        request_id = set_correlation_id()

        try:
            current_request = increment_request_count()
            start_time = time.perf_counter()

            with create_span(
                "request",
                **{
                    "execution.id": request_id,
                    "session.id": request_id,
                    "run_number": current_request,
                    "request_count": current_request,
                    "message_length": len(message) if isinstance(message, str) else 0,
                    "outcome": "unknown",
                },
            ) as span:
                # Input guardrail
                try:
                    message = self.input_guardrail.validate_prompt(message)
                except GuardrailViolationError as e:
                    mark_guardrail_violation(e)
                    span.set_attribute("guardrail.triggered", True)
                    span.set_attribute("guardrail.code", e.code)
                    logger.warning(
                        "Input guardrail blocked request",
                        extra={
                            "extra_data": {
                                "request_id": request_id,
                                "guardrail_code": e.code,
                                **e.details,
                            }
                        },
                    )
                    return e.public_message

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

                # Orchestrate — output guardrail is applied inside orchestrator.run()
                response = await self.orchestrator.run(
                    goal=message,
                    session_id=request_id,
                )

                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("request_latency_ms", duration_ms)
                span.set_attribute("duration_ms", duration_ms)
                span.set_attribute("outcome", "success")
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

        except GuardrailViolationError as e:
            mark_guardrail_violation(e)
            logger.warning(
                "Guardrail blocked request",
                extra={
                    "extra_data": {
                        "request_id": request_id,
                        "guardrail_code": e.code,
                        **e.details,
                    }
                },
            )
            return e.public_message

        except Exception as exc:
            from opentelemetry import trace as otel_trace

            current_span = otel_trace.get_current_span()
            if current_span.get_span_context().is_valid:
                current_span.set_attribute("outcome", "error")
                current_span.set_attribute("error.type", type(exc).__name__)
                current_span.record_exception(exc)
                current_span.set_status(otel_trace.StatusCode.ERROR, str(exc))
            logger.exception(
                "Failed to handle message",
                extra={"extra_data": {"request_id": request_id}},
            )
            return "Sorry, I encountered an error while processing your request."

        finally:
            reset_correlation_id()

    async def health_check(self) -> dict[str, Any]:
        """Application health status."""
        return {
            "manager": "healthy",
            "orchestrator": "healthy",
            "agents": self.agent_registry.list_agents(),
            "tools": len(self.container.tool_registry.get_langchain_tools()),
        }

    def is_initialized(self) -> bool:
        return hasattr(self, "_initialized") and self._initialized


async def _main() -> None:
    manager = ApplicationService()
    response = await manager.handle("What's the weather in Seattle?")
    print(response)


if __name__ == "__main__":
    asyncio.run(_main())
