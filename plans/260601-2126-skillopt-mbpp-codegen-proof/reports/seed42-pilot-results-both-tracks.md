# Seed-42 Pilot Results — MBPP (Phase 5) + bizSQL (Phase 11)

**Date:** 2026-06-02 · Target `qwen2.5:7b-instruct-q4_K_M` · Optimizer `deepseek-v4-pro` · seed 42 · MC-run hyperparams
(epochs 2, batch 20, edit_budget 4, patch update, gate on). Held-out test n=200, deterministic (temp 0).

## Headline

| Track | arm-1 base (test) | arm-3 trained (test) | Δ | dev (sel) | accepts | gate (+3.5pp & ≥1 accept) |
|-------|------|------|------|------|------|------|
| **MBPP** | 0.65 | 0.62 | **−3.0pp** | 0.58→0.67 (+9) | 3 | **FAIL** (flat, overfit) |
| **bizSQL** | 0.88 | **0.985** | **+10.5pp** | 0.88→0.98 (+10) | 4 | **PASS** (generalizes) |

bizSQL test Δ (+10.5) ≈ dev Δ (+10) → the gain **generalized**. MBPP dev climbed +9 but test fell −3 → **overfit**
(same signature as all commonsense-MC runs). Both runs ~33 min wall; bizSQL 2.8M optimizer tokens, MBPP 1.0M.

## Why the split — the real lever

Not "procedure vs knowledge" (the original hypothesis — MBPP is procedural yet went flat). The lever is whether a
task's failures share a **small set of transferable procedural fixes**:

- **bizSQL — homogeneous.** 18 weak-init failures collapsed to a handful of conventions: qualify shared columns,
  join `order_items→orders→products`, `BETWEEN` not `MONTH()`/`YEAR()`, revenue excludes refunded/cancelled,
  active sub = `canceled_at IS NULL`, GROUP BY id not name. ONE skill encoding these fixes most failures across
  train **and** test → +10.5pp that transfers. (Verified: `best_skill.md` is general conventions, zero leaked gold.)
- **MBPP — heterogeneous.** Each failure is its own algorithm (DP recurrence, formula, edge case). The optimizer
  fit selection-set-specific tips (+9 dev) that don't transfer (−3 test). No small shared fix set exists.
- **Commonsense-MC — knowledge-bound.** No procedural fix at all; pure recall → flat.

## bizSQL learned skill (mechanism confirmed)
`outputs/bizsql-train/deepseek-v4-pro/qwen7b-s42/best_skill.md` — sections: Output Contract, Key Conventions
(revenue/active-sub/active-product/ROUND), Grouping by entity id, Revenue calc (order-total vs line-item), Date
filtering (ISO/BETWEEN, no MONTH/YEAR), Column disambiguation. All general; brought the 7B from 0.88 to within
1.5pp of the strong-model ceiling (1.00).

## Verdicts
- **bizSQL: scale-gate PASS** → run 3 seeds (43/44) to confirm +10.5pp holds; expect a robust positive.
- **MBPP: scale-gate FAIL (flat)** → documented Phase-5 fallback available (code-specific analyst prompts + 1 re-run)
  to rule out generic-reflect-prompt fit as the cause. Optional: MBPP-flat vs bizSQL-win is itself the article's
  sharpest contrast.

## Artifacts
- `outputs/mbpp-train/deepseek-v4-pro/qwen7b-s42/` and `outputs/bizsql-train/deepseek-v4-pro/qwen7b-s42/`
  ({summary,history}.json, best_skill.md, test_eval*/, gpu.csv).

## Open questions (for user)
- Next GPU spend: bizSQL 3-seed scale-up, MBPP prompt-fallback, both (sequential), or stop and write?
