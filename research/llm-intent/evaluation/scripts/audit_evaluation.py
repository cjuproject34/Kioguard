from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


INTENT_ORDER = [
    "SELECT", "MODIFY", "FULFILLMENT", "PAYMENT_METHOD", "RECEIPT",
    "BENEFIT_CONTROL", "NAVIGATE", "CANCEL", "GUIDE", "INFO",
    "UI_CONTROL", "HELP", "COMMIT_REQUEST", "RESET",
]
CHALLENGE_GATE_IDS = [
    "CH-CLR-01", "CH-CLR-02", "CH-NEG-01", "CH-NEG-02", "CH-MUL-01", "CH-CTX-04",
]


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def derive_route(case: dict) -> tuple[str, list[str]]:
    impact = case["impact"]["level"]
    complexity = case["complexity"]["level"]
    requests = case["gold"]["requests"]
    fallback = case["gold"]["fallback"]
    reasons: list[str] = []
    if impact == "H": reasons.append("high_impact")
    if complexity in {"C3", "CU"}: reasons.append("semantic_complexity")
    if fallback is not None: reasons.append("fallback_required")
    if len(requests) > 1: reasons.append("multi_request")
    if any(r["condition"] is not None for r in requests): reasons.append("conditional_request")
    if reasons:
        return "LLM_REQUIRED", reasons
    if impact in {"L", "M"} and complexity == "C1" and len(requests) == 1:
        return "RULE_CANDIDATE", ["explicit_single_request"]
    return "ROUTER_REVIEW", ["boundary_case"]


def auto_flags(case: dict) -> list[str]:
    flags: list[str] = []
    reqs = case["gold"]["requests"]
    fallback = case["gold"]["fallback"]
    if case["review_status"] == "DRAFT": flags.append("HUMAN_REVIEW_PENDING")
    if case["impact"]["level"] == "U": flags.append("IMPACT_UNRESOLVED")
    if case["complexity"]["level"] == "CU": flags.append("COMPLEXITY_UNRESOLVED")
    if len(reqs) > 1: flags.append("MULTI_REQUEST")
    if any(r["condition"] is not None for r in reqs): flags.append("CONDITION_PRESENT")
    if not reqs and fallback is None: flags.append("EMPTY_WITHOUT_FALLBACK_REVIEW")
    if reqs and fallback is not None: flags.append("REQUEST_AND_FALLBACK_REVIEW")
    if case.get("constructed_context"): flags.append("CONSTRUCTED_CONTEXT")
    return flags


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="CPU-only audit; source JSONL files are never modified.")
    parser.add_argument("--core", type=Path, default=Path("data/selection_dev_v0.1.jsonl"))
    parser.add_argument("--challenge", type=Path, default=Path("data/selection_challenge_v0.1.jsonl"))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/cpu_audit"))
    args = parser.parse_args()

    core = load_jsonl(args.core)
    challenge = load_jsonl(args.challenge)
    cases = core + challenge
    by_id = {c["case_id"]: c for c in cases}

    gate_ids: list[str] = []
    for intent in INTENT_ORDER:
        gate_ids.append(next(c["case_id"] for c in core if any(r["intent"] == intent for r in c["gold"]["requests"])))
    gate_ids.extend(CHALLENGE_GATE_IDS)
    if len(gate_ids) != 20 or len(set(gate_ids)) != 20:
        raise SystemExit("gate must contain 20 unique cases")

    utterance_groups: dict[str, list[str]] = defaultdict(list)
    route_rows: list[dict] = []
    route_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()
    targets: Counter[str] = Counter()
    slots: dict[str, Counter[str]] = defaultdict(Counter)
    for case in cases:
        utterance_groups[case["utterance"]].append(case["case_id"])
        route, reasons = derive_route(case)
        flags = auto_flags(case)
        route_counts[route] += 1
        flag_counts.update(flags)
        for req in case["gold"]["requests"]:
            targets[f'{req["intent"]}:{req["target"]}'] += 1
            slots[req["intent"]].update(req["slots"].keys())
        route_rows.append({
            "case_id": case["case_id"], "dataset": case["dataset"],
            "utterance": case["utterance"], "impact": case["impact"]["level"],
            "impact_reason": case["impact"]["reason"],
            "complexity": case["complexity"]["level"],
            "complexity_reason": case["complexity"]["reason"],
            "gold_intents": ",".join(r["intent"] for r in case["gold"]["requests"]),
            "request_count": len(case["gold"]["requests"]),
            "fallback": (case["gold"]["fallback"] or {}).get("type", "NONE"),
            "recommended_route": route, "route_reasons": ",".join(reasons),
            "auto_flags": ",".join(flags), "human_decision": "",
        })

    gate_rows = []
    for order, cid in enumerate(gate_ids, 1):
        case = by_id[cid]
        row = next(r for r in route_rows if r["case_id"] == cid)
        gate_rows.append({"gate_order": order, **row})

    duplicates = [
        {"utterance": utterance, "case_ids": ids, "count": len(ids)}
        for utterance, ids in sorted(utterance_groups.items()) if len(ids) > 1
    ]
    summary = {
        "status": "CPU_AUDIT_COMPLETE_REQUIRES_HUMAN_REVIEW",
        "source_cases": len(cases),
        "source_files_modified": False,
        "review_status": dict(sorted(Counter(c["review_status"] for c in cases).items())),
        "impact": dict(sorted(Counter(c["impact"]["level"] for c in cases).items())),
        "complexity": dict(sorted(Counter(c["complexity"]["level"] for c in cases).items())),
        "impact_by_complexity": dict(sorted(Counter(f'{c["impact"]["level"]}/{c["complexity"]["level"]}' for c in cases).items())),
        "recommended_route": dict(sorted(route_counts.items())),
        "auto_flag_counts": dict(sorted(flag_counts.items())),
        "gate_case_ids": gate_ids,
        "duplicate_utterance_groups": duplicates,
        "limitations": [
            "recommended_route is a review proposal, not a trained or measured router decision",
            "all source cases remain DRAFT",
            "selection data is authored development data, not an independent held-out test",
        ],
    }
    inventory = {
        "target_counts": dict(sorted(targets.items())),
        "slot_key_counts_by_intent": {k: dict(sorted(v.items())) for k, v in sorted(slots.items())},
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "dataset_audit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / "slot_target_inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(args.out_dir / "router_review_v0.1.csv", route_rows)
    write_csv(args.out_dir / "gate_review_v0.1.csv", gate_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
