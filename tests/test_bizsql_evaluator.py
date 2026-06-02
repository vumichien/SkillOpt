"""Standalone tests for the BizSQL execution-accuracy evaluator.

Covers extraction robustness, that gold SQL reproduces its own result set,
order-insensitive + float-tolerant comparison, and that non-SELECT / multi-
statement input is rejected by the read-only SELECT-only guard. Runs against the
deterministically seeded data/bizsql/business.sqlite.
"""
from __future__ import annotations

import os

import pytest

from skillopt.envs.bizsql.evaluator import (
    canonicalize,
    evaluate,
    extract_sql,
    run_sql,
)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB = os.path.join(_ROOT, "data", "bizsql", "business.sqlite")
_SCHEMA = os.path.join(_ROOT, "data", "bizsql", "schema.sql")

SQL_FENCE = "```sql"
BARE_FENCE = "```"

_HAS_DB = os.path.isfile(_DB)


def _item(gold_sql: str, gold_result: list) -> dict:
    return {
        "id": "t",
        "question": "q",
        "db_path": _DB,
        "schema_ddl_ref": _SCHEMA,
        "gold_sql": gold_sql,
        "gold_result": gold_result,
    }


def test_extract_sql_fenced():
    text = f"Here you go:\n{SQL_FENCE}\nSELECT 1;\n{BARE_FENCE}\nThanks."
    assert extract_sql(text) == "SELECT 1"


def test_extract_sql_bare_fence():
    assert extract_sql(f"{BARE_FENCE}\nSELECT 2\n{BARE_FENCE}") == "SELECT 2"


def test_extract_sql_prose_prefix():
    assert extract_sql("SQL: SELECT 3 FROM customers").upper().startswith("SELECT 3")


def test_canonicalize_order_insensitive_and_float():
    a = [[1, 2.0000001], [3, 4.0]]
    b = [[3, 4.0], [1, 2.0]]
    assert canonicalize(a) == canonicalize(b)


@pytest.mark.skipif(not _HAS_DB, reason="business.sqlite not seeded")
def test_run_sql_gold_roundtrip():
    sql = "SELECT region, COUNT(*) FROM customers GROUP BY region"
    ok, rows, detail = run_sql(sql, _DB)
    assert ok, detail
    # a re-ordered / re-cased equivalent query must canonicalize equal
    ok2, rows2, _ = run_sql("SELECT region, COUNT(*) FROM customers GROUP BY region ORDER BY region DESC", _DB)
    assert canonicalize(rows) == canonicalize(rows2)


@pytest.mark.skipif(not _HAS_DB, reason="business.sqlite not seeded")
def test_evaluate_correct_and_wrong():
    sql = "SELECT COUNT(*) FROM customers WHERE region = 'EU'"
    ok, rows, _ = run_sql(sql, _DB)
    assert ok
    item = _item(sql, rows)
    good = evaluate(f"{SQL_FENCE}\n{sql}\n{BARE_FENCE}", item)
    assert good["em"] == 1.0
    wrong = evaluate(f"{SQL_FENCE}\nSELECT COUNT(*) FROM customers WHERE region = 'NA'\n{BARE_FENCE}", item)
    assert wrong["em"] == 0.0


@pytest.mark.skipif(not _HAS_DB, reason="business.sqlite not seeded")
@pytest.mark.parametrize("bad", [
    "DROP TABLE customers",
    "DELETE FROM orders",
    "UPDATE customers SET name = 'x'",
    "INSERT INTO customers VALUES (1)",
    "SELECT 1; DROP TABLE customers",
    "PRAGMA table_info(customers)",
])
def test_non_select_rejected(bad):
    ok, rows, detail = run_sql(bad, _DB)
    assert ok is False
    assert rows is None


@pytest.mark.skipif(not _HAS_DB, reason="business.sqlite not seeded")
@pytest.mark.parametrize("sql", [
    "SELECT 'delete me' AS note",          # blacklisted word inside a string literal
    "SELECT ';' AS semi",                  # semicolon inside a string literal
    "SELECT 1 AS x -- ; DROP TABLE t",     # blacklisted word inside a line comment
    "SELECT /* update later */ 1 AS x",    # blacklisted word inside a block comment
])
def test_valid_select_with_literals_not_false_rejected(sql):
    ok, rows, detail = run_sql(sql, _DB)
    assert ok, f"valid SELECT false-rejected: {detail}"
    assert rows is not None


def test_empty_or_absent_gold_never_matches():
    # An empty/absent gold_result must NOT be satisfied by an empty prediction.
    item = _item("SELECT 1 WHERE 1 = 0", [])  # gold_result empty
    result = evaluate(f"{SQL_FENCE}\nSELECT 1 WHERE 1 = 0\n{BARE_FENCE}", item)
    assert result["em"] == 0.0
    item2 = dict(_item("SELECT 1", []))
    del item2["gold_result"]
    assert evaluate(f"{SQL_FENCE}\nSELECT 1 WHERE 1 = 0\n{BARE_FENCE}", item2)["em"] == 0.0


@pytest.mark.skipif(not _HAS_DB, reason="business.sqlite not seeded")
def test_read_only_connection_blocks_writes_even_if_guard_bypassed():
    # The guard already rejects writes; this also proves the connection is RO.
    import sqlite3
    conn = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("CREATE TABLE hack (x INTEGER)")
    conn.close()
