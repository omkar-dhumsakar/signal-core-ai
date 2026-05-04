"""Supplier CSV parser and database persistence for StoreOps.

Handles parsing uploaded CSV files (sku, supplier_name, lead_time)
and linking each SKU to its supplier in PostgreSQL (or SQLite fallback).
"""

import csv
import io
import os
import sqlite3
from typing import Optional

import bcrypt

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite")
USE_POSTGRES = HAS_PSYCOPG2 and DATABASE_URL and DATABASE_URL != "sqlite"

DB_PATH = os.path.join(os.path.dirname(__file__), "suppliers.db")


# ── Connection Abstraction ─────────────────────────────────────────

def _get_connection():
    """Return a database connection (PostgreSQL or SQLite fallback)."""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def _execute(conn, sql, params=None):
    """Execute SQL, translating ? placeholders to %s for PostgreSQL."""
    if USE_POSTGRES:
        sql = sql.replace("?", "%s")
    cur = conn.cursor()
    if params:
        cur.execute(sql, params)
    else:
        cur.execute(sql)
    return cur


def _fetchone(cur):
    """Return a dict from the cursor's next row."""
    row = cur.fetchone()
    if row is None:
        return None
    if USE_POSTGRES:
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))
    else:
        return dict(row)


def _fetchall(cur):
    """Return a list of dicts from the cursor."""
    rows = cur.fetchall()
    if USE_POSTGRES:
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    else:
        return [dict(row) for row in rows]


# ── Schema Initialization ─────────────────────────────────────────

