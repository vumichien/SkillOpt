# Cook Report — Medium Article Rewrite (SkillOpt local-OSS CSQA)

**Date:** 2026-05-28 20:35
**Workflow:** `/ck:cook` (interactive)
**Artifact:** `docs/articles/medium-skillopt-local-oss-csqa.md`
**Research inputs:**
- `plans/reports/researcher-260528-2035-skillopt-paper-deep-dive-report.md`
- `plans/reports/researcher-260528-2035-medium-technical-article-best-practices-report.md`
- `plans/reports/code-reviewer-260528-2035-medium-article-factcheck-and-narrative-report.md`

---

## What changed (story arc + scaffolding)

| Section | Before | After |
|---|---|---|
| Title | "Can Microsoft's SkillOpt Optimize an OSS Model on Your Gaming GPU? I Spent $0.01 to Find Out." | "I Spent 3 Cents Training a Markdown File on My Gaming GPU" (cost-correct, stronger hook) |
| Subtitle | OK but cost-wrong | Cost-corrected; added `Last updated` stamp signaling scaffolded sections |
| TL;DR | Cost-wrong ($0.01) | Cost-corrected (~$0.034 ≈ 3¢), token math up-front |
| **Background** | ❌ missing | ✅ NEW — explains *why* prompts deserve training; paper quote (paraphrased), 52/52 result |
| **Why this experiment** | ❌ implicit | ✅ NEW — explicit framing: paper proved it at frontier; survives 10–100× target + optimizer downgrade? |
| **What SkillOpt actually does** | "Briefly" / 4 bullets | DL-analogy table (10 rows) + 6-stage loop named explicitly |
| The setup | OK | Pricing fixed |
| 3 runs / 3 lessons | Strong already | Light tightening; "pp" vs "%" cleanup on key claims; v3 sizes normalized to bytes-on-disk |
| Final numbers | Cost-wrong | Cost math shown; bytes normalized; GPU stats sourced |
| Skill snippet | "no human edits" (not literally true) | "lightly abridged; verbatim in best_skill.md" disclosed |
| Honest verdict | Strong | Cost claim updated |
| Reproducing | OK | unchanged |
| **What's coming next** | One paragraph, no structure | ✅ RESTRUCTURED as 4-experiment matrix (cross-dataset transfer, multi-seed, ARC fresh-train, bigger target) with `_coming_` cells ready to fill in |
| Closing | OK | Hypothesis-up-front framing for follow-up |

---

## Factual claims verified against repo

(from code-reviewer trail — see referenced report for `file:line` evidence)

- ✅ arXiv 2605.23904 (matches `README.md:5`)
- ✅ v3 metrics: 0.86 → 0.90 val, 0.76 → 0.74 test, 3/10 accepts, best_step=4, 708.2 s wall
- ✅ v3 optimizer tokens: 200 192 prompt + 22 867 completion → article rounds to 200k / 23k
- ✅ v3 skill bytes-on-disk: 157 → 380 → 1728 → 3666
- ✅ v2 trajectory and wall time 280.6 s ≈ 4.7 min
- ✅ v1 trajectory: 0/6 accepts, 907.5 s ≈ 15 min, −8.3 pp test
- ✅ GPU stats from `outputs/mcqa_local_pilot_v3/gpu.csv`: peak=100 %, mean=24.8 %, duty(>5 %)=35.4 % over 147 samples (independently recomputed)
- ✅ Skill content excerpt structurally matches `best_skill.md` (abridged disclosure added)
- ✅ DL-analogy table verified against `docs/guide/dl-analogy.md`
- ✅ 6-stage loop verified against `docs/guide/training-loop.md`

## Issues fixed from review

| Finding | Severity | Action |
|---|---|---|
| D1: DeepSeek input price 10× off ($0.014 → $0.14) | HIGH | Pricing corrected everywhere; cost recomputed to ~$0.034; title updated to "3 Cents" |
| D2: Skill size unit mix (chars labelled as B) | HIGH | Normalized to bytes-on-disk for v3 (157 / 380 / 1728 / 3666); v2 unchanged (already bytes) |
| D3: Skill snippet labelled "no human edits" but trimmed | MED | Disclosed as "lightly abridged" with pointer to verbatim file |
| D5: meta-skill row in DL table not used in run | MED | Added "off in this run" caveat |
| D6: Paper quote labelled "almost verbatim" | MED | Softened to "paraphrasing their introduction" / "adapted from" |
| D14: "no retries" claim unverifiable | LOW | Softened to "largest factor" |
| N1: Headline cost claim wrong | MED | Title + opening + verdict all updated |
| N3 / N10: Stale-data risk on scaffolded `_coming_` cells | MED | Dated `Last updated` stamp added near the top |

## Issues deliberately NOT changed

| Finding | Why kept |
|---|---|
| D9: GPU stats need sourcing | Independently verified from `gpu.csv` (147 samples) — reviewer didn't open the file |
| D15: `microsoft/SkillOpt` upstream link doesn't contain pilot scripts | Placeholder; will resolve when fork is public |
| D16: Broken doc-link to dl-analogy.md | Same — depends on final public repo URL |

---

## Article scaffolding for follow-up experiments

The "What's coming next" section now has 4 tables with `_coming_` cells:

1. **Cross-dataset transfer** (Mode A) — CSQA-trained skill on ARC-Challenge + OpenBookQA
2. **Multi-seed gate** — rigor check on v3's +4 pp val claim
3. **Fresh SkillOpt loop on ARC** (Mode B) — full matrix
4. **Bigger target** — Qwen2.5-14B / 32B with v3 skill

Each table is self-contained: when a number lands, only the matching cell needs replacement. The hypothesis section ("If Experiment 1 transfers cleanly…") frames both outcomes as publishable, which is the reviewer-recommended publication-bias antidote.

---

## Verdict

**Status:** DONE
**Summary:** Base article rewritten into story arc, all numeric claims verified or corrected against repo artifacts, scaffolded sections ready for follow-up. Reviewer's two HIGH issues (DeepSeek pricing, skill-size units) are fixed. Five MEDIUM issues addressed; three low-priority/placeholder items deferred until public-fork URL is set.

## Open questions for the user

1. **Publish timing**: ship now with `_coming_` cells (with the dated stamp setting expectations), or hold until Experiment 1 (CSQA → ARC transfer) lands? Reviewer recommended either explicit "Roadmap (not yet run)" framing or holding the post.
2. **Public fork URL**: needed to fix D15/D16 placeholder links before publish.
3. **DeepSeek pricing accuracy**: V2.5 era was $0.14 / $0.28; V3 is $0.27 / $1.10; off-peak discounts apply. Article currently uses $0.14 / $0.28 — confirm this matches the tier you were actually billed at.
