---
phase: 3
title: "Headroom Probe Gate"
status: code-complete-run-deferred
priority: P1
effort: "3-4h"
dependencies: [2]
---

# Phase 3: Headroom Probe Gate

# ⛔ HARD GATE — do not start Phase 5 (full training) until this passes.

## Overview
Before spending GPU on the full loop, prove the baseline failures are *procedural* (skill-fixable), not
*capability* (model can't solve it). This is the single biggest risk: if qwen2.5:7b-instruct's MBPP failures
are mostly capability, the loop goes flat for the same reason gemma-LogiQA did.

## Requirements
- Functional: run weak-init skill on 100 items, report baseline pass@1, dump every failure's signature, support
  manual procedural-vs-capability categorization of a ~20-failure sample.
- Non-functional: deterministic (temp=0), resume-aware, writes a probe report under the plan dir.

## Architecture
- `scripts/probe_mbpp_headroom.py`: load `data/mbpp_split_s42` (use the **train** or **val** split, NOT test —
  keep test locked), build the `MbppAdapter` rollout with `skills/initial-weak.md`, run pass@1 over 100 items,
  and for each FAIL write `{id, prompt, predicted_code, detail, n_pass}` to `probe_failures.json`.
- Auto-bucket failures by `detail` signature into coarse classes for triage:
  - `extraction/format` (no code block, prose, wrong fences) → procedural
  - `wrong_signature/name` (NameError / TypeError on call) → procedural
  - `edge_case` (passes example assert, fails another) → mostly procedural
  - `timeout` → mixed (could be infinite loop = procedural, or brute force = capability)
  - `assertion_wrong_logic` (runs, wrong answer, no obvious format issue) → likely capability
- **Manual step (the actual gate):** read ~20 sampled failures, label procedural vs capability, tally the
  procedural share. The auto-buckets are a starting point, not the verdict.

## Related Code Files
- Create: `scripts/probe_mbpp_headroom.py`.
- Create (output): `plans/260601-2126-skillopt-mbpp-codegen-proof/reports/mbpp-headroom-probe-report.md`
  (baseline pass@1, bucket tally, ~20 hand-labeled failures, GATE verdict).

## Implementation Steps
1. Write the probe script (reuse `MbppAdapter.build_eval_env` + `rollout` on the train/val split, weak skill).
2. Run under `.venv`, `PYTHONUTF8=1`; record baseline pass@1 and per-failure detail.
3. Auto-bucket; then hand-label a 20-failure sample into procedural vs capability.
4. Write the probe report with an explicit verdict.

## Success Criteria (GATE)
- [ ] Baseline pass@1 measured on 100 items (expected ~0.4–0.65 for qwen2.5:7b-instruct).
- [ ] **PASS condition:** ≥ ~10–15 pp of total items are procedural failures (skill-fixable headroom).
- [ ] Probe report written with verdict PASS/FAIL and the hand-labeled sample.

## Risk Assessment / Gate Outcomes
- **PASS** → proceed to Phase 4/5.
- **FAIL (capability-floored)** → STOP. Surface to user the brainstorm's open question: switch target to
  `qwen2.5-coder:7b` (raises code ceiling, still fits 10 GB) at the cost of the "same target as MC" story — or
  reduce task difficulty (MBPP `sanitized` subset is easier). Do NOT silently change the target; ask.
- **Borderline (baseline very high, little room)** → MBPP is too easy for this target; consider not pinning the
  signature, or a harder split. Ask user.
