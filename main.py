from __future__ import annotations
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from app.database import Database
from app.services import BusinessService
from app.documents import DocumentEngine
from app.ui import Window

ROOT = Path(__file__).resolve().parent

# Apple-inspired light palette — SF Pro feel, generous whitespace, subtle depth
STYLE = """
/* ── Global ─────────────────────────────────────────── */
QMainWindow, QWidget {
    background: #F7F7F9;
    color: #1D1D1F;
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Segoe UI Variable', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
    outline: none;
}

QLabel { background: transparent; }


/* ── Aurora identity ───────────────────────────────── */
QFrame#brand_card { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FFFFFF, stop:1 #F7F7FB); border: 1px solid #E8E8F0; border-radius: 18px; }
QLabel#logo_mark { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7C83FF, stop:1 #5B5FEF); color: #FFFFFF; border-radius: 13px; min-width: 42px; max-width: 42px; min-height: 42px; max-height: 42px; qproperty-alignment: AlignCenter; font-size: 18px; font-weight: 900; }
QLabel#brand { color: #111113; font-size: 16px; font-weight: 850; letter-spacing: -0.35px; }
QLabel#subbrand { color: #636366; font-size: 11px; font-weight: 800; letter-spacing: 1.1px; }
QLabel#brand_tag { color: #8A8A94; font-size: 8px; font-weight: 800; letter-spacing: 0.55px; }
QLabel#signature { color: #059669; font-size: 8px; font-weight: 800; letter-spacing: 0.75px; background: transparent; }

/* ── Sidebar ────────────────────────────────────────── */
QFrame#sidebar {
    background: #FBFBFD;
    border-right: 1px solid #E7E7EC;
}

QLabel#logo_mark {
    background: #6366F1;
    color: #FFFFFF;
    border-radius: 10px;
    min-width: 32px; max-width: 32px;
    min-height: 32px; max-height: 32px;
    qproperty-alignment: AlignCenter;
    font-size: 15px;
    font-weight: 800;
}

QLabel#brand {
    color: #1D1D1F;
    font-size: 15px;
    font-weight: 800;
    letter-spacing: -0.3px;
}

QLabel#subbrand {
    color: #86868B;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.6px;
}

QLabel#signature {
    color: #059669;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 0.8px;
    padding-top: 2px;
    background: transparent;
}

QLabel#nav_caption {
    color: #86868B;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    padding: 16px 12px 6px;
}

QPushButton#nav { text-align: left; color: #68686F; background: transparent; border: 1px solid transparent; padding: 10px 14px; border-radius: 12px; font-size: 13px; font-weight: 650; margin: 2px 6px; }
QPushButton#nav:hover { color: #1D1D1F; background: #F3F3F8; border-color: #EBEBF2; }
QPushButton#nav:checked { color: #5148E5; background: #EEF0FF; border-color: #E0E3FF; font-weight: 750; }

/* ── Buttons ────────────────────────────────────────── */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #818CF8, stop:1 #6366F1);
    color: #FFFFFF;
    border: none;
    padding: 10px 20px;
    border-radius: 12px;
    font-weight: 600;
    font-size: 13px;
    min-height: 20px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #6366F1, stop:1 #4F46E5);
}
QPushButton:pressed {
    background: #4338CA;
}
QPushButton:disabled {
    background: #E5E5EA;
    color: #C7C7CC;
}

QPushButton#secondary {
    background: #FFFFFF;
    color: #1D1D1F;
    border: 1px solid #D2D2D7;
    font-weight: 600;
}
QPushButton#secondary:hover {
    background: #F5F5F7;
    border-color: #C7C7CC;
}
QPushButton#secondary:pressed {
    background: #E5E5EA;
}

QPushButton#danger {
    background: #FFF5F5;
    color: #DC2626;
    border: 1px solid #FECACA;
    font-weight: 600;
}
QPushButton#danger:hover {
    background: #FEE2E2;
    border-color: #FCA5A5;
}

QPushButton#ghost {
    background: transparent;
    color: #6366F1;
    border: none;
    padding: 6px 10px;
    font-weight: 600;
    border-radius: 8px;
}
QPushButton#ghost:hover {
    background: #EEF2FF;
}

QPushButton#compact {
    background: #FFFFFF;
    color: #1D1D1F;
    border: 1px solid #E5E5EA;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    min-height: 16px;
}
QPushButton#compact:hover {
    background: #F5F5F7;
    border-color: #D2D2D7;
}

QPushButton#compact_primary {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #818CF8, stop:1 #6366F1);
    color: #FFFFFF;
    border: none;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    min-height: 16px;
}
QPushButton#compact_primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #6366F1, stop:1 #4F46E5);
}

QPushButton#icon_btn {
    background: transparent;
    color: #86868B;
    border: none;
    padding: 6px;
    border-radius: 8px;
    font-weight: 600;
    min-width: 28px; max-width: 28px;
    min-height: 28px; max-height: 28px;
}
QPushButton#icon_btn:hover {
    background: #F5F5F7;
    color: #6366F1;
}

/* ── Inputs ─────────────────────────────────────────── */
QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit, QDateEdit {
    background: #FFFFFF;
    color: #1D1D1F;
    border: 1px solid #D2D2D7;
    padding: 10px 12px;
    border-radius: 10px;
    min-height: 20px;
    font-size: 13px;
    selection-background-color: #6366F1;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QTextEdit:focus, QDateEdit:focus {
    border: 2px solid #6366F1;
    padding: 9px 11px;
}
QLineEdit::placeholder, QTextEdit::placeholder {
    color: #C7C7CC;
}

QComboBox::drop-down {
    border: 0;
    width: 28px;
}
QComboBox QAbstractItemView {
    background: #FFFFFF;
    color: #1D1D1F;
    selection-background-color: #EEF2FF;
    selection-color: #4F46E5;
    border: 1px solid #E0E2EA;
    border-radius: 10px;
    padding: 6px;
    outline: none;
    show-decoration-selected: 1;
}
QAbstractItemView {
    background: #FFFFFF;
    color: #1D1D1F;
    border: 1px solid #E0E2EA;
    outline: none;
}

QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 20px;
    border: none;
    background: transparent;
}

/* ── Tables ─────────────────────────────────────────── */
QTableWidget {
    background: #FFFFFF;
    color: #1D1D1F;
    border: 1px solid #E5E5EA;
    gridline-color: transparent;
    border-radius: 16px;
    alternate-background-color: #FAFAFA;
    selection-background-color: #EEF2FF;
    selection-color: #1D1D1F;
    outline: none;
}
QTableWidget::item {
    padding: 10px 14px;
    border-bottom: 1px solid #F5F5F7;
}
QTableWidget::item:hover {
    background: #F9FAFB;
}
QTableWidget::item:selected {
    background: #EEF2FF;
    color: #1D1D1F;
}
QHeaderView::section {
    background: #FAFAFA;
    border: 0;
    border-bottom: 1px solid #E5E5EA;
    padding: 12px 14px;
    font-size: 11px;
    font-weight: 700;
    color: #86868B;
    text-transform: uppercase;
    letter-spacing: 0.6px;
}
QHeaderView::section:hover {
    background: #F5F5F7;
}

/* ── Scrollbars ─────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 4px;
}
QScrollBar::handle:vertical {
    background: #D2D2D7;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #8E8E93;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 4px;
}
QScrollBar::handle:horizontal {
    background: #D2D2D7;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #8E8E93;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ── Tooltips ───────────────────────────────────────── */
QToolTip {
    background: #1D1D1F;
    color: #FFFFFF;
    border: 0;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
}

/* ── Typography tokens ──────────────────────────────── */
QLabel#page_title {
    font-size: 34px;
    font-weight: 700;
    color: #1D1D1F;
    letter-spacing: -1px;
    padding-bottom: 4px;
}
QLabel#page_subtitle {
    font-size: 14px;
    color: #86868B;
    font-weight: 500;
    padding-bottom: 16px;
}
QLabel#top_status {
    background: #EEF2FF;
    color: #6366F1;
    border-radius: 20px;
    padding: 6px 14px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.4px;
}
QLabel#section_title {
    font-size: 20px;
    font-weight: 700;
    color: #1D1D1F;
    padding: 8px 0;
    letter-spacing: -0.4px;
}
QLabel#section_caption {
    color: #86868B;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    padding-top: 4px;
    background: transparent;
}
QLabel#card {
    background: #FFFFFF;
    border: 1px solid #E5E5EA;
    border-radius: 20px;
    padding: 24px;
    font-size: 13px;
    color: #86868B;
    line-height: 160%;
}
QLabel#card_value {
    color: #1D1D1F;
    font-size: 32px;
    font-weight: 700;
    letter-spacing: -0.8px;
    padding-top: 6px;
}
QLabel#card_label {
    color: #86868B;
    font-size: 13px;
    font-weight: 600;
    padding-bottom: 2px;
}
QLabel#hint {
    color: #86868B;
    padding: 8px 0;
    font-size: 13px;
    line-height: 150%;
}
QLabel#empty_title {
    color: #1D1D1F;
    font-size: 16px;
    font-weight: 600;
    padding-top: 12px;
}
QLabel#empty_subtitle {
    color: #86868B;
    font-size: 13px;
    padding-top: 4px;
}

/* ── Group boxes (cards) ────────────────────────────── */
QGroupBox {
    background: #FFFFFF;
    border: 1px solid #E5E5EA;
    border-radius: 20px;
    margin-top: 12px;
    padding: 24px;
    font-weight: 700;
    color: #1D1D1F;
    font-size: 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
    color: #1D1D1F;
    font-weight: 700;
    font-size: 14px;
}

/* ── Status badges ──────────────────────────────────── */
QLabel#status_draft {
    background: #F5F5F7;
    color: #6E6E73;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#status_issued {
    background: #EEF2FF;
    color: #6366F1;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#status_paid {
    background: #F0FDF4;
    color: #16A34A;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#status_overdue {
    background: #FFF7ED;
    color: #EA580C;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#status_archived {
    background: #F5F5F7;
    color: #A1A1AA;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
    text-decoration: line-through;
}
QLabel#status_superseded {
    background: #F5F5F7;
    color: #A1A1AA;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
}

/* ── Dialogs ────────────────────────────────────────── */
QDialog {
    background: #F5F5F7;
}
QDialog QLineEdit, QDialog QComboBox, QDialog QDoubleSpinBox, QDialog QTextEdit {
    background: #FFFFFF;
}
QMessageBox {
    background: #FFFFFF;
}
QDialogButtonBox QPushButton {
    padding: 8px 16px;
    border-radius: 10px;
    font-size: 13px;
}

/* ── Splitter ───────────────────────────────────────── */
QSplitter::handle {
    background: #E5E5EA;
}
/* ── 2026 polish layer ─────────────────────────────── */
QWidget#content_shell { background: #F6F7FB; }
QFrame#app_topbar { background: rgba(255,255,255,0.96); border-bottom: 1px solid #E9EAF0; }
QLabel#topbar_module { color: #18181B; font-size: 16px; font-weight: 800; }
QLabel#topbar_path { color: #A1A1AA; font-size: 11px; font-weight: 600; letter-spacing: .2px; }
QLineEdit#global_search { background: #F8F9FC; border: 1px solid #E5E7EB; border-radius: 11px; min-height: 38px; padding: 0 13px; color: #18181B; }
QLineEdit#global_search:focus { background: #FFFFFF; border: 1px solid #818CF8; }
QLabel#db_badge { background: #ECFDF3; color: #15803D; border: 1px solid #D1FAE5; border-radius: 16px; padding: 7px 11px; font-size: 10px; font-weight: 800; }

QFrame#brand_card { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #FFFFFF,stop:1 #F6F7FF); border: 1px solid #E6E7F2; border-radius: 20px; }
QLabel#logo_mark { min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px; border-radius: 14px; font-size: 18px; font-weight: 900; }
QLabel#brand { font-size: 17px; font-weight: 900; letter-spacing: -.5px; }
QLabel#subbrand { font-size: 10px; font-weight: 800; letter-spacing: 1.4px; color: #62636A; }
QLabel#brand_tag { font-size: 7px; font-weight: 800; letter-spacing: .75px; color: #A1A1AA; }
QLabel#signature { font-size: 8px; color: #059669; letter-spacing: .8px; font-weight: 800; background: transparent; }

QLabel#page_title { font-size: 36px; font-weight: 800; letter-spacing: -1.4px; }
QLabel#hero_title { color: #17171A; font-size: 22px; font-weight: 800; letter-spacing: -.5px; }
QLabel#hero_subtitle { color: #71717A; font-size: 12px; font-weight: 500; }
QFrame#hero_card { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #FFFFFF,stop:1 #F2F3FF); border: 1px solid #E4E7F3; border-radius: 22px; }
QFrame#kpi_card { background: #FFFFFF; border: 1px solid #E8E9EF; border-radius: 18px; }
QFrame#kpi_card:hover { border-color: #D7DBFF; background: #FCFCFF; }
QLabel#kpi_label { color: #8A8B95; font-size: 9px; font-weight: 800; letter-spacing: 1px; }
QLabel#kpi_value { color: #17171A; font-size: 24px; font-weight: 800; letter-spacing: -.6px; }
QFrame#quick_card { background: #FFFFFF; border: 1px solid #E8E9EF; border-radius: 16px; }
QLabel#section_caption { font-size: 10px; background: transparent; color: #858895; }

QFrame#astra_panel { background: #FBFBFE; border-left: 1px solid #E6E7ED; }
QFrame#astra_head_card, QFrame#ai_card, QFrame#ai_composer { background: #FFFFFF; border: 1px solid #E6E7ED; border-radius: 16px; }
QLabel#ai_title { font-size: 18px; font-weight: 900; color: #17171A; letter-spacing: -.4px; }
QLabel#ai_context { color: #8B8D96; font-size: 10px; font-weight: 600; }
QLabel#ai_ready { background: #ECFDF3; color: #15803D; border: 1px solid #D1FAE5; border-radius: 12px; padding: 5px 8px; font-size: 9px; font-weight: 800; }
QLabel#ai_status { background: #F7F7FB; color: #737580; border-radius: 9px; padding: 7px 9px; font-size: 10px; font-weight: 700; }
QComboBox#ai_model_combo { background: #FBFBFD; border: 1px solid #DFE1E8; border-radius: 11px; padding: 0 32px 0 11px; min-height: 40px; font-weight: 650; }
QComboBox#ai_model_combo:focus { background: #FFFFFF; border: 1px solid #818CF8; }
QComboBox#ai_model_combo QAbstractItemView { background: #FFFFFF; border: 1px solid #E4E5EC; border-radius: 12px; padding: 6px; selection-background-color: #EEF2FF; selection-color: #4F46E5; }
QPushButton#ai_chip { background: #F7F7FB; color: #555864; border: 1px solid #E6E7ED; border-radius: 10px; padding: 7px 8px; min-height: 17px; font-size: 10px; font-weight: 700; }
QPushButton#ai_chip:hover { background: #EEF2FF; color: #4F46E5; border-color: #DCE1FF; }
QTextEdit#ai_chat { background: #F6F7FA; border: 1px solid #E5E7EB; border-radius: 15px; padding: 10px; }
QLineEdit#ai_input { background: #FFFFFF; border: 1px solid #DFE1E8; border-radius: 11px; min-height: 42px; padding: 0 12px; }
QLineEdit#ai_input:focus { border: 1px solid #818CF8; }
QPushButton#ai_subtle { background: #F8F8FA; color: #5F6470; border: 1px solid #E4E5EA; border-radius: 9px; padding: 7px 9px; font-size: 10px; font-weight: 700; }
QPushButton#ai_subtle:hover { background: #EEF2FF; color: #4F46E5; }
QPushButton#ai_send { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7C83FF,stop:1 #5B5FEF); color: #FFFFFF; border: none; border-radius: 10px; padding: 8px 14px; font-size: 11px; font-weight: 800; }
QPushButton#ai_send:hover { background: #4F46E5; }

QPushButton#nav { padding: 11px 14px; border-radius: 13px; margin: 2px 5px; }
QTableWidget { border-radius: 17px; }
QHeaderView::section { padding: 13px 14px; }
QGroupBox { border-radius: 18px; padding: 20px; }
/* ── Flat visual finish ─────────────────────────────── */
QWidget {
    outline: none;
}
QAbstractItemView {
    outline: none;
}
QFrame#astra_panel, QFrame#astra_head_card, QFrame#ai_card, QFrame#ai_composer {
    box-shadow: none;
}
QLineEdit#ai_input:focus, QComboBox#ai_model_combo:focus {
    background: #FFFFFF;
}
QLabel#ai_status, QLabel#section_caption {
    border: none;
}

"""


def main() -> int:
    db = Database(ROOT)
    db.migrate()
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    w = Window(BusinessService(db), DocumentEngine(db, ROOT), ROOT)
    w.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
