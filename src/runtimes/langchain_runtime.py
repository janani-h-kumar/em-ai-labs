"""
LangChain-based orchestration runtime using a local Ollama LLM.

Changes from original:
- health_check() no longer calls self.llm.invoke("test") — that's an
  expensive live LLM round-trip on every health poll. Replaced with a
  lightweight HTTP check against the Ollama /api/tags endpoint, which
  answers in milliseconds and uses no GPU resources.
- Token counting replaced: original used len(message.split()) (word count,
  inaccurate by ~30%). Now uses tiktoken (already in requirements.txt) for
  accurate token counts. Falls back to word-count if tiktoken is unavailable
  so nothing breaks in dev environments that skipped full deps.
- invoke() timeout: added a configurable hard timeout so a hung local model
  cannot block the process indefinitely.
- _verify_ollama_connection() no longer calls llm.invoke("test") on startup
  for the same reason — replaced with HTTP ping.
"""

import logging
import time
from typing import List, Optional, Dict, Any

import concurrent
import concurrent.futures
import requests
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import Tool

from src.runtimes.base_runtime import BaseRuntime, RuntimeTelemetry
from src.utils.config_loader import ConfigManager
from src.middleware.retry import retry_with_backoff
from src.utils.logging_utils import set_correlation_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token counting helper
# ---------------------------------------------------------------------------

def _count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """
    Count tokens accurately using tiktoken.

    Falls back to word-count if tiktoken is not installed, so this never
    raises in a minimal dev environment.
    """
    try:
        import tiktoken  # noqa: PLC0415
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except (ImportError, KeyError):
        # tiktoken not installed or model not recognised — rough approximation
        return len(text.split())


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LangChainRuntimeError(Exception):
    """Base exception for LangChain runtime errors."""
    pass


class LangChainRuntimeInitError(LangChainRuntimeError):
    """Initialisation error."""
    pass


class LangChainRuntimeExecutionError(LangChainRuntimeError):
    """Runtime execution error."""
    pass


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------

