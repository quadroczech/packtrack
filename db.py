"""PostgreSQL database layer for PackTrack."""
import os
import psycopg2
import psycopg2.extras
import psycopg2.pool
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ── Connection pool – reuses connections instead of opening a new one per request
_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=DATABASE_URL,
        )
    return _pool


@contextmanager
def get_conn():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def init_db():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pt_materials (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                weight_g NUMERIC(10,4) NOT NULL DEFAULT 0,
                supplier VARCHAR(200),
                ekokom_sheet VARCHAR(10) DEFAULT 'J1-1A',
                ekokom_material VARCHAR(50),
                ekokom_form VARCHAR(20) DEFAULT 'soft',
                ekokom_origin VARCHAR(30) DEFAULT 'domestic_primary',
                naturpack_material VARCHAR(50),
                naturpack_appendix VARCHAR(20) DEFAULT 'consumer',
                active BOOLEAN DEFAULT TRUE,
                notes TEXT,
                initial_stock INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pt_receipts (
                id SERIAL PRIMARY KEY,
                material_id INTEGER REFERENCES pt_materials(id),
                receipt_date DATE NOT NULL,
                quantity_pcs INTEGER NOT NULL,
                price_per_unit NUMERIC(10,4),
                supplier_invoice VARCHAR(100),
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pt_inventory (
                id SERIAL PRIMARY KEY,
                material_id INTEGER REFERENCES pt_materials(id),
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                closing_stock_pcs INTEGER NOT NULL,
                notes TEXT,
                entered_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(material_id, year, month)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pt_country_distribution (
                id SERIAL PRIMARY KEY,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                country_code VARCHAR(5) NOT NULL,
                country_name VARCHAR(100) NOT NULL,
                percentage NUMERIC(5,2) NOT NULL DEFAULT 0,
                report_ekokom BOOLEAN DEFAULT FALSE,
                report_naturpack BOOLEAN DEFAULT FALSE,
                report_annual BOOLEAN DEFAULT FALSE,
                UNIQUE(year, quarter, country_code)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pt_settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            INSERT INTO pt_settings (key, value) VALUES
                ('company_name', 'Czech Wool company s.r.o.'),
                ('company_address', 'Šedesátá 7015, 760 01 Zlín'),
                ('company_ico', '03922391'),
                ('company_dic', 'CZ03922391'),
                ('ekokom_id', 'R00230068'),
                ('contact_person', 'Fiala Adam'),
                ('contact_phone', '774 774 217'),
                ('contact_email', 'adam.fiala@oveckarna.cz'),
                ('invoice_email', 'fakturace@oveckarna.cz')
            ON CONFLICT (key) DO NOTHING
        """)
        # ── Migrations: add new columns if they don't exist ───────────────────
        cur.execute("""
            ALTER TABLE pt_materials
            ADD COLUMN IF NOT EXISTS include_in_reports BOOLEAN DEFAULT TRUE
        """)
        cur.execute("""
            ALTER TABLE pt_materials
            ADD COLUMN IF NOT EXISTS material_type VARCHAR(30) DEFAULT 'packaging'
        """)
        cur.execute("""
            ALTER TABLE pt_materials
            ADD COLUMN IF NOT EXISTS report_country VARCHAR(5) DEFAULT NULL
        """)
        cur.execute("""
            ALTER TABLE pt_materials
            ADD COLUMN IF NOT EXISTS price_per_unit NUMERIC(10,4) DEFAULT NULL
        """)


# ── Settings ─────────────────────────────────────────────────────────────────

def get_settings():
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT key, value FROM pt_settings ORDER BY key")
        return {row["key"]: row["value"] for row in cur.fetchall()}


def save_settings(data: dict):
    with get_conn() as conn:
        cur = conn.cursor()
        for key, value in data.items():
            cur.execute("""
                INSERT INTO pt_settings (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """, (key, value))


# ── Materials ─────────────────────────────────────────────────────────────────

def get_materials(active_only=False, supplier=None, ekokom_material=None,
                  naturpack_material=None, material_type=None):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        conditions = []
        params = []
        if active_only:
            conditions.append("active = TRUE")
        if supplier:
            conditions.append("supplier = %s")
            params.append(supplier)
        if ekokom_material == "__none__":
            conditions.append("ekokom_material IS NULL")
        elif ekokom_material:
            conditions.append("ekokom_material = %s")
            params.append(ekokom_material)
        if naturpack_material == "__none__":
            conditions.append("naturpack_material IS NULL")
        elif naturpack_material:
            conditions.append("naturpack_material = %s")
            params.append(naturpack_material)
        if material_type:
            conditions.append("material_type = %s")
            params.append(material_type)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(f"SELECT * FROM pt_materials {where} ORDER BY active DESC, name", params)
        return cur.fetchall()


def get_material(material_id):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM pt_materials WHERE id = %s", (material_id,))
        return cur.fetchone()


def create_material(data: dict):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pt_materials
                (name, description, weight_g, supplier,
                 ekokom_sheet, ekokom_material, ekokom_form, ekokom_origin,
                 naturpack_material, naturpack_appendix,
                 notes, initial_stock, include_in_reports, material_type, report_country,
                 price_per_unit)
            VALUES
                (%(name)s, %(description)s, %(weight_g)s, %(supplier)s,
                 %(ekokom_sheet)s, %(ekokom_material)s, %(ekokom_form)s, %(ekokom_origin)s,
                 %(naturpack_material)s, %(naturpack_appendix)s,
                 %(notes)s, %(initial_stock)s, %(include_in_reports)s, %(material_type)s,
                 %(report_country)s, %(price_per_unit)s)
            RETURNING id
        """, data)
        return cur.fetchone()[0]


def update_material(material_id, data: dict):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE pt_materials SET
                name=%(name)s, description=%(description)s,
                weight_g=%(weight_g)s, supplier=%(supplier)s,
                ekokom_sheet=%(ekokom_sheet)s, ekokom_material=%(ekokom_material)s,
                ekokom_form=%(ekokom_form)s, ekokom_origin=%(ekokom_origin)s,
                naturpack_material=%(naturpack_material)s,
                naturpack_appendix=%(naturpack_appendix)s,
                notes=%(notes)s, initial_stock=%(initial_stock)s,
                include_in_reports=%(include_in_reports)s,
                material_type=%(material_type)s,
                report_country=%(report_country)s,
                price_per_unit=%(price_per_unit)s
            WHERE id=%(id)s
        """, {**data, "id": material_id})


def toggle_material(material_id):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE pt_materials SET active = NOT active WHERE id = %s", (material_id,))


def delete_material(material_id):
    """Delete a material only if it has no linked receipts or inventory entries.
    Returns (True, '') on success or (False, reason) if blocked."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM pt_receipts WHERE material_id = %s", (material_id,))
        if cur.fetchone()[0] > 0:
            return False, "Materiál má evidované příjmy a nelze ho smazat. Deaktivujte ho místo toho."
        cur.execute("SELECT COUNT(*) FROM pt_inventory WHERE material_id = %s", (material_id,))
        if cur.fetchone()[0] > 0:
            return False, "Materiál má záznamy inventury a nelze ho smazat. Deaktivujte ho místo toho."
        cur.execute("DELETE FROM pt_materials WHERE id = %s", (material_id,))
        return True, ""


# ── Receipts ──────────────────────────────────────────────────────────────────

def get_receipts(material_id=None, year=None, month=None, limit=200):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        conditions = []
        params = []
        if material_id:
            conditions.append("r.material_id = %s")
            params.append(material_id)
        if year:
            conditions.append("EXTRACT(YEAR FROM r.receipt_date) = %s")
            params.append(year)
        if month:
            conditions.append("EXTRACT(MONTH FROM r.receipt_date) = %s")
            params.append(month)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(f"""
            SELECT r.*, m.name AS material_name, m.weight_g
            FROM pt_receipts r
            JOIN pt_materials m ON m.id = r.material_id
            {where}
            ORDER BY r.receipt_date DESC, r.id DESC
            LIMIT %s
        """, params + [limit])
        return cur.fetchall()


def get_receipts_by_month(material_id, year, month):
    """Sum of received pieces for a material in a given month."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(quantity_pcs), 0)
            FROM pt_receipts
            WHERE material_id = %s
              AND EXTRACT(YEAR FROM receipt_date) = %s
              AND EXTRACT(MONTH FROM receipt_date) = %s
        """, (material_id, year, month))
        return cur.fetchone()[0]


def create_receipt(data: dict):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pt_receipts
                (material_id, receipt_date, quantity_pcs, price_per_unit, supplier_invoice, notes)
            VALUES
                (%(material_id)s, %(receipt_date)s, %(quantity_pcs)s,
                 %(price_per_unit)s, %(supplier_invoice)s, %(notes)s)
        """, data)


def delete_receipt(receipt_id):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM pt_receipts WHERE id = %s", (receipt_id,))


# ── Inventory ─────────────────────────────────────────────────────────────────

def get_inventory_entry(material_id, year, month):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT * FROM pt_inventory
            WHERE material_id = %s AND year = %s AND month = %s
        """, (material_id, year, month))
        return cur.fetchone()


def get_inventory_for_month(year, month):
    """All inventory entries for a given month."""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT i.*, m.name AS material_name, m.weight_g,
                   m.initial_stock, m.active
            FROM pt_inventory i
            JOIN pt_materials m ON m.id = i.material_id
            WHERE i.year = %s AND i.month = %s
            ORDER BY m.name
        """, (year, month))
        return cur.fetchall()


def get_previous_closing(material_id, year, month):
    """Get closing stock of the previous month (for opening calculation)."""
    with get_conn() as conn:
        cur = conn.cursor()
        # Go to previous month
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1
        cur.execute("""
            SELECT closing_stock_pcs FROM pt_inventory
            WHERE material_id = %s AND year = %s AND month = %s
        """, (material_id, prev_year, prev_month))
        row = cur.fetchone()
        return row[0] if row else None


def upsert_inventory(material_id, year, month, closing_stock, notes=""):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pt_inventory (material_id, year, month, closing_stock_pcs, notes, entered_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (material_id, year, month)
            DO UPDATE SET closing_stock_pcs = EXCLUDED.closing_stock_pcs,
                          notes = EXCLUDED.notes,
                          entered_at = NOW()
        """, (material_id, year, month, closing_stock, notes))


