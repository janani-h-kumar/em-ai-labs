# src/tools/base_tool.py

import logging
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.tools import Tool
from pydantic import BaseModel

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

        try:
            return self._run(*args, **kwargs)

        except Exception as e:
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
