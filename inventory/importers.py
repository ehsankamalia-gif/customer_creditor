"""Bulk-import motorcycle stock from a supplier's dealer portal "stock list"
export - as a CSV/TSV file, an Excel (.xlsx) file (the common format for
"Export" buttons on these portals), or pasted table text.

Kept separate from services.py because parsing and mapping external data is
a different concern from this module's normal CRUD/business-rule API - but
every record it creates or updates still goes through the same Motorcycle
model, so the same constraints (unique chassis/engine, price >= 0) and the
same "a sold unit is never silently un-sold" rule apply automatically.
"""
import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal

import openpyxl

from .models import Motorcycle, ProductModel

# Recognized column headers, normalized (lowercased, non-alphanumeric
# stripped) so "Recv.Date", "Recv Date" and "Received Date" all match the
# same field - portals rarely spell their column headers the same way twice.
_HEADER_ALIASES = {
    'purchaseorder': 'purchase_reference',
    'deliveryorder': 'purchase_reference',
    'po': 'purchase_reference',
    'ponumber': 'purchase_reference',
    'recvdate': 'purchase_date',
    'receiveddate': 'purchase_date',
    'receiptdate': 'purchase_date',
    'model': 'model_name',
    'colour': 'color',
    'color': 'color',
    'engineno': 'engine_number',
    'engine': 'engine_number',
    'enginenumber': 'engine_number',
    'chassisno': 'chassis_number',
    'chassis': 'chassis_number',
    'chassisnumber': 'chassis_number',
    'framenumber': 'chassis_number',
    'status': 'status',
}

# The portal's own status words, mapped onto our fixed status list.
# Anything not recognized here falls back to the import's default status.
_STATUS_ALIASES = {
    'sold': Motorcycle.SOLD,
    'ok': Motorcycle.AVAILABLE,
    'available': Motorcycle.AVAILABLE,
    'instock': Motorcycle.AVAILABLE,
    'intransit': Motorcycle.IN_TRANSIT,
    'transit': Motorcycle.IN_TRANSIT,
    'reserved': Motorcycle.RESERVED,
    'booked': Motorcycle.RESERVED,
    'damaged': Motorcycle.DAMAGED,
}

_DATE_FORMATS = ['%d-%b-%Y', '%d-%B-%Y', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']


def _normalize(text):
    return re.sub(r'[^a-z0-9]', '', (text or '').strip().lower())


def _parse_date(value):
    value = (value or '').strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _cell_text(value):
    """Excel cells come back as native Python types (dates, numbers) rather
    than strings - normalize everything to text the same way a CSV cell
    would already be, so the rest of the parser doesn't need to care which
    format the data came from."""
    if value is None:
        return ''
    if isinstance(value, (datetime, date)):
        return value.strftime('%Y-%m-%d')
    return str(value).strip()


def _looks_like_xlsx(file_obj, filename):
    if filename and filename.lower().endswith(('.xlsx', '.xlsm')):
        return True
    # Fall back to sniffing the ZIP magic bytes, in case the upload lost
    # its filename/extension along the way.
    if hasattr(file_obj, 'seek'):
        position = file_obj.tell()
        head = file_obj.read(4)
        file_obj.seek(position)
        return isinstance(head, bytes) and head[:2] == b'PK'
    return False


def _read_xlsx_rows(file_obj):
    workbook = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        rows = []
        for row in sheet.iter_rows(values_only=True):
            cells = [_cell_text(c) for c in row]
            if any(cells):
                rows.append(cells)
        return rows
    finally:
        workbook.close()


def _read_delimited_rows(content):
    try:
        sample = '\n'.join(content.splitlines()[:5])
        dialect = csv.Sniffer().sniff(sample, delimiters=',\t;')
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(content), dialect)
    return [r for r in reader if any(cell.strip() for cell in r)]


def _find_header_row(raw_rows):
    """Return the index of the row that actually looks like our header.

    Real-world exports often put a title or date-range line above the
    table ("AHL Dealer Stock Report - 18 Sep 2026"), so the header isn't
    always row 0. A row counts as the header once at least two of its
    cells match a known column name.
    """
    for index, row in enumerate(raw_rows[:10]):
        matches = sum(1 for cell in row if _HEADER_ALIASES.get(_normalize(cell)))
        if matches >= 2:
            return index
    return 0