def get_avg_prices_all():
    """Weighted average purchase price per unit across all receipts.
    Falls back to material's own price_per_unit if no receipt prices exist.
    Returns {material_id: price_czk}."""
    with get_conn() as conn:
        cur = conn.cursor()
        # 1) receipt-based weighted average (highest priority)
        cur.execute("""
            SELECT material_id,
                   SUM(price_per_unit * quantity_pcs)::float / SUM(quantity_pcs)
            FROM pt_receipts
            WHERE price_per_unit IS NOT NULL
            GROUP BY material_id
        """)
        prices = {r[0]: float(r[1]) for r in cur.fetchall()}
        # 2) fallback: material's own price_per_unit for those not covered above
        cur.execute("""
            SELECT id, price_per_unit
            FROM pt_materials
            WHERE price_per_unit IS NOT NULL AND id != ALL(%s)
        """, (list(prices.keys()) or [0],))
        for mid, p in cur.fetchall():
            prices[mid] = float(p)
        return prices


def get_distinct_suppliers():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT supplier FROM pt_materials WHERE supplier IS NOT NULL AND supplier <> '' ORDER BY supplier")
        return [r[0] for r in cur.fetchall()]


def get_inventory_for_year(year):
    """Bulk fetch: {(material_id, month): closing_stock_pcs} for the whole year."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT material_id, month, closing_stock_pcs
            FROM pt_inventory WHERE year = %s
        """, (year,))
        return {(r[0], r[1]): r[2] for r in cur.fetchall()}


