from pathlib import Path
import tempfile
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication, QTableWidgetItem
from app.database import Database
from app.services import BusinessService
from app.documents import DocumentEngine
from app.ui import Window

root=Path(tempfile.mkdtemp(prefix='aurora_smoke_'))
db=Database(root); db.migrate(); s=BusinessService(db); e=DocumentEngine(db,root)
with db.transaction() as con:
    c=con.execute("INSERT INTO customers(company_name,created_at) VALUES(?,?)",('Test Client','2026-09-08T00:00:00')).lastrowid
    i=con.execute("INSERT INTO items(name,unit,selling_price,tax_rate) VALUES(?,?,?,?)",('Test Item','Unit',100,5)).lastrowid
    d=con.execute("INSERT INTO documents(kind,number,customer_id,status,issue_date,subtotal,tax,total,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",('INVOICE','INV-2026-0001',c,'ISSUED','2026-09-08',100,5,105,'2026-09-08','2026-09-08')).lastrowid
    p=con.execute("INSERT INTO payments(invoice_id,amount,method,payment_date,reference,created_at) VALUES(?,?,?,?,?,?)",(d,105,'UPI','2026-09-08','R1','2026-09-08')).lastrowid
app=QApplication.instance() or QApplication([])
w=Window(s,e,root)
# Quote/invoice combos are non-editable and contain only DB data after refresh
for name in ('Quotes','Invoices'):
    combo=w._doc_widgets(name)['customer']; assert not combo.isEditable(), name+' customer combo editable'
    assert combo.count()==1, (name, combo.count())
    assert combo.itemText(0)=='Test Client'
    item=w._doc_widgets(name)['item']; assert not item.isEditable(); assert item.count()==1; assert item.itemText(0)=='Test Item'
# Expense vendor has no fake dash entry
w.refresh('Expenses'); assert w.e_vendor.count()==0, f'fake expense vendor entry remains: {w.e_vendor.count()}'
# Receipt selection parser converts REC-00001 -> payment id 1
w.refresh('Receipts'); w.receipt_table.selectRow(0); assert w.selected_payment_id()==p, w.selected_payment_id()
# AI messages are separated by blocks; the exported plain text has multiple line breaks
w.ai_chat.clear(); w._append_ai_message('You','hey'); w._append_ai_message('Astra','Hello'); plain=w.ai_chat.toPlainText(); assert plain.index('hey') < plain.index('Hello'); assert '\n' in plain
print('PASS: quote/invoice DB-only dropdowns')
print('PASS: expense vendor has no dash placeholder item')
print('PASS: receipt selected ID parsing')
print('PASS: AI message block separation')
print('PASS: Qt UI smoke initialization')
