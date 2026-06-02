"""MBPP evaluation: extract a Python function and score it pass@1 via a sandbox.

The "answer" is a complete Python function. Extraction is robust to several
response shapes, in priority order:

  1. the first fenced ```python ... ``` block
  2. the first bare fenced ``` ... ``` block
  3. the whole response text (no fence)

Scoring runs the item's ``test_list`` asserts in an isolated subprocess
(``python -I``) with a timeout and a temp cwd. ``pass@1`` requires every assert
to pass. The sandbox borrows the tempfile/timeout/returncode pattern from
``skillopt/envs/spreadsheetbench/executor.py`` (no multi-turn, no xlsx).

Sandbox safety: 7B-generated code runs locally via subprocess + ``-I`` isolation
+ timeout + temp cwd; there is NO OS container. Acceptable for local, trusted-ish
use with pure-compute MBPP asserts only. Do not run with network-bound or
filesystem-destructive test setups.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

_FENCED_PYTHON = re.compile(r"```(?:python|py)\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_FENCED_ANY = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    """Pull the Python source out of a target response. Best-effort, never raises."""
    if not text:
        return ""
    m = _FENCED_PYTHON.search(text)
    if m:
        return m.group(1).strip()
    m = _FENCED_ANY.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _build_script(code: str, asserts: list[str], test_setup_code: str) -> str:
    parts: list[str] = []
    if test_setup_code and test_setup_code.strip():
        parts.append(test_setup_code.strip())
    parts.append(code)
    parts.extend(asserts)
    return "\n\n".join(parts) + "\n"


def _run_script(script: str, timeout: int) -> tuple[bool, str]:
    """Run *script* in an isolated subprocess + temp cwd. Returns (passed, detail)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = os.path.join(tmpdir, "candidate_test.py")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(script)
        try:
            proc = subprocess.run(
                [sys.executable, "-I", tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
            )
        except subprocess.TimeoutExpired:
            return False, f"timeout-{timeout}s"
        if proc.returncode == 0:
            return True, ""
        detail = (proc.stderr or proc.stdout or "").strip()
        # keep the final, most informative lines (assertion / exception)
        if len(detail) > 600:
            detail = detail[-600:]
        return False, detail


def run_tests(
    code: str,
    test_list: list[str],
    test_setup_code: str = "",
    timeout: int = 8,
) -> tuple[bool, str, int]:
    """Run all ``test_list`` asserts against *code* in the sandbox.

    Returns ``(passed, detail, n_pass)`` where ``passed`` is True iff every
    assert passes. ``n_pass`` counts how many individual asserts passed (only
    computed when the combined run fails, to keep the success path one subprocess).
    """
    asserts = [a for a in (test_list or []) if str(a).strip()]
    if not code.strip():
        return False, "empty code", 0
    if not asserts:
        return False, "no tests", 0

    passed, detail = _run_script(_build_script(code, asserts, test_setup_code), timeout)
    if passed:
        return True, "", len(asserts)

    # Combined run failed — count individual passes for the failure trace.
    n_pass = 0
    for a in asserts:
        ok, _ = _run_script(_build_script(code, [a], test_setup_code), timeout)
        if ok:
            n_pass += 1
    return False, detail or "assertion failed", n_pass


def evaluate(prediction_text: str, item: dict, timeout: int = 8) -> dict:
    """Evaluate one MBPP prediction. Returns em / passed / n_pass / code / detail."""
    code = extract_code(prediction_text)
    test_list = list(item.get("test_list") or [])
    setup = str(item.get("test_setup_code") or "")
    passed, detail, n_pass = run_tests(code, test_list, setup, timeout=timeout)
    return {
        "em": 1.0 if passed else 0.0,
        "passed": passed,
        "n_pass": n_pass,
        "n_tests": len([a for a in test_list if str(a).strip()]),
        "predicted_code": code,
        "detail": detail,
    }
