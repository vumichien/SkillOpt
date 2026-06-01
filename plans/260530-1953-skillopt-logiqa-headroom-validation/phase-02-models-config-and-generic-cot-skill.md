# Phase 02 — Models, LogiQA Config, Generic-CoT Skill (Arm 2)

## Context Links
- Config base: `configs/mcqa/local-pilot.yaml` (v3), `configs/mcqa/local-pilot-siqa.yaml`
- Init skills: `skillopt/envs/mcqa/skills/initial-weak.md` (arm 1), `initial.md`
- Backend: `skillopt/model/qwen_backend.py` (reads `TARGET_DEPLOYMENT`)

## Overview
- **Priority:** P0
- **Status:** pending
- Pull/verify the 3 new Ollama targets, add the LogiQA config, and author the fixed generic-CoT skill (arm 2).

## Key Insights
- Target is fully decoupled: set `TARGET_DEPLOYMENT` env (launcher honors it) — no per-model config needed.
  A single `local-pilot-logiqa.yaml` works for all 4 targets; only the env var changes.
- Arm 2 = a hand-written, **dataset-agnostic** CoT skill, used eval-only (no optimizer) so any arm3 gain
  is attributable to optimization, not "added CoT".
- All chosen targets fit 10 GB on GPU: qwen3.5:2b (~1.5-2 GB), qwen3.5:4b (~2.5-3 GB), gemma4:e4b (~3.5 GB),
  qwen2.5:7b-q4 (4.7 GB, already pulled).

## Requirements
- Functional: `ollama show <tag>` succeeds for all 4 targets; `configs/mcqa/local-pilot-logiqa.yaml` resolves;
  generic-CoT skill md exists.
- Non-functional: skill md concise (≤40 lines), no LogiQA-specific hints (must stay generic for fair arm 2).

## Architecture
- `configs/mcqa/local-pilot-logiqa.yaml`: `_base_: local-pilot.yaml`; override `env.split_dir: data/mcqa_logiqa_split`.
  Keep v3 hyperparams (train 100, bs 20, 2 epochs → 10 edits, lr 4 cosine, gate strict, eval_test true).
- New skill: `skillopt/envs/mcqa/skills/generic-cot.md` — generic "read question, restate, eliminate, reason
  step-by-step, output `<answer>X</answer>`" with NO task-specific heuristics.

## Related Code Files
- Create: `configs/mcqa/local-pilot-logiqa.yaml`, `skillopt/envs/mcqa/skills/generic-cot.md`
- Read for context: `local-pilot-siqa.yaml` (2-line override pattern), `initial-weak.md` (arm-1 format)

## Implementation Steps
1. `ollama pull qwen3.5:2b` / `qwen3.5:4b` / `gemma4:e4b` (adjust to exact tags from `ollama show`/library).
2. Record resolved tags + on-disk sizes in the plan's open-questions (for the article's repro section).
3. Write `local-pilot-logiqa.yaml` (override split_dir only).
4. Write `generic-cot.md` (arm 2) — generic CoT, `<answer>` format, ≤40 lines.
5. Sanity: 1-item smoke per target via `eval_skill_on_dataset.py --split val --workers 1` (errors=0 check).

## Todo List
- [ ] Pull + verify 3 model tags; note sizes
- [ ] Create LogiQA config
- [ ] Author generic-CoT skill (arm 2)
- [ ] 1-item smoke per target (Ollama reachable, no rollout errors)

## Success Criteria
- All 4 targets respond via Ollama `/v1` with errors=0 on a 1-item probe; config + skill files present.

## Risk Assessment
- Exact ollama tag mismatch (e.g. `qwen3.5:2b-instruct`) → resolve via `ollama show` before pulling broadly.
- gemma4:e4b chat template / thinking mode differences → keep `QWEN_CHAT_ENABLE_THINKING=false`; verify output parses.

## Security Considerations
- DeepSeek key stays in `.env.local-pilot` (gitignored). No secrets in configs.

## Next Steps
- Feeds Phase 03 (baselines use these targets + arm-1/arm-2 skills) and Phase 04 (loop uses the config).
