# Phase 06 — Docs + Medium Article Update

## Context Links
- Article: `docs/articles/medium-skillopt-local-oss-csqa.md`
- Analysis outputs: `results-logiqa.csv`, `delta-vs-scale.png` (Phase 05)
- Rules: `.claude/rules/documentation-management.md`

## Overview
- **Priority:** P1
- **Status:** pending
- Fold the LogiQA cross-family results into the article (and a validation doc) with real numbers + plot.

## Key Insights
- The article already pre-registered the headroom hypothesis ("Why it didn't work here" + "What's coming next").
  This phase resolves that cliffhanger with data — either "it works when there's headroom" (positive) or an
  honest "still flat even with headroom" pivot. Report whichever is true.
- Keep the article's honest, in-place-update voice; add a new section + update the TL;DR table.

## Requirements
- Functional: new article section (LogiQA × small models), updated TL;DR, embedded results table + plot ref,
  updated "What's coming next" (mark Experiment 2/scale done as applicable). A docs/ validation summary doc.
- Non-functional: markdown only (no code/plan-ref leakage into prose claims); cite arm3−arm2 with CI.

## Architecture
- Edit `docs/articles/medium-skillopt-local-oss-csqa.md`: add "## LogiQA: testing the headroom hypothesis"
  with method (3 arms, 4 targets, 3 seeds), results table, plot, and the verdict vs +3pp bar.
- Create `docs/skillopt-logiqa-validation.md` (concise validation summary mirroring pilot-validation style).

## Related Code Files
- Modify: `docs/articles/medium-skillopt-local-oss-csqa.md`
- Create: `docs/skillopt-logiqa-validation.md`
- Embed/ref: Phase 05 plot + CSV

## Implementation Steps
1. Write the validation doc (setup, per-target table, CI verdict, what the best skill wrote, cost/wall-time).
2. Add the article section + update TL;DR + "What's coming next" status rows.
3. Include the repro delta: exact ollama tags + `prepare_mcqa_data.py --dataset logiqa` command.
4. If positive: state the flip ("loop works given headroom"); if null: honest pivot + next lever.

## Todo List
- [ ] docs/skillopt-logiqa-validation.md
- [ ] Article section + TL;DR + roadmap update
- [ ] Repro commands (tags, data-prep, run matrix)
- [ ] Final honest verdict line tied to the success bar

## Success Criteria
- Article + validation doc updated with real LogiQA numbers, CI, plot, repro steps; verdict matches Phase 05.

## Risk Assessment
- Overclaiming on n=3 → hedge with CI + std; lead with arm3−arm2, not raw arm3.

## Security Considerations
- No secrets/keys in published markdown.

## Next Steps
- Optional round 2 (out of scope): Kimi K2.6 / frontier model as alternate cloud OPTIMIZER.
