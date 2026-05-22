import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


class MessageRouter:
    """
    Intelligent message router with pattern matching and scoring

    Features:
    - Keyword-based routing with weights
    - Regular expression patterns
    - Context-aware routing
    - Confidence scoring
    - Fallback handling
    """

    def __init__(self):
        """Initialize router with agent patterns"""
        self.agent_patterns: dict[str, list[tuple[str, int]]] = {}
        self.regex_patterns: dict[str, list[tuple[re.Pattern, int]]] = {}
        self._setup_patterns()

    def _setup_patterns(self) -> None:
        """Setup routing patterns for each agent"""

        # Weather Agent Patterns
        self.agent_patterns["weather"] = [
            # High confidence keywords
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
            # City/location indicators
            ("in ", 3),
            ("at ", 3),
            ("for ", 3),
            # Question patterns
            ("what's the weather", 12),
            ("how's the weather", 12),
            ("is it", 4),
            ("will it", 4),
        ]

        # Science Agent Patterns (future)
        self.agent_patterns["science"] = [
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
        ]

        # Setup regex patterns for more complex matching
        self.regex_patterns["weather"] = [
            # City extraction patterns
            (re.compile(r"weather (?:in|for|at) (\w+)", re.IGNORECASE), 15),
            (
                re.compile(
                    r"(?:what\'s|how\'s) (?:the )?weather (?:like )?(?:in )?(\w+)", re.IGNORECASE
                ),
                20,
            ),
            # Temperature questions
            (re.compile(r"(?:how|what) (?:hot|cold) (?:is it|will it be)", re.IGNORECASE), 12),
        ]

    def route_message(self, message: str) -> tuple[str, float]:
        """
        Route message to appropriate agent with confidence score

        Args:
            message: User input message

        Returns:
            tuple: (agent_name, confidence_score)
        """
        if not message or not message.strip():
            return "general", 0.0

        message = message.lower().strip()
        scores = defaultdict(float)

        # Score based on keyword patterns
        for agent, patterns in self.agent_patterns.items():
            for keyword, weight in patterns:
                if keyword in message:
                    scores[agent] += weight

        # Score based on regex patterns
        for agent, patterns in self.regex_patterns.items():
            for regex, weight in patterns:
                if regex.search(message):
                    scores[agent] += weight

        # Find highest scoring agent
        if scores:
            best_agent = max(scores, key=scores.get)
            confidence = min(scores[best_agent] / 20.0, 1.0)  # Normalize to 0-1

            logger.debug("Routed '%s' to %s (confidence: %.2f)", message, best_agent, confidence)
            return best_agent, confidence

        # Default fallback
        logger.debug("No matching agent for '%s', using general", message)
        return "general", 0.0

    def get_available_agents(self) -> list[str]:
        """
        Get list of available agents

        Returns:
            list: Agent names
        """
        return list(self.agent_patterns.keys()) + ["general"]

    def explain_routing(self, message: str) -> dict[str, any]:
        """
        Explain why a message was routed to a particular agent

        Args:
            message: User input message

        Returns:
            dict: Routing explanation
        """
        agent, confidence = self.route_message(message)
        scores = defaultdict(float)

        # Calculate detailed scores
        message_lower = message.lower()
        matched_keywords = []

        for agent_name, patterns in self.agent_patterns.items():
            for keyword, weight in patterns:
                if keyword in message_lower:
                    scores[agent_name] += weight
                    if agent_name == agent:
                        matched_keywords.append((keyword, weight))

        return {
            "message": message,
            "routed_to": agent,
            "confidence": confidence,
            "matched_keywords": matched_keywords,
            "total_score": scores[agent],
            "all_scores": dict(scores),
        }


# Global router instance
_router = MessageRouter()


def route_message(message: str) -> str:
    """
    Route message to appropriate agent (backward compatibility)

    Args:
        message: User input message

    Returns:
        str: Agent name
    """
    agent, _ = _router.route_message(message)
    return agent


def get_router() -> MessageRouter:
    """
    Get the global router instance

    Returns:
        MessageRouter: Router instance
    """
    return _router
