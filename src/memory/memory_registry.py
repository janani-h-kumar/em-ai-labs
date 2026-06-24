"""Dynamic memory backend discovery and registration."""

import importlib
import inspect
import logging
import pkgutil
import types
from dataclasses import dataclass

from src.memory.base_memory import BaseMemory

logger = logging.getLogger(__name__)


@dataclass
class MemoryDescriptor:
    """Metadata descriptor for a registered memory backend."""

    name: str
    description: str
    memory_class: type[BaseMemory]
    version: str = "1.0"


class MemoryRegistry:
    """
    Dynamically discovers and registers memory backend classes.

    Responsibilities:
    - Discover memory backend classes
    - Store descriptor metadata (no instances)
    - Provide class lookup for MemoryFactory
    """

    def __init__(self) -> None:
        self.memory_backends: dict[str, MemoryDescriptor | type[BaseMemory]] = {}
        self.discover_memory_backends()

    def discover_memory_backends(self) -> None:
        """Auto-discover all memory backend implementations."""
        import src.memory as memory_package

        logger.info("Discovering memory backends...")

        for _, module_name, _ in pkgutil.iter_modules(memory_package.__path__):
            if module_name in {"base_memory", "memory_factory", "memory_registry"}:
                continue

            module_path = f"src.memory.{module_name}"

            try:
                module = importlib.import_module(module_path)
                self._register_module_memory_backends(module)
            except Exception:
                logger.exception("Failed to import memory module: %s", module_path)

        logger.info("Registered memory backends: %s", list(self.memory_backends.keys()))

    def _register_module_memory_backends(self, module: types.ModuleType) -> None:
        """Register BaseMemory subclasses from a module."""
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, BaseMemory) or obj is BaseMemory:
                continue

            try:
                backend_name = getattr(obj, "name", obj.__name__.replace("Memory", "").lower())
                descriptor = MemoryDescriptor(
                    name=backend_name,
                    description=getattr(obj, "description", ""),
                    memory_class=obj,
                )
                self.memory_backends[backend_name] = descriptor
                logger.info("Registered memory backend: %s -> %s", backend_name, obj.__name__)
            except Exception:
                logger.exception("Failed to register memory backend class: %s", obj.__name__)

    def get_class(self, name: str) -> type[BaseMemory]:
        """Return the memory backend class for the given name."""
        if name not in self.memory_backends:
            raise ValueError(
                f"Memory backend '{name}' not found. Available: {list(self.memory_backends)}"
            )

        descriptor_or_class = self.memory_backends[name]
        if isinstance(descriptor_or_class, MemoryDescriptor):
            return descriptor_or_class.memory_class
        return descriptor_or_class

    def list_backends(self) -> list[str]:
        return list(self.memory_backends.keys())

    def has_backend(self, name: str) -> bool:
        return name in self.memory_backends

    def health_check(self) -> dict[str, dict]:
        """Return a lightweight health map for discovered memory backends."""
        return {
            name: {
                "status": "discovered",
                "class": descriptor.memory_class.__name__
                if isinstance(descriptor, MemoryDescriptor)
                else descriptor.__name__,
            }
            for name, descriptor in self.memory_backends.items()
        }
