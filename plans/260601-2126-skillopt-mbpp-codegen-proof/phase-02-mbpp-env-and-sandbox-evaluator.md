---
phase: 2
title: "MBPP Env and Sandbox Evaluator"
status: done
priority: P1
effort: "1-2d"
dependencies: [1]
---

# Phase 2: MBPP Env and Sandbox Evaluator

## Overview
Build a new `skillopt/envs/mbpp/` env (cloned from `envs/mcqa/`) whose rollout generates one Python
function per item (single-turn) and scores it pass@1 by running the item's `test_list` asserts in a
subprocess sandbox. This is the only substantive new code in the plan.

## Requirements
- Functional: register `mbpp` env; single-turn rollout; deterministic sandbox unit-test scorer; weak-init skill.
- Non-functional: each file < 200 LOC; sandbox = subprocess + timeout + temp cwd (no container); resume-aware
  batch runner (reuse mcqa's verbatim except the env name); reflect via the global analyst prompts (KISS).

## Architecture
Mirror the mcqa file set. The dataloader and batch_runner are near-verbatim clones; only the **evaluator**
and **rollout/prompts/skill** carry MBPP logic.

- `evaluator.py` (NEW logic — the critical piece):
  - `extract_code(text) -> str`: take the first ```python … ``` fenced block; else first ``` … ``` block;
    else the whole text. Strip prose. (This extraction robustness is itself something the skill will learn to
    make trivial — narrative gold for the article.)
  - `run_tests(code, test_list, test_setup_code, timeout=8) -> (passed: bool, detail: str, n_pass: int)`:
    build a script = `test_setup_code + "\n" + code + "\n" + "\n".join(test_list)`, write to a tempfile in a
    temp cwd, run `subprocess.run([sys.executable, "-I", tmp], capture_output, text, timeout)`. Borrow the
    tempfile/timeout/returncode pattern from `skillopt/envs/spreadsheetbench/executor.py` (NO multi-turn,
    NO xlsx). `passed = (returncode == 0)`. On AssertionError/Exception/timeout → passed False, detail =
    truncated stderr / "timeout-{t}s". (Optionally run asserts individually to count `n_pass` for the trace;
    pass@1 score only needs all-pass.)
  - `evaluate(prediction_text, item, timeout) -> {"em": 1.0|0.0, "passed", "n_pass", "predicted_code", "detail"}`.
- `dataloader.py`: `class MbppDataLoader(SplitDataLoader)` — identical to `McqaDataLoader` (reuse the same
  `_load_items` helper; `load_raw_items` returns the JSON array).
- `rollout.py` (clone of mcqa rollout.py, code-shaped):
  - `_build_system(skill)` via `load_prompt("rollout_system", env="mbpp")`.
  - `_build_user(item)` = `f"{item['prompt']}\n\nYour function must satisfy this example test:\n{item['example_assert']}"`.
  - `chat_target(..., max_completion_tokens=1024, stage="rollout", timeout=exec_timeout)` (code longer than a letter).
  - call `evaluate(response, item, timeout=sandbox_timeout)`; set `hard/soft/em`, `predicted_answer=""`(n/a),
    `fail_reason = detail`. Persist prompts + conversation like mcqa.
- `batch_runner.py`: clone mcqa's; change `task_type="mbpp"` and the `_stub_result` fields. Resume-aware logic unchanged.
- `adapter.py`: `class MbppAdapter(EnvAdapter)` — clone `McqaAdapter`; pass a new `sandbox_timeout` (default 8)
  through to `run_batch`→`process_one`. `get_task_types() -> ["mbpp"]`. Reflect path unchanged (uses
  `run_minibatch_reflect` + base `get_error/success_minibatch_prompt`, which fall back to the global
  `skillopt/prompts/analyst_error.md`/`analyst_success.md` — confirmed no per-env override needed for mcqa either).
- `prompts/rollout_system.md`: Python-programmer persona + output contract: "Return ONE ```python code block
  containing the complete function with the exact name implied by the example test. No prose, no explanation,
  no example usage." `{skill_section}` slot, same shape as mcqa.
- `skills/initial-weak.md`: minimal headroom-leaving stub: "Write a Python function that solves the problem.
  Put it in a ```python code block." (mirrors mcqa weak init philosophy).
- Register: add to `_register_builtins()` in `scripts/train.py` (try/except import block, same as the others):
  `from skillopt.envs.mbpp.adapter import MbppAdapter; _ENV_REGISTRY["mbpp"] = MbppAdapter`.

## Related Code Files
- Create: `skillopt/envs/mbpp/__init__.py`, `adapter.py`, `dataloader.py`, `evaluator.py`, `rollout.py`,
  `batch_runner.py`, `prompts/rollout_system.md`, `skills/initial-weak.md`.
- Modify: `scripts/train.py` (register `mbpp` in `_ENV_REGISTRY`).
- Read for context: `skillopt/envs/mcqa/*`, `skillopt/envs/spreadsheetbench/executor.py`,
  `skillopt/envs/base.py` (EnvAdapter, `get_*_minibatch_prompt`), `skillopt/prompts/analyst_error.md`.

## Implementation Steps
1. Clone the mcqa file set into `skillopt/envs/mbpp/`; rename classes (`Mbpp*`), set `task_type="mbpp"`.
2. Write `evaluator.py` sandbox (the only genuinely new module); unit-test it standalone (see Success).
3. Wire `rollout.py` to call the sandbox; bump `max_completion_tokens=1024`; thread `sandbox_timeout`.
4. Add `prompts/rollout_system.md` + `skills/initial-weak.md`.
5. Register the env in `scripts/train.py`.
6. Compile-check: `python -c "import skillopt.envs.mbpp.adapter"` under `.venv` with `PYTHONUTF8=1`.

## Success Criteria
- [ ] `evaluator.run_tests` returns True for every gold MBPP solution in `data/mbpp_split_s42` and False for an
      obviously-wrong stub — verified by a small standalone pytest (`tests/test_mbpp_evaluator.py`).
- [ ] `extract_code` handles: fenced ```python, bare ```, and no-fence raw code.
- [ ] `import skillopt.envs.mbpp.adapter` succeeds; `mbpp` resolves in `_ENV_REGISTRY`.
- [ ] A 2-item smoke rollout (weak skill) runs end-to-end and writes `results.jsonl` with `hard` scores.

## Risk Assessment
- **Sandbox safety**: 7B-generated code runs locally via subprocess + `-I` isolated + timeout + temp cwd; no
  container. Acceptable for local trusted-ish use; document the limitation. Do NOT run with network-bound or
  filesystem-destructive test setups (MBPP tests are pure-compute asserts).
- **Signature mismatch**: mitigated by `example_assert` in the prompt; if still high, allow the skill to learn it
  (don't hard-code name extraction).
- **Reflect prompt fit**: global analyst prompts are QA-generic. If pilot reflections are weak on code, add
  `skillopt/envs/mbpp/prompts/analyst_error.md` + `analyst_success.md` (code-specific) — deferred until proven needed (YAGNI).
