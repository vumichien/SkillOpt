---
phase: 5
title: "Seed-42 Pilot and 3-Arm Eval"
status: pending
priority: P1
effort: "0.5d (mostly GPU wall-time)"
dependencies: [3, 4]
---

# Phase 5: Seed-42 Pilot and 3-Arm Eval

# Decision gate: only scale to 3 seeds (Phase 6) if held-out Δ clears ±1 SE with ≥1 accept.

## Overview
Run the full SkillOpt loop on MBPP seed-42 and read the held-out result. This is the proof-of-mechanism run:
same loop / optimizer / GPU / target that was flat on MC, now on a procedure-bound task.

## Requirements
- Functional: one training run; extract the 3 arms (weak-init baseline test, trained test, accepts).
- Non-functional: deterministic eval (temp=0 gate via target), resume-aware, GPU sampled.

## Architecture
- Run: `.\scripts\run_mbpp_pilot.ps1` (config `configs/mbpp/local-pilot.yaml`, split `data/mbpp_split_s42`,
  seed 42, out `outputs/mbpp-train/deepseek-v4-pro/qwen7b-s42`). Set `SKILLOPT_*` env vars like the MC matrix.
- 3-arm read (same protocol as the MC plan's Step 2):
  - **arm-1 (baseline)** = `test_eval_baseline/summary.json` → `overall.hard_acc` (weak init, no optimization).
  - **arm-3 (trained)** = `test_eval/summary.json` → `overall.hard_acc` (best gated skill).
  - **accepts** = count `action == "accept"` steps in `history.json` (0 accepts ⇒ arm-3 == arm-1).
  - **real effect** = arm-3 − arm-1 on the 200-item held-out test.
- Also capture: dev trajectory (per-step sel score), skill growth (bytes), accepts list, DeepSeek token spend,
  wall time, GPU duty cycle — all for the article's per-step section.

## Related Code Files
- Read (outputs): `outputs/mbpp-train/deepseek-v4-pro/qwen7b-s42/{history.json, best_skill.md, test_eval*/summary.json, gpu.csv}`.
- Optional: `scripts/eval_skill_on_dataset.py` for any extra cross-check eval.
- Create (output): append pilot numbers to a scratch results note under the plan `reports/` dir (not the article yet).

## Implementation Steps
1. Ensure Phase-3 gate PASSED. Ensure Ollama up + model warm, `.env.local-pilot` keys present.
2. Run the pilot; monitor `[rollout]` progress + GPU sampler.
3. Extract the 3 arms + trajectory; save the per-step trace (one representative step: failed rollouts →
   reflection JSON under `steps/step_XXXX/` → skill diff → gate decision) for the article.
4. Record verdict against the gate.

## Success Criteria (Decision Gate)
- [ ] Run completes; `best_skill.md`, `history.json`, `test_eval*/summary.json` present.
- [ ] 3 arms extracted; accepts counted; dev trajectory captured.
- [ ] **SCALE condition (→ Phase 6):** held-out Δ (arm-3 − arm-1) beyond +1 binomial SE (~+3.5 pp @ n=200)
      AND ≥1 accept with monotonic dev climb.
- [ ] If Δ within noise or 0 accepts → STOP, diagnose (revisit Phase-3 categorization, reflect-prompt fit, or
      target capability), and surface options to user before any further GPU spend.

## Risk Assessment
- **Flat despite procedural headroom** → likely reflect-prompt fit (generic QA analyst prompts on code). Mitigation:
  add code-specific `mbpp/prompts/analyst_error.md`+`analyst_success.md` and re-run seed 42 once (the deferred
  YAGNI item from Phase 2). This is the primary fallback before abandoning.
- **Overfit (dev climbs, test flat)** → conventions should generalize; if not, the task may be too heterogeneous —
  note and proceed to 3 seeds only if the gate is genuinely cleared.
