---
status: ready-to-run
priority: high
created: 2026-05-28
updated: 2026-05-29
supersedes: ARC-Challenge transfer direction (same plan, prior revision)
design_source: plans/reports/brainstorm-260529-2056-skillopt-siqa-fresh-train-design-report.md
context_required_for_next_session:
  - plans/reports/brainstorm-260529-2056-skillopt-siqa-fresh-train-design-report.md (approved design)
  - skillopt/envs/mcqa/skills/initial-weak.md (weak init under test)
  - configs/mcqa/local-pilot.yaml (baseline config to extend)
  - docs/articles/medium-skillopt-local-oss-csqa.md (article to update)
---

# SkillOpt Fresh-Train on SocialIQA (Local OSS Target)

## Why this plan exists

v3 CSQA run proved the loop works mechanically (3/10 accepts, val 0.86 → 0.90 monotonic) but
test moved −2.0 % (within 95 % CI). Leading cause: **100-item val too small → optimizer fits
val surface patterns** (a near-duplicate val item baked into the skill).

This plan tests the central claim on a **fresh, non-paper dataset**: **does SkillOpt, trained
from weak init on SocialIQA, produce a held-out TEST lift on a local Qwen2.5-7B** — once the
overfit is mitigated (3× larger val + multi-seed robustness)?

- **Win** → SkillOpt produces a portable test-set gain at the smallest scale anyone will try.
- **Flat** → still publishable: two datasets, same overfit ceiling, headroom is the real lever.

Feeds a new headline experiment into the Medium article (`docs/articles/medium-skillopt-local-oss-csqa.md`).

## Key decisions (user-confirmed in brainstorm)

- **Mode B fresh-train** (not transfer). Within-dataset test lift is the headline.
- **Dataset = SocialIQA** (`allenai/social_i_qa`, CC-BY-4.0, 3-option). User pick over LogiQA counter-proposal.
- **Overfit mitigation** = 100 train / **300 val** / 200 test + **3 seeds (42/43/44)**, report mean ± std test delta.
- **Reuse v3 hyperparams** (weak init, bs=20, 2 epochs, lr=4 cosine, temp=0, workers=8). No `skillopt/` core edits.
- **"It works" win** = mean test delta > **+3pp** with CI excluding 0.

## Honest risk

SocialIQA ~74 % baseline = same regime as CSQA (~76 %). Test may stay flat even with mitigations;
they make a *small real* lift detectable, they cannot manufacture headroom. Flat result → honest
2-dataset framing. (LogiQA/ReClor had more real headroom but user chose SocialIQA.)

## Phases

| # | Phase | Status | File |
|---|---|---|---|
| 1 | SocialIQA data prep | ✅ done | [phase-01-socialiqa-data-prep.md](phase-01-socialiqa-data-prep.md) |
| 2 | Config, launcher override, training runs (3 seeds) | ✅ done | [phase-02-config-launcher-training-runs.md](phase-02-config-launcher-training-runs.md) |
| 3 | Multi-seed analysis + article update | ✅ done — article updated with flat 3-seed result, config, + why-it-failed/why-paper-worked analysis | [phase-03-multiseed-analysis-article-update.md](phase-03-multiseed-analysis-article-update.md) |
| 4 | (Stretch) cross-dataset transfer eval | script written + compiles; eval not run (deprioritized — flat core result, article not updated) | [phase-04-stretch-cross-dataset-transfer-eval.md](phase-04-stretch-cross-dataset-transfer-eval.md) |

## Result (2026-05-30)

**FLAT — does not prove SkillOpt works on SocialIQA.** 3-seed mean test Δ = **+0.33pp** (std 0.29pp; per-seed +0.5 / 0.0 / +0.5pp). Each non-zero delta = exactly 1 test item on n=200 → noise. Win bar (mean >+3pp, CI excluding 0) not met.

| Seed | Base val | Best val | Base test | Trained test | Test Δ | Accepts | Wall s |
|------|---|---|---|---|---|---|---|
| 42 | 0.817 | 0.830 | 0.785 | 0.790 | +0.5pp | 2 | 1312 |
| 43 | 0.837 | 0.837 | 0.780 | 0.780 | 0.0pp | 0 (gate never fired) | 1482 |
| 44 | 0.763 | 0.787 | 0.805 | 0.810 | +0.5pp | 2 | 1248 |

**Cause:** headroom ceiling the plan flagged. Weak-init baselines were 0.76–0.84 val — too high to climb (seed 43 had no candidate beating its 0.837 baseline). Same regime as CSQA v3. **Article updated** (`docs/articles/medium-skillopt-local-oss-csqa.md`): added "Experiment 2" (SocialIQA setup + config + 3-seed table), a "Why it didn't work here — and why it worked in the paper" analysis (headroom / procedure-vs-knowledge / gate-as-noise-amplifier / scale), TL;DR update, and reconciled the scaffolded Experiment 3. *(Initial run honored an earlier "only if it proves SkillOpt works" gate; user subsequently asked to write the flat result honestly with analysis.)*

**Open question 1 RESOLVED:** HF `allenai/social_i_qa` (via parquet branch `refs/convert/parquet` — the loader script is unsupported by modern `datasets`) exposes only `train` (33,410) + `validation` (1,954) = 35,364 labeled rows; no labeled `test`. Pooled train+validation, matching the CSQA approach.

## Key dependencies

- Hardware/env unchanged: RTX 3080 + Ollama + Qwen2.5-7B-Instruct Q4_K_M + DeepSeek-chat. `.env.local-pilot` configured. `.venv` (uv-managed, `datasets` installed).
- Phase 2 depends on Phase 1 (splits exist). Phase 3 depends on Phase 2 (run summaries). Phase 4 independent (needs Phase 1 splits + v3 skill only).

## Success criteria

- **Min**: 1 run (seed 42) completes; `baseline_test` vs `test` recorded; article updated.
- **Target**: 3-seed mean test delta ± std; article SocialIQA section written + committed.
- **Stretch**: Phase 4 transfer matrix cells filled.

## Runtime / cost

~25–35 min GPU/run (300-val gate is the driver) + ~3–5¢ DeepSeek. 3 seeds ≈ 90 min + ~12¢. Stretch ~12 min + ~$0.

## Open questions

1. SocialIQA HF test-label visibility — design assumes HF test labels hidden → pool train+validation (~35k labeled). Researcher claimed a visible 7k test split. **Verify on first `load_dataset`** (Phase 1 self-check).
2. Execute training in-session vs user triggers GPU run later (Ollama warm-up, GPU availability).
