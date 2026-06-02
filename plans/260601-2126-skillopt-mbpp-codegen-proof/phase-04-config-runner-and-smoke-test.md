---
phase: 4
title: "Config Runner and Smoke Test"
status: done
priority: P1
effort: "2-3h"
dependencies: [2]
---

# Phase 4: Config Runner and Smoke Test

## Overview
Wire the mbpp env into a runnable training config + PowerShell runner that mirror the mcqa pilot, with
endpoint smoke tests before any GPU spend. Hyperparameters are copied verbatim from `configs/mcqa/local-pilot.yaml`.

## Requirements
- Functional: a `configs/mbpp/local-pilot.yaml` that trains mbpp on seed-42 data; a resume-aware runner;
  endpoint + sandbox smoke tests.
- Non-functional: ONLY env + data differ from the MC v3 config — every optimizer/gradient/train knob identical.

## Architecture
- `configs/mbpp/local-pilot.yaml` (`_base_: ../_base_/default.yaml`), blocks copied from mcqa local-pilot:
  - `model`: `optimizer_backend: openai_chat`, `target_backend: qwen_chat`, `optimizer: deepseek-v4-pro`,
    `target: qwen2.5:7b-instruct-q4_K_M`, `optimizer_openai_base_url: https://api.deepseek.com/v1`,
    `optimizer_openai_api_key_env: OPTIMIZER_OPENAI_API_KEY`.
  - `train`: `train_size: 100`, `batch_size: 20`, `num_epochs: 2`, `seed: 42`.
  - `gradient`: `minibatch_size: 8`, `merge_batch_size: 8`.
  - `optimizer`: `learning_rate: 4`, `min_learning_rate: 2`, `lr_scheduler: cosine`, `use_slow_update: false`,
    `use_meta_skill: false`.
  - `evaluation`: `use_gate: true`, `eval_test: true`.
  - `env`: `name: mbpp`, `skill_init: skillopt/envs/mbpp/skills/initial-weak.md`, `split_mode: split_dir`,
    `split_dir: data/mbpp_split_s42`, `max_turns: 1`, `workers: 8`, plus the new `sandbox_timeout: 8`
    (and `exec_timeout` for the target call, e.g. 120). Confirm the adapter reads `sandbox_timeout` from cfg.
- `scripts/run_mbpp_pilot.ps1`: clone `scripts/run_local_pilot.ps1`; change config default to
  `configs/mbpp/local-pilot.yaml`, out_root default to `outputs/mbpp_local_pilot`. Keep the env-loading,
  optimizer-key check, Ollama warm-up, GPU sampler, and `SKILLOPT_CONFIG/SPLIT_DIR/SEED/OUT_ROOT` overrides
  verbatim (these already drive a multi-seed matrix).
- Smoke: reuse `scripts/smoke_test_optimizer.py` (DeepSeek endpoint) + a tiny sandbox smoke (run one gold MBPP
  solution through `evaluator.run_tests`). Optionally fold into the runner's pre-flight like `run_optimizer_pilot.ps1`.

## Related Code Files
- Create: `configs/mbpp/local-pilot.yaml`, `scripts/run_mbpp_pilot.ps1`.
- Read for context: `configs/mcqa/local-pilot.yaml`, `configs/_base_/default.yaml`, `scripts/run_local_pilot.ps1`,
  `scripts/run_optimizer_pilot.ps1`, `scripts/smoke_test_optimizer.py`.
- Verify: `skillopt/config.py` flattening passes `sandbox_timeout` through to the adapter kwargs.

## Implementation Steps
1. Write `configs/mbpp/local-pilot.yaml` (copy mcqa, swap env block + add `sandbox_timeout`).
2. Confirm `MbppAdapter.__init__` accepts/uses `sandbox_timeout` (added in Phase 2); if the config→adapter
   kwarg mapping is allowlisted in `skillopt/config.py`/`train.py`, add `sandbox_timeout` there.
3. Clone `run_mbpp_pilot.ps1`; set mbpp defaults; keep smoke + GPU sampler.
4. Dry-run the smoke path only (no full train): endpoint OK + one gold solution passes the sandbox.

## Success Criteria
- [ ] `run_mbpp_pilot.ps1` resolves target=`qwen2.5:7b-instruct-q4_K_M`, optimizer=`deepseek-v4-pro` from the config.
- [ ] DeepSeek endpoint smoke prints OK; sandbox smoke passes a gold solution.
- [ ] `diff` of mbpp vs mcqa config shows ONLY the `env` block + `sandbox_timeout` changed (hyperparam parity).

## Risk Assessment
- **Unmapped config key**: if `sandbox_timeout` isn't threaded into the adapter, the sandbox silently uses the
  default 8s — acceptable, but verify the mapping so the config is honest.
- **Console encoding**: always `PYTHONUTF8=1` (runner sets it) to avoid cp932 errors on this machine.
