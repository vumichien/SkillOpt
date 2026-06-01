# Phase 05 — Analysis: Mean Δ + 95% CI, Scale/Family Table

## Context Links
- Run artifacts: `outputs/logiqa_<target>_s<NN>/summary.json` (Phase 04), `outputs/logiqa-probe/*` (Phase 03)
- Prior analysis style: article's SocialIQA 3-seed table (mean ± std)

## Overview
- **Priority:** P1
- **Status:** pending
- Aggregate the 3-arm × 4-target × 3-seed results; compute the decisive **arm3 − arm2** delta with CI.

## Key Insights
- The headline statistic is **arm3 − arm2** per target (real SkillOpt effect), averaged over 3 seeds, with a
  95% CI. arm1 is reported as context (raw floor). Success = CI excludes 0 and mean ≥ +3pp on ≥1 target.
- Use a normal-approx CI on the per-seed delta (n=3): mean ± t(0.975,2)·s/√3 — small n, report std too and be honest about width. Optionally a paired bootstrap on item-level test results for a tighter, more defensible CI.

## Requirements
- Functional: one analysis script reads all `summary.json`, emits a table (target × arm × seed + mean/CI) and a
  plot (delta vs model scale, per family).
- Non-functional: script ≤120 LOC, kebab-case, writes CSV + PNG into the plan dir.

## Architecture
- `scripts/analyze_logiqa_results.py`: glob `outputs/logiqa_*_s*/summary.json` + probe summaries → DataFrame →
  per-target arm matrix → arm3−arm2 mean/std/CI → matplotlib scatter+errorbar (x=param count, color=family).

## Related Code Files
- Create: `scripts/analyze_logiqa_results.py`, `plans/260530-1953-skillopt-logiqa-headroom-validation/results-logiqa.csv`, `.../delta-vs-scale.png`

## Implementation Steps
1. Collect arm-1 (probe), arm-2 (probe), arm-3 (12 runs) test accuracies per (target,seed).
2. Compute per-target arm3−arm2 mean, std, 95% CI over 3 seeds.
3. Render table + plot; flag any target meeting the success bar (CI excludes 0, mean ≥ +3pp).
4. Write a short findings note (which targets passed; scale/family trend; honest null call if none pass).

## Todo List
- [ ] Aggregation script
- [ ] results-logiqa.csv (full matrix)
- [ ] delta-vs-scale.png
- [ ] Findings note (pass/fail vs success bar, trend)

## Success Criteria
- CSV + plot produced; explicit verdict per target against the +3pp/CI-excludes-0 bar.

## Risk Assessment
- n=3 CI is wide → also report item-level paired bootstrap for the best target to strengthen the claim.
- No target passes → honest "still null even with headroom" finding; pivot article framing (still publishable).

## Security Considerations
- None.

## Next Steps
- Feeds Phase 06 (numbers + plot into docs/article).
