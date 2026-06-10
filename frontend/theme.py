"""
Centralised design tokens and global stylesheet for Bestie Accounts.

Usage
-----
from frontend.theme import THEME, apply_global_style
apply_global_style(app)          # call once after QApplication()
"""
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QPalette, QColor

# ─────────────────────────────────────────────
#  Colour palette
# ─────────────────────────────────────────────
THEME = {
    # Surfaces
    "bg":           "#F5F7FB",   # window / page background
    "card":         "#FFFFFF",   # card background
    "sidebar":      "#1E293B",   # sidebar background
    "sidebar_dark": "#0F172A",   # logo bar / deeper areas
    "sidebar_hover":"#334155",   # nav item hover
    "sidebar_sel":  "#3B82F6",   # active nav item accent

    # Brand colours
    "primary":      "#3B82F6",   # blue
    "primary_hover": "#60A5FA",
    "primary_active": "#2563EB",
    "primary_dark": "#2563EB",
    "success":      "#16A34A",
    "success_dark": "#15803D",
    "danger":       "#DC2626",
    "danger_dark":  "#B91C1C",
    "warning":      "#F59E0B",
    "info":         "#0891B2",

    # Text
    "text_primary":   "#0F172A",
    "text_secondary": "#64748B",
    "text_muted":     "#94A3B8",
    "text_white":     "#FFFFFF",
    "text_sidebar":   "#CBD5E1",

    # Borders / dividers
    "border":       "#E5E7EB",
    "border_dark":  "#CBD5E1",
    "divider":      "#F1F5F9",

    # Header
    "header_bg":    "#FFFFFF",
    "header_border":"#E5E7EB",

    # Sidebar geometry
    "sidebar_width":         220,
    "sidebar_compact_width": 60,
}

