"""Standalone tests for the MBPP sandbox evaluator.

Covers extraction robustness, that every sampled gold solution in the seed-42
split passes its own ``test_list``, that an obviously-wrong stub fails, and that
an infinite loop is caught by the timeout.
"""
from __future__ import annotations

import json
import os

import pytest

from skillopt.envs.mbpp.evaluator import evaluate, extract_code, run_tests

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TRAIN = os.path.join(_ROOT, "data", "mbpp_split_s42", "train", "items.json")

PY_FENCE = "```python"
BARE_FENCE = "```"


def _gold_items(limit: int = 20) -> list[dict]:
    if not os.path.isfile(_TRAIN):
        return []
    with open(_TRAIN, encoding="utf-8") as f:
        items = json.load(f)
    return items[:limit]


def test_extract_code_fenced_python():
    text = f"Here is my solution:\n{PY_FENCE}\ndef f(x):\n    return x + 1\n{BARE_FENCE}\nDone."
    assert extract_code(text) == "def f(x):\n    return x + 1"


def test_extract_code_bare_fence():
    text = f"{BARE_FENCE}\ndef f(x):\n    return x + 1\n{BARE_FENCE}"
    assert extract_code(text) == "def f(x):\n    return x + 1"


def test_extract_code_no_fence():
    text = "def f(x):\n    return x + 1"
    assert extract_code(text) == "def f(x):\n    return x + 1"


def test_run_tests_simple_pass_and_fail():
    tl = ["assert add(2, 3) == 5", "assert add(-1, 1) == 0"]
    assert run_tests("def add(a, b):\n    return a + b", tl)[0] is True
    passed, _, n_pass = run_tests("def add(a, b):\n    return a - b", tl)
    assert passed is False and n_pass == 0


def test_run_tests_timeout():
    passed, detail, _ = run_tests("def loop():\n    while True:\n        pass", ["assert loop() == 1"], timeout=3)
    assert passed is False
    assert "timeout" in detail


@pytest.mark.skipif(not _gold_items(), reason="seed-42 split not prepared")
@pytest.mark.parametrize("item", _gold_items(), ids=lambda it: it["id"])
def test_gold_solution_passes(item):
    passed, detail, _ = run_tests(item["code"], item["test_list"], item.get("test_setup_code", ""))
    assert passed, f"gold {item['id']} failed its own tests: {detail}"


@pytest.mark.skipif(not _gold_items(1), reason="seed-42 split not prepared")
def test_evaluate_wrong_stub_scores_zero():
    item = _gold_items(1)[0]
    result = evaluate(f"{PY_FENCE}\ndef wrong_unrelated_name():\n    return None\n{BARE_FENCE}", item)
    assert result["em"] == 0.0
