# C01.1 - Global weighted inventory cost

## Write map

| File / function | Field | Previous behavior | New behavior / classification |
| --- | --- | --- | --- |
| api/routes/inventory.py / create_material | costo_unitario | Manual reference | MANUAL / REFERENCE, unchanged |
| api/routes/inventory.py / create_material | costo_promedio_actual | Initial supplied cost or reference; explicit zero treated as absent | Initial supplied cost (including zero) or reference; initialization only |
| api/routes/inventory.py / update_material | costo_unitario | Reference edit could replace missing/zero average | MANUAL / REFERENCE, never changes average |
| api/routes/inventory.py / update_material | costo_promedio_actual | Manually editable | Automatic after creation; differing edits rejected; identical legacy payload accepted |
| services/inventory.py / apply_inventory_movement, explicit entry or positive adjustment | Both costs | Replaced both with incoming cost | MUST RECALCULATE average only; reference unchanged |
| Same service, entry without cost | Both costs | Could assign a resolved warehouse/global fallback | Uses global current average; reference only seeds missing average |
| Same service, exit/negative adjustment | Average | Negative adjustment could replace average | MUST NOT CHANGE average; uses current global cost |
| inventory_documents.py / confirm_transfer | Indirect writes through movement service | Destination entry replaced global average with document snapshot | MUST NOT CHANGE average; both movements use current average, even if draft snapshot is old |
| inventory_documents.py / apply_count | Indirect writes through adjustment | Quantity adjustment could populate average via fallback | Current average, no explicit acquisition; no economic revaluation |
| procurement.py / receive_purchase_order | Indirect writes through entry | Receipt replaced both costs | MUST RECALCULATE using received quantity and line cost |
| inventory.py / return_material_from_project | Indirect entry | Replaced average at return cost | MUST RECALCULATE at original outgoing snapshot, per product decision |
| pos.py / cancel_sale | Indirect entry | Returned at current cost | MUST RECALCULATE at original outgoing snapshot, per product decision |

There is no other production assignment to Material's reference or average outside these paths.
PM budget component costs are separate records, not mutations of Material.

## Central calculation and precision

`weighted_average_cost(Q, C, q, c)` returns `(Q*C + q*c)/(Q+q)`.
If Q is zero it returns c; if q is zero it preserves C.
Decimal arithmetic uses a local precision of 50 and ROUND_HALF_UP to 0.0001.
No float is used for persisted cost calculations. Fractional quantities are supported.
The stock quantity is the sum of all warehouses for the tenant/material before the operation.
NULL average uses the reference as an initial basis, without backfill. Zero average is a real zero cost.
Explicit incoming zero is allowed by the existing nonnegative cost contract.
Reference changes do not change an existing average, including NULL or zero.
Each operation persists the rounded four-decimal average. Repeated partial receipts can
accumulate very small rounding residuals; no extra precision/value ledger is introduced.
At cutover, the existing stock and its current stored cost are the opening balance, even
if that stored cost previously represented last cost. For example, 9@30 + 1@10 produces 28.
This is a forward policy change, not a reconstruction or correction of historical inventory.

## Movement rules

- Entry 5@10 + 5@30: quantity 10, average 20, current value 200.
- Exit 3 from 10@20: quantity 7, average 20, current value 140.
- Zero stock followed by entry 5@30: average 30.
- Positive adjustment +5@40 from 5@20: average 30.
- Positive adjustment without acquisition cost: uses current average.
- Negative adjustment: ignores supplied acquisition cost and preserves average.
- Only the internal confirm_transfer service marks its paired legs with is_transfer=True;
  a caller-supplied reference cannot bypass weighting. Both legs use current average;
  the captured draft cost cannot overwrite it.
- Physical counts carry no acquisition cost and preserve the economic basis.
- OC partial receipts weight each received quantity at the line acquisition cost.
- PM return uses the last applicable outgoing snapshot resolver, honoring the cost originally read
  by PM (legacy average-first, new applied cost). This does not introduce lot tracking.
- POS cancellation uses the original sale movement cost. Payments and cancellation status flow are unchanged.

## Locking and transactions

All movement writes first acquire the tenant/material row, before reading local or global quantity.
SQL Server uses SQLAlchemy `WITH (UPDLOCK, HOLDLOCK)`; PostgreSQL uses FOR UPDATE.
SQLAlchemy refreshes cached ORM state on that read.
A conditional update of Material.costing_token performs compare-and-swap, then refreshes the material.
This also serializes SQLite writers; a stale token returns a business HTTP 409 and must be retried.
The caller owns the transaction. No commit was introduced into movement services.
The inventory route's existing exception handling rolls back claims, quantities and snapshots together.
Multi-material operations can encounter database deadlocks/busy errors: retry the whole rolled-back request,
never a partially completed line. Direct database writes outside this protocol are not supported.
SQLite concurrency and real query compilation for MSSQL/PostgreSQL are tested locally.
SQL Server driver/locking behavior has NOT been exercised against Azure in this gate.

## Snapshot contract and necessary migration

New movements have costing_policy = weighted_global_v1.
Their costo_unitario_snapshot is the applied movement cost (acquisition for entries, current average for exits).
Their costo_promedio_snapshot is the global average after the operation.
The historical warehouse balance shown in Kardex uses quantity_nueva times that snapshot average.
PM/POS real cost and margin must use the applied cost, including legitimate zero costs.

