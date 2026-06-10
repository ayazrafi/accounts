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
import frontend.session as session


# ────────────────────────────────────────────────────
#  Nav item definition
# ────────────────────────────────────────────────────
NAV_ITEMS: list[dict] = [
    {"icon": "frontend/assets/icons/home.svg", "label": "Dashboard", "hint": ""},
    {"icon": "frontend/assets/icons/company.svg", "label": "Companies", "hint": "Alt+C opens New"},
    {"icon": "frontend/assets/icons/book.svg", "label": "Ledgers", "hint": ""},
    {
        "icon": "frontend/assets/icons/edit-file.svg", 
        "label": "Voucher Entry", 
        "hint": "Alt+V",
        "sub_items": [
            "Contra", "Journal", "Payment", "Receipt", "Sales", "Purchase", "Debit Note", "Credit Note"
        ]
    },
    {"icon": "frontend/assets/icons/bar-chart.svg", "label": "Trial Balance", "hint": ""},
    {"icon": "frontend/assets/icons/pie-chart.svg", "label": "Profit & Loss", "hint": ""},
    {"icon": "frontend/assets/icons/file-text.svg", "label": "Ledger Statement", "hint": ""},
    {"icon": "frontend/assets/icons/package.svg", "label": "Inventory", "hint": ""},
    {"icon": "frontend/assets/icons/layers.svg", "label": "Balance Sheet", "hint": ""},
    {
        "icon": "frontend/assets/icons/file-invoice.svg", 
        "label": "GSTR Report", 
        "hint": "",
        "sub_items": [
            "GSTR-1", "GSTR-3B", "GST Summary"
        ]
    },
    {"icon": "frontend/assets/icons/settings.svg", "label": "Settings", "hint": ""},
    {"icon": "frontend/assets/icons/user.svg", "label": "User Management", "hint": ""},
]



