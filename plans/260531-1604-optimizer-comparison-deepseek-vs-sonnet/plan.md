# Optimizer Comparison: DeepSeek-V4-Pro vs Claude-Sonnet-4-6

**Question:** Does the *optimizer* model (the LLM that rewrites the skill) change SkillOpt's
held-out results? Same target, same data, same weak init — only the optimizer differs.

**Status:** Configs + code + runner PREPARED. Nothing has been run. Execute in a fresh session.

---

## Decisions (locked)

| Arm | Optimizer model | Endpoint (direct) | Key env var |
|-----|-----------------|-------------------|-------------|
| DeepSeek | `deepseek-v4-pro` | `https://api.deepseek.com/v1` | `OPTIMIZER_OPENAI_API_KEY` |
| Sonnet | `claude-sonnet-4-6` | `https://api.anthropic.com/v1` (OpenAI-compat) | `OPTIMIZER_CLAUDE_API_KEY` |

- No OpenRouter. Direct DeepSeek + Anthropic endpoints only.
- `deepseek-v4-pro` = the strong V4 tier (the deprecated `deepseek-chat` alias = weak V4-Flash;
  to reproduce the *old* article numbers, set `optimizer: deepseek-chat` in `local-pilot.yaml`).
- Target is config-driven (local Ollama): `qwen2.5:7b-instruct-q4_K_M` for CSQA/SIQA, `gemma3:4b` for LogiQA.
- Scope: **1-seed pilot first** (seed 42, 6 runs). Scale to 3 seeds (43/44) only after reviewing pilot.
- Run **step by step**: DeepSeek arm first → write results + insight in article → then Sonnet arm.

---

## What was prepared

**Code (so a config can pick which env var holds the optimizer key):**
- `skillopt/config.py` — map `model.optimizer_openai_api_key_env`.
- `scripts/train.py` — `--optimizer_openai_api_key_env` arg + map.
- `skillopt/engine/trainer.py` — resolve optimizer key from the named env var (default `OPTIMIZER_OPENAI_API_KEY`).
- `configs/_base_/default.yaml` — documents the new key.

**Configs:**
- `configs/mcqa/local-pilot.yaml` — DeepSeek arm: `deepseek-v4-pro` (CSQA; base for SIQA/LogiQA).
- `configs/mcqa/local-pilot-siqa.yaml`, `local-pilot-logiqa.yaml` — DeepSeek arm (inherit optimizer).
- `configs/mcqa/local-pilot-sonnet.yaml`, `local-pilot-siqa-sonnet.yaml`, `local-pilot-logiqa-sonnet.yaml`
  — Sonnet arm overlays (swap optimizer/base_url/key-env only).

**Scripts:**
- `scripts/run_optimizer_pilot.ps1` — 6-run pilot (3 datasets x 2 optimizers, seed 42), namespaced
  outputs, smoke-tests both endpoints before any GPU spend, idempotent.
- `scripts/run_local_pilot.ps1` — key check now accepts either arm's key; logs the resolved optimizer.

---

## Prerequisites (before running)

1. `.env.local-pilot` contains: `OPTIMIZER_OPENAI_API_KEY` (DeepSeek), `OPTIMIZER_CLAUDE_API_KEY`
   (Anthropic), `OPTIMIZER_OPENAI_BASE_URL`, `QWEN_CHAT_BASE_URL`, etc. (Do not commit it.)
2. Ollama running with both target models pulled: `ollama pull qwen2.5:7b-instruct-q4_K_M` and `ollama pull gemma3:4b`.
3. GPU free (RTX 3080, 10 GB — one Ollama target at a time; runs are sequential).

---

## Step-by-step

### Step 0 — Smoke-test endpoints (no GPU)
```powershell
.\scripts\run_optimizer_pilot.ps1   # aborts at the smoke stage if either endpoint/model is wrong
```
If the smoke prints `OK deepseek-v4-pro` and `OK claude-sonnet-4-6`, it continues into the runs.
(If a model id is rejected, fix it in the configs — e.g. a dated Anthropic id — and re-run.)