def init_db() -> None:
    """Create the suppliers, sku_supplier, and store_managers tables if they don't exist."""
    conn = _get_connection()
    try:
        if USE_POSTGRES:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS suppliers (
                    id   SERIAL PRIMARY KEY,
                    name TEXT   NOT NULL UNIQUE
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sku_supplier (
                    sku         TEXT    PRIMARY KEY,
                    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
                    lead_time   INTEGER NOT NULL DEFAULT 3
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS store_managers (
                    id            SERIAL PRIMARY KEY,
                    username      TEXT   NOT NULL UNIQUE,
                    password_hash TEXT   NOT NULL,
                    full_name     TEXT   NOT NULL,
                    store_name    TEXT   NOT NULL,
                    role          TEXT   NOT NULL DEFAULT 'manager'
                );
            """)
            conn.commit()
        else:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS suppliers (
                    id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT    NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS sku_supplier (
                    sku         TEXT    PRIMARY KEY,
                    supplier_id INTEGER NOT NULL,
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
                );

                CREATE TABLE IF NOT EXISTS store_managers (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    username   TEXT    NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    full_name  TEXT    NOT NULL,
                    store_name TEXT    NOT NULL,
                    role       TEXT    NOT NULL DEFAULT 'manager'
                );
                """
            )
            # Add lead_time column if missing (old schema compat)
            try:
                conn.execute("ALTER TABLE sku_supplier ADD COLUMN lead_time INTEGER NOT NULL DEFAULT 3")
                conn.commit()
            except Exception:
                pass

        _seed_default_managers(conn)
        print(f"[data_utils] Database initialized ({'PostgreSQL' if USE_POSTGRES else 'SQLite'})")
    finally:
        conn.close()


def _seed_default_managers(conn) -> None:
    """Insert default store managers if the table is empty."""
    cur = _execute(conn, "SELECT COUNT(*) FROM store_managers")
    row = cur.fetchone()
    count = row[0] if isinstance(row, tuple) else row["COUNT(*)"] if isinstance(row, dict) else row[0]
    if count > 0:
        return

    defaults = [
        {
            "username": "manager1",
            "password": "storeops123",
            "full_name": "Arjun Rao",
            "store_name": "BB Central Warehouse — Yelahanka",
            "role": "manager",
        },
        {
            "username": "admin",
            "password": "admin123",
            "full_name": "Ananya Hegde",
            "store_name": "BB Now — Koramangala",
            "role": "admin",
        },
    ]

    for mgr in defaults:
        pw_hash = bcrypt.hashpw(mgr["password"].encode(), bcrypt.gensalt()).decode()
        _execute(
            conn,
            "INSERT INTO store_managers (username, password_hash, full_name, store_name, role) "
            "VALUES (?, ?, ?, ?, ?)",
            (mgr["username"], pw_hash, mgr["full_name"], mgr["store_name"], mgr["role"]),
        )
    conn.commit()


# ── CSV Parsing ────────────────────────────────────────────────────

def parse_supplier_csv(file_bytes: bytes) -> list[dict]:
    """Parse raw CSV bytes and return a list of validated row dicts.

    Expected columns: sku, supplier_name, lead_time.
    Raises ValueError if required columns are missing or rows are malformed.
    """
    text = file_bytes.decode("utf-8-sig")  # handles BOM from Excel exports
    reader = csv.DictReader(io.StringIO(text))

    # --- validate header ---
    required = {"sku", "supplier_name", "lead_time"}
    fieldnames = reader.fieldnames
    if fieldnames is None:
        raise ValueError("CSV file is empty or has no header row.")
    actual = {f.strip().lower() for f in fieldnames}
    missing = required - actual
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

    # --- normalize field names ---
    field_map = {f.strip().lower(): f for f in fieldnames}

    rows: list[dict] = []
    for line_no, raw_row in enumerate(reader, start=2):
        sku = (raw_row.get(field_map["sku"]) or "").strip()
        supplier_name = (raw_row.get(field_map["supplier_name"]) or "").strip()
        lead_time_str = (raw_row.get(field_map["lead_time"]) or "").strip()

        if not sku or not supplier_name:
            raise ValueError(f"Row {line_no}: sku and supplier_name must not be empty.")

        try:
            lead_time = int(lead_time_str)
            if lead_time < 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError(
                f"Row {line_no}: lead_time must be a non-negative integer, got '{lead_time_str}'."
            )

        rows.append(
            {"sku": sku, "supplier_name": supplier_name, "lead_time": lead_time}
        )

    if not rows:
        raise ValueError("CSV file contains a header but no data rows.")

    return rows


def parse_supplier_dataframe(file_bytes: bytes, filename: str) -> list[dict]:
    """Parse a CSV or XLSX file using pandas and return validated row dicts.

    Detects format by file extension:
      - .csv  → pd.read_csv()
      - .xlsx → pd.read_excel()

    Expected columns: sku, supplier_name, lead_time.
    Raises ValueError on missing columns or invalid data.
    """
    import pandas as pd  # lazy import to keep startup fast

    try:
        if filename.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
        else:
            df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError(f"Could not read file: {exc}")

    # Normalize column names: strip whitespace, lowercase
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Map common column aliases to expected names
    aliases = {
        "lead_time_days": "lead_time",
        "leadtime": "lead_time",
        "lead_days": "lead_time",
        "supplier": "supplier_name",
        "sku_id": "sku",
    }
    df.rename(columns={k: v for k, v in aliases.items() if k in df.columns}, inplace=True)

    # Auto-fill supplier_name from category/product_name if missing
    if "supplier_name" not in df.columns:
        if "category" in df.columns:
            df["supplier_name"] = df["category"] + " Supplier"
        elif "product_name" in df.columns:
            df["supplier_name"] = df["product_name"]
        else:
            df["supplier_name"] = "Unknown Supplier"

    required = {"sku", "lead_time"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"File is missing required columns: {', '.join(sorted(missing))}")

    if df.empty:
        raise ValueError("File contains headers but no data rows.")

    rows: list[dict] = []
    for idx, raw_row in df.iterrows():
        line_no = int(idx) + 2  # 1-indexed, +1 for header
        sku = str(raw_row["sku"]).strip()
        supplier_name = str(raw_row["supplier_name"]).strip()
        lead_time_raw = raw_row["lead_time"]

        if not sku or sku == "nan":
            raise ValueError(f"Row {line_no}: sku must not be empty.")
        if not supplier_name or supplier_name == "nan":
            supplier_name = "Unknown Supplier"

        try:
            lead_time = int(float(lead_time_raw))
            if lead_time < 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError(
                f"Row {line_no}: lead_time must be a non-negative integer, got '{lead_time_raw}'."
            )

        rows.append({"sku": sku, "supplier_name": supplier_name, "lead_time": lead_time})

    return rows


# ── Supplier CRUD ──────────────────────────────────────────────────

def upsert_suppliers(rows: list[dict]) -> dict:
    """Insert or update supplier links for each parsed row.

    Returns {"inserted": int, "updated": int, "errors": list[str]}.
    """
    conn = _get_connection()
    inserted: int = 0
    updated: int = 0
    errors: list[str] = []

    try:
        for row in rows:
            try:
                # Ensure the supplier exists
                if USE_POSTGRES:
                    _execute(conn,
                        "INSERT INTO suppliers (name) VALUES (?) ON CONFLICT (name) DO NOTHING",
                        (row["supplier_name"],))
                else:
                    _execute(conn,
                        "INSERT OR IGNORE INTO suppliers (name) VALUES (?)",
                        (row["supplier_name"],))

                cur = _execute(conn,
                    "SELECT id FROM suppliers WHERE name = ?",
                    (row["supplier_name"],))
                supplier_id = _fetchone(cur)["id"]

                # Check if the SKU already has a supplier link
                cur = _execute(conn,
                    "SELECT supplier_id FROM sku_supplier WHERE sku = ?",
                    (row["sku"],))
                existing = _fetchone(cur)

                if existing:
                    _execute(conn,
                        "UPDATE sku_supplier SET supplier_id = ?, lead_time = ? WHERE sku = ?",
                        (supplier_id, row["lead_time"], row["sku"]))
                    updated += 1
                else:
                    _execute(conn,
                        "INSERT INTO sku_supplier (sku, supplier_id, lead_time) VALUES (?, ?, ?)",
                        (row["sku"], supplier_id, row["lead_time"]))
                    inserted += 1
            except Exception as exc:
                errors.append(f"SKU {row['sku']}: {exc}")

        conn.commit()
    finally:
        conn.close()

    return {"inserted": inserted, "updated": updated, "errors": errors}


def get_supplier_for_sku(sku: str) -> Optional[dict]:
    """Look up the supplier info for a given SKU.

    Returns {"supplier_id": int, "supplier_name": str, "lead_time": int}
    or None if no link exists.
    """
    conn = _get_connection()
    try:
        cur = _execute(conn,
            """
            SELECT s.id   AS supplier_id,
                   s.name AS supplier_name,
                   ss.lead_time
              FROM sku_supplier ss
              JOIN suppliers s ON s.id = ss.supplier_id
             WHERE ss.sku = ?
            """,
            (sku,))
        return _fetchone(cur)
    finally:
        conn.close()


def get_all_supplier_links() -> dict[str, dict]:
    """Return a mapping of sku → {supplier_id, supplier_name, lead_time} for all linked SKUs."""
    conn = _get_connection()
    try:
        cur = _execute(conn,
            """
            SELECT ss.sku,
                   s.id   AS supplier_id,
                   s.name AS supplier_name,
                   ss.lead_time
              FROM sku_supplier ss
              JOIN suppliers s ON s.id = ss.supplier_id
            """)
        rows = _fetchall(cur)
        result: dict[str, dict] = {r["sku"]: r for r in rows}
        return result
    finally:
        conn.close()


# ── Store Manager Authentication ───────────────────────────────────

def authenticate_manager(username: str, password: str) -> Optional[dict]:
    """Validate username/password and return manager info.

    If the username does not exist yet, a new store_manager record is created
    on-the-fly so that a *new* user can log in without a separate
    registration flow. The first successful login for a given username
    becomes the canonical password for that user.
    """
    conn = _get_connection()
    try:
        cur = _execute(conn,
            "SELECT id, username, password_hash, full_name, store_name, role "
            "FROM store_managers WHERE username = ?",
            (username,))
        row = _fetchone(cur)

        # Auto-provision a new manager if username does not exist yet.
        if row is None:
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            full_name = username.strip() or "New Manager"
            store_name = "StoreOps Demo Store"
            role = "manager"
            cur = _execute(conn,
                "INSERT INTO store_managers (username, password_hash, full_name, store_name, role) "
                "VALUES (?, ?, ?, ?, ?)",
                (username, pw_hash, full_name, store_name, role))
            conn.commit()

            if USE_POSTGRES:
                cur2 = _execute(conn, "SELECT id FROM store_managers WHERE username = ?", (username,))
                manager_id = _fetchone(cur2)["id"]
            else:
                manager_id = cur.lastrowid

            return {
                "manager_id": manager_id,
                "username": username,
                "full_name": full_name,
                "store_name": store_name,
                "role": role,
            }

        if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
            return None
        return {
            "manager_id": row["id"],
            "username": row["username"],
            "full_name": row["full_name"],
            "store_name": row["store_name"],
            "role": row["role"],
        }
    finally:
        conn.close()


def authenticate_google_user(email: str, name: str) -> dict:
    """Validate Google email and return manager info.

    If the email does not exist yet, a new store_manager record is created
    on-the-fly. The email acts as the username. A random password is used
    since authentication is handled via Google.
    """
    conn = _get_connection()
    try:
        cur = _execute(conn,
            "SELECT id, username, full_name, store_name, role "
            "FROM store_managers WHERE username = ?",
            (email,))
        row = _fetchone(cur)

        # Auto-provision a new manager if email does not exist yet.
        if row is None:
            import secrets
            random_pw = secrets.token_hex(16)
            pw_hash = bcrypt.hashpw(random_pw.encode(), bcrypt.gensalt()).decode()

            full_name = name.strip() or email.split('@')[0]
            store_name = "StoreOps Demo Store"
            role = "manager"
            _execute(conn,
                "INSERT INTO store_managers (username, password_hash, full_name, store_name, role) "
                "VALUES (?, ?, ?, ?, ?)",
                (email, pw_hash, full_name, store_name, role))
            conn.commit()

            if USE_POSTGRES:
                cur2 = _execute(conn, "SELECT id FROM store_managers WHERE username = ?", (email,))
                manager_id = _fetchone(cur2)["id"]
            else:
                manager_id = _execute(conn, "SELECT last_insert_rowid()").fetchone()[0]

            return {
                "manager_id": manager_id,
                "username": email,
                "full_name": full_name,
                "store_name": store_name,
                "role": role,
            }

        return {
            "manager_id": row["id"],
            "username": row["username"],
            "full_name": row["full_name"],
            "store_name": row["store_name"],
            "role": row["role"],
        }
    finally:
        conn.close()


def get_manager_by_id(manager_id: int) -> Optional[dict]:
    """Look up a store manager by ID."""
    conn = _get_connection()
    try:
        cur = _execute(conn,
            "SELECT id, username, full_name, store_name, role "
            "FROM store_managers WHERE id = ?",
            (manager_id,))
        row = _fetchone(cur)
        if row:
            return {
                "manager_id": row["id"],
                "username": row["username"],
                "full_name": row["full_name"],
                "store_name": row["store_name"],
                "role": row["role"],
            }
        return None
    finally:
        conn.close()


# ── Purchase Order Generation ──────────────────────────────────────

def generate_pos_from_confirmed(confirmed_orders: list, catalog: dict) -> list[dict]:
    """Group pure SKUs into Purchase Orders.
    Returns a list of dicts reflecting the PurchaseOrder schema.
    """
    if not confirmed_orders:
        return []

    conn = _get_connection()
    try:
        # Group raw inputs by SKU summing quantities
        aggregated = {}
        for entry in confirmed_orders:
            sku = entry["sku"]
            aggregated[sku] = aggregated.get(sku, 0) + entry.get("quantity", entry.get("qty", 0))

        # Fetch supplier info
        skus = list(aggregated.keys())
        if USE_POSTGRES:
            placeholders = ",".join(["%s"] * len(skus))
        else:
            placeholders = ",".join("?" * len(skus))

        query = f"""
            SELECT s.sku, s.lead_time, sup.name as supplier_name 
            FROM sku_supplier s
            JOIN suppliers sup ON s.supplier_id = sup.id
            WHERE s.sku IN ({placeholders})
        """
        cur = conn.cursor()
        cur.execute(query, skus)
        rows = _fetchall(cur)

        # Build mapping: sku -> {supplier_name, lead_time}
        mapping = {}
        for row in rows:
            mapping[row["sku"]] = {
                "supplier_name": row["supplier_name"],
                "lead_time": row["lead_time"]
            }

        # Group by supplier
        import uuid
        from datetime import datetime

        suppliers = {}

        for sku, qty in aggregated.items():
            info = mapping.get(sku, {"supplier_name": "General Supplier", "lead_time": 3})
            sup_name = info["supplier_name"]

            if sup_name not in suppliers:
                suppliers[sup_name] = {
                    "id": f"PO-{uuid.uuid4().hex[:6].upper()}",
                    "supplier_name": sup_name,
                    "items": [],
                    "total_quantity": 0,
                    "total_value": 0.0,
                    "eta_days": info["lead_time"],
                }

            # Catalog info
            cat_item = catalog.get(sku, {})
            product_name = cat_item.get("name", "Unknown Item")
            base_cost = cat_item.get("base_cost", 10.0)

            item_total = base_cost * qty

            suppliers[sup_name]["items"].append({
                "sku": sku,
                "product_name": product_name,
                "quantity": qty,
                "base_cost": base_cost,
                "total_cost": item_total,
            })

            suppliers[sup_name]["total_quantity"] += qty
            suppliers[sup_name]["total_value"] += item_total

            # Max lead time for the PO
            if info["lead_time"] > suppliers[sup_name]["eta_days"]:
                suppliers[sup_name]["eta_days"] = info["lead_time"]

        return list(suppliers.values())

    finally:
        conn.close()
