---
phase: 4
title: "(Stretch) Cross-Dataset Transfer Eval"
status: script-written-eval-not-run   # scripts/eval_skill_on_dataset.py created + compiles; eval deprioritized (flat core result, article not updated)
priority: P3
effort: "1h"
dependencies: [1]
---

# Phase 4: (Stretch) Cross-Dataset Transfer Eval

## Overview
Fill the article's transfer matrix: run the v3 CSQA-trained skill on SocialIQA test, and the new
SocialIQA-trained skill on CSQA test — two zero-shot eval passes, no training.

## Overview note
Independent of Phases 2-3 except it needs Phase 1 splits (SocialIQA) + the existing v3 CSQA skill
and CSQA splits. Only worth doing if Phases 1-3 land with time to spare.

## Requirements
- Functional: a small reusable eval script that loads a skill + a split and prints accuracy.
- Non-functional: reuse `run_batch` — do NOT re-implement the trainer's eval path (DRY).

## Architecture
`scripts/eval_skill_on_dataset.py` ≈ parameterized `scripts/smoke_test_pipeline.py`:
load skill markdown → load split via `McqaDataLoader` → `run_batch(items, ...)` → count `hard` →
write `summary.json` + `results.jsonl`. ~80 LOC. Target temp=0 for deterministic eval.

Matrix cells produced:
| skill ↓ / test → | CSQA test (200) | SocialIQA test (200) |
|---|---|---|
| Weak init | 0.760 (have) | (this phase) |
| v3 (CSQA-trained) | 0.740 (have) | (this phase) |
| SocialIQA-trained (best seed) | (this phase) | (Phase 3 has it) |

## Related Code Files
- Create: `scripts/eval_skill_on_dataset.py`
- Read for pattern: `scripts/smoke_test_pipeline.py`, `skillopt/envs/mcqa/batch_runner.py` (`run_batch`), `skillopt/envs/mcqa/dataloader.py` (`McqaDataLoader`)
- Inputs: `outputs/mcqa_local_pilot_v3/best_skill.md`, `skillopt/envs/mcqa/skills/initial-weak.md`, `outputs/mcqa_siqa_s42/best_skill.md`, `data/mcqa_siqa_split`, existing CSQA split dir.
- Modify: `docs/articles/medium-skillopt-local-oss-csqa.md` (Experiment 1 transfer table cells).

## Implementation Steps
1. Write `eval_skill_on_dataset.py` with args: `--skill`, `--split-dir`, `--split` (default test), `--out-dir`. Configure backends from `.env.local-pilot` env (copy the setup block from `smoke_test_pipeline.py`).
2. Eval weak init + v3 skill + SocialIQA skill on the relevant test splits (cross pairs).
3. Record deltas; fill the article's Experiment-1 matrix; remove its `_coming_` cells for the rows now known.

## Success Criteria
- [ ] `eval_skill_on_dataset.py` runs end-to-end, writes summary.json with `acc`.
- [ ] Transfer cells in the article filled with traceable numbers.
- [ ] No duplication of trainer eval logic (uses `run_batch`).

## Risk Assessment
- 3-option SocialIQA vs 5-option CSQA: the `<answer>` letter parser must accept A/B/C and A–E — confirm the mcqa evaluator is option-count-agnostic (it parses the emitted letter, so should be fine).
- Transfer likely null (different task distributions) — that's an expected, reportable outcome, not a failure.
- Skip entirely if time-boxed out; Phases 1-3 are the deliverable.
