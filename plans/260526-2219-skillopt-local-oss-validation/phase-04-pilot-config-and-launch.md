---
phase: 4
title: "Pilot Config and Launch"
status: complete
priority: P1
effort: "2-3h"
dependencies: [1, 2, 3]
---

# Phase 4: Pilot Config and Launch

## Overview
Create the mcqa pilot config + env template + one-command launch scripts (PowerShell + bash) that start Ollama, wire DeepSeek optimizer + Qwen local target, and run `scripts/train.py`.

## Key Insight (verified)
`scripts/train.py` loads YAML with `_base_` inheritance + accepts `--cfg-options section.key=value` and legacy flat flags. Setting backends explicitly (don't rely on `--backend`) is required for the DeepSeek-optimizer + qwen-target combo. Ollama serves OpenAI-compatible API at `http://localhost:11434/v1`. Qwen target uses `QWEN_CHAT_BASE_URL` + `TARGET_DEPLOYMENT`. `reasoning_effort` MUST be empty (DeepSeek rejects it — Phase 1 path drops it, but keep config clean too).

## Requirements
- Functional: `configs/mcqa/local-pilot.yaml` inherits `configs/_base_/default.yaml`, sets mcqa env + pilot params.
- Functional: launch script pulls/warms the Ollama model, exports DeepSeek + Qwen env, runs training to `outputs/`, fails fast if DeepSeek key missing.
- Non-functional: secrets via gitignored `.env`; reproducible; Windows-first `.ps1` + portable `.sh`.

## Architecture
**`configs/mcqa/default.yaml`** (base mcqa config, inherits `_base_`): sets `env.name: mcqa`, `env.skill_init: skillopt/envs/mcqa/skills/initial.md`, `max_turns: 1`, sensible defaults.

**`configs/mcqa/local-pilot.yaml`** (inherits `default.yaml`):
```yaml
_base_: default.yaml
model:
  reasoning_effort: ""
  optimizer_backend: openai_chat
  target_backend: qwen_chat
  optimizer: deepseek-chat
  target: qwen2.5:7b-instruct-q4_K_M     # Ollama tag
train:
  train_size: 48
  batch_size: 16
  num_epochs: 2
  seed: 42
gradient:
  minibatch_size: 8
  merge_batch_size: 8
optimizer:
  learning_rate: 4
  min_learning_rate: 2
  lr_scheduler: cosine
  use_slow_update: false
  use_meta_skill: false
evaluation:
  use_gate: true
  eval_test: true
env:
  name: mcqa
  skill_init: skillopt/envs/mcqa/skills/initial.md
  split_mode: split_dir
  split_dir: data/mcqa_csqa_split
  max_turns: 1
  workers: 4
```
(Verify exact key paths against `_base_/default.yaml` + the Phase-2 adapter `__init__` kwargs during impl.)

**`.env.local-pilot.example`**:
```
export OPTIMIZER_OPENAI_BASE_URL=https://api.deepseek.com/v1
export OPTIMIZER_OPENAI_API_KEY=sk-...          # fill locally, never commit
export QWEN_CHAT_BASE_URL=http://localhost:11434/v1
export QWEN_CHAT_API_KEY=ollama
export TARGET_DEPLOYMENT=qwen2.5:7b-instruct-q4_K_M
export QWEN_CHAT_ENABLE_THINKING=false
```

**`scripts/run_local_pilot.ps1` / `.sh`**: (1) check Ollama up, `ollama pull` model if absent, warm via `/v1/models` ping; (2) verify `OPTIMIZER_OPENAI_API_KEY` set (fail fast); (3) `python scripts/train.py --config configs/mcqa/local-pilot.yaml`; (4) echo `out_root`.

## Related Code Files
- Create: `configs/mcqa/default.yaml`, `configs/mcqa/local-pilot.yaml`
- Create: `.env.local-pilot.example`, `scripts/run_local_pilot.ps1`, `scripts/run_local_pilot.sh`
- Read for context: `configs/searchqa/default.yaml` + `configs/_base_/default.yaml` (key paths), `scripts/train.py` (flags), `skillopt/envs/mcqa/adapter.py` (accepted cfg kwargs), `skillopt/envs/mcqa/skills/initial.md` (confirm path)
- Verify: `.gitignore` excludes `.env`.

## Implementation Steps
1. Read `_base_/default.yaml` + searchqa config + the Phase-2 adapter signature to copy exact keys.
2. Write `configs/mcqa/default.yaml` + `local-pilot.yaml`; double-check `reasoning_effort: ""`, `split_dir`, `skill_init`.
3. Write `.env.local-pilot.example`; ensure `.gitignore` covers `.env`.
4. Write `run_local_pilot.ps1` + `.sh`.
5. Dry-run config resolution: `python scripts/train.py --config configs/mcqa/local-pilot.yaml --help` and confirm config loads (backends, optimizer=deepseek-chat, target tag, env=mcqa, split_dir) before any rollout.

## Success Criteria
- [ ] `python scripts/train.py --config configs/mcqa/local-pilot.yaml` resolves config without error (env=mcqa, deepseek optimizer, qwen target, split_dir) before rollouts.
- [ ] Launch script pulls/warms Ollama model + fails fast if DeepSeek key missing.
- [ ] `.env` gitignored; example has no real secrets.
- [ ] `reasoning_effort` empty in resolved config.

## Risk Assessment
- **Wrong Ollama tag / VRAM**: pick a tag from `ollama list`; 7B Q4 ~5-6GB fits 3080. OOM → smaller quant / lower ctx.
- **Backend auto-defaults**: set `optimizer_backend`/`target_backend` explicitly.
- **Adapter kwarg mismatch**: config keys must match `McqaAdapter.__init__` params (train.py passes only accepted kwargs) — verify in step 1.

## Next Steps
Phase 5 runs this end-to-end on the 3080.
