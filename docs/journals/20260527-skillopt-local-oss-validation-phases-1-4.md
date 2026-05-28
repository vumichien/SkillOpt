# SkillOpt Local OSS Validation: Phases 1–4 Implementation

**Date**: 2026-05-27 02:30
**Severity**: Medium
**Component**: SkillOpt skill-training loop generalization; local Qwen2.5-7B + DeepSeek optimizer validation
**Status**: Blocked (awaiting user GPU runtime)

## What Happened

Implemented Phases 1–4 of a 6-phase plan to validate that Microsoft SkillOpt's skill-training methodology generalizes to CommonsenseQA (a task the paper never touched) on local, commodity hardware: Ollama-hosted Qwen2.5-7B-Instruct Q4 quantization on RTX 3080, optimized by DeepSeek cloud (free tier). All four phases completed and verified to resolve end-to-end without runtime execution; Phases 5 (live training) and 6 (Medium article) are blocked waiting for user to provide DeepSeek API key and GPU runtime.

## The Brutal Truth

Got caught by Windows locale encoding before even running the first smoke test. The machine defaults to cp932 (Shift-JIS), so skillopt/config.py's plain YAML open() call silently corrupts UTF-8 config files on read. Spent 20 minutes thrashing before realizing the preexisting searchqa config also failed to load on THIS machine — masked a systemic issue in the codebase. Had to patch launch scripts to export PYTHONUTF8=1. This is NOT a new bug; it's a latent one that only fires on non-UTF-8 Windows locales, and it means every single train.py invocation silently fails silently on affected machines unless the environment variable is set. Frustrating because the codebase has no guards, no error messaging, nothing — just silent config load with garbage data.

The evaluator's letter-extraction logic was a measurement-instrument bug waiting to corrupt data. The fallback "first bare standalone A–E token" fabricated answers from English articles ("A dog runs fast" → extracted "A" as the answer). Since the evaluator is the binary accept/reject gate for the entire training loop, a buggy evaluator doesn't just skew metrics — it taints the ground truth signal that drives gradient learning. Caught and rewrote the priority chain to five levels of fallback before giving up, but this was a "silent data corruption" scenario that would have invalidated any pilot run.

## Technical Details

**Phase 1 — Generic OpenAI-compatible optimizer path**
- Patched `skillopt/model/azure_openai.py`: added module vars `OPTIMIZER_OPENAI_BASE_URL`, `OPTIMIZER_OPENAI_API_KEY`, setter `configure_optimizer_openai()`, and logic in `_chat_impl()`/`_chat_messages_impl()` to branch on `isinstance(client, AzureOpenAI)` (the client-type check is a reliable discriminator because AzureOpenAI is a subclass of OpenAI in the SDK; verified `issubclass(AzureOpenAI, OpenAI) == True`). Generic path sends `max_tokens` (not `max_completion_tokens`), omits `reasoning_effort`, and skips the Responses API.
- Wired config keys through `skillopt/config.py` (_FLATTEN_MAP), `scripts/train.py` (argparse + legacy key mapping), `configs/_base_/default.yaml`, and `skillopt/engine/trainer.py`.
- Added `scripts/smoke_test_optimizer.py` with a captured fake OpenAI client mock (live test blocked; code path verified structurally).

**Phase 2 — New `mcqa` environment**
- Created `skillopt/envs/mcqa/` (evaluator, dataloader, rollout, batch_runner, adapter, prompts, initial skill). Single-turn multiple-choice, exact-match letter scoring. Cloned structure from searchqa, reused `skillopt/gradient/reflect.run_minibatch_reflect()`.
- Split `run_batch()` logic into `batch_runner.py` to keep all files <200 LOC (modularization checklist).
- Registered `mcqa` in `scripts/train.py` dispatcher.

**Phase 3 — Data preparation**
- `scripts/prepare_mcqa_data.py` downloads tau/commonsense_qa (MIT license), pools labeled train + validation splits (HF test split labels hidden), maps to mcqa schema, writes to `data/mcqa_csqa_split/{train,val,test}/items.json` (48/24/48 samples, seed 42). Installed `datasets` via uv into project venv. Self-check passed; metadata correct.

**Phase 4 — Config & launch integration**
- `configs/mcqa/default.yaml` + `local-pilot.yaml` (DeepSeek optimizer, qwen target tag, empty `reasoning_effort`).
- `.env.local-pilot.example` template; `.gitignore` extended to ignore `.env.*` but track `!.env.*.example` (secrets stay local, example tracked).
- `scripts/run_local_pilot.ps1` + `.sh` launch scripts; both export `PYTHONUTF8=1` at entry.
- Verified end-to-end config resolution: `train.py --env=mcqa --optimizer=deepseek-chat --target=qwen` loads 48/24/48 samples without errors.

**Encoding trap detail:**
```
File: skillopt/config.py (original)
with open(config_path) as f:
    data = yaml.safe_load(f)
# On cp932 locale: silently reads UTF-8 config as mojibake
# Symptom: KeyError on expected config keys, silent parse corruption
# Fix: with open(config_path, encoding='utf-8') as f:
# But easier on this project: PYTHONUTF8=1 env var in launch scripts
```

