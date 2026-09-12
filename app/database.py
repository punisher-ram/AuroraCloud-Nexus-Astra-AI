"""SQLite storage, schema migrations, audit trail, and safe backups."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS customers (
 id INTEGER PRIMARY KEY, company_name TEXT NOT NULL, contact_person TEXT, phone TEXT,
 email TEXT, address TEXT, tax_id TEXT, notes TEXT, created_at TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS items (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE, description TEXT, sku TEXT,
 unit TEXT NOT NULL DEFAULT 'Unit', selling_price REAL NOT NULL DEFAULT 0, purchase_price REAL NOT NULL DEFAULT 0,
 tax_rate REAL NOT NULL DEFAULT 0, stock REAL NOT NULL DEFAULT 0, supplier TEXT, archived INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS vendors (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, contact_person TEXT, phone TEXT, email TEXT, address TEXT, notes TEXT, archived INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS expenses (
 id INTEGER PRIMARY KEY, vendor_id INTEGER REFERENCES vendors(id), description TEXT NOT NULL, amount REAL NOT NULL,
 expense_date TEXT NOT NULL, notes TEXT, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS documents (
 id INTEGER PRIMARY KEY, kind TEXT NOT NULL, number TEXT NOT NULL UNIQUE, customer_id INTEGER REFERENCES customers(id),
 source_document_id INTEGER REFERENCES documents(id), status TEXT NOT NULL DEFAULT 'DRAFT', issue_date TEXT NOT NULL,
 notes TEXT, terms TEXT, subtotal REAL NOT NULL DEFAULT 0, discount REAL NOT NULL DEFAULT 0, tax REAL NOT NULL DEFAULT 0,
 total REAL NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS document_lines (
 id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 item_id INTEGER REFERENCES items(id), description TEXT NOT NULL, quantity REAL NOT NULL, unit TEXT NOT NULL,
 rate REAL NOT NULL, discount REAL NOT NULL DEFAULT 0, tax_rate REAL NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS payments (
 id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL REFERENCES documents(id), amount REAL NOT NULL CHECK(amount > 0),
 method TEXT NOT NULL, payment_date TEXT NOT NULL, reference TEXT, notes TEXT, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS activity_log (
 id INTEGER PRIMARY KEY, action TEXT NOT NULL, entity_type TEXT, entity_id INTEGER, detail TEXT, created_at TEXT NOT NULL);

CREATE INDEX IF NOT EXISTS idx_documents_kind ON documents(kind);
CREATE INDEX IF NOT EXISTS idx_documents_customer ON documents(customer_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_issue_date ON documents(issue_date);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(company_name);
CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
CREATE INDEX IF NOT EXISTS idx_items_sku ON items(sku);
CREATE INDEX IF NOT EXISTS idx_vendors_name ON vendors(name);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_document_lines_document ON document_lines(document_id);
CREATE INDEX IF NOT EXISTS idx_document_lines_item ON document_lines(item_id);
"""


class Database:
    def __init__(self, root: Path):
        self.root, self.path = root, root / "data" / "aurora.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=8.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 8000")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.transaction() as db:
            db.executescript(SCHEMA)
            for key, value in {"business_name": "AURORA CLOUD", "signature": "by hash", "currency": "INR"}.items():
                db.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value))

    def health_check(self) -> dict[str, Any]:
        with sqlite3.connect(self.path, timeout=8.0) as db:
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            return {
                "path": str(self.path),
                "integrity": integrity,
                "customers": db.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
                "items": db.execute("SELECT COUNT(*) FROM items").fetchone()[0],
                "documents": db.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
                "payments": db.execute("SELECT COUNT(*) FROM payments").fetchone()[0],
            }

    def rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.transaction() as db:
            return db.execute(sql, params).fetchall()

    def log(self, db: sqlite3.Connection, action: str, entity_type: str = "", entity_id: int | None = None, detail: str = "") -> None:
        db.execute("INSERT INTO activity_log(action, entity_type, entity_id, detail, created_at) VALUES (?, ?, ?, ?, ?)",
                   (action, entity_type, entity_id, detail, datetime.now().isoformat(timespec="seconds")))

    def backup(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.root / "Backups" / f"aurora-{stamp}.db"
        target.parent.mkdir(exist_ok=True)
        with sqlite3.connect(self.path) as source, sqlite3.connect(target) as destination:
            source.backup(destination)
        return target
