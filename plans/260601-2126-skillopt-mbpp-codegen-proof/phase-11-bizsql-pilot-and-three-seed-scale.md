---
phase: 11
title: "BizSQL Pilot and Three-Seed Scale"
status: pending
priority: P1
effort: "1d (mostly GPU wall-time)"
dependencies: [10]
---

# Phase 11: BizSQL Seed-42 Pilot and Three-Seed Scale

# Decision gate: only scale to 3 seeds if seed-42 held-out Δ clears ±1 SE with ≥1 accept.

## Overview
Run the full SkillOpt loop on bizsql seed-42 and read the held-out result — the proof-of-mechanism run for the
self-generated business task: same loop / optimizer / GPU / target that was flat on MC, now on a procedure-bound
SQL task. If the pilot clears the gate, reproduce on seeds 43/44 and report mean ± std.

## Requirements
- Functional: seed-42 training run + 3-arm extraction (weak-init baseline test, trained test, accepts); if gate
  clears → seed 43/44 splits + runs + aggregate mean ± std of arm-3 − arm-1.
- Non-functional: deterministic eval (temp=0 gate), resume-aware, GPU sampled, sequential per-seed (one Ollama
  target on the GPU at a time).

## Architecture
- Pilot run: `.\scripts\run_bizsql_pilot.ps1` (config `configs/bizsql/local-pilot.yaml`, split
  `data/bizsql_split_s42`, seed 42, out `outputs/bizsql-train/deepseek-v4-pro/qwen7b-s42`). Set `SKILLOPT_*`
  env vars like the MC/MBPP matrices.
- 3-arm read (same protocol as the MBPP/MC plans):
  - **arm-1 (baseline)** = `test_eval_baseline/summary.json` → `overall.hard_acc` (weak init).
  - **arm-3 (trained)** = `test_eval/summary.json` → `overall.hard_acc` (best gated skill).
  - **accepts** = count `action == "accept"` in `history.json` (0 accepts ⇒ arm-3 == arm-1).
  - **real effect** = arm-3 − arm-1 on the 200-item held-out test.
- Capture for the article: dev trajectory (per-step sel score), skill growth (bytes), accepts list, one clean
  per-step trace (failed SQL rollouts → reflection JSON under `steps/step_XXXX/` → skill diff before/after →
  gate decision → held-out effect), DeepSeek token spend, wall time, GPU duty cycle.
- 3-seed scale (only if gate clears): `python scripts/prepare_bizsql_data.py --seed 43 --out-dir
  data/bizsql_split_s43` (and 44; same DB, same validation/stratify). Drive the runner with
  `SKILLOPT_SPLIT_DIR`/`SKILLOPT_SEED`/`SKILLOPT_OUT_ROOT` per seed → `outputs/bizsql-train/deepseek-v4-pro/
  qwen7b-s{43,44}`. Aggregate per-seed arm-1/arm-3/Δ/accepts + mean ± std.

## Related Code Files
- Reuse: `scripts/run_bizsql_pilot.ps1`, `scripts/prepare_bizsql_data.py`.
- Read (outputs): each seed's `outputs/bizsql-train/deepseek-v4-pro/qwen7b-s{42,43,44}/{history.json,
  best_skill.md, test_eval*/summary.json, gpu.csv, steps/step_XXXX/}`.
- Create (output): `plans/260601-2126-skillopt-mbpp-codegen-proof/reports/bizsql-3seed-results.md` (the numbers
  the article cites: per-seed arms + mean ± std Δ + total accepts + cost/wall/GPU).

## Implementation Steps
1. Ensure Phase-10 gate PASSED; Ollama up + model warm; `.env.local-pilot` keys present; `business.sqlite` exists.
2. Run the seed-42 pilot; monitor `[rollout]` progress + GPU sampler.
3. Extract the 3 arms + trajectory; save the representative per-step trace for the article.
4. Evaluate against the scale gate (below). If cleared: generate s43/s44 splits, run sequentially, extract arms.
5. Compute mean ± std Δ + total accepts; write `bizsql-3seed-results.md` with the flat-MC vs lift contrast.

## Success Criteria (Decision Gate)
- [ ] Seed-42 run completes; `best_skill.md`, `history.json`, `test_eval*/summary.json` present; 3 arms extracted.
- [ ] **SCALE condition (→ 3 seeds):** held-out Δ (arm-3 − arm-1) beyond +1 binomial SE (~+3.5 pp @ n=200) AND
      ≥1 accept with monotonic dev climb.
- [ ] If scaled: 3 seeds complete; mean Δ positive and outside noise (mean > ~+3.5 pp / √3, or each seed
      individually positive with low std).
- [ ] `bizsql-3seed-results.md` written with the flat-MC vs lift-bizSQL contrast numbers.
- [ ] If Δ within noise or 0 accepts → STOP, diagnose (revisit Phase-10 categorization, reflect-prompt fit, or
      target capability), surface options to user before further GPU spend.

## Risk Assessment
- **Flat despite procedural headroom** → likely reflect-prompt fit (generic QA analyst prompts on SQL).
  Mitigation: add SQL-specific `bizsql/prompts/analyst_error.md`+`analyst_success.md` and re-run seed 42 once
  (the deferred YAGNI item from Phase 9). Primary fallback before abandoning.
- **Overfit (dev climbs, test flat)** → schema conventions should generalize across all items; if not, questions
  too heterogeneous — note honestly, scale only if the gate is genuinely cleared.
- **One seed flat** (like SocialIQA seed 43) → report mean ± std honestly; a single low-headroom shuffle is
  expected, not a failure, if the mean clears noise.
- **GPU contention** → strictly sequential runs; runner warm-up + resume handle interruptions.
