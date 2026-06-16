"""
General fallback agent for unanswered or unscored requests.
"""

import logging

from src.agents.base_agent import AgentInitError, BaseAgent
from src.providers.base_provider import BaseLLMProvider
from src.utils.config_loader import ConfigManager

logger = logging.getLogger(__name__)


class GeneralAgent(BaseAgent):
    """Generic assistant for fallback routing when no specific agent matches."""

    name = "general"
    description = "Fallback general-purpose assistant"
    capabilities = ["general", "fallback", "assistant"]

    def __init__(
        self,
        config_manager: ConfigManager,
        base_llm_provider: BaseLLMProvider,
    ) -> None:
        self.base_llm_provider = base_llm_provider
        super().__init__(config_manager)

    def initialize(self) -> None:
        if self.base_llm_provider is None:
            raise AgentInitError("base_llm_provider is required")

        self.system_prompt = (
            "You are a helpful assistant. Respond succinctly and clearly to general user requests."
        )

        logger.info("GeneralAgent initialized successfully")

    async def handle(self, task, context):
        prompt = task.description
        try:
            response = self.base_llm_provider.chat_completion(
                prompt,
                system_prompt=self.system_prompt,
            )
            return str(response)
        except Exception:
            logger.exception("GeneralAgent failed to generate response")
            return "Sorry, I couldn't process that request right now."
