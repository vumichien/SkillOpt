#!/usr/bin/env python3
"""Smoke-test the generic OpenAI-compatible optimizer path (e.g. DeepSeek).

Verifies that, when OPTIMIZER_OPENAI_BASE_URL + OPTIMIZER_OPENAI_API_KEY are
set, the optimizer entry point reaches the endpoint via a plain OpenAI client
and returns non-empty text + token usage — without sending Azure-only params
(max_completion_tokens / reasoning_effort) that providers like DeepSeek reject.

Usage
-----
    export OPTIMIZER_OPENAI_BASE_URL=https://api.deepseek.com/v1
    export OPTIMIZER_OPENAI_API_KEY=sk-...
    python scripts/smoke_test_optimizer.py [--model deepseek-chat]
"""
from __future__ import annotations

import argparse
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from skillopt.model import (
    chat_optimizer,
    configure_optimizer_openai,
    set_optimizer_backend,
    set_optimizer_deployment,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=os.environ.get("OPTIMIZER_DEPLOYMENT", "deepseek-chat"))
    parser.add_argument("--max-tokens", type=int, default=64)
    args = parser.parse_args()

    base_url = os.environ.get("OPTIMIZER_OPENAI_BASE_URL", "").strip()
    api_key = os.environ.get("OPTIMIZER_OPENAI_API_KEY", "").strip()
    if not base_url or not api_key:
        print(
            "ERROR: set OPTIMIZER_OPENAI_BASE_URL and OPTIMIZER_OPENAI_API_KEY "
            "before running this smoke test.",
            file=sys.stderr,
        )
        return 2

    set_optimizer_backend("openai_chat")
    configure_optimizer_openai(base_url=base_url, api_key=api_key)
    set_optimizer_deployment(args.model)

    print(f"[smoke] endpoint={base_url}  model={args.model}")
    text, usage = chat_optimizer(
        "You are terse.",
        "Reply with exactly: OK.",
        max_completion_tokens=args.max_tokens,
        retries=2,
    )
    print(f"[smoke] response: {text!r}")
    print(f"[smoke] usage:    {usage}")

    if not text.strip():
        print("ERROR: empty response from optimizer endpoint.", file=sys.stderr)
        return 1
    print("[smoke] PASS — non-empty response + usage recorded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
