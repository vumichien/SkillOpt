# Phase 04 — SkillOpt Training Loop (Arm 3) ×4 Targets ×3 Seeds

## Context Links
- Loop: `scripts/train.py`; launcher `scripts/run_local_pilot.ps1`
- Config: `configs/mcqa/local-pilot-logiqa.yaml` (Phase 02)
- Pattern: prior SocialIQA per-seed runs (`outputs/mcqa_siqa_s4{2,3,4}`)

## Overview
- **Priority:** P0 (only after Phase 03 GO)
- **Status:** pending
- Run the full optimize-and-gate loop from weak init (arm 3) for each target × seed.

## Key Insights
- Launcher honors `SKILLOPT_CONFIG`, `SKILLOPT_SPLIT_DIR`, `SKILLOPT_OUT_ROOT`, `TARGET_DEPLOYMENT` — so the
  whole matrix is env-var permutations over one config; no new code.
- Per-seed split dirs from Phase 01 (`data/mcqa_logiqa_split[_s43|_s44]`) drive the 3 seeds.
- Each run already writes `best_skill.md`, `history.json`, `summary.json` (val/test acc), `gpu.csv`, token spend.

## Requirements
- Functional: 12 runs (4 targets × 3 seeds) complete; each emits arm-3 test acc + accepts trajectory.
- Non-functional: deterministic eval (temp 0); GPU-only (no CPU spill) for the 3 small targets.

## Architecture
- Loop over targets × seeds:
  `$env:TARGET_DEPLOYMENT=<tag>; $env:SKILLOPT_CONFIG="configs/mcqa/local-pilot-logiqa.yaml";`
  `$env:SKILLOPT_SPLIT_DIR=<seed split dir>; $env:SKILLOPT_OUT_ROOT="outputs/logiqa_<target>_s<NN>"; ./scripts/run_local_pilot.ps1`
- Keep v3 hyperparams (2 epochs → 10 candidate edits). Weak init = arm 1 skill (`skill_init` in base config).

## Related Code Files
- Use (no edit): `scripts/train.py`, `scripts/run_local_pilot.ps1`
- Create: `outputs/logiqa_<target>_s<NN>/` ×12

## Implementation Steps
1. Confirm Ollama up + each target warm (launcher auto-pulls/warms).
2. Run the 12-run matrix sequentially (small models are fast; monitor `gpu.csv` for spill on gemma4:e4b).
3. Capture per-run `summary.json` (baseline vs trained test acc) + accepts count + token spend.
4. Sanity: errors=0 in each run's results; reject any run with degenerate (all-error) rollouts and rerun.

## Todo List
- [ ] 12 runs (4 targets × seeds 42/43/44)
- [ ] Collect summary.json + history.json per run
- [ ] Verify errors=0; note wall-time + DeepSeek spend per run
- [ ] Archive best_skill.md per target (for the article's "what it wrote" section)

## Success Criteria
- 12 completed runs with errors=0; arm-3 test acc + accepts recorded for each (target,seed).

## Risk Assessment
- gemma4:e4b CPU-spill → if `gpu.csv` shows low util / slow, reduce context or accept slower run (still valid).
- Optimizer (DeepSeek) transient API errors → backend already retries 5×; rerun a failed run (resume-aware).

## Security Considerations
- Key from `.env.local-pilot` only.

## Next Steps
- Feeds Phase 05 (aggregate arm-3 vs arm-2/arm-1 across seeds).
