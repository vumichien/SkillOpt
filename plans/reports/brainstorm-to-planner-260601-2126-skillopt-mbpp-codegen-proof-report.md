# Brainstorm Summary — Proving SkillOpt Works: Small-Scale MBPP Code-Gen on Local 7B

**Date:** 2026-06-01 · **Status:** Design APPROVED → handoff to `/ck:plan` (default)
**Optimizer (fixed):** `deepseek-v4-pro` · **Target:** `qwen2.5:7b-instruct` (Ollama, RTX 3080)

---

## Problem statement

All prior SkillOpt validations on this repo went FLAT. Commonsense MC (CSQA/SocialIQA/LogiQA)
× {qwen2.5-7b, gemma3-4b} × {deepseek-v4-pro, sonnet-4-6} → mean held-out Δ ∈ [−1.2, −0.6] pp;
zero positive cross-dataset transfer. The article's diagnosis (`docs/articles/medium-skillopt-local-oss-csqa.md:418-430`)
is verified correct: MC is **knowledge-bound** and has **no single shared procedure**, so the
optimizer can only memorize val-specific heuristics that by construction don't transfer.

The paper wins (+9→+58 pp) only on **procedure/format/tool-policy** tasks where the base model
starts far from ceiling (SpreadsheetBench, OfficeQA, LiveMath, ALFWorld, DocVQA) — and even a tiny
**Qwen3.5-4B** lifted +14.6/+15.2/+29.6/+50.7 there (`docs/paper.md:177-183`). So **task family, not
target size or optimizer model, is the lever.**

**Goal:** prove SkillOpt's loop produces a real held-out lift by reproducing the paper's winning
*code-gen* family at small scale, on the SAME local target/optimizer/GPU that was flat on MC, with a
deep per-step "behind the scenes" narration for a new standalone Medium article.

## Design principle extracted from the flat results

