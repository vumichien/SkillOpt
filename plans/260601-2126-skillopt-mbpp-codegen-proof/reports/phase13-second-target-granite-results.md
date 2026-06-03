# Phase 13 Results — Second Local Target Capability Sweep (granite-code 8B)

**Date:** 2026-06-03 · **Seeds:** 42 (n=1 capability arm) · **Optimizer:** deepseek-v4-pro (fixed) ·
**Target:** `granite-code:8b-instruct-q4_K_M` (Ollama, RTX 3080)

## TL;DR

Swapped ONLY the target model (qwen2.5:7b → granite-code 8B); held optimizer / hyperparams / `_s42` splits /
weak-init / temp-0 / n=200 test constant. Both task-family verdicts **replicate on a second, very different
model**:

| Track | Family | Target | Base (test n=200) | Trained | Δ | Verdict |
|-------|--------|--------|-------------------|---------|-----|---------|
| MBPP | heterogeneous-procedural | qwen2.5 7B (prior) | 0.65 | 0.62 | −3pp | FLAT |
| MBPP | heterogeneous-procedural | **granite-code 8B** | **0.4400** | **0.4400** | **+0.00pp** | **FLAT** |
| bizSQL | homogeneous-procedural | qwen2.5 7B (prior, 3-seed) | ~0.88 | — | **+8.2pp** | WIN |
| bizSQL | homogeneous-procedural | **granite-code 8B** | **0.2150** | **0.6400** | **+42.5pp** | **WIN (huge)** |

**Headline:** MBPP-flat and bizSQL-WIN are **task-family facts, not qwen-capability artifacts.** The
"transferable procedural structure" lever holds across a wide base-capability gap (qwen MBPP 0.65 / granite 0.44 =
21pp; qwen bizSQL 0.88 / granite 0.215) — and the bizSQL lift is *larger* at low base (more convention headroom to fill).

## Why granite-code (not the planned gemma4:e4b)

Phase 13 was written for `gemma4:e4b`. Both Gemma-3n "elastic" 4-bit builds (e2b AND e4b) are **disqualified by an
Ollama gemma4-renderer bug**: for many inputs they emit tokens that decode to **empty content** (finish=length,
len=0) — e2b 3/4 empty, e4b ~all empty, e4b also ~6 tok/s. The bug is the Gemma-3n arch + Ollama runtime, not the
quant or the Modelfile (identical template to a working gemma3:4b). After researching candidates and **smoke-testing
on the exact harness** (research "stable" claims were insufficient — qwen3:4b/qwen3.5:4b looked fine on paper but
burned the 1024-token budget on stripped reasoning → 3/4 empty), `granite-code:8b-instruct-q4_K_M` (IBM, dense,
q4_K_M) verified clean: 6/6 real outputs, ~40 tok/s, 0 empties. Pivot approved by user. This keeps the local-OSS
brand and stays VRAM-safe (<10 GB at workers=4).

## Stage 1 — Probes (train split, no training)

| Track | Base | Empties | Procedural-fixable share | Gate decision |
|-------|------|---------|--------------------------|---------------|
| MBPP | 0.46 | 0 | 20% wrong-signature-name (skill-fixable convention) | TRAIN* |
| bizSQL | 0.26 | 0 | 32% schema-name + SQLite-dialect (`no such column`, `YEAR()`→strftime) | TRAIN |

*MBPP base 0.46 sits below the pre-registered `0.65 ≤ base ≤ 0.85` floor. Floor overridden (surfaced to user):
the floor encodes "capability-bound below it," but the probe showed 20% of failures are a pure naming convention
SkillOpt can teach — violating the floor's assumption. Training it was the honest test, and the flat held-out
result (below) confirms the *family* overfits regardless of base.

## Stage 3 — Training results (seed 42, held-out n=200 test)

### MBPP granite — FLAT (Δ = +0.0000)
- baseline_test_hard = **0.4400** (88/200); test_hard = **0.4400** (88/200); **Δ = +0.0000**
- Selection gate DID move: 0.3700 → 0.4200 (+5pp, best at step 1), 1 accept / 6 reject / 3 skip.
- Binomial SE @ p=0.44, n=200 ≈ **±3.5pp**; Δ=0 is dead-center noise.
- **Overfit signature:** the trained skill correctly encoded the convention the probe flagged —
  *"Return ONE python block with the exact name implied by the example test… count the arguments carefully…
  return type must match the example assert"* — which lifted the n=100 selection set but **did not transfer** to
  held-out. Each MBPP problem is its own algorithm; there is no shared procedure for a skill doc to carry across
  items. Same outcome as qwen MBPP (−3pp seed-42, 3-seed gated off).
