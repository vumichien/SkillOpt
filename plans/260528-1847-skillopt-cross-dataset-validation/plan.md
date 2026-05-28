---
status: ready-to-run
priority: high
created: 2026-05-28
context_required_for_next_session:
  - outputs/mcqa_local_pilot_v3/best_skill.md (the artifact under test)
  - docs/articles/medium-skillopt-local-oss-csqa.md (article to update)
  - configs/mcqa/local-pilot.yaml (working baseline config)
---

# Cross-Dataset Validation of SkillOpt on Local OSS Target

## Why this plan exists

Run v3 (`outputs/mcqa_local_pilot_v3/`) showed SkillOpt's optimization loop works mechanically:
- 3 accepts in 10 candidate edits
- Val acc 0.86 → 0.90 (monotonic climb)
- Skill grew 24× into a substantive CSQA prompting guide

But test acc moved −2.0 % (within 95 % CI of zero). The leading hypothesis: **the optimizer fits val-specific surface patterns**, including what looks like a near-duplicate of a val item baked into the skill ("lazy watching TV → bored").

This plan settles the question with a clean experiment: **does the v3-trained CSQA skill transfer to other MCQA datasets the optimizer never saw?**

- **If yes** → SkillOpt learned transferable heuristics. The val/test CSQA gap was binomial noise on n=200 test.
- **If no** → SkillOpt learned CSQA-specific patterns. Need to upsize val (or hold out part of val from reflect) for cross-domain results.

Either outcome is publishable. The Medium article ([`docs/articles/medium-skillopt-local-oss-csqa.md`](../../docs/articles/medium-skillopt-local-oss-csqa.md)) explicitly promises this follow-up.

---

## What to test (3 datasets, ordered by effort)

| Dataset | HF ID | Size | Why pick it | Difficulty signal |
|---|---|---|---|---|
| **ARC-Challenge** | `allenai/ai2_arc` config `ARC-Challenge` | ~2.6k labeled | Harder grade-school science MC, 4 options, GPT-4 zero-shot ~95 % | Qwen2.5-7B baseline likely 70-80 % |
| **OpenBookQA** | `allenai/openbookqa` config `main` | ~5k labeled | Elementary science with retrieval-style facts, 4 options | Qwen2.5-7B baseline likely 75-85 % |
| **BoolQ** (stretch) | `google/boolq` | ~16k labeled | Yes/No questions — different schema, tests skill robustness | Qwen2.5-7B baseline likely 80-85 % |

ARC-Challenge first (cleanest comparison with CSQA: both 5- or 4-way MC, both common-sense style).

---

## Two evaluation modes

### Mode A: zero-shot transfer (the main experiment)

Apply the **v3 trained CSQA skill** to ARC-Challenge **without any further SkillOpt training**.

```
baseline_acc = run weak init on ARC-Challenge test
transfer_acc = run v3 best_skill.md on ARC-Challenge test
```

- **If `transfer_acc > baseline_acc`** by more than the 95 % CI → the skill carries.
- **If indistinguishable** → CSQA-specific. Confirms overfit hypothesis.

This needs **no training run** — just two eval passes. ~15 minutes of GPU time. **Run this first.**

### Mode B: full SkillOpt loop on ARC-Challenge

Train a new skill from weak init on ARC-Challenge (same hyperparams as v3). Compare:
- ARC weak baseline vs ARC-trained skill (within-dataset improvement)
- ARC-trained skill vs v3 CSQA-trained skill (cross-dataset)

This produces the v4 datapoint that completes the matrix.

---

## Concrete tasks (next session checklist)

### Task 1: extend `scripts/prepare_mcqa_data.py` to handle ARC-Challenge

The script already has a `--dataset` flag with `_SUPPORTED` set. Check `scripts/prepare_mcqa_data.py:118` for the existing structure.

**Acceptance criteria:**
- Add `arc_challenge` to `_SUPPORTED`
- Add an HF-row → mcqa-row mapper (note: ARC labels are sometimes "1/2/3/4" or "A/B/C/D" — normalize to letters)
- `python scripts/prepare_mcqa_data.py --dataset arc_challenge --n-train 100 --n-val 100 --n-test 200 --out-dir data/mcqa_arc_split --self-check` passes

