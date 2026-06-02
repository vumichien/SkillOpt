---
phase: 6
title: "Three-Seed Scale and Aggregate"
status: pending
priority: P2
effort: "0.5d (GPU wall-time)"
dependencies: [5]
---

# Phase 6: Three-Seed Scale and Aggregate

## Overview
Only if the seed-42 pilot cleared the gate: reproduce on seeds 43 and 44 and report mean ± std of the held-out
delta, matching the rigor of the flat MC experiments so the contrast is fair.

## Requirements
- Functional: generate seed 43/44 splits; run the loop on each; aggregate mean ± std of arm-3 − arm-1.
- Non-functional: deterministic per-seed; same config; resume-aware.

## Architecture
- Data: `python scripts/prepare_mbpp_data.py --seed 43 --out-dir data/mbpp_split_s43` (and 44). Same
  100/100/200, same gold-code sanity filter.
- Runs: drive the existing runner with `SKILLOPT_SPLIT_DIR`/`SKILLOPT_SEED`/`SKILLOPT_OUT_ROOT` per seed into
  `outputs/mbpp-train/deepseek-v4-pro/qwen7b-s{43,44}` (one Ollama target on the GPU at a time; sequential).
- Aggregate: per-seed arm-1/arm-3/Δ/accepts table + mean ± std of Δ; compare to the MC mean (−0.6 pp) for the
  headline contrast.

## Related Code Files
- Reuse: `scripts/prepare_mbpp_data.py`, `scripts/run_mbpp_pilot.ps1`.
- Read: each seed's `outputs/.../{history.json, test_eval*/summary.json}`.
- Create (output): `plans/260601-2126-skillopt-mbpp-codegen-proof/reports/mbpp-3seed-results.md` (the numbers the article cites).

## Implementation Steps
1. Generate s43/s44 splits.
2. Run seed 43, then seed 44 (sequential GPU).
3. Extract 3 arms per seed; compute mean ± std Δ + total accepts.
4. Write the aggregate results note.

## Success Criteria
- [ ] 3 seeds complete; per-seed arms extracted.
- [ ] Mean Δ positive and outside noise (mean > ~+3.5 pp / sqrt(3), or each seed individually positive with low std).
- [ ] Aggregate note written with the flat-MC vs lift-MBPP contrast numbers.

## Risk Assessment
- **One seed flat (like SocialIQA seed 43)** → report honestly with mean ± std; a single near-ceiling/low-headroom
  shuffle is expected and not a failure if the mean clears noise.
- **GPU contention** → keep runs strictly sequential; the runner's warm-up + resume handles interruptions.
