import logging
import re
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class MessageRouter:
    """
    Intelligent message router with weighted keyword and regex scoring.

    Features:
    - Keyword-based routing
    - Regex-based routing
    - Confidence scoring
    - Routing explanations
    - Fallback support
    """

    def __init__(self, agent_capabilities: dict[str, list[str]] | None = None) -> None:
        """If `agent_capabilities` is provided, build keyword patterns from it.

        `agent_capabilities` should be a mapping: agent_name -> list of capability keywords.
        """
        self.agent_patterns: dict[str, list[tuple[str, int]]] = {}
        self.regex_patterns: dict[str, list[tuple[re.Pattern[str], int]]] = {}

        if agent_capabilities:
            self._build_patterns_from_capabilities(agent_capabilities)
        else:
            self._setup_patterns()

    def _setup_patterns(self) -> None:
        """Initialize routing patterns."""
        # No default patterns — router should be driven by agent metadata
        self.agent_patterns = {}
        self.regex_patterns = {}

    def _build_patterns_from_capabilities(self, agent_capabilities: dict[str, list[str]]) -> None:
        """Create keyword patterns from agent capabilities mapping."""
        for agent, caps in agent_capabilities.items():
            patterns = []
            for cap in caps:
                # default weight 10 for capability keywords
                patterns.append((cap.lower(), 10))

            self.agent_patterns[agent] = patterns

    def route_message(self, message: str) -> tuple[str, float]:
        """
        Route a message to the best matching agent.

        Args:
            message: User message

        Returns:
            tuple[str, float]:
                agent name and confidence score
        """
        if not message or not message.strip():
            return "general", 0.0

        normalized_message = message.lower().strip()
        scores: defaultdict[str, float] = defaultdict(float)

        self._score_keywords(normalized_message, scores)
        self._score_regex_patterns(normalized_message, scores)

        if not scores:
            logger.debug(
                "No matching agent found for message='%s'",
                message,
            )
            return "general", 0.0

        best_agent = max(scores, key=lambda agent: scores[agent])
        confidence = min(scores[best_agent] / 20.0, 1.0)

        logger.debug(
            "Message routed to '%s' with confidence %s",
            best_agent,
            confidence,
        )

        return best_agent, confidence

    def _score_keywords(
        self,
        message: str,
        scores: defaultdict[str, float],
    ) -> None:
        """Apply keyword scoring."""

        for agent, patterns in self.agent_patterns.items():
            for keyword, weight in patterns:
                if keyword in message:
                    scores[agent] += weight

    def _score_regex_patterns(
        self,
        message: str,
        scores: defaultdict[str, float],
    ) -> None:
        """Apply regex scoring."""

        for agent, patterns in self.regex_patterns.items():
            for regex, weight in patterns:
                if regex.search(message):
                    scores[agent] += weight

    def get_available_agents(self) -> list[str]:
        """
        Return available agent names.
        """
        agents = set(self.agent_patterns.keys())
        agents.add("general")

        return sorted(agents)

    def explain_routing(self, message: str) -> dict[str, Any]:
        """
        Explain routing decision.

        Args:
            message: User message

        Returns:
            dict[str, Any]: Explanation metadata
        """
        routed_agent, confidence = self.route_message(message)

        scores: defaultdict[str, float] = defaultdict(float)
        matched_keywords: list[tuple[str, int]] = []

        normalized_message = message.lower().strip()

        for agent, patterns in self.agent_patterns.items():
            for keyword, weight in patterns:
                if keyword in normalized_message:
                    scores[agent] += weight

                    if agent == routed_agent:
                        matched_keywords.append((keyword, weight))

        return {
            "message": message,
            "routed_to": routed_agent,
            "confidence": confidence,
            "matched_keywords": matched_keywords,
            "total_score": scores[routed_agent],
            "all_scores": dict(scores),
        }

    def route_task(self, task):
        return self.route_message(task.description)


# Global singleton router instance
_router = MessageRouter()


class Router(MessageRouter):
    pass
