#!/usr/bin/env python3
"""BizSQL headroom probe — two arms gate the full training run.

Arm A (target baseline): the local 7B with the weak-init skill over the train
(or val) split, via the same rollout path the trainer uses (``run_batch``).
Arm B (strong-model ceiling): the SAME weak prompt through a strong model
(the DeepSeek optimizer client) — the ENGINEERED-WIN GUARDRAIL: if a strong model
can't clear ~90%, the dataset is ill-posed (ambiguous / over-hard) and you fix
the data (Phase 8), you do NOT train.

Reports Arm A accuracy, Arm B ceiling, dumps every Arm-A failure, and auto-buckets
failures into coarse procedural-vs-capability classes. The auto-buckets are a
STARTING POINT — the actual gate is a human hand-labeling ~20 sampled failures.
Test split is left untouched.

Usage
-----
    python scripts/probe_bizsql_headroom.py --split-dir data/bizsql_split_s42 --split train

Requires ``.env.local-pilot`` (auto-loaded) + Ollama up + DeepSeek key (Arm B).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _load_env_file(path: str) -> None:
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ[key.strip()] = val.strip()


def _configure_backends() -> str:
    from skillopt.model import (
        configure_optimizer_openai,
        configure_qwen_chat,
        set_optimizer_backend,
        set_optimizer_deployment,
        set_target_backend,
        set_target_deployment,
    )

    qwen_base = os.environ.get("QWEN_CHAT_BASE_URL", "").strip()
    qwen_key = os.environ.get("QWEN_CHAT_API_KEY", "").strip()
    target = os.environ.get("TARGET_DEPLOYMENT", "").strip()
    if not all([qwen_base, qwen_key, target]):
        print("ERROR: QWEN_CHAT_* / TARGET_DEPLOYMENT missing; load .env.local-pilot", file=sys.stderr)
        raise SystemExit(2)

    base_url = os.environ.get("OPTIMIZER_OPENAI_BASE_URL", "").strip()
    api_key = os.environ.get("OPTIMIZER_OPENAI_API_KEY", "").strip()
    strong_model = os.environ.get("OPTIMIZER_DEPLOYMENT", "deepseek-v4-pro").strip()
    set_optimizer_backend("openai_chat")
    if base_url and api_key:
        configure_optimizer_openai(base_url=base_url, api_key=api_key)
    set_optimizer_deployment(strong_model)
    set_target_backend("qwen_chat")
    configure_qwen_chat(base_url=qwen_base, api_key=qwen_key, enable_thinking=False)
    set_target_deployment(target)
    return strong_model


def _bucket(detail: str, predicted_sql: str) -> str:
    """Coarse triage class from the failure signature. Procedural unless proven capability."""
    d = (detail or "").lower()
    if "timeout" in d:
        return "timeout"
    if not predicted_sql.strip() or "only select" in d or "multiple statements" in d or "write/ddl" in d:
        return "extraction_format"  # procedural (no/!SELECT/multi-statement)
    if "no such column" in d or "no such table" in d:
        return "wrong_column_table"  # procedural (schema grounding)
    if "syntax error" in d or "operationalerror" in d:
        return "sql_syntax"  # procedural
    if "wrong result" in d:
        return "wrong_result"  # runs clean but wrong rows — mixed; HUMAN splits filter/join/logic
    return "other"


# wrong_result is intentionally NOT auto-counted as procedural: it conflates a
# dropped status filter / bad join (procedural) with genuinely-wrong intent
# (capability). The human label on the ~20 sample decides its split.
_PROCEDURAL = {"extraction_format", "wrong_column_table", "sql_syntax"}


def _run_arm_b(items: list[dict], strong_model: str) -> tuple[float, int]:
    """Strong-model ceiling: same weak prompt, evaluated by execution accuracy."""
    from skillopt.envs.bizsql.evaluator import evaluate
    from skillopt.envs.bizsql.rollout import _build_system, _build_user
    from skillopt.model import chat_optimizer

    weak = "Write a SQL query that answers the question. Output only SQL in a code block."
    system = _build_system(weak)
    correct = 0
    for i, it in enumerate(items):
        try:
            resp, _ = chat_optimizer(system, _build_user(it), max_completion_tokens=512, retries=3)
        except Exception as e:  # noqa: BLE001
            print(f"  [armB] {it.get('id')} call failed: {e}", file=sys.stderr)
            continue
        if evaluate(resp, it)["em"] == 1.0:
            correct += 1
        if (i + 1) % 20 == 0:
            print(f"  [armB] {i + 1}/{len(items)} ceiling so far {correct}/{i + 1}", flush=True)
    acc = correct / len(items) if items else 0.0
    return acc, correct


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--split-dir", default="data/bizsql_split_s42")
    p.add_argument("--split", default="train", choices=["train", "val"])  # NOT test
    p.add_argument("--skill", default="skillopt/envs/bizsql/skills/initial-weak.md")
    p.add_argument("--out-dir", default="outputs/bizsql_probe")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--sql-timeout", type=int, default=5)
    p.add_argument("--skip-arm-b", action="store_true", help="skip the strong-model ceiling pass")
    p.add_argument("--target", default="", help="overrides TARGET_DEPLOYMENT from .env")
    args = p.parse_args()

    _load_env_file(os.path.join(_PROJECT_ROOT, ".env.local-pilot"))
    if args.target.strip():
        os.environ["TARGET_DEPLOYMENT"] = args.target.strip()
    strong_model = _configure_backends()

    from skillopt.envs.bizsql.batch_runner import run_batch
    from skillopt.envs.bizsql.dataloader import BizsqlDataLoader

    loader = BizsqlDataLoader(split_mode="split_dir", split_dir=args.split_dir)
    loader.setup({})
    items = getattr(loader, f"{args.split}_items")
    with open(args.skill, encoding="utf-8") as f:
        skill_text = f.read()

    print(f"[probe] Arm A (7B): skill={args.skill} split={args.split} ({len(items)} items)")
    os.makedirs(args.out_dir, exist_ok=True)
    results = run_batch(
        items=items, out_root=args.out_dir, skill_content=skill_text,
        max_turns=1, workers=args.workers, sql_timeout=args.sql_timeout,
    )

    total = len(results)
    correct = sum(1 for r in results if r.get("hard"))
    errors = sum(1 for r in results if not r.get("agent_ok"))
    arm_a = correct / total if total else 0.0

    by_id = {str(it["id"]): it for it in items}
    failures: list[dict] = []
    buckets: dict[str, int] = {}
    for r in results:
        if r.get("hard"):
            continue
        it = by_id.get(str(r.get("id")), {})
        b = _bucket(r.get("fail_reason", ""), r.get("predicted_sql", ""))
        buckets[b] = buckets.get(b, 0) + 1
        failures.append({
            "id": r.get("id"),
            "question": it.get("question", ""),
            "difficulty": it.get("difficulty", ""),
            "predicted_sql": r.get("predicted_sql", ""),
            "gold_sql": it.get("gold_sql", ""),
            "detail": r.get("fail_reason", ""),
            "bucket": b,
        })

    proc = sum(v for k, v in buckets.items() if k in _PROCEDURAL)
    proc_share = proc / total if total else 0.0

    arm_b, arm_b_correct = (None, None)
    if not args.skip_arm_b:
        print(f"[probe] Arm B (strong ceiling, {strong_model}) over {len(items)} items ...")
        arm_b, arm_b_correct = _run_arm_b(items, strong_model)

    out = {
        "split_dir": args.split_dir,
        "split": args.split,
        "target": os.environ.get("TARGET_DEPLOYMENT", "").strip(),
        "strong_model": strong_model,
        "arm_a_baseline": arm_a,
        "arm_a_correct": correct,
        "arm_b_ceiling": arm_b,
        "arm_b_correct": arm_b_correct,
        "total": total,
        "errors": errors,
        "buckets": buckets,
        "auto_procedural_count": proc,
        "auto_procedural_share": proc_share,
        "failures": failures,
    }
    with open(os.path.join(args.out_dir, "probe_failures.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[probe] Arm A baseline = {arm_a:.4f} ({correct}/{total}, errors={errors})")
    if arm_b is not None:
        print(f"[probe] Arm B ceiling  = {arm_b:.4f} ({arm_b_correct}/{total})  (gate wants >= ~90%)")
    print(f"[probe] failure buckets: {buckets}")
    print(f"[probe] AUTO procedural share = {proc_share:.1%} (excludes wrong_result; HUMAN labels ~20)")
    print(f"[probe] wrote {os.path.join(args.out_dir, 'probe_failures.json')}")
    if total == 0 or errors == total:
        print("[probe] ERROR: no successful rollouts — check Ollama is up and the model is pulled.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
