from abc import ABC, abstractmethod
from typing import Any

from langchain_core.tools import Tool
from pydantic import BaseModel

from src.utils.config_loader import ConfigManager


class BaseTool(ABC):
    """
    Abstract Base Class for all enterprise tools.
    Handles LangChain conversion, configuration injection, and standardized error shielding.
    """
    name: str
    description: str
    args_schema: type[BaseModel]

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    @abstractmethod
    def _run(self, *args: Any, **kwargs: Any) -> str:
        """
        The core logic of the tool. Must be implemented by subclasses.
        Accepts unstructured parameters but should rely on validated kwargs from args_schema.
        """
        pass

    def to_langchain_tool(self) -> Tool:
        """
        Generates a standard LangChain Tool with built-in execution safeguards.
        """
        return Tool(
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
            func=self._safe_execute
        )

    def _safe_execute(self, *args: Any, **kwargs: Any) -> str:
        """
        Internal wrapper that provides uniform error logging and a safe fallback string 
        to ensure a broken API call doesn't crash the entire LLM runtime loop.
        """
        try:
            # Route execution to the concrete subclass implementation
            return self._run(*args, **kwargs)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            
            # FIXED G201 / G004: Used logger.exception with lazy formatting to handle traceback and variables
            logger.exception("Execution error in tool '%s'", self.name)
            return f"Error executing tool '{self.name}': {str(e)}"
