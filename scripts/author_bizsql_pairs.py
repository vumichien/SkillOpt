#!/usr/bin/env python3
"""Claude-Code-authored blind BizSQL pairs — deterministic, fast, free.

Emits diverse, procedure-bound (question, gold_sql, difficulty) pairs by sweeping
real DB parameters (regions, categories, countries, date windows, top-N, HAVING
thresholds) over hand-written, convention-correct SQL templates. Every candidate
is execution-validated against business.sqlite and deduped BY RESULT SIGNATURE
against the running pool + itself, so only correct, distinct, small-result pairs
land in data/bizsql/raw_pairs.jsonl.

Blind-gold: this author sees ONLY the schema/conventions — never the target model
or a candidate skill.

Question-design discipline (so a STRONG model can hit the single gold from the
question alone — the engineered-win guardrail — while a weak 7B still fumbles the
execution):
  * The output SHAPE is always stated ("Return a single number." / "Return name
    and revenue.").
  * Where a formula is not the obvious default, it is named: category/product
    revenue = "line-item value (quantity x unit price)", NOT order totals.
  * Top-N tie handling is stated ("if values tie, order by name").
  * Domain conventions a competent analyst infers are left IMPLICIT so they remain
    learnable headroom for the 7B: "revenue" excludes refunded/cancelled orders;
    "active subscription" = canceled_at IS NULL; "active product" = active=1; date
    windows are inclusive ISO ranges; status/priority enums are lowercase.
  * Bias toward multi-table medium/hard items: a q4 7B mis-joins, drops a filter,
    or emits non-SQLite functions (MONTH/YEAR) even when the question is explicit.

Usage:  python scripts/author_bizsql_pairs.py [--limit N] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_RAW = os.path.join(_ROOT, "data", "bizsql", "raw_pairs.jsonl")
_DB = os.path.join(_ROOT, "data", "bizsql", "business.sqlite")

REGIONS = ["EU", "NA", "APAC", "LATAM"]
CATEGORIES = ["Software", "Hardware", "Accessories", "Services"]
PLANS = ["free", "starter", "pro", "enterprise"]
STATUSES = ["placed", "shipped", "delivered", "refunded", "cancelled"]
PRIORITIES = ["low", "medium", "high", "urgent"]
TICKET_STATUS = ["open", "pending", "resolved", "closed"]
COUNTRIES = ["Germany", "United States", "Japan", "France", "Brazil", "India",
             "Canada", "Australia", "Spain", "Italy", "Singapore", "Sweden"]

# (label, start, end) ISO windows over the order date range 2025-01-01..2026-12-28
YEARS = [("2025", "2025-01-01", "2025-12-31"), ("2026", "2026-01-01", "2026-12-31")]
QUARTERS = []
for _y in ("2025", "2026"):
    for _q, (_s, _e) in {"Q1": ("01-01", "03-31"), "Q2": ("04-01", "06-30"),
                         "Q3": ("07-01", "09-30"), "Q4": ("10-01", "12-31")}.items():
        QUARTERS.append((f"{_q} {_y}", f"{_y}-{_s}", f"{_y}-{_e}"))
PERIODS = YEARS + QUARTERS  # 10 windows

_REV = "status NOT IN ('refunded','cancelled')"
# spell out the line-item-revenue convention once, in plain English, for reuse
_LINE = "measured as the sum of line-item value (quantity x unit price) and excluding refunded and cancelled orders"


def _win(col: str, s: str, e: str) -> str:
    return f"{col} BETWEEN '{s}' AND '{e}'"


def pairs():
    """Yield (question, sql, difficulty). Correctness is by construction; volume
    comes from sweeping parameters over multi-table templates."""

    # ---- order-level revenue (2-table join; refund-exclusion implicit) ----------
    for r in REGIONS:                                          # region x period = 40
        for lbl, s, e in PERIODS:
            yield (f"What was the total revenue from {r} customers in {lbl}? "
                   f"Exclude refunded and cancelled orders. Return a single number.",
                   f"SELECT ROUND(SUM(o.total_amount),2) FROM orders o JOIN customers c ON o.customer_id=c.id "
                   f"WHERE c.region='{r}' AND {_win('o.ordered_at', s, e)} AND o.{_REV};", "medium")
    for ct in COUNTRIES:                                       # country x year = 24
        for lbl, s, e in YEARS:
            yield (f"What was the total revenue from customers in {ct} in {lbl}? "
                   f"Exclude refunded and cancelled orders. Return a single number.",
                   f"SELECT ROUND(SUM(o.total_amount),2) FROM orders o JOIN customers c ON o.customer_id=c.id "
                   f"WHERE c.country='{ct}' AND {_win('o.ordered_at', s, e)} AND o.{_REV};", "medium")

    # ---- average order value (2-table; refund-exclusion implicit) ---------------
    for r in REGIONS:                                          # region x period = 40
        for lbl, s, e in PERIODS:
            yield (f"What was the average order value for {r} customers in {lbl}? "
                   f"Ignore refunded and cancelled orders. Return a single number.",
                   f"SELECT ROUND(AVG(o.total_amount),2) FROM orders o JOIN customers c ON o.customer_id=c.id "
                   f"WHERE c.region='{r}' AND {_win('o.ordered_at', s, e)} AND o.{_REV};", "medium")

    # ---- category revenue (3-table join; formula STATED) ------------------------
    for cat in CATEGORIES:                                     # category x period = 40
        for lbl, s, e in PERIODS:
            yield (f"What was the total revenue from {cat} products in {lbl}, {_LINE}? Return a single number.",
                   f"SELECT ROUND(SUM(oi.qty*oi.unit_price),2) FROM order_items oi "
                   f"JOIN orders o ON oi.order_id=o.id JOIN products p ON oi.product_id=p.id "
                   f"WHERE p.category='{cat}' AND {_win('o.ordered_at', s, e)} AND o.{_REV};", "hard")
    for r in REGIONS:                                          # region x category x quarter (high card)
        for cat in CATEGORIES:
            for lbl, s, e in QUARTERS:
                yield (f"What was the total revenue from {cat} products sold to {r} customers in {lbl}, "
                       f"{_LINE}? Return a single number.",
                       f"SELECT ROUND(SUM(oi.qty*oi.unit_price),2) FROM order_items oi "
                       f"JOIN orders o ON oi.order_id=o.id JOIN products p ON oi.product_id=p.id "
                       f"JOIN customers c ON o.customer_id=c.id "
                       f"WHERE p.category='{cat}' AND c.region='{r}' AND {_win('o.ordered_at', s, e)} "
                       f"AND o.{_REV};", "hard")

    # ---- units sold by category (3-table) ---------------------------------------
    for cat in CATEGORIES:                                     # category x period = 40
        for lbl, s, e in PERIODS:
            yield (f"How many units of {cat} products were sold in {lbl}? "
                   f"Count quantity from line items, excluding refunded and cancelled orders. Return a single number.",
                   f"SELECT SUM(oi.qty) FROM order_items oi JOIN orders o ON oi.order_id=o.id "
                   f"JOIN products p ON oi.product_id=p.id "
                   f"WHERE p.category='{cat}' AND {_win('o.ordered_at', s, e)} AND o.{_REV};", "hard")

    # ---- order counts by status / region (1-2 table) ----------------------------
    for st in STATUSES:                                        # status x period = 50
        for lbl, s, e in PERIODS:
            yield (f"How many orders had status '{st}' in {lbl}? Return a single number.",
                   f"SELECT COUNT(*) FROM orders WHERE status='{st}' AND {_win('ordered_at', s, e)};", "easy")

    # ---- active subscriptions (canceled_at IS NULL implicit) --------------------
    for p in PLANS:                                            # plan = 4
        yield (f"What is the total monthly recurring revenue from active {p} subscriptions? Return a single number.",
               f"SELECT ROUND(SUM(mrr),2) FROM subscriptions WHERE plan='{p}' AND canceled_at IS NULL;", "medium")
    for p in PLANS:                                            # plan = 4
        yield (f"What is the average monthly recurring revenue of active {p} subscriptions? Return a single number.",
               f"SELECT ROUND(AVG(mrr),2) FROM subscriptions WHERE plan='{p}' AND canceled_at IS NULL;", "medium")
    for r in REGIONS:                                          # region = 4 (join + active)
        yield (f"What is the total monthly recurring revenue from active subscriptions held by {r} customers? "
               f"Return a single number.",
               f"SELECT ROUND(SUM(s.mrr),2) FROM subscriptions s JOIN customers c ON s.customer_id=c.id "
               f"WHERE c.region='{r}' AND s.canceled_at IS NULL;", "medium")
    for p in PLANS:                                            # plan x region active count = 16
        for r in REGIONS:
            yield (f"How many active {p} subscriptions are held by {r} customers? Return a single number.",
                   f"SELECT COUNT(*) FROM subscriptions s JOIN customers c ON s.customer_id=c.id "
                   f"WHERE s.plan='{p}' AND c.region='{r}' AND s.canceled_at IS NULL;", "medium")

    # ---- support tickets (lowercase enums) --------------------------------------
    for pr in PRIORITIES:                                      # priority x status = 16
        for ts in TICKET_STATUS:
            yield (f"How many {pr} priority support tickets are currently '{ts}'? Return a single number.",
                   f"SELECT COUNT(*) FROM support_tickets WHERE priority='{pr}' AND status='{ts}';", "easy")
    for r in REGIONS:                                          # region x priority = 16 (join)
        for pr in PRIORITIES:
            yield (f"How many {pr} priority support tickets were opened by {r} customers? Return a single number.",
                   f"SELECT COUNT(*) FROM support_tickets t JOIN customers c ON t.customer_id=c.id "
                   f"WHERE c.region='{r}' AND t.priority='{pr}';", "medium")

    # ---- active products (active=1 implicit) ------------------------------------
    for cat in CATEGORIES:                                     # category = 4
        yield (f"How many active products are in the {cat} category? Return a single number.",
               f"SELECT COUNT(*) FROM products WHERE category='{cat}' AND active=1;", "easy")
    for cat in CATEGORIES:                                     # category = 4
        yield (f"What is the average unit price of active products in the {cat} category? Return a single number.",
               f"SELECT ROUND(AVG(unit_price),2) FROM products WHERE category='{cat}' AND active=1;", "medium")

    # ---- customers acquired (date window on created_at) -------------------------
    for r in REGIONS:                                          # region x year = 12
        for y in ("2024", "2025", "2026"):
            yield (f"How many {r} customers signed up in {y}? Return a single number.",
                   f"SELECT COUNT(*) FROM customers WHERE region='{r}' "
                   f"AND {_win('created_at', y + '-01-01', y + '-12-31')};", "easy")

    # ---- top-N (LIMIT + tie rule STATED) ----------------------------------------
    for n in (3, 5, 10):                                       # top-N customers by rev = 12
        for lbl, s, e in YEARS + QUARTERS[:2]:
            yield (f"Who were the top {n} customers by revenue in {lbl}? Exclude refunded and cancelled orders. "
                   f"Return name and revenue, highest first; if two customers tie on revenue, order them by name.",
                   f"SELECT c.name, ROUND(SUM(o.total_amount),2) AS rev FROM orders o "
                   f"JOIN customers c ON o.customer_id=c.id "
                   f"WHERE {_win('o.ordered_at', s, e)} AND o.{_REV} "
                   f"GROUP BY c.id, c.name ORDER BY rev DESC, c.name LIMIT {n};", "hard")
    for n in (3, 5, 10):                                       # top-N products by units = 12
        for lbl, s, e in YEARS + QUARTERS[:2]:
            yield (f"What were the top {n} products by units sold in {lbl}? Exclude refunded and cancelled orders. "
                   f"Return product name and units, highest first; if two products tie on units, order them by name.",
                   f"SELECT p.name, SUM(oi.qty) AS units FROM order_items oi "
                   f"JOIN orders o ON oi.order_id=o.id JOIN products p ON oi.product_id=p.id "
                   f"WHERE {_win('o.ordered_at', s, e)} AND o.{_REV} "
                   f"GROUP BY p.id, p.name ORDER BY units DESC, p.name LIMIT {n};", "hard")

    # ---- HAVING (no LIMIT, so the result set is fully determined) ----------------
    for n in (5, 8, 10):                                       # customers > N orders = 9
        for lbl, s, e in YEARS + QUARTERS[:1]:
            yield (f"Which customers placed more than {n} orders in {lbl}? "
                   f"Return name and order count.",
                   f"SELECT c.name, COUNT(*) AS n FROM orders o JOIN customers c ON o.customer_id=c.id "
                   f"WHERE {_win('o.ordered_at', s, e)} GROUP BY c.id, c.name HAVING n > {n} "
                   f"ORDER BY n DESC, c.name;", "hard")

    # ---- grouped breakdowns (small fixed result; shape stated) ------------------
    for lbl, s, e in PERIODS[:6]:                              # category revenue breakdown = 6
        yield (f"Break revenue down by product category in {lbl}, {_LINE}. Return category and revenue.",
               f"SELECT p.category, ROUND(SUM(oi.qty*oi.unit_price),2) AS rev FROM order_items oi "
               f"JOIN orders o ON oi.order_id=o.id JOIN products p ON oi.product_id=p.id "
               f"WHERE {_win('o.ordered_at', s, e)} AND o.{_REV} GROUP BY p.category ORDER BY rev DESC, p.category;",
               "hard")
    for lbl, s, e in PERIODS[:6]:                              # order count by region = 6
        yield (f"How many non-refunded, non-cancelled orders did each region place in {lbl}? "
               f"Return region and order count.",
               f"SELECT c.region, COUNT(*) AS n FROM orders o JOIN customers c ON o.customer_id=c.id "
               f"WHERE {_win('o.ordered_at', s, e)} AND o.{_REV} GROUP BY c.region ORDER BY n DESC, c.region;",
               "medium")
    for lbl, s, e in PERIODS[:6]:                              # active MRR by plan = 6
        yield (f"Break the monthly recurring revenue of active subscriptions down by plan as of {lbl}. "
               f"Return plan and total MRR.",
               f"SELECT plan, ROUND(SUM(mrr),2) AS mrr FROM subscriptions "
               f"WHERE canceled_at IS NULL GROUP BY plan ORDER BY mrr DESC, plan;", "medium")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="cap new pairs (0 = no cap)")
    ap.add_argument("--out", default=_RAW)
    args = ap.parse_args()

    from skillopt.envs.bizsql.evaluator import canonicalize, run_sql

    seen_sql: set[str] = set()
    seen_res: set[str] = set()
    if os.path.isfile(args.out):
        for line in open(args.out, encoding="utf-8"):
            if not line.strip():
                continue
            row = json.loads(line)
            sql = row.get("gold_sql", "").strip()
            seen_sql.add(" ".join(sql.lower().split()))
            ok, res, _ = run_sql(sql, _DB, timeout=5)
            if ok and res:
                seen_res.add(repr(canonicalize(res)))
    print(f"[author] existing distinct results seen={len(seen_res)}")

    added = 0
    drop = {"exec": 0, "empty": 0, "wholetable": 0, "dup_sql": 0, "dup_result": 0}
    by_diff = {"easy": 0, "medium": 0, "hard": 0}
    with open(args.out, "a", encoding="utf-8") as out:
        for q, sql, diff in pairs():
            nsql = " ".join(sql.lower().split())
            if nsql in seen_sql:
                drop["dup_sql"] += 1
                continue
            ok, res, detail = run_sql(sql, _DB, timeout=5)
            if not ok:
                drop["exec"] += 1
                continue
            if not res or all(c is None for row in res for c in row):
                drop["empty"] += 1
                continue
            if len(res) > 50:
                drop["wholetable"] += 1
                continue
            sig = repr(canonicalize(res))
            if sig in seen_res:
                drop["dup_result"] += 1
                continue
            seen_sql.add(nsql)
            seen_res.add(sig)
            out.write(json.dumps({"question": q, "gold_sql": sql, "difficulty": diff,
                                  "archetype": "authored"}, ensure_ascii=False) + "\n")
            out.flush()
            added += 1
            by_diff[diff] = by_diff.get(diff, 0) + 1
            if args.limit and added >= args.limit:
                break

    print(f"[author] added {added} distinct pairs  drops={drop}")
    print(f"[author] difficulty mix of added: {by_diff}")
    print(f"[author] total distinct results now={len(seen_res)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
