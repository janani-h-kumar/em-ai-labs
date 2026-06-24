import anthropic

from src.providers.base_provider import BaseLLMProvider, HealthStatus


class ClaudeProvider(BaseLLMProvider):
    def __init__(self, config_manager):
        self._config = config_manager
        self._client = anthropic.Anthropic(api_key=config_manager.get("env.anthropic_api_key"))
        self._model = config_manager.get("claude.model", "claude-haiku-4-5-20251001")

    def chat_completion(self, messages, system_prompt=None, max_tokens=None):
        # Normalise plain string → list
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        kwargs = dict(
            model=self._model,
            max_tokens=max_tokens
            if max_tokens is not None
            else self._config.get("claude.max_tokens", 1000),
            messages=messages,
        )
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self._client.messages.create(**kwargs)
        result = response.content[0].text

        token_usage = getattr(response, "usage", None)
        prompt_tokens = completion_tokens = total_tokens = 0
        if token_usage is not None:
            try:
                prompt_tokens = int(token_usage.get("prompt_tokens", 0))
                completion_tokens = int(token_usage.get("completion_tokens", 0))
                total_tokens = int(token_usage.get("total_tokens", 0))
            except Exception:
                prompt_tokens = completion_tokens = total_tokens = 0

        logger.info(
            "Successfully received response from model",
            extra={
                "extra_data": {
                    "model_name": self._model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                }
            },
        )

        return result

    def health_check(self) -> HealthStatus:
        try:
            self.chat_completion("ping")
            return HealthStatus(status="healthy", provider="ClaudeProvider")
        except Exception as e:
            return HealthStatus(status="degraded", provider="ClaudeProvider", error=str(e))

    @property
    def model_name(self):
        return self._model