**Heads-up:** ARC has its own train/val/test splits with labeled test (unlike CSQA where test labels are hidden). Use all three labeled splits when sampling 400 items.

### Task 2: write `scripts/eval_skill_on_dataset.py` (transfer eval, no training)

A small script that:
1. Loads a skill markdown file (path arg)
2. Loads a split (default `test`) of a dataset
3. Runs the mcqa rollout on each item with that skill
4. Prints acc + per-item results

This is essentially `scripts/smoke_test_pipeline.py` parameterized.

```bash
.venv\Scripts\python.exe scripts/eval_skill_on_dataset.py \
    --skill outputs/mcqa_local_pilot_v3/best_skill.md \
    --split-dir data/mcqa_arc_split \
    --split test \
    --out-dir outputs/transfer_v3_to_arc
```

Output: `outputs/transfer_v3_to_arc/{results.jsonl, summary.json}`.

**~30 LOC. Should use `run_batch` from `skillopt/envs/mcqa/batch_runner.py:35` directly.**

### Task 3: run the transfer experiment (Mode A)

```powershell
# 1. Generate ARC splits
.venv\Scripts\python.exe scripts\prepare_mcqa_data.py `
    --dataset arc_challenge --n-train 100 --n-val 100 --n-test 200 `
    --out-dir data/mcqa_arc_split

# 2. Eval weak baseline on ARC test
.venv\Scripts\python.exe scripts\eval_skill_on_dataset.py `
    --skill skillopt/envs/mcqa/skills/initial-weak.md `
    --split-dir data/mcqa_arc_split --split test `
    --out-dir outputs/transfer_weak_to_arc

# 3. Eval v3 CSQA-trained skill on ARC test
.venv\Scripts\python.exe scripts\eval_skill_on_dataset.py `
    --skill outputs/mcqa_local_pilot_v3/best_skill.md `
    --split-dir data/mcqa_arc_split --split test `
    --out-dir outputs/transfer_v3_to_arc
```

Compare `summary.json` from both. Record the delta.

**Expected runtime**: 2 × ~6 min = ~12 min total (200 test items × ~2s/item).

### Task 4: (if transfer is null) run full SkillOpt loop on ARC (Mode B)

Only do this if Task 3 shows no transfer. New config:

```yaml
# configs/mcqa/local-pilot-arc.yaml
_base_: local-pilot.yaml
env:
  split_dir: data/mcqa_arc_split
```

Run:
```powershell
$env:SKILLOPT_OUT_ROOT = "outputs/mcqa_arc_pilot"
.\scripts\run_local_pilot.ps1 --config configs/mcqa/local-pilot-arc.yaml
```

(Launcher currently hardcodes the config path — Task 4 may need a small launcher edit to accept `--config`.)

**Expected runtime**: ~12 min (same as v3).

### Task 5: update the Medium article

The article (`docs/articles/medium-skillopt-local-oss-csqa.md`) has a placeholder section near the end:

> *"What's next (an update is coming)"*

Replace that section with:

#### If transfer worked (`transfer_acc > weak_baseline_acc + 3%`):
> **Update [date]:** Tested the v3 CSQA-trained skill on ARC-Challenge (200 test items, no further training). Weak baseline: X %. v3 skill: Y % (+Z pp). The heuristics SkillOpt wrote — keyword matching, step-by-step reasoning, causal/functional core — generalize beyond the dataset they were tuned on. The val/test gap in the CSQA run was statistical noise on n=200 test, not overfit.

#### If transfer was null (within CI):
> **Update [date]:** Tested the v3 skill on ARC-Challenge (200 items) — no measurable lift over weak baseline (delta < binomial CI). Confirms the CSQA val/test gap was overfit. Ran a fresh SkillOpt loop on ARC (Mode B): val 0.X → 0.Y, test +/- Z pp. **Takeaway:** SkillOpt's loop works per-dataset but the skills it writes don't yet transfer. The next step is enlarging the val split to dilute val-specific learning, or holding part of val out of reflect's reach.

