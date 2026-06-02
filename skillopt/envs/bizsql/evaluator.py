"""BizSQL evaluation: extract one SQL SELECT and score it by execution accuracy.

The "answer" is a single SQL ``SELECT`` run against the seeded SQLite DB; the
result set is compared (order-insensitive, type-normalized) to the item's
precomputed ``gold_result``. There is NO LLM judge — scoring is pure execution.

Safety (the DB is the sandbox):
  * open a READ-ONLY connection (``file:...?mode=ro``);
  * allow only a single ``SELECT`` / ``WITH ... SELECT`` statement;
  * reject multi-statement input and any write/DDL keyword;
  * abort runaway queries with an in-process statement timeout.

Extraction is robust to several response shapes, in priority order:
  1. the first fenced ```sql ... ``` block
  2. the first bare fenced ``` ... ``` block
  3. a leading "SQL:"/prose stripped, then the first SELECT/WITH ... statement
"""
from __future__ import annotations

import re
import sqlite3
import time

_FENCED_SQL = re.compile(r"```sql\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_FENCED_ANY = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_SELECT_START = re.compile(r"(?is)\b(with|select)\b.*")
_WRITE_KEYWORDS = re.compile(
    r"(?is)\b(insert|update|delete|drop|alter|attach|detach|create|replace|"
    r"pragma|vacuum|reindex|truncate|grant|revoke|begin|commit)\b"
)
# Strip SQL comments + string/identifier literals before the safety scan so a
# legit read-only query like `SELECT 'delete me'` or `SELECT ';'` is not
# false-rejected. Execution still uses the ORIGINAL sql; mode=ro is the backstop.
_LITERALS_AND_COMMENTS = re.compile(
    r"--[^\n]*"            # line comment
    r"|/\*.*?\*/"          # block comment
    r"|'(?:[^']|'')*'"     # single-quoted string literal
    r'|"(?:[^"]|"")*"',    # double-quoted identifier
    re.DOTALL,
)
_FLOAT_DP = 6
_PROGRESS_OPS = 1000  # progress handler fires every N VM ops


def extract_sql(text: str) -> str:
    """Pull a single SQL statement out of a target response. Best-effort."""
    if not text:
        return ""
    m = _FENCED_SQL.search(text)
    if m:
        sql = m.group(1)
    else:
        m = _FENCED_ANY.search(text)
        if m:
            sql = m.group(1)
        else:
            sql = text
    sql = sql.strip()
    # strip a leading "SQL:" / "Query:" prefix
    sql = re.sub(r"(?i)^\s*(sql|query|answer)\s*:\s*", "", sql).strip()
    # take from the first SELECT/WITH onward (drops trailing prose if any)
    m = _SELECT_START.search(sql)
    if m:
        sql = m.group(0).strip()
    return sql.rstrip(";").strip()


def _is_safe_select(sql: str) -> tuple[bool, str]:
    """Single read-only SELECT only. Returns (ok, reason).

    Safety checks run on a SCRUBBED copy (comments + string/identifier literals
    removed) so blacklisted words / semicolons inside a literal don't trigger a
    false rejection. The query is still executed verbatim under a read-only
    connection, so the scrub can never widen what actually runs.
    """
    if not sql.strip():
        return False, "empty sql"
    scrubbed = _LITERALS_AND_COMMENTS.sub(" ", sql.rstrip().rstrip(";")).strip()
    if ";" in scrubbed:  # any ';' left after stripping the trailing one => multi-statement
        return False, "multiple statements not allowed"
    if not re.match(r"(?is)^\s*(with|select)\b", scrubbed):
        return False, "only SELECT/WITH queries allowed"
    if _WRITE_KEYWORDS.search(scrubbed):
        return False, "write/DDL keyword rejected"
    return True, ""


def run_sql(sql: str, db_path: str, timeout: int = 5) -> tuple[bool, list | None, str]:
    """Execute a single read-only SELECT. Returns (ok, rows, detail)."""
    ok, reason = _is_safe_select(sql)
    if not ok:
        return False, None, reason

    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=float(timeout))
        deadline = time.monotonic() + float(timeout)
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, _PROGRESS_OPS)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        return True, [list(r) for r in rows], ""
    except sqlite3.OperationalError as e:
        msg = str(e)
        if "interrupted" in msg.lower():
            return False, None, f"timeout-{timeout}s"
        return False, None, f"OperationalError: {msg}"
    except Exception as e:  # noqa: BLE001
        return False, None, f"{type(e).__name__}: {e}"
    finally:
        if conn is not None:
            conn.close()


def _norm_cell(x):
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, float):
        return round(x, _FLOAT_DP)
    if isinstance(x, int):
        return round(float(x), _FLOAT_DP)  # int 5 == float 5.0
    if x is None:
        return None
    return str(x)


def canonicalize(rows: list | None) -> tuple:
    """Order-insensitive, type-normalized signature of a result set."""
    if not rows:
        return ()
    norm = [tuple(_norm_cell(c) for c in row) for row in rows]
    # sort by repr so mixed types / None never raise during comparison
    return tuple(sorted(norm, key=repr))


def evaluate(prediction_text: str, item: dict, timeout: int = 5) -> dict:
    """Evaluate one BizSQL prediction. Returns em / ok / predicted_sql / rows / detail."""
    sql = extract_sql(prediction_text)
    db_path = item["db_path"]
    gold = item.get("gold_result")
    ok, rows, detail = run_sql(sql, db_path, timeout=timeout)
    em = 0.0
    if not gold:
        # ill-formed item (data-prep should have dropped empty golds); never let
        # an empty prediction false-match an empty/absent gold via canonicalize(()).
        detail = detail or "no gold_result"
    elif ok and canonicalize(rows) == canonicalize(gold):
        em = 1.0
    elif ok and not detail:
        detail = "wrong result set"
    return {
        "em": em,
        "ok": ok,
        "predicted_sql": sql,
        "rows": rows,
        "detail": detail,
    }
