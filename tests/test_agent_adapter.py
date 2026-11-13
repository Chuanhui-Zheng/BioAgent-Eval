from __future__ import annotations

from bioagent.llm_adapter import StructuredToolModelAdapter


class FakeProvider:
    model = "fixture-model"

    def __init__(self, response):
        self.response = response
        self.usage_records = []

    def complete(self, messages, *, json_mode):
        assert json_mode is True
        self.usage_records.append({"input_tokens": 12, "output_tokens": 5})
        return self.response


def test_adapter_translates_tool_decision_and_usage():
    adapter = StructuredToolModelAdapter(FakeProvider(
        '{"action":"tool","tool_name":"retrieve_evidence","tool_arguments":{"query":"TCF7L2"}}'
    ))
    decision = adapter.decide("find evidence", [{"role": "user", "content": "find evidence"}], [])
    assert decision.action == "tool"
    assert decision.tool_name == "retrieve_evidence"
    assert decision.tool_arguments == {"query": "TCF7L2"}
    assert decision.usage.total_tokens == 17
