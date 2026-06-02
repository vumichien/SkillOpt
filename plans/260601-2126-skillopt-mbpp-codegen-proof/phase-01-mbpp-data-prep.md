---
phase: 1
title: "MBPP Data Prep"
status: done
priority: P1
effort: "2-3h"
dependencies: []
---

# Phase 1: MBPP Data Prep

## Overview
Produce deterministic MBPP split dirs (100 train / 100 val / 200 test) in the env's `items.json` schema,
seeds 42/43/44. Mirrors `scripts/prepare_mcqa_data.py` exactly in structure.

## Requirements
- Functional: download MBPP, map rows to the mbpp item schema, write seeded split dirs + meta.json + self-check.
- Non-functional: deterministic (seeded shuffle), idempotent `--self-check`, no network beyond HF download.

## Architecture
- HF source: `google-research-datasets/mbpp`, config `full` (974 rows; fall back to `sanitized`=427 only if
  needed — decide here, default `full`). Pool the labeled splits (`train`+`validation`+`test`+`prompt` as
  available — MBPP ships 374/90/500/10; pool all labeled rows, then carve our own 100/100/200, same approach
  as the MC pooling).
- Row fields used: `task_id`→id, `text`→prompt, `test_list` (list of 3 assert strings), `test_setup_code`
  (often empty), `code` (gold — kept only for reference/meta, NOT shown to target).
- **mbpp item schema** written to `{split}/items.json`:
  ```json
  {"id": "mbpp-3", "prompt": "Write a function to find the shared elements...",
   "test_list": ["assert similar_elements((3,4,5,6),(5,7,4,10))==(4,5)", "...", "..."],
   "test_setup_code": "",
   "example_assert": "assert similar_elements((3,4,5,6),(5,7,4,10))==(4,5)"}
  ```
  `example_assert` = `test_list[0]`, shown in the prompt to pin the function signature/name (without it,
  pass@1 collapses on name mismatch — a manufactured-unfair failure).
- This schema is loadable by the default `SplitDataLoader.load_split_items` (first `*.json` → array), so the
  Phase-2 dataloader is a one-line subclass like `McqaDataLoader`.

## Related Code Files
- Create: `scripts/prepare_mbpp_data.py` (clone of `scripts/prepare_mcqa_data.py`, MBPP row mapping).
- Create (output): `data/mbpp_split_s42/{train,val,test}/items.json` + `meta.json` (and `_s43`, `_s44`).

## Implementation Steps
1. Copy `prepare_mcqa_data.py` → `prepare_mbpp_data.py`. Replace converters with `_convert_mbpp_row(row)`:
   validate `text`, `test_list` (len ≥ 1, all `assert`-prefixed), build the schema above; drop rows whose
   gold `code` fails its own `test_list` under the sandbox (sanity filter — guarantees solvable + correct tests).
2. Pool all labeled MBPP rows; deterministic `random.Random(seed).shuffle`; carve 100/100/200.
3. Write splits + `meta.json` (source, license = MIT/cc-by-4.0 per HF card, seed, pool_size, counts).
4. Extend `_self_check` to validate: id/prompt present, `test_list` non-empty + all asserts, `example_assert`
   in `test_list`.
5. Run for seed 42 first: `python scripts/prepare_mbpp_data.py --n-train 100 --n-val 100 --n-test 200 --seed 42 --out-dir data/mbpp_split_s42`.
   (43/44 deferred to Phase 6 — only generated if the pilot clears the gate.)

## Success Criteria
- [ ] `data/mbpp_split_s42/` has train(100)/val(100)/test(200)/items.json + meta.json.
- [ ] `--self-check` PASS; every item's gold `code` passes its own `test_list` in the sandbox (validates tests).
- [ ] Run with `.venv\Scripts\python.exe`, `PYTHONUTF8=1`.

## Risk Assessment
- **MBPP test brittleness** (a few tests use floats/sets/order) → the gold-code sanity filter in step 1 drops
  any item whose own gold solution doesn't pass, removing flaky/ambiguous items up front.
- **Config name drift** on HF (`mbpp` vs `google-research-datasets/mbpp`) → pin the working name in the script;
  catch ImportError/load error with a clear message like the MC script does.
