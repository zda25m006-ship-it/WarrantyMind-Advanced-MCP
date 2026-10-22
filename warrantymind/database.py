import json
import sqlite3
import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from warrantymind.config import DB_PATH


def get_conn() -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=MEMORY;")
        conn.execute("PRAGMA temp_store=MEMORY;")
    except sqlite3.OperationalError:
        import tempfile
        fallback_db = Path(tempfile.gettempdir()) / "warrantymind.db"
        conn = sqlite3.connect(str(fallback_db), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt_bytes = bytes.fromhex(salt) if salt else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 310_000)
    return f"pbkdf2_sha256$310000${salt_bytes.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, rounds, salt, expected = stored_hash.split("$", 3)
            actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(rounds)).hex()
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False
    # Verify legacy local demo hashes for an orderly upgrade at next successful login.
    if "$" not in stored_hash:
        return False
    salt, expected = stored_hash.split("$", 1)
    actual = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return hmac.compare_digest(actual, expected)


def init_db() -> None:
    global DB_PATH
    try:
        conn = get_conn()
        conn.execute("CREATE TABLE IF NOT EXISTS _lock_probe (id INT);")
    except sqlite3.OperationalError:
        import tempfile
        DB_PATH = Path(tempfile.gettempdir()) / "warrantymind.db"
        conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        '''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT NOT NULL,
            service_center_id TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_username TEXT NOT NULL,
            product_category TEXT NOT NULL,
            product_model TEXT NOT NULL,
            serial_number TEXT NOT NULL,
            purchase_date TEXT NOT NULL,
            warranty_expiry TEXT NOT NULL,
            region TEXT NOT NULL,
            enrolled_plan TEXT NOT NULL,
            invoice_number TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS policy_clauses (
            clause_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            title TEXT NOT NULL,
            program_type TEXT NOT NULL,
            product_scope_json TEXT NOT NULL,
            region TEXT NOT NULL,
            text TEXT NOT NULL,
            depends_on_json TEXT NOT NULL,
            requires_physical_inspection INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS price_catalog (
            catalog_id TEXT PRIMARY KEY,
            product_category TEXT NOT NULL,
            component_code TEXT NOT NULL,
            component_name TEXT NOT NULL,
            diagnostic_fee_inr INTEGER NOT NULL,
            repair_min_inr INTEGER NOT NULL,
            repair_max_inr INTEGER NOT NULL,
            catalog_version TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS service_slots (
            slot_id TEXT PRIMARY KEY,
            center_id TEXT NOT NULL,
            center_name TEXT NOT NULL,
            city TEXT NOT NULL,
            slot_window TEXT NOT NULL,
            is_booked INTEGER NOT NULL DEFAULT 0,
            booked_case_id TEXT
        );

        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            customer_username TEXT NOT NULL,
            product_category TEXT NOT NULL,
            product_model TEXT NOT NULL,
            serial_number TEXT NOT NULL,
            reported_symptom TEXT NOT NULL,
            complaint_description TEXT NOT NULL,
            workflow_status TEXT NOT NULL,
            current_interrupt TEXT,
            state_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS outbox_events (
            event_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        '''
    )
    conn.commit()
    conn.close()


