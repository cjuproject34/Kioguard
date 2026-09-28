from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("score_predictions_v2.py")
spec = importlib.util.spec_from_file_location("scorer_v2", MODULE_PATH)
assert spec and spec.loader
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)


def request(rid="r1", intent="NAVIGATE"):
    return {"request_id": rid, "intent": intent, "target": "APP_UI", "slots": {}, "condition": None, "depends_on": None}


def test_valid_output():
    assert scorer.validate_output({"requests": [request()], "fallback": None}) == []


def test_request_sequence_is_checked():
    errors = scorer.validate_output({"requests": [request("r2")], "fallback": None})
    assert any("must be r1" in e for e in errors)


def test_missing_fallback_is_rejected():
    errors = scorer.validate_output({"requests": [request()]})
    assert "top-level keys differ" in errors


def test_code_fence_only_normalization():
    value, wrapper = scorer.strip_code_fence("```json\n{\"requests\":[],\"fallback\":null}\n```")
    assert wrapper == "MARKDOWN_CODE_FENCE"
    assert value.startswith("{")


if __name__ == "__main__":
    for fn in [test_valid_output, test_request_sequence_is_checked, test_missing_fallback_is_rejected, test_code_fence_only_normalization]:
        fn()
    print("4 scorer v2 tests passed")
