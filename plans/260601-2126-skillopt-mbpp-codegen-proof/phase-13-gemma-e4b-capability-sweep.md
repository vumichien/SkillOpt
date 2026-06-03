---
phase: 13
title: "Second Local Target Capability-Sweep (granite-code 8B; planned gemma4:e4b)"
status: completed
priority: P2
effort: "0.5-1d (mostly GPU wall-time)"
dependencies: [5, 11]
---

# Phase 13: Second Local Target Capability-Sweep — MBPP + bizSQL

## Context Links
- Brainstorm brief (authoritative design): `plans/reports/brainstorm-to-planner-260603-skillopt-gemma-e4b-capability-sweep-report.md`
- **Executed results report:** `plans/reports/phase13-second-target-granite-results.md`
- Second-target candidate research: `plans/reports/researcher-260603-second-target-model-candidates.md`
- Extends: Phase 5 (MBPP seed-42 flat), Phase 11 (bizSQL +8.2pp win), Phase 12 (combined article — this arm feeds its cross-family section).

## Results (Executed 2026-06-03) — COMPLETED

**Target pivot:** planned `gemma4:e4b` was disqualified. Both Gemma-3n "elastic" 4-bit builds (e2b + e4b) trip an
Ollama gemma4-renderer bug → empty-content generations (finish=length, len=0) for many inputs (e4b also ~6 tok/s);
the bug is the Gemma-3n arch + Ollama runtime, not the quant/Modelfile. After harness smoke-tests (qwen3:4b /
qwen3.5:4b also failed — thinking models burn the 1024-token budget on stripped reasoning), pivoted to
**`granite-code:8b-instruct-q4_K_M`** (IBM, dense, q4_K_M; 6/6 clean, ~40 tok/s, 0 empties). User-approved.

**Verdict — both task-family results replicate on a second, very different model (held-out n=200 test):**

