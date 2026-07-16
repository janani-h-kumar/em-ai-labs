"""
InProcessMemory — in-process session memory backend.

Satisfies the full BaseMemory lifecycle contract including clear_all()
and shutdown(). Appropriate for local dev, tests, and single-process
deployments. All state is lost on process restart.
"""

from langchain_core.chat_history import InMemoryChatMessageHistory

from src.memory.base_memory import BaseMemory


class InProcessMemory(BaseMemory):
    """In-process memory backend for short-lived session state."""

    name = "memory"
    description = "In-process session memory backend"

    def __init__(self) -> None:
        self._history_store: dict[str, InMemoryChatMessageHistory] = {}
        self._shutdown_called: bool = False

    def get_history(self, session_id: str) -> InMemoryChatMessageHistory:
        """Return or create the chat history for a session."""
        if session_id not in self._history_store:
            self._history_store[session_id] = InMemoryChatMessageHistory()
        return self._history_store[session_id]

    def clear(self, session_id: str) -> None:
        """Clear memory for a single session."""
        self._history_store.pop(session_id, None)

    def clear_all(self) -> None:
        """Clear memory for all sessions. Used in tests and on shutdown."""
        self._history_store.clear()

    def shutdown(self) -> None:
        """
        Release resources. Idempotent.

        For InProcessMemory this clears the history store and sets a flag
        so subsequent calls are no-ops. More important for DB-backed
        implementations that must close connections cleanly.
        """
        if not self._shutdown_called:
            self.clear_all()
            self._shutdown_called = True
