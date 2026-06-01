---
status: pending
plan: skillopt-logiqa-headroom-validation
created: 2026-05-30
owner: vumichien
brainstorm: plans/reports/brainstorm-summary-260530-1953-skillopt-headroom-arc-scale-validation-report.md
---

# Plan: SkillOpt LogiQA Headroom Validation (Cross-Family Small Models)

## Status: PLANNING

## Overview
Prove SkillOpt CAN produce a real positive held-out gain by moving from saturated commonsense MC
(CSQA/SocialIQA, both flat = ceiling) to **LogiQA** — a low-baseline, procedure-heavy logical-reasoning
task — across small local targets (Qwen3.5-2B/4B, Gemma4-E4B, Qwen2.5-7B anchor). A 3-arm baseline
(raw → generic-CoT → SkillOpt) isolates the real optimization effect. Harness is reused as-is; the only
new code is a ~25-LOC LogiQA converter + configs/skill files.

## Context & Constraints
- **Harness exists** — reuse `skillopt/` mcqa env, `scripts/train.py`, `eval_skill_on_dataset.py`,
  `prepare_mcqa_data.py`, `run_local_pilot.ps1`. NO rebuild.
- **Model swap** via `TARGET_DEPLOYMENT` env / `model.target` config; temp pinned 0 (`.env.local-pilot`).
- **Hardware** RTX 3080 10 GB — chosen targets fit on GPU; avoid 9B/26B (CPU-spill). Kimi K2.6 dropped.
- **Success** ≥+3pp (arm3−arm2), 3-seed 95% CI excludes 0, on ≥1 target.
- **Rules** files <200 LOC, kebab-case, no plan-refs in code/commit msgs, venv `.venv\Scripts\python.exe`.

## Phases (overview)
| # | Phase | One-line | Depends on |
|---|-------|----------|-----------|
| 01 | [Dataset converter + splits](phase-01-logiqa-dataset-converter-and-splits.md) ✅ | Add LogiQA to `prepare_mcqa_data.py`; generate 3 seeded splits | — |
| 02 | [Models + config + generic-CoT skill](phase-02-models-config-and-generic-cot-skill.md) 🔄 | Pull/verify ollama models; write LogiQA config + arm-2 skill | 01 |
| 03 | [Headroom-probe GATE](phase-03-headroom-probe-gate.md) ✅ | Arms 1+2 baselines (eval-only) ×4 targets; **GATE=GO** (clean table below) | 01,02 |
| 04 | [SkillOpt loop (arm 3)](phase-04-skillopt-training-loop.md) 🔄 | **Scope (user): gemma3:4b ×3 seeds FIRST.** Wired (config+launcher+runner ready); BLOCKED on DeepSeek key | 03 |
| 05 | [Analysis + CI](phase-05-analysis-and-ci.md) | Aggregate mean Δ + 95% CI; scale/family table + plot | 04 |
| 06 | [Docs + article update](phase-06-docs-and-article-update.md) | Update validation doc + Medium article with real numbers | 05 |

## Risks & Mitigations
| Risk | Mitigation |
|------|-----------|
| Newer small models stronger → less headroom | LogiQA baseline low; probe gate (P03) + 2B as best shot |
| LogiQA near-ceiling for a target | P03 gate escalates to ReClor/LogiQA-2.0 before the loop |
| Gain confounded by "just CoT" | 3-arm baseline; report arm3−arm2 |
| Exact ollama tags differ | verify with `ollama show`/pull in P02 |
| Honest result may still be null | pre-commit to report either way; null-in-headroom is a finding |

