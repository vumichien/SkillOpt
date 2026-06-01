# Brainstorm Summary — SkillOpt Headroom Validation (LogiQA × Cross-Family Small Models)

**Date:** 2026-05-30
**Status:** Design agreed, ready for `/ck:plan`
**Source article:** `docs/articles/medium-skillopt-local-oss-csqa.md`
**Supersedes:** earlier draft of this file that wrongly assumed the harness was gone.

---

## 1. Problem statement

All SkillOpt reproduction runs so far are **null/flat**: CSQA +0.7pp (3-seed, noise),
SocialIQA +0.33pp (3-seed), cross-dataset transfer = none. Root cause diagnosed =
**ceiling effect** — Qwen2.5-7B already 0.76–0.84 baseline on commonsense MC, no headroom.
Every run sat in the regime the paper predicts SkillOpt helps *least* (easy/saturated task,
capable target).

Goal: produce evidence SkillOpt **CAN** yield a real positive held-out gain, in a
deliberately chosen **headroom** regime (low-baseline + procedure-heavy task + weak models),
to share a credible "works when there's room" experiment.

---

## 2. Scout findings (CORRECTED — harness is fully present)

- **Harness exists and is battle-tested** (untracked/gitignored, so the git-only scout missed it):
  - `skillopt/` package incl. working `mcqa` env (`dataloader.py`, `evaluator.py`,
    `rollout.py`, `batch_runner.py`), dataset-agnostic MCQA schema.
  - `scripts/train.py` (full loop), `scripts/eval_skill_on_dataset.py` (zero-shot eval),
    `scripts/prepare_mcqa_data.py` (HF download → split dir).
  - configs `configs/mcqa/local-pilot.yaml` (the v3 config) + `local-pilot-siqa.yaml`.
  - launcher `scripts/run_local_pilot.ps1` (resume-aware, GPU sampler, env overrides:
    `SKILLOPT_CONFIG`, `SKILLOPT_SPLIT_DIR`, `SKILLOPT_OUT_ROOT`, `TARGET_DEPLOYMENT`).
  - prior `outputs/` (v3, siqa s42-44, transfer), data splits, weak/strong init skills.
- **Model swap is trivial:** target = `model.target` in config OR `TARGET_DEPLOYMENT` env;
  `skillopt/model/qwen_backend.py` reads it. Temp pinned 0 (`QWEN_CHAT_TEMPERATURE=0`).
- **New dataset ≈ 30 LOC:** `prepare_mcqa_data.py` has `_SUPPORTED`/`_LICENSES` dicts + per-dataset
  `_convert_*_row()` + a branch in `_build_pool`. Add one entry + one converter.
- **Hardware:** RTX 3080 **10 GB** (≈9.5 GB usable). Installed: `qwen2.5:7b-instruct-q4_K_M`
  (4.7 GB), `gemma4-26b-ctx32k` (17 GB, CPU-spill), `llama3.2` (3B), `deepseek-r1:1.5b`.

---

## 3. Requirements (locked with user)

| Item | Value |
|------|-------|
| Goal | **Prove it CAN work** (find ≥1 positive regime) |
| Dataset | **LogiQA** (`lucasmccabe/logiqa`) — 4-way logical-reasoning MC; low baseline + procedure-heavy |
| Targets | **Qwen3.5-2B, Qwen3.5-4B, Gemma4-E4B, Qwen2.5-7B (reuse anchor)** — all fit 10 GB except 7B reuse |
| Optimizer | DeepSeek-chat (unchanged; cloud, ~cents) |
| Baseline | **3 arms**: raw (weak-init) → generic-CoT (hand-written, fixed) → SkillOpt (optimized) |
| Seeds | 3 (42/43/44), as prior SocialIQA runs |
| Success | ≥ **+3pp** held-out (arm3 − arm2), 3-seed 95% CI excludes 0, on ≥1 (model) config |
| Scope | LogiQA only this round; Kimi K2.6 **dropped** (1T-param MoE, needs ~633 GB VRAM) |
| Constraints | RTX 3080 10 GB · Ollama local target · DeepSeek optimizer · Python 3.13 · reuse harness |
| Touchpoints | `scripts/prepare_mcqa_data.py` (+LogiQA), new `configs/mcqa/local-pilot-logiqa.yaml`, new generic-CoT skill md, `docs/skillopt-*` + article, new `plans/` |

