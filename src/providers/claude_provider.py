"""Anthropic Claude provider with canonical OpenTelemetry LLM spans."""

from __future__ import annotations

import logging
import time

import anthropic
from opentelemetry import trace as otel_trace

from src.observability.tracing import create_span
from src.providers.base_provider import BaseLLMProvider, HealthStatus

logger = logging.getLogger(__name__)


def _usage_value(usage: object, *names: str) -> int:
    if usage is None:
        return 0
    for name in names:
        try:
            if isinstance(usage, dict):
                value = usage.get(name)
            else:
                value = getattr(usage, name, None)
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    return 0


class ClaudeProvider(BaseLLMProvider):
    def __init__(self, config_manager):
        self._config = config_manager
        self._client = anthropic.Anthropic(
            api_key=config_manager.get("env.anthropic_api_key")
        )
        self._model = config_manager.get("claude.model", "claude-haiku-4-5-20251001")

    def chat_completion(self, messages, system_prompt=None, max_tokens=None):
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

        start_time = time.perf_counter()
        with create_span(
            "llm.call",
            provider="claude",
            model=self._model,
            message_count=len(messages),
            max_tokens=kwargs["max_tokens"],
            has_system_prompt=system_prompt is not None,
            outcome="unknown",
        ) as span:
            try:
                response = self._client.messages.create(**kwargs)
                result = response.content[0].text
                usage = getattr(response, "usage", None)
                input_tokens = _usage_value(usage, "input_tokens", "prompt_tokens")
                output_tokens = _usage_value(usage, "output_tokens", "completion_tokens")
                total_tokens = _usage_value(usage, "total_tokens") or input_tokens + output_tokens
                latency_ms = round((time.perf_counter() - start_time) * 1000, 1)

                span.set_attribute("latency_ms", latency_ms)
                span.set_attribute("input_tokens", input_tokens)
                span.set_attribute("output_tokens", output_tokens)
                span.set_attribute("total_tokens", total_tokens)
                span.set_attribute("prompt_tokens", input_tokens)
                span.set_attribute("completion_tokens", output_tokens)
                span.set_attribute("context_size_tokens", input_tokens)
                span.set_attribute("response_size_bytes", len(result.encode("utf-8")))
                span.set_attribute("outcome", "success")

                logger.info(
                    "Successfully received response from model",
                    extra={
                        "extra_data": {
                            "model_name": self._model,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_tokens": total_tokens,
                            "llm_latency_ms": latency_ms,
                        }
                    },
                )
                return result
            except Exception as exc:
                latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("latency_ms", latency_ms)
                span.set_attribute("outcome", "error")
                span.set_attribute("error.type", type(exc).__name__)
                span.record_exception(exc)
                span.set_status(otel_trace.StatusCode.ERROR, str(exc))
                raise

    def health_check(self) -> HealthStatus:
        try:
            self.chat_completion("ping")
            return HealthStatus(status="healthy", provider="ClaudeProvider")
        except Exception as exc:
            return HealthStatus(status="degraded", provider="ClaudeProvider", error=str(exc))

    @property
    def model_name(self):
        return self._model