def parse_stock_rows(file_or_text):
    """Turn a CSV/TSV file, an .xlsx file, or raw pasted text into
    normalized dict rows.

    Unrecognized columns are dropped; a row missing required data is kept
    (with whatever it has) so import_stock_rows() can report exactly which
    row failed and why, rather than the whole file failing silently.
    """
    filename = getattr(file_or_text, 'name', '') or ''

    if hasattr(file_or_text, 'read'):
        if _looks_like_xlsx(file_or_text, filename):
            raw_rows = _read_xlsx_rows(file_or_text)
        else:
            content = file_or_text.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8-sig')
            raw_rows = _read_delimited_rows(content.strip())
    else:
        raw_rows = _read_delimited_rows(file_or_text.strip())

    if len(raw_rows) < 2:
        return []

    header_row_index = _find_header_row(raw_rows)
    header = [_HEADER_ALIASES.get(_normalize(h)) for h in raw_rows[header_row_index]]

    parsed = []
    for line_number, raw_row in enumerate(raw_rows[header_row_index + 1:], start=header_row_index + 2):
        data = {'_line': line_number}
        for key, value in zip(header, raw_row):
            if key:
                data[key] = value.strip() if isinstance(value, str) else _cell_text(value)
        parsed.append(data)
    return parsed


def import_stock_rows(rows, *, default_status=Motorcycle.AVAILABLE):
    """Create/update Motorcycle records from parsed portal rows.

    Matching is by chassis number. For a unit that already exists, only
    the fields a supplier portal is actually authoritative for - purchase
    reference/date and status - are refreshed; price, location and notes
    (dealer-entered business data) are never touched by an import. A unit
    already marked Sold in our system is never moved to a different status
    by an import, matching the same rule services.change_status() enforces
    everywhere else - the portal can confirm a sale, but nothing should be
    able to quietly un-sell one.

    Price isn't available from this kind of export, so newly-created units
    are stored at 0 and need their pricing filled in via Edit before sale.
    """
    created, updated, unchanged = 0, 0, 0
    errors = []

    for row in rows:
        line = row.get('_line', '?')
        chassis = (row.get('chassis_number') or '').upper()
        engine = (row.get('engine_number') or '').upper()
        model_name = (row.get('model_name') or '').strip()

        if not chassis or not engine or not model_name:
            errors.append(f'Row {line}: missing chassis number, engine number or model - skipped.')
            continue

        purchase_date = _parse_date(row.get('purchase_date'))
        status = _STATUS_ALIASES.get(_normalize(row.get('status')), default_status)

        existing = Motorcycle.objects.filter(chassis_number__iexact=chassis).first()

        if existing is None:
            product_model, _created = ProductModel.objects.get_or_create(
                model_name__iexact=model_name, defaults={'model_name': model_name},
            )
            try:
                Motorcycle.objects.create(
                    product_model=product_model,
                    chassis_number=chassis,
                    engine_number=engine,
                    color=row.get('color', ''),
                    year=(purchase_date or datetime.now().date()).year,
                    purchase_reference=row.get('purchase_reference', ''),
                    purchase_date=purchase_date or datetime.now().date(),
                    purchase_price=Decimal('0'),
                    selling_price=Decimal('0'),
                    status=status,
                    date_sold=purchase_date if status == Motorcycle.SOLD else None,
                )
                created += 1
            except Exception as exc:
                errors.append(f'Row {line}: could not import chassis {chassis} - {exc}')
            continue

        changed_fields = []
        if row.get('purchase_reference') and existing.purchase_reference != row['purchase_reference']:
            existing.purchase_reference = row['purchase_reference']
            changed_fields.append('purchase_reference')
        if purchase_date and existing.purchase_date != purchase_date:
            existing.purchase_date = purchase_date
            changed_fields.append('purchase_date')
        if existing.status != Motorcycle.SOLD and status != existing.status:
            existing.status = status
            changed_fields.append('status')
            if status == Motorcycle.SOLD:
                existing.date_sold = purchase_date
                changed_fields.append('date_sold')

        if changed_fields:
            existing.save(update_fields=changed_fields)
            updated += 1
        else:
            unchanged += 1

    return {
        'created': created,
        'updated': updated,
        'unchanged': unchanged,
        'errors': errors,
    }
