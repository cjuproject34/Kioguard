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
DANGEROUS = {"CANCEL", "COMMIT_REQUEST", "RESET"}
REQUEST_KEYS = {"request_id", "intent", "target", "slots", "condition", "depends_on"}


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def same(a: object, b: object) -> bool:
    return canonical(a) == canonical(b)


def strip_code_fence(text: str) -> tuple[str, str]:
    raw = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.I | re.S)
    return (match.group(1).strip(), "MARKDOWN_CODE_FENCE") if match else (raw, "NONE")


def validate_output(value: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict): return ["top level is not an object"]
    if set(value) != {"requests", "fallback"}: errors.append("top-level keys differ")
    requests = value.get("requests")
    if not isinstance(requests, list): return errors + ["requests is not an array"]
    fallback = value.get("fallback", "__MISSING__")
    if fallback != "__MISSING__" and fallback is not None:
        if not isinstance(fallback, dict): errors.append("fallback is not an object or null")
        else:
            if set(fallback) - {"type", "field"}: errors.append("fallback has extra keys")
            if "type" not in fallback or fallback.get("type") not in FALLBACKS: errors.append("fallback type is invalid")
            if "field" in fallback and not isinstance(fallback["field"], str): errors.append("fallback field is invalid")
    seen: set[str] = set()
    for idx, req in enumerate(requests):
        if not isinstance(req, dict): errors.append(f"requests[{idx}] is not an object"); continue
        if set(req) != REQUEST_KEYS: errors.append(f"requests[{idx}] keys differ")
        if req.get("intent") not in INTENTS: errors.append(f"requests[{idx}] invalid intent")
        if not isinstance(req.get("slots"), dict): errors.append(f"requests[{idx}] slots is not an object")
        if req.get("target") is not None and not isinstance(req.get("target"), str): errors.append(f"requests[{idx}] target is invalid")
        rid = req.get("request_id")
        expected_rid = f"r{idx + 1}"
        if not isinstance(rid, str) or not re.fullmatch(r"r[1-9][0-9]*", rid or ""): errors.append(f"requests[{idx}] request_id format is invalid")
        elif rid != expected_rid: errors.append(f"requests[{idx}] request_id must be {expected_rid}")
        if rid in seen: errors.append(f"requests[{idx}] request_id is duplicated")
        dep = req.get("depends_on")
        if dep is not None and dep not in seen: errors.append(f"requests[{idx}] depends_on is invalid")
        condition = req.get("condition")
        if condition is not None:
            if not isinstance(condition, dict) or set(condition) != {"state_key", "operator", "value"} or condition.get("operator") not in {"EQ", "NE", "IN", "NOT_IN"}:
                errors.append(f"requests[{idx}] condition is invalid")
        if isinstance(rid, str): seen.add(rid)
    return errors


def rate(n: int, d: int) -> float:
    return n / d if d else 0.0


def field_exact(gold_req: list[dict], pred_req: list[dict], field: str) -> bool:
    return len(gold_req) == len(pred_req) and all(same(g.get(field), p.get(field)) for g, p in zip(gold_req, pred_req))


