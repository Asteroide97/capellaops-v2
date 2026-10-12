# Superadmin Gate 2B: trial and access contract

## Source and storage

- `auth.register_verify` assigns `Empresa.trial_ends_at = now + timedelta(days=15)` after successful SMS verification. `now` is the UTC request clock; no external SMS is called by these tests.
- `trial_start` does not exist. `created_at` is audit metadata, not an authorization clock.
- `empresas.trial_ends_at` uses SQLAlchemy `DateTime(timezone=True)`. Offset-aware values describe instants; naive values returned by SQLite are interpreted as UTC in authorization, matching the existing auth convention.
- Login and `/me` expose `trial_ends_at`; Superadmin uses the same field, not a second expiration value.

## Product-approved state mapping

There are no independent company-active/payment-active flags. Payment integration and `estado_pago` are placeholders. Do not describe `access_status=active` as verified payment.

| Stored state | Operational module entitlement |
| --- | --- |
| `trial` | Allowed only while `trial_ends_at > now`; equality/missing expiration denies. |
| `active` | Administrative access right; old trial expiration does not revoke it. |
| `past_due` | Existing allowed policy retained; separate product decision pending. |
| `suspended`, `cancelled`, unknown | Denied. |

Inactive users are denied. Plans and existing module overrides still apply; basic grants only Inventory. The platform Superadmin permission remains separate from company operational entitlements.

`can_access_company` is the temporal predicate; `can_access_module` also checks the user, plan and overrides. Inventory, procurement, POS, CRM and PM reuse the latter in their protected request dependencies/services. No right is snapshotted into the JWT. Module payloads use one UTC clock sample per response.

Login authenticates identity. `/me` and `/modules` remain available to describe the session and disabled modules; authenticating or seeing the dashboard does not grant operational access. Company administration and the separate billing queue have their existing guards: this gate does not expand their permissions or add a global tenant lock. There is no refresh-token endpoint or new billing integration in this gate.

## Superadmin date editor

The old ISO string slice displayed UTC clock digits as local time and reinterpreted them when saving. The editor now converts the instant to the browser's local calendar fields, with second/millisecond support. Unchanged input sends the exact original API timestamp, retaining its offset and microseconds. Time/date edits convert once to UTC, preserving sub-millisecond digits when the represented fractional portion is unchanged. After saving, the form is mapped again from the returned timestamp. Invalid/nonexistent local calendar times do not reach the API. No company state or trial duration is changed by the timezone fix.

## Existing capacity rules (not modified)

- Basic plan seed: two users, one active warehouse. Counts are tenant-scoped.
- Users: active `EmpresaUsuario` memberships count, including owner; inactive memberships and pending invitations do not count. A globally inactive `Usuario` still counts if its membership remains active. Pending invitations do not reserve capacity under the existing contract.
- Warehouse active creation/reactivation is blocked at/above the limit. Inactive creation does not count. Legacy over-limit rows remain readable and are not removed.

## Validation and boundaries

Synthetic in-memory SQLite fixtures exercise real login, warehouse endpoints, tenant checks and Superadmin timestamp persistence; the test launcher rejects non-SQLite connections and disables `.env` loading. Frontend tests execute the real Superadmin load/save handlers and check Mexico City, UTC and a DST-overlap timezone.

No production session, Azure, manual SQL, migration file, real account, invitation, plan, payment or stored trial is changed. This gate does not prove payment processing or authorize a production simulation. Before release, expect previously expired `trial` tenants to lose operational module access; do not silently reclassify them as `active`.
