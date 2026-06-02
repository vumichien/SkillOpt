#!/usr/bin/env python3
"""Deterministically seed data/bizsql/business.sqlite from data/bizsql/schema.sql.

Pure stdlib (``random.Random(7)``) — no faker dependency. Idempotent:
drops+recreates every table from the schema, then inserts a fixed synthetic
dataset. Re-running produces a byte-stable row set (same seed, same order).

Commit ``schema.sql`` + this seeder, NOT the ``.sqlite`` (regenerate on demand;
the .sqlite is gitignored).

Usage
-----
    python scripts/seed_bizsql_db.py
    python scripts/seed_bizsql_db.py --db data/bizsql/business.sqlite --check
"""
from __future__ import annotations

import argparse
import os
import random
import sqlite3

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_SCHEMA = os.path.join(_PROJECT_ROOT, "data", "bizsql", "schema.sql")
_DEFAULT_DB = os.path.join(_PROJECT_ROOT, "data", "bizsql", "business.sqlite")

_SEED = 7
_N_CUSTOMERS = 300
_N_PRODUCTS = 120
_N_ORDERS = 2000
_N_SUBSCRIPTIONS = 400
_N_TICKETS = 600

_REGIONS = {
    "EU": ["Germany", "France", "Spain", "Italy", "Netherlands", "Sweden"],
    "NA": ["United States", "Canada", "Mexico"],
    "APAC": ["Japan", "Australia", "Singapore", "India"],
    "LATAM": ["Brazil", "Argentina", "Chile"],
}
_CATEGORIES = ["Software", "Hardware", "Accessories", "Services"]
_ORDER_STATUS = ["placed", "shipped", "delivered", "refunded", "cancelled"]
_ORDER_STATUS_WEIGHTS = [10, 15, 50, 8, 7]  # delivered most common
_PLANS = [("free", 0.0), ("starter", 29.0), ("pro", 99.0), ("enterprise", 499.0)]
_PRIORITIES = ["low", "medium", "high", "urgent"]
_TICKET_STATUS = ["open", "pending", "resolved", "closed"]
_FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie",
          "Avery", "Quinn", "Drew", "Skyler", "Cameron", "Reese", "Devon", "Harper"]
_LAST = ["Smith", "Johnson", "Lee", "Garcia", "Muller", "Rossi", "Tanaka", "Silva",
         "Dubois", "Nguyen", "Kim", "Patel", "Andersson", "Costa", "Novak", "Khan"]


def _iso_date(rng: random.Random, start_year: int = 2024, end_year: int = 2026) -> str:
    """Random ISO date in [start_year-01-01, end_year-12-31] (no real calendar math needed)."""
    year = rng.randint(start_year, end_year)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)  # 28 keeps every month valid without leap-year logic
    return f"{year:04d}-{month:02d}-{day:02d}"


def _seed(db_path: str) -> None:
    rng = random.Random(_SEED)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)  # idempotent: start from a clean file

    with open(_SCHEMA, encoding="utf-8") as f:
        schema_sql = f.read()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(schema_sql)

    # customers
    customers = []
    for cid in range(1, _N_CUSTOMERS + 1):
        region = rng.choice(list(_REGIONS))
        country = rng.choice(_REGIONS[region])
        name = f"{rng.choice(_FIRST)} {rng.choice(_LAST)}"
        customers.append((cid, name, country, region, _iso_date(rng, 2024, 2025)))
    cur.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", customers)

    # products
    products = []
    for pid in range(1, _N_PRODUCTS + 1):
        category = rng.choice(_CATEGORIES)
        price = round(rng.uniform(5, 500), 2)
        active = 1 if rng.random() > 0.15 else 0
        products.append((pid, f"{category} Item {pid}", category, price, active))
    cur.executemany("INSERT INTO products VALUES (?,?,?,?,?)", products)

    # orders + order_items (total_amount denormalized = sum of its items)
    orders = []
    order_items = []
    item_id = 1
    for oid in range(1, _N_ORDERS + 1):
        customer_id = rng.randint(1, _N_CUSTOMERS)
        status = rng.choices(_ORDER_STATUS, weights=_ORDER_STATUS_WEIGHTS, k=1)[0]
        ordered_at = _iso_date(rng, 2025, 2026)
        n_lines = rng.randint(1, 5)
        total = 0.0
        for _ in range(n_lines):
            product_id = rng.randint(1, _N_PRODUCTS)
            qty = rng.randint(1, 6)
            unit_price = round(rng.uniform(5, 500), 2)
            order_items.append((item_id, oid, product_id, qty, unit_price))
            total += qty * unit_price
            item_id += 1
        orders.append((oid, customer_id, ordered_at, status, round(total, 2)))
    cur.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", orders)
    cur.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", order_items)

    # subscriptions (~35% canceled => canceled_at set)
    subscriptions = []
    for sid in range(1, _N_SUBSCRIPTIONS + 1):
        customer_id = rng.randint(1, _N_CUSTOMERS)
        plan, mrr = rng.choice(_PLANS)
        started_at = _iso_date(rng, 2024, 2025)
        canceled_at = _iso_date(rng, 2025, 2026) if rng.random() < 0.35 else None
        subscriptions.append((sid, customer_id, plan, mrr, started_at, canceled_at))
    cur.executemany("INSERT INTO subscriptions VALUES (?,?,?,?,?,?)", subscriptions)

    # support_tickets
    tickets = []
    for tid in range(1, _N_TICKETS + 1):
        customer_id = rng.randint(1, _N_CUSTOMERS)
        tickets.append((
            tid, customer_id, _iso_date(rng, 2025, 2026),
            rng.choice(_PRIORITIES), rng.choice(_TICKET_STATUS),
        ))
    cur.executemany("INSERT INTO support_tickets VALUES (?,?,?,?,?)", tickets)

    conn.commit()
    conn.close()


def _check(db_path: str) -> bool:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    ok = True
    for table, expected in (
        ("customers", _N_CUSTOMERS), ("products", _N_PRODUCTS),
        ("orders", _N_ORDERS), ("subscriptions", _N_SUBSCRIPTIONS),
        ("support_tickets", _N_TICKETS),
    ):
        n = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  [check] {table}: {n}")
        if n != expected:
            print(f"  [check] MISMATCH {table}: got {n}, expected {expected}")
            ok = False
    n_items = cur.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
    print(f"  [check] order_items: {n_items}")
    conn.close()
    return ok


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=_DEFAULT_DB)
    p.add_argument("--check", action="store_true", help="row-count check on an existing DB (no reseed)")
    args = p.parse_args()

    if args.check:
        ok = _check(args.db)
        print("check:", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    _seed(args.db)
    print(f"  seeded {args.db}")
    ok = _check(args.db)
    print("check:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
