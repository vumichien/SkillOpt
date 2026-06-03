# SkillOpt — Two Serialized Posts Consolidated into One Final Medium Post

**Date:** 2026-06-03 · **Type:** editorial / docs consolidation · **Deliverable:** `docs/articles/medium-skillopt-when-prompt-training-works.md`

## Goal

User: "apply the finding ... keep only one final medium post" that tells a story for **both tech and non-tech**
audiences, following a fixed skeleton (Problem + aim audience + objective → technical explain → experiment on
local OSS + finding + proposal → conclusion → references → appendix), with **deep per-step** explanations.

## What happened

Two serialized articles existed: the CSQA companion (loop mechanics + commonsense-MC flat baseline) and the
combined MBPP/bizSQL/granite post (cross-linked, "read that first" framing). Merged them into **one standalone
post** under the user-approved "exact line where it works" framing. Both old files DELETED (git preserves
history); the consolidated post carries the whole arc as four experiments of one study:

1. Commonsense MC — flat (knowledge-bound; incl. the LogiQA step-anatomy deep-dive + the 2×3×2 optimizer grid).
2. MBPP code-gen — flat despite being procedural (heterogeneous; the 6-unrelated-failures vs 2+2 cluster contrast).
3. bizSQL Text-to-SQL — WIN +8.2pp 3-seed (homogeneous; the 5×`MONTH()` one-root-cause step; the probe-lied-twice story).
4. Swap the target model (granite-code 8B) — MBPP flat replicates (0.44 base), bizSQL +42.5pp replicates → lever
   is the task family, not the model.

Dual-audience handled with "In plain English" glosses + a manager/cheat-sheet analogy alongside the JSON traces.
Headlined decision rule: **"do your failures repeat?"** (homogeneous-procedural → train; heterogeneous/knowledge → skip).

## Decisions & lessons

- **Don't rewrite archived plan history.** 13 files referenced the old article names; only the LIVE navigational
  surfaces were repointed (active plan.md, phase-12/13 deliverable lines, journal, memory + MEMORY.md). The older
  completed plans (260528/260530/260531) + their reports correctly describe what existed when they ran — leaving
  them is honest, not a dangling-link bug.
- **Fact-check gate earned its keep again.** Code-reviewer verified 42/42 numbers against git-HEAD copies of the
  deleted sources + run `summary.json`. The two values fabricated in a prior session (MBPP qwen base 0.72→0.65;
  gap 28pp→21pp) were correct in the consolidated post. One cosmetic fix applied: "all 10 rewrites" header over a
  6-row abridged table → "all 10 rewrites were rejected — here are 6 of them".
- **Single-seed honesty preserved:** bizSQL granite +42.5pp direction is solid (z≈9.5) but magnitude is n=1 — the
  post and appendix both flag the 3-seed confirmation as the open next step.

## Artifacts

- Final post: `docs/articles/medium-skillopt-when-prompt-training-works.md`
- Deleted (in git history): `medium-skillopt-local-oss-csqa.md`, `medium-skillopt-mbpp-codegen-local.md`
- Reference updates: `plan.md` (Phase 12 row), `phase-12-*`, `phase-13-*`, prior granite journal, memory file + MEMORY.md
