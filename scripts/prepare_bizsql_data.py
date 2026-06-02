#!/usr/bin/env python3
"""Validate blind gold pairs by execution and carve deterministic BizSQL splits.

Loads ``data/bizsql/raw_pairs.jsonl`` (the committed generation checkpoint) +
``data/bizsql/business.sqlite``; for each pair: executes ``gold_sql`` read-only,
DROPS it if it errors / times out / returns empty / returns a whole-table-sized
result (quality filter), else computes the gold result set. Dedups by normalized
SQL and by result signature, stratifies by difficulty (~60/30/10 easy/med/hard),
deterministically shuffles, and carves 100 train / 100 val / 200 test::

    {out_dir}/train/items.json
    {out_dir}/val/items.json
    {out_dir}/test/items.json
    {out_dir}/meta.json

Pure script over the checkpoint — no LLM calls, fully reproducible. Scoring uses
``gold_result`` only (execution-accuracy); ``gold_sql`` is kept for the article
trace. Gold is blind by construction (see generate_bizsql_pairs.py) and correct
by validation (this script drops anything that does not execute to a clean set).

Usage
-----
    python scripts/prepare_bizsql_data.py --n-train 100 --n-val 100 --n-test 200 \
        --seed 42 --out-dir data/bizsql_split_s42
    python scripts/prepare_bizsql_data.py --self-check --out-dir data/bizsql_split_s42
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from skillopt.envs.bizsql.evaluator import canonicalize, run_sql  # noqa: E402

_RAW = "data/bizsql/raw_pairs.jsonl"
_DB = "data/bizsql/business.sqlite"
_SCHEMA_REF = "data/bizsql/schema.sql"
_BANDS = ("easy", "medium", "hard")
_BAND_RATIO = {"easy": 0.6, "medium": 0.3, "hard": 0.1}
_MAX_RESULT_ROWS = 50   # questions return compact result sets; bigger => whole-table-ish
_SQL_TIMEOUT = 5


def _norm_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.strip().lower()).rstrip(";")


def _validate_pairs(raw_path: str, db_path: str) -> list[dict]:
    """Execute each gold, keep clean compact result sets, dedup by SQL + result."""
    if not os.path.isfile(raw_path):
        raise SystemExit(f"missing {raw_path}: run generate_bizsql_pairs.py first (or seed it).")
    if not os.path.isfile(db_path):
        raise SystemExit(f"missing {db_path}: run scripts/seed_bizsql_db.py first.")

    kept: list[dict] = []
    seen_sql: set[str] = set()
    seen_result: set = set()
    dropped = {"exec": 0, "empty": 0, "wholetable": 0, "dup_sql": 0, "dup_result": 0}
    total = 0
    with open(raw_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            row = json.loads(line)
            sql = str(row.get("gold_sql", "")).strip()
            question = str(row.get("question", "")).strip()
            difficulty = str(row.get("difficulty", "")).strip().lower()
            if not sql or not question or difficulty not in _BANDS:
                dropped["exec"] += 1
                continue
            nkey = _norm_sql(sql)
            if nkey in seen_sql:
                dropped["dup_sql"] += 1
                continue
            ok, rows, _ = run_sql(sql, db_path, timeout=_SQL_TIMEOUT)
            if not ok:
                dropped["exec"] += 1
                continue
            if not rows:
                dropped["empty"] += 1
                continue
            if len(rows) > _MAX_RESULT_ROWS:
                dropped["wholetable"] += 1
                continue
            sig = canonicalize(rows)
            if sig in seen_result:
                dropped["dup_result"] += 1
                continue
            seen_sql.add(nkey)
            seen_result.add(sig)
            kept.append({
                "question": question,
                "db_path": _DB,
                "schema_ddl_ref": _SCHEMA_REF,
                "difficulty": difficulty,
                "gold_sql": sql,
                "gold_result": [list(r) for r in rows],
            })
    print(f"  [validate] kept {len(kept)} / {total}  dropped={dropped}")
    return kept


def _stratified_carve(pool: list[dict], need: int, seed: int) -> list[dict]:
    """Take ~60/30/10 from each difficulty band; backfill shortfalls from the rest."""
    rng = random.Random(seed)
    by_band: dict[str, list[dict]] = {b: [] for b in _BANDS}
    for it in pool:
        by_band[it["difficulty"]].append(it)
    for b in _BANDS:
        rng.shuffle(by_band[b])

    selected: list[dict] = []
    for b in _BANDS:
        quota = round(need * _BAND_RATIO[b])
        selected.extend(by_band[b][:quota])
        by_band[b] = by_band[b][quota:]
    # backfill to exactly `need` from leftovers (largest bands first)
    leftovers = [it for b in _BANDS for it in by_band[b]]
    rng.shuffle(leftovers)
    while len(selected) < need and leftovers:
        selected.append(leftovers.pop())
    rng.shuffle(selected)
    return selected[:need]


def _write_split(out_dir: str, name: str, items: list[dict]) -> None:
    split_dir = os.path.join(out_dir, name)
    os.makedirs(split_dir, exist_ok=True)
    for i, it in enumerate(items):
        it["id"] = f"bizsql-{name}-{i:04d}"
    with open(os.path.join(split_dir, "items.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _self_check(out_dir: str, db_path: str) -> bool:
    ok = True
    for name in ("train", "val", "test"):
        path = os.path.join(out_dir, name, "items.json")
        if not os.path.isfile(path):
            print(f"  [self-check] MISSING {path}", file=sys.stderr)
            ok = False
            continue
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
        bands = {b: 0 for b in _BANDS}
        for it in items:
            if not it.get("id") or not it.get("question") or not it.get("db_path"):
                print(f"  [self-check] bad item (id/question/db_path) in {name}: {it.get('id')}", file=sys.stderr)
                ok = False
            if not it.get("gold_sql") or not it.get("gold_result"):
                print(f"  [self-check] missing gold_sql/result in {name}: {it.get('id')}", file=sys.stderr)
                ok = False
            if it.get("difficulty") not in _BANDS:
                print(f"  [self-check] bad difficulty in {name}: {it.get('id')}", file=sys.stderr)
                ok = False
            bands[it.get("difficulty", "")] = bands.get(it.get("difficulty", ""), 0) + 1
        # re-execute a 10-item sample to confirm gold_result still matches live execution
        for it in items[:10]:
            ex_ok, rows, _ = run_sql(it["gold_sql"], db_path, timeout=_SQL_TIMEOUT)
            if not ex_ok or canonicalize(rows) != canonicalize(it["gold_result"]):
                print(f"  [self-check] gold_result mismatch on re-exec ({name}/{it['id']})", file=sys.stderr)
                ok = False
        print(f"  [self-check] {name}: {len(items)} items, bands={bands}")
    return ok


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw-pairs", default=_RAW)
    p.add_argument("--db", default=_DB)
    p.add_argument("--n-train", type=int, default=100)
    p.add_argument("--n-val", type=int, default=100)
    p.add_argument("--n-test", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-dir", default="data/bizsql_split_s42")
    p.add_argument("--self-check", action="store_true", help="validate existing output dir, no rebuild")
    args = p.parse_args()

    if args.self_check:
        ok = _self_check(args.out_dir, args.db)
        print("self-check:", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    need = args.n_train + args.n_val + args.n_test
    pool = _validate_pairs(args.raw_pairs, args.db)
    if len(pool) < need:
        raise SystemExit(
            f"Only {len(pool)} validated pairs but need {need}. "
            "Generate more with scripts/generate_bizsql_pairs.py."
        )

    carved = _stratified_carve(pool, need, args.seed)
    train = carved[: args.n_train]
    val = carved[args.n_train: args.n_train + args.n_val]
    test = carved[args.n_train + args.n_val: need]

    os.makedirs(args.out_dir, exist_ok=True)
    _write_split(args.out_dir, "train", train)
    _write_split(args.out_dir, "val", val)
    _write_split(args.out_dir, "test", test)
    meta = {
        "source": "Claude-Code/strong-model blind generation -> execution-validated",
        "db": args.db,
        "schema": _SCHEMA_REF,
        "seed": args.seed,
        "validated_pool": len(pool),
        "counts": {"train": len(train), "val": len(val), "test": len(test)},
        "scoring": "execution-accuracy on gold_result (order-insensitive); gold_sql kept for trace only",
    }
    with open(os.path.join(args.out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"  wrote split to {args.out_dir}  ({meta['counts']}, validated pool={len(pool)})")
    for it in train[:2]:
        print(f"  sample {it['id']} [{it['difficulty']}]: {it['question'][:60]}")

    ok = _self_check(args.out_dir, args.db)
    print("self-check:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
