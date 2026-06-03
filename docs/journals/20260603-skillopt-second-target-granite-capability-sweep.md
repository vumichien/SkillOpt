# SkillOpt — Second Local Target Capability Sweep (granite-code 8B)

**Date:** 2026-06-03 · **Phase:** 13 (extends the MBPP+bizSQL proof plan) · **Seeds:** 42 (n=1 capability arm)

## Goal

Settle a skeptic hole in the task-family thesis: every prior SkillOpt number was on ONE weak target
(`qwen2.5:7b-instruct-q4_K_M`). Is "MBPP flat / bizSQL wins" a fact about the *task family*, or just about
*qwen*? Test by swapping ONLY `model.target` and re-running both tasks identically.

## What happened

**The planned target died.** `gemma4:e4b` (and `e2b`) — the Gemma-3n "elastic" 4-bit builds — trip an Ollama
gemma4-renderer bug: for most prompts they emit tokens that decode to **empty content** (finish=length, len=0);
e4b also runs ~6 tok/s. Not a quant or Modelfile problem (identical template to a working gemma3:4b) — it's the
Gemma-3n arch + Ollama runtime. Researched alternatives, then learned the real lesson the hard way: **a model
that "looks stable" on paper isn't — smoke-test the exact harness.** qwen3:4b / qwen3.5:4b also failed (thinking
models burn the fixed 1024-token budget on reasoning that gets stripped → empty). Landed on IBM
`granite-code:8b-instruct-q4_K_M` (dense, q4_K_M): 6/6 clean, ~40 tok/s, 0 empties. User approved the pivot.

**Both verdicts replicated** (held-out n=200 test, single varied factor = target):

| Task | qwen base→Δ | granite base→Δ | Verdict |
|------|-------------|----------------|---------|
| MBPP | 0.65 → −3pp | 0.44 → **+0.0pp** | FLAT on both |
| bizSQL | 0.88 → +8.2pp (3-seed) | 0.215 → **+42.5pp** (z≈9.5) | WIN on both |

- MBPP granite: selection gate moved +5pp (the optimizer DID find the function-name/arity convention the probe
  flagged) but **didn't transfer** to held-out — heterogeneous-procedural, no shared procedure to carry. Same as qwen.
- bizSQL granite: selection gate climbed 0.23→0.70 and **fully transferred** (+42.5pp). The winning skill is ~6
  shared schema/dialect house rules (JOIN customers for region, ISO-text date ranges not `YEAR()`, quarter
  boundaries, exclude refunded/cancelled, qty*unit_price vs total_amount). The lift was **bigger at the lower
  base** — the conventions a strong model already knows are exactly the headroom a weak one gains.

## Decisions & lessons

- **Lever confirmed = task family, not the model.** Holds across a 21pp MBPP base gap and a far wider bizSQL gap.
- **Floor-override, surfaced not silent:** MBPP granite base 0.46 sat below the pre-registered 0.65 train floor,
  but the probe showed 20% naming-convention (skill-fixable) failures — so training it was the honest test. Flat
  held-out result vindicated the family read regardless of base.
- **n=1 honesty:** bizSQL granite +42.5pp is single-seed — direction trustworthy (z≈9.5), magnitude wants a
  3-seed confirm before being quoted as a point estimate. MBPP did NOT lift → no MBPP 3-seed scale-up.
- **Code-review caught a fabricated number:** I wrote the qwen MBPP base as 0.72 in the report + article; verified
  value is 0.65 (qwen summary.json + plan.md). Corrected across all 4 files (and the derived "28pp"→"21pp" gap).
  Cross-table audit catches what single-table reads miss.

## Artifacts

- Report: `plans/260601-2126-skillopt-mbpp-codegen-proof/reports/phase13-second-target-granite-results.md`
- Configs: `configs/{mbpp,bizsql}/local-pilot-granite-8b.yaml` (override only target + workers)
- Runs (gitignored): `outputs/{mbpp,bizsql}-train/deepseek-v4-pro/granite8b-s42/`
- Article (consolidated single final post): `docs/articles/medium-skillopt-when-prompt-training-works.md`
