from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_trace_file(file_path: str | Path) -> list[dict[str, Any]]:
    """Load a JSONL trace file into Python objects."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")

    spans: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as trace_file:
        for line in trace_file:
            if not line.strip():
                continue
            spans.append(json.loads(line))
    return spans


def _format_duration(duration_ms: float | int | None) -> str:
    if duration_ms is None:
        return "unknown"
    if duration_ms >= 1000:
        return f"{round(duration_ms / 1000, 1)} sec"
    return f"{int(duration_ms)} ms"


def _format_bytes(size: int | None) -> str:
    if size is None:
        return "unknown"
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{round(size / 1024, 1)} KB"
    return f"{round(size / (1024 * 1024), 1)} MB"


def _span_attributes(span: dict[str, Any]) -> dict[str, Any]:
    return span.get("attributes", {}) or {}


def _find_span(spans: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((span for span in spans if span.get("name") == name), None)


def _find_tool_span(spans: list[dict[str, Any]]) -> dict[str, Any] | None:
    for span in spans:
        attrs = _span_attributes(span)
        if span.get("name") == "tool.execute" or attrs.get("tool_name") or attrs.get("tool"):
            return span
    return None


def format_trace_summary(
    spans: list[dict[str, Any]],
    *,
    run_number: int | None = None,
    trace_id: str | None = None,
) -> str:
    """Return a compact human-readable summary from a set of trace spans."""
    filtered_spans = list(spans)
    if trace_id is not None:
        filtered_spans = [span for span in filtered_spans if span.get("trace_id") == trace_id]
    elif run_number is not None:
        candidate_trace_ids = {
            span.get("trace_id")
            for span in filtered_spans
            if _span_attributes(span).get("run_number") == run_number
            or _span_attributes(span).get("request_count") == run_number
        }
        if candidate_trace_ids:
            filtered_spans = [
                span for span in filtered_spans if span.get("trace_id") in candidate_trace_ids
            ]
        else:
            filtered_spans = [
                span
                for span in filtered_spans
                if _span_attributes(span).get("run_number") == run_number
                or _span_attributes(span).get("request_count") == run_number
            ]

    if not filtered_spans:
        return "No matching spans found."

    filtered_spans.sort(key=lambda span: span.get("start_time_unix_nano", 0))

    first_span = filtered_spans[0]
    attributes = _span_attributes(first_span)
    run_number_value = run_number or attributes.get("run_number") or attributes.get("request_count")
    lines = [f"Run #{run_number_value}" if run_number_value is not None else "Run"]
    lines.append("")

    plan_span = _find_span(filtered_spans, "planner.create_plan")
    if plan_span:
        plan_attrs = _span_attributes(plan_span)
        lines.append("Plan")
        lines.append("  ↓")
        if plan_attrs.get("planner.heuristic_skip"):
            lines.append("  (heuristic skip)")
    else:
        lines.append("Plan")
        lines.append("  (not captured)")

    tool_span = _find_tool_span(filtered_spans)
    if tool_span:
        attrs = _span_attributes(tool_span)
        tool_name = attrs.get("tool_name") or attrs.get("tool") or "tool"
        latency = _format_duration(attrs.get("tool_latency_ms") or attrs.get("latency_ms"))
        size = _format_bytes(attrs.get("result_size_bytes") or attrs.get("response_size_bytes"))
        lines.append("")
        lines.append(f"{tool_name}")
        lines.append(f"  {latency}")
        if size != "unknown":
            lines.append(f"  {size}")

    llm_span = _find_span(filtered_spans, "llm.chat_completion")
    if llm_span:
        attrs = _span_attributes(llm_span)
        latency = _format_duration(attrs.get("latency_ms") or attrs.get("llm_latency_ms"))
        total_tokens = attrs.get("total_tokens")
        lines.append("")
        lines.append("LLM Call")
        lines.append(f"  {latency}")
        if total_tokens is not None:
            lines.append(f"  {total_tokens} tokens")

    return "\n".join(lines)


def render_trace_summary_from_file(
    trace_file: str | Path,
    *,
    run_number: int | None = None,
    trace_id: str | None = None,
) -> str:
    spans = load_trace_file(trace_file)
    return format_trace_summary(spans, run_number=run_number, trace_id=trace_id)
