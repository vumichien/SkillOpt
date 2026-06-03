# Brainstorm → Planner: gemma4:e4b Capability-Sweep (MBPP + bizSQL second target)

**Date:** 2026-06-03 · **Status:** design approved by user, ready to plan
**Extends:** `plans/260601-2126-skillopt-mbpp-codegen-proof/` (Phase-12 combined article). This is a new
capability-sensitivity arm — slot as a new phase (e.g. Phase 13) feeding the Exp-A/Exp-B cross-family section.

## Problem statement

MBPP went **flat/overfit** on the only target tested (`qwen2.5:7b-instruct-q4_K_M`): test 0.65→0.62 (−3pp),
dev +9 but didn't transfer (heterogeneous-procedural). bizSQL **won** on the same target (3-seed mean +8.2pp).
User hypothesis: MBPP flat may be a **model-capability artifact** (qwen2.5:7b-q4 too weak), not a task-family
fact. Test by swapping ONLY the target to a **stronger local** model, holding everything else constant.
This also closes a real skeptic hole: MBPP/bizSQL were each tested on only ONE target, unlike the MC matrix
(2 targets × 3 datasets). seed 42 only (save time).

## Scout findings (load-bearing facts)

- **Target swap = config-only.** `model.target` is read from YAML and passed straight to Ollama's
  OpenAI-compatible endpoint via the `qwen_chat` backend (a misnomer — it's just "ollama chat", model tag is a
  string). `skillopt/model/qwen_backend.py`. No code change to run a different Ollama model.
- **Probes already support `--target` override** → zero edits to probe a new model:
  `scripts/probe_mbpp_headroom.py` (read), `scripts/probe_bizsql_headroom.py` (mirror). Probe runs weak-init
  skill over **train** split (test stays locked), reports baseline pass@1 + procedural-share, writes
  `probe_failures.json`. Probe hardcodes `target_backend=qwen_chat` → fine for any local Ollama tag.
- **Run scripts** `scripts/run_mbpp_pilot.ps1` / `run_bizsql_pilot.ps1`: derive target from config, run a
  sandbox/SQL smoke, ensure Ollama up + `ollama pull $Model`, start GPU sampler, run `scripts/train.py`.
  Resume-aware via out_root. Orchestration env: `SKILLOPT_CONFIG`, `SKILLOPT_OUT_ROOT`, `SKILLOPT_SPLIT_DIR`,
  `SKILLOPT_SEED`. Secrets in `.env.local-pilot` (`OPTIMIZER_OPENAI_API_KEY` = DeepSeek, `QWEN_CHAT_*`,
  `TARGET_DEPLOYMENT`).
- **Existing results (qwen2.5:7b-q4, deepseek-v4-pro optimizer, seed 42):** MBPP base 0.65 / trained 0.62
  (gate FAIL). bizSQL base 0.88 / trained 0.985 (+10.5pp, gate PASS); strong-model ceiling ~1.00.
- **HARDWARE = RTX 3080, 10 GB VRAM total** (`nvidia-smi`: 10240 MiB; ~7.7 GB free w/ desktop). Decisive below.
- **Existing configs are identical except the `env` block** (controlled-variable story). New configs MUST keep
  hyperparams identical and override ONLY `model.target`.

## VRAM feasibility (unsloth gemma-4 reference vs 10 GB)

| Variant | 4-bit VRAM | Fits 10 GB | Decision |
|---|---|---|---|
| **E4B** | **5.5–6 GB** | ✅ (~3–4 GB left for KV/context) | **TRAIN TARGET** |
| E2B (already pulled, ~7.2 GB = Q8) | 4 GB @ 4-bit | ✅ | optional free anchor (user chose "both tracks", e2b not required) |
| 26B-A4B | 16–18 GB | ❌ overflow ~7 GB | **dropped** (MoE: all experts in mem; CPU offload → ~1–3 tok/s → days; 2-bit lobotomizes) |
| 31B | 17–20 GB | ❌ | dropped |

GGUF repo: `unsloth/gemma-4-E4B-it-GGUF`. **Must run the 4-bit** (Q8 e4b = 9–12 GB → overflows).

## Approved design — probe-gated local capability sweep

Hold constant: optimizer `deepseek-v4-pro`, weak-init skill (`initial-weak.md`), ALL hyperparams (epochs 2,
batch 20, minibatch 8, lr 4→2 cosine, gate on, no slow-update/meta-skill), same `_s42` splits, temp 0, n=200
held-out test. **Change ONLY `model.target` → `gemma4:e4b` (4-bit).**

**Stage 1 — Headroom probe (cheap, no training):** both tracks, train split, `--target` = the e4b Ollama tag.
**Stage 2 — Pre-registered gate (decide before GPU):**
- **MBPP:** train iff `0.65 ≤ base ≤ ~0.85` (real headroom). `base ≥ ~0.90` → record "no headroom (ceiling)",
  skip train.
- **bizSQL:** ⚠️ likely ceilings (qwen already 0.88, ceiling ~1.00). `base ≥ ~0.93` → record "e4b already
  near-ceiling → stronger model already knows the conventions (CONSISTENT with homogeneous-procedural, NOT a
  contradiction), no SkillOpt room", skip train. Train iff `base < ~0.90`.

