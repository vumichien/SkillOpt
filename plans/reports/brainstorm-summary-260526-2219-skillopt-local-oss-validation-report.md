# Brainstorm Summary — Validate SkillOpt on a Local OSS Model (RTX 3080)

**Date:** 2026-05-26
**Skill:** /ck:brainstorm
**Status:** Approved — ready for /ck:plan
**Repo:** microsoft/SkillOpt (this working dir)

---

## Problem Statement

Validate that SkillOpt's "train-the-skill-not-the-weights" loop yields a *measurable* quality gain for a small open-source target model runnable on an RTX 3080 (10–12GB). Then document mechanism + real results in a Medium article.

SkillOpt = neural-net-style optimization of a **markdown skill doc** (no weight updates). Loop (`skillopt/engine/trainer.py`): `rollout → reflect (textual gradients) → aggregate → select → update (apply edits) → evaluate (validation gate)`, with epochs, batch_size, learning_rate (= max edits/step), LR schedulers (cosine/linear), accept/reject gating.

---

## Codebase Findings (scout)

- **Two model roles:** `optimizer` (writes skill edits; backend restricted to `openai_chat`/`claude_chat`) and `target` (runs task with skill; supports `qwen_chat` = any local OpenAI-compatible/vLLM endpoint). Ref `skillopt/model/backend_config.py`, `qwen_backend.py`.
- **Local plug-in point:** `QWEN_CHAT_BASE_URL` (default `http://localhost:8000/v1`), `TARGET_DEPLOYMENT`, `enable_thinking=false` default (fine for Qwen2.5). Ref `qwen_backend.py`.
- **Optimizer client:** `azure_openai.py` imports generic `OpenAI` client too → DeepSeek base_url override *likely* supported (VERIFY).
- **SearchQA = simplest benchmark:** single-turn, self-contained context (no live search), EM/F1/sub_em scoring, target emits `<answer>...</answer>`. Context truncated to **6000 chars** (`rollout.py`) → **8k ctx enough, no 32k needed**.
- **Data format:** split dir `train/val/test`, each JSON array of `{id, question, context, answers[]}`. Default `2:1:7`, train_size 400, batch 40, minibatch 8.
- **Resume-aware:** re-running same cmd resumes; per-step artifacts under `outputs/<run>/`.

---

## Decisions (user-confirmed)

| Decision | Choice | Rationale |
|---|---|---|
| Model topology | Cloud optimizer + local target | Matches architecture; clean test of "does skill-training help a small OSS model" |
| Benchmark | SearchQA | Simplest, text-only, self-contained context, standard EM/F1 |
| Serving stack | Ollama (Windows) | Native Win, OpenAI-compatible `/v1`, easy Q4 GGUF + GPU/CPU offload |
| Target model | Qwen2.5-7B-Instruct Q4 | ~5–6GB Q4, fast rollouts, repo's Qwen lineage |
| Optimizer | DeepSeek-chat | OpenAI-compatible, cheap, strong reasoning → repeatable runs for <$2 |
| Run scale | Pilot first | De-risk mechanism cheaply; scale to full run later if promising |
| Data source | HotpotQA subset | Cleanest map to `{id,question,context,answers}`; gold passages → `[DOC]` |
| Pilot slow-update/meta-skill | Disabled | Isolate core loop, cut optimizer calls; re-enable for full run |

---

## Recommended Solution

### Role mapping
| Role | Plays | Backend | Runs on |
|---|---|---|---|
| Optimizer | DeepSeek-chat | `openai_chat` + base_url override | Cloud (cheap) |
| Target | Qwen2.5-7B-Instruct Q4 | `qwen_chat` | Local Ollama `:11434/v1` |

### Pilot config (new `configs/searchqa/local-pilot.yaml`, inherits default)
- Data: ~120 HotpotQA items → `train=48 / val=24 / test=48`.
- `train_size 48`, `batch_size 16`, `num_epochs 2` (~3 steps/epoch, ~6 steps total).
- `minibatch_size 8`, `learning_rate 4 / min 2`, `lr_scheduler cosine`.
- `workers 4` (Ollama serializes on one GPU; high worker counts time out).
- `use_slow_update: false`, `use_meta_skill: false`.
- 8k ctx sufficient (context pre-truncated to 6000 chars).

### Success bar
1. Loop completes end-to-end on local target without crashes (mechanism works).
2. `best_skill.md` test F1/EM beats `initial.md` skill by any positive margin.
3. Evidence from `history.json` (per-step curve), `skills/skill_vXXXX.md` (diffs), token tracker (cost).

---

## Deliverables (4, all confirmed)

1. **`scripts/prepare_searchqa_local.py`** — download HotpotQA subset → convert → `data/searchqa_local_split/{train,val,test}/items.json`.
2. **`configs/searchqa/local-pilot.yaml` + `.env` template + `run_local_pilot.{ps1,sh}`** — one-command launch (Ollama up + DeepSeek env + `scripts/train.py`).
3. **Analysis** — user runs on 3080; analyze `outputs/`: accuracy curve, skill diffs, token cost → narrative.
4. **Medium post outline + draft** — analogy (epochs/LR/gradients), optimizer-vs-target architecture, real before/after skill diff, results, cost, repro advice + pitfalls.

---

## Cost / Time

- Optimizer (DeepSeek): ~100–200 pilot calls → typically **< $2**.
- Target (local, free): few hundred Qwen2.5-7B single-turn calls → **~30–90 min** serialized on 3080.

---

## Risks → Mitigations

1. **DeepSeek base_url plumbing for `openai_chat`** — *VERIFY FIRST* (likely `OPENAI_BASE_URL` / config field; trivial shim if absent). Hard blocker if wrong.
2. **Small-model `<answer>` compliance** — EM sparse if Qwen ignores tag format; F1/sub_em soften; format-teaching is part of what skill learns. Watch EM-based gate signal.
3. **Ollama throughput** — keep `workers` low; expect serialized latency.
4. **HotpotQA field/license drift** — confirm mapping during prep.

---

## Validation Criteria

- `data/searchqa_local_split/` validates against SearchQA loader (`{id,question,context,answers}`).
- Training run produces `best_skill.md` + `history.json` with test metrics.
- best vs initial skill: positive test-F1 delta.
- Token summary captured for cost reporting.

---

## Next Steps

1. `/ck:plan` — phase the work: (P0) verify DeepSeek optimizer wiring; (P1) data prep script; (P2) config + launch scripts; (P3) run + analysis; (P4) Medium draft.

---

## Unresolved Questions

1. DeepSeek optimizer base_url mechanism — exact env var / config field unconfirmed (P0 verify).
2. HotpotQA variant (distractor vs fullwiki) — pick during prep; distractor gives bounded gold context.
3. Whether to also run the larger ~26B target for a model-size-scaling story in the post (deferred; pilot uses 7B only).
