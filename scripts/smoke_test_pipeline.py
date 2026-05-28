#!/usr/bin/env python3
"""End-to-end smoke test: 2 mcqa val items through DeepSeek + Ollama Qwen.

Verifies the full wiring (optimizer + target backends, mcqa env, dataloader,
rollout, evaluator) without spending money on a full train loop.

Requires .env.local-pilot loaded into the environment.
"""
from __future__ import annotations

import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from skillopt.model import (
    configure_optimizer_openai,
    configure_qwen_chat,
    set_optimizer_backend,
    set_optimizer_deployment,
    set_target_backend,
    set_target_deployment,
)
from skillopt.envs.mcqa.batch_runner import run_batch
from skillopt.envs.mcqa.dataloader import McqaDataLoader


def main() -> int:
    base_url = os.environ.get("OPTIMIZER_OPENAI_BASE_URL", "").strip()
    api_key = os.environ.get("OPTIMIZER_OPENAI_API_KEY", "").strip()
    qwen_base = os.environ.get("QWEN_CHAT_BASE_URL", "").strip()
    qwen_key = os.environ.get("QWEN_CHAT_API_KEY", "").strip()
    target = os.environ.get("TARGET_DEPLOYMENT", "").strip()
    if not all([base_url, api_key, qwen_base, qwen_key, target]):
        print("ERROR: load .env.local-pilot first", file=sys.stderr)
        return 2

    # Optimizer (DeepSeek)
    set_optimizer_backend("openai_chat")
    configure_optimizer_openai(base_url=base_url, api_key=api_key)
    set_optimizer_deployment("deepseek-chat")
    # Target (Ollama Qwen)
    set_target_backend("qwen_chat")
    configure_qwen_chat(base_url=qwen_base, api_key=qwen_key, enable_thinking=False)
    set_target_deployment(target)

    # Load val items (setup only uses cfg fallback when ctor fields empty)
    loader = McqaDataLoader(
        split_mode="split_dir",
        split_dir="data/mcqa_csqa_split",
    )
    loader.setup({})
    val_items = loader.val_items[:2]
    print(f"[smoke] loaded {len(val_items)} val items")

    # Read initial skill
    skill_path = "skillopt/envs/mcqa/skills/initial-weak.md"
    with open(skill_path, encoding="utf-8") as f:
        skill_text = f.read()

    # Run the batch (fresh dir; resume-aware behavior would skip a stale dir)
    out_root = "outputs/_smoke"
    os.makedirs(out_root, exist_ok=True)
    results = run_batch(
        items=val_items,
        out_root=out_root,
        skill_content=skill_text,
        max_turns=1,
        workers=2,
    )
    correct = sum(1 for r in results if r.get("hard"))
    print(f"[smoke] correct={correct}/{len(results)}")
    for r in results:
        print(
            f"[smoke]   id={str(r.get('id'))[:8]} gold={r.get('gold_answer')} "
            f"pred={r.get('predicted_answer')!r} hard={r.get('hard')} "
            f"ok={r.get('agent_ok')}"
        )
    print("[smoke] PASS - full pipeline executed end-to-end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
