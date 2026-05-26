---
phase: 3
title: "CommonsenseQA Data Prep"
status: complete
priority: P1
effort: "2h"
dependencies: [2]
---

# Phase 3: CommonsenseQA Data Prep

## Overview
Script that downloads CommonsenseQA and converts it to the mcqa env schema, writing `data/mcqa_csqa_split/{train,val,test}/items.json` (48/24/48 for the pilot).

## Key Insight (verified, HF Hub)
`tau/commonsense_qa` (MIT): `{id, question, question_concept, choices{label[],text[]}, answerKey}`, 5 choices A–E. **Test split has empty `answerKey`** (hidden labels) → we MUST carve our train/val/test only from the labeled `train` (9.7k) + `validation` (1.2k) splits. Map → mcqa schema: `choices` = list of `{label, text}` zipped from `choices.label`/`choices.text`; `answers` = `[answerKey]`.

## Requirements
- Functional: deterministic seeded split → 48 train / 24 val / 48 test, all with a valid gold letter.
- Functional: output exactly the mcqa schema Phase 2 consumes; `id` unique.
- Non-functional: small download (HF `datasets`); idempotent; `--self-check` validates schema + that every `answers[0]` ∈ choice labels.

## Architecture
- Source: `datasets.load_dataset("tau/commonsense_qa")`; pool = `train` + `validation` rows (both labeled). Confirm at runtime; if load fails, print actionable msg (`pip install datasets`).
- Convert per row:
  - `id` = csqa `id`
  - `question` = `question`
  - `choices` = `[{"label": l, "text": t} for l,t in zip(choices["label"], choices["text"])]`
  - `answers` = `[answerKey]`  (single letter, e.g. "C")
- Seed-shuffle pool (seed 42), slice 48/24/48 (disjoint).
- Write 3 `items.json` + `meta.json` (counts, source=`tau/commonsense_qa`, license=MIT, seed).
- argparse: `--n-train 48 --n-val 24 --n-test 48 --seed 42 --dataset commonsense_qa --out-dir data/mcqa_csqa_split` (`--dataset` left extensible for ARC later, but only CSQA implemented now — YAGNI).

## Related Code Files
- Create: `scripts/prepare_mcqa_data.py`
- Create (output): `data/mcqa_csqa_split/{train,val,test}/items.json` + `meta.json`
- Read for context: `skillopt/envs/mcqa/dataloader.py` + `evaluator.py` (Phase 2 — confirm exact field names + that gold is a letter), `skillopt/datasets/base.py`

## Implementation Steps
1. Read the Phase-2 mcqa dataloader/evaluator to lock field names (`choices` item shape, `answers` letter).
2. Write `scripts/prepare_mcqa_data.py`: load CSQA, build pool from train+validation, map → schema.
3. Seed-shuffle + slice 48/24/48; write files + `meta.json`.
4. `--self-check`: reload each file; assert keys present, `choices` non-empty, `answers[0]` is one of the choice labels.
5. Run; eyeball 2-3 converted items (question + 5 options + gold letter).

## Success Criteria
- [ ] `data/mcqa_csqa_split/{train,val,test}/items.json` exist (48/24/48), disjoint, deterministic for seed.
- [ ] Every item: non-empty `id`, `question`, 5 `choices` with `{label,text}`, `answers=[valid letter]`.
- [ ] Files load through the mcqa dataloader without error.
- [ ] `meta.json` records source + MIT license + seed.

## Risk Assessment
- **Using the unlabeled CSQA test split**: avoided — pool is train+validation only. Self-check asserts gold validity.
- **`datasets` not installed**: instruct `pip install datasets` (keep optional, not a hard project dep).
- **Choice count / label variance**: CSQA is consistently 5 (A–E); self-check catches anomalies.

## Next Steps
Feeds Phase 4 (`env.split_dir: data/mcqa_csqa_split`).
