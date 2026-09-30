from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


INTENTS = {
    "SELECT", "MODIFY", "FULFILLMENT", "PAYMENT_METHOD", "RECEIPT",
    "BENEFIT_CONTROL", "NAVIGATE", "CANCEL", "GUIDE", "INFO",
    "UI_CONTROL", "HELP", "COMMIT_REQUEST", "RESET",
}
DANGEROUS = {"CANCEL", "COMMIT_REQUEST", "RESET"}
TOP_LEVEL_KEYS = {"requests", "fallback"}
REQUEST_KEYS = {"request_id", "intent", "target", "slots", "condition", "depends_on"}


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_output(raw: str) -> tuple[object | None, bool, bool, str]:
    text = raw.strip()
    try:
        return json.loads(text), True, True, "NONE"
    except Exception:
        pass
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.I | re.S)
    if not match:
        return None, False, False, "NONE"
    try:
        return json.loads(match.group(1).strip()), False, True, "MARKDOWN_CODE_FENCE"
    except Exception:
        return None, False, False, "MARKDOWN_CODE_FENCE"


def strings(values: list[str]) -> str:
    return ",".join(values)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit gate failures without replacing strict baseline scores."
    )
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--model-id", default="unknown")
    args = parser.parse_args()

    gold_rows = load_jsonl(args.gold)
    prediction_rows = load_jsonl(args.predictions)
    predictions = {
        row["case_id"]: row for row in prediction_rows if isinstance(row.get("case_id"), str)
    }

    totals = Counter()
    case_rows: list[dict] = []
    for case in gold_rows:
        case_id = case["case_id"]
        pred_row = predictions.get(case_id)
        raw = pred_row.get("raw_output", "") if pred_row else ""
        parsed, strict_ok, normalized_ok, wrapper = parse_output(raw)
        totals["cases"] += 1
        totals["strict_json"] += strict_ok
        totals["normalized_json"] += normalized_ok

        categories: list[str] = []
        structural_errors: list[str] = []
        extra_request_keys: set[str] = set()
        missing_request_keys: set[str] = set()
        pred_requests: list[dict] = []
        pred_fallback: object = None

        if pred_row is None or pred_row.get("status") not in {None, "SUCCESS"}:
            categories.append("RUNTIME_OR_MISSING")
        if wrapper != "NONE":
            categories.append("TRANSPORT_WRAPPER")
        if not normalized_ok or not isinstance(parsed, dict):
            categories.append("JSON_PARSE")
        else:
            top_keys = set(parsed)
            if top_keys != TOP_LEVEL_KEYS:
                categories.append("TOP_LEVEL_CONTRACT")
                structural_errors.append(
                    f"top extra={sorted(top_keys - TOP_LEVEL_KEYS)} missing={sorted(TOP_LEVEL_KEYS - top_keys)}"
                )
            if isinstance(parsed.get("requests"), list):
                pred_requests = [x for x in parsed["requests"] if isinstance(x, dict)]
                if len(pred_requests) != len(parsed["requests"]):
                    categories.append("REQUEST_CONTRACT")
                    structural_errors.append("one or more requests are not objects")
            else:
                categories.append("REQUEST_CONTRACT")
                structural_errors.append("requests is not an array")
            pred_fallback = parsed.get("fallback")
            for index, request in enumerate(pred_requests):
                keys = set(request)
                extra_request_keys.update(keys - REQUEST_KEYS)
                missing_request_keys.update(REQUEST_KEYS - keys)
                if keys != REQUEST_KEYS:
                    categories.append("REQUEST_CONTRACT")
                    structural_errors.append(
                        f"request[{index}] extra={sorted(keys - REQUEST_KEYS)} missing={sorted(REQUEST_KEYS - keys)}"
                    )

        gold_requests = case["gold"]["requests"]
        gold_intents = [x["intent"] for x in gold_requests]
        pred_intents = [
            x.get("intent") for x in pred_requests if x.get("intent") in INTENTS
        ]
        if len(gold_requests) != len(pred_requests):
            categories.append("REQUEST_COUNT")
        if gold_intents != pred_intents:
            categories.append("INTENT")

        paired = len(gold_requests) == len(pred_requests)
        comparisons = {
            "target": paired and all(
                canonical(gold.get("target")) == canonical(pred.get("target"))
                for gold, pred in zip(gold_requests, pred_requests)
            ),
            "slots": paired and all(
                canonical(gold.get("slots")) == canonical(pred.get("slots"))
                for gold, pred in zip(gold_requests, pred_requests)
            ),
            "condition": paired and all(
                canonical(gold.get("condition")) == canonical(pred.get("condition"))
                for gold, pred in zip(gold_requests, pred_requests)
            ),
            "dependency": paired and all(
                canonical(gold.get("depends_on")) == canonical(pred.get("depends_on"))
                for gold, pred in zip(gold_requests, pred_requests)
            ),
            "fallback": normalized_ok
            and isinstance(parsed, dict)
            and canonical(case["gold"]["fallback"]) == canonical(pred_fallback),
        }
        for category, exact in comparisons.items():
            if not exact:
                categories.append(category.upper())

        extra_intents = list((Counter(pred_intents) - Counter(gold_intents)).elements())
        dangerous_extra = sorted(intent for intent in extra_intents if intent in DANGEROUS)
        must_not_hits = sorted(set(pred_intents).intersection(case.get("must_not_intents", [])))
        if dangerous_extra:
            categories.append("DANGEROUS_EXTRA")
        if must_not_hits:
            categories.append("MUST_NOT")

        categories = list(dict.fromkeys(categories))
        for category in categories:
            totals[f"category:{category}"] += 1
        for key in extra_request_keys:
            totals[f"extra_request_key:{key}"] += 1
        totals["lenient_intent_order_exact"] += gold_intents == pred_intents
        totals["lenient_full_exact"] += (
            normalized_ok
            and isinstance(parsed, dict)
            and canonical(case["gold"]) == canonical(parsed)
        )
        totals["dangerous_extra_cases"] += bool(dangerous_extra)
        totals["must_not_cases"] += bool(must_not_hits)

        case_rows.append(
            {
                "case_id": case_id,
                "impact": case["impact"]["level"],
                "complexity": case["complexity"]["level"],
                "utterance": case["utterance"],
                "strict_json": strict_ok,
                "normalized_json": normalized_ok,
                "wrapper": wrapper,
                "gold_intents": strings(gold_intents),
                "pred_intents_lenient": strings(pred_intents),
                "extra_request_keys": strings(sorted(extra_request_keys)),
                "missing_request_keys": strings(sorted(missing_request_keys)),
                "dangerous_extra_intents": strings(dangerous_extra),
                "must_not_hits": strings(must_not_hits),
                "error_categories": strings(categories),
                "structural_errors": " | ".join(structural_errors),
            }
        )

    n = totals["cases"]
    category_counts = {
        key.removeprefix("category:"): value
        for key, value in sorted(totals.items())
        if key.startswith("category:")
    }
    extra_key_counts = {
        key.removeprefix("extra_request_key:"): value
        for key, value in sorted(totals.items())
        if key.startswith("extra_request_key:")
    }
    summary = {
        "status": "DIAGNOSTIC_ONLY",
        "model_id": args.model_id,
        "cases": n,
        "prediction_rows": len(prediction_rows),
        "strict_json_rate": totals["strict_json"] / n if n else 0.0,
        "normalized_json_rate": totals["normalized_json"] / n if n else 0.0,
        "lenient_intent_order_exact_rate": totals["lenient_intent_order_exact"] / n if n else 0.0,
        "lenient_full_exact_rate": totals["lenient_full_exact"] / n if n else 0.0,
        "dangerous_extra_action_cases_lenient": totals["dangerous_extra_cases"],
        "must_not_violation_cases_lenient": totals["must_not_cases"],
        "error_category_counts": category_counts,
        "extra_request_key_counts": extra_key_counts,
        "note": (
            "Lenient fields expose errors hidden by an invalid contract. They are diagnostic only and do not replace "
            "the strict baseline scorer."
        ),
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (args.out_dir / "case_error_audit.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(case_rows[0]))
        writer.writeheader()
        writer.writerows(case_rows)
    (args.out_dir / "error_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = [
        f"# {args.model_id} gate error audit",
        "",
        "이 문서는 계약 무효 출력의 내부 의미 오류를 확인하기 위한 진단이다. 기존 strict 점수를 대체하지 않는다.",
        "",
        f"- 사례: {n}",
        f"- strict JSON: {totals['strict_json']}/{n}",
        f"- 정규화 JSON: {totals['normalized_json']}/{n}",
        f"- 계약을 무시한 의도 순서 일치: {totals['lenient_intent_order_exact']}/{n}",
        f"- 위험한 추가 행동: {totals['dangerous_extra_cases']}건",
        f"- must-not 위반: {totals['must_not_cases']}건",
        "",
        "## 오류 범주",
        "",
        "| 범주 | 사례 수 |",
        "|---|---:|",
    ]
    report.extend(f"| {key} | {value} |" for key, value in category_counts.items())
    report.extend(["", "## 추가 request 키", "", "| 키 | 사례 수 |", "|---|---:|"])
    report.extend(f"| `{key}` | {value} |" for key, value in extra_key_counts.items())
    report.extend(
        [
            "",
            "세부 사례는 `case_error_audit.csv`에서 확인한다.",
        ]
    )
    (args.out_dir / "error_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
