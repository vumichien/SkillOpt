"""MBPP rollout - single-turn Python code-generation agent (one item).

The agent receives a skill document plus a problem and one example assert
(pinning the function name/signature), and emits a Python function. Scored
pass@1 by running the item's ``test_list`` asserts in a sandbox. Batch
execution lives in :mod:`batch_runner`.
"""
from __future__ import annotations

import json
import os

from skillopt.envs.mbpp.evaluator import evaluate
from skillopt.model import chat_target
from skillopt.prompts import load_prompt

_MAX_COMPLETION_TOKENS = 1024  # code is longer than a single letter


def _build_system(skill_content: str) -> str:
    if skill_content.strip():
        skill_section = f"## Skill\n{skill_content.strip()}\n\n"
    else:
        skill_section = ""
    return load_prompt("rollout_system", env="mbpp").format(skill_section=skill_section)


def _build_user(item: dict) -> str:
    prompt = str(item.get("prompt", "")).strip()
    example = str(item.get("example_assert", "")).strip()
    if example:
        return f"{prompt}\n\nYour function must satisfy this example test:\n{example}"
    return prompt


def process_one(
    item: dict,
    out_root: str,
    skill_content: str,
    max_turns: int = 1,
    exec_timeout: int = 120,
    sandbox_timeout: int = 8,
) -> dict:
    """Process a single MBPP item: run agent + evaluate (single-turn)."""
    item_id = str(item["id"])
    prompt = item.get("prompt", "")

    result = {
        "id": item_id,
        "question": prompt,
        "task_type": "mbpp",
        "em": 0.0,
        "hard": 0,
        "soft": 0.0,
        "predicted_answer": "",
        "predicted_code": "",
        "n_pass": 0,
        "gold_answer": [],
        "response": "",
        "fail_reason": "",
        "agent_ok": False,
        "n_turns": 0,
    }

    try:
        pred_dir = os.path.join(out_root, "predictions", item_id)
        os.makedirs(pred_dir, exist_ok=True)

        system = _build_system(skill_content)
        user = _build_user(item)

        response, _ = chat_target(
            system=system, user=user,
            max_completion_tokens=_MAX_COMPLETION_TOKENS,
            retries=5, stage="rollout",
            timeout=exec_timeout,
        )
        result["response"] = response
        result["agent_ok"] = True
        result["n_turns"] = 1

        eval_result = evaluate(response, item, timeout=sandbox_timeout)
        result["em"] = eval_result["em"]
        result["predicted_code"] = eval_result["predicted_code"]
        result["n_pass"] = eval_result["n_pass"]
        result["hard"] = int(eval_result["em"])
        result["soft"] = eval_result["em"]
        if eval_result["em"] < 1.0:
            result["fail_reason"] = (
                f"pass@1 fail ({eval_result['n_pass']}/{eval_result['n_tests']} asserts): "
                f"{eval_result['detail'][:300]}"
            )

        conversation = [
            {"type": "message", "turn": 1, "content": response},
            {
                "role": "system",
                "content": (
                    f"[EVALUATION RESULT]\nProblem: {prompt}\n"
                    f"Passed: {eval_result['passed']}  "
                    f"Asserts: {eval_result['n_pass']}/{eval_result['n_tests']}  "
                    f"EM: {eval_result['em']}\nDetail: {eval_result['detail'][:500]}"
                ),
            },
        ]
        with open(os.path.join(pred_dir, "target_system_prompt.txt"), "w", encoding="utf-8") as f:
            f.write(system)
        with open(os.path.join(pred_dir, "target_user_prompt.txt"), "w", encoding="utf-8") as f:
            f.write(user)
        with open(os.path.join(pred_dir, "conversation.json"), "w", encoding="utf-8") as f:
            json.dump(conversation, f, ensure_ascii=False, indent=2)

    except Exception as e:  # noqa: BLE001
        result["fail_reason"] = f"error: {e}"

    return result