# ────────────────────────────────────────────────────
#  Single nav button
# ────────────────────────────────────────────────────
class _NavButton(QPushButton):
    """A sidebar navigation button that supports expanded/compact states."""

    def __init__(self, icon_path: str, label: str, tooltip: str, index: int, has_sub: bool = False):
        super().__init__()
        self._icon_path = icon_path
        self._label = label
        self._index = index
        self._expanded = True
        self._has_sub = has_sub
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
            text = f"  {self._label}"
            if self._has_sub:
                text += "  ▾"
            self.setText(text)
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
    import_requested = Signal()
    import_purchase_requested = Signal()
    import_payment_requested = Signal()
    company_toggle_requested = Signal()

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
        self._company_chip = QPushButton("No company selected")
        self._company_chip.setObjectName("CompanyChip")
        self._company_chip.setFixedHeight(34)
        self._company_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self._company_chip.clicked.connect(self._on_company_chip_clicked)
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

        for idx, item in enumerate(NAV_ITEMS):
            icon, label, hint = item["icon"], item["label"], item.get("hint", "")
            has_sub = "sub_items" in item
            btn = _NavButton(icon, label, hint, idx, has_sub=has_sub)
            
            # RBAC: Hide restricted items
            if label in ["Companies", "User Management"] and not session.is_super_admin:
                btn.setVisible(False)
            else:
                nav_layout.addWidget(btn)
                
            self._nav_buttons.append(btn)

            # Handle sub-items (e.g. Voucher Entry)
            if has_sub:
                btn.clicked.connect(lambda checked=False, i=idx: self._on_nav_click_with_sub(i))
                sub_container = QWidget()
                sub_container.setObjectName("SubContainer")
                sub_container.setVisible(False)
                sub_lay = QVBoxLayout(sub_container)
                sub_lay.setContentsMargins(42, 0, 8, 4)
                sub_lay.setSpacing(1)
                
                btn._sub_buttons_map = {}
                for sub_label in item["sub_items"]:
                    sub_btn = QPushButton(f"{sub_label}")
                    sub_btn.setObjectName("subNavItem")
                    sub_btn.setFixedHeight(30)
                    sub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    sub_btn.setStyleSheet(self._sub_nav_style())
                    sub_btn.clicked.connect(lambda checked=False, l=sub_label: self._on_sub_nav_click(l))
                    sub_lay.addWidget(sub_btn)
                    btn._sub_buttons_map[sub_label] = sub_btn
                
                nav_layout.addWidget(sub_container)
                btn._sub_container = sub_container
            else:
                btn.clicked.connect(lambda checked=False, i=idx: self._on_nav_click(i))

        nav_layout.addSpacing(10)
        import_btn = _NavButton("frontend/assets/icons/upload.svg", "Import Sales", "Ctrl+Alt+I", -1)
        import_btn.clicked.connect(self.import_requested.emit)
        nav_layout.addWidget(import_btn)
        self._nav_buttons.append(import_btn)
        self._import_sales_btn = import_btn

        import_p_btn = _NavButton("frontend/assets/icons/download.svg", "Import Purchase", "Ctrl+Alt+P", -1)
        import_p_btn.clicked.connect(self.import_purchase_requested.emit)
        nav_layout.addWidget(import_p_btn)
        self._nav_buttons.append(import_p_btn)
        self._import_purchase_btn = import_p_btn

        import_pr_btn = _NavButton("frontend/assets/icons/refresh-cw.svg", "Import Pay/Rec", "Ctrl+Alt+R", -1)
        import_pr_btn.clicked.connect(self.import_payment_requested.emit)
        nav_layout.addWidget(import_pr_btn)
        self._nav_buttons.append(import_pr_btn)
        self._import_payment_btn = import_pr_btn

        nav_layout.addStretch()
        scroll.setWidget(nav_container)
        layout.addWidget(scroll, 1)

        # Select first item by default
        if self._nav_buttons:
            self._nav_buttons[0].setChecked(True)
        self._current_index = 0

    # ── public API ────────────────────────────────────────────────────
    def clear_import_selection(self):
        """Uncheck all import shortcut buttons (called after dialog closes)."""
        for btn in (self._import_sales_btn, self._import_purchase_btn, self._import_payment_btn):
            btn.setChecked(False)

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
        
        # Hide sub-containers if collapsed
        if not self._expanded:
            for btn in self._nav_buttons:
                if hasattr(btn, "_sub_container"):
                    btn._sub_container.setVisible(False)

    def set_active_company(self, name: str):
        if name:
            display = name if len(name) <= 24 else name[:22] + "…"
            self._company_chip.setText(f"   {display}")
        else:
            self._company_chip.setText("   No company selected")

    def refresh_permissions(self):
        """Update navigation items and sub-items visibility based on current permissions."""
        for btn in self._nav_buttons:
            if btn._index == -1:
                continue
            label = btn._label
            if label in ["Companies", "User Management"]:
                btn.setVisible(session.is_super_admin)
            elif label == "Settings":
                btn.setVisible(session.is_super_admin)
            elif label == "Ledgers" or label == "Ledger Statement":
                btn.setVisible(session.has_permission("ledger", "view"))
            elif label == "Inventory":
                btn.setVisible(session.has_permission("item", "view"))
            elif label == "Dashboard":
                btn.setVisible(True)
            elif label == "Trial Balance" or label == "Profit & Loss" or label == "Balance Sheet":
                btn.setVisible(session.has_permission("ledger", "view"))
            elif label == "GSTR Report":
                has_sales_view = session.has_permission("sales", "view")
                has_purch_view = session.has_permission("purchase", "view")
                btn.setVisible(has_sales_view or has_purch_view)
            elif label == "Voucher Entry":
                sub_visible = False
                if hasattr(btn, "_sub_buttons_map"):
                    for vtype, sub_btn in btn._sub_buttons_map.items():
                        visible = session.has_permission(vtype, "view")
                        sub_btn.setVisible(visible)
                        if visible:
                            sub_visible = True
                btn.setVisible(sub_visible)
                
        # Update dynamic imports visibility
        self._import_sales_btn.setVisible(session.has_permission("sales", "edit"))
        self._import_purchase_btn.setVisible(session.has_permission("purchase", "edit"))
        
        can_pay = session.has_permission("payment", "edit")
        can_rec = session.has_permission("receipt", "edit")
        self._import_payment_btn.setVisible(can_pay or can_rec)

    def _on_company_chip_clicked(self):
        self.company_toggle_requested.emit()

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
        
        # Hide other sub-containers, and ensure active one is visible
        for i, btn in enumerate(self._nav_buttons):
            if i == index:
                if hasattr(btn, "_sub_container"):
                    btn._sub_container.setVisible(True)
            elif hasattr(btn, "_sub_container"):
                btn._sub_container.setVisible(False)

    def _on_nav_click_with_sub(self, index: int):
        # If expanding a sub-menu, make sure sidebar is expanded
        if not self._expanded:
            self.toggle()
        
        self._on_nav_click(index)

    def _on_sub_nav_click(self, label: str):
        if label in ["GSTR-1", "GSTR-3B", "GST Summary"]:
            # Find GSTR Report index (which is 9)
            self.nav_item_changed.emit(9)
            window = self.window()
            if hasattr(window, "page_list"):
                gstr_page = window.page_list[9]
                from frontend.pages.gstr_report import GSTRReportPage
                if isinstance(gstr_page, GSTRReportPage):
                    gstr_page.switch_tab(label)
        else:
            # Find "Voucher Entry" index (which is 3)
            self.nav_item_changed.emit(3)
            # Access MainWindow to call _open_voucher
            window = self.window()
            if hasattr(window, "page_list"):
                voucher_page = window.page_list[3]
                from frontend.pages.voucher import VoucherPage
                if isinstance(voucher_page, VoucherPage):
                    voucher_page._open_voucher(label)

    def _sub_nav_style(self) -> str:
        return f"""
            QPushButton#subNavItem {{
                background: transparent;
                color: #94A3B8;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                text-align: left;
                padding-left: 12px;
            }}
            QPushButton#subNavItem:hover {{
                color: #FFFFFF;
                background: rgba(255, 255, 255, 0.05);
            }}
            QPushButton#subNavItem:pressed {{
                background: rgba(255, 255, 255, 0.1);
            }}
        """

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
            QPushButton#CompanyChip {{
                font-size: 11px;
                color: #94A3B8;
                background: {THEME['sidebar_dark']};
                border: none;
                text-align: left;
                padding-left: 12px;
                border-bottom: 1px solid #1E293B;
            }}
            QPushButton#CompanyChip:hover {{
                color: #FFFFFF;
                background: {THEME['sidebar_hover']};
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
