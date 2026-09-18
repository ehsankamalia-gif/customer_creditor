# Module architecture

This project is a modular monolith: one Django process and one database, but
organized as independent modules (Django apps) that don't reach into each
other's internals.

## Modules

- **`accounts`** — the identity/platform module. Owns the `User` model,
  authentication (signup/login), and the "My Account" page. This is the one
  module every other module is allowed to depend on.
- **`staff`** — a workflow module for privileged account management (staff
  dashboard, user directory, staff/permission management, admin & staff
  account-creation screens). Talks to `accounts` only through its public API.
- **`inventory`** — owns the motorcycle stock (`ProductModel`, `Supplier`,
  `StockLocation`, `Motorcycle`). Doesn't depend on any other domain module.
  See `inventory/README.md` for its data model, status rules and how to
  extend it.
- **`credit`** — the credit/loan domain: `CreditSale`, `Installment` and
  `LedgerEntry`. A sale's customer is an `accounts` user (reached only via
  `accounts.services.list_customers()` / `get_manageable_user()`); a sale's
  item is optionally an `inventory` motorcycle (reached only via
  `inventory.services`). Exposes the customer-facing dashboard/ledger/payment
  screens and the staff-facing sales/payments/customer-ledger screens.
- **`spares`** — the shop's own spare-parts cash ledger
  (`SpareLedgerTransaction`, `SpareLedgerMonthlyClose`). Independent of
  `credit` — it tracks the shop's cash position, not a customer's balance.

## The rule

A module may only use another module's **public API**, never its internals:

- `<module>/services.py` — plain functions for reading/writing that module's
  data (e.g. `accounts.services.list_manageable_users()`).
- `<module>/forms.py` — Django forms for creating/editing that module's own
  models.
- `<module>/mixins.py` — reusable view mixins (e.g. access-control checks).

A module must **never**:

- `from <other_module>.models import X` and query it directly.
- Import another module's `views.py` or `api.py` — those are entry points
  (URL-routed), not APIs meant for other modules to call.

`accounts` is the exception that proves the rule: as the platform module it
depends on nothing else in this project. `staff` depends on `accounts`'s API
only (`accounts.services`, `accounts.forms`, `accounts.mixins`) — `accounts`
never imports anything from `staff`.

When a new domain module is added, follow the same recipe: it owns its own
models and exposes a `services.py`, and it reaches `accounts` only through
`accounts.services` / `accounts.forms` / `accounts.mixins` — never
`accounts.models`. `credit` follows this for both of its dependencies: it
reaches `accounts` through `accounts.services` and reaches `inventory`
through `inventory.services`. Peer modules never depend on each other
directly either; if two peer modules need to share data, that goes through
one of their `services.py` APIs, not a direct model import.

**Payoff**: changing `staff` never requires touching `accounts`, and changing
`accounts`'s internals never requires touching `staff`, as long as the public
API surface (`services.py`/`forms.py`/`mixins.py`) stays the same.
