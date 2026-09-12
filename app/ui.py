from __future__ import annotations
from datetime import date
import html
import re
import threading
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import *
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut, QTextCharFormat, QBrush, QColor

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None
from .ai.serneia import SerneiaClient, SerneiaError
from .services import BusinessService
from .documents import DocumentEngine

NAV = ["Dashboard", "Quotes", "Invoices", "Customers", "Items", "Payments", "Receipts", "Ledger", "Inventory", "Expenses", "Vendors", "Analytics", "Documents", "Settings", "Activity"]
NAV_ICONS = {"Dashboard":"◈", "Quotes":"◫", "Invoices":"▣", "Customers":"◎", "Items":"◇", "Payments":"₹", "Receipts":"◰", "Ledger":"≡", "Inventory":"◌", "Expenses":"↗", "Vendors":"◉", "Analytics":"◒", "Documents":"▤", "Settings":"⚙", "Activity":"◷"}


class ModelWorker(QObject):
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, client):
        super().__init__()
        self.client = client

    def run(self):
        try:
            self.finished.emit(self.client.list_models())
        except Exception as exc:
            self.failed.emit(str(exc))


class ChatWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, client, question, context, model):
        super().__init__()
        self.client = client
        self.question = question
        self.context = context
        self.model = model

    def run(self):
        try:
            self.finished.emit(self.client.ask(self.question, self.context, model=self.model))
        except Exception as exc:
            self.failed.emit(str(exc))


class SerneiaSignals(QObject):
    models_loaded = Signal(object)
    models_failed = Signal(str)
    chat_finished = Signal(str)
    chat_failed = Signal(str)



