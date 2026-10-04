from __future__ import annotations

import csv
import datetime as dt
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path


MODEL_ID = "Qwen/Qwen3.5-2B"
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
MODEL_REVISION = "15852e8c16360a2fea060d615a32b45270f8a8fc"
LLAMA_COMMIT = "b04642061d183dff8504127dfbee1c1a8352682c"
SEED = 20260930
MAX_NEW_TOKENS = 220
CONTEXT_SIZE = 8192
THREADS = int(os.environ.get("KIOGUARD_THREADS", "2"))
PROMPT_VERSION = os.environ.get("KIOGUARD_PROMPT_VERSION", "v3.2")
EXPERIMENT_ID = os.environ.get("KIOGUARD_EXPERIMENT_ID", "QWEN35_2B_GGUF_CASE_REPLAY_V3")
CASE_LIMIT = int(os.environ.get("KIOGUARD_CASE_LIMIT", "0"))
VARIANTS = tuple(
    value.strip()
    for value in os.environ.get("KIOGUARD_VARIANTS", "F16,Q4_K_M,Q8_0").split(",")
    if value.strip()
)

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[4]
EVAL_ROOT = REPO_ROOT / "research" / "llm-intent" / "evaluation"
DEFAULT_PROMPT_NAME = f"prompt_{PROMPT_VERSION.replace('.', '_')}_full.txt"
PROMPT_PATH = Path(
    os.environ.get(
        "KIOGUARD_PROMPT_PATH",
        str(EVAL_ROOT / "prompts" / DEFAULT_PROMPT_NAME),
    )
)
WORK_ROOT = Path(os.environ.get("KIOGUARD_WORK_ROOT", "/content/qwen35_2b_case_replay"))
OUTPUT_ROOT = Path(
    os.environ.get(
        "KIOGUARD_OUTPUT_ROOT",
        f"/content/drive/MyDrive/KioGuard/experiments/{EXPERIMENT_ID}",
    )
)
LLAMA_ROOT = Path(os.environ.get("KIOGUARD_LLAMA_ROOT", "/content/llama.cpp"))
MODEL_ROOT = WORK_ROOT / "hf_model"
GGUF_ROOT = WORK_ROOT / "gguf"
LLAMA_BUILD = LLAMA_ROOT / "build_cpu"


def log(message: str) -> None:
    print(f"[{dt.datetime.now().isoformat(timespec='seconds')}] {message}", flush=True)


def run(command: list[str], *, cwd: Path | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
    log("$ " + " ".join(command))
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        capture_output=capture,
    )


def ensure_python_packages() -> None:
    required = ["huggingface_hub", "transformers", "sentencepiece"]
    missing = []
    for name in required:
        if importlib.util.find_spec(name) is None:
            missing.append(name)
    if missing:
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-q",
                "huggingface_hub>=0.36",
                "transformers>=5.0.0",
                "sentencepiece",
                "protobuf",
            ]
        )


def ensure_drive() -> None:
    if str(OUTPUT_ROOT).startswith("/content/drive/") and not Path("/content/drive/MyDrive").exists():
        from google.colab import drive

        drive.mount("/content/drive")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def ensure_llama_cpp() -> tuple[Path, Path]:
    if not (LLAMA_ROOT / ".git").exists():
        run(["git", "clone", "https://github.com/ggml-org/llama.cpp.git", str(LLAMA_ROOT)])
    run(["git", "fetch", "origin", LLAMA_COMMIT], cwd=LLAMA_ROOT)
    run(["git", "checkout", "--detach", LLAMA_COMMIT], cwd=LLAMA_ROOT)
    run([sys.executable, "-m", "pip", "install", "-q", "-r", str(LLAMA_ROOT / "requirements.txt")])
    run(
        [
            "cmake",
            "-S",
            str(LLAMA_ROOT),
            "-B",
            str(LLAMA_BUILD),
            "-DGGML_CUDA=OFF",
            "-DLLAMA_CURL=OFF",
            "-DCMAKE_BUILD_TYPE=Release",
        ]
    )
    run(
        [
            "cmake",
            "--build",
            str(LLAMA_BUILD),
            "--config",
            "Release",
            "-j2",
            "--target",
            "llama-cli",
            "llama-quantize",
        ]
    )
    bin_root = LLAMA_BUILD / "bin"
    cli = bin_root / "llama-cli"
    quantize = bin_root / "llama-quantize"
    if not cli.exists() or not quantize.exists():
        raise FileNotFoundError(f"llama.cpp binaries missing under {bin_root}")
    return cli, quantize


