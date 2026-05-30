#!/usr/bin/env python3
"""Prepare CommonsenseQA as an mcqa split directory.

Downloads ``tau/commonsense_qa`` (MIT), pools the labeled ``train`` +
``validation`` splits (the HF ``test`` split has hidden labels), maps each row
to the mcqa env schema, and writes a deterministic seeded split::

    {out_dir}/train/items.json
    {out_dir}/val/items.json
    {out_dir}/test/items.json
    {out_dir}/meta.json

mcqa item schema::

    {"id": "...", "question": "...",
     "choices": [{"label": "A", "text": "..."}, ...],
     "answers": ["C"]}

Usage
-----
    python scripts/prepare_mcqa_data.py            # download + write + self-check
    python scripts/prepare_mcqa_data.py --self-check  # validate existing output only

Requires ``datasets`` for the download step: ``pip install datasets``.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

_SUPPORTED = {
    "commonsense_qa": "tau/commonsense_qa",
    "social_i_qa": "allenai/social_i_qa",
}
_LICENSES = {
    "commonsense_qa": "MIT",
    "social_i_qa": "CC-BY-4.0",
}
# allenai/social_i_qa ships a loader script (unsupported by modern `datasets`);
# the HF auto-conversion bot publishes a parquet branch we load instead.
_REVISIONS = {
    "social_i_qa": "refs/convert/parquet",
}


def _convert_csqa_row(row: dict) -> dict | None:
    """Map one CommonsenseQA row to the mcqa schema. None if unusable."""
    labels = list((row.get("choices") or {}).get("label") or [])
    texts = list((row.get("choices") or {}).get("text") or [])
    answer_key = str(row.get("answerKey") or "").strip().upper()
    if not labels or not texts or len(labels) != len(texts):
        return None
    if not answer_key or answer_key not in {str(l).strip().upper() for l in labels}:
        return None  # drop rows with missing/invalid gold (e.g. hidden test labels)
    return {
        "id": str(row.get("id") or ""),
        "question": str(row.get("question") or "").strip(),
        "choices": [
            {"label": str(l).strip().upper(), "text": str(t).strip()}
            for l, t in zip(labels, texts)
        ],
        "answers": [answer_key],
    }


# SocialIQA: numeric 1-indexed string label -> mcqa letter; 3 fixed options A/B/C.
_SIQA_LABEL_TO_LETTER = {"1": "A", "2": "B", "3": "C"}


def _convert_siqa_row(row: dict, index: int) -> dict | None:
    """Map one SocialIQA row to the mcqa schema. None if unusable.

    SocialIQA rows have no id, a separate ``context`` + ``question``, three
    answer fields ``answerA/B/C`` and a string numeric ``label`` ("1".."3").
    """
    context = str(row.get("context") or "").strip()
    question = str(row.get("question") or "").strip()
    answers = [str(row.get(k) or "").strip() for k in ("answerA", "answerB", "answerC")]
    gold = _SIQA_LABEL_TO_LETTER.get(str(row.get("label") or "").strip())
    if not question or not all(answers) or gold is None:
        return None  # drop rows with missing fields / out-of-range label
    return {
        "id": f"siqa-{index}",
        "question": (context + "\n" + question).strip() if context else question,
        "choices": [
            {"label": letter, "text": text}
            for letter, text in zip(("A", "B", "C"), answers)
        ],
        "answers": [gold],
    }


def _build_pool(dataset_key: str) -> list[dict]:
    try:
        from datasets import load_dataset
    except ImportError:
        print(
            "ERROR: the `datasets` package is required to download data.\n"
            "Install it with:  pip install datasets",
            file=sys.stderr,
        )
        raise SystemExit(2)

    hf_name = _SUPPORTED[dataset_key]
    revision = _REVISIONS.get(dataset_key)
    ds = load_dataset(hf_name, revision=revision) if revision else load_dataset(hf_name)
    pool: list[dict] = []
    idx = 0  # global running index (SocialIQA has no per-row id)
    for split in ("train", "validation"):  # labeled splits only; test left untouched
        if split not in ds:
            continue
        for row in ds[split]:
            if dataset_key == "social_i_qa":
                converted = _convert_siqa_row(row, idx)
            else:
                converted = _convert_csqa_row(row)
            idx += 1
            if converted is not None:
                pool.append(converted)
    if not pool:
        raise SystemExit(f"No labeled rows found for {hf_name}.")
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
            labels = {c["label"] for c in it.get("choices", [])}
            if not it.get("id") or not it.get("question"):
                print(f"  [self-check] bad item (id/question) in {name}: {it.get('id')}", file=sys.stderr)
                ok = False
            if not it.get("choices") or not all(c.get("label") and c.get("text") for c in it["choices"]):
                print(f"  [self-check] bad choices in {name}: {it.get('id')}", file=sys.stderr)
                ok = False
            gold = (it.get("answers") or [None])[0]
            if gold not in labels:
                print(f"  [self-check] gold {gold!r} not in labels {labels} ({name}/{it.get('id')})", file=sys.stderr)
                ok = False
        print(f"  [self-check] {name}: {len(items)} items")
    return ok


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", default="commonsense_qa", choices=sorted(_SUPPORTED))
    p.add_argument("--n-train", type=int, default=48)
    p.add_argument("--n-val", type=int, default=24)
    p.add_argument("--n-test", type=int, default=48)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-dir", default="data/mcqa_csqa_split")
    p.add_argument("--self-check", action="store_true", help="validate existing output dir, no download")
    args = p.parse_args()

    if args.self_check:
        ok = _self_check(args.out_dir)
        print("self-check:", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    need = args.n_train + args.n_val + args.n_test
    pool = _build_pool(args.dataset)
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
        "source": _SUPPORTED[args.dataset],
        "license": _LICENSES[args.dataset],
        "seed": args.seed,
        "pool_size": len(pool),
        "counts": {"train": len(train), "val": len(val), "test": len(test)},
    }
    with open(os.path.join(args.out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"  wrote split to {args.out_dir}  ({meta['counts']}, pool={len(pool)})")
    for it in train[:2]:
        gold = it["answers"][0]
        gold_text = next((c["text"] for c in it["choices"] if c["label"] == gold), "?")
        print(f"  sample {it['id']}: {it['question'][:60]} -> {gold}. {gold_text}")

    ok = _self_check(args.out_dir)
    print("self-check:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
