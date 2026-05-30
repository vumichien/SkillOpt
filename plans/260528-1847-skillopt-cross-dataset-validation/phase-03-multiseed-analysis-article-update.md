---
phase: 3
title: "Multi-seed Analysis + Article Update"
status: done   # flat result (+0.33pp mean) written into article with config + why-it-failed/why-paper-worked analysis
priority: P1
effort: "1.5h"
dependencies: [2]
---

# Phase 3: Multi-seed Analysis + Article Update

## Overview
Aggregate the 3 seed runs into a mean ± std test delta, decide the win/flat verdict, and write
a new SocialIQA experiment section into the Medium article with verified numbers.

## Requirements
- Functional: report per-seed `baseline_test` / `test` / delta + aggregate mean ± std; update article.
- Non-functional: every number cited must trace to a `summary.json` field (fact-check discipline from prior code-reviewer report). Use percentage-points ("pp") not "%" for deltas.

## Architecture
Win test: mean test delta > +3pp AND the delta CI excludes 0. For n=200 test, 1 item = 0.5pp;
binomial 95 % CI half-width ≈ ±6.9pp at p≈0.5, tighter near the tails. Across 3 seeds, report
mean ± sample std of the per-seed deltas as the robustness signal (small-n, so present as
descriptive, not a formal t-test).

Aggregation is a few lines of arithmetic over 3 `summary.json` files — no new module needed
(KISS). Do it inline / a throwaway snippet; do NOT add a stats dependency.

## Related Code Files
- Read: `outputs/mcqa_siqa_s42/summary.json`, `_s43/summary.json`, `_s44/summary.json`
- Read: `outputs/mcqa_siqa_s42/best_skill.md` (excerpt for the article — disclose if trimmed, per prior review D3)
- Modify: `docs/articles/medium-skillopt-local-oss-csqa.md`
  - Add a new section: "Experiment: training a skill from scratch on SocialIQA".
  - Update/replace the scaffolded "What's coming next" → Experiment 3 (fresh-train matrix) with real SocialIQA rows.
  - Keep the existing CSQA v1/v2/v3 narrative intact; SocialIQA is an additive new result.

## Implementation Steps
1. Extract per seed: `baseline_test_hard`, `test_hard`, delta, total_accepts, best_step, val trajectory, wall_time_s, token spend.
2. Compute mean ± std of test delta across seeds 42/43/44; note per-seed val climb.
3. Write verdict: WIN (mean Δ > +3pp, CI excludes 0) vs FLAT (within CI). Use the phrasing templates from the design report's risk framing — honest either way.
4. Draft the article section: setup (SocialIQA, 3-option, splits, mitigations), per-seed table, aggregate, the trained skill excerpt (disclose trim), and the verdict. Mirror the existing v3 table style.
5. Cross-check every cited number against the JSON (self-fact-check; this article had a prior 10× pricing error — be rigorous).
6. Commit: `feat: extend SkillOpt validation to SocialIQA fresh-train` (no `chore`/`docs` — real content delivery, per project git rule; this is article + scripts, not `.claude/`).

## Success Criteria
- [ ] Per-seed + aggregate numbers recorded, each traceable to a `summary.json` field.
- [ ] Article has a complete SocialIQA section; no `_coming_` placeholder left for the fresh-train experiment.
- [ ] Verdict stated honestly (win or flat) with CI reasoning.
- [ ] Skill excerpt labeled "abridged; full at outputs/..." if trimmed.

## Risk Assessment
- Flat test across seeds → still a valid result; frame as the honest 2-dataset overfit-ceiling story, do NOT overclaim. (User accepted this risk choosing SocialIQA.)
- Cherry-pick temptation (report only the best seed) → forbidden; report all 3 + aggregate.
- Stale scaffolding: ensure the article's older "Experiment 1/3 _coming_" cells are reconciled with what actually ran (whole-plan consistency).
