---
phase: 7
title: "Standalone Article"
status: pending
priority: P2
effort: "1d"
dependencies: [5, 6]
---

# Phase 7: Standalone Article

> **⚠️ SUPERSEDED by [Phase 12](./phase-12-combined-two-experiment-article.md).** The article is now ONE
> two-experiment post (MBPP public + business Text-to-SQL self-generated). This phase's MBPP material becomes
> Experiment A in Phase 12 — do NOT write a separate standalone article. Kept for traceability.

## Overview
Write the new standalone Medium article: the same SkillOpt loop that was flat on commonsense MC now produces a
real held-out lift on MBPP code-gen, with a deep per-step "behind the scenes" trace that ends in a win.

## Requirements
- Functional: a self-contained article citing the seed-42 (and 3-seed) MBPP numbers + the flat-MC contrast.
- Non-functional: depth is the point — show the mechanism step by step (the user's core ask). Honest verdict;
  unresolved questions at the end.

## Architecture (article structure)
- File: `docs/articles/medium-skillopt-mbpp-codegen-local.md` (standalone; links to but does not depend on the CSQA post).
- Sections:
  1. **Hook** — recap: MC went flat across 3 datasets × 2 targets × 2 optimizers; hypothesis from the diagnosis:
     procedure-bound tasks should lift. Test it on MBPP.
  2. **Why MBPP is the right family** — single generalizable procedure (output conventions, signature, edge cases)
     + deterministic verifier + procedural headroom; contrast with MC's per-item knowledge.
  3. **Setup** — qwen2.5:7b-instruct (Ollama, RTX 3080), deepseek-v4-pro optimizer, single-turn pass@1, subprocess
     sandbox; identical hyperparams to the MC v3 run (the controlled variable is ONLY the task).
  4. **The headroom probe** (Phase 3) — baseline pass@1 + the procedural-vs-capability split; why this de-risked the run.
  5. **Weak init + what we expect the optimizer to discover.**
  6. **★ Per-step deep dive (centerpiece)** — one real step: failed rollouts (wrong fn name / fenced prose /
     missed edge case) → optimizer reflection JSON → skill edit (before/after) → gate on 100 val → held-out effect.
     Then the full accept trajectory (monotonic dev climb).
  7. **Results** — baseline vs trained test @ n=200, Δ + SE, accepts, skill growth, DeepSeek cost, wall, GPU.
  8. **3-seed mean ± std** + the headline contrast table (MC −0.6 pp flat vs MBPP +X pp lift).
  9. **Why it worked here and not there** — ties back to the headroom thesis with the new positive data point.
  10. **Reproduce** — exact commands (prepare_mbpp_data, run_mbpp_pilot), artifacts map.
  11. **Honest verdict + open questions** (incl. stretch: HumanEval transfer; coder-model fallback if used).

## Related Code Files
- Create: `docs/articles/medium-skillopt-mbpp-codegen-local.md`.
- Read: this plan's `reports/mbpp-headroom-probe-report.md`, `reports/mbpp-3seed-results.md`, the run outputs
  (`history.json`, `best_skill.md`, `steps/step_XXXX/`), `docs/articles/medium-skillopt-local-oss-csqa.md` (for the contrast + voice).

## Implementation Steps
1. Pull the real numbers from the Phase 5/6 outputs (no invented figures).
2. Extract one clean per-step trace from `steps/step_XXXX/` (real reflection JSON + real skill diff).
3. Draft sections in order; keep the contrast table front-and-center.
4. Verbatim-cite `best_skill.md` excerpt (the procedure the optimizer actually wrote).
5. Optionally render visuals via `/ck:preview --diagram` for the loop schematic.

## Success Criteria
- [ ] Article uses only real measured numbers from the runs.
- [ ] Per-step trace shows failed rollout → reflection → edit → gate → held-out gain, end to end.
- [ ] Flat-MC vs lift-MBPP contrast table present; verdict honest; open questions listed.

## Risk Assessment
- **Temptation to overclaim** → report Δ with SE; if 3-seed mean is modest, frame as "real but bounded", not a
  miracle. Honesty is the article's brand (per the CSQA post).
- **If pilot/3-seed did NOT lift** → the article pivots to "even the paper's winning family is headroom-bound on a
  7B" — still publishable, but that is a different post; decide with user before writing.
