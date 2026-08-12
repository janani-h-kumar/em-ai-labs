"""
LangChain-based orchestration runtime using a local Ollama LLM with Stateful Multi-Turn Memory.
"""

import concurrent
import concurrent.futures
import logging
import time
from typing import Any

import requests
from opentelemetry import trace as otel_trace
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.tools import Tool
from langchain_ollama import ChatOllama

from src.memory.conversation_memory import (
    BaseMemory,
    InProcessMemory,
)
from src.middleware.retry import retry_with_backoff
from src.observability.tracing import create_span
from src.runtimes.base_runtime import BaseRuntime, RuntimeTelemetry
from src.utils.config_loader import ConfigManager
from src.utils.logging_utils import reset_correlation_id, set_correlation_id

logger = logging.getLogger(__name__)


def _count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    try:
        import tiktoken  # noqa: PLC0415

        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except (ImportError, KeyError):
        return len(text.split())


class LangChainRuntimeError(Exception):
    """Base exception for LangChain runtime errors."""

    pass


class LangChainRuntimeInitError(LangChainRuntimeError):
    """Initialisation error."""

    pass


class LangChainRuntimeExecutionError(LangChainRuntimeError):
    """Runtime execution error."""

    pass


class LangChainRuntime(BaseRuntime):
    INVOKE_TIMEOUT_SECONDS = 120
    agent_executor: RunnableWithMessageHistory | None = None

    def __init__(
        self,
        config_manager: ConfigManager,
        tools: list[Tool] | None = None,
        memory: BaseMemory | None = None,
    ) -> None:
        super().__init__(name="LangChainRuntime")

        try:
            self.config_manager = config_manager

            # ENTERPRISE MEMORY STORE: Partitioned by tracking session IDs
            self.conversational_memory = memory or InProcessMemory()

            ollama_base_url = config_manager.get("env.OLLAMA_BASE_URL", "http://localhost:11434")
            ollama_model = config_manager.get("env.LLM_MODEL", default="qwen3:4b")

            # FIXED G004: Converted to lazy formatting
            logger.info("Initialising ChatOllama with model: %s", ollama_model)
            self.llm = ChatOllama(
                base_url=ollama_base_url,
                model=ollama_model,
                temperature=0.2,
                num_ctx=2048,  # Crucial for multi-turn to prevent context blowout
                # stop=["Observation:", "Human:"],
            )

            self._verify_ollama_connection(ollama_base_url)

            if tools:
                self.set_tools(tools)

            if not self.tools:
                logger.warning("No tools provided; agent executor not initialised.")

            if self.config_manager.get("runtime.warmup_enabled"):
                self._warmup_model()
                # threading.Thread(target=self._warmup_model, daemon=True).start()

        except Exception as e:
            msg = f"Failed to initialise LangChainRuntime: {e}"
            # FIXED G004: Converted to lazy formatting
            logger.error("Failed to initialise LangChainRuntime: %s", e)
            raise LangChainRuntimeInitError(msg) from e

    @retry_with_backoff(
        max_retries=3,
        base_delay=1,
        retryable_exceptions=(requests.Timeout, requests.ConnectionError),
    )
    def _verify_ollama_connection(self, base_url: str) -> None:
        url = base_url.rstrip("/") + "/api/tags"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                raise LangChainRuntimeInitError(f"Ollama returned HTTP {response.status_code}")
            logger.info("Ollama connection verified via /api/tags")
        except Exception as e:
            # FIXED: Corrected the un-prefixed f-string syntax issue from original code safely via lazy logging extraction
            logger.error("Cannot reach Ollama at %s", base_url)
            raise LangChainRuntimeInitError(f"Cannot reach Ollama at {base_url}") from e

    def _warmup_model(self):
        try:
            self.llm.invoke("ping")
            logger.info("Model warmup complete")
        except Exception as e:
            # FIXED G004: Converted to lazy formatting
            logger.warning("Warmup failed: %s", e)

    # -----------------------------------------------------------------------
    # Modern Tool Agent Compiler
    # -----------------------------------------------------------------------
    def _setup_agent(self) -> AgentExecutor:
        # Prompt explicitly reserves a location for conversation tracking
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful enterprise AI assistant. Provide concise, accurate responses. "
                    "Use your allocated tools to look up real-time information when required.",
                ),
                MessagesPlaceholder(variable_name="chat_history"),  # Multi-turn window
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        agent = create_tool_calling_agent(llm=self.llm, tools=self.tools, prompt=prompt)

        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            # verbose=True,
            handle_parsing_errors=True,
            max_execution_time=self.INVOKE_TIMEOUT_SECONDS,
        )

    # -----------------------------------------------------------------------
    # Invoke
    # -----------------------------------------------------------------------
    def invoke(self, message: str, session_id: str = "default-enterprise-session") -> str:
        """Execute one runtime request under an ``agent.run`` span."""
        start_time = time.perf_counter()
        request_id = set_correlation_id()
        model = self.config_manager.get("env.LLM_MODEL", default="llama3.1")
        estimated_context_tokens = _count_tokens(message, model)

        with create_span(
            "agent.run",
            **{
                "agent.name": "langchain_runtime",
                "agent.version": "1.0",
                "execution.id": request_id,
                "session.id": session_id,
                "model": model,
                "context_size_tokens": estimated_context_tokens,
                "outcome": "unknown",
            },
        ) as span:
            try:
                logger.info(
                    "Processing stateful message",
                    extra={"extra_data": {"request_id": request_id, "session_id": session_id}},
                )

                if not self.agent_executor:
                    raise LangChainRuntimeExecutionError("Agent executor not initialised.")

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        self.agent_executor.invoke,
                        {"input": message},
                        config={"configurable": {"session_id": session_id}},
                    )
                    try:
                        result = future.result(timeout=self.INVOKE_TIMEOUT_SECONDS)
                    except concurrent.futures.TimeoutError as exc:
                        raise LangChainRuntimeExecutionError(
                            f"Agent timed out after {self.INVOKE_TIMEOUT_SECONDS} seconds."
                        ) from exc

                response = str(result.get("output", "No response generated."))
                input_tokens = _count_tokens(message, model)
                output_tokens = _count_tokens(response, model)
                total_tokens = input_tokens + output_tokens
                latency_ms = round((time.perf_counter() - start_time) * 1000, 1)

                self.telemetry = RuntimeTelemetry(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                    model=model,
                    context_size_tokens=input_tokens,
                )

                span.set_attribute("input_tokens", input_tokens)
                span.set_attribute("output_tokens", output_tokens)
                span.set_attribute("total_tokens", total_tokens)
                span.set_attribute("context_size_tokens", input_tokens)
                span.set_attribute("latency_ms", latency_ms)
                span.set_attribute("outcome", "success")
                return response

            except Exception as exc:
                latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("latency_ms", latency_ms)
                span.set_attribute("outcome", "error")
                span.set_attribute("error.type", type(exc).__name__)
                span.record_exception(exc)
                span.set_status(otel_trace.StatusCode.ERROR, str(exc))
                logger.error(
                    "Runtime execution failed: %s",
                    exc,
                    extra={"extra_data": {"request_id": request_id}},
                )
                raise LangChainRuntimeExecutionError(f"Failed to execute: {exc}") from exc
            finally:
                reset_correlation_id()

    def _get_session_history(
        self,
        session_id: str,
    ) -> InMemoryChatMessageHistory:
        """Return session chat history."""
        return self.conversational_memory.get_history(session_id)

    def set_tools(self, tools: list[Tool]) -> None:
        super().set_tools(tools)

        if tools:
            raw_executor = self._setup_agent()

            # ENTERPRISE DESIGN PATTERN: Wrap the raw Agent Executor inside a
            # Message History orchestration wrapper to automate history appending.
            self.agent_executor = RunnableWithMessageHistory(
                runnable=raw_executor,
                get_session_history=self._get_session_history,
                input_messages_key="input",
                history_messages_key="chat_history",
                output_messages_key="output",  # Crucial: tells history engine which key to read
            )
        else:
            self.agent_executor = None

    def health_check(self) -> dict[str, Any]:
        ollama_base_url = self.config_manager.get("env.OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            resp = requests.get(ollama_base_url.rstrip("/") + "/api/tags", timeout=3)
            ollama_status = "up" if resp.status_code == 200 else "degraded"
        except Exception:
            ollama_status = "down"

        return {
            "runtime": self.name,
            "status": "healthy" if ollama_status == "up" else "degraded",
            "ollama": ollama_status,
            # "active_sessions": len(self.conversational_memory.list_sessions),
            "agent_executor_initialized": self.agent_executor is not None,
        }
