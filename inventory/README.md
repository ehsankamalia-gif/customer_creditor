# Inventory module

Tracks physical motorcycle stock: one row per physical unit, from the day
it's bought to the day it's sold (and, if needed, returned).

## Purpose

Owns everything about "what motorcycles does the dealership have, and what
state is each one in." Other modules (like `credit`) reference a unit by ID
through this module's public API — they never query its tables directly.

## Data model

- **ProductModel** — a model/variant the dealership carries (e.g. "CD 70").
  Lets `year`/`color`/etc. stay per-unit while model-level facts (make,
  engine capacity, tax codes) live in one place.
- **Supplier** — a vendor units are purchased from.
- **StockLocation** — a showroom/branch/warehouse a unit can sit in.
- **Motorcycle** — one physical unit. Key fields:
  - Identification: `chassis_number` (unique), `engine_number` (unique),
    `vin` (unique, optional), `product_model`, `year`, `color`.
  - Purchase: `purchase_supplier`, `purchase_reference` (the supplier's
    purchase/delivery order number), `purchase_price`, `purchase_date`.
  - Selling: `selling_price`.
  - Stock: `status`, `location`, `date_sold`.
  - Other: `notes`, `is_active` (soft delete), `created_at`, `updated_at`.

`ProductModel`, `Supplier` and `StockLocation` are lookup tables, not free
text — new models/suppliers/locations are added as data (through their own
"Add" screens or Django admin), never by editing code.

## Stock status

A fixed list (`Motorcycle.STATUS_CHOICES`), not free text:

| Status | Badge | Meaning |
|---|---|---|
| Available | green | Ready to sell |
| Reserved | amber | Held for a customer, not yet sold |
| Sold | gray | Sale finalized |
| In transit | blue | Purchased/allocated but not yet on the lot |
| Damaged | red | Not sellable in current condition |

**A sold unit cannot go back to any other status through the normal status
dropdown.** That's enforced in `services.change_status()`, not just the
UI — it's the one business rule in this module that isn't optional. Undoing
a sale is a separate, explicit action: `services.return_to_stock()` /
the "Return to Stock" button on the detail page.

## Business rules (enforced server-side, in models/services — not just forms)

- Chassis number and engine number must be unique (DB `unique=True` +
  form validation gives a clear "already exists" message instead of a raw
  database error).
- `purchase_price` and `selling_price` can't be negative
  (`MinValueValidator(0)`).
- `year` must be 1980 or later (`MinValueValidator(1980)`).
- Once a unit's status is `SOLD`, its chassis number, engine number, VIN,
  supplier, purchase price and purchase date can't be edited — the edit
  form drops those fields entirely rather than disabling them, since a
  disabled HTML field isn't submitted anyway and can't be trusted as the
  only safeguard.
- Deleting a unit means archiving it (`is_active = False`). There is no
  hard-delete in the UI — archived units are hidden from the default list
  and filters but never removed, so sold/transaction-linked history is
  never lost.

## Public API (`inventory/services.py`)

This is the only way another module should touch inventory data:

- `list_in_stock_motorcycles()` — units available for a new sale.
- `list_all_motorcycles(include_archived=False)`
- `search_motorcycles(query=, status=, product_model_id=, color=, location_id=, ordering=)`
  — the query behind the inventory list page's search/filter/sort.
- `get_motorcycle(pk)`
- `summary_stats()` — counts and totals for the dashboard.
- `mark_sold(motorcycle)` — called by `credit` when a credit sale is
  finalized against a linked unit.
- `change_status(motorcycle, new_status)` / `return_to_stock(motorcycle)`
- `archive_motorcycle(motorcycle)` / `restore_motorcycle(motorcycle)`
- `list_product_models()` / `list_suppliers()` / `list_locations()` /
  `list_colors_in_use()`

## Pages