def ensure_models(quantize: Path) -> dict[str, Path]:
    from huggingface_hub import snapshot_download

    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    GGUF_ROOT.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=str(MODEL_ROOT),
        resume_download=True,
    )
    models = {
        "F16": GGUF_ROOT / "qwen35-2b-f16.gguf",
        "Q4_K_M": GGUF_ROOT / "qwen35-2b-q4_k_m.gguf",
        "Q8_0": GGUF_ROOT / "qwen35-2b-q8_0.gguf",
    }
    if not models["F16"].exists():
        run(
            [
                sys.executable,
                str(LLAMA_ROOT / "convert_hf_to_gguf.py"),
                str(MODEL_ROOT),
                "--outfile",
                str(models["F16"]),
                "--outtype",
                "f16",
            ]
        )
    if not models["Q4_K_M"].exists():
        run([str(quantize), str(models["F16"]), str(models["Q4_K_M"]), "Q4_K_M"])
    if not models["Q8_0"].exists():
        run([str(quantize), str(models["F16"]), str(models["Q8_0"]), "Q8_0"])
    return models


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def render_qwen35_user_prompt(prompt: str, chat_template: str) -> str:
    required_markers = (
        "<|im_start|>user",
        "<|im_end|>",
        "<|im_start|>assistant",
        "<think>\\n\\n</think>\\n\\n",
    )
    missing = [marker for marker in required_markers if marker not in chat_template]
    if missing:
        raise ValueError(f"Pinned Qwen3.5 chat template changed; missing markers: {missing}")
    return (
        "<|im_start|>user\n"
        + prompt
        + "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


def load_cases_and_prompts() -> tuple[list[dict], dict[str, str], str]:
    configured_paths = os.environ.get("KIOGUARD_GOLD_PATHS", "").strip()
    if configured_paths:
        gold_paths = [Path(value) for value in configured_paths.split(os.pathsep) if value]
    else:
        gold_paths = [
            EVAL_ROOT / "artifacts" / "gate_error_audit" / "qwen35_2b_v3_1" / "gate_gold.jsonl"
        ]
    prompt_path = PROMPT_PATH
    tokenizer_config_path = MODEL_ROOT / "tokenizer_config.json"
    cases: list[dict] = []
    seen_case_ids: set[str] = set()
    for gold_path in gold_paths:
        for case in load_jsonl(gold_path):
            case_id = case.get("case_id")
            if not isinstance(case_id, str):
                raise ValueError(f"Case without string case_id in {gold_path}")
            if case_id in seen_case_ids:
                raise ValueError(f"Duplicate case_id across gold inputs: {case_id}")
            seen_case_ids.add(case_id)
            cases.append(case)
    if CASE_LIMIT > 0:
        cases = cases[:CASE_LIMIT]
    prompt_prefix = prompt_path.read_text(encoding="utf-8").strip() + "\n"
    prompt_hash = hashlib.sha256(prompt_prefix.encode("utf-8")).hexdigest()
    tokenizer_config = json.loads(tokenizer_config_path.read_text(encoding="utf-8"))
    chat_template = tokenizer_config.get("chat_template")
    if not isinstance(chat_template, str):
        raise ValueError(f"chat_template missing from {tokenizer_config_path}")
    rendered: dict[str, str] = {}
    for case in cases:
        payload = {"context": case["context"], "utterance": case["utterance"]}
        prompt = prompt_prefix + "\n입력:\n" + json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        )
        rendered[case["case_id"]] = render_qwen35_user_prompt(prompt, chat_template)
    return cases, rendered, prompt_hash


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def extract_contract_json(text: str) -> str | None:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("requests"), list):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return None


def repair_missing_nullable_request_fields(text: str) -> tuple[str, list[str]]:
    """Fill only omitted request fields whose contract value is explicitly null.

    The model occasionally leaves out condition or depends_on even though their
    absence has the same meaning as null. No intent, target, slot, dependency, or
    condition value is inferred here.
    """
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return text, []
    if not isinstance(value, dict):
        return text, []
    requests = value.get("requests")
    if not isinstance(requests, list):
        return text, []
    repairs: list[str] = []
    if set(value) == {"requests"}:
        value["fallback"] = None
        repairs.append("top_level_fallback_defaulted_null")
    for index, request in enumerate(requests):
        if not isinstance(request, dict):
            continue
        for key in ("condition", "depends_on"):
            if key not in request:
                request[key] = None
                repairs.append(f"request_{index}_{key}_defaulted_null")
    if not repairs:
        return text, []
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")), repairs