### Step 1 — DeepSeek arm first (3 datasets, seed 42)
Run only the DeepSeek arm to get results before touching Sonnet:
```powershell
$env:PYTHONUTF8="1"
foreach ($r in @(
  @{cfg="configs/mcqa/local-pilot.yaml";        split="data/mcqa_csqa_split_v2"; out="outputs/csqa-train/deepseek-v4-pro/qwen7b-s42"},
  @{cfg="configs/mcqa/local-pilot-siqa.yaml";   split="data/mcqa_siqa_split";    out="outputs/siqa-train/deepseek-v4-pro/qwen7b-s42"},
  @{cfg="configs/mcqa/local-pilot-logiqa.yaml"; split="data/mcqa_logiqa_split";  out="outputs/logiqa-train/deepseek-v4-pro/gemma3-4b-s42"}
)) {
  $env:SKILLOPT_CONFIG=$r.cfg; $env:SKILLOPT_SPLIT_DIR=$r.split; $env:SKILLOPT_SEED="42"; $env:SKILLOPT_OUT_ROOT=$r.out
  .\scripts\run_local_pilot.ps1
}
```

### Step 2 — Read DeepSeek results
Per run dir (`outputs/<ds>-train/deepseek-v4-pro/<tslug>-s42/`):
- `test_eval_baseline/summary.json` → `overall.hard_acc` = arm-1 (weak init, no optimization).
- `test_eval/summary.json` → `overall.hard_acc` = arm-3 (optimized skill).
- `history.json` → count steps with `action == "accept"` (0 accepts ⇒ arm-3 == arm-1).
- Real effect for this arm = arm-3 − arm-1 (held-out test accuracy).

### Step 3 — Write DeepSeek results + insight into the article
Update `docs/articles/medium-skillopt-local-oss-csqa.md` with the 3 DeepSeek-V4-Pro numbers and
the insight (accepts? did a stronger optimizer change the FLAT story?).

### Step 4 — Sonnet arm (same 3 datasets, seed 42)
```powershell
$env:PYTHONUTF8="1"
foreach ($r in @(
  @{cfg="configs/mcqa/local-pilot-sonnet.yaml";        split="data/mcqa_csqa_split_v2"; out="outputs/csqa-train/sonnet-4-6/qwen7b-s42"},
  @{cfg="configs/mcqa/local-pilot-siqa-sonnet.yaml";   split="data/mcqa_siqa_split";    out="outputs/siqa-train/sonnet-4-6/qwen7b-s42"},
  @{cfg="configs/mcqa/local-pilot-logiqa-sonnet.yaml"; split="data/mcqa_logiqa_split";  out="outputs/logiqa-train/sonnet-4-6/gemma3-4b-s42"}
)) {
  $env:SKILLOPT_CONFIG=$r.cfg; $env:SKILLOPT_SPLIT_DIR=$r.split; $env:SKILLOPT_SEED="42"; $env:SKILLOPT_OUT_ROOT=$r.out
  .\scripts\run_local_pilot.ps1
}
```
(Or just run `.\scripts\run_optimizer_pilot.ps1` once to do all 6 in order; it skips finished runs.)

### Step 5 — Compare + finalize article
Side-by-side per dataset: arm-3−arm-1 for DeepSeek vs Sonnet, plus accepts count. Insight =
does the optimizer model move the needle, or is the ceiling set by the target/task (as the
prior FLAT validations argued)?

---

## Output dir map

```
outputs/<dataset>-train/<optimizer>/<target>-s42/
  dataset   = csqa | siqa | logiqa
  optimizer = deepseek-v4-pro | sonnet-4-6
  target    = qwen7b (csqa,siqa) | gemma3-4b (logiqa)
```

## Scaling to 3 seeds (after pilot)
Repeat Steps 1/4 with seed 43 (`data/mcqa_*_split_s43`) and 44 (`data/mcqa_*_split_s44`) into
`...-s43` / `...-s44` dirs. CSQA has no s43/s44 split yet — generate via `scripts/prepare_mcqa_data.py`
or reuse seed-42 only for CSQA.

## Notes / risks
- Anthropic OpenAI-compat endpoint: if `claude-sonnet-4-6` is rejected, try a dated id; the smoke
  test catches this before GPU spend.
- Always set `PYTHONUTF8=1` when loading configs on this machine (cp932 console else errors on any
  non-ASCII byte). `run_local_pilot.ps1` already sets it internally.
- One target on the GPU at a time; keep runs sequential (do not launch overlapping `train.py`).

## Open questions
- DeepSeek model: using `deepseek-v4-pro` (the strong tier you originally asked for). If you instead
  want to reproduce the exact old article numbers, switch `local-pilot.yaml` optimizer to `deepseek-chat`.
- 3-seed scale-up for CSQA needs s43/s44 splits generated (only seed-42 exists today).