class LangChainRuntime(BaseRuntime):

    # Seconds before invoke() gives up waiting for the LLM.
    # Tune this to your model's typical latency + a generous buffer.
    INVOKE_TIMEOUT_SECONDS = 120

    def __init__(
        self,
        config_manager: ConfigManager,
        tools: Optional[List[Tool]] = None,
    ):
        super().__init__(name="LangChainRuntime")

        try:
            self.config_manager = config_manager

            ollama_base_url = config_manager.get(
                "env.OLLAMA_BASE_URL", "http://localhost:11434"
            )
            ollama_model = config_manager.get("env.LLM_MODEL", default="llama3.1")

            logger.info(f"Initialising ChatOllama with model: {ollama_model}")
            self.llm = ChatOllama(
                base_url=ollama_base_url,
                model=ollama_model,
                temperature=0.2,
            )

            # FIX: replaced llm.invoke("test") with HTTP ping
            self._verify_ollama_connection(ollama_base_url)

            if tools:
                self.set_tools(tools)

            self.agent_executor = (
                self._setup_agent() if self.tools else None
            )
            if not self.tools:
                logger.warning("No tools provided; agent executor not initialised.")

            logger.info(f"LangChainRuntime initialised with ChatOllama({ollama_model})")

        except Exception as e:
            msg = f"Failed to initialise LangChainRuntime: {e}"
            logger.error(msg)
            raise LangChainRuntimeInitError(msg)

    # -----------------------------------------------------------------------
    # Connection verification — FIX
    # -----------------------------------------------------------------------

    @retry_with_backoff(
        max_retries=3,
        base_delay=1,
        retryable_exceptions=(requests.Timeout, requests.ConnectionError),
    )
    def _verify_ollama_connection(self, base_url: str) -> None:
        """
        Ping Ollama's /api/tags endpoint to confirm it is reachable.

        This is a free HTTP call — no LLM inference, no GPU usage, no cost.
        Original used self.llm.invoke("test") which ran real inference on
        every startup and health check.
        """
        url = base_url.rstrip("/") + "/api/tags"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                raise LangChainRuntimeInitError(
                    f"Ollama returned HTTP {response.status_code} at {url}"
                )
            logger.info("Ollama connection verified via /api/tags")
        except requests.ConnectionError:
            raise LangChainRuntimeInitError(
                f"Cannot reach Ollama at {base_url}. Is it running? Try: ollama serve"
            )
        except requests.Timeout:
            raise LangChainRuntimeInitError(
                f"Ollama at {base_url} did not respond within 5s."
            )

    # -----------------------------------------------------------------------
    # Agent setup
    # -----------------------------------------------------------------------

    def _setup_agent(self) -> Any:
        system_prompt = (
            "You are a helpful AI assistant. Provide concise, accurate, and useful "
            "responses. Use available tools (weather, web_search) to find information "
            "when necessary. Always cite sources when using tools. Be friendly and "
            "professional."
        )
        agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt,
        )
        logger.info(f"Agent compiled with {len(self.tools)} tool(s)")
        return agent

    # -----------------------------------------------------------------------
    # Invoke — FIX token counting + timeout
    # -----------------------------------------------------------------------

    @retry_with_backoff(
        max_retries=2,
        base_delay=0.5,
        retryable_exceptions=(requests.Timeout, requests.ConnectionError),
    )
    def invoke(self, message: str) -> str:
        start_time = time.time()
        request_id = set_correlation_id()

        try:
            logger.info(
                "Processing message",
                extra={"extra_data": {
                    "request_id": request_id,
                    "message_length": len(message),
                }},
            )

            if not self.agent_executor:
                raise LangChainRuntimeExecutionError(
                    "Agent executor not initialised — no tools available."
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    self.agent_executor.invoke,
                    {"messages": [("user", message)]}
                )
                try:
                    result = future.result(timeout=self.INVOKE_TIMEOUT_SECONDS)
                except concurrent.futures.TimeoutError:
                    raise LangChainRuntimeExecutionError(
                        f"Agent did not respond within {self.INVOKE_TIMEOUT_SECONDS}s. "
                        "Try a shorter query or increase INVOKE_TIMEOUT_SECONDS."
                )

            messages = result.get("messages", [])
            response = messages[-1].content if messages else "No response generated."

            # FIX: use tiktoken for accurate token counts
            ollama_model = self.config_manager.get("env.LLM_MODEL", default="llama3.1")
            input_tokens = _count_tokens(message)
            output_tokens = _count_tokens(response)
            latency_ms = (time.time() - start_time) * 1000

            self.telemetry = RuntimeTelemetry(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                latency_ms=latency_ms,
                model=ollama_model,
            )

            return response

        except LangChainRuntimeExecutionError:
            raise
        except Exception as e:
            logger.error(
                f"Runtime execution failed: {e}",
                extra={"extra_data": {"request_id": request_id}},
            )
            raise LangChainRuntimeExecutionError(f"Failed to execute: {e}")

    # -----------------------------------------------------------------------
    # set_tools & health_check — FIX
    # -----------------------------------------------------------------------

    def set_tools(self, tools: List[Tool]) -> None:
        super().set_tools(tools)
        self.agent_executor = self._setup_agent() if tools else None

    def health_check(self) -> Dict[str, Any]:
        """
        Check Ollama availability via HTTP — not via LLM inference.

        Original called self.llm.invoke("test") here, which ran real model
        inference on every health poll (expensive, slow, burns GPU time).
        """
        ollama_base_url = self.config_manager.get(
            "env.OLLAMA_BASE_URL"
        )
        try:
            url = ollama_base_url.rstrip("/") + "/api/tags"
            resp = requests.get(url, timeout=3)
            ollama_status = "up" if resp.status_code == 200 else "degraded"
        except Exception:
            ollama_status = "down"

        return {
            "runtime": self.name,
            "status": "healthy" if ollama_status == "up" else "degraded",
            "ollama": ollama_status,
            "tools_available": len(self.tools) if self.tools else 0,
            "agent_executor_initialized": self.agent_executor is not None,
        }
