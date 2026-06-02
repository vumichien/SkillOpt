#!/usr/bin/env python3
"""Prepare MBPP as an mbpp split directory.

Downloads ``google-research-datasets/mbpp`` (config ``full``), pools every
labeled row (``train`` + ``validation`` + ``test`` + ``prompt``), maps each row
to the mbpp env schema, drops any row whose gold ``code`` does not pass its own
``test_list`` in the sandbox (sanity filter — guarantees solvable + correct
tests), and writes a deterministic seeded split::

    {out_dir}/train/items.json
    {out_dir}/val/items.json
    {out_dir}/test/items.json
    {out_dir}/meta.json

mbpp item schema::

    {"id": "mbpp-3", "prompt": "Write a function to ...",
     "test_list": ["assert f(...) == ...", "...", "..."],
     "test_setup_code": "",
     "example_assert": "assert f(...) == ...",
     "code": "<gold reference — never shown to the target at rollout time>"}

``example_assert`` (= ``test_list[0]``) is shown in the prompt to pin the
function name/signature; without it pass@1 collapses on name mismatch. ``code``
is kept for the Phase-2 evaluator test and the article trace; the rollout
prompt builder reads only ``prompt`` / ``example_assert`` / ``test_list``.

Usage
-----
    python scripts/prepare_mbpp_data.py --n-train 100 --n-val 100 --n-test 200 \
        --seed 42 --out-dir data/mbpp_split_s42
    python scripts/prepare_mbpp_data.py --self-check --out-dir data/mbpp_split_s42

Requires ``datasets`` for the download step: ``pip install datasets``.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from skillopt.envs.mbpp.evaluator import run_tests  # noqa: E402

_HF_NAME = "google-research-datasets/mbpp"
_HF_CONFIG = "full"
_LICENSE = "cc-by-4.0"
_SANITY_TIMEOUT = 10


def _convert_mbpp_row(row: dict) -> dict | None:
    """Map one MBPP row to the mbpp schema (no sandbox check yet). None if unusable."""
    task_id = row.get("task_id")
    text = str(row.get("text") or "").strip()
    test_list = [str(t).strip() for t in (row.get("test_list") or []) if str(t).strip()]
    setup = str(row.get("test_setup_code") or "")
    code = str(row.get("code") or "").strip()
    if task_id is None or not text or not code:
        return None
    if len(test_list) < 1 or not all(t.startswith("assert") for t in test_list):
        return None  # need clean assert-based tests to pin the signature + score
    return {
        "id": f"mbpp-{task_id}",
        "prompt": text,
        "test_list": test_list,
        "test_setup_code": setup,
        "example_assert": test_list[0],
        "code": code,
    }


def _build_pool() -> list[dict]:
    try:
        from datasets import load_dataset
    except ImportError:
        print(
            "ERROR: the `datasets` package is required to download data.\n"
            "Install it with:  pip install datasets",
            file=sys.stderr,
        )
        raise SystemExit(2)

    try:
        ds = load_dataset(_HF_NAME, _HF_CONFIG)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            f"Failed to load {_HF_NAME} (config {_HF_CONFIG}): {exc}\n"
            "Check the dataset name / network and retry."
        )

    raw: list[dict] = []
    for split in ("train", "validation", "test", "prompt"):  # pool all labeled rows
        if split not in ds:
            continue
        for row in ds[split]:
            converted = _convert_mbpp_row(row)
            if converted is not None:
                raw.append(converted)
    if not raw:
        raise SystemExit(f"No usable rows found for {_HF_NAME}.")

    # Sanity filter: keep only rows whose gold code passes its own test_list.
    pool: list[dict] = []
    dropped = 0
    for i, it in enumerate(raw):
        passed, _, _ = run_tests(it["code"], it["test_list"], it["test_setup_code"], timeout=_SANITY_TIMEOUT)
        if passed:
            pool.append(it)
        else:
            dropped += 1
        if (i + 1) % 100 == 0:
            print(f"  [sanity] {i + 1}/{len(raw)} checked, kept {len(pool)}, dropped {dropped}", flush=True)
    print(f"  [sanity] kept {len(pool)} / {len(raw)} rows ({dropped} gold-code failures dropped)")
    return pool


def _write_split(out_dir: str, name: str, items: list[dict]) -> None:
    split_dir = os.path.join(out_dir, name)
    os.makedirs(split_dir, exist_ok=True)
    with open(os.path.join(split_dir, "items.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _self_check(out_dir: str) -> bool:
    ok = True
    for name in ("train", "val", "test"):
        path = os.path.join(out_dir, name, "items.json")
        if not os.path.isfile(path):
            print(f"  [self-check] MISSING {path}", file=sys.stderr)
            ok = False
            continue
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
        for it in items:
            tests = it.get("test_list") or []
            if not it.get("id") or not it.get("prompt"):
                print(f"  [self-check] bad item (id/prompt) in {name}: {it.get('id')}", file=sys.stderr)
                ok = False
            if not tests or not all(str(t).startswith("assert") for t in tests):
                print(f"  [self-check] bad test_list in {name}: {it.get('id')}", file=sys.stderr)
                ok = False
            if it.get("example_assert") not in tests:
                print(f"  [self-check] example_assert not in test_list ({name}/{it.get('id')})", file=sys.stderr)
                ok = False
        print(f"  [self-check] {name}: {len(items)} items")
    return ok


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--n-train", type=int, default=100)
    p.add_argument("--n-val", type=int, default=100)
    p.add_argument("--n-test", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-dir", default="data/mbpp_split_s42")
    p.add_argument("--self-check", action="store_true", help="validate existing output dir, no download")
    args = p.parse_args()

    if args.self_check:
        ok = _self_check(args.out_dir)
        print("self-check:", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    need = args.n_train + args.n_val + args.n_test
    pool = _build_pool()
    if len(pool) < need:
        raise SystemExit(f"Only {len(pool)} usable rows but need {need}.")

    rng = random.Random(args.seed)
    rng.shuffle(pool)
    train = pool[: args.n_train]
    val = pool[args.n_train: args.n_train + args.n_val]
    test = pool[args.n_train + args.n_val: need]

    os.makedirs(args.out_dir, exist_ok=True)
    _write_split(args.out_dir, "train", train)
    _write_split(args.out_dir, "val", val)
    _write_split(args.out_dir, "test", test)
    meta = {
        "source": f"{_HF_NAME} ({_HF_CONFIG})",
        "license": _LICENSE,
        "seed": args.seed,
        "pool_size": len(pool),
        "counts": {"train": len(train), "val": len(val), "test": len(test)},
        "note": "gold-code sanity-filtered; `code` is a hidden gold reference, not shown to the target",
    }
    with open(os.path.join(args.out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"  wrote split to {args.out_dir}  ({meta['counts']}, pool={len(pool)})")
    for it in train[:2]:
        print(f"  sample {it['id']}: {it['prompt'][:60]} -> {it['example_assert'][:50]}")

    ok = _self_check(args.out_dir)
    print("self-check:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
