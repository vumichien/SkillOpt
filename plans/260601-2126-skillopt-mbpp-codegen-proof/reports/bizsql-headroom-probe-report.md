# BizSQL Headroom Probe Report (Phase 10 Gate)

**Date:** 2026-06-02 · **Target:** `qwen2.5:7b-instruct-q4_K_M` (Ollama) · **Strong model (Arm B):** `deepseek-v4-pro`
**Split:** train (100), val/test locked · **Skill:** `skillopt/envs/bizsql/skills/initial-weak.md` (minimal "write SQL")
**Run:** `outputs/bizsql_probe/` · prior MC/MBPP hyperparams unchanged (design invariant)

## Verdict: **PASS** (after two bug fixes + a data rebuild)

| Arm | Final | Gate bar |
|-----|-------|----------|
| **A** — local 7B weak-init | **0.82** (82/100) | baseline |
| **B** — strong-model ceiling (weak prompt) | **1.00** (100/100) | ≥ ~90% → **clears, +10pp** |
| Procedural share of the 18-pt gap (hand-labeled) | **~18 pp** | ≥ 10–15 pp → **clears** |

Arm B = 1.00 ⇒ every item is solvable from the question alone (engineered-win guardrail satisfied). The full 18-pt
A→B gap is realizable, and hand-labeling shows it is **~entirely procedural** (skill-fixable), not capability.

## How we got here (two bugs masked the real signal)

The first probes reported Arm B = 0.66 then 0.74 — *below* or barely above Arm A — which read as "dataset
ambiguous, FAIL." That reading was wrong; it was two measurement/data defects:

1. **Evaluator float precision (`evaluator.py`).** Compared cells at 6 dp while gold pervasively wraps aggregates in
   `ROUND(x,2)`; correct unrounded sums scored wrong. Fixed → **2 dp** (cent precision). Also would have corrupted
   the training reward. `canonicalize` was already order-insensitive (pure `ORDER BY` never mattered).
2. **Arm B token starvation (`probe_bizsql_headroom.py:110`).** Strong-model calls used
   `max_completion_tokens=512`. `deepseek-v4-pro` is a *reasoning* model — reasoning consumed the whole budget and
   the SQL came back truncated/empty, so the "ceiling" measured *how much SQL fits in 512 tokens*, not solvability.
   Worse on the harder 3-table split (0.74→0.63). Fixed → **4096** (same fix already applied to the generator).
   With the real budget, Arm B jumped **0.63 → 1.00**.

**Data rebuild (the "invest in a redo" decision).** Independently, the original pool mixed 701 free-form
DeepSeek-generated pairs (genuinely ambiguous gold shapes/interpretations) with 169 authored. Discarded the LLM
pairs; rebuilt **420 authored-only** pairs (`scripts/author_bizsql_pairs.py`) with: output shape stated in every
question; category/product revenue formula named ("line-item value = qty×unit_price"); top-N tie rule stated;
domain conventions kept *implicit* (revenue excludes refunded/cancelled, active sub = `canceled_at IS NULL`, active
product = `active=1`, lowercase enums, ISO windows) so they remain learnable 7B headroom. Weighted to multi-table
hard (241 hard / 133 med / 46 easy) → train split 55% hard. Re-carved seed-42 (100/100/200, pool 420, 0 drops).

## Hand-labeled failures (all 18 Arm-A failures, not a sample)

| Root cause | n | Class | Skill fix |
|-----------|---|-------|-----------|
| `ambiguous column: unit_price` (unqualified join col; often drops the `orders` join → loses date/status filter) | 10 | procedural | qualify cols; join `order_items→orders→products` |
| `no such function: MONTH` (MySQL-ism; SQLite has none) | 3 | procedural | use `BETWEEN` on ISO dates / `strftime` |
| invented `active` column on subscriptions (id 0035) | 1 | procedural | active sub = `canceled_at IS NULL` |
| top-N / breakdown: dropped date window, `GROUP BY name`, loose tie | 4 | procedural | `GROUP BY id`, stated tie-break, `BETWEEN` |
| genuine capability (wrong intent) | 0 | — | — |

These are exactly a procedure-bound skill's content (column qualification, SQLite dialect, the active-subscription
convention, join + GROUP BY discipline). A strong model applies them unprompted (Arm B 100%); the q4 7B does not.

## Caveat (documented, non-blocking)
- Baseline 0.82 is higher than the plan's expected 0.25–0.55 (clarifying questions to fix Arm B also helped the 7B),
  so absolute lift is capped at 18 pp. But it is a **clean ~18 pp of near-pure procedural headroom** with a proven
  1.00 ceiling — the intended contrast against the FLAT commonsense-MC result. If the pilot lift is small, the
  high baseline (not a capability floor) is the reason.

## Contrast with MBPP (Phase 3 gate: PASS)
MBPP scores against *unit tests* (many programs pass); bizSQL against a *single gold result set*. Single-gold is
why both the eval-rounding and the strong-model-truncation bugs surfaced here and not on MBPP — and why this gate
needed the data to be unambiguous enough for a strong model to hit 100%.

## Open questions
- None blocking. Proceed to Phase 11 (bizSQL pilot + 3-seed). Sequencing: pilots use the DeepSeek optimizer, so run
  MBPP and bizSQL pilots sequentially, not concurrently, to avoid optimizer-call contention.
