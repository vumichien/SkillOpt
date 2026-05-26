---
phase: 1
title: "DeepSeek Optimizer Support"
status: complete
priority: P1
effort: "3-5h"
dependencies: []
---

# Phase 1: DeepSeek Optimizer Support

## Overview
Patch the optimizer path so it can use DeepSeek (any OpenAI-compatible API) instead of Azure-only. Hard blocker — every later phase depends on a working optimizer.

## Key Insight (verified)
`skillopt/model/__init__.py:89` routes `openai_chat` optimizer → `azure_openai.chat_optimizer` → `get_optimizer_client()` → `_make_client("optimizer")` which **always** returns `AzureOpenAI(azure_endpoint=...)` (`azure_openai.py:281-309`). Generic `OpenAI(base_url=...)` exists only for the qwen target (`:320-334`). DeepSeek serves OpenAI-style `/chat/completions` — incompatible with Azure URL shape. Also SkillOpt sends `max_completion_tokens` and (when set) `reasoning_effort`; DeepSeek-chat expects `max_tokens` and rejects `reasoning_effort`.

## Requirements
- Functional: when optimizer base_url + api_key configured, optimizer calls hit that OpenAI-compatible endpoint (DeepSeek) via generic `OpenAI` client. Target path unchanged.
- Functional: param compat for the generic optimizer path — `max_tokens` not `max_completion_tokens`; omit `reasoning_effort`.
- Non-functional: zero behavior change when new env vars unset (Azure path intact). No new heavy deps (`openai` already present).

## Architecture
New env vars in `azure_openai.py`:
- `OPTIMIZER_OPENAI_BASE_URL` (e.g. `https://api.deepseek.com/v1`)
- `OPTIMIZER_OPENAI_API_KEY`

Wiring:
1. Module-level vars + `configure_optimizer_openai(...)` setter (mirror existing config plumbing).
2. `get_optimizer_client()`: if base_url set → cached `OpenAI(base_url, api_key)`; else current `_make_client("optimizer")`.
3. Branch `_chat_impl` + `_chat_messages_impl` so the generic optimizer path uses `max_tokens=` and skips `reasoning_effort`. Pass an explicit flag from the optimizer entry points (cleanest) or detect generic-client mode. Target/Azure calls untouched.
4. Config/CLI surface: add `model.optimizer_openai_base_url` + `model.optimizer_openai_api_key` to `configs/_base_/default.yaml`, `_LEGACY_TO_STRUCTURED` + argparse in `scripts/train.py`, read into the configure call in `engine/trainer.py` setup.

## Related Code Files
- Modify: `skillopt/model/azure_openai.py` (client factory + chat impls + config vars/setter)
- Modify: `skillopt/model/__init__.py` (re-export setter if added)
- Modify: `scripts/train.py` (argparse + `_LEGACY_TO_STRUCTURED`)
- Modify: `configs/_base_/default.yaml` (new keys, default "")
- Read for context: `skillopt/engine/trainer.py` (where `configure_azure_openai`/`set_optimizer_backend` called)
- Create: `scripts/smoke_test_optimizer.py`

## Implementation Steps
1. Read `engine/trainer.py` model-setup block + `azure_openai.py:1-100` config section to match style.
2. Add `OPTIMIZER_OPENAI_BASE_URL`/`_API_KEY` vars + `configure_optimizer_openai(...)` setter.
3. Modify `get_optimizer_client()` to return generic `OpenAI` when base_url set (cache in `_optimizer_client`).
4. Add param-compat branch in `_chat_impl` + `_chat_messages_impl` (`max_tokens`, no `reasoning_effort`).
5. Add config keys + CLI flags + legacy map; wire reads in trainer init.
6. Write `scripts/smoke_test_optimizer.py`: configure DeepSeek, call `chat_optimizer("You are terse.","Reply OK.")`, print text + usage.
7. Run smoke test w/ real DeepSeek key; iterate param mapping until non-empty. Confirm `python scripts/train.py --help` + `import skillopt` clean.

## Success Criteria
- [ ] `scripts/smoke_test_optimizer.py` returns non-empty text + token usage from DeepSeek.
- [ ] Azure path unchanged when new env vars unset (imports/`--help` clean).
- [ ] `--cfg-options model.optimizer_openai_base_url=... model.optimizer_openai_api_key=...` reaches the optimizer client.
- [ ] No `reasoning_effort`/`max_completion_tokens` sent to DeepSeek (400-free call).

## Risk Assessment
- **DeepSeek param quirks (unknown-field 400s):** mitigate via smoke test + `max_tokens` mapping; prefer `deepseek-chat` (not `deepseek-reasoner`) for the optimizer.
- **Scope creep into a provider registry:** KISS — only what DeepSeek needs; generic base_url is a free side effect.
- **Secret hygiene:** key from env/.env only; never commit.

## Next Steps
Unblocks Phases 2-4. Phase 4 launch scripts set `OPTIMIZER_OPENAI_BASE_URL`/`_API_KEY`.
