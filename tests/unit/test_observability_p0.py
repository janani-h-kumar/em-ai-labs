from unittest.mock import MagicMock

import pytest

from src.observability.tracing import (
    SPAN_AGENT_RUN,
    SPAN_LLM_CALL,
    SPAN_TOOL_API_REQUEST,
    SPAN_TOOL_CALL,
    create_span,
)


def test_canonical_span_names():
    assert [SPAN_AGENT_RUN, SPAN_LLM_CALL, SPAN_TOOL_CALL, SPAN_TOOL_API_REQUEST] == [
        "agent.run",
        "llm.call",
        "tool.call",
        "tool.api_request",
    ]


def test_create_span_sets_common_duration_and_outcome(monkeypatch):
    from src.observability import tracing

    span = MagicMock()
    span.is_recording.return_value = True
    manager = MagicMock()
    manager.__enter__.return_value = span
    manager.__exit__.return_value = False
    monkeypatch.setattr(tracing.tracer, "start_as_current_span", lambda name: manager)
    monkeypatch.setattr(tracing.trace, "get_current_span", lambda: span)

    with tracing.create_span("agent.run", **{"agent.name": "general"}):
        pass

    attrs = {call.args[0]: call.args[1] for call in span.set_attribute.call_args_list}
    assert attrs["agent.name"] == "general"
    assert attrs["outcome"] == "success"
    assert "duration_ms" in attrs