**Evaluator extraction logic (original buggy version):**
```python
# Fallback: "first bare A–E token"
import re
match = re.search(r'\b[A-E]\b', response)
if match:
    return match.group()
# Problem: "A dog runs fast" → matches \bA\b at start → extracted "A" as answer
# This was SILENT data corruption in the accept/reject signal
```

**Evaluator extraction (fixed, 5-level priority):**
1. `<answer>` XML tag content
2. Whole response is a single letter [A–E]
3. Explicit phrase: "answer is X" / "option X" / "choice X"
4. Option format: "X." or "(X)"
5. Last word is a single letter [A–E]
6. Return "" (no valid answer found) — do NOT guess

Tested against 14 cases including article-prefix scenarios; all pass.

## What We Tried

- **Encoding issue**: checked if config YAML was malformed (it wasn't); checked if YAML parser had encoding parameter (it didn't); traced actual file read with Python debugger; confirmed cp932 mojibake on UTF-8 input. Solution: export PYTHONUTF8=1 in launch scripts + noted in .env.local-pilot.example comment.
- **Evaluator fallback**: initial "first bare letter" was semantic garbage; tried regex anchors and word boundaries but the real fix was ranking extraction methods by confidence (tag > exact-match > phrase > format > position) and only guessing as last resort. 14 test cases pass.

## Root Cause Analysis

**Encoding:**
- Codebase assumes UTF-8 everywhere but makes no guarantees at I/O boundaries.
- Windows cp932 locale is common in Japan/East Asia; the bug lies dormant on UTF-8 Windows machines.
- skillopt/config.py predates explicit encoding parameter (likely written on a UTF-8 machine or inside a UTF-8-forced GitHub Actions runner).
- No validation at config load; silent corruption propagates into trainer state.

**Evaluator:**
- Letter extraction as a fallback is pattern-matching, not parsing; natural language is ambiguous.
- The "any bare letter" fallback was chosen for **recall** (catch variations) but sacrificed **precision** (false positives on articles).
- Since the evaluator output drives the training signal (accept/reject gate for gradient computation), a precision error here is a systemic measurement failure, not just a metric glitch.
- The initial design did not rank extraction methods by confidence; it fell through to the weakest heuristic.

## Lessons Learned

1. **I/O encoding is not optional.** Even "obvious" code paths need explicit encoding parameters at file I/O boundaries. Add a linter check or code comment at every `open(file)` call in the config pipeline. On Windows, assume cp932 is possible; on Unix, assume UTF-8 is not guaranteed. Test configs on both locales during CI.

2. **Evaluators are measurement instruments, not convenience functions.** If the evaluator output is the ground truth for training, a 1% false-positive rate is a 1% corruption of the training signal. Prioritize extraction by confidence (parse → format → heuristic → give up) instead of recall. Document the fallback chain. Add a confidence score or "ambiguous" flag to the evaluator output so downstream can detect low-confidence labels.

3. **Client-type discrimination via `isinstance()` is clean when inheritance is stable.** The `AzureOpenAI` subclass structure is public API; checking `isinstance(client, AzureOpenAI)` is more semantic and maintainable than threading a boolean flag through every function signature. Verified once, then trust it.

4. **Modularization under 200 LOC forces clarity.** Splitting `run_batch()` into `batch_runner.py` to stay under 200 LOC lines forced better separation: the coordinator logic stayed in the env module, the I/O loop moved to the runner. Both files are now easier to test and reason about.

5. **Mock clients must be as realistic as possible.** The fake OpenAI client in the smoke test matched method signatures + return types but didn't capture behavior (e.g., error handling on invalid API keys). If the test can't catch a real config error, it's not testing the right thing. Upgrade to capturing real DeepSeek API responses for offline replay.

## Next Steps

1. **User runs Phases 5–6** (requires DeepSeek API key + local GPU runtime):
   - Phase 5: `scripts/run_local_pilot.ps1` or `.sh` (configurable num epochs; currently hardcoded 3). Parse training curves (loss, accuracy, gradient norms). Analyze learned skill prompts.
   - Phase 6: Draft Medium article. Structure: (a) why CommonsenseQA as the validation task, (b) SkillOpt method 101, (c) local hardware setup, (d) what the pilot learned, (e) generalization claim + caveats.

2. **Config encoding hardening** (parallel, low priority):
   - Add `encoding='utf-8'` to `skillopt/config.py` yaml.safe_load() call + any other `open()` sites in the config chain.
   - Add CI test for cp932 locale (or at least verify the encoding parameter sticks).

3. **Evaluator confidence scoring** (post-pilot, if results show signal noise):
   - Instrument each extraction method with a confidence score.
   - Log ambiguous labels during training so we can audit the ground truth quality.

## Unresolved Questions

1. Does DeepSeek reasonably optimize Qwen's skill prompts on CommonsenseQA, or does the skill stay near the initialized prompt? (Answered only by running Phase 5.)
2. What accuracy does the trained skill achieve on the holdout test set? (Phase 5 result.)
3. Does the pilot training run long enough to show convergence or just descent? (Depends on Phase 5 epoch count + wall-clock budget.)
