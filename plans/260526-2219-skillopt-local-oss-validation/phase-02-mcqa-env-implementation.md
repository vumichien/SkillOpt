---
phase: 2
title: "MCQA Env Implementation"
status: complete
priority: P1
effort: "4-6h"
dependencies: [1]
---

# Phase 2: MCQA Env Implementation

## Overview
Build a new dataset-agnostic multiple-choice QA environment (`skillopt/envs/mcqa/`) by cloning the SearchQA env and swapping the rollout prompt, evaluator (letter exact-match), and initial skill. Register it so `--config configs/mcqa/...` works.

## Key Insight (verified)
SearchQA is the simplest single-turn text env and its `reflect()` just calls generic `gradient.reflect.run_minibatch_reflect` (`envs/searchqa/adapter.py:106`). The trainer is env-agnostic; it only needs rollout rows with `{id, hard(0/1), soft(0-1), fail_reason, response}` (`envs/base.py:216-232`). So mcqa = SearchQA structure with: (a) prompt that presents labeled options, (b) evaluator that extracts a letter and compares to gold letter, (c) an initial MC-reasoning skill. Reuse dataloader pattern (`SplitDataLoader`) and `run_minibatch_reflect` unchanged.

## Requirements
- Functional: single-turn MC rollout — target sees skill (system) + question+labeled options (user), emits `<answer>X</answer>`; scored by exact letter match vs gold.
- Functional: result rows match the trainer contract (`id, hard, soft, predicted_answer, response, fail_reason, agent_ok, n_turns`).
- Functional: registered in `scripts/train.py` registry as `mcqa`; loads via `--config configs/mcqa/default.yaml`.
- Non-functional: dataset-agnostic (works for any `{id, question, choices[{label,text}], answers[letter]}`); ≤200 lines/file (modularize like SearchQA); reuse generic reflect (DRY).

## Architecture
Item schema (produced by Phase 3, consumed here):
```json
{"id": "...", "question": "...", "choices": [{"label":"A","text":"..."}, ...], "answers": ["C"]}
```
Files (clone from `skillopt/envs/searchqa/`):
- `mcqa/dataloader.py` — `McqaDataLoader(SplitDataLoader)`, same `_load_items` JSON/JSONL logic as SearchQA.
- `mcqa/rollout.py` — `process_one` + `run_batch` (copy SearchQA's, **drop `[DOC]` context truncation**). `_build_user`: render `Question:\n{q}\n\nOptions:\nA. ...\nB. ...` from `choices`. `_build_system`: skill section + format instruction. Single `chat_target` call (max_turns=1), `max_completion_tokens` small (e.g. 256 — MC needs only brief reasoning + letter). Keep exec-backend branch only if trivially copyable; else drop it (we use qwen_chat).
- `mcqa/evaluator.py` — `extract_letter(text)`: prefer `<answer>X</answer>`, else first standalone A–E near "answer", else first capital letter token; `evaluate(pred_text, gold_letters)` → `{em, predicted_answer, gold}`. `hard = int(em)`, `soft = em` (no partial credit — KISS).
- `mcqa/adapter.py` — `McqaAdapter(EnvAdapter)`: clone SearchQA adapter; `get_task_types()` → `["mcqa"]`; `reflect()` calls `run_minibatch_reflect` unchanged.
- `mcqa/prompts/rollout_system.md` — system prompt template with `{skill_section}` placeholder, instructing answer in `<answer>X</answer>`.
- `mcqa/skills/initial.md` — **the skill we train** (seed): minimal MC-reasoning rubric (read all options; eliminate clearly-wrong; watch negation/qualifier traps; pick best-supported; output the letter in `<answer>` tags). Keep short — let the optimizer grow it.
- `mcqa/__init__.py`.
- Register in `scripts/train.py:_register_builtins` (`from skillopt.envs.mcqa.adapter import McqaAdapter; _ENV_REGISTRY["mcqa"]=...`).

## Related Code Files
- Create: `skillopt/envs/mcqa/{__init__.py,dataloader.py,rollout.py,evaluator.py,adapter.py}`, `mcqa/prompts/rollout_system.md`, `mcqa/skills/initial.md`
- Modify: `scripts/train.py` (register `mcqa`)
- Read for context (clone source): `skillopt/envs/searchqa/{dataloader,rollout,evaluator,adapter}.py`, `skillopt/envs/searchqa/prompts/rollout_system.md`, `skillopt/envs/searchqa/skills/initial.md`, `skillopt/datasets/base.py` (SplitDataLoader API), `skillopt/gradient/reflect.py` (run_minibatch_reflect signature already used by SearchQA adapter)

## Implementation Steps
1. Read the SearchQA env files + `datasets/base.py` + how `run_minibatch_reflect` is called (already visible in searchqa/adapter.py) to lock the contract.
2. Create `mcqa/` package; port dataloader (rename class, same load logic).
3. Write `rollout.py`: option rendering, single-turn `chat_target`, save conversation, call evaluator, build result row (incl. `fail_reason` describing wrong-letter so the analyst gets signal).
4. Write `evaluator.py` (letter extraction + EM).
5. Write `adapter.py` (clone, swap dataloader + task types).
6. Write `prompts/rollout_system.md` + `skills/initial.md`.
7. Register `mcqa` in `train.py`.
8. Compile-check: `python -c "from skillopt.envs.mcqa.adapter import McqaAdapter"`; `python scripts/train.py --help`.
9. Unit-smoke the evaluator: feed sample responses (`<answer>C</answer>`, "The answer is B.", malformed) → assert correct letter + EM.

## Success Criteria
- [ ] `mcqa` importable + registered; `train.py --help` clean; no file >200 LOC.
- [ ] Evaluator extracts letters from tagged/untagged/malformed responses; EM correct vs gold.
- [ ] `reflect()` reuses `run_minibatch_reflect` (no bespoke gradient code).
- [ ] Rollout produces trainer-contract rows with a useful `fail_reason` on wrong answers.

## Risk Assessment
- **Letter-extraction brittleness** (model says "B) because…" or restates option text): make `extract_letter` robust (tag → "answer is X" → leading letter), and have the initial skill enforce the tag. Wrong extraction = false negatives → biased signal.
- **Over-cloning exec-backend complexity**: we only need qwen_chat; drop codex/exec branches to stay <200 LOC (YAGNI).
- **soft==hard means no gradient on near-misses**: acceptable for MC; the analyst still sees the chosen-vs-gold letter via `fail_reason`.

## Next Steps
Phase 3 produces data in this env's schema; Phase 4 config points `env.name: mcqa`.
