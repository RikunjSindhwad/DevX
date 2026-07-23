---
id: database-design-and-indexing
title: Database Design & Indexing
type: pattern
tags: [database, sql, indexing, schema-design, normalization, transactions, migrations, oltp, olap, performance]
summary: How to design schemas for transactional and analytical workloads, use indexes effectively, avoid common query traps, and migrate data safely without downtime.
related:
  - {slug: owasp-top-10-quickref, rel: relates-to}
  - {slug: api-design, rel: relates-to}
  - {slug: test-strategy-and-flakiness, rel: see-also}
created: 2026-06-20
---

# Database Design & Indexing

Every persistent application eventually lives or dies by its data layer. Schema decisions made early are
expensive to reverse, index choices directly determine whether a query takes microseconds or minutes,
and transaction discipline is the difference between correct and subtly corrupted state.

This entry covers the principles that apply across relational systems (PostgreSQL, MySQL, SQLite) and
document stores (MongoDB, DynamoDB) alike — reaching for named examples only to ground a general rule.

## OLTP vs OLAP Workloads

**OLTP (Online Transaction Processing)** handles many short, concurrent reads and writes — a user
placing an order, updating a profile. Optimize for low latency per row, high concurrency, and write
throughput. Rows are narrow; foreign keys enforce integrity; indexes target equality and range lookups
on individual columns.

**OLAP (Online Analytical Processing)** handles fewer but heavier queries — aggregations over millions
of rows, full-table scans, joins spanning many tables. Optimize for read throughput and columnar access.
Wide, denormalized tables (star/snowflake schemas) reduce join costs at query time by paying a
write-time duplication price.

Running OLAP queries against an OLTP schema is a common performance trap; the right answer is a read
replica, a materialized view, or a dedicated analytical store, not just "add more indexes."

## Normalization and Deliberate Denormalization

**Normalization** removes redundancy by breaking data into canonical tables linked by foreign keys:

- **1NF** — each column holds one atomic value; no repeating groups.
- **2NF/3NF** — every non-key column depends on the whole key, and only on the key.
- **BCNF** — every determinant is a candidate key.

Third normal form is the practical target for most OLTP schemas: it minimizes update anomalies (changing a city name in one place, not fifty) and keeps write paths simple.

**Denormalization** is not a mistake — it is a deliberate trade. Duplicate a column, store a
precomputed count, or cache a join result when the read pattern justifies the write overhead. The
discipline is to decide consciously: document the duplication, enforce it via application logic or a
trigger, and test that divergence can't occur silently. Blindly denormalizing "for performance" before
measuring is premature optimization.

## How Indexes Work

An index is a secondary data structure that lets the database locate rows matching a predicate without a full table scan.

**B-tree indexes** (the default in every major relational database) maintain a balanced tree of key
values that points to heap rows. Lookups descend the tree in O(log N) steps. They serve equality (`=`),
ordered range (`<`, `>`, `BETWEEN`), and `ORDER BY` efficiently. Every write to a table that has a
B-tree index also updates the tree — indexes accelerate reads at the cost of write throughput and disk
space.

**Selectivity terminology varies**, so state the metric. Here, "highly selective" means a predicate
matches a small fraction of rows (high discriminating power), such as `user_id = 42` on a million-row
table; an index is often profitable. A predicate matching most rows, such as a status value present on
90% of rows, often leads the optimizer to prefer a sequential scan because index plus heap access costs
more than reading the table.

**Composite indexes** cover multiple columns. The column order matters: the index is useful for queries
that filter on a prefix of the declared columns. An index on `(country, created_at)` helps
`WHERE country = 'DE'` and `WHERE country = 'DE' AND created_at > '2025-01-01'` but does not help
`WHERE created_at > '2025-01-01'` alone (no leading column match). Choose order from the actual query
prefixes, equality/range predicates, sorting/grouping needs, and the database's planner; "most selective
first" is not a universal composite-index rule.

**Covering indexes** include every column the query needs, so the database never touches the heap at all
— the index satisfies the query entirely. In PostgreSQL the `INCLUDE (col)` clause adds non-key columns
to a B-tree index without affecting sort order. In MongoDB, a projection that matches an index is a
"covered query" for the same reason.

**Partial indexes** index only the rows matching a `WHERE` clause, yielding a smaller, faster structure: `CREATE INDEX ON orders (created_at) WHERE status = 'pending'` is far smaller than an index on all orders.

