from __future__ import annotations

"""Run the 20-case KioGuard gate against local Gemma 4 E2B GGUF variants.

The runner is resumable: only contract-valid SUCCESS rows are skipped.  Raw
stdout, normalized output, scorer input, manifests, diagnostics, and aggregate
comparisons are preserved separately for every precision variant.
"""

import csv
import datetime as dt
import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path


MODEL_ID = "google/gemma-4-E2B-it"
MODEL_REVISION = "3e22461f65e89153144f8adb70e3b8c2cc9845a7"
LLAMA_COMMIT = "7fe450e19"
SEED = 20260930
MAX_NEW_TOKENS = int(os.environ.get("KIOGUARD_MAX_NEW_TOKENS", "220"))
CONTEXT_SIZE = int(os.environ.get("KIOGUARD_CONTEXT_SIZE", "4096"))
THREADS = int(os.environ.get("KIOGUARD_THREADS", "12"))
PROMPT_VERSION = os.environ.get("KIOGUARD_PROMPT_VERSION", "v3.2")
EXPERIMENT_ID = os.environ.get(
    "KIOGUARD_EXPERIMENT_ID", "GEMMA4_E2B_GGUF_CASE_REPLAY_V1"
)

INTENTS = {
    "SELECT", "MODIFY", "FULFILLMENT", "PAYMENT_METHOD", "RECEIPT",
    "BENEFIT_CONTROL", "NAVIGATE", "CANCEL", "GUIDE", "INFO",
    "UI_CONTROL", "HELP", "COMMIT_REQUEST", "RESET",
}
FALLBACKS = {
    "ASK_SCREEN_TARGET", "ASK_GUIDANCE_NEED", "ASK_TARGET", "ASK_CONTEXT",
    "ASK_REFERENCE", "ASK_INPUT_REPEAT", "ASK_SCOPE", "OUT_OF_SCOPE", "NO_ACTION",
}
REQUEST_KEYS = {"request_id", "intent", "target", "slots", "condition", "depends_on"}

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[4]
EVAL_ROOT = REPO_ROOT / "research" / "llm-intent" / "evaluation"
DEFAULT_PROMPT_NAME = f"prompt_{PROMPT_VERSION.replace('.', '_')}_full.txt"
PROMPT_PATH = Path(os.environ.get("KIOGUARD_PROMPT_PATH", EVAL_ROOT / "prompts" / DEFAULT_PROMPT_NAME))
WORK_ROOT = Path(os.environ.get("KIOGUARD_WORK_ROOT", r"D:\KioGuard\gemma4_e2b_ptq"))
MODEL_DIR = Path(os.environ.get("KIOGUARD_MODEL_DIR", WORK_ROOT / "models"))
LLAMA_BIN = Path(os.environ.get("KIOGUARD_LLAMA_BIN", WORK_ROOT / "tools" / "llama-b11146"))
OUTPUT_ROOT = Path(os.environ.get("KIOGUARD_OUTPUT_ROOT", WORK_ROOT / "experiments" / EXPERIMENT_ID))
CASE_LIMIT = int(os.environ.get("KIOGUARD_CASE_LIMIT", "0"))
VARIANTS = tuple(
    value.strip() for value in os.environ.get("KIOGUARD_VARIANTS", "BF16,Q4_K_M,Q8_0").split(",")
    if value.strip()
)


def log(message: str) -> None:
    print(f"[{dt.datetime.now().isoformat(timespec='seconds')}] {message}", flush=True)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    log("$ " + " ".join(command))
    return subprocess.run(command, check=True, text=True)


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def ensure_runtime() -> tuple[Path, dict[str, Path]]:
    cli = LLAMA_BIN / ("llama-completion.exe" if os.name == "nt" else "llama-completion")
    models = {
        "BF16": MODEL_DIR / "gemma-4-E2B-it-bf16.gguf",
        "Q4_K_M": MODEL_DIR / "gemma-4-E2B-it-q4_k_m.gguf",
        "Q8_0": MODEL_DIR / "gemma-4-E2B-it-q8_0.gguf",
    }
    missing = [str(path) for path in [cli, *(models[name] for name in VARIANTS)] if not path.exists()]
    if missing:
        raise FileNotFoundError("Required local artifact missing: " + ", ".join(missing))
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    return cli, models


