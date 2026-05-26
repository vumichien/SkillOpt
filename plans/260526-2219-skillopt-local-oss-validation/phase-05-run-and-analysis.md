---
phase: 5
title: "Run and Analysis"
status: blocked-on-user-run
priority: P2
effort: "1-3h active + run time"
dependencies: [4]
---

# Phase 5: Run and Analysis

## Overview
User runs the mcqa pilot on the RTX 3080; then analyze `outputs/<run>/` to determine whether the trained skill beats the initial skill on CommonsenseQA test, and extract artifacts for the article.

## Key Insight (verified)
Each run writes `history.json` (per-step history), `best_skill.md`, `skills/skill_vXXXX.md` (per-step snapshots), `steps/step_XXXX/`, `config.json`, `runtime_state.json` (resume). `scripts/eval_only.py` re-evals a skill on a split (README split aliases: `valid_unseen`=test, `valid_seen`=val). Token tracker summary printed at end. mcqa rows carry `hard`=letter-EM.

## Requirements
- Functional: complete pilot run; record initial-vs-best test accuracy delta.
- Functional: concise analysis artifact (curve, skill diff, cost) for Phase 6.
- Non-functional: reproducible numbers; report wall-clock + token cost; honest reporting incl. negative results.

## Architecture
- **Run** (user, 3080): `scripts/run_local_pilot.*`. Resume-aware.
- **Baseline**: `eval_only.py --config configs/mcqa/local-pilot.yaml --skill skillopt/envs/mcqa/skills/initial.md --split valid_unseen --split_dir data/mcqa_csqa_split ...`
- **Trained**: `eval_only.py ... --skill outputs/<run>/best_skill.md --split valid_unseen ...`
- **Analysis (Claude)**: read `history.json` (per-step val/test acc curve); diff `initial.md` vs `best_skill.md` (what reasoning rules the optimizer added); read token summary (DeepSeek cost). Summarize to a report under `plans/reports/`.

## Related Code Files
- Use: `scripts/run_local_pilot.*`, `scripts/eval_only.py`
- Read (outputs): `outputs/<run>/history.json`, `best_skill.md`, `skills/skill_v*.md`, `config.json`
- Read for context: `skillopt/envs/mcqa/skills/initial.md`
- Create: `plans/reports/analysis-260526-mcqa-csqa-pilot-results-report.md`

## Implementation Steps
1. User runs the launch script; confirm completion (or resume); capture console final test metric + token summary.
2. Run `eval_only.py` baseline (initial.md) + trained (best_skill.md) on test for a clean delta.
3. Claude reads `history.json` → per-step accuracy curve description.
4. Claude diffs `initial.md` vs `best_skill.md` → pull 2-3 concrete reasoning rules the optimizer learned (article examples).
5. Read token summary → DeepSeek $ + note local wall-clock.
6. Write analysis report; verdict vs success bar (positive test-accuracy delta?).

## Success Criteria
- [ ] Pilot completes end-to-end on local target (mechanism proven on a non-paper task).
- [ ] Baseline vs trained test accuracy recorded.
- [ ] Analysis report: curve, concrete skill-diff examples, cost, honest verdict.
- [ ] If no improvement: documented hypotheses (gate signal, batch size, epochs, letter-extraction) + suggested next config.

## Risk Assessment
- **Flat/negative delta on tiny pilot**: possible; report honestly + propose scale-up (more train items, enable slow_update/meta_skill, more epochs). A null result still validates the pipeline on a new task.
- **Letter-extraction false negatives** depress accuracy: cross-check a few `fail_reason`s vs raw `response`; if extraction is the culprit, fix evaluator (loop back to Phase 2) before judging the method.
- **Long wall-clock**: low workers + resume-aware run mitigate.
- **Don't auto-reverse pilot-first scope** if weak — surface to user before a full run.

## Next Steps
Feeds Phase 6 with real numbers + skill-diff examples.
