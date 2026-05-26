---
title: "Validate SkillOpt on Local OSS Model (Qwen2.5-7B + DeepSeek, CommonsenseQA)"
description: ""
status: in_progress
priority: P2
branch: "main"
tags: []
blockedBy: []
blocks: []
created: "2026-05-26T13:49:45.425Z"
createdBy: "ck:plan"
source: skill
---

# Validate SkillOpt on Local OSS Model (Qwen2.5-7B + DeepSeek, CommonsenseQA)

## Overview

Test whether Microsoft SkillOpt's skill-training loop (rollout→reflect→aggregate→select→update→gate; no weight updates) **generalizes to a task the paper did NOT cover**, on a **local OSS target** (Qwen2.5-7B-Instruct Q4 via Ollama, RTX 3080) driven by a **cheap cloud optimizer** (DeepSeek). Task: **multiple-choice reasoning (CommonsenseQA)** via a new dataset-agnostic `mcqa` env. Pilot-first. Then a Medium article.

**Why not SearchQA:** it's a SkillOpt paper benchmark — reproducing it proves nothing about generalization. CommonsenseQA (MIT, MC commonsense) is outside the paper's domains (embodied / open-QA / math / vision-doc / office-code) → a real generalization test. Exact-match letter scoring also gives the accept/reject gate a cleaner signal than fuzzy F1.

**Source brainstorm:** `plans/reports/brainstorm-summary-260526-2219-skillopt-local-oss-validation-report.md`

**Verified codebase facts:**
- Two roles: `optimizer` (writes skill edits) + `target` (runs task). Dispatch `skillopt/model/__init__.py`.
- Target `qwen_chat` builds generic `OpenAI(base_url=QWEN_CHAT_BASE_URL)` → Ollama plugs in (`azure_openai.py:320-334`).
- **Optimizer `openai_chat` is Azure-only** (`_make_client("optimizer")`→`AzureOpenAI`, `azure_openai.py:281-309`) → DeepSeek needs a patch (Phase 1).
- **Reflection is task-agnostic:** SearchQA `reflect()` delegates to generic `gradient.reflect.run_minibatch_reflect` reading `{id,hard,soft,fail_reason,response}` rows → a new env reuses the whole gradient engine (`envs/searchqa/adapter.py:93-121`).
- Adding an env = clone SearchQA dir, swap evaluator + rollout prompt + initial skill + register in `scripts/train.py:_register_builtins`. Env template at `envs/_template/`.
- Data format: split dir `train/val/test`, each JSON array `{id, ...}`. mcqa item: `{id, question, choices:[{label,text}], answers:[letter]}` (shape we define; rollout/evaluator must agree).
- CommonsenseQA (`tau/commonsense_qa`, MIT): `{id, question, choices{label[],text[]}, answerKey}`, 5 choices A–E. **Test split has no `answerKey`** → carve our train/val/test from the labeled train+validation splits.

**Success bar:** loop runs end-to-end on local target; `best_skill.md` test accuracy (letter EM) beats `initial.md`; optimizer cost <$2; ~30–90 min local wall-clock.

**Constraints:** modify code in CWD only (never `~/.claude/skills`); Python = snake_case; config inherits via `_base_`; keep `workers` low (Ollama serializes on one GPU); no secrets in git.

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [DeepSeek Optimizer Support](./phase-01-deepseek-optimizer-support.md) | Complete (live DeepSeek smoke pending user key) |
| 2 | [MCQA Env Implementation](./phase-02-mcqa-env-implementation.md) | Complete |
| 3 | [CommonsenseQA Data Prep](./phase-03-commonsenseqa-data-prep.md) | Complete (48/24/48 written) |
| 4 | [Pilot Config and Launch](./phase-04-pilot-config-and-launch.md) | Complete (config resolves end-to-end) |
| 5 | [Run and Analysis](./phase-05-run-and-analysis.md) | Blocked — needs user run on RTX 3080 (Ollama + DeepSeek key) |
| 6 | [Medium Article](./phase-06-medium-article.md) | Blocked by Phase 5 (needs real numbers) |

## Dependencies

<!-- Cross-plan dependencies -->