def get_receipts_totals_for_year(year):
    """Bulk fetch: {(material_id, month): total_pcs} for the whole year."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT material_id,
                   EXTRACT(MONTH FROM receipt_date)::int,
                   COALESCE(SUM(quantity_pcs), 0)
            FROM pt_receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
            GROUP BY material_id, EXTRACT(MONTH FROM receipt_date)
        """, (year,))
        return {(r[0], r[1]): int(r[2]) for r in cur.fetchall()}


def get_post_inventory_receipts(year, month):
    """
    For each material, returns total pcs received AFTER its last inventory entry
    (using entered_at as proxy for the physical count date).
    Only considers inventories up to the given year/month.
    Returns {material_id: total_pcs}.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            WITH last_inv AS (
                SELECT DISTINCT ON (material_id)
                    material_id,
                    entered_at::date AS inv_date
                FROM pt_inventory
                WHERE year < %s OR (year = %s AND month <= %s)
                ORDER BY material_id, year DESC, month DESC, entered_at DESC
            )
            SELECT r.material_id, COALESCE(SUM(r.quantity_pcs), 0)
            FROM pt_receipts r
            JOIN last_inv li ON r.material_id = li.material_id
            WHERE r.receipt_date > li.inv_date
            GROUP BY r.material_id
        """, (year, year, month))
        return {r[0]: int(r[1]) for r in cur.fetchall()}


