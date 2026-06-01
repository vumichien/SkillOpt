# Phase 01 — LogiQA Dataset Converter + Seeded Splits

## Context Links
- Brainstorm: `plans/reports/brainstorm-summary-260530-1953-skillopt-headroom-arc-scale-validation-report.md`
- Existing converter: `scripts/prepare_mcqa_data.py` (CSQA + SocialIQA patterns)
- mcqa schema consumer: `skillopt/envs/mcqa/dataloader.py`

## Overview
- **Priority:** P0 (blocks everything)
- **Status:** pending
- Add LogiQA (`lucasmccabe/logiqa`) to the existing data-prep script and emit 3 seeded split dirs.

## Key Insights
- `prepare_mcqa_data.py` already has the exact pattern: `_SUPPORTED`/`_LICENSES`/`_REVISIONS` dicts,
  per-dataset `_convert_*_row()`, branch in `_build_pool`, deterministic seeded split (train+validation pool).
- LogiQA schema: `context`(str), `query`(str), `options`(list[4] str), `correct_option`(int 0-3).
  Labeled train(~7376)/val(~651)/test(~651); no hidden labels (unlike CSQA/SIQA), but reuse the
  train+validation pooling for parity. Pool ≈8027 rows ≫ need (600/seed).

## Requirements
- Functional: `python scripts/prepare_mcqa_data.py --dataset logiqa --n-train 100 --n-val 300 --n-test 200 --seed {42,43,44} --out-dir data/mcqa_logiqa_split[_sNN]` writes valid mcqa split dirs that pass `--self-check`.
- Non-functional: deterministic per seed; converter ≤30 LOC; no change to existing CSQA/SIQA behavior.

## Architecture
- Add to `_SUPPORTED`: `"logiqa": "lucasmccabe/logiqa"`; `_LICENSES`: `"logiqa": "CC-BY-NC-SA-4.0"` (verify on HF page).
- `_convert_logiqa_row(row, index)`:
  - `question = (context + "\n" + query).strip()` (context optional-safe like SIQA).
  - `choices = [{"label": L, "text": opt} for L, opt in zip("ABCD", options)]` — guard `len(options)==4`.
  - `gold = "ABCD"[correct_option]` — guard `0 <= correct_option < len(options)`; else return None.
  - `id = f"logiqa-{index}"`.
- Branch in `_build_pool`: `if dataset_key == "logiqa": converted = _convert_logiqa_row(row, idx)`.

## Related Code Files
- Modify: `scripts/prepare_mcqa_data.py`
- Create: `data/mcqa_logiqa_split/` (seed 42), `data/mcqa_logiqa_split_s43/`, `data/mcqa_logiqa_split_s44/`
- Read for context: existing `_convert_siqa_row` (closest analogue — context+question merge, numeric→letter).

## Implementation Steps
1. Add dict entries (`_SUPPORTED`, `_LICENSES`; `_REVISIONS` only if HF needs a parquet branch — check).
2. Implement `_convert_logiqa_row` mirroring `_convert_siqa_row` structure.
3. Add the `logiqa` branch in `_build_pool`; add `"logiqa"` to argparse `--dataset choices` (auto via `sorted(_SUPPORTED)`).
4. Run for seeds 42/43/44 into the three split dirs.
5. `--self-check` each output dir.

## Todo List
- [ ] Verify LogiQA HF field names + license via `datasets` load (a 3-row peek)
- [ ] Add dict entries + converter
- [ ] Wire branch in `_build_pool`
- [ ] Generate 3 seeded splits
- [ ] Self-check all 3 (expect train=100/val=300/test=200)

## Success Criteria
- 3 split dirs exist; each `--self-check` prints PASS with counts 100/300/200; gold letters ∈ {A,B,C,D}.

## Risk Assessment
- HF field names differ from assumption → mitigate by a 3-row peek before coding the converter.
- LogiQA ships a loader script (like SIQA) → may need `_REVISIONS["logiqa"]="refs/convert/parquet"`.

## Security Considerations
- None (public dataset, read-only download).

## Next Steps
- Feeds Phase 02 (config points at `data/mcqa_logiqa_split`) and Phase 03 (probe uses these splits).
