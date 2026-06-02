---
phase: 8
title: "BizSQL Schema and Claude-Code Data Gen"
status: code-complete-run-deferred
priority: P1
effort: "1d"
dependencies: []
---

# Phase 8: BizSQL Schema and Claude-Code Data Generation

## Overview
Build the self-generated business Text-to-SQL dataset: a fixed e-commerce/SaaS SQLite schema + deterministic
seeded DB, a Claude-Code-authored set of (NL question, **blind** gold SQL) pairs, validated by execution, then
carved into deterministic `items.json` splits (100 train / 100 val / 200 test, seeds 42/43/44). This is the
"real business problem, my own data" track. Mirrors `prepare_mcqa_data.py`/`prepare_mbpp_data.py` in structure.

## Requirements
- Functional: a fixed schema + reproducible DB; diverse blind (question, gold_sql) pairs; auto-validate gold by
  execution; compute the gold result set; deterministic seeded splits + meta.json + self-check.
- Non-functional: deterministic data prep (seeded shuffle, fixed DB seed); generation checkpointed to a
  committed `raw_pairs.jsonl` so the split step is fully reproducible without re-calling any LLM; each script
  < 200 LOC; `.venv` + `PYTHONUTF8=1`.

## Architecture
Separate **creative generation** (Claude-Code / strong-model, non-deterministic, run once) from **deterministic
data prep** (pure script over the checkpoint). Three artifacts:

1. **Schema + DB (deterministic).**
   - `data/bizsql/schema.sql` — 6-table e-commerce/SaaS DDL: `customers` (id, name, country, region,
     created_at), `products` (id, name, category, unit_price, active), `orders` (id, customer_id, ordered_at,
     status ∈ {placed,shipped,delivered,refunded,cancelled}, total_amount), `order_items` (id, order_id,
     product_id, qty, unit_price), `subscriptions` (id, customer_id, plan, mrr, started_at, canceled_at NULL),
     `support_tickets` (id, customer_id, opened_at, priority, status). Document the **conventions** the skill
     must learn: status enum casing, ISO `YYYY-MM-DD` dates, join keys, "revenue excludes refunded/cancelled",
     soft-state via `canceled_at IS NULL`.
   - `scripts/seed_bizsql_db.py` — fixed-seed deterministic seeder (stdlib `random.Random(7)`, no faker dep
     required; if faker used, pin its seed). Writes `data/bizsql/business.sqlite`. Realistic-but-synthetic rows
     (e.g. ~300 customers, ~120 products, ~2k orders, ~5k order_items, ~400 subscriptions, ~600 tickets).
     Idempotent: drop+recreate from `schema.sql`. **Commit the schema + seeder, not the .sqlite** (regen on
     demand; .sqlite in `.gitignore`).

