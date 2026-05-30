# Brainstorm Summary: SkillOpt Fresh-Train on SocialIQA

**Date:** 2026-05-29 | **Mode:** brainstorm → design approved | **Supersedes:** ARC direction in `plans/260528-1847-skillopt-cross-dataset-validation/plan.md`

---

## Problem statement

Prove SkillOpt works on a dataset NOT in the paper (arXiv 2605.23904). v3 CSQA run showed loop mechanically works (3/10 accepts, val 0.86→0.90 monotonic) but test −2.0pp (within CI) — leading cause: 100-val too small, optimizer fit val surface patterns ("lazy watching TV" near-dup baked into skill). User goal: **create a new skill/task on a new dataset and use SkillOpt to train it up, showing a held-out TEST lift** for the Medium article (`docs/articles/medium-skillopt-local-oss-csqa.md`).

## Decisions captured (user-confirmed)

1. **Success bar** = fresh-train a new skill on a new dataset (Mode B), within-dataset test lift is the headline (transfer secondary).
2. **Overfit mitigation** = bigger val (300) + multi-seed.
3. **Dataset** = **SocialIQA** (user pick, overriding researcher's same recommendation AND brainstorm's LogiQA counter-proposal).

## Dataset research (see `researcher-260529-2131-mcqa-dataset-headroom-for-qwen7b-report.md`)

Ranked: SocialIQA (74% baseline), TruthfulQA MC1 (~45-50%, too small ~817 rows), Winogrande. Brainstorm flagged researcher's "18-24pp headroom" as misleading (measured to 100%; realistic SocialIQA ceiling ~80-83% → ~6-10pp catchable). LogiQA/ReClor proposed as higher-real-headroom alternatives. **User chose SocialIQA anyway** (cleanest data/license, trusts mitigations). Decision respected.

## Approved design

- **Dataset:** SocialIQA `allenai/social_i_qa`, CC-BY-4.0, 3-option MCQA (`context`+`question`+`answerA/B/C`, `label∈{1,2,3}`). Pool train+validation (~35k labeled; HF test labels hidden). Mapper: `question=context+"\n"+question`; choices A/B/C; gold=label→letter.
- **Splits:** 100 train / 300 val / 200 test (3× val vs v3).
- **Recipe:** reuse v3 — weak 3-line init (`skillopt/envs/mcqa/skills/initial-weak.md`), bs=20, 2 epochs (10 candidate edits), lr=4 cosine, temp=0 eval, strict-better gate, workers=8. `eval_test=true` → train.py reports baseline_test + trained_test.
- **Multi-seed (KISS):** 3 full runs seeds 42/43/44 (reshuffle data draw), report mean±std test delta. NOT gate-internal seed voting (temp=0 makes within-seed eval deterministic → moot + invasive). Run seed 42 first per user's "approve as-is" (note: user picked "Approve as-is" not "single-seed first", so all 3 seeds in scope; seed 42 still naturally lands first).
- **Stretch:** cross-dataset cells — v3 CSQA-skill → SocialIQA test; new SocialIQA-skill → CSQA test. Fills article transfer matrix. ~12 min, ~$0.

## Code changes (no `skillopt/` core edits)

| File | Change | LOC |
|---|---|---|
| `scripts/prepare_mcqa_data.py` | dispatch `_convert_row` per-dataset; add `social_i_qa` converter + HF id; extend `_SUPPORTED` | +~40 |
| `configs/mcqa/local-pilot-siqa.yaml` | `_base_: local-pilot.yaml`, `env.split_dir: data/mcqa_siqa_split` | ~5 |
| `scripts/run_local_pilot.ps1` | accept `$env:SKILLOPT_CONFIG` override (line 75 hardcodes config) | 1 |
| `scripts/eval_skill_on_dataset.py` (stretch) | transfer eval via `run_batch` (`skillopt/envs/mcqa/batch_runner.py`) | ~80 |
| `docs/articles/medium-skillopt-local-oss-csqa.md` | add SocialIQA experiment section + fill matrix cells | edit |

## Runtime / cost

~25-35 min GPU/run (300-val gate is driver) + ~3-5¢ DeepSeek. 3 seeds ≈ 90 min + ~12¢. Stretch ~12 min + ~$0.

## Success criteria

- Min: 1 run done, baseline_test vs trained_test recorded, article updated.
- Target: 3-seed mean test delta ± std + article section.
- "It works" win: mean test delta > +3pp, CI excludes 0.

## Risks

- SocialIQA ~74% = CSQA regime → test may stay flat. Mitigation: 300 val + 3 seeds make small real lift detectable; if flat → honest 2-dataset framing (overfit ceiling real, headroom is lever). Still publishable.
- HF label-format surprise → caught by `--self-check` (gold ∈ labels).
- 300-val gate ~3× slower → acceptable at workers=8.
- SocialIQA 3-option (random 33% vs CSQA 20%) — weak baseline ~70%, fine.

## Unresolved questions

1. SocialIQA HF schema/test-label visibility — confirm on first `load_dataset` (design assumes hidden test, pool train+val; researcher claimed visible 7k test — verify).
2. Run experiment this session vs user triggers GPU run later — user chose "Update existing plan + /ck:plan"; whether to execute training in-session still open (Ollama/GPU availability).
