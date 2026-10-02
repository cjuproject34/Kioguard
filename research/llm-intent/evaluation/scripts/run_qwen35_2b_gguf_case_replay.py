from __future__ import annotations

import csv
import datetime as dt
import hashlib
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
MODEL_REVISION = "15852e8c16360a2fea060d615a32b45270f8a8fc"
LLAMA_COMMIT = "b04642061d183dff8504127dfbee1c1a8352682c"
SEED = 20260930
MAX_NEW_TOKENS = 220
CONTEXT_SIZE = 8192
THREADS = int(os.environ.get("KIOGUARD_THREADS", "2"))

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[4]
EVAL_ROOT = REPO_ROOT / "research" / "llm-intent" / "evaluation"
WORK_ROOT = Path(os.environ.get("KIOGUARD_WORK_ROOT", "/content/qwen35_2b_case_replay"))
OUTPUT_ROOT = Path(
    os.environ.get(
        "KIOGUARD_OUTPUT_ROOT",
        "/content/drive/MyDrive/KioGuard/experiments/QWEN35_2B_GGUF_CASE_REPLAY_V1",
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
        try:
            __import__(name)
        except ImportError:
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


def load_cases_and_prompts() -> tuple[list[dict], dict[str, str], str]:
    from transformers import AutoTokenizer

    gold_path = EVAL_ROOT / "artifacts" / "gate_error_audit" / "qwen35_2b_v3_1" / "gate_gold.jsonl"
    prompt_path = EVAL_ROOT / "prompts" / "prompt_v3_1_full.txt"
    cases = load_jsonl(gold_path)
    prompt_prefix = prompt_path.read_text(encoding="utf-8").strip() + "\n"
    prompt_hash = hashlib.sha256(prompt_prefix.encode("utf-8")).hexdigest()
    tokenizer = AutoTokenizer.from_pretrained(
        str(MODEL_ROOT),
        local_files_only=True,
        trust_remote_code=True,
    )
    rendered: dict[str, str] = {}
    for case in cases:
        payload = {"context": case["context"], "utterance": case["utterance"]}
        prompt = prompt_prefix + "\n입력:\n" + json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        )
        messages = [{"role": "user", "content": prompt}]
        try:
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        rendered[case["case_id"]] = text
    return cases, rendered, prompt_hash


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


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
    return text, steps


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
                "--simple-io",
            ]
            started = time.perf_counter()
            proc = subprocess.run(command, text=True, capture_output=True)
            seconds = time.perf_counter() - started
            normalized, steps = normalize_stdout(proc.stdout, prompts[case_id])
            status = "SUCCESS" if proc.returncode == 0 else "ERROR"
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
            }
            scorer_row = {
                **base,
                "raw_output": normalized,
                "normalization_steps": steps,
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
        "experiment_id": "QWEN35_2B_GGUF_CASE_REPLAY_V1",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "variant": name,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "llama_commit": LLAMA_COMMIT,
        "model_path": str(model_path),
        "model_bytes": model_path.stat().st_size,
        "model_sha256": file_sha256(model_path),
        "prompt_version": "v3.1",
        "prompt_sha256": prompt_hash,
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
    variants = ["F16", "Q4_K_M", "Q8_0"]
    summaries = {}
    case_scores: dict[str, dict[str, dict]] = {}
    for variant in variants:
        folder = OUTPUT_ROOT / variant.lower()
        summaries[variant] = json.loads(
            (folder / "scores" / "summary_v2.json").read_text(encoding="utf-8")
        )
        with (folder / "scores" / "case_scores_v2.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            case_scores[variant] = {row["case_id"]: row for row in csv.DictReader(handle)}

    case_ids = list(case_scores["F16"])
    rows = []
    for case_id in case_ids:
        f16 = case_scores["F16"][case_id]
        q4 = case_scores["Q4_K_M"][case_id]
        q8 = case_scores["Q8_0"][case_id]
        f16_exact = bool_value(f16["full_exact"])
        q4_exact = bool_value(q4["full_exact"])
        q8_exact = bool_value(q8["full_exact"])
        rows.append(
            {
                "case_id": case_id,
                "impact": f16["impact"],
                "f16_full_exact": f16_exact,
                "q4_full_exact": q4_exact,
                "q8_full_exact": q8_exact,
                "common_failure": not f16_exact and not q4_exact and not q8_exact,
                "q4_only_regression": f16_exact and not q4_exact,
                "q8_only_regression": f16_exact and not q8_exact,
                "q4_recovery": not f16_exact and q4_exact,
                "q8_recovery": not f16_exact and q8_exact,
                "f16_mismatches": f16["mismatch_categories"],
                "q4_mismatches": q4["mismatch_categories"],
                "q8_mismatches": q8["mismatch_categories"],
                "f16_contract_valid": bool_value(f16["contract_valid"]),
                "q4_contract_valid": bool_value(q4["contract_valid"]),
                "q8_contract_valid": bool_value(q8["contract_valid"]),
            }
        )

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
    aggregate = {
        "experiment_id": "QWEN35_2B_GGUF_CASE_REPLAY_V1",
        "status": "COMPLETE",
        "variants": summaries,
        "case_attribution": {
            "common_failure_cases": sum(row["common_failure"] for row in rows),
            "q4_only_regression_cases": sum(row["q4_only_regression"] for row in rows),
            "q8_only_regression_cases": sum(row["q8_only_regression"] for row in rows),
            "q4_recovery_cases": sum(row["q4_recovery"] for row in rows),
            "q8_recovery_cases": sum(row["q8_recovery"] for row in rows),
        },
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
        for variant in ("F16", "Q4_K_M", "Q8_0"):
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
