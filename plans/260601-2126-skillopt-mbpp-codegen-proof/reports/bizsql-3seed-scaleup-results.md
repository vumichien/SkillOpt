# bizSQL 3-Seed Scale-Up — the Win Holds

**Date:** 2026-06-02 · Target `qwen2.5:7b-instruct-q4_K_M` · Optimizer `deepseek-v4-pro`
· MC-run hyperparams (epochs 2, batch 20, edit_budget 4, patch update, gate on) · held-out test n=200, temp 0.
Scale gate per seed: held-out Δ ≥ +3.5pp (≈1 binomial SE @ n=200) **and** ≥1 accept.

## Headline — robust generalizing win across 3 seeds

| Seed | split | base (test) | trained (test) | **Δ** | dev (sel) | accepts | gate |
|------|-------|------|------|------|------|------|------|
| 42 | s42 | 0.880 | 0.985 | **+10.5pp** | 0.88→0.98 (+10) | 4 | **PASS** |
| 43 | s43 | 0.890 | 0.965 | **+7.5pp** | 0.86→1.00 (+14) | 2 | **PASS** |
| 44 | s44 | 0.870 | 0.935 | **+6.5pp** | 0.88→0.95 (+7) | 2 | **PASS** |
| **mean** | | **0.880** | **0.962** | **+8.2pp** (SD ±2.1) | | 2.7 | **3/3 PASS** |

Worst seed (+6.5pp) is still ~3× the per-seed binomial SE (≈2.1pp @ n=200) above zero. All three dev climbs
track their test climbs (+10/+10, +14/+7.5, +7/+6.5) → the gain **generalizes every time** — no overfit signature.
Contrast: every commonsense-MC run and the MBPP pilot showed dev-up / test-flat-or-down.

## Mechanism holds — clean skills, no leaked gold (all 3 verified)

Each seed's `best_skill.md` is general SQL conventions only — zero gold values, zero item-specific answers:
- **s42:** revenue-exclusion, active-sub/active-product, ROUND 2dp, GROUP BY id-not-name, line-item vs `total_amount`,
  ISO `BETWEEN` (no `MONTH()`/`YEAR()`), column disambiguation.
- **s43:** same family — date-range boundary calc (quarter end-dates), GROUP BY primary key, table-alias qualification,
  revenue exclusion, line-item-when-product-filtered, active products, "read schema comments".
- **s44:** output contract, `total_amount` when no product breakdown, alias qualification, `strftime`/ISO date ranges,
  schema-comment conventions.

Three independent optimizer runs converged on the **same small convention set** from different train splits — the
defining property of a homogeneous-procedural task. That's why the fix transfers to held-out test.

## What this confirms for the article

The lever for SkillOpt success is **transferable procedural structure**, not "procedure vs knowledge":

| Track | family | result | why |
|-------|--------|--------|-----|
| Commonsense-MC | knowledge-bound | flat | no procedural fix exists — pure recall |
| MBPP code-gen | heterogeneous-procedural | flat (−3pp, overfit) | each failure its own algorithm → optimizer fits selection set, no shared fix |
| **bizSQL Text-to-SQL** | **homogeneous-procedural** | **+8.2pp mean, 3/3 PASS** | small shared convention set fixes failures across train **and** test → generalizes |

bizSQL is the article's clean positive: a real, reproducible, mechanism-explained win that the MC and MBPP
negatives make sharper.

## Artifacts
- `outputs/bizsql-train/deepseek-v4-pro/qwen7b-s{42,43,44}/` — {summary,history}.json, best_skill.md, test_eval*/, gpu.csv.
- Splits: `data/bizsql_split_s{42,43,44}` (train 100 / val 100 / test 200, hard-heavy, carved from the 420 authored pool).
- Wall time: s42 ~33 min, s43 ~42 min, s44 ~34 min. Optimizer tokens ~2.4–2.8M/run.

## Open questions (for user)
- Next: write the Phase-12 combined Medium article (MC flat + MBPP flat + bizSQL +8.2pp win), or run the optional
  MBPP code-specific-analyst-prompt fallback first to rule out generic-reflect-prompt fit as MBPP's flat cause?
- Commit the uncommitted run artifacts + reports now, or keep holding?