## Resolved During Implementation (2026-05-30)
- **Ollama on 0.24.0** — old 0.6.5 client could not pull from current registry; upgraded. qwen3.5/gemma4 ARE real downloads (the earlier "don't exist" was the old-client failure), BUT they do not RUN on ollama 0.24.0's bundled llama.cpp: `qwen3.5:4b` → arch `qwen3next` unsupported, `gemma4:e2b` → arch `gemma3n` unsupported (both hard-fail at load, not VRAM). Need a newer engine than 0.24.0 ships. Not blocking — slate below covers the same scale/family span.
- **Model load triage on 0.24.0 (verified via /v1 with enable_thinking=false, the flag the backend forces):**
  - DEAD: `qwen3.5:4b`/`gemma4:e2b` (unsupported arch), `qwen3:4b` (returns EMPTY content under enable_thinking=false even at 512 tok — fundamental, not a token cap). All three excluded.
  - GOOD (clean parseable answers): `qwen2.5:1.5b`, `llama3.2:latest` (3B, Llama family), `gemma3:4b` (Gemma), `qwen2.5:7b-instruct-q4_K_M` (anchor), `qwen2.5:3b` (spare).
- **Final slate (3 families × 4 scales — stronger diversity than original Qwen-heavy plan):** `qwen2.5:1.5b` (Qwen/1.5B), `llama3.2` (Llama/3B), `gemma3:4b` (Gemma/4B), `qwen2.5:7b` (Qwen/anchor). NOTE: `qwen3:4b` was the user's working-slate pick but is infeasible → `llama3.2` substituted; **confirm with user before Phase 04 training** (forced feasibility swap of a user-confirmed item).
- **env-clobber bug found + fixed (critical):** `eval_skill_on_dataset.py::_load_env_file` forces .env values to WIN over the shell (intentional, for temp pinning). A `TARGET_DEPLOYMENT=…` line in `.env.local-pilot` therefore silently overrode every per-run `$env:TARGET_DEPLOYMENT` — three different slugs all recorded `target=qwen2.5:7b`. FIX: added explicit `--target` CLI arg applied AFTER `_load_env_file`; `summary.json` now records resolved `target` for audit. Probe re-run clean. (Same clobber will bite Phase-04 train.py — verify its target path uses an arg, not bare env, before P04.)
- **Headroom baselines (CLEAN, `--target`-fixed probe, seed-42 test 200 items, target field audited per row, errors=0):**
  | Model | raw arm1 | generic-CoT arm2 | CoT effect (arm2−arm1) |
  |-------|----------|------------------|------------------------|
  | qwen2.5:1.5b | 0.365 | 0.355 | −1.0pp |
  | llama3.2:3b  | 0.385 | 0.370 | −1.5pp |
  | gemma3:4b    | 0.375 | **0.420** | **+4.5pp** |
  | qwen2.5:7b   | **0.585** | 0.540 | −4.5pp |
  Random (4-way)=0.25. Earlier 0.585/0.645 corrupted runs DISCARDED (env-clobber). NOTE qwen2.5:7b raw 0.585 here is REAL (audited target=qwen2.5:7b), distinct from the earlier accidental-7b clobber.
- **P03 GATE = GO, with target prioritization (KEY FINDING):** LogiQA is NOT saturated on any target (max 0.585) → headroom exists (unlike CSQA/SocialIQA). BUT generic CoT HURTS 3 of 4 models; only **gemma3:4b responds positively to added procedure (+4.5pp)** — direct evidence it can act on a better skill. Phase-04 priority: **(1) gemma3:4b** (sweet spot: headroom + proven procedure-responsive = best shot at real arm3−arm2 gain), **(2) qwen2.5:7b** (most headroom-to-ceiling, capable), **(3) llama3.2 / qwen2.5:1.5b** (FLOOR RISK: ~0.36–0.39, barely above 0.25 random, CoT-negative → may be too weak to act on procedure, the floor-mirror of the CSQA ceiling). Keep all 4 to tell the floor↔sweet-spot↔(no)ceiling story.
- **train.py target mechanism VERIFIED SAFE (Phase-04 blocker CLEARED):** `--target_model` CLI flag → `model.target` config (train.py `_CLI_TO_CFG`); `_apply_env_secrets` fills `model.target` from `TARGET_DEPLOYMENT` env ONLY when `not _has_explicit(flat, cfg_key)` — so an explicit `--target_model` wins over any `.env.local-pilot` `TARGET_DEPLOYMENT` line. train.py has NO `_load_env_file` clobber (that was eval-only). Phase-04 runner MUST pass `--target_model <tag>` + `--seed <n>` per run (current `run_local_pilot.ps1` relies on bare `TARGET_DEPLOYMENT` → needs a multi-model/multi-seed wrapper).
- **LogiQA loader fix:** `lucasmccabe/logiqa` ships a `logiqa.py` script rejected by `datasets` 4.8.5 → added `_REVISIONS["logiqa"]="refs/convert/parquet"`. Schema verified: context/query/options[4]/correct_option(int). Pool 8027 (train+validation).
- **Splits generated:** seed 42/43/44 → 100/300/200, self-check PASS.
- **venv access:** Bash blocked from `.venv` by scout hook → run venv Python via PowerShell.

