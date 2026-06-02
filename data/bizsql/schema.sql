-- ============================================================================
-- BizSQL: a fixed synthetic e-commerce / SaaS schema for the SkillOpt
-- Text-to-SQL track. Six tables. Deterministically seeded by
-- scripts/seed_bizsql_db.py (random.Random(7)) into data/bizsql/business.sqlite.
--
-- CONVENTIONS the skill must learn (these are the procedural headroom — a 7B
-- that ignores them produces runnable-but-wrong results):
--
--   * Dates are ISO TEXT 'YYYY-MM-DD' (lexicographic compare works for ranges).
--   * orders.status is lowercase in {placed, shipped, delivered, refunded, cancelled}.
--   * support_tickets.status is lowercase in {open, pending, resolved, closed}.
--   * priority is lowercase in {low, medium, high, urgent}.
--   * REVENUE excludes refunded AND cancelled orders
--       => WHERE status NOT IN ('refunded','cancelled').
--   * products.active is 0/1; "active products" => active = 1.
--   * An ACTIVE subscription has canceled_at IS NULL; MRR sums only those.
--   * Money columns are REAL; round to 2 dp when the question asks for an amount.
--   * Join keys: orders.customer_id->customers.id, order_items.order_id->orders.id,
--       order_items.product_id->products.id, subscriptions.customer_id->customers.id,
--       support_tickets.customer_id->customers.id.
-- ============================================================================

DROP TABLE IF EXISTS support_tickets;
DROP TABLE IF EXISTS subscriptions;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    country     TEXT    NOT NULL,   -- e.g. 'Germany', 'United States'
    region      TEXT    NOT NULL,   -- one of: EU, NA, APAC, LATAM
    created_at  TEXT    NOT NULL    -- ISO 'YYYY-MM-DD'
);

CREATE TABLE products (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    category    TEXT    NOT NULL,   -- e.g. 'Software', 'Hardware', 'Accessories', 'Services'
    unit_price  REAL    NOT NULL,
    active      INTEGER NOT NULL    -- 0 or 1
);

CREATE TABLE orders (
    id            INTEGER PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES customers(id),
    ordered_at    TEXT    NOT NULL,  -- ISO 'YYYY-MM-DD'
    status        TEXT    NOT NULL,  -- placed | shipped | delivered | refunded | cancelled
    total_amount  REAL    NOT NULL   -- denormalized order total (sum of its order_items)
);

CREATE TABLE order_items (
    id          INTEGER PRIMARY KEY,
    order_id    INTEGER NOT NULL REFERENCES orders(id),
    product_id  INTEGER NOT NULL REFERENCES products(id),
    qty         INTEGER NOT NULL,
    unit_price  REAL    NOT NULL   -- price at order time (may differ from products.unit_price)
);

CREATE TABLE subscriptions (
    id           INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(id),
    plan         TEXT    NOT NULL,  -- 'free' | 'starter' | 'pro' | 'enterprise'
    mrr          REAL    NOT NULL,  -- monthly recurring revenue for this subscription
    started_at   TEXT    NOT NULL,  -- ISO 'YYYY-MM-DD'
    canceled_at  TEXT             -- ISO 'YYYY-MM-DD' or NULL (NULL => still active)
);

CREATE TABLE support_tickets (
    id           INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(id),
    opened_at    TEXT    NOT NULL,  -- ISO 'YYYY-MM-DD'
    priority     TEXT    NOT NULL,  -- low | medium | high | urgent
    status       TEXT    NOT NULL   -- open | pending | resolved | closed
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);
CREATE INDEX idx_subscriptions_customer ON subscriptions(customer_id);
CREATE INDEX idx_tickets_customer ON support_tickets(customer_id);
