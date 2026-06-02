# MBPP Headroom Probe Report (Phase 3 Gate)

**Date:** 2026-06-02 · **Target:** `qwen2.5:7b-instruct-q4_K_M` (Ollama) · **Split:** train (100), test locked
**Skill:** `skillopt/envs/mbpp/skills/initial-weak.md` · **Run:** `outputs/mbpp_probe/probe_failures.json`

## Result

- **Baseline pass@1 = 0.66** (66/100, 0 rollout errors).
- 34 failures. Exception mix: 33 AssertionError (ran, wrong output), 1 NameError. No crashes/timeouts.
- Auto-bucket procedural share = 10.0% (floor — auto-bucketer can't read intent; understates).

## Hand-label (the actual gate)

Auto-buckets only key off the truncated `detail`; real verdict reads prompt + predicted code.

### Definite procedural (right idea / convention miss — skill-fixable)
- **9 `edge_case`** (pass 1–2 of 3 asserts): 11, 149, 407, 402, 617, 900, 150, 138, 347 — correct core, fails an edge.
- **1 NameError**: 334.
- Zero-pass procedural (sampled 14 of ~23): 282 (over-complicated a plain map/lambda), 415 (tuple order `(8,7)` vs `(7,8)`), 321 (misread string input as a count), 470 (misread "pairwise" = consecutive, not even/odd zip), 202 (0-vs-1 index convention `s[1::2]`→`s[0::2]`), 529 (wrong seed pair).

### Capability (genuine algorithm miss)
- 291 (fence-painting DP recurrence), 360 (Carol-number formula unknown), 416 (wrong "three parts" decomposition), 344 (missed odd-factors⇒perfect-square), 288 (wrong modular-inverse condition).

### Bad test (exclude — not fairly fixable)
- 233, 139: MBPP gold hardcodes `pi=3.1415`; `2*math.pi*r` is mathematically correct but mismatches the truncated expected value. ~2% noise floor.

### Sample tally (14 zero-pass): ~6 procedural · ~5 capability · ~2 bad-test
Extrapolated over ~22 zero-pass ⇒ ~9–10 more procedural on top of the 10 definite.

## Verdict: **PASS**

- **Procedural headroom ≈ 16–20 pp** ≥ the ≥10–15 pp gate.
- No Arm B needed — these are standard MBPP items; solvability is not in question.
- Caveat: baseline 0.66 caps total headroom at 34 pp (~half procedural). Movement should be visible but not huge; if the pilot lift is marginal, baseline ceiling — not capability floor — is the reason. Documented, not blocking.

## Open questions
- Borderline labels (531 min-coins, 529 seed) could flip ±1–2 pp; does not change the PASS.
