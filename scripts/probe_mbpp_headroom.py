#!/usr/bin/env python3
"""MBPP headroom probe — is the 7B's failure procedural (skill-fixable) or capability?

Runs the weak-init skill over the train (or val) split with the real target via
the same rollout path the trainer uses (``run_batch``), reports baseline pass@1,
dumps every failure's signature to ``probe_failures.json``, and auto-buckets
failures into coarse procedural-vs-capability classes for triage. The auto-buckets
are a STARTING POINT — the actual gate is a human hand-labeling ~20 sampled
failures (see plan Phase 3). Test split is left untouched.

Usage
-----
    python scripts/probe_mbpp_headroom.py --split-dir data/mbpp_split_s42 --split train

Requires ``.env.local-pilot`` (auto-loaded) + Ollama up with the target pulled.
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


def _configure_backends() -> None:
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
    set_optimizer_backend("openai_chat")
    if base_url and api_key:
        configure_optimizer_openai(base_url=base_url, api_key=api_key)
    set_optimizer_deployment("deepseek-chat")
    set_target_backend("qwen_chat")
    configure_qwen_chat(base_url=qwen_base, api_key=qwen_key, enable_thinking=False)
    set_target_deployment(target)


def _bucket(detail: str, n_pass: int, n_tests: int, predicted_code: str) -> str:
    """Coarse triage class from the failure signature. Procedural unless proven capability."""
    d = (detail or "").lower()
    if "timeout" in d:
        return "timeout"  # mixed: infinite loop (procedural) or brute force (capability)
    if not predicted_code.strip() or "syntaxerror" in d or "indentationerror" in d:
        return "extraction_format"  # procedural
    if "nameerror" in d or "is not defined" in d or "attributeerror" in d:
        return "wrong_signature_name"  # procedural (called wrong name / missing helper)
    if "typeerror" in d or "positional argument" in d or ("argument" in d and "takes" in d):
        return "wrong_signature_name"  # procedural (arity/signature mismatch)
    if "assertionerror" in d or d == "assertion failed":
        if 0 < n_pass < n_tests:
            return "edge_case"  # mostly procedural (passes example, fails another)
        return "assertion_wrong_logic"  # likely capability
    return "other"


_PROCEDURAL = {"extraction_format", "wrong_signature_name", "edge_case"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--split-dir", default="data/mbpp_split_s42")
    p.add_argument("--split", default="train", choices=["train", "val"])  # NOT test — keep locked
    p.add_argument("--skill", default="skillopt/envs/mbpp/skills/initial-weak.md")
    p.add_argument("--out-dir", default="outputs/mbpp_probe")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--sandbox-timeout", type=int, default=8)
    p.add_argument("--target", default="", help="overrides TARGET_DEPLOYMENT from .env")
    args = p.parse_args()

    _load_env_file(os.path.join(_PROJECT_ROOT, ".env.local-pilot"))
    if args.target.strip():
        os.environ["TARGET_DEPLOYMENT"] = args.target.strip()
    _configure_backends()

    from skillopt.envs.mbpp.batch_runner import run_batch
    from skillopt.envs.mbpp.dataloader import MbppDataLoader

    loader = MbppDataLoader(split_mode="split_dir", split_dir=args.split_dir)
    loader.setup({})
    items = getattr(loader, f"{args.split}_items")
    with open(args.skill, encoding="utf-8") as f:
        skill_text = f.read()

    print(f"[probe] skill={args.skill} split={args.split} ({len(items)} items) from {args.split_dir}")
    os.makedirs(args.out_dir, exist_ok=True)
    results = run_batch(
        items=items, out_root=args.out_dir, skill_content=skill_text,
        max_turns=1, workers=args.workers, sandbox_timeout=args.sandbox_timeout,
    )

    total = len(results)
    correct = sum(1 for r in results if r.get("hard"))
    errors = sum(1 for r in results if not r.get("agent_ok"))
    acc = correct / total if total else 0.0

    by_id = {str(it["id"]): it for it in items}
    failures: list[dict] = []
    buckets: dict[str, int] = {}
    for r in results:
        if r.get("hard"):
            continue
        it = by_id.get(str(r.get("id")), {})
        n_tests = len(it.get("test_list") or [])
        b = _bucket(r.get("fail_reason", ""), int(r.get("n_pass", 0)), n_tests, r.get("predicted_code", ""))
        buckets[b] = buckets.get(b, 0) + 1
        failures.append({
            "id": r.get("id"),
            "prompt": it.get("prompt", ""),
            "predicted_code": r.get("predicted_code", ""),
            "detail": r.get("fail_reason", ""),
            "n_pass": r.get("n_pass", 0),
            "n_tests": n_tests,
            "bucket": b,
        })

    proc = sum(v for k, v in buckets.items() if k in _PROCEDURAL)
    proc_share = proc / total if total else 0.0

    out = {
        "split_dir": args.split_dir,
        "split": args.split,
        "target": os.environ.get("TARGET_DEPLOYMENT", "").strip(),
        "baseline_pass_at_1": acc,
        "correct": correct,
        "total": total,
        "errors": errors,
        "buckets": buckets,
        "auto_procedural_count": proc,
        "auto_procedural_share": proc_share,
        "failures": failures,
    }
    with open(os.path.join(args.out_dir, "probe_failures.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[probe] baseline pass@1 = {acc:.4f} ({correct}/{total}, errors={errors})")
    print(f"[probe] failure buckets: {buckets}")
    print(f"[probe] AUTO procedural share = {proc_share:.1%} (gate wants >= ~10-15 pp; HUMAN must hand-label ~20)")
    print(f"[probe] wrote {os.path.join(args.out_dir, 'probe_failures.json')}")
    if total == 0 or errors == total:
        print("[probe] ERROR: no successful rollouts — check Ollama is up and the model is pulled.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