def load_cases_and_prompts() -> tuple[list[dict], dict[str, str], str]:
    gold_path = EVAL_ROOT / "artifacts" / "gate_error_audit" / "qwen35_2b_v3_1" / "gate_gold.jsonl"
    cases = load_jsonl(gold_path)
    if CASE_LIMIT > 0:
        cases = cases[:CASE_LIMIT]
    prompt_prefix = PROMPT_PATH.read_text(encoding="utf-8").strip() + "\n"
    prompt_hash = hashlib.sha256(prompt_prefix.encode("utf-8")).hexdigest()
    prompts: dict[str, str] = {}
    for case in cases:
        payload = {"context": case["context"], "utterance": case["utterance"]}
        prompt = prompt_prefix + "\n입력:\n" + json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        )
        # Exact single-user, add_generation_prompt rendering from the pinned
        # Gemma 4 chat_template.jinja with enable_thinking=false.  Passing the
        # already-rendered prompt to llama-completion avoids llama-cli's
        # interactive Gemma 4 path, which can stall on this long prompt.
        prompts[case["case_id"]] = (
            "<bos><|turn>user\n" + prompt.strip() + "<turn|>\n<|turn>model\n"
        )
    return cases, prompts, prompt_hash


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def extract_contract_json(text: str) -> str | None:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("requests"), list):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return None


def repair_missing_nullable_request_fields(text: str) -> tuple[str, list[str]]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return text, []
    requests = value.get("requests") if isinstance(value, dict) else None
    if not isinstance(requests, list):
        return text, []
    repairs: list[str] = []
    for index, request in enumerate(requests):
        if not isinstance(request, dict):
            continue
        for key in ("condition", "depends_on"):
            if key not in request:
                request[key] = None
                repairs.append(f"request_{index}_{key}_defaulted_null")
    if repairs:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text, repairs


def normalize_stdout(raw: str) -> tuple[str, list[str]]:
    text = ANSI_RE.sub("", raw).strip()
    steps: list[str] = []
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.I | re.S)
    if fence:
        text = fence.group(1).strip()
        steps.append("markdown_code_fence_removed")
    contract_json = extract_contract_json(text)
    if contract_json is not None:
        text = contract_json
        steps.append("contract_json_extracted")
    text, repairs = repair_missing_nullable_request_fields(text)
    steps.extend(repairs)
    return text, steps


def contract_validation_error(text: str) -> str | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"invalid_json:{exc.msg}"
    if not isinstance(value, dict) or set(value) != {"requests", "fallback"}:
        return "top_level_keys_invalid"
    requests = value.get("requests")
    if not isinstance(requests, list):
        return "requests_not_list"
    fallback = value.get("fallback")
    if fallback is not None:
        if not isinstance(fallback, dict):
            return "fallback_not_object_or_null"
        if set(fallback) - {"type", "field"}:
            return "fallback_extra_keys"
        if fallback.get("type") not in FALLBACKS:
            return "fallback_type_invalid"
        if "field" in fallback and not isinstance(fallback["field"], str):
            return "fallback_field_invalid"
    seen: set[str] = set()
    for index, request in enumerate(requests):
        if not isinstance(request, dict):
            return f"request_{index}_not_object"
        if set(request) != REQUEST_KEYS:
            return f"request_{index}_keys_invalid"
        if request.get("intent") not in INTENTS:
            return f"request_{index}_intent_invalid"
        if request.get("target") is not None and not isinstance(request["target"], str):
            return f"request_{index}_target_invalid"
        if not isinstance(request.get("slots"), dict):
            return f"request_{index}_slots_invalid"
        request_id = request.get("request_id")
        if request_id != f"r{index + 1}":
            return f"request_{index}_id_invalid"
        depends_on = request.get("depends_on")
        if depends_on is not None and depends_on not in seen:
            return f"request_{index}_depends_on_invalid"
        condition = request.get("condition")
        if condition is not None:
            if not isinstance(condition, dict) or set(condition) != {"state_key", "operator", "value"}:
                return f"request_{index}_condition_invalid"
            if condition.get("operator") not in {"EQ", "NE", "IN", "NOT_IN"}:
                return f"request_{index}_condition_operator_invalid"
        seen.add(request_id)
    return None


