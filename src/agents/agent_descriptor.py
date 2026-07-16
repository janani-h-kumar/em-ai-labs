"""
AgentDescriptor — lightweight metadata model for registered agents.

Lives in its own module so it can be imported by the router, registry,
and tests without pulling in the full ServiceContainer dependency chain.
"""

from dataclasses import dataclass, field


@dataclass
class AgentDescriptor:
    """Metadata descriptor for a registered agent."""

    name: str
    description: str
    capabilities: list[str]
    agent_class: type  # type[BaseAgent] — avoid import cycle
    version: str = "1.0"
    tags: list[str] = field(default_factory=list)