def normalize_stdout(raw: str, rendered_prompt: str) -> tuple[str, list[str]]:
    text = ANSI_RE.sub("", raw).strip()
    steps: list[str] = []
    if rendered_prompt and rendered_prompt in text:
        text = text.split(rendered_prompt, 1)[1].strip()
        steps.append("prompt_echo_removed")
    for marker in ("<|im_end|>", "<|endoftext|>", "<|eot_id|>"):
        if marker in text:
            text = text.split(marker, 1)[0].strip()
            steps.append(f"suffix_removed:{marker}")
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
    if not isinstance(value, dict):
        return "top_level_not_object"
    if set(value) != {"requests", "fallback"}:
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
        target = request.get("target")
        if target is not None and not isinstance(target, str):
            return f"request_{index}_target_invalid"
        if not isinstance(request.get("slots"), dict):
            return f"request_{index}_slots_invalid"
        request_id = request.get("request_id")
        expected_id = f"r{index + 1}"
        if request_id != expected_id:
            return f"request_{index}_id_must_be_{expected_id}"
        depends_on = request.get("depends_on")
        if depends_on is not None and depends_on not in seen:
            return f"request_{index}_depends_on_invalid"
        condition = request.get("condition")
        if condition is not None:
            if not isinstance(condition, dict):
                return f"request_{index}_condition_invalid"
            if set(condition) != {"state_key", "operator", "value"}:
                return f"request_{index}_condition_keys_invalid"
            if condition.get("operator") not in {"EQ", "NE", "IN", "NOT_IN"}:
                return f"request_{index}_condition_operator_invalid"
        seen.add(request_id)
    return None


