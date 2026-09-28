from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def find_summary(run: Path) -> Path | None:
    candidates = [run / "scores" / "summary.json", run / "summary.json"]
    return next((p for p in candidates if p.exists()), None)


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate existing result summaries without modifying run directories.")
    parser.add_argument("--result-root", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    rows = []
    for run in sorted(p for p in args.result_root.iterdir() if p.is_dir() and p.resolve() != args.out_dir.resolve()):
        summary_path = find_summary(run)
        if not summary_path: continue
        try: summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception: continue
        metadata = {}
        for name in ["metadata.json", "run_metadata.json"]:
            path = run / name
            if path.exists():
                try: metadata = json.loads(path.read_text(encoding="utf-8")); break
                except Exception: pass
        rows.append({
            "run": run.name,
            "model_id": metadata.get("model_id", summary.get("model_id", "")),
            "cases": summary.get("cases"),
            "contract_valid_rate": summary.get("contract_valid_rate"),
            "exact_semantic_match_rate": summary.get("exact_semantic_match_rate"),
            "macro_intent_f1": summary.get("macro_intent_f1"),
            "fallback_exact_rate": summary.get("fallback_exact_rate"),
            "high_impact_exact_rate": summary.get("high_impact_exact_rate"),
            "dangerous_extra_action_cases": summary.get("dangerous_extra_action_cases"),
            "must_not_violation_cases": summary.get("must_not_violation_cases"),
            "summary_path": str(summary_path),
        })
    args.out_dir.mkdir(parents=True, exist_ok=True)
    output = args.out_dir / "existing_results_comparison.csv"
    if rows:
        with output.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    report = {
        "runs_found": len(rows), "source_root": str(args.result_root), "source_modified": False,
        "output": str(output), "note": "Missing fields remain blank; no score is inferred.",
    }
    (args.out_dir / "existing_results_analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
