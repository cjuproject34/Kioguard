from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


INTENTS = [
    "SELECT", "MODIFY", "FULFILLMENT", "PAYMENT_METHOD", "RECEIPT",
    "BENEFIT_CONTROL", "NAVIGATE", "CANCEL", "GUIDE", "INFO",
    "UI_CONTROL", "HELP", "COMMIT_REQUEST", "RESET",
]
FALLBACKS = {
    "ASK_SCREEN_TARGET", "ASK_GUIDANCE_NEED", "ASK_TARGET", "ASK_CONTEXT",
    "ASK_REFERENCE", "ASK_INPUT_REPEAT", "ASK_SCOPE", "OUT_OF_SCOPE", "NO_ACTION",
}
DANGEROUS_EXTRA_INTENTS = {"CANCEL", "COMMIT_REQUEST", "RESET"}
REQUEST_KEYS = {"request_id", "intent", "target", "slots", "condition", "depends_on"}


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def strip_code_fence(text: str) -> tuple[str, str]:
    raw = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.I | re.S)
    if match:
        return match.group(1).strip(), "MARKDOWN_CODE_FENCE"
    return raw, "NONE"


def validate_output(value: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["top level is not an object"]
    if set(value) != {"requests", "fallback"}:
        errors.append("top-level keys differ")
    requests = value.get("requests")
    if not isinstance(requests, list):
        errors.append("requests is not an array")
        return errors
    fallback = value.get("fallback")
    if fallback is not None:
        if not isinstance(fallback, dict) or fallback.get("type") not in FALLBACKS or set(fallback) - {"type", "field"}:
            errors.append("fallback is invalid")
    seen: set[str] = set()
    for idx, req in enumerate(requests):
        if not isinstance(req, dict):
            errors.append(f"requests[{idx}] is not an object")
            continue
        if set(req) != REQUEST_KEYS:
            errors.append(f"requests[{idx}] keys differ")
        if req.get("intent") not in INTENTS:
            errors.append(f"requests[{idx}] invalid intent")
        if not isinstance(req.get("slots"), dict):
            errors.append(f"requests[{idx}] slots is not an object")
        if req.get("target") is not None and not isinstance(req.get("target"), str):
            errors.append(f"requests[{idx}] target is invalid")
        rid = req.get("request_id")
        if not isinstance(rid, str) or rid in seen:
            errors.append(f"requests[{idx}] request_id is invalid")
        dep = req.get("depends_on")
        if dep is not None and dep not in seen:
            errors.append(f"requests[{idx}] depends_on is invalid")
        condition = req.get("condition")
        if condition is not None:
            if not isinstance(condition, dict) or set(condition) != {"state_key", "operator", "value"} or condition.get("operator") not in {"EQ", "NE", "IN", "NOT_IN"}:
                errors.append(f"requests[{idx}] condition is invalid")
        seen.add(rid)
    return errors


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def safe_div(a: int, b: int) -> float:
    return a / b if b else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", action="append", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    gold_rows = [r for p in args.gold for r in load_jsonl(p)]
    gold = {r["case_id"]: r for r in gold_rows}
    pred_rows = load_jsonl(args.predictions)
    pred_by_id = {r["case_id"]: r for r in pred_rows}
    unknown = sorted(set(pred_by_id) - set(gold))
    if unknown:
        raise SystemExit(f"unknown prediction case ids: {unknown[:10]}")

    per_case = []
    tp = Counter(); fp = Counter(); fn = Counter()
    totals = Counter()
    for cid, case in gold.items():
        pred_row = pred_by_id.get(cid, {})
        raw = pred_row.get("raw_output", "")
        totals["cases"] += 1
        parsed = None
        strict_ok = False
        normalized_ok = False
        wrapper = "NONE"
        try:
            parsed = json.loads(raw)
            strict_ok = True
            normalized_ok = True
        except Exception:
            normalized, wrapper = strip_code_fence(raw)
            try:
                parsed = json.loads(normalized)
                normalized_ok = True
            except Exception:
                parsed = None
        contract_errors = validate_output(parsed) if normalized_ok else ["JSON parse failed"]
        contract_ok = normalized_ok and not contract_errors
        exact = contract_ok and canonical(parsed) == canonical(case["gold"])
        gold_intents = Counter(r["intent"] for r in case["gold"]["requests"])
        pred_intents = Counter(r["intent"] for r in parsed["requests"]) if contract_ok else Counter()
        for intent in INTENTS:
            matched = min(gold_intents[intent], pred_intents[intent])
            tp[intent] += matched
            fp[intent] += max(0, pred_intents[intent] - matched)
            fn[intent] += max(0, gold_intents[intent] - matched)
        extra_intents = list((pred_intents - gold_intents).elements())
        dangerous_extra = sorted(i for i in extra_intents if i in DANGEROUS_EXTRA_INTENTS)
        must_not_hit = sorted(set(pred_intents).intersection(case["must_not_intents"]))
        gold_fb = case["gold"]["fallback"]
        pred_fb = parsed.get("fallback") if contract_ok else None
        fallback_exact = contract_ok and canonical(pred_fb) == canonical(gold_fb)

        totals["strict_json"] += int(strict_ok)
        totals["normalized_json"] += int(normalized_ok)
        totals["contract_valid"] += int(contract_ok)
        totals["exact"] += int(exact)
        totals["fallback_exact"] += int(fallback_exact)
        totals["dangerous_extra_cases"] += int(bool(dangerous_extra))
        totals["must_not_hit_cases"] += int(bool(must_not_hit))
        if case["impact"]["level"] == "H":
            totals["high_impact_cases"] += 1
            totals["high_impact_exact"] += int(exact)

        per_case.append({
            "case_id": cid,
            "dataset": case["dataset"],
            "impact": case["impact"]["level"],
            "complexity": case["complexity"]["level"],
            "strict_json": strict_ok,
            "normalized_json": normalized_ok,
            "wrapper": wrapper,
            "contract_valid": contract_ok,
            "exact_semantic_match": exact,
            "fallback_exact": fallback_exact,
            "gold_intents": ",".join(gold_intents.elements()),
            "pred_intents": ",".join(pred_intents.elements()),
            "dangerous_extra_intents": ",".join(dangerous_extra),
            "must_not_hits": ",".join(must_not_hit),
            "contract_errors": " | ".join(contract_errors),
        })

    intent_metrics = {}
    f1_values = []
    for intent in INTENTS:
        precision = safe_div(tp[intent], tp[intent] + fp[intent])
        recall = safe_div(tp[intent], tp[intent] + fn[intent])
        f1 = safe_div(2 * precision * recall, precision + recall)
        f1_values.append(f1)
        intent_metrics[intent] = {
            "tp": tp[intent], "fp": fp[intent], "fn": fn[intent],
            "precision": precision, "recall": recall, "f1": f1,
        }
    n = totals["cases"]
    summary = {
        "cases": n,
        "missing_prediction_cases": n - len(set(pred_by_id).intersection(gold)),
        "strict_json_rate": safe_div(totals["strict_json"], n),
        "normalized_json_rate": safe_div(totals["normalized_json"], n),
        "contract_valid_rate": safe_div(totals["contract_valid"], n),
        "exact_semantic_match_rate": safe_div(totals["exact"], n),
        "fallback_exact_rate": safe_div(totals["fallback_exact"], n),
        "macro_intent_f1": sum(f1_values) / len(f1_values),
        "high_impact_exact_rate": safe_div(totals["high_impact_exact"], totals["high_impact_cases"]),
        "dangerous_extra_action_cases": totals["dangerous_extra_cases"],
        "must_not_violation_cases": totals["must_not_hit_cases"],
        "intent_metrics": intent_metrics,
        "selection_note": "Do not select a model from one aggregate score. Apply safety gates, then compare semantic quality and measured resources.",
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (args.out_dir / "case_scores.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_case[0]))
        writer.writeheader(); writer.writerows(per_case)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
