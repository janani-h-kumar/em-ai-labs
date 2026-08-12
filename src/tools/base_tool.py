"""Base tool contract and standardized tool-call telemetry."""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.tools import Tool
from opentelemetry import trace as otel_trace
from pydantic import BaseModel

from src.observability.tracing import create_span
from src.utils.config_loader import ConfigManager

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Abstract base class for all framework tools."""

    name: str
    description: str
    args_schema: type[BaseModel]

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    @abstractmethod
    def _run(self, *args: Any, **kwargs: Any) -> str:
        """Core execution logic implemented by subclasses."""
        raise NotImplementedError

    @staticmethod
    def _response_size_bytes(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray)):
            return len(value)
        try:
            return len(str(value).encode("utf-8"))
        except Exception:
            return None

    def _safe_execute(self, *args: Any, **kwargs: Any) -> str:
        """Execute the tool under the canonical ``tool.call`` span."""
        tool_name = getattr(self, "name", "unknown_tool")
        start_time = time.perf_counter()

        with create_span(
            "tool.call",
            tool_name=tool_name,
            tool=tool_name,
            outcome="unknown",
        ) as span:
            try:
                result = self._run(*args, **kwargs)
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("duration_ms", duration_ms)
                span.set_attribute("latency_ms", duration_ms)
                span.set_attribute("outcome", "success")

                response_size = self._response_size_bytes(result)
                if response_size is not None:
                    span.set_attribute("response_size_bytes", response_size)

                return result
            except Exception as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("duration_ms", duration_ms)
                span.set_attribute("latency_ms", duration_ms)
                span.set_attribute("outcome", "error")
                span.set_attribute("error.type", type(exc).__name__)
                span.record_exception(exc)
                span.set_status(otel_trace.StatusCode.ERROR, str(exc))
                logger.exception("Execution error in tool '%s'", tool_name)
                raise

    def to_langchain_tool(self) -> Tool:
        """Convert the enterprise tool into a LangChain-compatible tool."""
        return Tool(
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
            func=self._safe_execute,
        )
