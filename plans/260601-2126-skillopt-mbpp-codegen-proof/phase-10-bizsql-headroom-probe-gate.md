---
phase: 10
title: "BizSQL Headroom Probe Gate"
status: code-complete-run-deferred
priority: P1
effort: "3-4h"
dependencies: [9]
---

# Phase 10: BizSQL Headroom Probe Gate

# ⛔ HARD GATE — do not start Phase 11 (full training) until this passes.

## Overview
Before spending GPU on the full loop, prove two things: (1) the task is **solvable** (a strong model scores
near-ceiling → the headroom is real, the win is not engineered), and (2) the local 7B's failures are
*procedural* (skill-fixable), not *capability* (model can't write the SQL). Text-to-SQL is more
capability-sensitive than MBPP — this gate is the single biggest risk for the business track.

## Requirements
- Functional: run the weak-init skill on 100 items (train/val, NOT test) → baseline execution-accuracy + dump
  every failure; run a STRONG model on the same items → strong-model ceiling; support manual procedural-vs-
  capability categorization of a ~20-failure sample.
- Non-functional: deterministic (temp=0), resume-aware, writes a probe report under the plan dir.

## Architecture
- `scripts/probe_bizsql_headroom.py`: load `data/bizsql_split_s42` **train/val** (keep test locked), build the
  `BizsqlAdapter` rollout with `skills/initial-weak.md`, run execution-accuracy over 100 items.
  - **Arm A (target baseline):** `qwen2.5:7b-instruct` weak-init pass@1. For each FAIL write
    `{id, question, difficulty, predicted_sql, detail, gold_sql}` → `probe_failures.json`.
  - **Arm B (strong-model ceiling):** same 100 items through the strong model (DeepSeek/Claude) with the SAME
    weak prompt → ceiling accuracy. This is the **engineered-win guardrail**: if a strong model can't clear
    ~90%, the dataset is ill-posed (ambiguous/over-hard) — fix the data (Phase 8), don't train.
- Auto-bucket target failures by `detail`/diff into coarse classes for triage:
  - `extraction/format` (no SQL block, prose, multi-statement) → procedural
  - `wrong_column/table_name` (OperationalError: no such column) → procedural (schema grounding)
  - `missing_filter` (runs, wrong rows — forgot status/refund/date filter) → procedural
  - `wrong_join` (runs, wrong rows — bad/missing join key) → mostly procedural
  - `wrong_aggregation/groupby` (GROUP BY discipline) → procedural
  - `genuinely_wrong_logic` (correct schema use, still wrong intent) → likely capability
- **Manual step (the actual gate):** read ~20 sampled target failures, label procedural vs capability, tally
  the procedural share. Auto-buckets are a starting point, not the verdict.

## Related Code Files
- Create: `scripts/probe_bizsql_headroom.py`.
- Create (output): `plans/260601-2126-skillopt-mbpp-codegen-proof/reports/bizsql-headroom-probe-report.md`
  (Arm A baseline, Arm B strong ceiling, bucket tally, ~20 hand-labeled failures, GATE verdict).
- Read for context: `scripts/probe_mbpp_headroom.py` (Phase-3 analog), `skillopt/envs/bizsql/*`,
  `skillopt/model.py` (strong-model client for Arm B).

## Implementation Steps
1. Write the probe script (reuse `BizsqlAdapter.build_eval_env` + rollout on train/val, weak skill; add the
   Arm-B strong-model pass).
2. Run under `.venv`, `PYTHONUTF8=1`; record Arm A baseline, Arm B ceiling, per-failure detail.
3. Auto-bucket; hand-label a 20-failure sample procedural vs capability.
4. Write the probe report with an explicit verdict.

## Success Criteria (GATE)
- [ ] Arm A baseline measured on 100 items (expected ~0.25–0.55 for qwen2.5:7b-instruct on grounded SQL).
- [ ] **Arm B strong-model ceiling ≥ ~90%** (proves the task is solvable / not engineered-hard). If < ~85% →
      FAIL the dataset: revisit Phase 8 (ambiguous questions, wrong gold, over-hard band), do NOT train.
- [ ] **PASS condition:** ≥ ~10–15 pp of total items are *procedural* failures (skill-fixable headroom), AND
      Arm B clears the ceiling bar.
- [ ] Probe report written with verdict PASS/FAIL and the hand-labeled sample.

## Risk Assessment / Gate Outcomes
- **PASS** → proceed to Phase 11.
- **FAIL (capability-floored: failures genuinely-wrong-logic, low procedural share)** → STOP. Surface the locked
  fallback: switch target to `qwen2.5-coder:7b` (raises SQL ceiling, fits 10 GB) at the cost of the
  "same target as MC/MBPP" story — OR ease the difficulty bands in Phase 8 (more easy/med, fewer hard). Do NOT
  silently change the target; ask the user (per the locked decision).
- **FAIL (Arm B ceiling low)** → dataset problem, not a model problem: fix gold/questions/bands in Phase 8 and
  re-probe. This is the engineered-win guardrail doing its job.
- **Borderline (baseline already high, little room)** → schema/questions too easy; add harder med-band items or
  drop the schema-DDL hint for a subset. Ask user.
