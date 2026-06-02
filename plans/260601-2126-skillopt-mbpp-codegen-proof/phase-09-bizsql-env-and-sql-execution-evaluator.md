---
phase: 9
title: "BizSQL Env and SQL Execution Evaluator"
status: done
priority: P1
effort: "1-2d"
dependencies: [8]
---

# Phase 9: BizSQL Env, SQL Execution Evaluator, Config and Runner

## Overview
Build `skillopt/envs/bizsql/` (cloned from `envs/mcqa/`): single-turn rollout that generates one SQL query per
item and scores it by **execution accuracy** (run on the seeded SQLite DB, compare result set to `gold_result`).
Add the config (IDENTICAL hyperparams to MC v3 / MBPP) + a resume-aware runner. The execution evaluator is the
only substantive new code; everything else clones mcqa.

## Requirements
- Functional: register `bizsql` env; single-turn rollout with schema DDL in the prompt; deterministic SQL
  execution scorer (read-only, SELECT-only, timeout, order-insensitive result compare); weak-init skill;
  `configs/bizsql/local-pilot.yaml`; `run_bizsql_pilot.ps1`; endpoint + DB smoke.
- Non-functional: each file < 200 LOC; ONLY env + data differ from the MC v3 config (every optimizer/gradient/
  train knob identical); resume-aware batch runner reused verbatim except env name; reflect via global analyst
  prompts (KISS, YAGNI override only if Phase-11 reflections are weak on SQL).

## Architecture
Mirror the mcqa file set. Dataloader/batch_runner/adapter are near-verbatim clones; **evaluator** and
**rollout/prompts/skill** carry SQL logic.

- `evaluator.py` (NEW logic — the critical piece):
  - `extract_sql(text) -> str`: first ```sql … ``` fenced block; else first ``` … ``` block; else strip a
    leading "SQL:"/prose and take the first `SELECT … ;`/statement. (Extraction robustness is itself something
    the skill learns to make trivial — narrative gold for the article.)
  - `run_sql(sql, db_path, timeout=5) -> (ok: bool, rows: list|None, detail: str)`: **safety-first** —
    reject anything that is not a single `SELECT` (regex + reject `;`-multiple-stmts, `INSERT/UPDATE/DELETE/
    DROP/ALTER/ATTACH/PRAGMA` writes); open SQLite with a **read-only** connection
    (`sqlite3.connect("file:...?mode=ro", uri=True)`); set `progress_handler`/`set_progress_handler` or a
    watchdog thread for the statement timeout; `cur.execute(sql); rows = cur.fetchall()`. On error/timeout →
    `ok=False, detail=truncated message`.
  - `canonicalize(rows) -> hashable`: normalize cell types (round floats to ~6 dp, str-coerce, None→null) and
    sort the row multiset (order-insensitive) UNLESS the gold query/question implies ORDER BY (default
    order-insensitive — questions are phrased for sets; keep it simple and consistent).
  - `evaluate(prediction_text, item, timeout) -> {"em": 1.0|0.0, "ok", "predicted_sql", "rows", "detail"}`:
    `em = 1.0` iff `ok` and `canonicalize(rows) == canonicalize(item["gold_result"])`.
- `dataloader.py`: `class BizsqlDataLoader(SplitDataLoader)` — identical to `McqaDataLoader` (reuse `_load_items`).
- `rollout.py` (clone of mcqa rollout, SQL-shaped):
  - `_build_system(skill)` via `load_prompt("rollout_system", env="bizsql")`.
  - `_build_user(item)` = the schema DDL (read `schema_ddl_ref` once, cache) + `f"\n\nQuestion:\n{question}\n\n
    Return one SQL SELECT in a ```sql code block."` — schema in prompt pins table/column names (analog of MBPP's
    `example_assert`; without it pass@1 collapses on name-guessing = manufactured-unfair failure).
  - `chat_target(..., max_completion_tokens=512, stage="rollout", timeout=exec_timeout)`.
  - call `evaluate(response, item, timeout=sql_timeout)`; set `hard/soft/em`, `fail_reason = detail`. Persist
    prompts + conversation like mcqa.
- `batch_runner.py`: clone mcqa's; `task_type="bizsql"`; resume logic unchanged.
- `adapter.py`: `class BizsqlAdapter(EnvAdapter)` — clone `McqaAdapter`; thread a new `sql_timeout` (default 5)
  to `run_batch`→`process_one`; `get_task_types() -> ["bizsql"]`. Reflect path unchanged (global analyst prompts).
- `prompts/rollout_system.md`: SQL-analyst persona + output contract: "Return ONE ```sql block with a single
  SELECT answering the question using ONLY the given schema. No prose." `{skill_section}` slot (mcqa shape).
- `skills/initial-weak.md`: minimal: "Write a SQL query that answers the question. Output only SQL in a code
  block." (leaves procedural headroom).
- Register: add to `_register_builtins()` in `scripts/train.py` (try/except block like the others):
  `from skillopt.envs.bizsql.adapter import BizsqlAdapter; _ENV_REGISTRY["bizsql"] = BizsqlAdapter`.

