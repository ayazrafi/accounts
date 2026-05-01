"""
Collapsible animated sidebar navigation component.

Expanded width : THEME['sidebar_width']       (220 px)
Compact width  : THEME['sidebar_compact_width'] (60 px)

The sidebar emits  nav_item_changed(int)  signal when the user selects a page.
"""
from __future__ import annotations

from PySide6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, Signal, QSize, QTimer
)
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QSizePolicy, QToolTip
)
from PySide6.QtGui import QFont, QCursor, QIcon

from frontend.theme import THEME
from frontend.utils import get_icon


# ────────────────────────────────────────────────────
#  Nav item definition
# ────────────────────────────────────────────────────
NAV_ITEMS: list[tuple[str, str, str]] = [
    # (icon_path, label, shortcut hint)
    ("frontend/assets/icons/home.svg", "Dashboard",        ""),
    ("frontend/assets/icons/company.svg", "Companies",        "Alt+C opens New"),
    ("frontend/assets/icons/book.svg", "Ledgers",          ""),
    ("frontend/assets/icons/edit-file.svg", "Voucher Entry",    "Alt+V"),
    ("frontend/assets/icons/bar-chart.svg", "Trial Balance",   ""),
    ("frontend/assets/icons/pie-chart.svg", "Profit & Loss",   ""),
    ("frontend/assets/icons/file-text.svg", "Ledger Statement", ""),
    ("frontend/assets/icons/package.svg", "Inventory",        ""),
    ("frontend/assets/icons/layers.svg", "Balance Sheet",   ""),
]


# ────────────────────────────────────────────────────
#  Single nav button
# ────────────────────────────────────────────────────
class _NavButton(QPushButton):
    """A sidebar navigation button that supports expanded/compact states."""

    def __init__(self, icon_path: str, label: str, tooltip: str, index: int):
        super().__init__()
        self._icon_path = icon_path
        self._label = label
        self._index = index
        self._expanded = True
        self.setCheckable(True)
        self.setObjectName("navBtn")
        self.setFixedHeight(46)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIcon(get_icon(icon_path, "#ffffff"))
        self.setIconSize(QSize(20, 20))
        if tooltip:
            self.setToolTip(f"{label}  —  {tooltip}")
        else:
            self.setToolTip(label)
        self._refresh_text()

    def _refresh_text(self):
        if self._expanded:
            self.setText(f"  {self._label}")
            self.setStyleSheet(_nav_btn_style(expanded=True))
        else:
            self.setText("")
            self.setStyleSheet(_nav_btn_style(expanded=False))

    def set_expanded(self, expanded: bool):
        self._expanded = expanded
        self._refresh_text()


def _nav_btn_style(*, expanded: bool) -> str:
    align = "text-align: left; padding-left: 16px;" if expanded else "text-align: center; padding: 0;"
    return f"""
        QPushButton#navBtn {{
            background: transparent;
            color: {THEME['text_sidebar']};
            border: none;
            border-left: 3px solid transparent;
            border-radius: 0;
            font-size: 13px;
            {align}
        }}
        QPushButton#navBtn:hover {{
            background: {THEME['sidebar_hover']};
            color: #FFFFFF;
        }}
        QPushButton#navBtn:checked {{
            background: rgba(59,130,246,0.18);
            color: #FFFFFF;
            border-left: 3px solid {THEME['sidebar_sel']};
            font-weight: 600;
        }}
    """