- Cost: 2329s wall, 888K tokens (669K prompt / 218K completion, 1439 calls).

### bizSQL granite — WIN (Δ = +0.4250)
- baseline_test_hard = **0.2150** (43/200); test_hard = **0.6400** (128/200); **Δ = +0.4250 (+42.5pp)**
- Selection gate climbed 0.2300 → 0.5300 → 0.5700 → **0.7000** (best at step 7), 3 accept / 6 reject / 1 skip.
  Unlike MBPP, this gate lift **fully transferred** to held-out test.
- Binomial SE: base ±2.9pp, trained ±3.4pp; unpaired SE of difference ≈ **±4.5pp** → **z ≈ 9.5**, overwhelmingly
  beyond ±1 SE (paired McNemar would be even tighter).
- **Transfer mechanism — the winning skill (98→4451 chars) is a small SHARED convention set** every held-out
  query reuses:
  1. JOIN `customers` when filtering/grouping by `region`/`country` (else `no such column: region`).
  2. Dates are ISO text `'YYYY-MM-DD'` → direct lexicographic range comparison; **avoid `YEAR()`/`strftime`**.
  3. Quarter-boundary mapping (Q1→Jan, Q2→Apr, Q3→Jul, Q4→Oct; half-open ranges).
  4. Revenue excludes `status IN ('refunded','cancelled')`.
  5. Product-filtered revenue = `SUM(order_items.qty*unit_price)` not `orders.total_amount`; quantity = `SUM(qty)`.
  6. Output contract: one `SELECT`/CTE, no prose.
  These are ~6 conventions shared by ALL items → the skill doc generalizes. This is exactly homogeneous-procedural.
- Cost: 3368s wall, 4.14M tokens (3.82M prompt / 315K completion, 1647 calls). Prompt-heavy because each rollout
  carries the full 6-table schema; ~4.7× MBPP's token cost.

## Interpretation vs the task-family thesis

The lever is **transferable procedural structure**, confirmed on a second model:

- **Knowledge-bound (MC):** FLAT both prior optimizer arms — no procedure to teach. (Phase 1–earlier.)
- **Heterogeneous-procedural (MBPP):** FLAT on qwen (0.65 base) AND granite (0.44 base). A real convention exists
  (function naming) and the optimizer *finds* it (selection gate moves), but per-item algorithms don't share
  structure → held-out flat. **Two models, two base levels, same flat → not a capability artifact.**
- **Homogeneous-procedural (bizSQL):** WIN on qwen (+8.2pp 3-seed from 0.88) AND granite (+42.5pp from 0.215). A
  small shared schema/dialect convention set transfers. **Larger lift at lower base** — the conventions the strong
  model already knew are exactly the headroom the weak model gains.

This closes the "only tested on one weak model" skeptic hole and strengthens, not weakens, the thesis.

## 3-seed scale-up flag

Per the pre-registered rule ("flag 3-seed scale-up if MBPP lifts on the second model"): **MBPP did NOT lift
(+0.00pp) → no MBPP scale-up.** bizSQL granite lifted hugely (+42.5pp) in the *expected* direction, replicating the
qwen 3-seed WIN — directionally unambiguous. The **single-seed (n=1) magnitude** for bizSQL granite is a capability
arm, NOT equal-rigor to the 3-seed qwen runs; if the article leans on the +42.5pp *number* (vs the *direction*), a
3-seed confirmation (seeds 43/44) is the honest follow-up. Direction + z≈9.5 make a thesis change safe now; the
magnitude is the only thing n=1 leaves soft.

## Artifacts (qwen runs untouched)

- `configs/{mbpp,bizsql}/local-pilot-granite-8b.yaml` — `_base_` qwen config, override only `model.target` + `workers:4`.
- `outputs/{mbpp,bizsql}_probe_granite_8b/probe_failures.json`
- `outputs/mbpp-train/deepseek-v4-pro/granite8b-s42/` (test Δ=+0.00)
- `outputs/bizsql-train/deepseek-v4-pro/granite8b-s42/` (test Δ=+42.5pp)

## Unresolved questions

- bizSQL granite +42.5pp is n=1 — magnitude (not direction) wants 3-seed (43/44) before being quoted as a point
  estimate in the article. Direction is safe.
- Gemma-3n renderer empty-content bug is logged here as the disqualifier; not separately filed upstream (out of scope).