- `configs/bizsql/local-pilot.yaml` (`_base_: ../_base_/default.yaml`) — blocks copied verbatim from
  `configs/mbpp/local-pilot.yaml` EXCEPT the `env` block:
  - `model`: optimizer `deepseek-v4-pro` (DeepSeek base url + `OPTIMIZER_OPENAI_API_KEY`), target
    `qwen2.5:7b-instruct-q4_K_M`, backends `openai_chat`/`qwen_chat`. **Identical to MBPP.**
  - `train`: `train_size: 100`, `batch_size: 20`, `num_epochs: 2`, `seed: 42`. `gradient`: `minibatch_size: 8`,
    `merge_batch_size: 8`. `optimizer`: `learning_rate: 4`, `min_learning_rate: 2`, `lr_scheduler: cosine`,
    `use_slow_update: false`, `use_meta_skill: false`. `evaluation`: `use_gate: true`, `eval_test: true`.
  - `env`: `name: bizsql`, `skill_init: skillopt/envs/bizsql/skills/initial-weak.md`, `split_mode: split_dir`,
    `split_dir: data/bizsql_split_s42`, `max_turns: 1`, `workers: 8`, `sql_timeout: 5`, `exec_timeout: 120`.
- `scripts/run_bizsql_pilot.ps1`: clone `scripts/run_mbpp_pilot.ps1`; config default
  `configs/bizsql/local-pilot.yaml`, out_root default `outputs/bizsql_local_pilot`. Keep env-load, optimizer-key
  check, Ollama warm-up, GPU sampler, `SKILLOPT_CONFIG/SPLIT_DIR/SEED/OUT_ROOT` overrides verbatim. Pre-flight:
  ensure `business.sqlite` exists (else run `seed_bizsql_db.py`) + DeepSeek endpoint smoke + one gold SQL through
  `evaluator.run_sql`.

## Related Code Files
- Create: `skillopt/envs/bizsql/__init__.py`, `adapter.py`, `dataloader.py`, `evaluator.py`, `rollout.py`,
  `batch_runner.py`, `prompts/rollout_system.md`, `skills/initial-weak.md`; `configs/bizsql/local-pilot.yaml`;
  `scripts/run_bizsql_pilot.ps1`; `tests/test_bizsql_evaluator.py`.
- Modify: `scripts/train.py` (register `bizsql`); `skillopt/config.py`/train kwarg allowlist if `sql_timeout`
  must be threaded through (verify, like MBPP's `sandbox_timeout`).
- Read for context: `skillopt/envs/mcqa/*`, `configs/mcqa/local-pilot.yaml`, `configs/_base_/default.yaml`,
  `scripts/run_mbpp_pilot.ps1` (or `run_local_pilot.ps1`), `scripts/smoke_test_optimizer.py`,
  `skillopt/envs/base.py`.

## Implementation Steps
1. Clone the mcqa file set into `skillopt/envs/bizsql/`; rename classes (`Bizsql*`), set `task_type="bizsql"`.
2. Write `evaluator.py` (the only genuinely new module): `extract_sql`, read-only/SELECT-only `run_sql` with
   timeout, order-insensitive `canonicalize`, `evaluate`. Unit-test standalone.
3. Wire `rollout.py` to inject schema DDL + call the evaluator; `max_completion_tokens=512`; thread `sql_timeout`.
4. Add `prompts/rollout_system.md` + `skills/initial-weak.md`; register env in `scripts/train.py`.
5. Write `configs/bizsql/local-pilot.yaml` (copy MBPP config, swap `env` block + `sql_timeout`).
6. Clone `run_bizsql_pilot.ps1`; set bizsql defaults + DB/endpoint/SQL smoke.
7. Compile-check: `python -c "import skillopt.envs.bizsql.adapter"` under `.venv`, `PYTHONUTF8=1`. Dry-run smoke
   only (no full train).

## Success Criteria
- [ ] `tests/test_bizsql_evaluator.py`: `run_sql` returns gold rows for every gold SQL in `data/bizsql_split_s42`
      and `em=1.0`; an obviously-wrong SQL scores `em=0.0`; a non-SELECT (e.g. `DROP TABLE`) is REJECTED (ok=False).
- [ ] `extract_sql` handles ```sql, bare ```, and "SQL: SELECT …" no-fence cases.
- [ ] `canonicalize` makes row-order differences score equal; float rounding tolerant.
- [ ] `import skillopt.envs.bizsql.adapter` succeeds; `bizsql` resolves in `_ENV_REGISTRY`.
- [ ] `diff` of bizsql vs mbpp config shows ONLY the `env` block + `sql_timeout` changed (hyperparam parity).
- [ ] A 2-item smoke rollout (weak skill) runs end-to-end and writes results with `hard` scores.

## Risk Assessment
- **SQL injection / destructive query from 7B** → read-only connection + single-SELECT allowlist + reject
  multi-statement; DB is a regenerable synthetic copy. Document the limitation (no full OS sandbox needed —
  SQLite RO is the sandbox).
- **Result-compare false negatives** (column order / float / NULL / int-vs-float) → `canonicalize` normalizes
  types + sorts multiset; round floats. Validate on the gold round-trip in the unit test.
- **Schema-name guessing unfairly fails 7B** → schema DDL in the prompt (mandatory); confirm it fits within
  context with `max_completion_tokens=512`.
- **Reflect prompt fit** → global analyst prompts are QA-generic; if Phase-11 SQL reflections are weak, add
  `skillopt/envs/bizsql/prompts/analyst_error.md`+`analyst_success.md` — deferred until proven needed (YAGNI).
