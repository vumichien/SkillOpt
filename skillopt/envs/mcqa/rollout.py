"""MCQA rollout - single-turn multiple-choice agent (one item).

The agent receives a skill document plus a question with labeled options, and
emits its choice inside ``<answer>X</answer>`` tags. Scored by exact letter
match against the gold label. Batch execution lives in :mod:`batch_runner`.
"""
from __future__ import annotations

import json
import os

from skillopt.model import chat_target
from skillopt.prompts import load_prompt
from skillopt.envs.mcqa.evaluator import evaluate

_MAX_COMPLETION_TOKENS = 256


def _choice_labels(item: dict) -> list[str]:
    return [str(c.get("label", "")).strip().upper() for c in item.get("choices", []) if c.get("label")]


def _build_system(skill_content: str) -> str:
    if skill_content.strip():
        skill_section = f"## Skill\n{skill_content.strip()}\n\n"
    else:
        skill_section = ""
    return load_prompt("rollout_system", env="mcqa").format(skill_section=skill_section)


def _build_user(question: str, choices: list[dict]) -> str:
    lines = [f"{str(c.get('label','')).strip()}. {str(c.get('text','')).strip()}" for c in choices]
    options = "\n".join(lines)
    return f"Question:\n{question}\n\nOptions:\n{options}"


def process_one(
    item: dict,
    out_root: str,
    skill_content: str,
    max_turns: int = 1,
    exec_timeout: int = 120,
) -> dict:
    """Process a single MC item: run agent + evaluate (single-turn)."""
    item_id = str(item["id"])
    question = item.get("question", "")
    choices = item.get("choices", [])
    gold_letters = item.get("answers", [])
    labels = _choice_labels(item)

    result = {
        "id": item_id,
        "question": question,
        "task_type": "mcqa",
        "em": 0.0,
        "hard": 0,
        "soft": 0.0,
        "predicted_answer": "",
        "gold_answer": [str(g).strip().upper() for g in gold_letters],
        "response": "",
        "fail_reason": "",
        "agent_ok": False,
        "n_turns": 0,
    }

    try:
        pred_dir = os.path.join(out_root, "predictions", item_id)
        os.makedirs(pred_dir, exist_ok=True)

        system = _build_system(skill_content)
        user = _build_user(question, choices)

        response, _ = chat_target(
            system=system, user=user,
            max_completion_tokens=_MAX_COMPLETION_TOKENS,
            retries=5, stage="rollout",
            timeout=exec_timeout,
        )
        result["response"] = response
        result["agent_ok"] = True
        result["n_turns"] = 1

        eval_result = evaluate(response, gold_letters, valid_labels=labels)
        result["em"] = eval_result["em"]
        result["predicted_answer"] = eval_result["predicted_answer"]
        result["hard"] = int(eval_result["em"])
        result["soft"] = eval_result["em"]
        if eval_result["em"] < 1.0:
            result["fail_reason"] = (
                f"wrong letter: predicted {eval_result['predicted_answer'] or '<none>'} "
                f"but gold is {eval_result['gold']}"
            )

        conversation = [
            {"type": "message", "turn": 1, "content": response},
            {
                "role": "system",
                "content": (
                    f"[EVALUATION RESULT]\nQuestion: {question}\n"
                    f"Predicted: {eval_result['predicted_answer']!r}  "
                    f"Gold: {eval_result['gold']!r}  EM: {eval_result['em']}"
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
