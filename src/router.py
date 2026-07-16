"""
Message router — capability-driven, descriptor-aware.

Accepts AgentDescriptor objects rather than a derived dict[str, list[str]].
This means when AgentDescriptor grows new fields (description, version,
embedding, tags) the router automatically has access to them without any
changes to ApplicationService or the router constructor.

RoutingResult provides richer routing metadata for logging and observability
without requiring downstream callers to do additional registry lookups.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RoutingResult:
    """
    Structured result from a routing decision.

    Richer than tuple[str, float] — carries the matched capabilities so
    the orchestrator and observability layer can log exactly why a message
    was routed to a particular agent, without additional registry lookups.
    When embedding-based routing is added, this is the return type it will
    use as well — the contract stays stable.
    """

    agent_name: str
    confidence: float
    matched_capabilities: list[str] = field(default_factory=list)


class MessageRouter:
    """
    Capability-driven message router.

    Accepts AgentDescriptors and builds keyword patterns from their
    capabilities lists. Falls back to 'general' agent on no match.
    """

    def __init__(self, descriptors: list | None = None) -> None:
        """
        Args:
            descriptors: list[AgentDescriptor] — pass
                agent_registry.descriptors() here. When None, the router has
                no patterns and routes everything to 'general'.
        """
        # agent_name -> list of (keyword, weight) tuples
        self.agent_patterns: dict[str, list[tuple[str, int]]] = {}
        # agent_name -> list of (compiled regex, weight) tuples
        self._compiled_patterns: dict[str, list[tuple[re.Pattern[str], int]]] = {}

        if descriptors:
            self._build_patterns_from_descriptors(descriptors)

    def _build_patterns_from_descriptors(self, descriptors: list) -> None:
        """Build keyword patterns from AgentDescriptor capability lists."""
        for descriptor in descriptors:
            caps = getattr(descriptor, "capabilities", []) or []
            agent_name = getattr(descriptor, "name", "")
            if not agent_name:
                continue
            self.agent_patterns[agent_name] = [(cap.lower(), 10) for cap in caps]

    def route_message(self, message: str) -> RoutingResult:
        """
        Route a message to the best matching agent.

        Returns RoutingResult with agent_name, confidence, and matched capabilities.
        Falls back to 'general' with confidence 0.0 on no match.
        """
        if not message or not message.strip():
            return RoutingResult(agent_name="general", confidence=0.0)

        normalized = message.lower().strip()
        scores: defaultdict[str, float] = defaultdict(float)
        matched: dict[str, list[str]] = defaultdict(list)

        for agent, patterns in self.agent_patterns.items():
            for keyword, weight in patterns:
                if keyword in normalized:
                    scores[agent] += weight
                    matched[agent].append(keyword)

        for agent, cpatterns in self._compiled_patterns.items():
            for regex, weight in cpatterns:
                if regex.search(normalized) is not None:
                    scores[agent] += weight

        if not scores:
            logger.debug("No matching agent found for message=%r — routing to general", message)
            return RoutingResult(agent_name="general", confidence=0.0)

        best_agent = max(scores, key=lambda a: scores[a])
        confidence = min(scores[best_agent] / 20.0, 1.0)

        result = RoutingResult(
            agent_name=best_agent,
            confidence=confidence,
            matched_capabilities=matched.get(best_agent, []),
        )

        logger.debug(
            "Routed to '%s' confidence=%s matched=%s",
            best_agent,
            confidence,
            result.matched_capabilities,
        )
        return result

    def route_task(self, task) -> RoutingResult:
        """Route a Task by its description."""
        return self.route_message(task.description)

    def explain_routing(self, message: str) -> dict[str, Any]:
        """Return a diagnostic breakdown of a routing decision."""
        result = self.route_message(message)
        scores: defaultdict[str, float] = defaultdict(float)
        normalized = message.lower().strip()

        for agent, patterns in self.agent_patterns.items():
            for keyword, weight in patterns:
                if keyword in normalized:
                    scores[agent] += weight

        return {
            "message": message,
            "routed_to": result.agent_name,
            "confidence": result.confidence,
            "matched_capabilities": result.matched_capabilities,
            "total_score": scores[result.agent_name],
            "all_scores": dict(scores),
        }

    def get_available_agents(self) -> list[str]:
        agents = set(self.agent_patterns.keys())
        agents.add("general")
        return sorted(agents)
