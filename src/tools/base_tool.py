# src/tools/base_tool.py

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
    """
    Abstract Base Class for enterprise-grade tools.
    """

    name: str
    description: str
    args_schema: type[BaseModel]

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    @abstractmethod
    def _run(self, *args: Any, **kwargs: Any) -> str:
        """
        Core execution logic implemented by subclasses.
        """
        raise NotImplementedError

    def _safe_execute(self, *args: Any, **kwargs: Any) -> str:
        """
        Standardized execution wrapper with exception shielding.
        """

        with create_span(
            "tool.execute",
            tool_name=getattr(self, "name", "unknown_tool"),
            args=str(args)[:200],
            kwargs=str(kwargs)[:200],
        ) as span:
            start_time = time.perf_counter()
            try:
                result = self._run(*args, **kwargs)
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("tool_latency_ms", duration_ms)
                logger.info(
                    "Tool execution completed",
                    extra={
                        "extra_data": {
                            "tool_name": getattr(self, "name", "unknown_tool"),
                            "tool_latency_ms": duration_ms,
                        }
                    },
                )
                return result

            except Exception as e:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("tool_latency_ms", duration_ms)
                span.set_status(otel_trace.StatusCode.ERROR, str(e))
                logger.exception(
                    "Execution error in tool '%s'",
                    self.name,
                )

                return f"Error executing tool '{self.name}': {str(e)}"

    def to_langchain_tool(self) -> Tool:
        """
        Convert enterprise tool into LangChain-compatible Tool.
        """

        return Tool(
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
            func=self._safe_execute,
        )