---

## 4. Chosen solution

**LogiQA × {Qwen3.5-2B, Qwen3.5-4B, Gemma4-E4B, Qwen2.5-7B} × 3 arms × 3 seeds.**

**Why LogiQA:** baseline ~0.45–0.55 even at 7B (real headroom at every scale) AND
procedure-heavy logical reasoning — the regime where a learned skill (a reasoning playbook)
can genuinely help, vs knowledge-heavy tasks where it can't. Best P(positive).

**3 baseline arms** (isolates the real optimization effect):
1. Raw (weak init, no skill)
2. Generic-CoT skill (hand-written, fixed, dataset-agnostic) — eval only, no optimizer
3. SkillOpt (optimized skill) — full `train.py` loop
→ Real SkillOpt contribution = **arm3 − arm2** (a gain isn't just "added CoT").

**Cross-family bonus:** Gemma4 + Qwen3.5 (not just smaller Qwen) → tests "works beyond one
family." 7B reuse anchors against existing CSQA/SocialIQA nulls on the same loop.

**Headroom-probe gate (de-risk, cheap):** run arms 1+2 baselines (no optimizer) on all targets
FIRST via `eval_skill_on_dataset.py`. If even the 2B baseline > ~0.80 on LogiQA, escalate task
difficulty (ReClor / LogiQA-2.0) BEFORE spending the loop. Prevents a fourth wasted null.

**LogiQA converter (≈25 LOC):** map `context`+`query` → question, `options[0..3]` → choices A–D,
`correct_option` (int) → gold letter; reuse the script's deterministic seeded split.

---

## 5. Work outline (light — no rebuild)

1. Add LogiQA to `prepare_mcqa_data.py` (dict entry + `_convert_logiqa_row`).
2. `ollama pull` qwen3.5:2b, qwen3.5:4b, gemma4:e4b (verify exact tags via `ollama show`).
3. Generate 3 seeded LogiQA splits (100 train / 300 val / 200 test, matching SocialIQA setup).
4. Write generic-CoT skill md (arm 2).
5. Headroom probe: arms 1+2 baselines × 4 targets (eval-only).
6. If headroom OK: SkillOpt loop (arm 3) × 4 targets × 3 seeds (`TARGET_DEPLOYMENT` override).
7. Aggregate per-target mean Δ + 95% CI; produce scale/family table + plot.
8. Update `docs/skillopt-pilot-validation`-style doc + Medium article with real numbers.

---

## 6. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Newer small models stronger → less headroom | LogiQA baseline low enough; probe gate + smallest model (2B) as best shot |
| LogiQA still near-ceiling for some target | probe gate escalates to ReClor/LogiQA-2.0 before loop |
| Gain confounded by "just CoT" | 3-arm baseline, report arm3 − arm2 |
| 9B/26B CPU-spill slowness | excluded; all chosen targets fit 10 GB on GPU |
| Honest result may still be null | pre-commit to report either way; null-in-headroom is itself a finding |
| Exact ollama tags differ | verify with `ollama show` / pull at impl time |

---

## 7. Success metrics

- Primary: ≥+3pp (arm3 − arm2), 3-seed 95% CI excludes 0, on ≥1 target.
- Secondary: gain larger for smaller model and/or holds across families → validates thesis.
- Deliverable: updated validation doc + article with real numbers + plot.

---

## 8. Next step

`/ck:plan` (default) from this report → phased plan: add LogiQA converter → pull models →
splits → generic-CoT skill → headroom probe → SkillOpt loop → CI analysis → docs/article.
(Default plan, not --tdd: this adds a converter + runs experiments; it does not refactor
critical existing logic with test coverage to preserve.)

---

## 9. Unresolved questions

- Exact Ollama tags/quant for qwen3.5:2b / qwen3.5:4b / gemma4:e4b (verify at pull).
- LogiQA pooling: reuse script's train+validation pool (≈8k rows, ample) vs also include
  labeled test — default reuse train+validation for parity; confirm in plan.
- Iteration count: keep v3's 2 epochs → 10 candidate edits (default) vs raise — default keep.
- Round 2 (out of scope now): Kimi K2.6 / frontier model as alternate cloud OPTIMIZER.
