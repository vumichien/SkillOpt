# Phase 03 — Headroom-Probe GATE (Arms 1+2 Baselines)

## Context Links
- Eval tool: `scripts/eval_skill_on_dataset.py` (zero-shot, reuses trainer rollout/scoring)
- Skills: `initial-weak.md` (arm 1), `generic-cot.md` (arm 2, from Phase 02)

## Overview
- **Priority:** P0 — **DECISION GATE**. Cheap (no optimizer spend) and prevents a wasted loop.
- **Status:** pending
- Measure raw + generic-CoT baselines on LogiQA test for all 4 targets; decide go vs escalate.

## Key Insights
- The entire experiment hinges on headroom. If even the weakest target (2B) is already near-ceiling on
  LogiQA, the loop will be flat for the same reason CSQA/SIQA were — so probe FIRST.
- `eval_skill_on_dataset.py` already counts `errors` (failed rollouts) so a broken run can't masquerade as flat.

## Requirements
- Functional: produce arm-1 and arm-2 test accuracy for each of 4 targets on the seed-42 LogiQA test (200 items).
- Decision rule: if **min over targets of arm-1 baseline > ~0.80**, headroom is too thin → escalate dataset
  (ReClor or LogiQA-2.0) by repeating Phase 01 with the harder source, then re-run this gate.

## Architecture
- 8 eval runs (4 targets × 2 arms), each: set `TARGET_DEPLOYMENT`, run
  `eval_skill_on_dataset.py --skill <arm skill> --split-dir data/mcqa_logiqa_split --split test --out-dir outputs/logiqa-probe/<target>-<arm>`.
- Collect `summary.json` accuracies into a 4×2 table.

## Related Code Files
- Use (no edit): `scripts/eval_skill_on_dataset.py`
- Create: `outputs/logiqa-probe/*/summary.json` (artifacts)

## Implementation Steps
1. For each target × {arm1=initial-weak.md, arm2=generic-cot.md}: run eval on seed-42 test.
2. Tabulate acc + errors; confirm errors=0 everywhere.
3. Apply decision rule. If escalate → loop back to Phase 01 with ReClor/LogiQA-2.0; else proceed to Phase 04.

## Todo List
- [ ] 8 baseline evals (4 targets × 2 arms), errors=0
- [ ] Build 4×2 baseline table
- [ ] Apply gate decision (go / escalate) and record rationale

## Success Criteria
- Complete 4×2 baseline table with errors=0; explicit recorded go/escalate decision.
- GO requires ≥1 target with arm-1 baseline ≤ ~0.75 (clear headroom) on LogiQA.

## Risk Assessment
- All targets near-ceiling → escalate dataset (built-in mitigation; do NOT push a doomed loop).
- gemma4:e4b answer-format parse failures inflate "errors" → inspect a few results.jsonl rows; fix prompt/extraction if needed (extractor is 5-level, should be robust).

## Security Considerations
- None.

## Next Steps
- GO → Phase 04 training loop. ESCALATE → Phase 01 (harder dataset), then re-gate.