**Key rule:** measure before adding indexes. Use `EXPLAIN ANALYZE` (Postgres) or `.explain("executionStats")` (MongoDB) to see what the planner actually does, then add the minimum set of indexes that eliminates the bottleneck.

## The N+1 Query Problem

N+1 occurs when code fetches a list of N parent records and then issues one query per record to fetch children — producing N+1 round trips instead of 2. It is silent in development (small data) and catastrophic in production (large data).

**Pattern to recognize:**

```
orders = db.query("SELECT * FROM orders")   # 1 query
for order in orders:
    items = db.query("SELECT * FROM items WHERE order_id = ?", order.id)  # N queries
```

**Solutions:**
- **Join or subquery** — fetch parents and children together in one query.
- **Batch load** — collect all parent IDs, then `WHERE order_id IN (...)` to fetch all children at once, then correlate in application memory.
- **ORM eager loading** — most ORMs expose `include`/`eager_load`/`prefetch_related` to express the batch load declaratively; use it whenever traversing a one-to-many association.

In document databases, embedding child documents avoids N+1 at the schema level — at the cost of document size limits and update complexity. The right choice depends on read/write ratio and document growth.

## Transactions and Isolation Levels

A **transaction** groups operations into an atomic unit: all succeed or all roll back, leaving no partial state. The ACID properties (Atomicity, Consistency, Isolation, Durability) describe the contract.

**Isolation levels** trade anomaly protection against concurrency. The standard anomalies:

| Anomaly | Description |
|---|---|
| Dirty read | Seeing uncommitted data from another transaction |
| Non-repeatable read | Same row reads differently within one transaction |
| Phantom read | A re-run range query returns different rows |
| Lost update | Two transactions each read-then-write the same row; one clobbers the other |

| Level | Prevents |
|---|---|
| Read Uncommitted | (nothing) |
| Read Committed | Dirty reads |
| Repeatable Read | Dirty reads, non-repeatable reads, phantoms (in Postgres) |
| Serializable | All of the above + lost updates, write skew |

PostgreSQL's default is **Read Committed**: each statement sees a snapshot of committed data at
statement start. This handles most OLTP workloads. Use **Serializable** (or explicit
`SELECT ... FOR UPDATE`) when correctness requires that two transactions cannot both succeed after
reading the same rows — e.g., reserving the last seat, decrementing inventory.

In document databases (MongoDB since 4.0, DynamoDB transactions), multi-document transactions exist but
carry a higher cost; prefer single-document atomicity where possible by designing documents to contain
all data for one logical operation.

## Safe Migrations: Expand / Contract

Schema changes on live databases are among the highest-risk operations in a software project. The **expand / contract** pattern makes them safe by decoupling the structural change from the data change from the application cutover:

1. **Expand** — add the new column/table/index as nullable or with a default. Deploy the application that can write to both old and new structures. No downtime.
2. **Backfill** — populate the new column for existing rows in small batches (avoid a single enormous `UPDATE` that locks the table and blows the transaction log).
3. **Switch reads** — deploy the application version that reads from the new structure only.
4. **Contract** — drop the old column/table/index now that no code references it.

**Backward-compatible changes** (always safe): adding a nullable column, adding a table, adding an index `CONCURRENTLY` (Postgres), widening a `VARCHAR`.

**Breaking changes** (require expand/contract or a maintenance window): renaming a column, dropping a column, narrowing a type, adding a `NOT NULL` constraint without a default, changing a foreign key target.

Keep migrations in version control alongside the application code. Run them automatically in CI against
a copy of production data to catch surprises before they reach production. See
[[test-strategy-and-flakiness]] for guidance on making migration-dependent tests reliable.

## Quick Reference

| Decision | Lean toward |
|---|---|
| High-write, low-read table | Fewer indexes |
| High-read, low-write table | Covering indexes, partial indexes |
| Many small concurrent writes | OLTP normal form, row-level locking |
| Aggregation-heavy queries | Materialized views, OLAP schema, read replica |
| Schema change on live table | Expand/contract, `CREATE INDEX CONCURRENTLY` |
| Critical inventory / seat reservation | Serializable or `SELECT FOR UPDATE` |

---

> Source: https://use-the-index-luke.com/ · curated · 2026-06-20