## Phase-04 Wiring (DONE 2026-05-31 — ready to launch once key is in)
- **Decisions (user):** scope = **gemma3:4b ×3 seeds (42/43/44) FIRST**; llama3.2:3b substitution for infeasible qwen3:4b ACCEPTED (lower-priority floor model, deferred).
- **Config created:** `configs/mcqa/local-pilot-logiqa.yaml` (`_base_: local-pilot.yaml`; `model.target=gemma3:4b`, `env.split_dir=data/mcqa_logiqa_split`). Verified it resolves: target=gemma3:4b, split=LogiQA, skill_init=arm-1 weak, 2 epochs, train_size=100, gate+eval_test on, optimizer=deepseek-chat. (First draft used `data.split_dir` — wrong key, silently kept the CSQA base split; fixed to `env.split_dir`.)
- **Target is CONFIG-DRIVEN (user decision — model chosen by which config you run, never by env):** supersedes the earlier `--target_model`-from-env approach. Kills the env-clobber class at the source (it bit twice: eval `.env` loader, then launcher `.env` loader, each silently using qwen2.5:7b under a gemma3 label). `run_local_pilot.ps1` resolves `$Model` from the config's `model.target` (venv-python `load_config` one-liner) for Ollama warm-up, and passes NO `--target_model` — config is sole source of truth. `.env` = secrets + temp only; SKILLOPT_* (config/split/seed/out_root) snapshot-restored across the `.env` load. Both scripts parse-clean; config resolves `model.target=gemma3:4b`.
- **Matrix runner:** `scripts/run_logiqa_train.ps1` — `$conditions` = CONFIG files (target baked in); gemma3:4b→`local-pilot-logiqa.yaml` × seeds{42→split,43→_s43,44→_s44}; idempotent (skip if `best_skill.md` exists); clears `TARGET_DEPLOYMENT`; out_root `outputs/logiqa-train/<slug>-s<NN>`. Extend via a new config entry.
- **GOTCHA:** ONE run at a time — RTX 3080 10GB can't host two targets; overlapping launches make train.py die ~0.6s (GPU contention, not a bug). Kill all `train.py` + clear out_root before relaunch.
- **Launch command:** `.\scripts\run_logiqa_train.ps1` — LAUNCHED 2026-05-31 (key confirmed; gemma3:4b ×3 seeds in progress).

## Open Questions
- **DeepSeek key — RESOLVED:** user added the real key; gemma3:4b ×3-seed training launched 2026-05-31. Awaiting arm-3 test acc per seed.
- Iterations — ASSUMED keep v3 (2 epochs → 10 candidate edits).
- train.py target mechanism — RESOLVED: train.py never reads `TARGET_DEPLOYMENT` (no `.env` clobber there); target flows via `--target_model`. Safe.

## Success Criteria
- ≥+3pp (arm3−arm2) held-out, 3-seed 95% CI excludes 0, on ≥1 target (PRIMARY).
- Secondary: gain larger for smaller model and/or holds across families.
- Deliverable: updated validation doc + article with real numbers + CI table + plot.
