import importlib
import inspect
import logging
import pkgutil

from langchain_core.tools import Tool

from src.tools.base_tool import BaseTool
from src.utils.config_loader import ConfigManager

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Auto-discovers and initializes all BaseTool subclasses.
    """

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

        self._tool_instances: dict[str, BaseTool] = {}

    def discover_tools(self) -> None:
        """
        Scan src.tools package for BaseTool subclasses.
        """

        import src.tools

        for _, module_name, _ in pkgutil.iter_modules(src.tools.__path__):
            # Skip internal framework modules
            if module_name in {
                "base_tool",
                "tool_registry",
            }:
                continue

            module_path = f"src.tools.{module_name}"

            try:
                module = importlib.import_module(module_path)

            except Exception:
                logger.exception(
                    "Failed importing module '%s'",
                    module_path,
                )
                continue

            for _, obj in inspect.getmembers(
                module,
                inspect.isclass,
            ):
                if issubclass(obj, BaseTool) and obj is not BaseTool:
                    try:
                        instance = obj(self.config_manager)

                        self._tool_instances[instance.name] = instance

                        logger.info(
                            "Registered tool '%s'",
                            instance.name,
                        )

                    except Exception:
                        logger.exception(
                            "Failed initializing tool '%s'",
                            obj.__name__,
                        )

    def get_tool(self, name: str) -> BaseTool:
        return self._tool_instances[name]

    def get_all_tools(self) -> list[BaseTool]:
        return list(self._tool_instances.values())

    def get_langchain_tools(self) -> list[Tool]:
        return [tool.to_langchain_tool() for tool in self._tool_instances.values()]