| Page | URL name | Who |
|---|---|---|
| Dashboard (counts + stock/sales value) | `inventory:dashboard` | staff w/ `view_motorcycle` |
| Inventory list (search/filter/sort/paginate) | `inventory:inventory_list` | staff w/ `view_motorcycle` |
| Motorcycle detail | `inventory:motorcycle_detail` | staff w/ `view_motorcycle` |
| Add motorcycle | `inventory:add_motorcycle` | staff w/ `add_motorcycle` |
| Edit motorcycle | `inventory:edit_motorcycle` | staff w/ `change_motorcycle` |
| Change status / Return to stock | `inventory:change_status` / `inventory:return_to_stock` | staff w/ `change_motorcycle` |
| Archive / Restore | `inventory:archive_motorcycle` / `inventory:restore_motorcycle` | staff w/ `delete_motorcycle` |
| Add model / supplier / location | `inventory:add_product_model` / `add_supplier` / `add_location` | staff w/ the matching `add_*` permission |
| Import stock | `inventory:import_stock` | staff w/ `add_motorcycle` |

Permissions are Django's standard per-model `add_*`/`change_*`/`delete_*`/
`view_*` codenames — grant them to a staff member from **Manage Staff &
Permissions**; nothing inventory-specific needs configuring beyond that.

## Search

The inventory list filters server-side (see `search_motorcycles()`), so it
scales without loading the whole table into the browser. `q` does a partial,
case-insensitive match across chassis number, engine number, model name and
color in one query — searching "CD70" matches the model, "black" matches
the color, a chassis-number fragment matches partial chassis numbers.

## Importing stock from a supplier portal (`inventory/importers.py`)

**Import Stock** (on the dashboard and inventory list) loads or syncs stock
from an Excel (`.xlsx`) file, a CSV file, or a copy-pasted table — e.g. the
file behind a manufacturer's dealer portal "stock list" Export button.
There's no live connection to any external site: it reads a file you upload,
or text you paste, and nothing else. There's deliberately no automated login
to any third-party portal — a scripted login has to defeat whatever
anti-automation protections that site has (this portal's login page has a
CAPTCHA), which isn't something this module does even for your own account.

Recognized columns (matched flexibly on name): Purchase Order, Recv. Date,
Model, Colour, Engine No, Chassis No, Status. Unrecognized columns are
ignored, and a title/report-heading row above the real header (common in
these exports) is detected and skipped automatically.

How it behaves, by design:

- **New chassis number** → a new `Motorcycle` is created, auto-creating its
  `ProductModel` by name if needed. Pricing isn't in this kind of export, so
  new units are stored at price 0 and need their purchase/selling price set
  via Edit before they're sold.
- **Existing chassis number** → only `purchase_reference`, `purchase_date`
  and `status` are refreshed. Price, location and notes you've entered are
  never touched by an import.
- **A unit already `Sold` here** → an import can never move it to a
  different status. This is the same "no silent un-sell" rule
  `services.change_status()` enforces everywhere else, applied here too.
- Bad rows (e.g. a missing chassis number) are reported individually and
  skipped — one bad row never fails the whole file.
- Status words from the portal ("OK", "Sold", etc.) are mapped in
  `importers._STATUS_ALIASES`; add an entry there if a portal uses different
  wording.

Running the same file/paste twice is safe — the second run reports rows as
"already up to date" rather than duplicating or re-touching them, so this
can be re-run any time to pick up new deliveries or status changes.

## How to extend

- **Add a new model/color/location/status value that's just data**
  (a new motorcycle model, a new supplier, a new branch): use the "Add"
  screens or Django admin. No code change needed.
- **Add a new stock status**: add it to `Motorcycle.STATUS_CHOICES` in
  `models.py`, add a badge color in
  `templatetags/inventory_extras.py::_STATUS_BADGE_CLASSES`, run
  `makemigrations`. If the new status needs its own transition rule (like
  `SOLD` does), add it to `services.change_status()`.
- **Add a field**: add it to `Motorcycle`, run `makemigrations`, add it to
  the relevant form(s) in `forms.py`, add it to `motorcycle_detail.html`.
  If it should be locked after a sale, add its name to
  `Motorcycle.LOCKED_AFTER_SALE_FIELDS`.
- **Let another module use inventory data** (e.g. a future `sales` or
  `reports` module): add a function to `services.py` and call it from
  there — never import `inventory.models` from outside this app.
