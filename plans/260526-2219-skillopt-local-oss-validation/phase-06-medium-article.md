---
phase: 6
title: "Medium Article"
status: blocked-by-phase-5
priority: P3
effort: "3-4h"
dependencies: [5]
---

# Phase 6: Medium Article

## Overview
Write an in-depth Medium post: how SkillOpt works (NN analogy + optimizer/target architecture), the real CommonsenseQA experiment (a task the paper didn't cover), before/after skill diffs + results, and reproduction advice.

## Requirements
- Functional: standalone markdown draft with diagrams/code blocks, real numbers from Phase 5, repro section.
- Non-functional: accurate to the codebase (no hand-waving the mechanism); honest about pilot limits + cost; readable for an ML-literate, SkillOpt-new audience.

## Architecture (article outline)
1. **Hook** — "I trained a *prompt* like a neural network on my gaming GPU — on a task the paper never tested."
2. **Mental model** — map SkillOpt → NN training: epochs, batch_size, learning_rate (= max edits/step), cosine LR, validation gate (accept/reject), "textual gradients" = reflections on failed rollouts.
3. **Architecture** — two roles: **optimizer** (writes skill edits) vs **target** (runs task). Why a cheap cloud optimizer + local OSS target is the interesting combo. Diagram the 6-stage loop.
4. **Why a NEW task matters** — reproducing a paper benchmark (SearchQA) proves nothing; the real test is generalization → CommonsenseQA (multiple-choice commonsense), outside the paper's domains. Mention building a 60-line `mcqa` env (the method is task-pluggable).
5. **Setup** — RTX 3080 + Ollama (Qwen2.5-7B Q4) target, DeepSeek optimizer. Include the **optimizer patch gotcha** (Azure-only → generic OpenAI base_url) as a real-world lesson.
6. **Experiment** — CSQA→mcqa data prep, pilot config (the numbers), what one training step does (rollout → reflect → edit → gate).
7. **Results** — initial vs trained test accuracy, the curve, **a real before/after `best_skill.md` diff** (what reasoning rules the optimizer learned — the payoff). Token cost + wall-clock.
8. **Advice** — pitfalls (optimizer must be OpenAI-compatible + patched, DeepSeek param quirks, keep workers low for Ollama, robust answer extraction, exact-match gate signal, start with a pilot) + how to adapt to your own task (clone the env, swap evaluator).
9. **Closing** — when skill-training beats fine-tuning/prompt-eng; honest limits of an n=120 pilot.

## Related Code Files
- Read (inputs): Phase 5 analysis report, `best_skill.md` + `initial.md` (the diff), `history.json` (curve), token summary, brainstorm summary report.
- Create: `plans/reports/medium-draft-skillopt-mcqa-csqa-experiment.md` (draft under plans/ per repo rule; user copies to Medium).
- Optional: mermaid loop diagram via `/ck:mermaidjs-v11`.

## Implementation Steps
1. Read Phase 5 analysis + skill diff + curve; pick the 2-3 sharpest "what the skill learned" examples.
2. Draft per outline; embed real numbers + the skill diff as code blocks.
3. Add loop + optimizer/target diagrams.
4. Write repro section (Phase 3-4 commands, DeepSeek patch note, env setup, cost estimate).
5. Self-review vs code: every method claim traceable to `trainer.py`/`gradient/`/`optimizer/`; flag any claim not backed by the run.

## Success Criteria
- [ ] Covers mechanism + architecture + real experiment + repro advice.
- [ ] Contains a real before/after skill diff + actual pilot metrics (or honest null result + why).
- [ ] Repro section runnable by a reader with a 3080 + DeepSeek key.
- [ ] No claims unsupported by the codebase or the run.

## Risk Assessment
- **Over-claiming from a small pilot**: explicitly frame as pilot (n=120, 2 epochs); don't generalize to "SkillOpt always helps".
- **Mechanism inaccuracy**: cross-check every claim against the modules before publishing.
- **Secret leakage in snippets**: placeholders only.

## Next Steps
Publish (user). Optional follow-up (out of scope): full-scale run; add ARC-Challenge via same env for a 2-task story; larger target model for a scaling angle.
