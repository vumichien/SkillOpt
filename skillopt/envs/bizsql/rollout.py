"""BizSQL rollout - single-turn Text-to-SQL agent (one item).

The agent receives a skill document, the schema DDL (pinning table/column names),
and a business question; it emits one SQL SELECT. Scored by execution accuracy
against the item's precomputed ``gold_result``. Batch execution lives in
:mod:`batch_runner`.
"""
from __future__ import annotations

import json
import os

from skillopt.envs.bizsql.evaluator import evaluate
from skillopt.model import chat_target
from skillopt.prompts import load_prompt

_MAX_COMPLETION_TOKENS = 512
_SCHEMA_CACHE: dict[str, str] = {}


def _load_schema(path: str) -> str:
    if path not in _SCHEMA_CACHE:
        try:
            with open(path, encoding="utf-8") as f:
                _SCHEMA_CACHE[path] = f.read().strip()
        except OSError:
            _SCHEMA_CACHE[path] = ""
    return _SCHEMA_CACHE[path]


def _build_system(skill_content: str) -> str:
    if skill_content.strip():
        skill_section = f"## Skill\n{skill_content.strip()}\n\n"
    else:
        skill_section = ""
    return load_prompt("rollout_system", env="bizsql").format(skill_section=skill_section)


def _build_user(item: dict) -> str:
    schema = _load_schema(item.get("schema_ddl_ref", ""))
    question = str(item.get("question", "")).strip()
    return (
        f"Database schema:\n{schema}\n\n"
        f"Question:\n{question}\n\n"
        f"Return one SQL SELECT in a ```sql code block."
    )


def process_one(
    item: dict,
    out_root: str,
    skill_content: str,
    max_turns: int = 1,
    exec_timeout: int = 120,
    sql_timeout: int = 5,
) -> dict:
    """Process a single BizSQL item: run agent + evaluate (single-turn)."""
    item_id = str(item["id"])
    question = item.get("question", "")

    result = {
        "id": item_id,
        "question": question,
        "task_type": "bizsql",
        "em": 0.0,
        "hard": 0,
        "soft": 0.0,
        "predicted_answer": "",
        "predicted_sql": "",
        "difficulty": item.get("difficulty", ""),
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

        eval_result = evaluate(response, item, timeout=sql_timeout)
        result["em"] = eval_result["em"]
        result["predicted_sql"] = eval_result["predicted_sql"]
        result["hard"] = int(eval_result["em"])
        result["soft"] = eval_result["em"]
        if eval_result["em"] < 1.0:
            result["fail_reason"] = f"exec-acc fail: {eval_result['detail'][:300]}"

        conversation = [
            {"type": "message", "turn": 1, "content": response},
            {
                "role": "system",
                "content": (
                    f"[EVALUATION RESULT]\nQuestion: {question}\n"
                    f"OK: {eval_result['ok']}  EM: {eval_result['em']}\n"
                    f"Predicted SQL: {eval_result['predicted_sql']}\n"
                    f"Detail: {eval_result['detail'][:500]}"
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
