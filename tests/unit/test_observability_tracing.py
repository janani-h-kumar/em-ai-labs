from opentelemetry import trace

from src.observability.tracing import create_span, get_span_id, get_trace_id


def test_active_span_has_trace_and_span_ids():
    with create_span("test.span"):
        assert get_trace_id() is not None
        assert get_span_id() is not None


def test_child_span_uses_same_trace():
    with create_span("parent"):
        parent_trace = get_trace_id()
        with create_span("child"):
            assert get_trace_id() == parent_trace
            assert trace.get_current_span().name == "child"
