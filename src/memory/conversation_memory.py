# src/memory/conversation_memory.py


from langchain_core.chat_history import InMemoryChatMessageHistory

from src.memory.base_memory import BaseMemory


class InProcessMemory(BaseMemory):
    """In-process memory backend for short-lived session state."""

    name = "memory"
    description = "In-process session memory backend"

    def __init__(self) -> None:
        self._history_store: dict[str, InMemoryChatMessageHistory] = {}

    def get_history(self, session_id: str) -> InMemoryChatMessageHistory:

        if session_id not in self._history_store:
            self._history_store[session_id] = InMemoryChatMessageHistory()

        return self._history_store[session_id]

    def clear(self, session_id: str) -> None:

        self._history_store.pop(session_id, None)