# ────────────────────────────────────────────────────
#  Sidebar widget
# ────────────────────────────────────────────────────
class Sidebar(QFrame):
    """Animated collapsible sidebar.  Emits nav_item_changed(page_index)."""

    nav_item_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self._expanded = True
        self._expanded_w  = THEME["sidebar_width"]
        self._compact_w   = THEME["sidebar_compact_width"]
        self._anim_dur    = 220          # ms
        self._nav_buttons: list[_NavButton] = []

        self.setFixedWidth(self._expanded_w)
        self._build()
        self._apply_base_style()

    # ── construction ──────────────────────────────────────────────────
    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ─── Logo bar ─────────────────────────────────────────────────
        logo_bar = QFrame()
        logo_bar.setObjectName("SidebarLogoBar")
        logo_bar.setFixedHeight(58)
        logo_h = QHBoxLayout(logo_bar)
        logo_h.setContentsMargins(12, 0, 12, 0)
        logo_h.setSpacing(10)

        self._hamburger = QPushButton()
        self._hamburger.setIcon(get_icon("frontend/assets/icons/menu.svg", "#ffffff"))
        self._hamburger.setIconSize(QSize(20, 20))
        self._hamburger.setObjectName("HamburgerBtn")
        self._hamburger.setFixedSize(34, 34)
        self._hamburger.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hamburger.setToolTip("Toggle sidebar  (Ctrl+\\)")
        self._hamburger.clicked.connect(self.toggle)

        self._logo_lbl = QLabel("Bestie Accounts")
        self._logo_lbl.setObjectName("LogoLabel")

        logo_h.addWidget(self._hamburger)
        logo_h.addWidget(self._logo_lbl)
        logo_h.addStretch()
        layout.addWidget(logo_bar)

        # ─── Company chip ──────────────────────────────────────────────
        self._company_chip = QLabel("")
        self._company_chip.setObjectName("CompanyChip")
        self._company_chip.setFixedHeight(34)
        self._company_chip.setWordWrap(False)
        layout.addWidget(self._company_chip)

        # ─── Nav items (scrollable) ────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setObjectName("NavScroll")
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        nav_container = QWidget()
        nav_container.setObjectName("NavContainer")
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 8, 0, 8)
        nav_layout.setSpacing(2)

        for idx, (icon, label, hint) in enumerate(NAV_ITEMS):
            btn = _NavButton(icon, label, hint, idx)
            btn.clicked.connect(lambda checked=False, i=idx: self._on_nav_click(i))
            nav_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        nav_layout.addStretch()
        scroll.setWidget(nav_container)
        layout.addWidget(scroll, 1)

        # Select first item by default
        if self._nav_buttons:
            self._nav_buttons[0].setChecked(True)
        self._current_index = 0

    # ── public API ────────────────────────────────────────────────────
    def toggle(self):
        """Animate between expanded and compact mode."""
        target_w = self._compact_w if self._expanded else self._expanded_w
        self._expanded = not self._expanded

        for attr in ("maximumWidth", "minimumWidth"):
            anim = QPropertyAnimation(self, attr.encode())
            anim.setDuration(self._anim_dur)
            anim.setStartValue(self.width())
            anim.setEndValue(target_w)
            anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            anim.start()
            # Keep reference so garbage collector doesn't kill it
            setattr(self, f"_anim_{attr}", anim)

        # Update button appearance after animation starts
        QTimer.singleShot(10, self._refresh_nav_state)

        # Show/hide text labels
        self._logo_lbl.setVisible(self._expanded)
        self._company_chip.setVisible(self._expanded)

    def set_active_company(self, name: str):
        if name:
            display = name if len(name) <= 24 else name[:22] + "…"
            self._company_chip.setText(f"   {display}")
        else:
            self._company_chip.setText("   No company selected")

    def select_page(self, index: int):
        """Programmatically select a nav item (0-based)."""
        if 0 <= index < len(self._nav_buttons):
            self._nav_buttons[self._current_index].setChecked(False)
            self._nav_buttons[index].setChecked(True)
            self._current_index = index

    # ── private helpers ───────────────────────────────────────────────
    def _on_nav_click(self, index: int):
        self._nav_buttons[self._current_index].setChecked(False)
        self._nav_buttons[index].setChecked(True)
        self._current_index = index
        self.nav_item_changed.emit(index)

    def _refresh_nav_state(self):
        for btn in self._nav_buttons:
            btn.set_expanded(self._expanded)

    def _apply_base_style(self):
        self.setStyleSheet(f"""
            QFrame#Sidebar {{
                background: {THEME['sidebar']};
                border-right: 1px solid #0F172A;
            }}
            QFrame#SidebarLogoBar {{
                background: {THEME['sidebar_dark']};
                border-bottom: 1px solid #1E3A5F;
            }}
            QLabel#LogoLabel {{
                font-size: 15px;
                font-weight: 700;
                color: #FFFFFF;
                letter-spacing: 0.3px;
            }}
            QPushButton#HamburgerBtn {{
                background: transparent;
                color: #94A3B8;
                font-size: 18px;
                border: none;
                border-radius: 6px;
            }}
            QPushButton#HamburgerBtn:hover {{
                background: #1E3A5F;
                color: #FFFFFF;
            }}
            QLabel#CompanyChip {{
                font-size: 11px;
                color: #94A3B8;
                background: {THEME['sidebar_dark']};
                padding-left: 2px;
                border-bottom: 1px solid #1E293B;
            }}
            QWidget#NavContainer {{
                background: {THEME['sidebar']};
            }}
            QScrollArea#NavScroll {{
                background: {THEME['sidebar']};
                border: none;
            }}
            QScrollBar:vertical {{
                width: 4px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: #334155;
                border-radius: 2px;
            }}
        """)
