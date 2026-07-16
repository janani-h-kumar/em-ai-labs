"""
BaseMemory — abstract contract for all memory backends.

Lifecycle contract:
- get_history()   : retrieve or create session history
- clear()         : clear a single session
- clear_all()     : clear all sessions (e.g. on shutdown or test teardown)
- shutdown()      : release resources (file handles, DB connections, etc.)
                    Called by ServiceContainer on process exit.
"""

from abc import ABC, abstractmethod

from langchain_core.chat_history import InMemoryChatMessageHistory


class BaseMemory(ABC):
    """Abstract contract for conversation/session memory backends."""

    @abstractmethod
    def get_history(self, session_id: str) -> InMemoryChatMessageHistory:
        """Return (or create) the chat history object for a session."""

    @abstractmethod
    def clear(self, session_id: str) -> None:
        """Clear memory for a single session."""

    @abstractmethod
    def clear_all(self) -> None:
        """
        Clear memory for all sessions.

        Required for clean process shutdown and test isolation.
        In-process implementations drop the dict.
        Persistent implementations close cursors and flush buffers.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """
        Release any resources held by this backend.

        Called by ServiceContainer on process exit. Implementations must be
        idempotent — calling shutdown() twice must not raise.
        In-process: no-op. DB-backed: close connection. File-backed: flush and close.
        """
