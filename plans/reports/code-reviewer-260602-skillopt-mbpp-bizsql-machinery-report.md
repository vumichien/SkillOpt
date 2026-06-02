# Code Review — SkillOpt MBPP + bizSQL Machinery

Date: 2026-06-02
Scope: new MBPP env, new bizSQL env, data-prep + probe scripts, configs, train.py registry, .gitignore.
Focus: correctness / regression / contract safety (style excluded — ruff passes).
Tests: 39/39 pass (26 mbpp + 13 bizsql) via project venv.

## Overall Assessment

Solid, faithful clones of the mcqa template. Adapters satisfy the `EnvAdapter`
contract; batch_runner/rollout/dataloader shapes match mcqa exactly with only the
documented per-env additions (`sandbox_timeout` / `sql_timeout`). The SQL guard is
SECURE (no write/DDL/multi-statement escape; `mode=ro` is a hard backstop). All 8
acceptance criteria are met. Findings below are correctness-of-measurement and
minor robustness issues, none blocking the deterministic-machinery milestone.

## Acceptance Criteria — Verdict

1. EnvAdapter interface + mcqa parity + timeout threading — PASS. Both adapters
   subclass EnvAdapter, override the same methods as McqaAdapter, and thread
   `sandbox_timeout`/`sql_timeout` cfg->adapter->run_batch->process_one->evaluator.
2. MBPP sandbox safe + correct; extract_code fenced/bare/raw — PASS (see L2 caveat).
3. bizSQL READ-ONLY + SELECT-only, statement timeout, order/float/None-tolerant
   canonicalize, no DB-mutation escape — PASS for safety (see M1 over-rejection,
   M2 empty-set).
4. No train.py registry regression — PASS. New try/except blocks mirror the
   existing pattern exactly (scripts/train.py:56-65).
5. Config hyperparam parity (env block only) — PASS (see note on `_base_` depth).
6. Data-prep determinism + idempotency + sound gold filters — PASS.
7. Probe arm extraction + no TEST split — PASS. Both probes hard-restrict
   `--split` to `choices=["train","val"]`.
8. Blind-gold guardrail in generate_bizsql_pairs.py — PASS. Generator context is
   schema + conventions only; no skill, no target model.

## Critical

None.

## High

None.

## Medium

### M1 — SQL guard over-rejects legitimate SELECTs (measurement bias, NOT a leak)
`skillopt/envs/bizsql/evaluator.py:58-70`. The guard is correct on safety but
operates on raw text, so it false-positive-rejects valid read-only SELECTs whose
string literals / comments contain a banned token or `;`. Verified live:
  - `SELECT 'delete me'`        -> "write/DDL keyword rejected"
  - `SELECT ';'`                -> "multiple statements not allowed"
  - `SELECT 1 -- ; DELETE ...`  -> "multiple statements not allowed" (`;` in comment)
  - `SELECT /* update */ 1`     -> "write/DDL keyword rejected"
Impact: a 7B that emits a SELECT returning a literal string containing
"update"/"delete"/etc., or a `;` inside a quoted value, is scored em=0 even though
the query is valid and read-only. This UNDERSTATES target accuracy and could bias
the headroom probe / training signal. Real-world likelihood on business questions
is low-to-moderate (status strings like 'cancelled' are fine; 'deleted'/'updated'
literals or aliased text are the risk). Safety is unaffected — `mode=ro` blocks
mutation regardless. Suggest: tokenize/strip string-literals + comments before the
keyword/`;` scan, OR rely on `mode=ro` + a single-statement parse and drop the
keyword blacklist. Document as a known measurement caveat if left as-is.

### M2 — canonicalize() collapses empty result-set and absent gold to the same `()`
`skillopt/envs/bizsql/evaluator.py:112-118`. `canonicalize([])`,
`canonicalize(None)`, and `canonicalize(())` all return `()`. So a prediction
that returns ZERO rows scores em=1.0 against a gold whose `gold_result` is missing
or empty. Mitigated in practice: `prepare_bizsql_data.py:89-91` drops empty golds,
so committed items always have a non-empty `gold_result` — an empty prediction
therefore cannot match. But the invariant lives in the data-prep step, not the
evaluator; if a future split bypasses that filter (or an item is hand-added), a
zero-row prediction would silently pass. Suggest a guard in `evaluate`: treat
`ok and not rows` as em=0 unless `gold_result` is itself explicitly non-empty, or
sentinel-distinguish empty-vs-missing in `canonicalize`.

## Low

### L1 — `task_timeout` argument is dead in all three envs
`adapter.py:81` (mbpp), `:81` (bizsql), mcqa `:79` pass `task_timeout=self.exec_timeout`
(=120) into `run_batch`, but `run_batch` immediately clamps it:
`task_timeout = max(task_timeout, exec_timeout + 60)` (batch_runner.py:49) -> 180.
So the passed value is always overridden; the per-task watchdog is effectively
`exec_timeout + 60`. This is INHERITED from mcqa (not a new bug) and harmless, but
the argument is misleading. No action needed for parity; note for future cleanup.

### L2 — extract_code/extract_sql take the FIRST fenced block only
`mbpp/evaluator.py:32-42`, `bizsql/evaluator.py:35-55`. Non-greedy regex returns
the first ```` ```python ```` (or first bare ```` ``` ````) block and ignores later
ones. If a model emits an explanatory snippet first and the real answer second,
it scores 0. Matches the documented priority order and the mcqa convention, and is
the conventional MBPP/Spider behavior, so acceptable. Flagging only as a known
extraction limitation that may show up in probe failure buckets as
`extraction_format`.

### L3 — Sandbox does not kill grandchild processes on timeout
`mbpp/evaluator.py:54-69`. `subprocess.run(timeout=...)` kills the candidate
process but not any child it spawned (no process-group kill). The docstring
already scopes usage to "pure-compute MBPP asserts, trusted-ish local, no OS
container," so this is acknowledged and acceptable for the intended local use.
Do not run with untrusted/process-spawning test setups.

## Positive Observations

- train.py registry change is a minimal, exact mirror of the existing pattern;
  existing envs unaffected (import-guarded).
- `.gitignore` negations verified by `git check-ignore`: schema.sql + raw_pairs.jsonl
  are committable; business.sqlite + split dirs stay ignored. Correct and matches intent.
- Config parity holds: mcqa local-pilot chains through `mcqa/default.yaml` ->
  `_base_/default.yaml`; mbpp/bizsql chain straight to `_base_/default.yaml`. Both
  redeclare train/gradient/optimizer/model blocks identically, so the only effective
  delta is the env block — exactly the design intent for a clean task-family contrast.
- bizSQL read-only backstop independently proven: `mode=ro` rejects DDL even if the
  guard were bypassed (test_bizsql_evaluator.py:99-105). Good defense-in-depth.
- Blind-gold guardrail is airtight: generator system prompt is schema+conventions only.
- Both data-prep scripts seed `random.Random` and self-check; bizSQL self-check
  re-executes a 10-item sample against live DB to confirm gold_result still matches.
- Probes can never touch the test split (argparse choices), and `_PROCEDURAL`
  bucket sets correctly exclude `wrong_result` (bizsql) from the auto procedural share.

## Unresolved Questions

1. M1: is the SQL-literal/comment false-rejection acceptable as a measurement
   caveat for the article, or should the guard be hardened to strip literals/comments
   before scanning? (Safety is fine either way; this only affects reported accuracy.)
2. M2: should the empty-result invariant be enforced in the evaluator as well as in
   data-prep, to be robust to future split changes?
