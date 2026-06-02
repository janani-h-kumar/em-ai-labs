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

    def __init__(self) -> None:
        self.agent_patterns: dict[str, list[tuple[str, int]]] = {}
        self.regex_patterns: dict[str, list[tuple[re.Pattern[str], int]]] = {}

        self._setup_patterns()

    def _setup_patterns(self) -> None:
        """Initialize routing patterns."""

        self.agent_patterns = {
            "weather_agent": [
                ("weather", 10),
                ("temperature", 10),
                ("forecast", 10),
                ("rain", 8),
                ("snow", 8),
                ("storm", 8),
                ("humidity", 7),
                ("hot", 6),
                ("cold", 6),
                ("sunny", 6),
                ("cloudy", 6),
                ("wind", 6),
                ("climate", 5),
                ("degrees", 5),
                ("what's the weather", 12),
                ("how's the weather", 12),
                ("is it", 4),
                ("will it", 4),
            ],
            "science": [
                ("why", 8),
                ("how does", 10),
                ("what is", 6),
                ("science", 8),
                ("physics", 7),
                ("chemistry", 7),
                ("biology", 7),
                ("space", 6),
                ("universe", 6),
                ("earth", 5),
                ("experiment", 6),
                ("theory", 5),
            ],
        }

        self.regex_patterns = {
            "weather_client": [
                (
                    re.compile(
                        r"weather (?:in|for|at) ([a-zA-Z\s]+)",
                        re.IGNORECASE,
                    ),
                    15,
                ),
                (
                    re.compile(
                        r"(?:what's|how's) "
                        r"(?:the )?weather "
                        r"(?:like )?"
                        r"(?:in )?([a-zA-Z\s]+)",
                        re.IGNORECASE,
                    ),
                    20,
                ),
                (
                    re.compile(
                        r"(?:how|what) "
                        r"(?:hot|cold) "
                        r"(?:is it|will it be)",
                        re.IGNORECASE,
                    ),
                    12,
                ),
            ]
        }

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

        best_agent = max(scores, key=lambda scores: len(scores))
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