def seed_demo_data() -> None:
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    users = [
        ("customer1", hash_password("Customer123!"), "customer", "Aarav Sharma", None),
        ("customer2", hash_password("Customer123!"), "customer", "Priya Nair", None),
        ("technician1", hash_password("Tech123!"), "technician", "Vikram Menon (Lead Pixel Device Technician)", "CENTER-MAA-01"),
        ("support1", hash_password("Support123!"), "support", "Divya Krishnan (Senior Pixel Support Specialist)", None),
    ]
    for u in users:
        cur.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, role, full_name, service_center_id) VALUES (?, ?, ?, ?, ?)",
            u,
        )

    orders = [
        (
            "ORD-1001",
            "customer1",
            "Pixel Phone",
            "Google Pixel 9 Pro",
            "SN-PIXEL9P-99412",
            "2025-03-10",
            "UNVERIFIED",
            "IN",
            "Google warranty terms pending official verification",
            "INV-2026-8821",
        ),
        (
            "ORD-1002",
            "customer1",
            "Pixel Phone",
            "Google Pixel 8",
            "SN-PIXEL8-77301",
            "2024-08-15",
            "UNVERIFIED",
            "IN",
            "Warranty status requires official verification",
            "INV-2024-4410",
        ),
        (
            "ORD-1003",
            "customer1",
            "Pixelbook",
            "Google Pixelbook Go",
            "SN-PIXELBOOK-55219",
            "2024-05-20",
            "UNVERIFIED",
            "IN",
            "Warranty status requires official verification",
            "INV-2024-3109",
        ),
        (
            "ORD-1004",
            "customer1",
            "Pixel Watch",
            "Google Pixel Watch 3",
            "SN-PIXELWATCH3-11890",
            "2026-06-01",
            "UNVERIFIED",
            "IN",
            "Google warranty terms pending official verification",
            "INV-2026-9912",
        ),
    ]
    for o in orders:
        cur.execute(
            '''INSERT OR REPLACE INTO orders
            (order_id, customer_username, product_category, product_model, serial_number, purchase_date, warranty_expiry, region, enrolled_plan, invoice_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            o,
        )

    # Former Apple-specific policy claims were unverified demo data; replace them with safe internal guidance.
    cur.execute("DELETE FROM policy_clauses WHERE clause_id LIKE 'CLAUSE-%' OR clause_id = 'PROG-GREENLINE-2026'")
    clauses = [
        (
            "WM-SOP-01",
            "WARRANTYMIND-PIXEL-SOP-2026",
            "Verify current Google warranty by market",
            "INTERNAL_SOP",
            json.dumps(["Pixel Phone", "Pixel Watch", "Pixelbook"]),
            "IN",
            "Warranty coverage can vary by country, model, purchase channel, purchase date, and plan. Retrieve the current official Google terms and have a human verify they apply to the customer's exact order. Never infer a free repair or rejection from a symptom, community report, or demo order record.",
            json.dumps([]),
            1,
        ),
        (
            "WM-SOP-02",
            "WARRANTYMIND-PIXEL-SOP-2026",
            "Remote evidence has limits",
            "INTERNAL_SOP",
            json.dumps(["Pixel Phone", "Pixel Watch", "Pixelbook"]),
            "IN",
            "A photo model may describe visible evidence but cannot verify internal damage, device identity, serial number, purchase eligibility, or coverage. Record uncertainty and ask for technician inspection when required.",
            json.dumps([]),
            1,
        ),
        (
            "WM-SOP-03",
            "WARRANTYMIND-PIXEL-SOP-2026",
            "Community posts are diagnostic context only",
            "INTERNAL_SOP",
            json.dumps(["Pixel Phone", "Pixel Watch", "Pixelbook"]),
            "IN",
            "Reddit and Google Help Community posts are user-generated reports. Contributor identity and expertise are not verified. They may suggest questions or troubleshooting leads, but they are never proof of a manufacturer defect, warranty coverage, or repair outcome.",
            json.dumps([]),
            1,
        ),
    ]
    for c in clauses:
        cur.execute(
            '''INSERT OR REPLACE INTO policy_clauses
            (clause_id, document_id, title, program_type, product_scope_json, region, text, depends_on_json, requires_physical_inspection)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            c,
        )

    # No Pixel repair prices are seeded: prices must come from an approved, current source.
    cur.execute("DELETE FROM price_catalog WHERE catalog_id IN ('CAT-IPH-DISP', 'CAT-IPH-BATT', 'CAT-IPH-ENCL', 'CAT-MBP-DISP', 'CAT-MBP-LOGIC', 'CAT-AW-DISP')")
    catalog = []
    for item in catalog:
        cur.execute(
            '''INSERT OR REPLACE INTO price_catalog
            (catalog_id, product_category, component_code, component_name, diagnostic_fee_inr, repair_min_inr, repair_max_inr, catalog_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            item,
        )

    slots = [
        ("SLOT-MAA-01", "CENTER-MAA-01", "WarrantyMind Demo Service Desk", "Chennai", "Demo slot, 10:30 AM - 11:30 AM", 0, None),
        ("SLOT-MAA-02", "CENTER-MAA-01", "WarrantyMind Demo Service Desk", "Chennai", "Demo slot, 02:30 PM - 03:30 PM", 0, None),
        ("SLOT-MAA-03", "CENTER-MAA-01", "WarrantyMind Demo Service Desk", "Chennai", "Demo slot, 11:00 AM - 12:00 PM", 0, None),
        ("SLOT-BLR-01", "CENTER-MAA-01", "WarrantyMind Demo Service Desk", "Bengaluru", "Demo slot, 04:00 PM - 05:00 PM", 0, None),
    ]
    for s in slots:
        cur.execute(
            '''INSERT OR IGNORE INTO service_slots
            (slot_id, center_id, center_name, city, slot_window, is_booked, booked_case_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            s,
        )

    conn.commit()
    conn.close()