A clean held-out win requires a task with: **(1) a single generalizable procedure** (skill lifts all
test items, not memorized ones), **(2) a deterministic verifier** (clean gate signal), **(3) procedural
— not capability — headroom** (baseline low because the 7B mis-*follows* the procedure, not because it
*can't*). MC violated all three. MBPP code-gen satisfies all three.

## Locked decisions (from user)

| Dim | Decision |
|-----|----------|
| Proof type | Reproduce a paper-winning family, small-scale, deep step-by-step dive |
| Task family | Code-gen + unit tests |
| Dataset | **MBPP** (974 real tasks, 3 asserts + docstring each); split 100 train / 100 val / 200 test |
| Harness | **Single-turn pass@1** (sandboxed unit-test exec) |
| Target | `qwen2.5:7b-instruct` (keep — clean contrast with flat MC runs) |
| Optimizer | `deepseek-v4-pro` (fixed) |
| Rigor | seed-42 pilot → 3 seeds (43/44) if Δ beats ±1 SE (~±3.5pp @ n=200) + visible accepts |
| Env build | **New dedicated `skillopt/envs/mbpp/`**, clone of `mcqa/` layout |
| Headroom probe | **HARD GATE (Phase 0)** before full training |
| Deliverable | New standalone article + plan via `/ck:plan` default |

## Approaches evaluated

1. **Synthetic Claude-generated task** — max headroom control, but reintroduces "engineered win"
   objection. REJECTED in favor of real benchmark.
2. **Real LiveMath / SpreadsheetBench (implemented envs)** — most paper-faithful but math risks
   capability-ceiling on 7B; spreadsheet needs dataset + multi-turn exec harness (heaviest). REJECTED
   for first proof (spreadsheet could be a later follow-up).
3. **MBPP code-gen, single-turn pass@1, new mbpp env (CHOSEN)** — real, canonical small code benchmark,
   deterministic asserts, known 7B procedural headroom, generalizable conventions, lightest credible
   build. Mirrors paper's direct-chat code column.

## Final solution — artifacts to build

1. `skillopt/envs/mbpp/` — clone of `envs/mcqa/` (adapter, dataloader, evaluator, rollout, batch_runner,
   prompts/, skills/). New critical piece = **subprocess sandbox evaluator**: extract code (strip md
   fences), define fn, run 3 asserts in subprocess (timeout ~8s, temp cwd), score 1.0 iff all pass.
   Exact-match analog of `mcqa/evaluator.py`. Borrow exec/timeout pattern from
   `spreadsheetbench/executor.py` WITHOUT its multi-turn baggage.
2. `scripts/prepare_mbpp_data.py` — deterministic `data/mbpp_split_s{42,43,44}/` (train/val/test
   items.json). Each item: `{id, text/prompt, test_list, test_setup_code?, signature/entry_point}`.
3. `configs/mbpp/local-pilot.yaml` — **identical hyperparams to MC v3** (bs=20, 2 epochs→10 edits,
   lr=4 cosine, temp=0 gate, strict-improve); only env + optimizer differ. Fixed hyperparams =
   scientifically clean flat→win contrast.
4. `scripts/run_mbpp_pilot.ps1` — clone of `run_local_pilot.ps1`: smoke-test endpoints → train →
   3-arm eval (baseline weak-init / trained / accepts), idempotent, `PYTHONUTF8=1`.
5. `docs/articles/medium-skillopt-mbpp-codegen-local.md` — standalone article.

### Prompt / rollout design
Single-turn. System = skill. User = MBPP problem text + **one example assert** (pins signature; without
it pass@1 collapses on name-mismatch — an unfair manufactured failure). Score on all 3 asserts held out.

### Weak-init skill
Minimal ("Write a Python function. Put it in a code block.") — leaves procedural headroom, mirrors MC
weak-init philosophy.

### Procedure the optimizer should discover (generalizes → held-out lift)
Emit only a function (no prose), match implied signature, `return` not `print`, handle empty/zero/negative
edge cases, read docstring constraints precisely, no markdown-fence noise. Unlike MC, these hold across
ALL items.

### Article structure (depth = the ask)
Hook (flat MC → hypothesis) → why MBPP is the right family → setup → weak init + expected discovery →
**per-step deep dive** (failed rollouts → optimizer reflection JSON → skill edit before/after → gate on
100 val → held-out effect) → accept trajectory → results (baseline vs trained @ n=200, Δ+SE, accepts,
skill growth, cost, wall, GPU) → 3-seed mean±std → the contrast section (same loop/optimizer/GPU/target,
now lifts; confirms headroom diagnosis) → reproduce steps. Stretch (flagged): HumanEval transfer.

## Phased plan shape (for `/ck:plan`)

- **Phase 0 — Headroom probe (HARD GATE):** baseline pass@1 on 100 items + hand-categorize ~20 failures
  into procedural (skill-fixable) vs capability. Proceed only if ≥~10–15 pp procedural. Fallback if
  capability-floored: `qwen2.5-coder:7b` (user call; changes "same target" story).
- **Phase 1** — `prepare_mbpp_data.py` + splits (s42 first).
- **Phase 2** — `envs/mbpp/` adapter + dataloader + **sandbox evaluator** + rollout + weak-init skill.
- **Phase 3** — `configs/mbpp/local-pilot.yaml` + `run_mbpp_pilot.ps1` + endpoint smoke test.
- **Phase 4** — seed-42 pilot; read 3-arm result; decide scale.
- **Phase 5** — seeds 43/44 if pilot clears ±1 SE; aggregate mean±std.
- **Phase 6** — write standalone article with per-step trace + contrast.

## Success metrics / acceptance criteria

- Phase 0 gate passes (≥~10–15 pp procedural headroom).
- Held-out test Δ (trained − weak-init, n=200) **beyond ±1 binomial SE (~±3.5 pp)** with ≥1 visible
  accept and monotonic dev climb.
- 3-seed mean Δ positive and outside noise.
- Article reproduces the per-step mechanism end-to-end and ends in a held-out win.

## Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Capability-floor (failures not procedural) → flat like gemma-LogiQA | Phase-0 hard gate; fallback `qwen2.5-coder:7b` |
| Sandbox safety (Windows, no container) | subprocess + timeout + temp cwd; trusted-ish local 7B output; true isolation out of scope (flagged) |
| Signature/name mismatch → unfair fails | include one example assert in prompt |
| Small-eval overfit | conventions generalize; 100-val gate + n=200 test + 3 seeds |
| Eval cost/time | single-turn pass@1, temp=0 → ~15–30 min/seed, trivial DeepSeek spend |

## Out of scope

Other envs; optimizers other than deepseek-v4-pro; multi-target grids; multi-turn ReAct. HumanEval
transfer = flagged stretch only.

## Open questions

- **Phase-0 fallback:** if qwen2.5:7b-instruct is capability-floored, switch to `qwen2.5-coder:7b`
  (raises ceiling but breaks "same target as MC")? Default = pause and ask user at the gate.
- **MBPP variant:** full MBPP (974) vs sanitized (427)? Default = full MBPP, deterministic sample;
  decide in Phase 1.
- **3-seed CSQA-style splits:** generate s42/43/44 up front or lazily? Default = s42 first, 43/44 only
  if pilot clears the bar.