# ─────────────────────────────────────────────
#  Global stylesheet
# ─────────────────────────────────────────────
GLOBAL_QSS = f"""
/* ── Root window & pages ── */
QMainWindow, QWidget#AppRoot {{
    background: {THEME['bg']};
}}

/* ── Generic QWidget page background ── */
QWidget {{
    font-family: 'Segoe UI', 'Inter', 'Roboto', Arial, sans-serif;
    font-size: 13px;
    color: {THEME['text_primary']};
}}

/* ── Scroll areas ── */
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    width: 6px;
    background: transparent;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {THEME['border_dark']};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {THEME['primary']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    height: 6px;
    background: transparent;
}}
QScrollBar::handle:horizontal {{
    background: {THEME['border_dark']};
    border-radius: 3px;
    min-width: 30px;
}}

/* ── QLineEdit / QDateEdit / QDoubleSpinBox ── */
QLineEdit, QDateEdit, QDoubleSpinBox, QSpinBox, QTextEdit {{
    background: {THEME['card']};
    border: 1px solid {THEME['border_dark']};
    border-radius: 7px;
    padding: 6px 10px;
    color: {THEME['text_primary']};
    selection-background-color: {THEME['primary']};
}}
QLineEdit:focus, QDateEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QTextEdit:focus {{
    border: 1.5px solid {THEME['primary']};
}}

/* ══════════════════════════════════════════════════════════════════
   SpinBox  ─  Industrialist ERP pattern
   A solid steel-grey button panel on the right, divided by a sharp
   hairline.  ▲ / ▼ arrows are crisp CSS triangles. Mirrors the look
   of classic accounting / ERP software (Tally, SAP GUI style).
   ══════════════════════════════════════════════════════════════════ */

/* Container — give right side room for the 22-px panel */
QDoubleSpinBox, QSpinBox {{
    padding-right: 24px;
}}

/* ── Up button (top half of the panel) ── */
QDoubleSpinBox::up-button, QSpinBox::up-button {{
    subcontrol-origin:   border;
    subcontrol-position: top right;
    width:  22px;
    height: 13px;
    background: #E8ECF0;
    border-left:         1px solid {THEME['border_dark']};
    border-bottom:       1px solid {THEME['border_dark']};
    border-top-right-radius: 6px;
    border-top-left-radius:  0px;
}}
QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover {{
    background: #D0D8E4;
}}
QDoubleSpinBox::up-button:pressed, QSpinBox::up-button:pressed {{
    background: #B8C4D4;
}}
QDoubleSpinBox::up-button:disabled, QSpinBox::up-button:disabled {{
    background: #F2F4F6;
}}

/* ── Down button (bottom half of the panel) ── */
QDoubleSpinBox::down-button, QSpinBox::down-button {{
    subcontrol-origin:   border;
    subcontrol-position: bottom right;
    width:  22px;
    height: 13px;
    background: #E8ECF0;
    border-left:            1px solid {THEME['border_dark']};
    border-top:             1px solid {THEME['border_dark']};
    border-bottom-right-radius: 6px;
    border-bottom-left-radius:  0px;
}}
QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
    background: #D0D8E4;
}}
QDoubleSpinBox::down-button:pressed, QSpinBox::down-button:pressed {{
    background: #B8C4D4;
}}
QDoubleSpinBox::down-button:disabled, QSpinBox::down-button:disabled {{
    background: #F2F4F6;
}}

/* ── Up arrow ── */
QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
    image: url("frontend/assets/icons/chevron-up.svg");
    width:  12px;
    height: 12px;
}}
QDoubleSpinBox::up-arrow:disabled, QSpinBox::up-arrow:disabled {{
    image: url("frontend/assets/icons/chevron-up.svg");
    opacity: 0.3;
}}

/* ── Down arrow ── */
QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
    image: url("frontend/assets/icons/chevron-down.svg");
    width:  12px;
    height: 12px;
}}
QDoubleSpinBox::down-arrow:disabled, QSpinBox::down-arrow:disabled {{
    image: url("frontend/assets/icons/chevron-down.svg");
    opacity: 0.3;
}}

/* ── QComboBox ── */
QComboBox {{
    background: {THEME['card']};
    border: 1px solid {THEME['border_dark']};
    border-radius: 7px;
    padding: 6px 10px;
    color: {THEME['text_primary']};
}}
QComboBox:focus {{
    border: 1.5px solid {THEME['primary']};
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox QAbstractItemView {{
    background: {THEME['card']};
    border: 1px solid {THEME['border']};
    border-radius: 7px;
    selection-background-color: {THEME['primary']};
    selection-color: #fff;
    padding: 4px;
}}

/* ── QPushButton base ── */
QPushButton {{
    border-radius: 7px;
    padding: 7px 18px;
    font-weight: 600;
    font-size: 13px;
    border: none;
    background: {THEME['primary']};
    color: {THEME['text_white']};
}}
QPushButton:hover  {{ background: {THEME['primary_dark']}; }}
QPushButton:pressed{{ background: #1D4ED8; }}
QPushButton:disabled {{ background: {THEME['border']}; color: {THEME['text_muted']}; }}

/* ── QTableWidget ── */
QTableWidget {{
    background: {THEME['card']};
    border: 1px solid {THEME['border']};
    gridline-color: {THEME['divider']};
    alternate-background-color: {THEME['bg']};
}}
QTableWidget::item {{
    padding: 8px 12px;
    color: {THEME['text_primary']};
}}
QTableWidget::item:selected {{
    background: #DBEAFE;
    color: {THEME['primary_dark']};
}}
QTableWidget::item:hover:!selected {{
    background: {THEME['divider']};
}}
QHeaderView::section {{
    background: {THEME['bg']};
    color: {THEME['text_secondary']};
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    padding: 8px 12px;
    border: none;
    border-bottom: 2px solid {THEME['border']};
}}

/* ── Sorting arrows ── */
QHeaderView::up-arrow {{
    image: url("frontend/assets/icons/chevron-up.svg");
    width: 10px; height: 10px; padding-right: 5px;
}}
QHeaderView::down-arrow {{
    image: url("frontend/assets/icons/chevron-down.svg");
    width: 10px; height: 10px; padding-right: 5px;
}}

/* ── Table Cell Editors (Full height/width) ── */
QTableWidget QLineEdit, 
QTableWidget QDoubleSpinBox, 
QTableWidget QSpinBox, 
QTableWidget QComboBox {{
    border: none;
    border-radius: 0;
    background: #FFFFFF;
    padding: 0 8px;
    margin: 0;
    height: 100%;
}}
QTableWidget QLineEdit:focus, 
QTableWidget QDoubleSpinBox:focus, 
QTableWidget QSpinBox:focus {{
    background: #EBF2FF;
    border: 1px solid {THEME['primary']};
}}

/* ── QDialog ── */
QDialog {{
    background: {THEME['bg']};
}}
QDialog QFormLayout QLabel {{
    color: {THEME['text_secondary']};
    font-size: 12px;
    font-weight: 500;
}}

/* ── QMessageBox ── */
QMessageBox {{
    background: {THEME['card']};
}}

/* ── QStatusBar ── */
QStatusBar {{
    background: {THEME['card']};
    border-top: 1px solid {THEME['border']};
    color: {THEME['text_secondary']};
    font-size: 12px;
}}

/* ── QToolTip ── */
QToolTip {{
    background: {THEME['sidebar']};
    color: {THEME['text_white']};
    border: none;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
}}

/* ── Separator ── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {THEME['border']};
    max-height: 1px;
}}
"""


def apply_global_style(app: QApplication) -> None:
    """Apply the global stylesheet + font + palette to the entire application."""
    # Font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Light palette (overrides Fusion defaults)
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(THEME["bg"]))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(THEME["text_primary"]))
    pal.setColor(QPalette.ColorRole.Base,            QColor(THEME["card"]))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(THEME["bg"]))
    pal.setColor(QPalette.ColorRole.Text,            QColor(THEME["text_primary"]))
    pal.setColor(QPalette.ColorRole.Button,          QColor(THEME["primary"]))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(THEME["text_white"]))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(THEME["primary"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(THEME["text_white"]))
    pal.setColor(QPalette.ColorRole.Link,            QColor(THEME["primary"]))
    app.setPalette(pal)

    # Resolve QSS resource paths dynamically in PyInstaller package
    import sys
    import os
    style_qss = GLOBAL_QSS
    base_path = getattr(sys, '_MEIPASS', None)
    if base_path:
        # Convert backslashes to forward slashes for QSS urls on Windows
        resolved_prefix = os.path.join(base_path, "frontend/assets").replace('\\', '/')
        style_qss = style_qss.replace('url("frontend/assets', f'url("{resolved_prefix}')

    app.setStyleSheet(style_qss)