2. **Blind pair generation (Claude-Code, run once → checkpoint).**
   - `scripts/generate_bizsql_pairs.py` — calls a STRONG model (reuse the DeepSeek optimizer client in
     `skillopt/model.py`, or Claude) with ONLY `schema.sql` + conventions in context (**blind gold guardrail:
     no candidate skill, no target model, ever in context**). Prompts for diverse NL business questions +
     gold SQL across difficulty bands. Appends raw `{question, gold_sql, difficulty}` to
     `data/bizsql/raw_pairs.jsonl` (committed). Over-generate (~400–500 raw) to survive validation drops.
   - **Diversity-forced:** vary entities (revenue/counts/averages/top-N/date-window/status-filter/join across
     2 tables), filters, and phrasings so no single memorized constant can win. The generator prompt enumerates
     question archetypes × difficulty so coverage is explicit, not incidental.
   - **Difficulty bands** (~60/30/10 easy/med/hard): easy = single table + 1 filter/aggregate; med = 2-table
     join + group-by + date/status filter; hard = 3 tables or nested/having. Cap hard at ~10% to stay in the
     procedural-headroom band, NOT the capability ceiling (the #1 risk — see Phase 10).

3. **Deterministic validate + split.**
   - `scripts/prepare_bizsql_data.py` — load `raw_pairs.jsonl` + `business.sqlite`; for each pair: execute
     `gold_sql` read-only (reuse the Phase-9 `run_sql` evaluator helper) → DROP if it errors, times out, or
     returns empty/whole-table (quality filter); compute the **gold result set** (canonicalized rows). Dedup by
     normalized SQL + by result signature. Stratify by difficulty band, then deterministic
     `random.Random(seed).shuffle` → carve 100/100/200. Write splits + meta.json + self-check.

**bizsql item schema** (`{split}/items.json`):
```json
{"id": "bizsql-042", "question": "Total revenue from EU customers in Q1 2026, excluding refunded orders.",
 "db_path": "data/bizsql/business.sqlite", "schema_ddl_ref": "data/bizsql/schema.sql",
 "difficulty": "medium", "gold_sql": "SELECT ...", "gold_result": [[12345.67]]}
```
`gold_sql` is kept for the article's per-step trace; **scoring uses `gold_result` only** (execution-accuracy).
The schema DDL is fed into the prompt at rollout time (Phase 9), so the target never has to guess names.
Loadable by the default `SplitDataLoader.load_split_items` (first `*.json` → array) → Phase-9 dataloader is a
one-line subclass.

## Related Code Files
- Create: `data/bizsql/schema.sql`, `scripts/seed_bizsql_db.py`, `scripts/generate_bizsql_pairs.py`,
  `scripts/prepare_bizsql_data.py`.
- Create (committed checkpoint): `data/bizsql/raw_pairs.jsonl`.
- Create (output, gitignored): `data/bizsql/business.sqlite`, `data/bizsql_split_s42/{train,val,test}/items.json`
  + `meta.json` (and `_s43`, `_s44`).
- Read for context: `scripts/prepare_mcqa_data.py`, `scripts/prepare_mbpp_data.py` (structure/self-check),
  `skillopt/model.py` (strong-model client for the generator), `.env.local-pilot` (optimizer key).
- Modify: `.gitignore` (add `data/bizsql/business.sqlite`, `data/bizsql_split_*`).

## Implementation Steps
1. Author `schema.sql` (6 tables + documented conventions) and `seed_bizsql_db.py`; build `business.sqlite`.
2. Write `generate_bizsql_pairs.py`; run ONCE (blind: schema only) to emit ~400–500 pairs → `raw_pairs.jsonl`.
   Manually skim a sample for realism/diversity (curation is part of "by Claude Code").
3. Write `prepare_bizsql_data.py`: execute-validate every gold, compute `gold_result`, dedup, stratify, split.
   Run seed 42 first: `--n-train 100 --n-val 100 --n-test 200 --seed 42 --out-dir data/bizsql_split_s42`.
   (43/44 deferred to Phase 11, only if the pilot clears the gate.)
4. Extend `_self_check`: id/question/db_path present, `gold_sql` non-empty, `gold_result` non-empty, difficulty
   ∈ band set; re-execute a 10-item sample to confirm `gold_result` matches live execution.

## Success Criteria
- [ ] `data/bizsql/business.sqlite` regenerates deterministically from `schema.sql` + `seed_bizsql_db.py`.
- [ ] `data/bizsql_split_s42/` has train(100)/val(100)/test(200)/items.json + meta.json; `--self-check` PASS.
- [ ] Every retained item's `gold_sql` executes clean and its `gold_result` matches a fresh execution.
- [ ] Difficulty distribution ≈ 60/30/10; ≥ ~8 distinct question archetypes present (diversity check).
- [ ] Gold generated BLIND (generator context contains only schema/conventions — assert in the script header).

## Risk Assessment
- **Engineered-win perception** → blind gold + objective execution validation + diversity coverage; the article
  shows the generator prompt + the validation step transparently.
- **Gold incorrectness** → execute-validate drops errors/empties; optional double-generation + result-agreement
  keep if the post-validation gold-error rate (spot-checked) is high. Default: single-gen + auto-validate.
- **SQL ambiguity (multiple correct queries)** → scoring is on RESULT SET, not SQL string; the dedup-by-result
  step and the "drop whole-table/empty" filter remove ill-posed questions.
- **Too-hard distribution → capability floor** → cap hard band ~10%; Phase 10 gate is the real check; tune bands
  there if the 7B floors.