def main() -> None:
    parser = argparse.ArgumentParser(description="Versioned decomposed scorer; does not replace v1 baselines.")
    parser.add_argument("--gold", action="append", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    gold_rows = [r for p in args.gold for r in load_jsonl(p)]
    gold_ids = [r["case_id"] for r in gold_rows]
    if len(gold_ids) != len(set(gold_ids)): raise SystemExit("duplicate gold case_id")
    gold = {r["case_id"]: r for r in gold_rows}
    pred_rows = load_jsonl(args.predictions)
    pred_id_counts = Counter(r.get("case_id") for r in pred_rows)
    duplicate_prediction_ids = sorted(str(k) for k, v in pred_id_counts.items() if v > 1)
    missing_case_id_rows = sum(1 for r in pred_rows if not isinstance(r.get("case_id"), str))
    pred_by_id = {r.get("case_id"): r for r in pred_rows if isinstance(r.get("case_id"), str)}
    unknown = sorted(set(pred_by_id) - set(gold))

    totals = Counter()
    tp = Counter(); fp = Counter(); fn = Counter()
    per_case: list[dict] = []
    for cid, case in gold.items():
        totals["cases"] += 1
        pred_row = pred_by_id.get(cid)
        raw = pred_row.get("raw_output", "") if pred_row else ""
        row_status = pred_row.get("status", "MISSING" if pred_row is None else "UNKNOWN") if pred_row else "MISSING"
        strict_ok = normalized_ok = False
        wrapper = "NONE"; parsed = None
        try:
            parsed = json.loads(raw); strict_ok = normalized_ok = True
        except Exception:
            normalized, wrapper = strip_code_fence(raw)
            try: parsed = json.loads(normalized); normalized_ok = True
            except Exception: parsed = None
        errors = validate_output(parsed) if normalized_ok else ["JSON parse failed"]
        contract_ok = normalized_ok and not errors
        gold_req = case["gold"]["requests"]
        pred_req = parsed["requests"] if contract_ok else []
        gold_intents = Counter(r["intent"] for r in gold_req)
        pred_intents = Counter(r["intent"] for r in pred_req)
        for intent in INTENTS:
            matched = min(gold_intents[intent], pred_intents[intent])
            tp[intent] += matched; fp[intent] += max(0, pred_intents[intent] - matched); fn[intent] += max(0, gold_intents[intent] - matched)
        extra = pred_intents - gold_intents
        dangerous = sorted(i for i in extra.elements() if i in DANGEROUS)
        must_not = sorted(set(pred_intents).intersection(case["must_not_intents"]))

        checks = {
            "request_count_exact": contract_ok and len(gold_req) == len(pred_req),
            "intent_multiset_exact": contract_ok and gold_intents == pred_intents,
            "intent_order_exact": contract_ok and [r["intent"] for r in gold_req] == [r["intent"] for r in pred_req],
            "target_exact": contract_ok and field_exact(gold_req, pred_req, "target"),
            "slots_exact": contract_ok and field_exact(gold_req, pred_req, "slots"),
            "condition_exact": contract_ok and field_exact(gold_req, pred_req, "condition"),
            "depends_on_exact": contract_ok and field_exact(gold_req, pred_req, "depends_on"),
            "fallback_exact": contract_ok and same(case["gold"]["fallback"], parsed.get("fallback")),
            "full_exact": contract_ok and same(case["gold"], parsed),
        }
        mismatches = [name.removesuffix("_exact") for name, ok in checks.items() if not ok]
        totals["strict_json"] += strict_ok; totals["normalized_json"] += normalized_ok; totals["contract_valid"] += contract_ok
        for name, ok in checks.items(): totals[name] += ok
        totals["dangerous_extra_cases"] += bool(dangerous); totals["must_not_hit_cases"] += bool(must_not)
        if case["impact"]["level"] == "H": totals["high_impact_cases"] += 1; totals["high_impact_full_exact"] += checks["full_exact"]
        per_case.append({
            "case_id": cid, "dataset": case["dataset"], "impact": case["impact"]["level"], "complexity": case["complexity"]["level"],
            "prediction_status": row_status, "strict_json": strict_ok, "normalized_json": normalized_ok, "wrapper": wrapper,
            "contract_valid": contract_ok, **checks,
            "gold_intents": ",".join(gold_intents.elements()), "pred_intents": ",".join(pred_intents.elements()),
            "dangerous_extra_intents": ",".join(dangerous), "must_not_hits": ",".join(must_not),
            "mismatch_categories": ",".join(mismatches), "contract_errors": " | ".join(errors),
        })

    intent_metrics = {}
    f1s = []
    for intent in INTENTS:
        precision = rate(tp[intent], tp[intent] + fp[intent]); recall = rate(tp[intent], tp[intent] + fn[intent])
        f1 = rate(2 * precision * recall, precision + recall); f1s.append(f1)
        intent_metrics[intent] = {"tp": tp[intent], "fp": fp[intent], "fn": fn[intent], "precision": precision, "recall": recall, "f1": f1}
    n = totals["cases"]
    summary = {
        "scorer_version": "2.0",
        "cases": n, "prediction_rows": len(pred_rows),
        "missing_prediction_cases": sum(1 for cid in gold if cid not in pred_by_id),
        "duplicate_prediction_ids": duplicate_prediction_ids, "unknown_prediction_ids": unknown,
        "prediction_rows_missing_case_id": missing_case_id_rows,
        "strict_json_rate": rate(totals["strict_json"], n), "normalized_json_rate": rate(totals["normalized_json"], n),
        "contract_valid_rate": rate(totals["contract_valid"], n),
        **{f"{name}_rate": rate(totals[name], n) for name in ["request_count_exact", "intent_multiset_exact", "intent_order_exact", "target_exact", "slots_exact", "condition_exact", "depends_on_exact", "fallback_exact", "full_exact"]},
        "macro_intent_f1": sum(f1s) / len(f1s),
        "high_impact_full_exact_rate": rate(totals["high_impact_full_exact"], totals["high_impact_cases"]),
        "dangerous_extra_action_cases": totals["dangerous_extra_cases"], "must_not_violation_cases": totals["must_not_hit_cases"],
        "intent_metrics": intent_metrics,
        "baseline_note": "This decomposed v2 report supplements, and does not overwrite, score_predictions.py v1 results.",
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary_v2.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (args.out_dir / "case_scores_v2.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_case[0])); writer.writeheader(); writer.writerows(per_case)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if duplicate_prediction_ids or unknown or missing_case_id_rows:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
