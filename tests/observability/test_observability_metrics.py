from src.observability import metrics


class RecordingInstrument:
    def __init__(self):
        self.calls = []

    def record(self, value, attributes):
        self.calls.append((value, attributes))


def test_metric_attributes_are_low_cardinality(monkeypatch):
    instrument = RecordingInstrument()
    monkeypatch.setattr(metrics, "agent_run_duration", instrument)
    monkeypatch.setattr(metrics, "agent_run_tool_calls", instrument)
    monkeypatch.setattr(metrics, "agent_run_retry_count", instrument)

    metrics.record_agent_run(
        120.5,
        tool_calls=2,
        retry_count=1,
        attributes={
            "agent.name": "WeatherAgent",
            "provider": "ollama",
            "model": "phi3",
            "environment": "dev",
            "session.id": "do-not-export",
            "request_id": "do-not-export",
        },
    )

    assert instrument.calls
    for _, attributes in instrument.calls:
        assert "session.id" not in attributes
        assert "request_id" not in attributes
        assert attributes["agent.name"] == "WeatherAgent"


def test_record_llm_usage_records_all_token_values(monkeypatch):
    instruments = [RecordingInstrument(), RecordingInstrument(), RecordingInstrument()]
    monkeypatch.setattr(metrics, "agent_llm_input_tokens", instruments[0])
    monkeypatch.setattr(metrics, "agent_llm_output_tokens", instruments[1])
    monkeypatch.setattr(metrics, "agent_llm_total_tokens", instruments[2])

    metrics.record_llm_usage(
        input_tokens=11,
        output_tokens=7,
        total_tokens=18,
        attributes={"provider": "claude", "model": "claude-test"},
    )

    assert instruments[0].calls[0][0] == 11
    assert instruments[1].calls[0][0] == 7
    assert instruments[2].calls[0][0] == 18
    assert instruments[0].calls[0][1]["provider"] == "claude"
    assert instruments[0].calls[0][1]["model"] == "claude-test"
    assert instruments[0].calls[0][1]["environment"] == "dev"