def read_completed(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {
        row["case_id"]: row
        for row in load_jsonl(path)
        if isinstance(row.get("case_id"), str) and row.get("status") == "SUCCESS"
    }


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
    run(
        [
            sys.executable,
            str(EVAL_ROOT / "scripts" / "score_predictions.py"),
            "--gold",
            str(gold_path),
            "--predictions",
            str(predictions),
            "--out-dir",
            str(score_dir),
        ]
    )
    run(
        [
            sys.executable,
            str(EVAL_ROOT / "scripts" / "score_predictions_v2.py"),
            "--gold",
            str(gold_path),
            "--predictions",
            str(predictions),
            "--out-dir",
            str(score_dir),
        ]
    )
    run(
        [
            sys.executable,
            str(EVAL_ROOT / "scripts" / "audit_gate_errors.py"),
            "--gold",
            str(gold_path),
            "--predictions",
            str(predictions),
            "--out-dir",
            str(diagnostics),
            "--model-id",
            MODEL_ID,
        ]
    )


def run_variant(
    name: str,
    model_path: Path,
    cli: Path,
    cases: list[dict],
    prompts: dict[str, str],
    prompt_hash: str,
    gold_path: Path,
) -> None:
    variant_dir = OUTPUT_ROOT / name.lower()
    variant_dir.mkdir(parents=True, exist_ok=True)
    raw_path = variant_dir / "predictions_raw.jsonl"
    normalized_path = variant_dir / "predictions_normalized.jsonl"
    scorer_path = variant_dir / "predictions.jsonl"
    completed = read_completed(scorer_path)
    log(f"{name}: resume from {len(completed)}/{len(cases)} completed cases")
    fail_fast = not completed
    generation_times = [
        float(row["generation_seconds"])
        for row in completed.values()
        if row.get("generation_seconds") is not None
    ]

    raw_handle = raw_path.open("a", encoding="utf-8")
    normalized_handle = normalized_path.open("a", encoding="utf-8")
    scorer_handle = scorer_path.open("a", encoding="utf-8")
    try:
        for index, case in enumerate(cases, 1):
            case_id = case["case_id"]
            if case_id in completed:
                continue
            command = [
                str(cli),
                "-m",
                str(model_path),
                "-p",
                prompts[case_id],
                "-n",
                str(MAX_NEW_TOKENS),
                "-c",
                str(CONTEXT_SIZE),
                "-t",
                str(THREADS),
                "--temp",
                "0",
                "--seed",
                str(SEED),
                "-ngl",
                "0",
                "--no-display-prompt",
                "--single-turn",
                "--reasoning-budget",
                "0",
                "--color",
                "off",
                "--simple-io",
            ]
            started = time.perf_counter()
            proc = subprocess.run(
                command,
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
            seconds = time.perf_counter() - started
            normalized, steps = normalize_stdout(proc.stdout, prompts[case_id])
            validation_error = contract_validation_error(normalized)
            status = "SUCCESS" if proc.returncode == 0 and validation_error is None else "ERROR"
            base = {
                "case_id": case_id,
                "status": status,
                "returncode": proc.returncode,
                "generation_seconds": seconds,
            }
            raw_row = {
                **base,
                "raw_stdout": proc.stdout,
                "raw_stderr": proc.stderr,
                "command": command,
            }
            normalized_row = {
                **base,
                "normalized_output": normalized,
                "normalization_steps": steps,
                "validation_error": validation_error,
            }
            scorer_row = {
                **base,
                "raw_output": normalized,
                "normalization_steps": steps,
                "validation_error": validation_error,
            }
            for handle, row in (
                (raw_handle, raw_row),
                (normalized_handle, normalized_row),
                (scorer_handle, scorer_row),
            ):
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
            if status == "SUCCESS":
                generation_times.append(seconds)
            log(f"{name} [{index}/{len(cases)}] {case_id} {status} {seconds:.2f}s")
            if status != "SUCCESS" and fail_fast:
                raise RuntimeError(
                    f"{name} first case {case_id} produced no valid requests JSON "
                    f"(returncode={proc.returncode}, validation_error={validation_error})"
                )
            fail_fast = False
    finally:
        raw_handle.close()
        normalized_handle.close()
        scorer_handle.close()

    latest_by_case = {
        row["case_id"]: row
        for row in load_jsonl(scorer_path)
        if isinstance(row.get("case_id"), str)
    }
    saved = [latest_by_case[case["case_id"]] for case in cases if case["case_id"] in latest_by_case]
    with scorer_path.open("w", encoding="utf-8") as handle:
        for row in saved:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "variant": name,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "llama_commit": LLAMA_COMMIT,
        "model_path": str(model_path),
        "model_bytes": model_path.stat().st_size,
        "model_sha256": file_sha256(model_path),
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_hash,
        "nullable_contract_field_repair": True,
        "case_count": len(cases),
        "prediction_rows": len(saved),
        "successful_cases": sum(row.get("status") == "SUCCESS" for row in saved),
        "mean_generation_seconds": statistics.mean(generation_times) if generation_times else None,
        "max_new_tokens": MAX_NEW_TOKENS,
        "context_size": CONTEXT_SIZE,
        "threads": THREADS,
        "seed": SEED,
        "temperature": 0,
        "gpu_layers": 0,
        "platform": platform.platform(),
        "python": sys.version,
    }
    (variant_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    score_variant(variant_dir, gold_path)


def bool_value(value: str) -> bool:
    return value.strip().lower() == "true"


def build_comparison() -> None:
    summaries = {}
    case_scores: dict[str, dict[str, dict]] = {}
    for variant in VARIANTS:
        folder = OUTPUT_ROOT / variant.lower()
        summaries[variant] = json.loads(
            (folder / "scores" / "summary_v2.json").read_text(encoding="utf-8")
        )
        with (folder / "scores" / "case_scores_v2.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            case_scores[variant] = {row["case_id"]: row for row in csv.DictReader(handle)}

    baseline = VARIANTS[0]
    case_ids = list(case_scores[baseline])
    rows = []
    for case_id in case_ids:
        base_score = case_scores[baseline][case_id]
        base_exact = bool_value(base_score["full_exact"])
        row = {"case_id": case_id, "impact": base_score["impact"]}
        exact_values = []
        for variant in VARIANTS:
            score = case_scores[variant][case_id]
            exact = bool_value(score["full_exact"])
            key = variant.lower()
            exact_values.append(exact)
            row[f"{key}_full_exact"] = exact
            row[f"{key}_mismatches"] = score["mismatch_categories"]
            row[f"{key}_contract_valid"] = bool_value(score["contract_valid"])
            if variant != baseline:
                row[f"{key}_regression"] = base_exact and not exact
                row[f"{key}_recovery"] = not base_exact and exact
        row["common_failure"] = not any(exact_values)
        rows.append(row)

    fields = list(rows[0])
    with (OUTPUT_ROOT / "case_level_comparison.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT_ROOT / "case_level_comparison.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    attribution = {"common_failure_cases": sum(row["common_failure"] for row in rows)}
    for variant in VARIANTS[1:]:
        key = variant.lower()
        attribution[f"{key}_regression_cases"] = sum(row[f"{key}_regression"] for row in rows)
        attribution[f"{key}_recovery_cases"] = sum(row[f"{key}_recovery"] for row in rows)
    aggregate = {
        "experiment_id": EXPERIMENT_ID,
        "status": "COMPLETE",
        "variants": summaries,
        "case_attribution": attribution,
    }
    (OUTPUT_ROOT / "aggregate_comparison.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    log(json.dumps(aggregate, ensure_ascii=False, indent=2))


def main() -> None:
    ensure_drive()
    ensure_python_packages()
    cli, quantize = ensure_llama_cpp()
    models = ensure_models(quantize)
    cases, prompts, prompt_hash = load_cases_and_prompts()
    gold_path = OUTPUT_ROOT / "gate_gold.jsonl"
    with gold_path.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")

    status_path = OUTPUT_ROOT / "run_status.json"
    try:
        for variant in VARIANTS:
            status_path.write_text(
                json.dumps(
                    {
                        "status": "RUNNING",
                        "current_variant": variant,
                        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            run_variant(
                variant,
                models[variant],
                cli,
                cases,
                prompts,
                prompt_hash,
                gold_path,
            )
        build_comparison()
        status = {"status": "COMPLETE", "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    except Exception as exc:
        status = {
            "status": "ERROR",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        raise
    finally:
        status_path.write_text(
            json.dumps(status, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
