"""
LangChain-based orchestration runtime using Ollama LLM.

This runtime combines LangChain's agent framework with a local Ollama LLM
to provide intelligent tool orchestration for agents.
"""

import logging
import time
from typing import List, Optional, Dict, Any

#  UPDATED: Use the modern React Agent creator from the new package
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from src.runtimes.base_runtime import BaseRuntime, RuntimeTelemetry
from src.utils.config_loader import ConfigManager
from src.middleware.retry import retry_with_backoff
from src.utils.logging_utils import set_correlation_id
from langchain_core.tools import Tool

logger = logging.getLogger(__name__)


class LangChainRuntimeError(Exception):
    """Base exception for LangChain runtime errors."""
    pass


class LangChainRuntimeInitError(LangChainRuntimeError):
    """Initialization error."""
    pass


class LangChainRuntimeExecutionError(LangChainRuntimeError):
    """Runtime execution error."""
    pass


class LangChainRuntime(BaseRuntime):
    
    def __init__(
        self,
        config_manager: ConfigManager,
        tools: Optional[List[Tool]] = None
    ):
        super().__init__(name="LangChainRuntime")
        
        try:
            self.config_manager = config_manager
            
            #  FIX 1: Use ChatOllama for conversational agent state management
            ollama_base_url = config_manager.get("env.OLLAMA_BASE_URL", "http://localhost:11434")
            ollama_model = config_manager.get("env.LLM_MODEL", default="llama3.1")
            
            logger.info(f"Initializing ChatOllama with model: {ollama_model}")
            self.llm = ChatOllama(
                base_url=ollama_base_url,
                model=ollama_model,
                temperature=0.2
            )
            
            # Verify Ollama connection
            self._verify_ollama_connection()
            
            # Setup agent if tools are provided
            if tools:
                self.set_tools(tools)

            if self.tools:
                self.agent_executor = self._setup_agent()
            else:
                self.agent_executor = None
                logger.warning("No tools provided; agent will not be initialized")
            
            logger.info(f"✅ LangChainRuntime initialized with ChatOllama({ollama_model})")
            
        except Exception as e:
            error_msg = f"Failed to initialize LangChainRuntime: {e}"
            logger.error(error_msg)
            raise LangChainRuntimeInitError(error_msg)
    
    @retry_with_backoff(max_retries=3, base_delay=1)
    def _verify_ollama_connection(self) -> None:
        try:
            self.llm.invoke("test")
            logger.info("✅ Ollama connection verified")
        except Exception as e:
            raise LangChainRuntimeInitError(
                f"Cannot connect to Ollama. Ensure it's running at "
                f"{self.config_manager.get('env.OLLAMA_BASE_URL')}: {e}"
            )
    
    def _setup_agent(self) -> Any:
        """Setup compiled LangGraph ReAct agent with tools."""
        system_prompt = self._build_system_prompt()

        #  FIX: Changed state_modifier= to prompt=
        agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt,
        )

        logger.info(f"Agent compiled with {len(self.tools)} tools")
        return agent
    
    def _build_system_prompt(self) -> str:
        return (
            "You are a helpful AI assistant. Provide concise, accurate, and useful responses. "
            "Use available tools (weather, web_search) to find information when necessary. "
            "Always cite sources when using tools. Be friendly and professional."
        )
    
    @retry_with_backoff(max_retries=2, base_delay=0.5)
    def invoke(self, message: str) -> str:
        start_time = time.time()
        request_id = set_correlation_id()
        
        try:
            logger.info(
                f"Processing message",
                extra={"extra_data": {
                    "request_id": request_id,
                    "message_length": len(message)
                }}
            )
            
            if not self.agent_executor:
                raise LangChainRuntimeExecutionError(
                    "Agent executor not initialized. No tools available."
                )
            
            #  FIX 3: Wrap input message into a structured LangGraph message state dictionary
            # Passing a dictionary prevents the INVALID_GRAPH_NODE_RETURN_VALUE error!
            result = self.agent_executor.invoke({"messages": [("user", message)]})
            
            #  FIX 4: Safely extract the last message content returned from the compiled state graph
            messages = result.get("messages", [])
            if messages:
                response = messages[-1].content
            else:
                response = "No response generated by the agent graph state."
            
            # Calculate telemetry
            input_tokens = len(message.split())
            output_tokens = len(response.split())
            latency_ms = (time.time() - start_time) * 1000
            
            self.telemetry = RuntimeTelemetry(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                latency_ms=latency_ms,
                model=self.config_manager.get("env.LLM_MODEL", default="llama3.1")
            )
            
            return response
        
        except Exception as e:
            logger.error(f"Runtime execution failed: {e}", extra={"extra_data": {"request_id": request_id}})
            raise LangChainRuntimeExecutionError(f"Failed to execute: {e}")
    
    def set_tools(self, tools: List[Tool]) -> None:
        super().set_tools(tools)
        if tools:
            self.agent_executor = self._setup_agent()
        else:
            self.agent_executor = None
    
    def health_check(self) -> Dict[str, Any]:
        try:
            self.llm.invoke("test")
            ollama_status = "up"
        except:
            ollama_status = "down"
        
        return {
            "runtime": self.name,
            "status": "healthy" if ollama_status == "up" else "degraded",
            "ollama": ollama_status,
            "tools_available": len(self.tools) if self.tools else 0,
            "agent_executor_initialized": self.agent_executor is not None,
        }