def get_inventory_bulk(year, month):
    """Bulk fetch for a single month: {material_id: closing_stock_pcs}."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT material_id, closing_stock_pcs
            FROM pt_inventory WHERE year = %s AND month = %s
        """, (year, month))
        return {r[0]: r[1] for r in cur.fetchall()}


def get_receipts_bulk(year, month):
    """Bulk fetch for a single month: {material_id: total_pcs}."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT material_id, COALESCE(SUM(quantity_pcs), 0)
            FROM pt_receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
              AND EXTRACT(MONTH FROM receipt_date) = %s
            GROUP BY material_id
        """, (year, month))
        return {r[0]: int(r[1]) for r in cur.fetchall()}


def get_months_with_inventory(year):
    """Return list of months that have at least one inventory entry for a year."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT month FROM pt_inventory
            WHERE year = %s ORDER BY month
        """, (year,))
        return [row[0] for row in cur.fetchall()]


def get_available_years():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT year FROM pt_inventory
            UNION SELECT DISTINCT EXTRACT(YEAR FROM receipt_date)::int FROM pt_receipts
            ORDER BY 1 DESC
        """)
        rows = cur.fetchall()
        if not rows:
            from datetime import date
            return [date.today().year]
        return [r[0] for r in rows]


# ── Country distribution ──────────────────────────────────────────────────────

def get_distribution(year, quarter):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT * FROM pt_country_distribution
            WHERE year = %s AND quarter = %s
            ORDER BY percentage DESC
        """, (year, quarter))
        return cur.fetchall()


def get_all_distributions(year):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT * FROM pt_country_distribution
            WHERE year = %s ORDER BY quarter, percentage DESC
        """, (year,))
        return cur.fetchall()


def upsert_distribution(year, quarter, country_code, country_name,
                        percentage, report_ekokom, report_naturpack, report_annual):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pt_country_distribution
                (year, quarter, country_code, country_name, percentage,
                 report_ekokom, report_naturpack, report_annual)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (year, quarter, country_code) DO UPDATE SET
                country_name = EXCLUDED.country_name,
                percentage = EXCLUDED.percentage,
                report_ekokom = EXCLUDED.report_ekokom,
                report_naturpack = EXCLUDED.report_naturpack,
                report_annual = EXCLUDED.report_annual
        """, (year, quarter, country_code, country_name,
              percentage, report_ekokom, report_naturpack, report_annual))


def delete_distribution_row(row_id):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM pt_country_distribution WHERE id = %s", (row_id,))


def copy_distribution(from_year, from_quarter, to_year, to_quarter):
    """Copy distribution from one quarter to another."""
    rows = get_distribution(from_year, from_quarter)
    for row in rows:
        upsert_distribution(to_year, to_quarter, row["country_code"],
                            row["country_name"], row["percentage"],
                            row["report_ekokom"], row["report_naturpack"],
                            row["report_annual"])


def get_country_pct(year, quarter, country_code):
    """Return percentage for a specific country in a quarter."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT percentage FROM pt_country_distribution
            WHERE year = %s AND quarter = %s AND country_code = %s
        """, (year, quarter, country_code))
        row = cur.fetchone()
        return float(row[0]) if row else 0.0