def read_latest_rows(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {row["case_id"]: row for row in load_jsonl(path) if isinstance(row.get("case_id"), str)}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def score_variant(variant_dir: Path, gold_path: Path) -> None:
    predictions = variant_dir / "predictions.jsonl"
    score_dir = variant_dir / "scores"
    diagnostics = variant_dir / "diagnostics"
    run([sys.executable, str(EVAL_ROOT / "scripts" / "score_predictions.py"), "--gold", str(gold_path), "--predictions", str(predictions), "--out-dir", str(score_dir)])
    run([sys.executable, str(EVAL_ROOT / "scripts" / "score_predictions_v2.py"), "--gold", str(gold_path), "--predictions", str(predictions), "--out-dir", str(score_dir)])
    run([sys.executable, str(EVAL_ROOT / "scripts" / "audit_gate_errors.py"), "--gold", str(gold_path), "--predictions", str(predictions), "--out-dir", str(diagnostics), "--model-id", MODEL_ID])


def run_variant(name: str, model_path: Path, cli: Path, cases: list[dict], prompts: dict[str, str], prompt_hash: str, gold_path: Path) -> None:
    variant_dir = OUTPUT_ROOT / name.lower()
    variant_dir.mkdir(parents=True, exist_ok=True)
    raw_path = variant_dir / "predictions_raw.jsonl"
    normalized_path = variant_dir / "predictions_normalized.jsonl"
    scorer_path = variant_dir / "predictions.jsonl"
    latest = read_latest_rows(scorer_path)
    completed = {case_id: row for case_id, row in latest.items() if row.get("status") == "SUCCESS"}
    log(f"{name}: resume from {len(completed)}/{len(cases)} contract-valid cases")
    generation_times = [float(row["generation_seconds"]) for row in completed.values() if row.get("generation_seconds") is not None]

    with raw_path.open("a", encoding="utf-8") as raw_handle, normalized_path.open("a", encoding="utf-8") as normalized_handle, scorer_path.open("a", encoding="utf-8") as scorer_handle:
        for index, case in enumerate(cases, 1):
            case_id = case["case_id"]
            if case_id in completed:
                continue
            command = [
                str(cli), "-m", str(model_path), "-p", prompts[case_id],
                "-n", str(MAX_NEW_TOKENS), "-c", str(CONTEXT_SIZE), "-t", str(THREADS),
                "--temp", "0", "--seed", str(SEED), "-ngl", "0",
                "--no-display-prompt", "-no-cnv",
                "--color", "off", "--simple-io",
            ]
            started = time.perf_counter()
            proc = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace")
            seconds = time.perf_counter() - started
            normalized, steps = normalize_stdout(proc.stdout)
            validation_error = contract_validation_error(normalized)
            status = "SUCCESS" if proc.returncode == 0 and validation_error is None else "ERROR"
            base = {"case_id": case_id, "status": status, "returncode": proc.returncode, "generation_seconds": seconds}
            rows = (
                (raw_handle, {**base, "raw_stdout": proc.stdout, "raw_stderr": proc.stderr, "command": command}),
                (normalized_handle, {**base, "normalized_output": normalized, "normalization_steps": steps, "validation_error": validation_error}),
                (scorer_handle, {**base, "raw_output": normalized, "normalization_steps": steps, "validation_error": validation_error}),
            )
            for handle, row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
            if status == "SUCCESS":
                generation_times.append(seconds)
            log(f"{name} [{index}/{len(cases)}] {case_id} {status} {seconds:.2f}s")
            if index == 1 and status != "SUCCESS" and not completed:
                raise RuntimeError(f"{name} preflight failed: returncode={proc.returncode}, validation_error={validation_error}")

    latest = read_latest_rows(scorer_path)
    saved = [latest[case["case_id"]] for case in cases if case["case_id"] in latest]
    with scorer_path.open("w", encoding="utf-8") as handle:
        for row in saved:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {
        "experiment_id": EXPERIMENT_ID, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "variant": name, "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
        "llama_commit": LLAMA_COMMIT, "model_path": str(model_path), "model_bytes": model_path.stat().st_size,
        "model_sha256": file_sha256(model_path), "prompt_version": PROMPT_VERSION, "prompt_sha256": prompt_hash,
        "reasoning": "off (native Gemma 4 template pre-rendered)", "nullable_contract_field_repair": True, "case_count": len(cases),
        "prediction_rows": len(saved), "successful_cases": sum(row.get("status") == "SUCCESS" for row in saved),
        "mean_generation_seconds": statistics.mean(generation_times) if generation_times else None,
        "max_new_tokens": MAX_NEW_TOKENS, "context_size": CONTEXT_SIZE, "threads": THREADS,
        "seed": SEED, "temperature": 0, "gpu_layers": 0, "platform": platform.platform(), "python": sys.version,
    }
    (variant_dir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    score_variant(variant_dir, gold_path)


def bool_value(value: str) -> bool:
    return value.strip().lower() == "true"


def build_comparison() -> None:
    summaries: dict[str, dict] = {}
    case_scores: dict[str, dict[str, dict]] = {}
    for variant in VARIANTS:
        folder = OUTPUT_ROOT / variant.lower()
        summaries[variant] = json.loads((folder / "scores" / "summary_v2.json").read_text(encoding="utf-8"))
        with (folder / "scores" / "case_scores_v2.csv").open(encoding="utf-8-sig", newline="") as handle:
            case_scores[variant] = {row["case_id"]: row for row in csv.DictReader(handle)}
    baseline = VARIANTS[0]
    rows: list[dict] = []
    for case_id in case_scores[baseline]:
        row: dict = {"case_id": case_id, "impact": case_scores[baseline][case_id]["impact"]}
        base_exact = bool_value(case_scores[baseline][case_id]["full_exact"])
        all_exact: list[bool] = []
        for variant in VARIANTS:
            score = case_scores[variant][case_id]
            exact = bool_value(score["full_exact"])
            all_exact.append(exact)
            key = variant.lower()
            row[f"{key}_full_exact"] = exact
            row[f"{key}_mismatches"] = score["mismatch_categories"]
            row[f"{key}_contract_valid"] = bool_value(score["contract_valid"])
            if variant != baseline:
                row[f"{key}_regression"] = base_exact and not exact
                row[f"{key}_recovery"] = not base_exact and exact
        row["common_failure"] = not any(all_exact)
        rows.append(row)
    fields = list(rows[0])
    with (OUTPUT_ROOT / "case_level_comparison.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    (OUTPUT_ROOT / "case_level_comparison.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    attribution = {"common_failure_cases": sum(row["common_failure"] for row in rows)}
    for variant in VARIANTS[1:]:
        key = variant.lower()
        attribution[f"{key}_regression_cases"] = sum(row[f"{key}_regression"] for row in rows)
        attribution[f"{key}_recovery_cases"] = sum(row[f"{key}_recovery"] for row in rows)
    aggregate = {"experiment_id": EXPERIMENT_ID, "status": "COMPLETE", "variants": summaries, "case_attribution": attribution}
    (OUTPUT_ROOT / "aggregate_comparison.json").write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(json.dumps(aggregate, ensure_ascii=False, indent=2))


def main() -> None:
    cli, models = ensure_runtime()
    cases, prompts, prompt_hash = load_cases_and_prompts()
    gold_path = OUTPUT_ROOT / "gate_gold.jsonl"
    with gold_path.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
    status_path = OUTPUT_ROOT / "run_status.json"
    try:
        for variant in VARIANTS:
            status_path.write_text(json.dumps({"status": "RUNNING", "current_variant": variant, "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            run_variant(variant, models[variant], cli, cases, prompts, prompt_hash, gold_path)
        build_comparison()
        status = {"status": "COMPLETE", "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    except Exception as exc:
        status = {"status": "ERROR", "error_type": type(exc).__name__, "error": str(exc), "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        raise
    finally:
        status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
