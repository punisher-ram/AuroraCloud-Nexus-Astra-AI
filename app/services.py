"""Business rules shared by the Aurora Nexus interface and document engines."""
from __future__ import annotations

import sys
import ctypes
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote
import webbrowser

from .database import Database


class BusinessService:
    def __init__(self, db: Database): self.db = db

    # ── Customers ──────────────────────────────────────────
    def create_customer(self, values: dict[str, str]) -> int:
        name = values.get("company_name", "").strip()
        if not name: raise ValueError("Company name is required.")
        fields = ("company_name", "contact_person", "phone", "email", "address", "tax_id", "notes")
        with self.db.transaction() as con:
            cur = con.execute(f"INSERT INTO customers({','.join(fields)}, created_at) VALUES ({','.join('?' * len(fields))}, ?)",
                              tuple(values.get(f, "").strip() for f in fields) + (datetime.now().isoformat(timespec="seconds"),))
            self.db.log(con, "Customer created", "customer", cur.lastrowid, name)
            return int(cur.lastrowid)

    def update_customer(self, id: int, values: dict[str, str]) -> None:
        name = values.get("company_name", "").strip()
        if not name: raise ValueError("Company name is required.")
        fields = ("company_name", "contact_person", "phone", "email", "address", "tax_id", "notes")
        sets = ", ".join(f"{f}=?" for f in fields)
        with self.db.transaction() as con:
            con.execute(f"UPDATE customers SET {sets} WHERE id=?", tuple(values.get(f, "").strip() for f in fields) + (id,))
            self.db.log(con, "Customer updated", "customer", id, name)

    def archive_customer(self, id: int) -> None:
        with self.db.transaction() as con:
            con.execute("UPDATE customers SET archived=1 WHERE id=?", (id,))
            self.db.log(con, "Customer archived", "customer", id)

    def restore_customer(self, id: int) -> None:
        with self.db.transaction() as con:
            con.execute("UPDATE customers SET archived=0 WHERE id=?", (id,))
            self.db.log(con, "Customer restored", "customer", id)

    def customer(self, id: int):
        rows = self.db.rows("SELECT * FROM customers WHERE id=?", (id,))
        if not rows: raise ValueError("Customer not found.")
        return rows[0]

    def customers(self, include_archived=False):
        sql = "SELECT * FROM customers"
        if not include_archived: sql += " WHERE archived=0"
        sql += " ORDER BY company_name"
        return self.db.rows(sql)

    # ── Items ──────────────────────────────────────────────
    def create_item(self, values: dict[str, Any]) -> int:
        name = str(values.get("name", "")).strip()
        if not name: raise ValueError("Item name is required.")
        fields = ("name", "description", "sku", "unit", "selling_price", "purchase_price", "tax_rate", "stock", "supplier")
        nums = {"selling_price", "purchase_price", "tax_rate", "stock"}
        payload = tuple(float(values.get(f, 0) or 0) if f in nums else str(values.get(f, "") or "") for f in fields)
        with self.db.transaction() as con:
            try: cur = con.execute(f"INSERT INTO items({','.join(fields)}) VALUES ({','.join('?' * len(fields))})", payload)
            except Exception as exc: raise ValueError(f"Could not save item: {exc}") from exc
            self.db.log(con, "Item created", "item", cur.lastrowid, name)
            return int(cur.lastrowid)

    def update_item(self, id: int, values: dict[str, Any]) -> None:
        name = str(values.get("name", "")).strip()
        if not name: raise ValueError("Item name is required.")
        fields = ("name", "description", "sku", "unit", "selling_price", "purchase_price", "tax_rate", "stock", "supplier")
        nums = {"selling_price", "purchase_price", "tax_rate", "stock"}
        sets = ", ".join(f"{f}=?" for f in fields)
        payload = tuple(float(values.get(f, 0) or 0) if f in nums else str(values.get(f, "") or "") for f in fields)
        with self.db.transaction() as con:
            con.execute(f"UPDATE items SET {sets} WHERE id=?", payload + (id,))
            self.db.log(con, "Item updated", "item", id, name)

    def archive_item(self, id: int) -> None:
        with self.db.transaction() as con:
            con.execute("UPDATE items SET archived=1 WHERE id=?", (id,))
            self.db.log(con, "Item archived", "item", id)

    def restore_item(self, id: int) -> None:
        with self.db.transaction() as con:
            con.execute("UPDATE items SET archived=0 WHERE id=?", (id,))
            self.db.log(con, "Item restored", "item", id)

    def item(self, id: int):
        rows = self.db.rows("SELECT * FROM items WHERE id=?", (id,))
        if not rows: raise ValueError("Item not found.")
        return rows[0]

    def items(self, search: str = "", include_archived=False):
        sql = "SELECT * FROM items WHERE name LIKE ?"
        params = [f"%{search}%"]
        if not include_archived:
            sql += " AND archived=0"
        sql += " ORDER BY name"
        return self.db.rows(sql, tuple(params))

    # ── Documents ──────────────────────────────────────────
    def next_number(self, con, kind: str) -> str:
        prefix = {"QUOTE": "QTE", "INVOICE": "INV", "PURCHASE_ORDER": "PO"}[kind]
        count = con.execute("SELECT COUNT(*) FROM documents WHERE kind=?", (kind,)).fetchone()[0] + 1
        return f"{prefix}-{date.today():%Y}-{count:04d}"

    def _create_document_with_con(self, con, kind: str, customer_id: int, lines: list[dict[str, Any]], *, notes: str = "", terms: str = "", source_id: int | None = None, status: str = "ISSUED") -> int:
        if not customer_id: raise ValueError("Choose a customer.")
        if not lines: raise ValueError("Add at least one line item.")
        subtotal = sum(float(x["quantity"]) * float(x["rate"]) - float(x.get("discount", 0)) for x in lines)
        tax = sum((float(x["quantity"]) * float(x["rate"]) - float(x.get("discount", 0))) * float(x.get("tax_rate", 0)) / 100 for x in lines)
        now = datetime.now().isoformat(timespec="seconds")
        number = self.next_number(con, kind)
        cur = con.execute("""INSERT INTO documents(kind,number,customer_id,source_document_id,status,issue_date,notes,terms,subtotal,tax,total,created_at,updated_at)
            VALUES(?,?,?,?, ?, ?,?,?,?,?,?,?,?)""", (kind, number, customer_id, source_id, status, date.today().isoformat(), notes, terms, subtotal, tax, subtotal + tax, now, now))
        doc_id = int(cur.lastrowid)
        for line in lines:
            con.execute("INSERT INTO document_lines(document_id,item_id,description,quantity,unit,rate,discount,tax_rate) VALUES(?,?,?,?,?,?,?,?)",
                (doc_id, line.get("item_id"), line["description"], float(line["quantity"]), line.get("unit", "Unit"), float(line["rate"]), float(line.get("discount", 0)), float(line.get("tax_rate", 0))))
        self.db.log(con, f"{kind.title()} created", "document", doc_id, number)
        return doc_id

    def create_document(self, kind: str, customer_id: int, lines: list[dict[str, Any]], *, notes: str = "", terms: str = "", source_id: int | None = None, status: str = "ISSUED") -> int:
        with self.db.transaction() as con:
            return self._create_document_with_con(con, kind, customer_id, lines, notes=notes, terms=terms, source_id=source_id, status=status)

    def update_document(self, id: int, values: dict[str, Any]) -> None:
        doc = self.document(id)
        notes = values.get("notes", doc["notes"])
        terms = values.get("terms", doc["terms"])
        status = values.get("status", doc["status"])
        with self.db.transaction() as con:
            con.execute("UPDATE documents SET notes=?, terms=?, status=?, updated_at=? WHERE id=?", (notes, terms, status, datetime.now().isoformat(timespec="seconds"), id))
            self.db.log(con, "Document updated", "document", id, doc["number"])

    def archive_document(self, id: int) -> None:
        with self.db.transaction() as con:
            con.execute("UPDATE documents SET archived=1 WHERE id=?", (id,))
            self.db.log(con, "Document archived", "document", id)

    def restore_document(self, id: int) -> None:
        with self.db.transaction() as con:
            con.execute("UPDATE documents SET archived=0 WHERE id=?", (id,))
            self.db.log(con, "Document restored", "document", id)

    def duplicate_document(self, id: int) -> int:
        doc = self.document(id)
        lines = [dict(r) for r in self.db.rows("SELECT item_id, description, quantity, unit, rate, discount, tax_rate FROM document_lines WHERE document_id=?", (id,))]
        return self.create_document(doc["kind"], doc["customer_id"], lines, notes=doc["notes"] or "", terms=doc["terms"] or "")

    def revise_quote(self, id: int) -> int:
        quote = self.document(id)
        if quote["kind"] != "QUOTE": raise ValueError("Only quotes can be revised.")
        lines = [dict(r) for r in self.db.rows("SELECT item_id, description, quantity, unit, rate, discount, tax_rate FROM document_lines WHERE document_id=?", (id,))]
        with self.db.transaction() as con:
            con.execute("UPDATE documents SET archived=1, status='SUPERSEDED', updated_at=? WHERE id=?", (datetime.now().isoformat(timespec="seconds"), id))
            new_id = self._create_document_with_con(con, "QUOTE", quote["customer_id"], lines, notes=quote["notes"] or "", terms=quote["terms"] or "", status="ISSUED")
            con.execute("UPDATE documents SET revision=? WHERE id=?", (quote["revision"] + 1, new_id))
            self.db.log(con, "Quote revised", "document", new_id, f"Rev {quote['revision'] + 1}")
            return new_id

    def convert_quote(self, quote_id: int) -> int:
        quote = self.document(quote_id)
        if quote["kind"] != "QUOTE": raise ValueError("Only quotes can be converted.")
        lines = [dict(r) for r in self.db.rows("SELECT item_id, description, quantity, unit, rate, discount, tax_rate FROM document_lines WHERE document_id=?", (quote_id,))]
        with self.db.transaction() as con:
            invoice = self._create_document_with_con(con, "INVOICE", quote["customer_id"], lines, notes=quote["notes"] or "", terms=quote["terms"] or "", source_id=quote_id)
            self.db.log(con, "Quote converted", "document", quote_id, f"Invoice #{invoice}")
            return invoice

    def document(self, doc_id: int):
        rows = self.db.rows("SELECT * FROM documents WHERE id=?", (doc_id,))
        if not rows: raise ValueError("Document not found.")
        return rows[0]

    def document_lines(self, doc_id: int):
        return self.db.rows("SELECT * FROM document_lines WHERE document_id=?", (doc_id,))

    def outstanding(self, doc_id: int) -> float:
        total = self.document(doc_id)["total"]
        paid = self.db.rows("SELECT COALESCE(SUM(amount),0) paid FROM payments WHERE invoice_id=?", (doc_id,))[0]["paid"]
        return float(total - paid)

    def documents(self, kind: str, include_archived=False):
        sql = """SELECT d.*, c.company_name, COALESCE((SELECT SUM(amount) FROM payments p WHERE p.invoice_id=d.id),0) paid 
                 FROM documents d LEFT JOIN customers c ON c.id=d.customer_id WHERE d.kind=?"""
        params = [kind]
        if not include_archived: sql += " AND d.archived=0"
        sql += " ORDER BY d.id DESC"
        return self.db.rows(sql, tuple(params))

    # ── Payments ───────────────────────────────────────────
    def record_payment(self, invoice_id: int, amount: float, method: str, reference: str, notes: str) -> int:
        invoice = self.document(invoice_id)
        if invoice["kind"] != "INVOICE": raise ValueError("Payments can only be applied to invoices.")
        outstanding = self.outstanding(invoice_id)
        if amount <= 0 or amount > outstanding + .005: raise ValueError(f"Payment must be between 0 and {outstanding:.2f}.")
        with self.db.transaction() as con:
            cur = con.execute("INSERT INTO payments(invoice_id,amount,method,payment_date,reference,notes,created_at) VALUES(?,?,?,?,?,?,?)", (invoice_id, amount, method, date.today().isoformat(), reference, notes, datetime.now().isoformat(timespec="seconds")))
            self.db.log(con, "Payment recorded", "payment", cur.lastrowid, invoice["number"])
            return int(cur.lastrowid)

    def delete_payment(self, id: int) -> None:
        with self.db.transaction() as con:
            con.execute("DELETE FROM payments WHERE id=?", (id,))
            self.db.log(con, "Payment deleted", "payment", id)

    def payment(self, id: int):
        rows = self.db.rows("SELECT p.*, d.number, c.company_name FROM payments p JOIN documents d ON d.id=p.invoice_id LEFT JOIN customers c ON c.id=d.customer_id WHERE p.id=?", (id,))
        if not rows: raise ValueError("Payment not found.")
        return rows[0]

    def payments(self):
        return self.db.rows("SELECT p.*, d.number, c.company_name FROM payments p JOIN documents d ON d.id=p.invoice_id LEFT JOIN customers c ON c.id=d.customer_id ORDER BY p.id DESC")

    # ── Vendors ────────────────────────────────────────────
    def create_vendor(self, values: dict[str, str]) -> int:
        name = values.get("name", "").strip()
        if not name: raise ValueError("Vendor name is required.")
        fields = ("name", "contact_person", "phone", "email", "address", "notes")
        with self.db.transaction() as con:
            cur = con.execute(f"INSERT INTO vendors({','.join(fields)}) VALUES ({','.join('?' * len(fields))})", tuple(values.get(f, "").strip() for f in fields))
            self.db.log(con, "Vendor created", "vendor", cur.lastrowid, name)
            return int(cur.lastrowid)

    def update_vendor(self, id: int, values: dict[str, str]) -> None:
        name = values.get("name", "").strip()
        if not name: raise ValueError("Vendor name is required.")
        fields = ("name", "contact_person", "phone", "email", "address", "notes")
        sets = ", ".join(f"{f}=?" for f in fields)
        with self.db.transaction() as con:
            con.execute(f"UPDATE vendors SET {sets} WHERE id=?", tuple(values.get(f, "").strip() for f in fields) + (id,))
            self.db.log(con, "Vendor updated", "vendor", id, name)

    def archive_vendor(self, id: int) -> None:
        with self.db.transaction() as con:
            con.execute("UPDATE vendors SET archived=1 WHERE id=?", (id,))
            self.db.log(con, "Vendor archived", "vendor", id)

    def restore_vendor(self, id: int) -> None:
        with self.db.transaction() as con:
            con.execute("UPDATE vendors SET archived=0 WHERE id=?", (id,))
            self.db.log(con, "Vendor restored", "vendor", id)

    def vendor(self, id: int):
        rows = self.db.rows("SELECT * FROM vendors WHERE id=?", (id,))
        if not rows: raise ValueError("Vendor not found.")
        return rows[0]

    def vendors(self, include_archived=False):
        sql = "SELECT * FROM vendors"
        if not include_archived: sql += " WHERE archived=0"
        sql += " ORDER BY name"
        return self.db.rows(sql)

    # ── Expenses ───────────────────────────────────────────
    def create_expense(self, values: dict[str, Any]) -> int:
        desc = values.get("description", "").strip()
        if not desc: raise ValueError("Description is required.")
        amount = float(values.get("amount", 0) or 0)
        if amount <= 0: raise ValueError("Amount must be greater than 0.")
        vendor_id = values.get("vendor_id") or None
        expense_date = values.get("expense_date", date.today().isoformat())
        notes = values.get("notes", "")
        with self.db.transaction() as con:
            cur = con.execute("INSERT INTO expenses(vendor_id, description, amount, expense_date, notes, created_at) VALUES(?,?,?,?,?,?)",
                              (vendor_id, desc, amount, expense_date, notes, datetime.now().isoformat(timespec="seconds")))
            self.db.log(con, "Expense created", "expense", cur.lastrowid, desc)
            return int(cur.lastrowid)

    def update_expense(self, id: int, values: dict[str, Any]) -> None:
        desc = values.get("description", "").strip()
        if not desc: raise ValueError("Description is required.")
        amount = float(values.get("amount", 0) or 0)
        if amount <= 0: raise ValueError("Amount must be greater than 0.")
        vendor_id = values.get("vendor_id") or None
        expense_date = values.get("expense_date", date.today().isoformat())
        notes = values.get("notes", "")
        with self.db.transaction() as con:
            con.execute("UPDATE expenses SET vendor_id=?, description=?, amount=?, expense_date=?, notes=? WHERE id=?",
                        (vendor_id, desc, amount, expense_date, notes, id))
            self.db.log(con, "Expense updated", "expense", id, desc)

    def delete_expense(self, id: int) -> None:
        with self.db.transaction() as con:
            con.execute("DELETE FROM expenses WHERE id=?", (id,))
            self.db.log(con, "Expense deleted", "expense", id)

    def expense(self, id: int):
        rows = self.db.rows("SELECT e.*, v.name vendor FROM expenses e LEFT JOIN vendors v ON v.id=e.vendor_id WHERE e.id=?", (id,))
        if not rows: raise ValueError("Expense not found.")
        return rows[0]

    def expenses(self):
        return self.db.rows("SELECT e.*, v.name vendor FROM expenses e LEFT JOIN vendors v ON v.id=e.vendor_id ORDER BY e.expense_date DESC")

    # ── Dashboard & Reports ────────────────────────────────
    def dashboard(self):
        row = self.db.rows("""SELECT COALESCE(SUM(total),0) revenue, COUNT(*) invoices, COALESCE(SUM((SELECT SUM(amount) FROM payments p WHERE p.invoice_id=d.id)),0) collected FROM documents d WHERE kind='INVOICE' AND archived=0""")[0]
        quotes = self.db.rows("SELECT COUNT(*) count, SUM(CASE WHEN EXISTS(SELECT 1 FROM documents i WHERE i.source_document_id=d.id) THEN 1 ELSE 0 END) converted FROM documents d WHERE kind='QUOTE' AND archived=0")[0]
        return {"revenue": float(row["revenue"]), "collected": float(row["collected"]), "outstanding": float(row["revenue"] - row["collected"]), "invoices": row["invoices"], "quotes": quotes["count"], "converted": quotes["converted"] or 0}

    def email_draft(self, email: str, subject: str, body: str) -> None:
        url = f"mailto:{quote(email)}?subject={quote(subject)}&body={quote(body)}"
        if sys.platform == "win32":
            # ShellExecuteW opens mailto without any console window flash
            ctypes.windll.shell32.ShellExecuteW(None, "open", url, None, None, 1)
        else:
            webbrowser.open(url)
