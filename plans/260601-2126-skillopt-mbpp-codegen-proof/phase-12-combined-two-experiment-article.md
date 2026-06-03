---
phase: 12
title: "Combined Two-Experiment Article"
status: pending
priority: P2
effort: "1-1.5d"
dependencies: [6, 11]
---

# Phase 12: Combined Two-Experiment Article (supersedes Phase 7)

## Overview
Write ONE standalone Medium article carrying BOTH experiments: the same SkillOpt loop that was flat on
commonsense MC now produces a real held-out lift on (A) a **public** code benchmark (MBPP) AND (B) a
**self-generated business** Text-to-SQL task built with Claude Code — with a deep per-step trace for each and a
cross-family conclusion. **This phase supersedes the standalone-MBPP scope of Phase 7**; Phase 7's MBPP material
becomes Experiment A here.

## Requirements
- Functional: a self-contained article citing the real MBPP 3-seed numbers (Phase 6) + the real bizSQL 3-seed
  numbers (Phase 11) + the flat-MC contrast; a transparent dataset-generation-methodology section for Exp B.
- Non-functional: depth is the point (user's core ask) — show the mechanism step by step for both experiments.
  Honest verdict; only real measured numbers; unresolved questions at the end. Engineered-win objection
  explicitly addressed for Exp B (objective verifier + pre-registered gate + blind gold).

## Architecture (article structure)
- File: `docs/articles/medium-skillopt-when-prompt-training-works.md` (later consolidated single final post —
  merges this two-experiment article + the CSQA post + the granite second-target arc; old per-experiment article
  files removed). Update `mkdocs.yml`/nav if articles are listed.
- Sections:
  1. **Hook** — recap: MC went flat across 3 datasets × 2 targets × 2 optimizers; the diagnosis (procedure-bound
     tasks should lift). Two tests: a public benchmark and "but does it work on MY business data?"
  2. **What SkillOpt does + the shared setup** — qwen2.5:7b-instruct (Ollama, RTX 3080), deepseek-v4-pro,
     single-turn, IDENTICAL hyperparams across MC/MBPP/bizSQL (the controlled variable is ONLY the task family).
  3. **Experiment A — MBPP (public).** Why it's the right family; the headroom probe; weak init; ★ per-step deep
     dive (failed rollouts → reflection JSON → skill diff → gate → held-out effect); results @ n=200 + Δ + SE;
     3-seed mean ± std. (Absorbs Phase 7 content.)
  4. **Experiment B — Business Text-to-SQL (self-generated).**
     a. **Why I built my own benchmark** — real business problem (NL→SQL over a fixed schema) + the
        engineered-win objection stated up front.
     b. **The guardrails that make a self-made win credible** — objective execution-accuracy verifier (no LLM
        judge), blind gold, pre-registered headroom gate (strong model ≥~90% / 7B fails procedurally), diversity.
     c. **How Claude Code generated it** — schema + seeded SQLite DB, blind (question, gold SQL) generation,
        execution-validation, deterministic split. Show the generator prompt + the validation step (transparency).
     d. **The headroom probe** (Phase 10) — Arm A 7B baseline vs Arm B strong ceiling + procedural share.
     e. ★ **per-step deep dive** — failed SQL rollouts (wrong column / dropped status filter / bad join) →
        optimizer reflection JSON → skill edit before/after (schema-grounding conventions) → gate on val →
        held-out effect.
     f. **Results** — baseline vs trained @ n=200, Δ + SE, accepts, skill growth, 3-seed mean ± std, cost/wall/GPU.
  5. **Cross-family conclusion** — the headline table: **MC (flat −0.6 pp) vs MBPP (+X pp) vs bizSQL (+Y pp)** —
     same loop/optimizer/GPU/target; the lift tracks task family (procedural headroom + deterministic verifier +
     generalizable procedure), exactly as the diagnosis predicted. Confirms model strength was never the lever.
  6. **Reproduce** — exact commands for both tracks (prepare_mbpp_data / run_mbpp_pilot; seed_bizsql_db /
     generate_bizsql_pairs / prepare_bizsql_data / run_bizsql_pilot) + artifacts map.
  7. **Honest verdict + open questions** (incl. any coder-7b fallback if used; the 2-target mini-experiment as a
     flagged stretch; HumanEval transfer stretch).

## Related Code Files
- Create/replace: `docs/articles/medium-skillopt-when-prompt-training-works.md` (consolidated single final post).
- Modify: `mkdocs.yml` nav if needed; mark Phase 7 as superseded by Phase 12 in `plan.md`.
- Read: `reports/mbpp-headroom-probe-report.md`, `reports/mbpp-3seed-results.md`,
  `reports/bizsql-headroom-probe-report.md`, `reports/bizsql-3seed-results.md`, run outputs
  (`history.json`, `best_skill.md`, `steps/step_XXXX/`), `docs/articles/medium-skillopt-local-oss-csqa.md`
  (contrast + voice), `data/bizsql/schema.sql` + the generator prompt (for the methodology section).

## Implementation Steps
1. Pull real numbers from Phase 6 (MBPP) and Phase 11 (bizSQL) outputs — no invented figures.
2. Extract one clean per-step trace per experiment from `steps/step_XXXX/` (real reflection JSON + real diff).
3. Draft sections in order; keep the cross-family contrast table front-and-center.
4. Verbatim-cite each `best_skill.md` excerpt (the procedures the optimizer actually wrote) + the bizSQL
   generator prompt (methodology transparency).
5. Optionally render the loop schematic + the cross-family table via `/ck:preview --diagram`.

## Success Criteria
- [ ] Article uses only real measured numbers from both tracks.
- [ ] Per-step trace for EACH experiment (failed rollout → reflection → edit → gate → held-out gain).
- [ ] Exp B methodology section shows generation + the three credibility guardrails explicitly.
- [ ] Cross-family contrast table present (MC flat vs MBPP lift vs bizSQL lift); verdict honest; open questions listed.

## Risk Assessment
- **Temptation to overclaim** → report Δ with SE; if a 3-seed mean is modest, frame as "real but bounded", not a
  miracle. Honesty is the article's brand (per the CSQA post).
- **If either track did NOT lift** → the article pivots honestly: a public OR self-made procedure-bound task that
  still floors on a 7B is itself a finding about the headroom boundary. Decide framing with the user before writing.
- **Engineered-win criticism on Exp B** → pre-empt it in §4a/§4b; the objective verifier + blind gold +
  pre-registered gate are the answer, shown not just asserted.