**Stage 3 — Train seed-42 only**, gated tracks only. New configs inherit qwen config, override only target. New
out_root so qwen runs stay intact. Eval same `_s42` test (n=200).
**Stage 4 — Interpret (user: "decide after numbers"):** e4b Δ vs qwen Δ = a **single-seed (n=1) capability
arm**, explicitly NOT equal-rigor to the 3-seed qwen runs. If MBPP lifts on e4b → **scale to 3 seeds before any
thesis pivot** (thesis = "task family is the lever; model strength was never the lever").

## Concrete implementation map (for planner)

**Create:**
- `configs/mbpp/local-pilot-gemma-e4b.yaml` → `_base_: local-pilot.yaml`, override only `model.target: <e4b tag>`
  (consider `model.target_backend: qwen_chat` unchanged). Optionally drop `env.workers` to 4 (see risks).
- `configs/bizsql/local-pilot-gemma-e4b.yaml` → same pattern over `bizsql/local-pilot.yaml`.

**Probe commands** (after `ollama pull` of e4b; `.env.local-pilot` auto-loaded):
```
.venv\Scripts\python.exe scripts\probe_mbpp_headroom.py   --split-dir data/mbpp_split_s42   --split train --target <e4b-tag> --out-dir outputs/mbpp_probe_gemma_e4b
.venv\Scripts\python.exe scripts\probe_bizsql_headroom.py --split-dir data/bizsql_split_s42 --split train --target <e4b-tag> --out-dir outputs/bizsql_probe_gemma_e4b
```

**Train commands** (gated tracks only), via existing pilots with orchestration env:
```
$env:SKILLOPT_CONFIG="configs/mbpp/local-pilot-gemma-e4b.yaml";   $env:SKILLOPT_OUT_ROOT="outputs/mbpp-train/deepseek-v4-pro/gemma-e4b-s42";   $env:SKILLOPT_SEED="42"; scripts\run_mbpp_pilot.ps1
$env:SKILLOPT_CONFIG="configs/bizsql/local-pilot-gemma-e4b.yaml"; $env:SKILLOPT_OUT_ROOT="outputs/bizsql-train/deepseek-v4-pro/gemma-e4b-s42"; $env:SKILLOPT_SEED="42"; scripts\run_bizsql_pilot.ps1
```
(out_root segment `gemma-e4b-s42` mirrors existing `qwen7b-s42` → qwen artifacts untouched.)

## Risks & mitigations

- **e4b OOM with workers:8** (~6 GB weights + 8× KV cache on 10 GB). → Stage-1 probe flushes it first; if it
  OOMs/queues, set `env.workers: 4` in the gemma configs. Watch `gpu.csv`.
- **e4b Ollama tag must resolve** for `ollama pull $Model`. HF-GGUF tag form
  `hf.co/unsloth/gemma-4-E4B-it-GGUF:<quant>`. **Verify the exact 4-bit quant tag exists & pulls BEFORE the
  run** (the run script will fail fast if not). Pin the resolved tag string in both configs.
- **bizSQL ceiling misread.** Pre-register the interpretation (above) so a flat bizSQL ≠ "win was fragile".
- **Quant mismatch** (e2b-Q8 vs e4b-Q4) is second-order for a param-count sweep — do NOT fuss (YAGNI).
- **Optimizer/target both DeepSeek-family?** No — target is local gemma; optimizer is deepseek-v4-pro. Clean.

## Success criteria

- [ ] Probe baseline pass@1 + procedural-share recorded for e4b on MBPP and bizSQL (real numbers).
- [ ] Gate decision logged per track (train / skip-ceiling) with the measured base vs threshold.
- [ ] For gated tracks: seed-42 train completes, held-out n=200 Δ + binomial SE reported; qwen runs intact.
- [ ] Result framed as single-seed capability arm; 3-seed scale-up flagged as conditional follow-up.
- [ ] Feeds Phase-12 article cross-family section as the "second local target" robustness datapoint.

## Article integration

Adds the second target for code/SQL families → matches MC rigor. Outcomes: MBPP flat on e4b ⇒ thesis
bulletproof; MBPP lifts ⇒ honest pivot ("capability is a secondary lever for heterogeneous tasks", n=1 → scale
3 seeds first); bizSQL still-wins ⇒ model-robust; bizSQL ceilings ⇒ "stronger model already knows the
conventions" (consistent). All four are publishable, honest reads.

## Unresolved questions

1. Exact e4b 4-bit Ollama tag (Q4_K_M vs unsloth UD-Q4_K_XL) — confirm pull works on the box before Stage 3.
2. Include already-pulled `gemma4:e2b` as a free 3rd probe anchor? User chose "e4b, both tracks"; e2b optional —
   decide if the article wants a 3-point curve.
3. If MBPP lifts on e4b: scale to 3 seeds now or defer? (User: "decide after numbers".)
4. `workers` final value for e4b — set after Stage-1 probe reveals VRAM behavior.
