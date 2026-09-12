# AURORA CLOUD — NEXUS · Astra AI Edition

This additive upgrade keeps the existing ERP modules, navigation, document workflows, payments, receipts, exports, backups and Groq integration intact while polishing the interface and extending Astra.

## UI upgrades
- Integrated Aurora Cloud / Nexus identity card with cleaner hierarchy.
- Refined sidebar, page headers, spacing, cards, tables, buttons and inputs.
- New top application bar with module breadcrumb and global ERP search.
- Ctrl+K global search for modules and common customer/item/vendor/invoice/quote records.
- Dashboard KPI cards, quick actions and a cleaner activity area.
- Existing tables now support sorting.

## Astra AI upgrades
- Existing working direct Groq HTTP architecture preserved.
- Distinct visual treatment for You, Astra and System messages.
- Quick prompt chips for overview, outstanding balances, latest transactions and selected-record explanations.
- Copy and clear chat actions.
- Attach PDF to Astra: extracts PDF text locally and sends the selected text as context.
- Conversation memory across the current Astra session.
- More targeted ERP context for selected customers, items, vendors and documents.
- Selected generated invoice/quote PDF text remains available to Astra.
- SQLite remains the source of truth; Astra is read-only for business facts.

## SQLite reliability
- WAL journal mode for smoother concurrent reads/writes.
- Busy timeout and normal synchronous mode.
- Additional indexes for common document, customer, item, vendor, expense and payment lookups.
- Settings includes a database integrity/health check.

## PDF
- Existing premium invoice / quote / receipt designs are preserved.
- Base Helvetica PDF currency remains `INR` to avoid unsupported glyph squares.

## Setup
```cmd
python -m venv .venv
.venv\\Scripts\\activate
python -m pip install -r requirements.txt
python main.py
```

## Smoke test
```cmd
python SMOKE_TEST.py
```
Expected result includes:
- database PASS
- invoice PDF PASS
- receipt PDF PASS
- Groq chat mock PASS
