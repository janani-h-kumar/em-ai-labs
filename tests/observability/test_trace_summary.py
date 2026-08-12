import json
from pathlib import Path

from src.observability.trace_summary import (
    format_trace_summary,
    render_trace_summary_from_file,
)


def test_format_trace_summary_with_tool_and_llm_spans():
    spans = [
        {
            "name": "request",
            "trace_id": "trace-1",
            "attributes": {
                "run_number": 18,
                "request_count": 18,
            },
            "start_time_unix_nano": 1,
        },
        {
            "name": "planner.create_plan",
            "trace_id": "trace-1",
            "attributes": {
                "planner.heuristic_skip": False,
                "decision": "llm_plan",
            },
            "start_time_unix_nano": 2,
        },
        {
            "name": "tool.call",
            "trace_id": "trace-1",
            "attributes": {
                "tool_name": "weather_tool",
                "duration_ms": 243,
                "response_size_bytes": 1229,
            },
            "start_time_unix_nano": 3,
        },
        {
            "name": "llm.call",
            "trace_id": "trace-1",
            "attributes": {
                "latency_ms": 1890,
                "total_tokens": 834,
            },
            "start_time_unix_nano": 4,
        },
    ]

    summary = format_trace_summary(spans, run_number=18)

    assert "Run #18" in summary
    assert "Plan" in summary
    assert "weather_tool" in summary
    assert "243 ms" in summary
    assert "LLM Call" in summary
    assert "1.9 sec" in summary
    assert "834 tokens" in summary


def test_render_trace_summary_from_file(tmp_path: Path):
    spans = [
        {
            "name": "request",
            "trace_id": "trace-2",
            "attributes": {
                "run_number": 42,
            },
            "start_time_unix_nano": 1,
        }
    ]
    trace_file = tmp_path / "trace.jsonl"
    trace_file.write_text("\n".join(json.dumps(span) for span in spans), encoding="utf-8")

    summary = render_trace_summary_from_file(str(trace_file), run_number=42)
    assert "Run #42" in summary
