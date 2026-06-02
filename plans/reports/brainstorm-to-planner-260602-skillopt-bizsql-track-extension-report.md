# Brainstorm Summary — Add a Claude-Code-Generated Business Text-to-SQL Track to the SkillOpt Proof

**Date:** 2026-06-02 · **Status:** Design APPROVED → handoff to `/ck:plan` (extend existing plan)
**Extends:** `plans/260601-2126-skillopt-mbpp-codegen-proof/plan.md` (MBPP public-benchmark proof)
**Target (fixed):** `qwen2.5:7b-instruct` (Ollama, RTX 3080) · coder-7b gated fallback
**Optimizer (fixed):** `deepseek-v4-pro` · **Verifier:** SQL execution-accuracy (pure code)

---

## 1. Problem statement

Current plan proves SkillOpt lifts a **public** benchmark (MBPP code-gen). User wants the Medium post to
*also* carry a **self-generated, business-aligned** dataset — a "real problem that needs a skill to get
correct results" — generated **by Claude Code**, with SkillOpt applied to improve a skill on it, and the
results written up alongside MBPP in ONE combined article.

Chosen task family = **Text-to-SQL over a fixed e-commerce/SaaS analytics schema**.

## 2. The binding constraint (why most "business datasets" would fail)

Repo's verified thesis (`docs/articles/medium-skillopt-local-oss-csqa.md:418-430`; all prior MC runs flat
−1.2…−0.6 pp): a clean held-out lift needs THREE properties —
1. **single generalizable procedure** (skill lifts ALL test items, not memorized ones),
2. **deterministic verifier** (clean gate signal),
3. **procedural — not capability — headroom** (7B fails by mis-*following*, not by *can't*).

Any new dataset that violates these goes flat again. Text-to-SQL satisfies all three **iff** difficulty is
controlled (see §4). This is the make-or-break and is gated in Phase 10.

## 3. Brutal-honesty issue: the "engineered win" objection

Prior brainstorm REJECTED synthetic Claude-generated data precisely because it "reintroduces the
engineered-win objection." User now wants it. Resolution = 3 locked guardrails (user-confirmed):
- **Objective code verifier only** — execution-accuracy (run SQL, compare result set); NEVER an LLM judge.
- **Pre-registered headroom gate** — BEFORE training: strong model (Claude/DeepSeek) ≥~90% AND local 7B
  fails *procedurally*. Proves the win is procedural, not manufactured.
- **Blind gold** — gold SQL written to answer the question against the schema, with NO reference to any
  candidate skill; held-out test the optimizer never sees.
- (+ diversity-forced items so no single memorized constant wins.)

Article MUST show the generation method transparently — the credibility comes from the objective verifier +
the pre-registered gate, not from hiding the synthesis.

## 4. Why Text-to-SQL fits (per-property analysis)

| Property | How Text-to-SQL satisfies it | Failure mode if ignored |
|----------|------------------------------|--------------------------|
| Generalizable procedure | Schema-grounding conventions: exact table/column names, documented join keys, status/refund filters, date format, GROUP BY discipline, return only asked columns, single valid SELECT, no prose. Hold across ALL questions. | If procedure were per-question (knowledge), it'd go flat like MC. |
| Deterministic verifier | Execute candidate SQL on `business.sqlite`, compare RESULT SET to gold result (order-insensitive set/multiset). Standard Spider/BIRD execution-accuracy. | String-matching SQL would reject valid paraphrases → noisy gate. |
| Procedural headroom | 7B knows SQL syntax but mis-grounds to schema (wrong column, dropped status filter, wrong date fmt, wrong join). Skill-fixable. | If questions need complex nested subqueries → capability floor → flat like gemma-LogiQA. |

**Difficulty-band control is the key knob:** keep most items at 1–2 tables + aggregation + date/status
filters (procedural-headroom band); few harder. Claude-Code generation gives exact control here.

## 5. Dataset generation by Claude Code (deep, step by step)

`scripts/prepare_bizsql_data.py` + a Claude Code generation pass:

1. **Fix schema + seed DB.** Claude Code authors `data/bizsql/schema.sql` (deterministic DDL:
   customers, orders, order_items, products, subscriptions, support_tickets) + a fixed-seed deterministic
   seeder (e.g. seeded faker) → `data/bizsql/business.sqlite`. Synthetic but realistic rows. Document the
   conventions (status enums, date format, join keys) — these are what the skill must learn.
2. **Generate (question, gold SQL) pairs.** Strong model writes diverse NL business questions across
   difficulty bands + gold SQL. **Blind gold:** gold written only against schema; no skill in context.
3. **Auto-validate gold (objective-verifier guardrail).** Execute every gold SQL on the DB; drop any that
   error or return empty. Keep the executed RESULT SET as the verifier target. (Optional: double-generate
   gold and keep only result-agreeing pairs → higher gold trust.)
4. **Difficulty-band control.** Bucket questions; keep majority in procedural-headroom band; cap hard ones.
5. **Diversity-forced.** Vary templates / entities / filters / aggregations so memorized constants can't win.
6. **Deterministic split.** Write `data/bizsql_split_s{42,43,44}/{train,val,test}/items.json` (mcqa shape)
   + `meta.json`. 100 train / 100 val / 200 test per seed (mirror MBPP/MC sizing).

**Item schema:** `{id, question, db_path, gold_sql, gold_result}` (gold_sql kept for the per-step trace;
scoring uses gold_result only).

## 6. The env (`skillopt/envs/bizsql/` — clone of `envs/mcqa/`)

- `dataloader.py` — JSON-array loader (reuse generic SplitDataLoader).
- `rollout.py` — single-turn: system = skill; user = question + **schema DDL** (pins table/column names;
  without it pass@1 collapses on name-guessing — an unfair manufactured failure, analogous to MBPP's
  example-assert). Emit SQL in a code block.
- `evaluator.py` (**new critical piece**) — **SQL execution evaluator**: strip md fences → reject non-SELECT
  / DML / DDL (read-only connection) → execute with statement timeout (~5–8s) on a copy/RO connection of
  `business.sqlite` → compare result set to `gold_result` (order-insensitive unless ORDER BY asked) →
  score 1.0 iff equal. SQLite is naturally sandboxable; reject anything but a single SELECT.
- `adapter.py` / `batch_runner.py` — clone mcqa; reuse generic minibatch reflect engine.
- `skills/initial-weak.md` — *"Write a SQL query that answers the question. Output only SQL in a code block."*

**Procedure the optimizer should discover (generalizes → held-out lift):** exact schema names, documented
join keys, apply status/refund filters, schema date format, GROUP BY all non-aggregates, return exactly the
asked columns, single valid SELECT, no prose/fences. Unlike MC, these hold across ALL items.

## 7. Config — identical hyperparams (clean contrast)

`configs/bizsql/local-pilot.yaml` — **identical hyperparams to MC v3 / MBPP** (bs=20, 2 epochs→10 edits,
lr=4 cosine, temp=0 gate, strict-improve). ONLY env (`bizsql`) + data differ. Same optimizer
(`deepseek-v4-pro`), same target (`qwen2.5:7b-instruct`). This makes flat→win attributable to TASK FAMILY,
not config/model/optimizer.

## 8. Target-model decision (the whichllm question) — RESOLVED

- **Primary = keep `qwen2.5:7b-instruct`** (user-confirmed). Preserves the flat-MC→win contrast — the
  proof's whole value. whichllm leaderboard = general scores, NOT Text-to-SQL execution accuracy → irrelevant;
  repo finding = model strength is NOT the lever, headroom is. 14B-Q3/27B entries are tight/spill on 10 GB.
- **Phase-10 gate is the real decision point.** SQL is harder than MBPP. If instruct-7B is capability-floored
  on SQL, fall back to **`qwen2.5-coder:7b`** (same size/family, fits 10 GB, code-specialized) and DISCLOSE
  the swap in the article. Fix = difficulty-band control + gate + coder fallback, NOT chasing the leaderboard.
- Optional stretch (flagged, post-primary): 2-target mini-experiment (instruct vs coder) to show the skill
  lift holds across both. Not core.

## 9. Plan integration — extend current plan (phases 8–12) + ONE combined article

New phases appended to `plans/260601-2126-skillopt-mbpp-codegen-proof/`:
- **Phase 8 — Business schema + DB seed + Claude-Code data gen.** `schema.sql`, deterministic seeder,
  `prepare_bizsql_data.py`, blind gold, auto-validate, 3 seeds.
- **Phase 9 — `envs/bizsql/` + SQL exec evaluator + weak-init skill + `configs/bizsql/local-pilot.yaml`** +
  `run_bizsql_pilot.ps1` (clone of run_mbpp_pilot) + endpoint smoke.
- **Phase 10 — Headroom probe HARD GATE.** Baseline pass@1 on 100 items + hand-categorize ~20 failures
  procedural vs capability + strong-model ceiling check. Proceed only if ≥~10–15 pp procedural. Fallback
  decision: coder-7b (pause + ask user, per existing gate convention).
- **Phase 11 — seed-42 pilot → 3-seed scale** if Δ clears ±1 SE (~±3.5 pp @ n=200) with ≥1 visible accept.
- **Phase 12 — Combined article integration.** Rewrites phase-07 scope: ONE post =
  Exp A (MBPP public) + Exp B (business SQL self-generated) + the generation methodology section +
  cross-family conclusion ("same flat loop now lifts on BOTH a public code benchmark AND a self-built
  business task → headroom thesis holds across task families").

Also update `plan.md`: title/description, Phases table (add 8–12), Key Decisions (add bizsql rows),
Gates (add Phase-10), Success Criteria (add business-track Δ), Dependencies (add SQLite stdlib — no new dep).

## 10. Combined article structure (depth = the ask)

Hook (flat MC → MBPP win → "but does it work on MY data?") → **Exp A: MBPP** (existing phase-07 structure,
per-step trace) → **Exp B: business Text-to-SQL** — (a) why I built it + the engineered-win guardrails
(objective verifier, blind gold, pre-registered gate), (b) how Claude Code generated schema+DB+pairs,
(c) headroom probe, (d) per-step deep dive (failed SQL rollouts → optimizer reflection JSON → skill edit
before/after → gate on val → held-out effect), (e) results @ n=200, Δ+SE, 3-seed mean±std → **cross-family
conclusion table** (MC flat vs MBPP lift vs bizSQL lift) → honest verdict + open questions.

## 11. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Capability ceiling on SQL (#1; SQL harder than MBPP) → flat | difficulty-band control at generation + Phase-10 hard gate + coder-7b fallback |
| Engineered-win perception | objective exec verifier + blind gold + pre-registered gate + diversity; show method transparently |
| Gold incorrectness | auto-execute + drop errors/empties; optional double-gen + result-agreement keep |
| SQL ambiguity (multiple correct queries) | score on RESULT SET equality (order-insensitive), not SQL string; prefer unambiguous questions |
| DB safety | read-only connection, reject non-SELECT, statement timeout, copy DB per run |
| Schema-name guessing unfairly fails 7B | include schema DDL in the user prompt (analog of MBPP example-assert) |
| Small-eval overfit | conventions generalize; 100-val gate + n=200 test + 3 seeds |

## 12. Out of scope

Other envs; optimizers other than deepseek-v4-pro; multi-turn agentic SQL; the 2-target mini-experiment
(flagged stretch); real proprietary data (synthetic schema only). The MBPP track is unchanged except the
article merge.

## 13. Success criteria (business track)

- Phase-10 gate passes (≥~10–15 pp procedural headroom; strong model near-ceiling).
- Held-out test Δ (trained − weak-init, n=200) beyond ±1 binomial SE (~±3.5 pp) with ≥1 visible accept +
  monotonic dev climb.
- 3-seed mean Δ positive and outside noise.
- Combined article reproduces the generation method + per-step mechanism end-to-end and ends in a held-out
  win on BOTH tracks (or honestly reports whichever floors).

## 14. Open questions (for `/ck:plan` to resolve or surface)

- **Dataset size:** 100/100/200 per seed (mirror MBPP) vs smaller to cut gen cost? Default = mirror MBPP.
- **Gold double-generation:** single-gen + auto-validate (cheaper) vs double-gen + result-agreement (higher
  trust)? Default = single-gen + auto-validate; escalate to double-gen only if gold-error rate high.
- **Schema size:** how many tables/columns? Default = 6 tables, enough for joins+aggregation+date/status,
  small enough to fit the DDL in the prompt. Decide exact DDL in Phase 8.
- **Difficulty bands:** exact % split easy/medium/hard. Default = ~60/30/10; tune at Phase-10 gate.
