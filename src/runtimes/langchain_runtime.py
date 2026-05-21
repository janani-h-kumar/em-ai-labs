"""
LangChain-based orchestration runtime using a local Ollama LLM with Stateful Multi-Turn Memory.
"""

import logging
import threading
import time
from typing import List, Optional, Dict, Any

import concurrent
import concurrent.futures
import requests
from langchain_ollama import ChatOllama
from langchain_core.tools import Tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory

from src.runtimes.base_runtime import BaseRuntime, RuntimeTelemetry
from src.utils.config_loader import ConfigManager
from src.middleware.retry import retry_with_backoff
from src.utils.logging_utils import set_correlation_id

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
    
    def __init__(
        self,
        config_manager: ConfigManager,
        tools: Optional[List[Tool]] = None,
    ):
        super().__init__(name="LangChainRuntime")

        try:
            self.config_manager = config_manager
            
            # ENTERPRISE MEMORY STORE: Partitioned by tracking session IDs
            self._history_store: Dict[str, InMemoryChatMessageHistory] = {}

            ollama_base_url = config_manager.get("env.OLLAMA_BASE_URL", "http://localhost:11434")
            ollama_model = config_manager.get("env.LLM_MODEL", default="llama3.1")

            logger.info(f"Initialising ChatOllama with model: {ollama_model}")
            self.llm = ChatOllama(
                base_url=ollama_base_url,
                model=ollama_model,
                temperature=0.2,
                num_ctx=2048,           # Crucial for multi-turn to prevent context blowout
                # stop=["Observation:", "Human:"],                
            )

            self._verify_ollama_connection(ollama_base_url)

            if tools:
                self.set_tools(tools)

            if not self.tools:
                logger.warning("No tools provided; agent executor not initialised.")

            if self.config_manager.get("runtime.warmup_enabled"):
                self._warmup_model()
                #threading.Thread(target=self._warmup_model, daemon=True).start()

        except Exception as e:
            msg = f"Failed to initialise LangChainRuntime: {e}"
            logger.error(msg)
            raise LangChainRuntimeInitError(msg)

    @retry_with_backoff(max_retries=3, base_delay=1, retryable_exceptions=(requests.Timeout, requests.ConnectionError))
    def _verify_ollama_connection(self, base_url: str) -> None:
        url = base_url.rstrip("/") + "/api/tags"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                raise LangChainRuntimeInitError(f"Ollama returned HTTP {response.status_code}")
            logger.info("Ollama connection verified via /api/tags")
        except Exception as e:
            raise LangChainRuntimeInitError(f"Cannot reach Ollama at {base_url}: {e}")

    def _warmup_model(self):
        try:
            self.llm.invoke("ping")
            logger.info("Model warmup complete")
        except Exception as e:
            logger.warning(f"Warmup failed: {e}")

    # -----------------------------------------------------------------------
    # Stateful Memory Helper
    # -----------------------------------------------------------------------
    def _get_session_history(self, session_id: str) -> InMemoryChatMessageHistory:
        """Retrieves or spins up an isolated chat history stack for a session."""
        if session_id not in self._history_store:
            self._history_store[session_id] = InMemoryChatMessageHistory()
        return self._history_store[session_id]

    # -----------------------------------------------------------------------
    # Modern Tool Agent Compiler
    # -----------------------------------------------------------------------
    def _setup_agent(self) -> AgentExecutor:
        # Prompt explicitly reserves a location for conversation tracking
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a helpful enterprise AI assistant. Provide concise, accurate responses. "
                "Use your allocated tools to look up real-time information when required."
            ),
            MessagesPlaceholder(variable_name="chat_history"), # Multi-turn window
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(llm=self.llm, tools=self.tools, prompt=prompt)
        
        return AgentExecutor(
            agent=agent, 
            tools=self.tools, 
            # verbose=True,
            handle_parsing_errors=True,
            max_execution_time=self.INVOKE_TIMEOUT_SECONDS
        )

    # -----------------------------------------------------------------------
    # Invoke
    # -----------------------------------------------------------------------
    def invoke(self, message: str, session_id: str = "default-enterprise-session") -> str:
        """
        Executes an orchestration turn. Accepts an optional session_id parameter 
        to isolate multi-turn context between distinct users or workflows.
        """
        start_time = time.time()
        request_id = set_correlation_id()

        try:
            logger.info(
                "Processing stateful message",
                extra={"extra_data": {"request_id": request_id, "session_id": session_id}},
            )

            if not self.agent_executor:
                raise LangChainRuntimeExecutionError("Agent executor not initialised.")

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                # Execute against the stateful wrapper wrapper
                future = executor.submit(
                    self.agent_executor.invoke,
                    {"input": message},
                    config={"configurable": {"session_id": session_id}} # Dictates the memory workspace
                )
                try:
                    result = future.result(timeout=self.INVOKE_TIMEOUT_SECONDS)
                except concurrent.futures.TimeoutError:
                    raise LangChainRuntimeExecutionError(f"Agent timed out after {self.INVOKE_TIMEOUT_SECONDS}s.")

            response = result.get("output", "No response generated.")

            # Telemetry processing
            ollama_model = self.config_manager.get("env.LLM_MODEL", default="llama3.1")
            input_tokens = _count_tokens(message)
            output_tokens = _count_tokens(response)
            
            self.telemetry = RuntimeTelemetry(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                latency_ms=(time.time() - start_time) * 1000,
                model=ollama_model,
            )

            return response

        except Exception as e:
            logger.error(f"Runtime execution failed: {e}", extra={"extra_data": {"request_id": request_id}})
            raise LangChainRuntimeExecutionError(f"Failed to execute: {e}")

    def set_tools(self, tools: List[Tool]) -> None:
        super().set_tools(tools)
        setup_agent_duration = time.perf_counter()
        
        if tools:
            raw_executor = self._setup_agent()
            
            # ENTERPRISE DESIGN PATTERN: Wrap the raw Agent Executor inside a 
            # Message History orchestration wrapper to automate history appending.
            self.agent_executor = RunnableWithMessageHistory(
                runnable=raw_executor,
                get_session_history=self._get_session_history,
                input_messages_key="input",
                history_messages_key="chat_history",
                output_messages_key="output", # Crucial: tells history engine which key to read
            )
        else:
            self.agent_executor = None

    def health_check(self) -> Dict[str, Any]:
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
            "active_sessions": len(self._history_store),
            "agent_executor_initialized": self.agent_executor is not None,
        }