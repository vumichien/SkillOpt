#!/usr/bin/env python3
"""Zero-shot eval: run one skill markdown on one mcqa split, print accuracy.

Reuses the trainer's rollout path (``run_batch``) so cross-dataset transfer
numbers are produced by exactly the same evaluator the training loop uses — no
re-implementation of scoring. Deterministic eval (target temperature comes from
the environment; ``.env.local-pilot`` sets it to 0).

Usage
-----
    python scripts/eval_skill_on_dataset.py \
        --skill outputs/mcqa_local_pilot_v3/best_skill.md \
        --split-dir data/mcqa_siqa_split \
        --split test \
        --out-dir outputs/transfer/v3-on-siqa

Requires ``.env.local-pilot`` (auto-loaded from the project root if present).
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
    """Minimal .env loader (mirrors run_local_pilot.ps1): file values WIN over the
    ambient shell, so a stale exported QWEN_CHAT_TEMPERATURE can't break temp=0 eval."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ[key.strip()] = val.strip()


def _configure_backends() -> None:
    from skillopt.model import (
        configure_optimizer_openai,
        configure_qwen_chat,
        set_optimizer_backend,
        set_optimizer_deployment,
        set_target_backend,
        set_target_deployment,
    )

    base_url = os.environ.get("OPTIMIZER_OPENAI_BASE_URL", "").strip()
    api_key = os.environ.get("OPTIMIZER_OPENAI_API_KEY", "").strip()
    qwen_base = os.environ.get("QWEN_CHAT_BASE_URL", "").strip()
    qwen_key = os.environ.get("QWEN_CHAT_API_KEY", "").strip()
    target = os.environ.get("TARGET_DEPLOYMENT", "").strip()
    if not all([qwen_base, qwen_key, target]):
        print("ERROR: QWEN_CHAT_* / TARGET_DEPLOYMENT missing; load .env.local-pilot", file=sys.stderr)
        raise SystemExit(2)

    # Optimizer is unused for pure eval but configured for parity with the trainer.
    set_optimizer_backend("openai_chat")
    if base_url and api_key:
        configure_optimizer_openai(base_url=base_url, api_key=api_key)
    set_optimizer_deployment("deepseek-chat")
    set_target_backend("qwen_chat")
    configure_qwen_chat(base_url=qwen_base, api_key=qwen_key, enable_thinking=False)
    set_target_deployment(target)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--skill", required=True, help="path to a skill markdown file")
    p.add_argument("--split-dir", required=True, help="mcqa split directory")
    p.add_argument("--split", default="test", choices=["train", "val", "test"])
    p.add_argument("--out-dir", required=True, help="where to write summary.json + results.jsonl")
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args()

    _load_env_file(os.path.join(_PROJECT_ROOT, ".env.local-pilot"))
    _configure_backends()

    from skillopt.envs.mcqa.batch_runner import run_batch
    from skillopt.envs.mcqa.dataloader import McqaDataLoader

    loader = McqaDataLoader(split_mode="split_dir", split_dir=args.split_dir)
    loader.setup({})
    items = getattr(loader, f"{args.split}_items")
    with open(args.skill, encoding="utf-8") as f:
        skill_text = f.read()

    print(f"[eval] skill={args.skill} split={args.split} ({len(items)} items) from {args.split_dir}")
    os.makedirs(args.out_dir, exist_ok=True)
    results = run_batch(items=items, out_root=args.out_dir, skill_content=skill_text,
                        max_turns=1, workers=args.workers)
    correct = sum(1 for r in results if r.get("hard"))
    total = len(results)
    # Failed rollouts (Ollama down / model missing / timeout) are stubbed as
    # agent_ok=False — count them so a degenerate run can't masquerade as a real
    # flat result (this experiment's entire conclusion hinges on "flat", not "broken").
    errors = sum(1 for r in results if not r.get("agent_ok"))
    acc = correct / total if total else 0.0

    summary = {
        "skill": args.skill,
        "split_dir": args.split_dir,
        "split": args.split,
        "acc": acc,
        "correct": correct,
        "total": total,
        "errors": errors,
    }
    with open(os.path.join(args.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[eval] acc={acc:.4f} ({correct}/{total}, errors={errors}) -> {os.path.join(args.out_dir, 'summary.json')}")
    if total == 0 or errors == total:
        print("[eval] ERROR: no successful rollouts — check Ollama is up and the model is pulled.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
