#!/usr/bin/env python3
"""Generate blind (question, gold_sql, difficulty) pairs for the BizSQL track.

Calls a STRONG model (the DeepSeek optimizer client) with ONLY the schema DDL +
conventions in context — the BLIND GOLD guardrail: no candidate skill, no target
model, ever in context. Asks for diverse business questions + gold SQL across
difficulty bands and archetypes, then APPENDS raw ``{question, gold_sql,
difficulty, archetype}`` rows to ``data/bizsql/raw_pairs.jsonl`` (the committed
checkpoint). Over-generate (~400-500) so validation drops in Phase prepare still
leave enough. This script makes LLM calls — run it once, not in CI.

Usage
-----
    python scripts/generate_bizsql_pairs.py --target-count 450

Requires ``.env.local-pilot`` with OPTIMIZER_OPENAI_BASE_URL + OPTIMIZER_OPENAI_API_KEY.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_SCHEMA = os.path.join(_PROJECT_ROOT, "data", "bizsql", "schema.sql")
_RAW = os.path.join(_PROJECT_ROOT, "data", "bizsql", "raw_pairs.jsonl")

# Archetypes x difficulty force coverage so no single memorized constant can win.
_ARCHETYPES = [
    ("count_filter", "easy", "single-table COUNT/SUM with one WHERE filter"),
    ("aggregate", "easy", "single-table AVG/MIN/MAX/SUM, optional one filter"),
    ("status_filter", "easy", "filter on a lowercase status/priority enum"),
    ("date_window", "medium", "filter on an ISO date range (e.g. a quarter or year)"),
    ("group_by", "medium", "GROUP BY a category/region with an aggregate"),
    ("two_table_join", "medium", "join two tables on a key + filter/aggregate"),
    ("revenue_rule", "medium", "revenue excluding refunded/cancelled orders"),
    ("active_subscription", "medium", "active subscriptions via canceled_at IS NULL (MRR sum)"),
    ("top_n", "medium", "ORDER BY ... LIMIT N (top customers/products)"),
    ("three_table", "hard", "join 3 tables (e.g. customers-orders-order_items)"),
    ("having_nested", "hard", "GROUP BY with HAVING or a nested subquery"),
]


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


def _configure_optimizer() -> str:
    from skillopt.model import (
        configure_optimizer_openai,
        set_optimizer_backend,
        set_optimizer_deployment,
    )
    base_url = os.environ.get("OPTIMIZER_OPENAI_BASE_URL", "").strip()
    api_key = os.environ.get("OPTIMIZER_OPENAI_API_KEY", "").strip()
    if not base_url or not api_key:
        print("ERROR: OPTIMIZER_OPENAI_BASE_URL / OPTIMIZER_OPENAI_API_KEY missing; load .env.local-pilot",
              file=sys.stderr)
        raise SystemExit(2)
    model = os.environ.get("OPTIMIZER_DEPLOYMENT", "deepseek-v4-pro").strip()
    set_optimizer_backend("openai_chat")
    configure_optimizer_openai(base_url=base_url, api_key=api_key)
    set_optimizer_deployment(model)
    return model


def _system_prompt(schema: str) -> str:
    # BLIND GOLD: context is schema + conventions only. No skill, no target model.
    return (
        "You are a senior analytics engineer authoring a Text-to-SQL benchmark over a FIXED "
        "SQLite database. You see ONLY the schema below. Write natural business questions an "
        "operator would ask, each with ONE correct SQL SELECT (SQLite dialect) that answers it "
        "using only these tables/columns. Obey the documented conventions exactly (status casing, "
        "ISO dates, revenue excludes refunded/cancelled, active subscription = canceled_at IS NULL).\n\n"
        f"SCHEMA:\n{schema}\n\n"
        "Each query must return a small, well-defined result set (not the whole table, not empty). "
        "Vary entities, filters, and phrasings. Return ONLY a JSON array; each element is "
        '{"question": str, "gold_sql": str, "difficulty": "easy|medium|hard"}.'
    )


def _user_prompt(archetype: str, difficulty: str, hint: str, n: int) -> str:
    return (
        f"Generate {n} DISTINCT items of archetype '{archetype}' ({hint}), difficulty '{difficulty}'. "
        "Each question phrased differently; vary the concrete filter values, columns, and tables. "
        "Return ONLY the JSON array."
    )


def _extract_json_array(text: str) -> list[dict]:
    m = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    blob = m.group(1) if m else text
    start, end = blob.find("["), blob.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        data = json.loads(blob[start:end + 1])
        return [d for d in data if isinstance(d, dict)]
    except json.JSONDecodeError:
        return []


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target-count", type=int, default=450, help="approx total pairs to accumulate")
    p.add_argument("--per-call", type=int, default=8, help="pairs requested per LLM call")
    p.add_argument("--out", default=_RAW)
    p.add_argument("--difficulties", default="easy,medium,hard",
                   help="comma list; restrict generation to these bands (easy saturates fast)")
    args = p.parse_args()

    allowed = {d.strip() for d in args.difficulties.split(",") if d.strip()}
    archetypes = [a for a in _ARCHETYPES if a[1] in allowed] or _ARCHETYPES

    _load_env_file(os.path.join(_PROJECT_ROOT, ".env.local-pilot"))
    model = _configure_optimizer()
    from skillopt.model import chat_optimizer

    with open(_SCHEMA, encoding="utf-8") as f:
        schema = f.read().strip()
    system = _system_prompt(schema)

    existing = 0
    if os.path.isfile(args.out):
        with open(args.out, encoding="utf-8") as f:
            existing = sum(1 for line in f if line.strip())
    print(f"[gen] model={model} existing={existing} target={args.target_count} -> {args.out}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    written = 0
    with open(args.out, "a", encoding="utf-8") as out:
        round_i = 0
        while existing + written < args.target_count:
            archetype, difficulty, hint = archetypes[round_i % len(archetypes)]
            round_i += 1
            try:
                text, _ = chat_optimizer(
                    system, _user_prompt(archetype, difficulty, hint, args.per_call),
                    max_completion_tokens=4096, retries=3,
                )
            except Exception as e:  # noqa: BLE001
                print(f"[gen] call failed ({archetype}/{difficulty}): {e}", file=sys.stderr)
                continue
            items = _extract_json_array(text)
            for it in items:
                q, sql = str(it.get("question", "")).strip(), str(it.get("gold_sql", "")).strip()
                diff = str(it.get("difficulty", difficulty)).strip().lower()
                if not q or not sql:
                    continue
                row = {"question": q, "gold_sql": sql,
                       "difficulty": diff if diff in {"easy", "medium", "hard"} else difficulty,
                       "archetype": archetype}
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
                written += 1
            print(f"[gen] {archetype}/{difficulty}: +{len(items)}  total={existing + written}", flush=True)

    print(f"[gen] done. wrote {written} new pairs ({existing + written} total) to {args.out}")
    print("[gen] next: python scripts/prepare_bizsql_data.py --seed 42 --out-dir data/bizsql_split_s42")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