| Track | Family | Base | Trained | Δ | Verdict |
|-------|--------|------|---------|-----|---------|
| MBPP | heterogeneous-procedural | 0.4400 | 0.4400 | **+0.00pp** | FLAT (val gate +5pp didn't transfer → overfit) |
| bizSQL | homogeneous-procedural | 0.2150 | 0.6400 | **+42.5pp** | WIN (z≈9.5; val gate 0.23→0.70 transferred) |

- **MBPP-flat = task-family fact, not a qwen artifact** — flat on qwen (0.65 base) AND granite (0.44 base).
- **bizSQL-WIN replicates AND is larger at low base** — qwen +8.2pp (3-seed, 0.88 base) / granite +42.5pp (0.215).
- Single-seed (n=1) capability arm. MBPP did NOT lift → no MBPP 3-seed scale-up (per pre-reg rule). bizSQL granite
  +42.5pp direction is safe (z≈9.5); the *magnitude* is n=1 and wants 3-seed (43/44) before being quoted as a point
  estimate. qwen runs untouched.

Full numbers, probe shares, winning-skill convention list, costs: see the executed results report linked above.

## Overview
Re-run MBPP + bizSQL with ONLY the target model swapped (`qwen2.5:7b-instruct-q4_K_M` → `gemma4:e4b` 4-bit) to
test whether MBPP's flatness is a model-capability artifact or a task-family fact. Adds a second, stronger local
target for the code/SQL families — matching the MC matrix's 2-target rigor and closing the "only tested on one
weak model" skeptic hole. Probe-gated; seed 42 only.

## Key Insights (from brainstorm + scout)
- Target swap is **config-only** — `model.target` is passed straight to Ollama via the `qwen_chat` backend (just
  a model-tag string). Probes already accept `--target` → zero edits to probe a new model.
- **VRAM is the hard constraint (RTX 3080 = 10 GB).** Per unsloth gemma-4 ref @ 4-bit: E4B 5.5–6 GB ✅ fits;
  26B-A4B 16–18 GB ❌ (MoE — all experts resident; CPU offload → ~1–3 tok/s → days; 2-bit lobotomizes). So **e4b
  4-bit is the only VRAM-safe step-up.** This is consistent with — not a reversal of — the plan's locked
  "14B/27B spill 10 GB VRAM" note; the "model not a lever" decision is being *measured*, at the user's request.
- bizSQL likely **ceilings** on a stronger model (qwen already 0.88; strong-ceiling ~1.00) → a flat bizSQL here is
  a ceiling effect ("stronger model already knows the conventions"), CONSISTENT with homogeneous-procedural — NOT
  a contradiction of the Phase-11 win. Pre-register this read so it can't be misread later.

## Requirements
- Functional: probe e4b baseline + procedural-share on MBPP and bizSQL (train split); gate; train seed-42 on
  gated track(s); report held-out n=200 Δ + binomial SE; leave qwen runs intact.
- Non-functional: change ONLY `model.target`; identical optimizer / hyperparams / `_s42` splits / weak-init skill
  / temp-0. Honest framing as a single-seed (n=1) capability arm — NOT equal-rigor to the 3-seed qwen runs.

## Architecture
Hold constant: optimizer `deepseek-v4-pro`, `initial-weak.md`, epochs 2 / batch 20 / minibatch 8 / lr 4→2 cosine /
gate on / no slow-update / no meta-skill, `data/{mbpp,bizsql}_split_s42`, temp 0, n=200 test. Vary ONLY the target.

Pipeline: **Stage 1 probe (cheap, no train)** → **Stage 2 pre-registered gate** → **Stage 3 seed-42 train (gated
tracks only)** → **Stage 4 interpret + feed article**.

### Pre-registered gate (Stage 2)
- **MBPP:** train iff `0.65 ≤ base ≤ ~0.85`. `base ≥ ~0.90` → log "no headroom (ceiling)", skip train.
- **bizSQL:** train iff `base < ~0.90`. `base ≥ ~0.93` → log "e4b near-ceiling → already knows conventions
  (consistent w/ homogeneous-procedural)", skip train.

## Related Code Files
- Create: `configs/mbpp/local-pilot-gemma-e4b.yaml` — `_base_: local-pilot.yaml`, override ONLY `model.target`
  (+ `env.workers: 4` if Stage-1 probe shows VRAM pressure). Pin the resolved e4b Ollama tag.
- Create: `configs/bizsql/local-pilot-gemma-e4b.yaml` — same pattern over `bizsql/local-pilot.yaml`.
- Read (no edits): `scripts/probe_mbpp_headroom.py`, `scripts/probe_bizsql_headroom.py`,
  `scripts/run_mbpp_pilot.ps1`, `scripts/run_bizsql_pilot.ps1`, `skillopt/model/qwen_backend.py`.
- Modify (Stage 4, only if results warrant): `docs/articles/medium-skillopt-mbpp-codegen-local.md` (add the
  second-target datapoint to the cross-family section); `plan.md` (mark Phase 13 status).
- Outputs (qwen-safe, new segments): `outputs/{mbpp,bizsql}_probe_gemma_e4b/`,
  `outputs/{mbpp,bizsql}-train/deepseek-v4-pro/gemma-e4b-s42/`.

## Implementation Steps
1. **Resolve + pin the e4b 4-bit Ollama tag.** Try `ollama pull hf.co/unsloth/gemma-4-E4B-it-GGUF:Q4_K_M`
   (fallback: list the repo's GGUF tags, pick the 4-bit `UD-Q4_K_XL`/`Q4_K_M`, confirm it loads). Record the exact
   tag string; it goes verbatim in both configs. Confirm it loads in <10 GB (`nvidia-smi` while warm).
2. **Write the two gemma-e4b configs** inheriting the qwen configs, overriding only `model.target`.
3. **Stage 1 — probe both tracks** (`.env.local-pilot` auto-loaded; e4b pulled):
   - `.venv\Scripts\python.exe scripts\probe_mbpp_headroom.py --split-dir data/mbpp_split_s42 --split train --target <e4b-tag> --out-dir outputs/mbpp_probe_gemma_e4b`
   - `.venv\Scripts\python.exe scripts\probe_bizsql_headroom.py --split-dir data/bizsql_split_s42 --split train --target <e4b-tag> --out-dir outputs/bizsql_probe_gemma_e4b`
   - If OOM / heavy queueing, set `env.workers: 4` in the configs and re-probe.
4. **Stage 2 — apply the gate** per track; log base vs threshold and the train/skip decision.
5. **Stage 3 — train seed-42** on gated track(s) via existing pilots:
   - `$env:SKILLOPT_CONFIG="configs/mbpp/local-pilot-gemma-e4b.yaml"; $env:SKILLOPT_OUT_ROOT="outputs/mbpp-train/deepseek-v4-pro/gemma-e4b-s42"; $env:SKILLOPT_SEED="42"; scripts\run_mbpp_pilot.ps1`
   - `$env:SKILLOPT_CONFIG="configs/bizsql/local-pilot-gemma-e4b.yaml"; $env:SKILLOPT_OUT_ROOT="outputs/bizsql-train/deepseek-v4-pro/gemma-e4b-s42"; $env:SKILLOPT_SEED="42"; scripts\run_bizsql_pilot.ps1`
6. **Stage 4 — interpret + report.** Write a results report under `plans/.../reports/`. e4b Δ vs qwen Δ, base vs
   gate, accepts, wall/tokens/GPU. If MBPP **lifts** on e4b → flag 3-seed scale-up as a conditional follow-up
   BEFORE any article thesis change (per "decide after numbers"). Fold the datapoint into Phase-12 article.

## Todo List
- [x] Second-target model resolved (planned e4b disqualified by Gemma-3n renderer bug → granite-code 8B), confirmed loads <10 GB, pinned in configs
- [x] `configs/mbpp/local-pilot-granite-8b.yaml` created (only `model.target` + `workers:4` differ from qwen config)
- [x] `configs/bizsql/local-pilot-granite-8b.yaml` created (only `model.target` + `workers:4` differ)
- [x] Stage-1 probe run both tracks; `probe_failures.json` written; `workers=4` finalized (MBPP 0.46, bizSQL 0.26, 0 empties)
- [x] Stage-2 gate decision logged per track (MBPP floor-override surfaced to user; bizSQL clears headroom)
- [x] Stage-3 seed-42 train completed both tracks; qwen artifacts untouched
- [x] Stage-4 results report written; article datapoint added; MBPP did NOT lift → no MBPP 3-seed; bizSQL n=1 magnitude flagged for 3-seed

## Success Criteria
- [x] Second-target probe baseline pass@1 + procedural-share recorded (real numbers): MBPP 0.46 (20% naming), bizSQL 0.26 (32% schema/dialect).
- [x] Gate decision explicit and logged per track with measured base vs threshold (MBPP floor-override surfaced; bizSQL clears).
- [x] Both tracks: seed-42 train completes; held-out n=200 Δ + binomial SE reported (MBPP +0.00±3.5pp; bizSQL +42.5pp, z≈9.5); qwen runs intact.
- [x] Framed as single-seed capability arm; MBPP did NOT lift → no scale-up; bizSQL magnitude flagged for 3-seed.
- [x] Phase-12 article updated with the second-local-target datapoint; honest verdict (MBPP-flat = family fact, bizSQL-WIN replicates).

## Risk Assessment
- **e4b OOM @ workers:8** (~6 GB weights + 8× KV on 10 GB) → Stage-1 probe flushes it; fall back `workers:4`;
  watch `gpu.csv`. Mitigated by probing before training.
- **e4b tag won't pull / wrong quant** → resolve + pin in Step 1 before any run; run scripts fail-fast on
  unresolvable tags.
- **bizSQL ceiling misread as "win was fragile"** → pre-registered interpretation (Stage 2) prevents this.
- **Scope creep to 3 seeds / 26b / cloud** → out of scope; 3-seed is a *conditional follow-up* only if MBPP lifts;
  26b is VRAM-infeasible; cloud breaks the local-OSS brand.