class Window(QMainWindow):
    def __init__(self, service: BusinessService, engine: DocumentEngine, root: Path):
        super().__init__(); self.s, self.e, self.root = service, engine, root; self.current_module="Dashboard"; self.ai_client=SerneiaClient(); self.ai_panel=None; self.ai_chat=None; self.ai_input=None; self.ai_model=None; self.ai_status=None; self._ai_history=[]; self._ai_open_module="Dashboard"; self._models_loading=False; self._chat_busy=False; self.ai_attachments=[]; self._model_thread=None; self._chat_thread=None; self.document_widgets={"Quotes":{}, "Invoices":{}}; self.document_lines={"Quotes":[], "Invoices":[]}; self._serneia_signals=SerneiaSignals()
        self._serneia_signals.models_loaded.connect(self._models_loaded)
        self._serneia_signals.models_failed.connect(self._models_failed)
        self._serneia_signals.chat_finished.connect(self._chat_finished)
        self._serneia_signals.chat_failed.connect(self._chat_failed)
        self.setWindowTitle("AURORA CLOUD — NEXUS"); self.resize(1680,1050); self.setMinimumSize(1280,800)
        self.setWindowIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        central=QWidget(); self.setCentralWidget(central); shell=QHBoxLayout(central); shell.setContentsMargins(0,0,0,0); shell.setSpacing(0)
        side=QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(260); sl=QVBoxLayout(side); sl.setContentsMargins(18,24,18,18); sl.setSpacing(2)
        brand_card=QFrame(); brand_card.setObjectName("brand_card")
        brand_layout=QHBoxLayout(brand_card); brand_layout.setContentsMargins(10,10,12,10); brand_layout.setSpacing(10)
        mark=self.label("A","logo_mark"); brand_layout.addWidget(mark)
        word=QVBoxLayout(); word.setSpacing(1)
        word.addWidget(self.label("AURORA CLOUD","brand")); word.addWidget(self.label("NEXUS","subbrand")); word.addWidget(self.label("BUSINESS OPERATING SYSTEM","brand_tag")); word.addWidget(self.label("by hash","signature"))
        brand_layout.addLayout(word); sl.addWidget(brand_card); sl.addSpacing(22)
        self.stack=QStackedWidget(); self.buttons={}
        for name in NAV:
            b=QPushButton(f"{NAV_ICONS[name]}   {name}"); b.setObjectName("nav"); b.setCheckable(True); b.setCursor(Qt.PointingHandCursor); b.clicked.connect(lambda checked=False,n=name:self.go(n)); sl.addWidget(b); self.buttons[name]=b; self.stack.addWidget(self.make_page(name))
        sl.addStretch(); sl.addWidget(self.label("DATA SAFETY","nav_caption")); backup=QPushButton("◌   Create backup"); backup.setObjectName("secondary"); backup.clicked.connect(self.backup); sl.addWidget(backup); sl.addSpacing(12); sl.addWidget(self.label("AURORA NEXUS  ·  by hash","signature"), alignment=Qt.AlignCenter)
        self.shell=shell; shell.addWidget(side)
        content=QFrame(); content.setObjectName("content_shell")
        content_layout=QVBoxLayout(content); content_layout.setContentsMargins(0,0,0,0); content_layout.setSpacing(0)
        topbar=QFrame(); topbar.setObjectName("app_topbar")
        top_layout=QHBoxLayout(topbar); top_layout.setContentsMargins(24,16,24,14); top_layout.setSpacing(12)
        self.header_module=self.label("Dashboard","topbar_module"); top_layout.addWidget(self.header_module)
        top_layout.addWidget(self.label("/  AURORA CLOUD — NEXUS","topbar_path"))
        top_layout.addStretch()
        self.global_search=QLineEdit(); self.global_search.setObjectName("global_search"); self.global_search.setPlaceholderText("Search ERP  ·  Ctrl+K"); self.global_search.setClearButtonEnabled(True); self.global_search.setMaximumWidth(330); self.global_search.returnPressed.connect(self.global_search_action); top_layout.addWidget(self.global_search)
        self.db_badge=self.label("●  LOCAL DATABASE","db_badge"); top_layout.addWidget(self.db_badge)
        content_layout.addWidget(topbar)
        content_layout.addWidget(self.stack,1)
        shell.addWidget(content,1)
        self.build_ai_panel(shell)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.focus_global_search)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, activated=lambda:self.toggle_ai(self.current_module))
        self.go("Dashboard")
        self._remove_visual_shadows()

    def build_ai_panel(self, shell):
        panel = QFrame()
        panel.setObjectName("astra_panel")
        panel.setFixedWidth(390)
        panel.hide()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        head_card=QFrame(); head_card.setObjectName("astra_head_card"); hl=QVBoxLayout(head_card); hl.setContentsMargins(14,12,14,12); hl.setSpacing(8)
        head=QHBoxLayout(); title_box=QVBoxLayout(); title_box.setSpacing(1)
        title=QLabel("✦  ASTRA AI"); title.setObjectName("ai_title"); title_box.addWidget(title)
        self.ai_context_label=QLabel("Current module · Dashboard"); self.ai_context_label.setObjectName("ai_context"); title_box.addWidget(self.ai_context_label)
        head.addLayout(title_box); head.addStretch()
        self.ai_live_dot=QLabel("●  READY"); self.ai_live_dot.setObjectName("ai_ready"); head.addWidget(self.ai_live_dot)
        close=QPushButton("×"); close.setObjectName("icon_btn"); close.setToolTip("Close Astra"); close.clicked.connect(lambda: panel.hide()); head.addWidget(close)
        hl.addLayout(head)
        self.ai_status=QLabel("Astra is ready"); self.ai_status.setObjectName("ai_status")
        hl.addWidget(self.ai_status)
        layout.addWidget(head_card)

        model_card=QFrame(); model_card.setObjectName("ai_card"); ml=QVBoxLayout(model_card); ml.setContentsMargins(12,10,12,10); ml.setSpacing(8)
        lab=QLabel("MODEL"); lab.setObjectName("section_caption"); ml.addWidget(lab)
        mr=QHBoxLayout(); self.ai_model=QComboBox(); self.ai_model.setObjectName("ai_model_combo"); self.ai_model.setMinimumHeight(42); self.ai_model.setMaxVisibleItems(12); self.ai_model.setSizeAdjustPolicy(QComboBox.AdjustToContents); self.ai_model.setMinimumContentsLength(24); self.ai_model.setEditable(False); self.ai_model.setInsertPolicy(QComboBox.NoInsert)
        view=self.ai_model.view(); view.setMinimumWidth(430); view.setMinimumHeight(330); view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded); view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        mr.addWidget(self.ai_model,1); refresh_models=QPushButton("↻"); refresh_models.setObjectName("icon_btn"); refresh_models.setToolTip("Refresh Gemini models"); refresh_models.clicked.connect(self.load_ai_models); mr.addWidget(refresh_models); ml.addLayout(mr)
        layout.addWidget(model_card)

        quick=QHBoxLayout(); quick.setSpacing(6)
        for text,prompt in (("Overview","Give me a concise overview of this module."),("Outstanding","Show me what is currently outstanding."),("Latest","What is the latest relevant transaction?"),("Explain","Explain the selected record.")):
            b=QPushButton(text); b.setObjectName("ai_chip"); b.clicked.connect(lambda _=False,p=prompt:self._ai_quick_prompt(p)); quick.addWidget(b)
        layout.addLayout(quick)

        self.ai_chat=QTextEdit(); self.ai_chat.setObjectName("ai_chat"); self.ai_chat.setReadOnly(True); self.ai_chat.setAcceptRichText(True); self.ai_chat.setPlaceholderText("Astra can read your ERP data, selected records and PDFs here."); layout.addWidget(self.ai_chat,1)

        composer=QFrame(); composer.setObjectName("ai_composer"); cl=QVBoxLayout(composer); cl.setContentsMargins(10,10,10,10); cl.setSpacing(8)
        self.ai_input=QLineEdit(); self.ai_input.setObjectName("ai_input"); self.ai_input.setPlaceholderText("Ask Astra about your business…"); self.ai_input.returnPressed.connect(self._submit_ai_message); cl.addWidget(self.ai_input)
        cr=QHBoxLayout(); attach=QPushButton("Attach PDF"); attach.setObjectName("ai_subtle"); attach.clicked.connect(self.attach_ai_pdf); cr.addWidget(attach)
        copy=QPushButton("Copy"); copy.setObjectName("ai_subtle"); copy.clicked.connect(self.copy_ai_chat); cr.addWidget(copy)
        clear=QPushButton("Clear"); clear.setObjectName("ai_subtle"); clear.clicked.connect(self.clear_ai_chat); cr.addWidget(clear); cr.addStretch()
        self.ai_send=QPushButton("Ask Astra  ↵"); self.ai_send.setObjectName("ai_send"); self.ai_send.setDefault(False); self.ai_send.setAutoDefault(False); self.ai_send.clicked.connect(self._submit_ai_message); cr.addWidget(self.ai_send); cl.addLayout(cr)
        layout.addWidget(composer)

        shell.addWidget(panel)
        self.ai_panel=panel
        self.ai_attachments=[]
        self._populate_model_catalog(self.ai_client.FALLBACK_MODELS)

    def _flatten_combo_popup(self, combo):
        """Keep combo popups visually flat without OS-style drop shadows."""
        try:
            popup = combo.view().window()
            popup.setWindowFlag(Qt.NoDropShadowWindowHint, True)
        except Exception:
            pass

    def _populate_model_catalog(self, models):
        current = self.ai_model.currentData() or self.ai_client.default_model
        self.ai_model.blockSignals(True)
        self.ai_model.clear()
        for number, model_id in enumerate(models, 1):
            self.ai_model.addItem(f"{number}  ·  {model_id}", model_id)
        preferred = self.ai_model.findData(current)
        if preferred < 0:
            preferred = self.ai_model.findData(self.ai_client.default_model)
        if preferred < 0 and self.ai_model.count():
            preferred = 0
        if preferred >= 0:
            self.ai_model.setCurrentIndex(preferred)
        self.ai_model.blockSignals(False)
        self.ai_model.setEnabled(True)

    def focus_global_search(self):
        self.global_search.setFocus(); self.global_search.selectAll()

    def global_search_action(self):
        q=self.global_search.text().strip().lower()
        if not q: return
        exact={n.lower():n for n in NAV}
        if q in exact:
            self.go(exact[q]); self.global_search.clear(); return
        checks=[("customer","Customers","SELECT id, company_name FROM customers WHERE archived=0 AND (company_name LIKE ? OR contact_person LIKE ?) ORDER BY company_name LIMIT 8"),("invoice","Invoices","SELECT id, number FROM documents WHERE kind='INVOICE' AND number LIKE ? ORDER BY id DESC LIMIT 8"),("quote","Quotes","SELECT id, number FROM documents WHERE kind='QUOTE' AND number LIKE ? ORDER BY id DESC LIMIT 8"),("item","Items","SELECT id, name FROM items WHERE archived=0 AND (name LIKE ? OR sku LIKE ?) ORDER BY name LIMIT 8"),("vendor","Vendors","SELECT id, name FROM vendors WHERE archived=0 AND (name LIKE ? OR contact_person LIKE ?) ORDER BY name LIMIT 8")]
        results=[]
        for _,module,sql in checks:
            try:
                params=(f"%{q}%",f"%{q}%") if sql.count("?")==2 else (f"%{q}%",)
                rows=self.s.db.rows(sql,params)
                for r in rows: results.append((module, f"{r[1]}", int(r[0])))
            except Exception: pass
        d=QDialog(self); d.setWindowTitle("AURORA Search"); d.setMinimumWidth(560); l=QVBoxLayout(d); l.setSpacing(10); l.addWidget(QLabel(f"Results for  ‘{self.global_search.text().strip()}’"));
        if not results:
            l.addWidget(QLabel("No matching ERP records found."))
        else:
            for module,label,record_id in results[:20]:
                b=QPushButton(f"{module}   ·   {label}"); b.setObjectName("secondary"); b.clicked.connect(lambda _=False,m=module,i=record_id:self._open_search_result(d,m,i)); l.addWidget(b)
        d.exec(); self.global_search.clear()

    def _open_search_result(self,dialog,module,record_id):
        self.go(module)
        if module=="Customers": table=self.customer_table
        elif module=="Items": table=self.item_table
        elif module=="Quotes": table=self._doc_widgets("Quotes")["table"]
        elif module=="Invoices": table=self._doc_widgets("Invoices")["table"]
        elif module=="Vendors": table=self.vendor_table
        else: table=None
        if table is not None:
            for row in range(table.rowCount()):
                item=table.item(row,0)
                if item and str(item.text())==str(record_id): table.selectRow(row); break
        dialog.accept()

    def _ai_quick_prompt(self,prompt):
        self.ai_input.setText(prompt); self.ai_input.setFocus()

    def copy_ai_chat(self):
        QGuiApplication.clipboard().setText(self.ai_chat.toPlainText())
        self.ai_status.setText("Astra chat copied to clipboard")

    def clear_ai_chat(self):
        self.ai_chat.clear(); self._ai_history.clear(); self.ai_attachments.clear(); self.ai_status.setText("Astra chat cleared")

    def attach_ai_pdf(self):
        if PdfReader is None:
            self._append_ai_message("Astra error","PDF reader support is not installed.",error=True); return
        path,_=QFileDialog.getOpenFileName(self,"Attach PDF to Astra","","PDF files (*.pdf)")
        if not path: return
        try:
            text="\n".join((page.extract_text() or "") for page in PdfReader(path).pages[:12])[:22000]
            self.ai_attachments.append({"name":Path(path).name,"path":path,"text":text})
            self.ai_status.setText(f"PDF attached · {Path(path).name}")
            self._append_ai_message("System",f"Attached PDF: {Path(path).name}")
        except Exception as exc:
            self._append_ai_message("Astra error",f"Could not read PDF: {exc}",error=True)

    def load_ai_models(self):
        """Use the exact working Hash&KeGPT threading pattern for Gemini model discovery."""
        if getattr(self, "_models_loading", False):
            return
        self._models_loading = True
        self._populate_model_catalog(self.ai_client.FALLBACK_MODELS)
        if self.ai_status:
            self.ai_status.setText("Connecting to Gemini…")

        def run():
            try:
                models = self.ai_client.list_models()
                self._serneia_signals.models_loaded.emit(models)
            except Exception as exc:
                self._serneia_signals.models_failed.emit(str(exc))
            finally:
                self._models_loading = False

        threading.Thread(target=run, daemon=True).start()

    def _models_loaded(self, models):
        # Keep the dropdown populated even if Gemini answers with an empty list.
        if not models:
            models = self.ai_client.FALLBACK_MODELS
            status = "Using built-in Gemini model catalogue"
        else:
            status = f"{len(models)} Gemini models available"
        self._populate_model_catalog(models)
        if self.ai_status:
            self.ai_status.setText(status)

    def _models_failed(self, message):
        self._populate_model_catalog(self.ai_client.FALLBACK_MODELS)
        if self.ai_status:
            self.ai_status.setText("Using Gemini model catalogue")
        self._append_ai_message("Astra", f"Model list: {message}", error=True)

    def _update_ai_context_badge(self):
        selected=self._selected_record_context(self.current_module)
        if selected:
            self.ai_context_label.setText(f"Current module · {self.current_module}  ·  selected record")
        else:
            self.ai_context_label.setText(f"Current module · {self.current_module}")

    def toggle_ai(self, module):
        was_visible = self.ai_panel.isVisible()
        self.current_module = module
        selected=self._selected_record_context(module)
        suffix="  ·  selected record" if selected else ""
        self.ai_context_label.setText(f"Current module · {module}{suffix}")
        if was_visible and getattr(self, "_ai_open_module", module) == module:
            self.ai_panel.hide()
            return
        self._ai_open_module = module
        if not self._chat_busy:
            self.ai_input.setEnabled(True)
            self.ai_model.setEnabled(True)
            if getattr(self, "ai_send", None):
                self.ai_send.setEnabled(True)
        self.ai_panel.show()
        self._update_ai_context_badge()
        self.ai_input.setFocus()
        # This is the important part: clicking the Serneia button starts the
        # same live Gemini /models flow used by the Gemini API.
        self.load_ai_models()

    def _selected_record_context(self, module):
        table = None
        if module == "Customers": table = getattr(self, "customer_table", None)
        elif module == "Items": table = getattr(self, "item_table", None)
        elif module in ("Quotes", "Invoices"): table = self._doc_widgets(module).get("table")
        elif module == "Payments": table = getattr(self, "payment_table", None)
        elif module == "Receipts": table = getattr(self, "receipt_table", None)
        elif module in ("Ledger", "Inventory", "Documents", "Analytics", "Vendors", "Expenses", "Activity"):
            table = getattr(self, "tables", {}).get(module)
        if table is None or table.currentRow() < 0:
            return None
        values = {}
        for col in range(table.columnCount()):
            item = table.item(table.currentRow(), col)
            if item:
                values[table.horizontalHeaderItem(col).text()] = item.text()
        return values

    def build_ai_context(self, question=""):
        module=self.current_module
        context={"assistant_name":"Astra AI","application":"AURORA CLOUD — NEXUS","current_module":module,"available_modules":NAV[:],"data_policy":"Read-only ERP context. Astra may analyze and recommend, but must not invent or claim database changes.","database_source":"SQLite source of truth"}
        selected=self._selected_record_context(module)
        if selected: context["selected_visible_record"]=selected
        def rows(sql,params=(),limit=50): return [dict(r) for r in self.s.db.rows(sql,params)][:limit]
        try:
            terms=[t for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9._/-]{2,}",question.lower()) if t not in {"the","and","for","with","about","what","show","tell","please","give"}]
            customers=rows("SELECT * FROM customers ORDER BY archived ASC, company_name",limit=20)
            items=rows("SELECT * FROM items ORDER BY archived ASC, name",limit=20)
            vendors=rows("SELECT * FROM vendors ORDER BY archived ASC, name",limit=20)
            expenses=rows("SELECT e.*, v.name AS vendor FROM expenses e LEFT JOIN vendors v ON v.id=e.vendor_id ORDER BY e.expense_date DESC",limit=20)
            invoices=rows("SELECT d.*, c.company_name, c.email AS customer_email, c.phone AS customer_phone, c.address AS customer_address, c.tax_id AS customer_tax_id, COALESCE((SELECT SUM(amount) FROM payments p WHERE p.invoice_id=d.id),0) AS paid FROM documents d LEFT JOIN customers c ON c.id=d.customer_id WHERE d.kind='INVOICE' ORDER BY d.id DESC",limit=25)
            quotes=rows("SELECT d.*, c.company_name, c.email AS customer_email, c.phone AS customer_phone, c.address AS customer_address, c.tax_id AS customer_tax_id, COALESCE((SELECT SUM(amount) FROM payments p WHERE p.invoice_id=d.id),0) AS paid FROM documents d LEFT JOIN customers c ON c.id=d.customer_id WHERE d.kind='QUOTE' ORDER BY d.id DESC",limit=25)
            payments=rows("SELECT p.*, d.number AS invoice_number, d.total AS invoice_total, c.company_name FROM payments p JOIN documents d ON d.id=p.invoice_id LEFT JOIN customers c ON c.id=d.customer_id ORDER BY p.id DESC",limit=25)
            activity=rows("SELECT * FROM activity_log ORDER BY id DESC",limit=30)
            settings=rows("SELECT * FROM settings ORDER BY key",limit=30)
            context["counts"]={"customers":len(self.s.customers(include_archived=True)),"items":len(self.s.items(include_archived=True)),"vendors":len(self.s.vendors(include_archived=True)),"expenses":len(self.s.expenses()),"invoices":len(self.s.documents("INVOICE",include_archived=True)),"quotes":len(self.s.documents("QUOTE",include_archived=True)),"payments":len(self.s.payments()),"activity_entries":len(self.s.db.rows("SELECT id FROM activity_log"))}
            context["recent_erp_data"]={"customers":customers,"items":items,"vendors":vendors,"expenses":expenses,"invoices":invoices,"quotes":quotes,"payments":payments,"activity_log":activity,"settings":settings}
            if terms:
                def collect(records,keys,cap=8):
                    out=[]; seen=set()
                    for r in records:
                        rid=r.get("id"); hay=" ".join(str(r.get(k,"")) for k in keys).lower()
                        if rid not in seen and any(t in hay for t in terms): out.append(r); seen.add(rid)
                        if len(out)>=cap: break
                    return out
                context["question_matches"]={
                    "customers":collect(rows("SELECT * FROM customers ORDER BY id DESC",limit=200),["company_name","contact_person","email","phone","tax_id","notes"]),
                    "items":collect(rows("SELECT * FROM items ORDER BY id DESC",limit=200),["name","description","sku","supplier"]),
                    "vendors":collect(rows("SELECT * FROM vendors ORDER BY id DESC",limit=200),["name","contact_person","email","phone","notes"]),
                    "expenses":collect(rows("SELECT e.*, v.name AS vendor FROM expenses e LEFT JOIN vendors v ON v.id=e.vendor_id ORDER BY e.id DESC",limit=200),["description","vendor","notes"]),
                    "invoices":collect(rows("SELECT d.*, c.company_name FROM documents d LEFT JOIN customers c ON c.id=d.customer_id WHERE d.kind='INVOICE' ORDER BY d.id DESC",limit=200),["number","company_name","status","notes","terms"]),
                    "quotes":collect(rows("SELECT d.*, c.company_name FROM documents d LEFT JOIN customers c ON c.id=d.customer_id WHERE d.kind='QUOTE' ORDER BY d.id DESC",limit=200),["number","company_name","status","notes","terms"])}
            doc_ids=list(dict.fromkeys([int(x["id"]) for x in invoices+quotes if x.get("id") is not None]+[int(x["id"]) for b in (context.get("question_matches",{}).get("invoices",[]),context.get("question_matches",{}).get("quotes",[])) for x in b if x.get("id") is not None]))[:50]
            details=[]
            if doc_ids:
                ph=','.join('?' for _ in doc_ids); lr=rows(f"SELECT * FROM document_lines WHERE document_id IN ({ph}) ORDER BY document_id,id",tuple(doc_ids),limit=500); by={}
                for line in lr: by.setdefault(str(line["document_id"]),[]).append(line)
                pool=invoices+quotes+context.get("question_matches",{}).get("invoices",[])+context.get("question_matches",{}).get("quotes",[]); seen=set()
                for d in pool:
                    if d.get("id") in seen: continue
                    seen.add(d.get("id")); x=dict(d); x["lines"]=by.get(str(d["id"]),[]); details.append(x)
            context["documents_with_lines"]=details
            if selected and module in ("Quotes","Invoices") and selected.get("Number"):
                matched=next((d for d in details if d.get("number")==selected["Number"]),None)
                if matched:
                    context["selected_document"]=matched
                    context["selected_document_payments"]=rows("SELECT * FROM payments WHERE invoice_id=? ORDER BY id DESC",(matched["id"],),limit=50)
                    folder="Quotes" if matched.get("kind")=="QUOTE" else "Invoices"; pdf_path=self.root/"Documents"/folder/f"{matched['number']}.pdf"
                    context["selected_pdf"]={"path":str(pdf_path),"exists":pdf_path.exists()}
                    if pdf_path.exists() and PdfReader is not None:
                        try: context["selected_pdf"]["text"]="\n".join((page.extract_text() or "") for page in PdfReader(str(pdf_path)).pages[:8])[:16000]
                        except Exception as exc: context["selected_pdf"]["read_error"]=str(exc)
            if selected:
                if module=="Customers" and selected.get("ID"):
                    cid=int(selected["ID"]); context["selected_customer_history"]=rows("SELECT d.id,d.kind,d.number,d.issue_date,d.status,d.total,COALESCE((SELECT SUM(amount) FROM payments p WHERE p.invoice_id=d.id),0) AS paid FROM documents d WHERE d.customer_id=? ORDER BY d.id DESC LIMIT 30",(cid,),limit=30)
                elif module=="Items" and selected.get("ID"):
                    iid=int(selected["ID"]); context["selected_item_usage"]=rows("SELECT dl.document_id,d.kind,d.number,d.issue_date,d.status,dl.quantity,dl.rate,dl.discount,dl.tax_rate FROM document_lines dl JOIN documents d ON d.id=dl.document_id WHERE dl.item_id=? ORDER BY d.id DESC LIMIT 30",(iid,),limit=30)
                elif module=="Vendors":
                    name=selected.get("Vendor") or selected.get("Name")
                    if name: context["selected_vendor_expenses"]=rows("SELECT e.*,v.name AS vendor FROM expenses e LEFT JOIN vendors v ON v.id=e.vendor_id WHERE v.name=? ORDER BY e.id DESC LIMIT 30",(name,),limit=30)
            if self.ai_attachments:
                context["attached_pdfs"]=[{"name":x["name"],"text":x["text"]} for x in self.ai_attachments[-3:]]
            context["capabilities"]={"erp_database":"read-only contextual access to customers, items, vendors, expenses, invoices, quotes, payments, activity and settings","selected_record":True,"selected_document_lines":True,"generated_pdf_text":PdfReader is not None,"question_aware_retrieval":True,"attached_pdf_reading":bool(self.ai_attachments),"customer_history":True,"item_usage":True,"vendor_expense_history":True}
        except Exception as exc: context["context_error"]=str(exc)
        return context

    def _format_ai_message_html(self, speaker, message):
        """Build one safe, styled chat block. Kept separate so it is easy to test."""
        palette={
            "You": ("#3155D9", "#EEF4FF", "#172033"),
            "Astra": ("#047857", "#F0FDF4", "#16352A"),
            "Astra error": ("#B91C1C", "#FEF2F2", "#7F1D1D"),
            "System": ("#64748B", "#F8FAFC", "#334155"),
        }
        label_color, bg, text_color = palette.get(speaker, ("#6366F1", "#FFFFFF", "#1D1D1F"))
        safe_message = html.escape(str(message)).replace("\n", "<br>")
        safe_speaker = html.escape(str(speaker))
        return (
            f'<div style="margin:0 0 14px 0; padding:12px 14px; '
            f'background:{bg}; border:1px solid #E4E7EC; border-radius:14px;">'
            f'<div style="color:{label_color}; font-weight:800; margin-bottom:6px; '
            f'letter-spacing:.2px;">{safe_speaker}</div>'
            f'<div style="color:{text_color}; line-height:1.55;">{safe_message}</div>'
            f'</div>'
        )

    def _append_ai_message(self, speaker, message, error=False):
        """Append a styled Astra message using a single, safe HTML fragment."""
        if self.ai_chat is None:
            return
        cursor=self.ai_chat.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.ai_chat.setTextCursor(cursor)
        if self.ai_chat.toPlainText().strip():
            cursor.insertBlock()
        cursor.insertHtml(self._format_ai_message_html(speaker, message))
        cursor.insertBlock()
        self.ai_chat.ensureCursorVisible()

    def _submit_ai_message(self, *_args):
        """Single, deterministic submission path for Enter and Ask Astra."""
        if self.ai_input is None or not self.ai_input.isEnabled() or self._chat_busy:
            return
        question = self.ai_input.text().strip()
        if not question:
            return
        # Clear first. Even if any downstream UI formatting fails, the message
        # cannot remain trapped inside the composer.
        self.ai_input.clear()
        self.ask_serneia(question)

    def ask_serneia(self, question=None):
        question = (question if question is not None else self.ai_input.text()).strip()
        if not question or getattr(self, "_chat_busy", False):
            return
        model = self.ai_model.currentData() or self.ai_client.default_model
        self._append_ai_message("You", question)
        self.ai_input.setEnabled(False)
        self.ai_model.setEnabled(False)
        if getattr(self, "ai_send", None):
            self.ai_send.setEnabled(False)
        self.ai_status.setText(f"Astra is using {model}…")
        self._chat_busy = True

        # Match the proven Hash&KeGPT architecture: a plain Python background
        # thread performs the requests.post() call. Qt only receives the result.
        history=list(self._ai_history)
        context = self.build_ai_context(question)
        self._ai_history.append({"role":"user","content":question})
        def run():
            try:
                answer = self.ai_client.ask(question, context, model=model, history=history)
                self._serneia_signals.chat_finished.emit(answer)
            except Exception as exc:
                self._serneia_signals.chat_failed.emit(str(exc))

        threading.Thread(target=run, daemon=True).start()

    def _finish_chat_ui(self):
        self._chat_busy = False
        self.ai_input.setEnabled(True)
        self.ai_model.setEnabled(True)
        if getattr(self, "ai_send", None):
            self.ai_send.setEnabled(True)
        self.ai_input.setFocus()

    def _chat_finished(self, answer):
        self._ai_history.append({"role":"assistant","content":answer})
        self._append_ai_message("Astra", answer)
        self.ai_status.setText(f"Model: {self.ai_model.currentData() or self.ai_client.default_model}")
        self._finish_chat_ui()

    def _chat_failed(self, message):
        if self._ai_history and self._ai_history[-1].get("role")=="user": self._ai_history.pop()
        self._append_ai_message("Astra error", message, error=True)
        self.ai_status.setText("Astra request failed")
        self._finish_chat_ui()

    def _remove_visual_shadows(self):
        """Keep the desktop UI deliberately flat: remove any accidental Qt graphics shadows."""
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        for widget in self.findChildren(QWidget):
            effect = widget.graphicsEffect()
            if isinstance(effect, QGraphicsDropShadowEffect):
                widget.setGraphicsEffect(None)

    def label(self,text,style=""):
        w=QLabel(text); w.setObjectName(style); return w

    def go(self,name):
        self.stack.setCurrentIndex(NAV.index(name))
        self.current_module=name
        self.header_module.setText(name)
        for item_name, button in self.buttons.items():
            button.setChecked(item_name == name)
        self.refresh(name)

    def make_page(self,name):
        subtitles={"Dashboard":"A clear view of revenue, collections and operational activity.","Quotes":"Build, revise and convert customer quotes.","Invoices":"Create invoices, track payment status and issue PDFs.","Customers":"Keep customer contacts, billing information and history organized.","Items":"Manage products, prices, tax rates and stock.","Payments":"Record incoming payments and reconcile invoice balances.","Receipts":"View and issue professional payment receipts.","Ledger":"Follow invoice totals, collections and outstanding balances.","Inventory":"Monitor current stock, units and suppliers.","Expenses":"Track operating expenses and vendor costs.","Vendors":"Maintain supplier relationships and contact details.","Analytics":"Review customer revenue and business performance.","Documents":"Browse the complete document register.","Settings":"Control your business identity and local database health.","Activity":"Review the audit trail of changes and actions."}
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(34,28,34,28); l.setSpacing(16)
        h=QHBoxLayout(); h.setSpacing(12); h.addWidget(self.label(name,"page_title")); h.addStretch(); ask=QPushButton("✦ Ask Astra AI"); ask.setObjectName("compact_primary"); ask.clicked.connect(lambda checked=False,n=name:self.toggle_ai(n)); h.addWidget(ask); h.addSpacing(4); h.addWidget(self.label("AURORA NEXUS  ·  LOCAL","top_status")); l.addLayout(h)
        l.addWidget(self.label(subtitles.get(name,"Manage your business data."),"page_subtitle"))
        if name=="Dashboard": self.dashboard_page(l)
        elif name in ("Quotes","Invoices"): self.document_page(l,name)
        elif name=="Customers": self.customer_page(l)
        elif name=="Items": self.item_page(l)
        elif name=="Payments": self.payment_page(l)
        elif name=="Receipts": self.receipt_page(l)
        elif name=="Vendors": self.vendor_page(l)
        elif name=="Expenses": self.expense_page(l)
        elif name in ("Ledger","Documents","Activity","Inventory","Analytics"): self.report_page(l,name)
        else: self.settings_page(l)
        return w

    # ── Dashboard ──────────────────────────────────────────
    def dashboard_page(self,l):
        intro=QFrame(); intro.setObjectName("hero_card"); il=QHBoxLayout(intro); il.setContentsMargins(22,18,22,18); il.setSpacing(18)
        left=QVBoxLayout(); left.setSpacing(3); left.addWidget(self.label("Your business at a glance","hero_title")); left.addWidget(self.label("Monitor revenue, collections, documents and day-to-day activity from one place.","hero_subtitle")); il.addLayout(left,1)
        quick=QPushButton("✦  Ask Astra"); quick.setObjectName("compact_primary"); quick.clicked.connect(lambda:self.toggle_ai("Dashboard")); il.addWidget(quick); l.addWidget(intro)

        self.cards=QHBoxLayout(); self.cards.setSpacing(12); self.kpi_values={}
        for title in ("Revenue","Collected","Outstanding","Invoices","Quote conversion"):
            card=QFrame(); card.setObjectName("kpi_card"); cl=QVBoxLayout(card); cl.setContentsMargins(16,14,16,14); cl.setSpacing(3); cl.addWidget(self.label(title.upper(),"kpi_label")); value=self.label("—","kpi_value"); cl.addWidget(value); self.kpi_values[title]=value; self.cards.addWidget(card)
        l.addLayout(self.cards)

        qa=QFrame(); qa.setObjectName("quick_card"); ql=QHBoxLayout(qa); ql.setContentsMargins(14,10,14,10); ql.setSpacing(8); ql.addWidget(self.label("QUICK ACTIONS","section_caption"))
        for text,module in (("New Quote","Quotes"),("New Invoice","Invoices"),("Add Customer","Customers"),("Add Expense","Expenses")):
            b=QPushButton(text); b.setObjectName("secondary"); b.clicked.connect(lambda _=False,m=module:self.go(m)); ql.addWidget(b)
        ql.addWidget(self.label("","spacer"),1)
        bk=QPushButton("Create backup"); bk.setObjectName("ghost"); bk.clicked.connect(self.backup); ql.addWidget(bk); l.addWidget(qa)

        l.addWidget(self.label("Recent activity","section_title")); self.activity=QTableWidget(); self.activity.setColumnCount(3); self.activity.setHorizontalHeaderLabels(["When","Action","Details"]); self.activity.verticalHeader().setVisible(False); self.activity.setSelectionBehavior(QTableWidget.SelectRows); self.activity.setEditTriggers(QTableWidget.NoEditTriggers); self.activity.setSortingEnabled(True); self.activity.setAlternatingRowColors(True); self.activity.setColumnWidth(0,165); self.activity.setColumnWidth(1,180); l.addWidget(self.activity,1)

    # ── Documents ──────────────────────────────────────────
    def _doc_widgets(self, name=None):
        name = name or self.current_module
        return self.document_widgets[name]

    def _active_doc_lines(self):
        return self.document_lines[self.current_module]

    def document_page(self,l,name):
        kind="QUOTE" if name=="Quotes" else "INVOICE"
        w={}
        self.document_widgets[name]=w
        form=QGroupBox(f"New {name[:-1]}"); grid=QGridLayout(form); grid.setHorizontalSpacing(16); grid.setVerticalSpacing(12)
        w["customer"]=QComboBox(); w["customer"].setEditable(False); w["customer"].setInsertPolicy(QComboBox.NoInsert); w["customer"].setPlaceholderText("Select customer")
        w["customer"].setMaxVisibleItems(10); w["customer"].view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded); self._flatten_combo_popup(w["customer"])
        w["item"]=QComboBox(); w["item"].setEditable(False); w["item"].setInsertPolicy(QComboBox.NoInsert); w["item"].setPlaceholderText("Select item")
        w["item"].setMaxVisibleItems(10); w["item"].view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded); self._flatten_combo_popup(w["item"])
        w["qty"]=QDoubleSpinBox(); w["qty"].setValue(1); w["qty"].setMaximum(1e9); w["qty"].setDecimals(2)
        w["rate"]=QDoubleSpinBox(); w["rate"].setMaximum(1e9); w["rate"].setDecimals(2)
        w["tax"]=QDoubleSpinBox(); w["tax"].setMaximum(100); w["tax"].setDecimals(2)
        w["item"].currentIndexChanged.connect(lambda _=0, n=name: self._fill_item_defaults(n))
        add=QPushButton("+  Add line"); add.setObjectName("secondary"); add.clicked.connect(lambda _=False,n=name:self.add_line(n))
        w["lines"]=QTableWidget(0,6); w["lines"].setMinimumHeight(180); w["lines"].setMaximumHeight(240); w["lines"].setHorizontalHeaderLabels(["Item","Qty","Rate","Tax","Amount",""]); w["lines"].verticalHeader().setVisible(False); w["lines"].setAlternatingRowColors(True); w["lines"].setEditTriggers(QTableWidget.NoEditTriggers)
        save=QPushButton(f"Create {name[:-1]}"); save.setObjectName("primary"); save.clicked.connect(lambda _=False,k=kind,n=name:self.save_document(k,n))
        fields=(("Customer",w["customer"]),("Item",w["item"]),("Quantity",w["qty"]),("Rate (₹)",w["rate"]),("Tax %",w["tax"]))
        for i,(t,x) in enumerate(fields): grid.addWidget(QLabel(t),i//3*2,i%3); grid.addWidget(x,i//3*2+1,i%3)
        grid.addWidget(add,2,2); l.addWidget(form); l.addWidget(self.label("LINE ITEMS","section_caption")); l.addWidget(w["lines"]); l.addWidget(save)
        l.addWidget(self.label(f"SAVED {name.upper()}","section_caption"))
        tb=QHBoxLayout(); tb.setSpacing(6)
        w["view"]=QPushButton("View PDF"); w["view"].setObjectName("compact"); w["view"].clicked.connect(lambda _=False:self.selected_pdf(name)); w["view"].setEnabled(False)
        w["email"]=QPushButton("Email PDF"); w["email"].setObjectName("compact"); w["email"].clicked.connect(lambda _=False:self.email_selected_document(name)); w["email"].setEnabled(False)
        w["edit"]=QPushButton("Edit"); w["edit"].setObjectName("compact"); w["edit"].clicked.connect(lambda _=False:self.edit_selected_document(name)); w["edit"].setEnabled(False)
        w["duplicate"]=QPushButton("Duplicate"); w["duplicate"].setObjectName("compact"); w["duplicate"].clicked.connect(lambda _=False:self.duplicate_selected_document(name)); w["duplicate"].setEnabled(False)
        w["archive"]=QPushButton("Archive"); w["archive"].setObjectName("danger"); w["archive"].setStyleSheet("padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600;"); w["archive"].clicked.connect(lambda _=False:self.archive_selected_document(name)); w["archive"].setEnabled(False)
        for b in (w["view"],w["email"],w["edit"],w["duplicate"],w["archive"]): tb.addWidget(b)
        if name=="Quotes":
            w["convert"]=QPushButton("Convert to Invoice"); w["convert"].setObjectName("compact_primary"); w["convert"].clicked.connect(lambda _=False:self.convert_selected(name)); w["convert"].setEnabled(False); tb.addWidget(w["convert"])
            w["revise"]=QPushButton("Revise"); w["revise"].setObjectName("compact"); w["revise"].clicked.connect(lambda _=False:self.revise_selected(name)); w["revise"].setEnabled(False); tb.addWidget(w["revise"])
        tb.addStretch(); export=QPushButton("Export Excel"); export.setObjectName("compact"); export.clicked.connect(lambda _=False,k=kind:self.export_documents(k)); tb.addWidget(export); l.addLayout(tb)
        w["table"]=QTableWidget(); w["table"].setAlternatingRowColors(True); w["table"].setSelectionBehavior(QTableWidget.SelectRows); w["table"].setEditTriggers(QTableWidget.NoEditTriggers); w["table"].verticalHeader().setVisible(False); w["table"].itemSelectionChanged.connect(lambda n=name:self.update_doc_actions(n))
        l.addWidget(w["table"],1)

    def update_doc_actions(self,name):
        w=self._doc_widgets(name); has_sel=w["table"].currentRow()>=0
        for key in ("view","email","edit","duplicate","archive"): w[key].setEnabled(has_sel)
        if name=="Quotes": w["convert"].setEnabled(has_sel); w["revise"].setEnabled(has_sel)

    # ── Customers ──────────────────────────────────────────
    def customer_page(self,l):
        form=QGroupBox("New Customer"); row=QHBoxLayout(form); row.setSpacing(12); self.c_fields={}
        for key,title in (("company_name","Company *"),("contact_person","Contact"),("phone","Phone"),("email","Email"),("tax_id","GST / Tax ID")):
            e=QLineEdit(); e.setPlaceholderText(title); self.c_fields[key]=e; row.addWidget(e)
        add=QPushButton("Add customer"); add.setObjectName("primary"); add.clicked.connect(self.add_customer); row.addWidget(add); l.addWidget(form)
        tb=QHBoxLayout(); tb.setSpacing(6)
        self.c_edit_btn=QPushButton("Edit"); self.c_edit_btn.setObjectName("compact"); self.c_edit_btn.clicked.connect(self.edit_selected_customer); self.c_edit_btn.setEnabled(False)
        self.c_arch_btn=QPushButton("Archive"); self.c_arch_btn.setObjectName("danger"); self.c_arch_btn.setStyleSheet("padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600;"); self.c_arch_btn.clicked.connect(self.archive_selected_customer); self.c_arch_btn.setEnabled(False)
        tb.addWidget(self.c_edit_btn); tb.addWidget(self.c_arch_btn); tb.addStretch(); l.addLayout(tb)
        self.customer_table=QTableWidget(); self.customer_table.setAlternatingRowColors(True); self.customer_table.setSelectionBehavior(QTableWidget.SelectRows); self.customer_table.setEditTriggers(QTableWidget.NoEditTriggers); self.customer_table.verticalHeader().setVisible(False); self.customer_table.itemSelectionChanged.connect(lambda:[b.setEnabled(self.customer_table.currentRow()>=0) for b in (self.c_edit_btn,self.c_arch_btn)])
        l.addWidget(self.customer_table,1)

    # ── Items ──────────────────────────────────────────────
    def item_page(self,l):
        form=QGroupBox("New Item"); row=QHBoxLayout(form); row.setSpacing(12); self.i_fields={}
        for key,title in (("name","Item *"),("sku","SKU"),("unit","Unit"),("selling_price","Sell price"),("purchase_price","Purchase price"),("tax_rate","Tax %"),("stock","Stock"),("supplier","Supplier")):
            e=QLineEdit(); e.setPlaceholderText(title); self.i_fields[key]=e; row.addWidget(e)
        add=QPushButton("Add item"); add.setObjectName("primary"); add.clicked.connect(self.add_item); row.addWidget(add); l.addWidget(form)
        tb=QHBoxLayout(); tb.setSpacing(6)
        self.i_edit_btn=QPushButton("Edit"); self.i_edit_btn.setObjectName("compact"); self.i_edit_btn.clicked.connect(self.edit_selected_item); self.i_edit_btn.setEnabled(False)
        self.i_arch_btn=QPushButton("Archive"); self.i_arch_btn.setObjectName("danger"); self.i_arch_btn.setStyleSheet("padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600;"); self.i_arch_btn.clicked.connect(self.archive_selected_item); self.i_arch_btn.setEnabled(False)
        tb.addWidget(self.i_edit_btn); tb.addWidget(self.i_arch_btn); tb.addStretch(); l.addLayout(tb)
        self.item_table=QTableWidget(); self.item_table.setAlternatingRowColors(True); self.item_table.setSelectionBehavior(QTableWidget.SelectRows); self.item_table.setEditTriggers(QTableWidget.NoEditTriggers); self.item_table.verticalHeader().setVisible(False); self.item_table.itemSelectionChanged.connect(lambda:[b.setEnabled(self.item_table.currentRow()>=0) for b in (self.i_edit_btn,self.i_arch_btn)])
        l.addWidget(self.item_table,1)

    # ── Payments ───────────────────────────────────────────
    def payment_page(self,l):
        form=QGroupBox("Record Payment"); row=QHBoxLayout(form); row.setSpacing(12)
        self.pay_invoice=QComboBox(); self.pay_amount=QDoubleSpinBox(); self.pay_amount.setMaximum(1e9); self.pay_amount.setDecimals(2); self.pay_method=QComboBox(); self.pay_method.addItems(["Bank transfer","Cash","UPI","Card","Cheque"]); self.pay_reference=QLineEdit(); self.pay_reference.setPlaceholderText("Reference")
        b=QPushButton("Record payment"); b.setObjectName("primary"); b.clicked.connect(self.add_payment)
        for w in (self.pay_invoice,self.pay_amount,self.pay_method,self.pay_reference,b): row.addWidget(w)
        l.addWidget(form)
        tb=QHBoxLayout(); tb.setSpacing(6)
        self.p_del_btn=QPushButton("Delete"); self.p_del_btn.setObjectName("danger"); self.p_del_btn.setStyleSheet("padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600;"); self.p_del_btn.clicked.connect(self.delete_selected_payment); self.p_del_btn.setEnabled(False)
        tb.addWidget(self.p_del_btn); tb.addStretch(); l.addLayout(tb)
        self.payment_table=QTableWidget(); self.payment_table.setAlternatingRowColors(True); self.payment_table.setSelectionBehavior(QTableWidget.SelectRows); self.payment_table.setEditTriggers(QTableWidget.NoEditTriggers); self.payment_table.verticalHeader().setVisible(False); self.payment_table.itemSelectionChanged.connect(lambda: self.p_del_btn.setEnabled(self.payment_table.currentRow()>=0))
        l.addWidget(self.payment_table,1)

    # ── Receipts ───────────────────────────────────────────
    def receipt_page(self,l):
        l.addWidget(self.label("Receipt PDFs are generated automatically when a payment is recorded.","hint"))
        tb=QHBoxLayout(); tb.setSpacing(6)
        self.r_view_btn=QPushButton("View PDF"); self.r_view_btn.setObjectName("compact"); self.r_view_btn.clicked.connect(self.view_selected_receipt); self.r_view_btn.setEnabled(False)
        self.r_email_btn=QPushButton("Email PDF"); self.r_email_btn.setObjectName("compact"); self.r_email_btn.clicked.connect(self.email_selected_receipt); self.r_email_btn.setEnabled(False)
        tb.addWidget(self.r_view_btn); tb.addWidget(self.r_email_btn); tb.addStretch(); l.addLayout(tb)
        self.receipt_table=QTableWidget(); self.receipt_table.setAlternatingRowColors(True); self.receipt_table.setSelectionBehavior(QTableWidget.SelectRows); self.receipt_table.setEditTriggers(QTableWidget.NoEditTriggers); self.receipt_table.verticalHeader().setVisible(False); self.receipt_table.itemSelectionChanged.connect(lambda:[b.setEnabled(self.receipt_table.currentRow()>=0) for b in (self.r_view_btn,self.r_email_btn)])
        l.addWidget(self.receipt_table,1)

    # ── Vendors ────────────────────────────────────────────
    def vendor_page(self,l):
        form=QGroupBox("New Vendor"); row=QHBoxLayout(form); row.setSpacing(12); self.v_fields={}
        for key,title in (("name","Vendor *"),("contact_person","Contact"),("phone","Phone"),("email","Email"),("address","Address")):
            e=QLineEdit(); e.setPlaceholderText(title); self.v_fields[key]=e; row.addWidget(e)
        add=QPushButton("Add vendor"); add.setObjectName("primary"); add.clicked.connect(self.add_vendor); row.addWidget(add); l.addWidget(form)
        tb=QHBoxLayout(); tb.setSpacing(6)
        self.v_edit_btn=QPushButton("Edit"); self.v_edit_btn.setObjectName("compact"); self.v_edit_btn.clicked.connect(self.edit_selected_vendor); self.v_edit_btn.setEnabled(False)
        self.v_arch_btn=QPushButton("Archive"); self.v_arch_btn.setObjectName("danger"); self.v_arch_btn.setStyleSheet("padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600;"); self.v_arch_btn.clicked.connect(self.archive_selected_vendor); self.v_arch_btn.setEnabled(False)
        tb.addWidget(self.v_edit_btn); tb.addWidget(self.v_arch_btn); tb.addStretch(); l.addLayout(tb)
        self.vendor_table=QTableWidget(); self.vendor_table.setAlternatingRowColors(True); self.vendor_table.setSelectionBehavior(QTableWidget.SelectRows); self.vendor_table.setEditTriggers(QTableWidget.NoEditTriggers); self.vendor_table.verticalHeader().setVisible(False); self.vendor_table.itemSelectionChanged.connect(lambda:[b.setEnabled(self.vendor_table.currentRow()>=0) for b in (self.v_edit_btn,self.v_arch_btn)])
        l.addWidget(self.vendor_table,1)

    # ── Expenses ───────────────────────────────────────────
    def expense_page(self,l):
        form=QGroupBox("New Expense"); row=QHBoxLayout(form); row.setSpacing(12)
        self.e_vendor=QComboBox(); self.e_vendor.setPlaceholderText("No vendor (optional)"); self.e_vendor.setCurrentIndex(-1); self.e_vendor.setMaxVisibleItems(10); self.e_vendor.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded); self._flatten_combo_popup(self.e_vendor); self.e_desc=QLineEdit(); self.e_desc.setPlaceholderText("Description *"); self.e_amount=QDoubleSpinBox(); self.e_amount.setMaximum(1e9); self.e_amount.setDecimals(2); self.e_date=QLineEdit(); self.e_date.setPlaceholderText("YYYY-MM-DD"); self.e_date.setText(date.today().isoformat()); self.e_notes=QLineEdit(); self.e_notes.setPlaceholderText("Notes")
        b=QPushButton("Add expense"); b.setObjectName("primary"); b.clicked.connect(self.add_expense)
        for w in (self.e_vendor,self.e_desc,self.e_amount,self.e_date,self.e_notes,b): row.addWidget(w)
        l.addWidget(form)
        tb=QHBoxLayout(); tb.setSpacing(6)
        self.e_edit_btn=QPushButton("Edit"); self.e_edit_btn.setObjectName("compact"); self.e_edit_btn.clicked.connect(self.edit_selected_expense); self.e_edit_btn.setEnabled(False)
        self.e_del_btn=QPushButton("Delete"); self.e_del_btn.setObjectName("danger"); self.e_del_btn.setStyleSheet("padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600;"); self.e_del_btn.clicked.connect(self.delete_selected_expense); self.e_del_btn.setEnabled(False)
        tb.addWidget(self.e_edit_btn); tb.addWidget(self.e_del_btn); tb.addStretch(); l.addLayout(tb)
        self.expense_table=QTableWidget(); self.expense_table.setAlternatingRowColors(True); self.expense_table.setSelectionBehavior(QTableWidget.SelectRows); self.expense_table.setEditTriggers(QTableWidget.NoEditTriggers); self.expense_table.verticalHeader().setVisible(False); self.expense_table.itemSelectionChanged.connect(lambda:[b.setEnabled(self.expense_table.currentRow()>=0) for b in (self.e_edit_btn,self.e_del_btn)])
        l.addWidget(self.expense_table,1)

    # ── Reports & Settings ─────────────────────────────────
    def report_page(self,l,name):
        self.tables=getattr(self,"tables",{}); t=QTableWidget(); t.setAlternatingRowColors(True); t.setSelectionBehavior(QTableWidget.SelectRows); t.setEditTriggers(QTableWidget.NoEditTriggers); t.verticalHeader().setVisible(False); self.tables[name]=t; l.addWidget(t,1)

    def settings_page(self,l):
        l.addWidget(self.label("Application Settings","section_title"))
        form=QGroupBox("Identity"); fl=QVBoxLayout(form); fl.setSpacing(12)
        fl.addWidget(QLabel("Creator signature used across the application and PDF documents"))
        self.signature=QLineEdit(); self.signature.setText("by hash"); fl.addWidget(self.signature)
        save=QPushButton("Save signature"); save.setObjectName("primary"); save.clicked.connect(self.save_settings); fl.addWidget(save); l.addWidget(form)
        health=QGroupBox("Local database"); hl=QHBoxLayout(health); hl.setSpacing(12)
        self.db_health_label=QLabel("SQLite source of truth · Ready"); self.db_health_label.setObjectName("db_health"); hl.addWidget(self.db_health_label,1)
        check=QPushButton("Run health check"); check.setObjectName("secondary"); check.clicked.connect(self.check_database); hl.addWidget(check)
        l.addWidget(health); l.addStretch()

    # ── Actions: Documents ─────────────────────────────────
    def _resolve_customer_id(self, name):
        combo=self._doc_widgets(name)["customer"]
        data=combo.currentData()
        if data is not None:
            return int(data)
        text=combo.currentText().strip().lower()
        for x in self.s.customers():
            if str(x["company_name"]).strip().lower()==text:
                return int(x["id"])
        raise ValueError("Select an existing customer from the list (or type its exact company name).")

    def _resolve_item(self, name):
        combo=self._doc_widgets(name)["item"]
        data=combo.currentData()
        if data:
            return dict(data)
        text=combo.currentText().strip().lower()
        for x in self.s.items():
            if str(x["name"]).strip().lower()==text:
                return dict(x)
        raise ValueError("Select an existing item from the list (or type its exact item name).")

    def _fill_item_defaults(self, name):
        combo=self._doc_widgets(name)["item"]
        item=combo.currentData()
        if not item:
            return
        w=self._doc_widgets(name)
        row=dict(item)
        w["rate"].setValue(float(row.get("selling_price") or 0))
        w["tax"].setValue(float(row.get("tax_rate") or 0))

    def add_line(self,name=None):
        name=name or self.current_module
        w=self._doc_widgets(name)
        try:
            row=self._resolve_item(name)
            line={"item_id":row["id"],"description":row["name"],"unit":row["unit"],"quantity":w["qty"].value(),"rate":w["rate"].value() or row["selling_price"],"tax_rate":w["tax"].value() or row["tax_rate"],"discount":0}
            self.document_lines[name].append(line)
            self.draw_lines(name)
        except ValueError as e:
            self.warn(str(e))

    def draw_lines(self,name=None):
        name=name or self.current_module
        w=self._doc_widgets(name); lines=self.document_lines[name]
        w["lines"].setRowCount(0)
        for n,x in enumerate(lines):
            r=w["lines"].rowCount(); w["lines"].insertRow(r); amount=x["quantity"]*x["rate"]*(1+x["tax_rate"]/100)
            for c,v in enumerate((x["description"],x["quantity"],f"₹{x['rate']:,.2f}",f"{x['tax_rate']:g}%",f"₹{amount:,.2f}")): w["lines"].setItem(r,c,QTableWidgetItem(str(v)))
            b=QPushButton("×"); b.setObjectName("icon_btn"); b.setToolTip("Remove"); b.clicked.connect(lambda checked=False,i=n,nm=name:self.remove_line(i,nm)); w["lines"].setCellWidget(r,5,b)

    def remove_line(self,i,name=None):
        name=name or self.current_module
        self.document_lines[name].pop(i); self.draw_lines(name)

    def save_document(self,kind,name):
        try:
            customer_id=self._resolve_customer_id(name)
            lines=self.document_lines[name]
            if not lines:
                raise ValueError("Add at least one line item before creating the document.")
            doc=self.s.create_document(kind,customer_id,lines); path=self.e.pdf(doc); self.document_lines[name]=[]; self.draw_lines(name); self.info(f"{kind.title()} created and PDF generated.\n\n{path}"); self.refresh(name)
        except ValueError as e: self.warn(str(e))

    def selected_id(self,table):
        row=table.currentRow()
        if row<0: raise ValueError("Select a record first.")
        value=table.item(row,0).text() if table.item(row,0) else ""
        try:
            return int(value)
        except ValueError:
            match=re.search(r"(\d+)$", str(value))
            if match:
                return int(match.group(1))
            raise ValueError("The selected record does not have a valid ID.")

    def selected_payment_id(self):
        row=self.receipt_table.currentRow()
        if row<0: raise ValueError("Select a receipt first.")
        value=self.receipt_table.item(row,0).text() if self.receipt_table.item(row,0) else ""
        match=re.fullmatch(r"REC-(\d+)", str(value).strip(), re.IGNORECASE)
        if not match: raise ValueError("The selected receipt does not have a valid receipt number.")
        return int(match.group(1))

    def selected_pdf(self,name=None):
        name=name or self.current_module; w=self._doc_widgets(name)
        try: path=self.e.pdf(self.selected_id(w["table"])); self.info(f"PDF generated:\n\n{path}")
        except (ValueError,IndexError) as e: self.warn(str(e))

    def email_selected_document(self,name=None):
        name=name or self.current_module; w=self._doc_widgets(name)
        try:
            doc_id=self.selected_id(w["table"]); doc=self.s.document(doc_id); path=self.e.pdf(doc_id)
            QGuiApplication.clipboard().setText(str(path)); subject=f"{doc['kind'].replace('_',' ')} {doc['number']} from AURORA CLOUD"; body=f"Please find attached {doc['kind'].replace('_',' ')} {doc['number']}.\n\nPDF path (copied to clipboard): {path}"
            customer=doc["customer_id"]
            if customer:
                c=self.s.customer(customer); email=c["email"]
                if email: self.s.email_draft(email,subject,body); self.info(f"Email client opened. PDF copied to clipboard:\n{path}"); return
            self.s.email_draft("",subject,body); self.info(f"Email draft opened. PDF copied to clipboard:\n{path}")
        except (ValueError,IndexError) as e: self.warn(str(e))

    def edit_selected_document(self,name=None):
        name=name or self.current_module; w=self._doc_widgets(name)
        try: self.edit_document_dialog(self.selected_id(w["table"]))
        except (ValueError,IndexError) as e: self.warn(str(e))

    def duplicate_selected_document(self,name=None):
        name=name or self.current_module; w=self._doc_widgets(name)
        try:
            new_id=self.s.duplicate_document(self.selected_id(w["table"])); path=self.e.pdf(new_id); self.info(f"Document duplicated. PDF generated:\n\n{path}"); kind=self.s.document(new_id)["kind"]; self.refresh("Quotes" if kind=="QUOTE" else "Invoices")
        except (ValueError,IndexError) as e: self.warn(str(e))

    def archive_selected_document(self,name=None):
        name=name or self.current_module; w=self._doc_widgets(name)
        try:
            doc_id=self.selected_id(w["table"]); doc=self.s.document(doc_id)
            if self.confirm("Archive document?",f"Archive {doc['number']}? It will be hidden from main lists."): self.s.archive_document(doc_id); self.info("Document archived."); self.refresh("Quotes" if doc["kind"]=="QUOTE" else "Invoices")
        except (ValueError,IndexError) as e: self.warn(str(e))

    def convert_selected(self,name=None):
        name=name or self.current_module; w=self._doc_widgets(name)
        try: invoice=self.s.convert_quote(self.selected_id(w["table"])); path=self.e.pdf(invoice); self.info(f"Invoice created and PDF generated:\n\n{path}"); self.refresh("Quotes")
        except (ValueError,IndexError) as e: self.warn(str(e))

    def revise_selected(self,name=None):
        name=name or self.current_module; w=self._doc_widgets(name)
        try: new_id=self.s.revise_quote(self.selected_id(w["table"])); path=self.e.pdf(new_id); self.info(f"Quote revised and PDF generated:\n\n{path}"); self.refresh("Quotes")
        except (ValueError,IndexError) as e: self.warn(str(e))

    def export_documents(self,kind):
        docs=self.s.documents(kind); path=self.e.excel(kind.title()+"s",["Number","Customer","Date","Total","Paid","Status"],[(x["number"],x["company_name"],x["issue_date"],x["total"],x["paid"],x["status"]) for x in docs],self.root/"Reports"/f"{kind.lower()}s.xlsx"); self.info(f"Excel export created:\n\n{path}")

    # ── Actions: Customers ─────────────────────────────────
    def add_customer(self):
        try: self.s.create_customer({k:v.text() for k,v in self.c_fields.items()}); [v.clear() for v in self.c_fields.values()]; self.refresh("Customers")
        except ValueError as e: self.warn(str(e))

    def edit_selected_customer(self):
        try: self.edit_customer_dialog(self.selected_id(self.customer_table))
        except (ValueError,IndexError) as e: self.warn(str(e))

    def archive_selected_customer(self):
        try:
            cid=self.selected_id(self.customer_table); c=self.s.customer(cid)
            if self.confirm("Archive customer?",f"Archive {c['company_name']}?"): self.s.archive_customer(cid); self.info("Customer archived."); self.refresh("Customers")
        except (ValueError,IndexError) as e: self.warn(str(e))

    # ── Actions: Items ─────────────────────────────────────
    def add_item(self):
        try: self.s.create_item({k:v.text() for k,v in self.i_fields.items()}); [v.clear() for v in self.i_fields.values()]; self.refresh("Items")
        except ValueError as e: self.warn(str(e))

    def edit_selected_item(self):
        try: self.edit_item_dialog(self.selected_id(self.item_table))
        except (ValueError,IndexError) as e: self.warn(str(e))

    def archive_selected_item(self):
        try:
            iid=self.selected_id(self.item_table); item=self.s.item(iid)
            if self.confirm("Archive item?",f"Archive {item['name']}?"): self.s.archive_item(iid); self.info("Item archived."); self.refresh("Items")
        except (ValueError,IndexError) as e: self.warn(str(e))

    # ── Actions: Payments ──────────────────────────────────
    def add_payment(self):
        try: p=self.s.record_payment(self.pay_invoice.currentData(),self.pay_amount.value(),self.pay_method.currentText(),self.pay_reference.text(),""); path=self.e.receipt_pdf(p); self.info(f"Payment recorded. Receipt saved to:\n\n{path}"); self.refresh("Payments")
        except ValueError as e: self.warn(str(e))

    def delete_selected_payment(self):
        try:
            pid=self.selected_id(self.payment_table); p=self.s.payment(pid)
            if self.confirm("Delete payment?",f"Delete payment of ₹{p['amount']:,.2f} for {p['number']}?"): self.s.delete_payment(pid); self.info("Payment deleted."); self.refresh("Payments")
        except (ValueError,IndexError) as e: self.warn(str(e))

    # ── Actions: Receipts ──────────────────────────────────
    def view_selected_receipt(self):
        try: pid=self.selected_payment_id(); path=self.e.receipt_pdf(pid); self.info(f"Receipt PDF:\n\n{path}")
        except (ValueError,IndexError) as e: self.warn(str(e))

    def email_selected_receipt(self):
        try:
            pid=self.selected_payment_id(); p=self.s.payment(pid); path=self.e.receipt_pdf(pid)
            QGuiApplication.clipboard().setText(str(path))
            subject=f"Receipt for Invoice {p['number']} from AURORA CLOUD"
            body=f"Receipt #{pid:05d} for Invoice {p['number']}.\nAmount: ₹{p['amount']:,.2f}\n\nPDF copied to clipboard: {path}"
            if p["company_name"]:
                c=self.s.db.rows("SELECT email FROM customers WHERE company_name=?",(p["company_name"],))
                if c and c[0]["email"]: self.s.email_draft(c[0]["email"],subject,body); self.info(f"Email client opened. PDF copied to clipboard:\n{path}"); return
            self.s.email_draft("",subject,body); self.info(f"Email draft opened. PDF copied to clipboard:\n{path}")
        except (ValueError,IndexError) as e: self.warn(str(e))

    # ── Actions: Vendors ───────────────────────────────────
    def add_vendor(self):
        try: self.s.create_vendor({k:v.text() for k,v in self.v_fields.items()}); [v.clear() for v in self.v_fields.values()]; self.refresh("Vendors")
        except ValueError as e: self.warn(str(e))

    def edit_selected_vendor(self):
        try: self.edit_vendor_dialog(self.selected_id(self.vendor_table))
        except (ValueError,IndexError) as e: self.warn(str(e))

    def archive_selected_vendor(self):
        try:
            vid=self.selected_id(self.vendor_table); v=self.s.vendor(vid)
            if self.confirm("Archive vendor?",f"Archive {v['name']}?"): self.s.archive_vendor(vid); self.info("Vendor archived."); self.refresh("Vendors")
        except (ValueError,IndexError) as e: self.warn(str(e))

    # ── Actions: Expenses ──────────────────────────────────
    def add_expense(self):
        try:
            values={"vendor_id":self.e_vendor.currentData(),"description":self.e_desc.text(),"amount":self.e_amount.value(),"expense_date":self.e_date.text(),"notes":self.e_notes.text()}
            self.s.create_expense(values); self.e_desc.clear(); self.e_amount.setValue(0); self.e_notes.clear(); self.refresh("Expenses")
        except ValueError as e: self.warn(str(e))

    def edit_selected_expense(self):
        try: self.edit_expense_dialog(self.selected_id(self.expense_table))
        except (ValueError,IndexError) as e: self.warn(str(e))

    def delete_selected_expense(self):
        try:
            eid=self.selected_id(self.expense_table); ex=self.s.expense(eid)
            if self.confirm("Delete expense?",f"Delete '{ex['description']}?'"): self.s.delete_expense(eid); self.info("Expense deleted."); self.refresh("Expenses")
        except (ValueError,IndexError) as e: self.warn(str(e))

    # ── Dialogs ────────────────────────────────────────────
    def edit_customer_dialog(self,cid):
        c=self.s.customer(cid); d=QDialog(self); d.setWindowTitle("Edit Customer"); d.setMinimumWidth(520); l=QVBoxLayout(d); l.setSpacing(14); fields={}
        for key,title in [("company_name","Company *"),("contact_person","Contact"),("phone","Phone"),("email","Email"),("tax_id","GST / Tax ID"),("address","Address"),("notes","Notes")]:
            e=QLineEdit(); e.setPlaceholderText(title); e.setText(c[key] or ""); fields[key]=e; l.addWidget(e)
        btns=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); btns.accepted.connect(lambda:self._save_customer(d,cid,fields)); btns.rejected.connect(d.reject); l.addWidget(btns); d.exec()

    def _save_customer(self,dialog,cid,fields):
        try: self.s.update_customer(cid,{k:v.text() for k,v in fields.items()}); dialog.accept(); self.info("Customer updated."); self.refresh("Customers")
        except ValueError as e: self.warn(str(e))

    def edit_item_dialog(self,iid):
        item=self.s.item(iid); d=QDialog(self); d.setWindowTitle("Edit Item"); d.setMinimumWidth(520); l=QVBoxLayout(d); l.setSpacing(14); fields={}
        for key,title in [("name","Item *"),("sku","SKU"),("unit","Unit"),("selling_price","Sell price"),("purchase_price","Purchase price"),("tax_rate","Tax %"),("stock","Stock"),("supplier","Supplier"),("description","Description")]:
            e=QLineEdit(); e.setPlaceholderText(title); e.setText(str(item[key] or "")); fields[key]=e; l.addWidget(e)
        btns=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); btns.accepted.connect(lambda:self._save_item(d,iid,fields)); btns.rejected.connect(d.reject); l.addWidget(btns); d.exec()

    def _save_item(self,dialog,iid,fields):
        try: self.s.update_item(iid,{k:v.text() for k,v in fields.items()}); dialog.accept(); self.info("Item updated."); self.refresh("Items")
        except ValueError as e: self.warn(str(e))

    def edit_document_dialog(self,doc_id):
        doc=self.s.document(doc_id); d=QDialog(self); d.setWindowTitle(f"Edit {doc['number']}"); d.setMinimumWidth(520); l=QVBoxLayout(d); l.setSpacing(14)
        l.addWidget(QLabel("Status")); status=QComboBox(); status.addItems(["DRAFT","ISSUED","CANCELLED"]); status.setCurrentText(doc["status"]); l.addWidget(status)
        l.addWidget(QLabel("Notes")); notes=QTextEdit(); notes.setText(doc["notes"] or ""); notes.setMaximumHeight(100); l.addWidget(notes)
        l.addWidget(QLabel("Terms")); terms=QTextEdit(); terms.setText(doc["terms"] or ""); terms.setMaximumHeight(100); l.addWidget(terms)
        btns=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); btns.accepted.connect(lambda:self._save_doc(d,doc_id,status,notes,terms)); btns.rejected.connect(d.reject); l.addWidget(btns); d.exec()

    def _save_doc(self,dialog,doc_id,status,notes,terms):
        try: self.s.update_document(doc_id,{"status":status.currentText(),"notes":notes.toPlainText(),"terms":terms.toPlainText()}); dialog.accept(); self.info("Document updated."); self.refresh("Quotes" if self.s.document(doc_id)["kind"]=="QUOTE" else "Invoices")
        except ValueError as e: self.warn(str(e))

    def edit_vendor_dialog(self,vid):
        v=self.s.vendor(vid); d=QDialog(self); d.setWindowTitle("Edit Vendor"); d.setMinimumWidth(520); l=QVBoxLayout(d); l.setSpacing(14); fields={}
        for key,title in [("name","Vendor *"),("contact_person","Contact"),("phone","Phone"),("email","Email"),("address","Address"),("notes","Notes")]:
            e=QLineEdit(); e.setPlaceholderText(title); e.setText(v[key] or ""); fields[key]=e; l.addWidget(e)
        btns=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); btns.accepted.connect(lambda:self._save_vendor(d,vid,fields)); btns.rejected.connect(d.reject); l.addWidget(btns); d.exec()

    def _save_vendor(self,dialog,vid,fields):
        try: self.s.update_vendor(vid,{k:v.text() for k,v in fields.items()}); dialog.accept(); self.info("Vendor updated."); self.refresh("Vendors")
        except ValueError as e: self.warn(str(e))

    def edit_expense_dialog(self,eid):
        ex=self.s.expense(eid); d=QDialog(self); d.setWindowTitle("Edit Expense"); d.setMinimumWidth(520); l=QVBoxLayout(d); l.setSpacing(14)
        vendor=QComboBox(); vendor.setPlaceholderText("No vendor (optional)"); vendor.setMaxVisibleItems(10); vendor.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded); [vendor.addItem(x["name"],x["id"]) for x in self.s.vendors()]
        vendor.setCurrentIndex(next((i for i in range(vendor.count()) if vendor.itemData(i)==ex["vendor_id"]),-1) if ex["vendor_id"] else -1)
        l.addWidget(QLabel("Vendor")); l.addWidget(vendor)
        desc=QLineEdit(); desc.setText(ex["description"]); l.addWidget(QLabel("Description")); l.addWidget(desc)
        amount=QDoubleSpinBox(); amount.setMaximum(1e9); amount.setDecimals(2); amount.setValue(ex["amount"]); l.addWidget(QLabel("Amount")); l.addWidget(amount)
        date=QLineEdit(); date.setText(ex["expense_date"]); l.addWidget(QLabel("Date")); l.addWidget(date)
        notes=QLineEdit(); notes.setText(ex["notes"] or ""); l.addWidget(QLabel("Notes")); l.addWidget(notes)
        btns=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); btns.accepted.connect(lambda:self._save_expense(d,eid,vendor,desc,amount,date,notes)); btns.rejected.connect(d.reject); l.addWidget(btns); d.exec()

    def _save_expense(self,dialog,eid,vendor,desc,amount,date,notes):
        try: self.s.update_expense(eid,{"vendor_id":vendor.currentData(),"description":desc.text(),"amount":amount.value(),"expense_date":date.text(),"notes":notes.text()}); dialog.accept(); self.info("Expense updated."); self.refresh("Expenses")
        except ValueError as e: self.warn(str(e))

    # ── Helpers ────────────────────────────────────────────
    def backup(self): self.info(f"Backup created:\n\n{self.s.db.backup()}")

    def check_database(self):
        try:
            h=self.s.db.health_check()
            ok=str(h["integrity"]).lower()=="ok"
            self.db_health_label.setText(("●  Database healthy" if ok else "●  Database check reported an issue") + f"   ·   {h['documents']} documents   ·   {h['customers']} customers   ·   {h['payments']} payments")
            if not ok: self.warn(f"SQLite integrity check: {h['integrity']}")
        except Exception as exc:
            self.db_health_label.setText("●  Database check failed")
            self.warn(str(exc))

    def save_settings(self):
        with self.s.db.transaction() as db: db.execute("UPDATE settings SET value=? WHERE key='signature'",(self.signature.text().strip() or "by hash",)); self.s.db.log(db,"Settings updated")
        self.info("Settings saved.")

    def fill(self,t,headers,rows):
        t.setSortingEnabled(False)
        t.setColumnCount(len(headers)); t.setHorizontalHeaderLabels(headers); t.setRowCount(0)
        for values in rows:
            r=t.rowCount(); t.insertRow(r)
            for c,v in enumerate(values): t.setItem(r,c,QTableWidgetItem(str(v if v is not None else "")))
        t.resizeColumnsToContents(); t.horizontalHeader().setStretchLastSection(True); t.setSortingEnabled(True)

    def refresh(self,name):
        if name=="Dashboard":
            d=self.s.dashboard()
            values={"Revenue":f"₹{d['revenue']:,.2f}","Collected":f"₹{d['collected']:,.2f}","Outstanding":f"₹{d['outstanding']:,.2f}","Invoices":str(d['invoices']),"Quote conversion":f"{d['converted']}/{d['quotes']}" if d['quotes'] else "0/0"}
            for title,val in values.items():
                if title in self.kpi_values: self.kpi_values[title].setText(val)
            self.fill(self.activity,["When","Action","Details"],[(x["created_at"],x["action"],x["detail"]) for x in self.s.db.rows("SELECT * FROM activity_log ORDER BY id DESC LIMIT 12")])
            self.db_badge.setText("●  LOCAL DATABASE · SYNCED")
        elif name=="Customers": self.fill(self.customer_table,["ID","Company","Contact","Phone","Email","GST"],[(x["id"],x["company_name"],x["contact_person"],x["phone"],x["email"],x["tax_id"]) for x in self.s.customers()])
        elif name=="Items": self.fill(self.item_table,["ID","Item","SKU","Unit","Selling","Tax","Stock","Supplier"],[(x["id"],x["name"],x["sku"],x["unit"],x["selling_price"],x["tax_rate"],x["stock"],x["supplier"]) for x in self.s.items()])
        elif name in ("Quotes","Invoices"):
            kind="QUOTE" if name=="Quotes" else "INVOICE"; docs=self.s.documents(kind); w=self._doc_widgets(name); self.fill(w["table"],["ID","Number","Customer","Date","Total","Paid","Status"],[(x["id"],x["number"],x["company_name"],x["issue_date"],f"₹{x['total']:,.2f}",f"₹{x['paid']:,.2f}",x["status"]) for x in docs])
            current_customer_id=w["customer"].currentData(); current_item_id=(w["item"].currentData() or {}).get("id") if isinstance(w["item"].currentData(),dict) else None
            w["customer"].clear(); [w["customer"].addItem(x["company_name"],x["id"]) for x in self.s.customers()]
            w["item"].clear(); [w["item"].addItem(x["name"],dict(x)) for x in self.s.items()]
            cidx=w["customer"].findData(current_customer_id) if current_customer_id is not None else -1
            iidx=-1
            if current_item_id is not None:
                for idx in range(w["item"].count()):
                    data=w["item"].itemData(idx)
                    if isinstance(data,dict) and data.get("id")==current_item_id:
                        iidx=idx; break
            w["customer"].setCurrentIndex(cidx if cidx >= 0 else -1)
            w["item"].setCurrentIndex(iidx if iidx >= 0 else -1)
            self.draw_lines(name)
        elif name=="Payments":
            rows=self.s.payments(); self.fill(self.payment_table,["ID","Invoice","Customer","Amount","Method","Date","Reference"],[(x["id"],x["number"],x["company_name"],f"₹{x['amount']:,.2f}",x["method"],x["payment_date"],x["reference"]) for x in rows]); self.pay_invoice.clear(); [self.pay_invoice.addItem(f"{x['number']} · ₹{self.s.outstanding(x['id']):,.2f} due",x['id']) for x in self.s.documents("INVOICE") if self.s.outstanding(x['id'])>0.005]
        elif name=="Receipts":
            rows=self.s.payments(); self.fill(self.receipt_table,["Receipt","Invoice","Customer","Amount","Date"],[(f"REC-{x['id']:05d}",x["number"],x["company_name"],f"₹{x['amount']:,.2f}",x["payment_date"]) for x in rows])
        elif name=="Ledger": self.fill(self.tables[name],["Invoice","Customer","Total","Paid","Outstanding"],[(x["number"],x["company_name"],x["total"],x["paid"],f"{x['total']-x['paid']:.2f}") for x in self.s.documents("INVOICE")])
        elif name=="Inventory": self.fill(self.tables[name],["Item","Stock","Unit","Supplier"],[(x["name"],x["stock"],x["unit"],x["supplier"]) for x in self.s.items()])
        elif name=="Documents":
            rows=self.s.db.rows("SELECT d.*,c.company_name FROM documents d LEFT JOIN customers c ON c.id=d.customer_id ORDER BY d.id DESC"); self.fill(self.tables[name],["Type","Number","Customer","Date","Total","Status"],[(x["kind"],x["number"],x["company_name"],x["issue_date"],x["total"],x["status"]) for x in rows])
        elif name=="Analytics":
            rows=self.s.db.rows("SELECT c.company_name,COALESCE(SUM(d.total),0) total FROM customers c LEFT JOIN documents d ON d.customer_id=c.id AND d.kind='INVOICE' GROUP BY c.id ORDER BY total DESC"); self.fill(self.tables[name],["Customer","Invoice revenue"],[(x["company_name"],f"₹{x['total']:,.2f}") for x in rows])
        elif name=="Vendors": self.fill(self.tables[name],["Vendor","Contact","Phone","Email"],[(x["name"],x["contact_person"],x["phone"],x["email"]) for x in self.s.vendors()])
        elif name=="Expenses":
            current_vendor_id=self.e_vendor.currentData()
            self.e_vendor.clear(); [self.e_vendor.addItem(x["name"],x["id"]) for x in self.s.vendors()]
            self.e_vendor.setCurrentIndex(self.e_vendor.findData(current_vendor_id) if current_vendor_id is not None else -1)
            self.fill(self.tables[name],["Date","Description","Vendor","Amount"],[(x["expense_date"],x["description"],x["vendor"],f"₹{x['amount']:,.2f}") for x in self.s.expenses()])
        elif name=="Activity": self.fill(self.tables[name],["When","Action","Entity","Details"],[(x["created_at"],x["action"],x["entity_type"],x["detail"]) for x in self.s.db.rows("SELECT * FROM activity_log ORDER BY id DESC")])
        elif name=="Settings":
            sig=self.s.db.rows("SELECT value FROM settings WHERE key='signature'")
            if sig: self.signature.setText(sig[0]["value"])

    def confirm(self,title,text):
        return QMessageBox.question(self,title,text,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes

    def warn(self,text): QMessageBox.warning(self,"Aurora Nexus",text)
    def info(self,text): QMessageBox.information(self,"Aurora Nexus",text)
