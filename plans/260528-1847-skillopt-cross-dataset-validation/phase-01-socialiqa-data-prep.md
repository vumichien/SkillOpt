---
phase: 1
title: "SocialIQA Data Prep"
status: done
priority: P1
effort: "1h"
dependencies: []
---

# Phase 1: SocialIQA Data Prep

## Overview
Extend `scripts/prepare_mcqa_data.py` to support SocialIQA and generate three seeded
mcqa split directories (100 train / 300 val / 200 test) for seeds 42, 43, 44.

## Requirements
- Functional: download `allenai/social_i_qa`, map rows to the mcqa schema, write deterministic seeded splits passing `--self-check`.
- Non-functional: per-dataset converter dispatch (don't break existing `commonsense_qa` path); keep file readable (current file ~170 LOC, stay well under modularization concern after +40).

## Architecture
SocialIQA HF row schema (verify on first load):
```
{ "context": "...", "question": "...",
  "answerA": "...", "answerB": "...", "answerC": "...",
  "label": "1" | "2" | "3" }   # string label, 1-indexed
```
Target mcqa schema (unchanged):
```
{ "id": "...", "question": "<context>\n<question>",
  "choices": [{"label":"A","text":"..."}, {"label":"B",...}, {"label":"C",...}],
  "answers": ["A"] }            # gold letter
```
Mapping: `question = context.strip() + "\n" + question.strip()`; choices A/B/C from answerA/B/C;
gold = `{"1":"A","2":"B","3":"C"}[label]`. SocialIQA has no per-row id → synthesize `siqa-{index}`.

**Label/test caveat (open question 1):** design assumes HF `test` labels hidden → pool `train` +
`validation` (~35k labeled). If `load_dataset` exposes a labeled `test`, still pool only
train+validation for consistency with the CSQA approach (keeps test untouched as a clean pool).

## Related Code Files
- Modify: `scripts/prepare_mcqa_data.py`
  - `_SUPPORTED`: add `"social_i_qa": "allenai/social_i_qa"`.
  - Refactor `_convert_row(row)` → dispatch by dataset key. Cleanest: rename current body to `_convert_csqa_row`, add `_convert_siqa_row`, and a `_CONVERTERS = {"commonsense_qa": ..., "social_i_qa": ...}` map. `_build_pool` calls the right converter.
  - `_build_pool(dataset_key)`: keep pooling `("train","validation")` labeled splits (already correct).
- Create (data, not code): `data/mcqa_siqa_split/` (seed 42), `data/mcqa_siqa_split_s43/`, `data/mcqa_siqa_split_s44/`.

## Implementation Steps
1. Add `social_i_qa` to `_SUPPORTED` and wire a per-dataset converter dispatch (preserve existing CSQA behavior exactly — DRY, don't duplicate the writer/split logic).
2. Implement `_convert_siqa_row`: synthesize id, concat context+question, build A/B/C choices, map numeric label → letter; return `None` if any field missing or label out of range (defensive, mirrors CSQA converter).
3. Generate seed-42 split:
   ```powershell
   .venv\Scripts\python.exe scripts\prepare_mcqa_data.py `
     --dataset social_i_qa --n-train 100 --n-val 300 --n-test 200 `
     --seed 42 --out-dir data/mcqa_siqa_split
   ```
4. Generate seeds 43 and 44 into `data/mcqa_siqa_split_s43` and `_s44` (same flags, `--seed 43/44`).
5. Spot-check `meta.json` counts (100/300/200) and a couple of printed samples (gold text matches a plausible answer).

## Success Criteria
- [ ] `--self-check` PASS on all three split dirs (gold ∈ labels for every item).
- [ ] Existing `commonsense_qa` path still works (regression: re-run CSQA prep or self-check existing CSQA dir).
- [ ] Each split: train=100, val=300, test=200; choices are exactly A/B/C.
- [ ] Open question 1 resolved (note in run log whether HF test labels were visible).

## Risk Assessment
- HF schema drift (field names / label type) → converter returns `None`, `_build_pool` raises "No labeled rows"; fix mapper, don't silently ship empty splits. Verify field names from the first `load_dataset` print before bulk run.
- `allenai/social_i_qa` vs legacy `social_i_qa` id — try `allenai/social_i_qa` first; fall back to `social_i_qa` if 404. Record which worked in `meta.json` source field (already captured).
- Pool size < 600 → impossible here (~35k), but `need` guard already raises if so.