Migration 20261006_0049 adds two nullable columns with no defaults or data updates:

- movimientos_inventario.costing_policy: distinguishes new snapshot semantics from legacy records.
- materiales.costing_token: portable optimistic concurrency protection, without a stock/cost backfill.

The marker is necessary because legacy PM reads average snapshot first, while a new return's
average after reception can differ from its original applied cost. Legacy interpretation is retained.
The token is necessary because SQLite ignores FOR UPDATE; lost updates must not be silently accepted.
No legacy movement is relabeled or rewritten. No quantities are repaired or historical costs recomputed.
The migration must precede running this version of the application; no deployment is performed by this gate.
Downgrade removes these fields and therefore loses the new semantic markers; do not operationally roll
back to the old costing implementation after new economic movements without a separate reviewed plan.

## Consumers and UI

PM event serialization, material cost summary, new consumption creation and the diagnostic repair
calculator use the shared applied-cost reader; legacy reads retain their previous priority.
POS uses new applied snapshots for margin and for cancellation reentry; manual service lines are unchanged.
Inventory margin alerts preserve old fallback behavior for legacy movements and honor new zero snapshots.
Current value is global quantity times current average (reference only when average is absent).
F04 retains local quantity times global cost and legacy ambiguity labeling. A consistent zero value
with zero average is now unambiguously local, even if reference is positive.
The Materials form permits initial average only at creation, sends no average on edits and shows it read-only.
Kardex labels its current base as global weighted average. Existing CSV and historical snapshots stay intact.

## Test coverage

test_inventory_weighted_cost.py covers T1-T20, fractional precision, null/zero, global warehouse stock,
legacy/new PM and POS snapshots, real PM returns, POS cancellation, rollback and tenant isolation.
Two simultaneous SQLite sessions start from the same material state; one succeeds and one receives 409.
Retrying the rejected entry produces quantity 15 / average 30 with exactly two movements.
Migration upgrade/downgrade is tested on an explicit temporary SQLite URL, with unchanged legacy snapshots.
inventoryWeightedCost.test.js covers F04 weighted values and read-only/edit payload behavior.
Existing inventory and PM regressions must remain passing. No Azure integration or authenticated browser
smoke is claimed by these tests. No commit, push, deployment or production migration is performed.

## C01.3 - Precision and project return blockers

Quantity4 and validate_quantity_precision share one Decimal-only representability rule.
1.2345 and 1.23450000 are accepted without a value change; 1.23456 and 0.00004 are rejected.
Quantity signs and zero eligibility retain each endpoint's existing constraints.
Movement, transfer, count, requisition, purchase receipt, PM consumption/return and POS line
request schemas use the shared contract. Cost/reference/price rounding is not changed.
Services also validate before locks; a bulk batch preflights every quantity before its first line.
No existing quantities are normalized, rounded or repaired.

Project returns now claim the tenant/material before reading net confirmed consumption or
selecting its applicable cost snapshot. Both reads and the inventory/PM writes share the
caller's transaction. The common ledger writer also enforces the limit for project-return
entries, preventing alternate movement entry points from bypassing it.
Net returnable consumption depends only on confirmed project-linked inventory movements.
Every production writer of those immutable rows uses apply_inventory_movement and the same
material exclusion; manual PM consumption rows are not inventory-returnable ledger rows.
No separate consumption-row lock or new migration is required.
The existing MSSQL hints and portable token compare-and-swap are reused, with no internal commit.

Regression tests cover Q1-Q8 and R1-R6, including a deterministic two-session interleaving
that accepted both returns before the fix. It now permits one and rejects the other with 409,
leaving stock 10, net consumption 0 and project real cost 0. Rollback after the real movement
flush preserves stock, average, token, movement count and the PM summary.
Migration 0049 is unchanged; SQL Server execution and deployment remain separate gates.

## C01.4 - Real isolated SQL Server validation: PASS

Validated on local .\SQLEXPRESS using ODBC Driver 18 and Windows integrated authentication.
CapellaOps_C01_4_QA was created empty and used only synthetic fixtures. No database was copied,
no production connection was used and backend/.env loading was disabled.
0049 upgrade/downgrade passed with nullable fields, no defaults and unchanged legacy business rows.
Real hints held the material lock until transaction end; a different material operated independently.
The driver returned rowcount 0 for a stale token (409); retry succeeded. E1-E5, precision,
post-flush rollback and legacy NULL interpretation passed on real SQL Server.
Three concurrent entry runs ended at quantity 15 / average 30 / two movements.
Three concurrent PM returns applied once and rejected the second (409), ending at net 0,
stock 10 and project real cost 0. Partial returns 1 + 2 passed.
The QA database and temporary harness were deleted; evidence is stored outside the repository.
No Azure, production migration, deployment, commit or backfill was performed.

## C01.5 - Final audit scoped-return hardening

A general project return can leave a task/item-filtered ledger subtotal positive even though
the project's overall material balance is exhausted. Return validation now caps the filtered
balance with the global project/material balance, under the same material exclusion.
No return is allocated retroactively to tasks or budget items; historical rows are unchanged.
Both the PM return path and the common ledger writer use this bound.
This final fix has local regression and MSSQL query compilation coverage; C01.4 real SQL Server
evidence predates it and must not be presented as an execution of the new scoped-return scenario.
