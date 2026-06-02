# src/memory/base_memory.py

from abc import ABC, abstractmethod

from langchain_core.chat_history import InMemoryChatMessageHistory


class BaseMemory(ABC):
    """
    Abstract contract for conversation/session memory.
    """

    @abstractmethod
    def get_history(self, session_id: str) -> InMemoryChatMessageHistory:
        """
        Return chat history object for a session.
        """

    @abstractmethod
    def clear(self, session_id: str) -> None:
        """
        Clear memory for a session.
        """
