from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("run_qwen35_2b_gguf_case_replay.py")
spec = importlib.util.spec_from_file_location("gguf_replay", MODULE_PATH)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def output(requests, fallback=None):
    return json.dumps({"requests": requests, "fallback": fallback}, ensure_ascii=False)


def request(intent="SELECT", rid="r1", depends_on=None):
    return {
        "request_id": rid,
        "intent": intent,
        "target": "NEW_ORDER",
        "slots": {},
        "condition": None,
        "depends_on": depends_on,
    }


def test_valid_request_and_fallback_only():
    assert runner.contract_validation_error(output([request()])) is None
    assert runner.contract_validation_error(
        output([], {"type": "ASK_SCREEN_TARGET", "field": "screen"})
    ) is None
    assert runner.contract_validation_error(output([], {"type": "NO_ACTION"})) is None


def test_fallback_type_cannot_be_an_intent():
    error = runner.contract_validation_error(output([request("ASK_SCREEN_TARGET")]))
    assert error == "request_0_intent_invalid"


def test_complete_contract_is_required():
    value = {"requests": [request()]}
    assert runner.contract_validation_error(json.dumps(value)) == "top_level_keys_invalid"
    malformed = request()
    malformed.pop("slots")
    assert runner.contract_validation_error(output([malformed])) == "request_0_keys_invalid"


def test_request_order_and_dependency_are_checked():
    assert runner.contract_validation_error(output([request(rid="r2")])) == "request_0_id_must_be_r1"
    assert runner.contract_validation_error(output([request(depends_on="r9")])) == "request_0_depends_on_invalid"


def test_missing_nullable_request_fields_are_repaired_without_semantic_inference():
    incomplete = request()
    incomplete.pop("condition")
    incomplete.pop("depends_on")
    repaired, steps = runner.repair_missing_nullable_request_fields(output([incomplete]))
    assert runner.contract_validation_error(repaired) is None
    assert steps == [
        "request_0_condition_defaulted_null",
        "request_0_depends_on_defaulted_null",
    ]
    repaired_request = json.loads(repaired)["requests"][0]
    assert repaired_request["intent"] == incomplete["intent"]
    assert repaired_request["slots"] == incomplete["slots"]


def test_missing_top_level_nullable_fallback_is_repaired():
    incomplete = json.dumps({"requests": [request()]}, ensure_ascii=False)
    repaired, steps = runner.repair_missing_nullable_request_fields(incomplete)
    assert runner.contract_validation_error(repaired) is None
    assert steps == ["top_level_fallback_defaulted_null"]
    assert json.loads(repaired)["fallback"] is None


if __name__ == "__main__":
    tests = [
        test_valid_request_and_fallback_only,
        test_fallback_type_cannot_be_an_intent,
        test_complete_contract_is_required,
        test_request_order_and_dependency_are_checked,
        test_missing_nullable_request_fields_are_repaired_without_semantic_inference,
        test_missing_top_level_nullable_fallback_is_repaired,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} GGUF replay contract tests passed")
