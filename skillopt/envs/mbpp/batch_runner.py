"""Parallel, resume-aware batch execution for MBPP rollouts.

Runs :func:`skillopt.envs.mbpp.rollout.process_one` over a list of items with a
thread pool, streaming results to ``results.jsonl`` and skipping already-done
ids on re-run. Kept separate from single-item rollout logic for file-size and
separation-of-concerns. Mirrors the mcqa batch_runner; the only env-specific
differences are ``task_type`` and the extra ``sandbox_timeout`` thread-through.
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from skillopt.envs.mbpp.rollout import process_one


def _stub_result(item: dict, fail_reason: str, phase: str) -> dict:
    return {
        "id": str(item["id"]),
        "question": item.get("prompt", ""),
        "task_type": "mbpp",
        "hard": 0,
        "soft": 0.0,
        "predicted_answer": "",
        "predicted_code": "",
        "n_pass": 0,
        "response": "",
        "fail_reason": fail_reason,
        "agent_ok": False,
        "n_turns": 0,
        "gold_answer": [],
        "phase": phase,
    }


def run_batch(
    items: list[dict],
    out_root: str,
    skill_content: str,
    max_turns: int = 1,
    exec_timeout: int = 120,
    workers: int = 8,
    task_timeout: int = 600,
    sandbox_timeout: int = 8,
) -> list[dict]:
    """Run the MBPP agent on all items with a thread pool. Resume-aware."""
    task_timeout = max(int(task_timeout), int(exec_timeout) + 60)
    results_path = os.path.join(out_root, "results.jsonl")
    os.makedirs(out_root, exist_ok=True)

    done_ids: set[str] = set()
    existing: list[dict] = []
    if os.path.exists(results_path):
        with open(results_path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    done_ids.add(str(r["id"]))
                    existing.append(r)
                except Exception:
                    pass

    pending = [it for it in items if str(it["id"]) not in done_ids]
    if not pending:
        return existing

    total = len(existing) + len(pending)
    completed = len(existing)
    correct = sum(1 for r in existing if r.get("hard", 0))
    results = list(existing)
    started_at: dict[str, float] = {}

    def _run_one(item: dict) -> dict:
        started_at[str(item["id"])] = time.time()
        return process_one(item, out_root, skill_content, max_turns, exec_timeout, sandbox_timeout)

    with open(results_path, "a", encoding="utf-8") as outf:
        ex = ThreadPoolExecutor(max_workers=workers)
        try:
            futs = {ex.submit(_run_one, it): it for it in pending}
            pending_futs = set(futs)
            while pending_futs:
                done, _ = wait(pending_futs, timeout=5, return_when=FIRST_COMPLETED)
                now = time.time()
                timed_out = [
                    fut for fut in pending_futs - done
                    if str(futs[fut]["id"]) in started_at
                    and now - started_at[str(futs[fut]["id"])] >= task_timeout
                ]
                for fut in done:
                    pending_futs.remove(fut)
                    item = futs[fut]
                    try:
                        res = fut.result()
                    except Exception as exc:  # noqa: BLE001
                        res = _stub_result(item, f"unexpected: {type(exc).__name__}: {exc}", "error")
                    results.append(res)
                    completed += 1
                    correct += 1 if res.get("hard", 0) else 0
                    acc = correct / completed if completed else 0
                    print(f"    [rollout] {completed}/{total} (acc={acc:.3f}) id={res['id']} hard={res.get('hard','?')}", flush=True)
                    outf.write(json.dumps(res, ensure_ascii=False) + "\n")
                    outf.flush()
                for fut in timed_out:
                    pending_futs.remove(fut)
                    fut.cancel()
                    res = _stub_result(futs[fut], f"task-timeout-{task_timeout}s", "timeout")
                    results.append(res)
                    completed += 1
                    print(f"    [rollout] {completed}/{total} id={res['id']} TIMEOUT", flush=True)
                    outf.write(json.dumps(res, ensure_ascii=False) + "\n")
                    outf.flush()
        finally:
            ex.shutdown(wait=False, cancel_futures=True)

    return results
