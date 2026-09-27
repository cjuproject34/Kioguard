from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


INTENTS = {
    "SELECT", "MODIFY", "FULFILLMENT", "PAYMENT_METHOD", "RECEIPT",
    "BENEFIT_CONTROL", "NAVIGATE", "CANCEL", "GUIDE", "INFO",
    "UI_CONTROL", "HELP", "COMMIT_REQUEST", "RESET",
}
FALLBACKS = {
    "ASK_SCREEN_TARGET", "ASK_GUIDANCE_NEED", "ASK_TARGET", "ASK_CONTEXT",
    "ASK_REFERENCE", "ASK_INPUT_REPEAT", "ASK_SCOPE", "OUT_OF_SCOPE", "NO_ACTION",
}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: {exc}") from exc
    return rows


def validate(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    seen_cases: set[str] = set()
    required_case_keys = {
        "case_id", "dataset", "group_id", "source_type", "domain", "utterance",
        "context", "gold", "impact", "complexity", "must_not_intents",
        "review_status", "constructed_context", "notes",
    }
    required_context_keys = {
        "current_stage", "current_screen", "current_order_exists", "payment_completed",
        "selected_items", "previous_system_question", "available_actions",
        "observed_ui_elements", "verified_state",
    }
    request_keys = {"request_id", "intent", "target", "slots", "condition", "depends_on"}
    for row in rows:
        cid = row.get("case_id", "<missing>")
        if set(row) != required_case_keys:
            errors.append(f"{cid}: case keys differ: {sorted(set(row) ^ required_case_keys)}")
        if cid in seen_cases:
            errors.append(f"{cid}: duplicate case_id")
        seen_cases.add(cid)
        if set(row.get("context", {})) != required_context_keys:
            errors.append(f"{cid}: context keys differ")
        if row.get("impact", {}).get("level") not in {"L", "M", "H", "U"}:
            errors.append(f"{cid}: invalid impact")
        if row.get("complexity", {}).get("level") not in {"C1", "C2", "C3", "CU"}:
            errors.append(f"{cid}: invalid complexity")
        gold = row.get("gold", {})
        if set(gold) != {"requests", "fallback"}:
            errors.append(f"{cid}: gold keys differ")
            continue
        fb = gold.get("fallback")
        if fb is not None:
            if fb.get("type") not in FALLBACKS:
                errors.append(f"{cid}: invalid fallback type")
            if set(fb) - {"type", "field"}:
                errors.append(f"{cid}: invalid fallback keys")
        seen_requests: set[str] = set()
        gold_intents: set[str] = set()
        for req in gold.get("requests", []):
            if set(req) != request_keys:
                errors.append(f"{cid}: request keys differ")
            if req.get("intent") not in INTENTS:
                errors.append(f"{cid}: invalid intent {req.get('intent')}")
            rid = req.get("request_id")
            if rid in seen_requests:
                errors.append(f"{cid}: duplicate request_id {rid}")
            dep = req.get("depends_on")
            if dep is not None and dep not in seen_requests:
                errors.append(f"{cid}: depends_on must reference earlier request")
            seen_requests.add(rid)
            gold_intents.add(req.get("intent"))
        overlap = gold_intents.intersection(row.get("must_not_intents", []))
        if overlap:
            errors.append(f"{cid}: gold and must_not overlap {sorted(overlap)}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    rows: list[dict] = []
    file_info = []
    for path in args.paths:
        current = load_jsonl(path)
        rows.extend(current)
        file_info.append({
            "path": str(path),
            "rows": len(current),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    errors = validate(rows)
    report = {
        "valid": not errors,
        "cases": len(rows),
        "files": file_info,
        "datasets": dict(sorted(Counter(r["dataset"] for r in rows).items())),
        "review_status": dict(sorted(Counter(r["review_status"] for r in rows).items())),
        "impact": dict(sorted(Counter(r["impact"]["level"] for r in rows).items())),
        "complexity": dict(sorted(Counter(r["complexity"]["level"] for r in rows).items())),
        "intent_requests": dict(sorted(Counter(q["intent"] for r in rows for q in r["gold"]["requests"]).items())),
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
