---
phase: 2
title: "Config, Launcher Override, Training Runs (3 seeds)"
status: done
priority: P1
effort: "2h (mostly GPU wall time)"
dependencies: [1]
---

# Phase 2: Config, Launcher Override, Training Runs

## Overview
Add a SocialIQA training config, make the launcher accept a config override, then run the
SkillOpt fresh-train loop for seeds 42/43/44 and collect each run's `summary.json`.

## Requirements
- Functional: one `train.py` run per seed produces `best_skill.md` + `summary.json` with `baseline_test_hard` and `test_hard`.
- Non-functional: reuse v3 hyperparams exactly (only the split dir changes per seed). No `skillopt/` core edits.

## Architecture
`configs/mcqa/local-pilot-siqa.yaml` extends `local-pilot.yaml`, overriding only `env.split_dir`.
Per-seed split dirs differ, so either (a) one config + 3 split dirs selected via env/CLI, or
(b) point the config at seed-42 dir and pass `--split_dir`/`--config` per run. Simplest: keep one
base SocialIQA config (seed-42 dir) and override the split dir per seed via the launcher.

Launcher currently hardcodes `--config configs/mcqa/local-pilot.yaml` at `run_local_pilot.ps1:75`.
Add a `$env:SKILLOPT_CONFIG` override (mirrors the existing `$env:SKILLOPT_OUT_ROOT` pattern at line 48).

**RESOLVED:** `train.py` accepts `--config`, `--split_dir`, `--seed`, `--out_root` (verified
`scripts/train.py:137,204,242,255`). → **one** SocialIQA config + per-seed `--split_dir` override.
No per-seed config files needed. Add a `$env:SKILLOPT_SPLIT_DIR` thread to the launcher too, or
call `train.py` directly for seeds 43/44.

train.py reports both baseline (weak init on test) and trained (best skill on test) because
`evaluation.eval_test: true` is inherited from `local-pilot.yaml`.

## Related Code Files
- Create: `configs/mcqa/local-pilot-siqa.yaml`
  ```yaml
  _base_: local-pilot.yaml
  env:
    split_dir: data/mcqa_siqa_split   # seed-42 default; override per seed
  ```
- Modify: `scripts/run_local_pilot.ps1` (line ~75)
  - Add near line 48: `$Config = if ($env:SKILLOPT_CONFIG) { $env:SKILLOPT_CONFIG } else { "configs/mcqa/local-pilot.yaml" }`
  - Change line 75 invocation to: `& $Py scripts/train.py --config $Config --out_root $OutRoot`
  - (If train.py accepts `--split_dir` override, optionally also thread `$env:SKILLOPT_SPLIT_DIR`; otherwise create 2 extra tiny configs for s43/s44.)

## Implementation Steps
1. Write `configs/mcqa/local-pilot-siqa.yaml`.
2. Patch `run_local_pilot.ps1` for `$env:SKILLOPT_CONFIG` (verify `train.py` already accepts `--config`/`--out_root` — it does per README).
3. Per-seed mechanism (RESOLVED): one config + vary `--split_dir` per seed (CLI flag confirmed). Optionally thread `$env:SKILLOPT_SPLIT_DIR` through the launcher; else call `train.py` directly for s43/s44.
4. Ensure Ollama up + model warm (launcher already checks). Run seed 42:
   ```powershell
   $env:SKILLOPT_CONFIG = "configs/mcqa/local-pilot-siqa.yaml"
   $env:SKILLOPT_OUT_ROOT = "outputs/mcqa_siqa_s42"
   .\scripts\run_local_pilot.ps1
   ```
5. Inspect `outputs/mcqa_siqa_s42/summary.json` (`baseline_test_hard`, `test_hard`, accepts, wall time). Sanity-gate before spending GPU on 43/44: did the loop run end-to-end and gate fire at all?
6. Run seeds 43 and 44 into `outputs/mcqa_siqa_s43` / `_s44` (swap split dir + out root).

## Success Criteria
- [ ] `local-pilot-siqa.yaml` loads (PYTHONUTF8 guard already in launcher).
- [ ] Launcher honors `$env:SKILLOPT_CONFIG`; default path unchanged when unset (regression).
- [ ] 3 runs each produce `best_skill.md` + `summary.json` with baseline_test + test fields.
- [ ] GPU sampler wrote `gpu.csv` per run (for article duty-cycle stat, optional).

## Risk Assessment
- 300-val gate ≈ 3× slower than v3 → ~25-35 min/run; acceptable. Resume-aware (re-run continues) if interrupted.
- `--split_dir` overrides the config's `env.split_dir` — double-check precedence on run 1 (out_root contents reference the right split) to avoid a wasted run pointed at the wrong split.
- DeepSeek rate limits / key → launcher fails fast (line 26). Ensure `.env.local-pilot` present.
- Weak-init SocialIQA baseline may differ from CSQA — that's expected; record it, don't tune to it.
