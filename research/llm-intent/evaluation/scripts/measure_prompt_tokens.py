from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def proxy_count(text: str) -> int:
    # Reproducible CPU proxy only. It is not a model tokenizer result.
    return len(re.findall(r"[가-힣]|[A-Za-z0-9_]+|[^\s]", text))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--tokenizer", help="Optional HF tokenizer id or local path. May require network/cache.")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    tokenizer = None
    tokenizer_error = None
    if args.tokenizer:
        try:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)
        except Exception as exc:
            tokenizer_error = f"{type(exc).__name__}: {exc}"
    rows = []
    for path in args.paths:
        text = path.read_text(encoding="utf-8")
        rows.append({
            "path": str(path), "characters": len(text), "utf8_bytes": len(text.encode("utf-8")),
            "cpu_proxy_units": proxy_count(text),
            "exact_token_count": len(tokenizer.encode(text, add_special_tokens=False)) if tokenizer else None,
        })
    if len(rows) == 2:
        base = rows[0]
        for row in rows[1:]:
            row["character_reduction_vs_first"] = 1 - row["characters"] / base["characters"]
            row["proxy_reduction_vs_first"] = 1 - row["cpu_proxy_units"] / base["cpu_proxy_units"]
            if tokenizer and base["exact_token_count"]:
                row["exact_token_reduction_vs_first"] = 1 - row["exact_token_count"] / base["exact_token_count"]
    report = {
        "tokenizer": args.tokenizer, "tokenizer_loaded": tokenizer is not None, "tokenizer_error": tokenizer_error,
        "warning": "cpu_proxy_units are not model tokens; use exact_token_count for model-specific conclusions.", "files": rows,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