Add a comparison table:

| Skill | CSQA test (200) | ARC-Challenge test (200) |
|---|---|---|
| Weak init | 76 % (baseline) | ?? |
| v3 (CSQA-trained) | 74 % | ?? |
| v4 (ARC-trained, if Mode B) | — | ?? |

Then commit with `feat: extend SkillOpt validation to ARC-Challenge` (no `chore`/`docs` per project rules since this is real content delivery).

---

## File ownership (next session)

| New file | Purpose | Estimated LOC |
|---|---|---|
| `scripts/prepare_mcqa_data.py` (extend) | Add ARC dataset support | +30 LOC |
| `scripts/eval_skill_on_dataset.py` (new) | Transfer eval script | ~80 LOC |
| `configs/mcqa/local-pilot-arc.yaml` (new) | ARC training config | ~5 LOC |
| `docs/articles/medium-skillopt-local-oss-csqa.md` (edit) | Update with transfer results | replace 1 section |
| `outputs/transfer_v3_to_arc/` (new) | Result artifacts | data, not LOC |
| `outputs/transfer_weak_to_arc/` (new) | Baseline artifacts | data, not LOC |

No edits to `skillopt/` core code expected. If they are, file an issue first.

---

## Context the next session needs (paste into prompt)

```
You are continuing the SkillOpt local-OSS validation work. Background:

- v3 pilot complete: SkillOpt accepted 3/10 candidate edits on CSQA, val
  0.86 → 0.90, but test moved -2.0 % (within 95% CI). Trained skill at
  outputs/mcqa_local_pilot_v3/best_skill.md, 3.6 KB.
- Medium article drafted at docs/articles/medium-skillopt-local-oss-csqa.md
  with an explicit "update coming" section that needs cross-dataset data.

Current task (this plan): plans/260528-1847-skillopt-cross-dataset-validation/plan.md

Hardware/env unchanged: RTX 3080 + Ollama + Qwen2.5-7B-Instruct Q4_K_M
+ DeepSeek-chat. .env.local-pilot is already configured. Working venv at
.venv (uv-managed, datasets package already installed).

Start with Task 3 (Mode A transfer eval) — it's the cheapest experiment
that settles the central question. Only proceed to Task 4 (Mode B full
training on ARC) if transfer is null.
```

---

## Success criteria

- **Minimum**: Task 3 completes with a `summary.json` from both eval runs, recorded in the article update.
- **Target**: Tasks 1-3 + article updated and committed within 1 hour of session start.
- **Stretch**: Task 4 (Mode B full ARC training) for the complete matrix.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| ARC HF dataset has different label format (1-4 vs A-D) | Normalize in `_convert_row` mapper; add to self-check |
| Qwen2.5-7B baseline on ARC too high (>90 %) → no headroom | If so, fall back to ARC-Challenge HARD subset or BoolQ |
| `eval_skill_on_dataset.py` becomes a re-implementation of trainer's eval path | Use `run_batch` directly from `skillopt/envs/mcqa/batch_runner.py:35`; don't re-invent |
| Article update gets stale if transfer experiment takes weeks | Time-box: if Task 3 isn't done in 30 min, ship the article as-is with caveat removed |

---

## Open questions (for the next session)

1. **Multi-seed gate.** Should we re-run v3 with 3-seed val evaluation (vote across 3 deterministic runs with different shuffles) to check if the v3 +4 % val was robust to subsampling? Cheap (~30 min) and adds rigor to the article.
2. **Hold part of val out of reflect.** Currently the optimizer can in principle see val items via failure analysis hooks. Worth auditing `skillopt/gradient/reflect.py` to confirm train-only fed to reflect.
3. **Larger optimizer model.** Would `deepseek-reasoner` (~10× cost, ~$0.10 per run) propose more transferable heuristics? Worth one run as a sensitivity check.
4. **Different target.** Run the same v3 trained skill against Qwen2.5-14B or 32B (if VRAM allows on the 3080 with offload) — does a smarter target benefit *more* from the skill, or has it already internalized these heuristics?
