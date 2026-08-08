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
    {
        "icon": "frontend/assets/icons/home.svg",
        "label": "Dashboard",
        "hint": "",
        "page_index": 0
    },
    {
        "icon": "frontend/assets/icons/company.svg",
        "label": "Companies",
        "hint": "Alt+C opens New",
        "page_index": 1
    },
    {
        "icon": "frontend/assets/icons/book.svg",
        "label": "Masters",
        "hint": "",
        "sub_items": [
            {"label": "Ledgers", "page_index": 2},
            {"label": "Inventory", "page_index": 7},
            {"label": "Transporters", "page_index": 13}
        ]
    },
    {
        "icon": "frontend/assets/icons/edit-file.svg",
        "label": "Voucher Entry",
        "hint": "Alt+V",
        "page_index": 3,
        "sub_items": [
            {"label": "Contra", "action": "voucher"},
            {"label": "Journal", "action": "voucher"},
            {"label": "Payment", "action": "voucher"},
            {"label": "Receipt", "action": "voucher"},
            {"label": "Sales", "action": "voucher"},
            {"label": "Purchase", "action": "voucher"},
            {"label": "Debit Note", "action": "voucher"},
            {"label": "Credit Note", "action": "voucher"}
        ]
    },
    {
        "icon": "frontend/assets/icons/bar-chart.svg",
        "label": "Reports",
        "hint": "",
        "sub_items": [
            {"label": "Trial Balance", "page_index": 4},
            {"label": "Profit & Loss", "page_index": 5},
            {"label": "Ledger Statement", "page_index": 6},
            {"label": "Balance Sheet", "page_index": 8},
            {"label": "Stock Group Summary", "page_index": 14},
            {"label": "Stock Category Summary", "page_index": 15},
            {"label": "Stock Monthly Summary", "page_index": 16},
            {"label": "Stock Vouchers", "page_index": 17},
            {"label": "Stock Query", "page_index": 18}
        ]
    },
    {
        "icon": "frontend/assets/icons/file-invoice.svg",
        "label": "GSTR Report",
        "hint": "",
        "page_index": 9,
        "sub_items": [
            {"label": "GSTR-1", "action": "gstr"},
            {"label": "GSTR-3B", "action": "gstr"},
            {"label": "GST Summary", "action": "gstr"}
        ]
    },
    {
        "icon": "frontend/assets/icons/settings.svg",
        "label": "Settings",
        "hint": "",
        "sub_items": [
            {"label": "Backup", "page_index": 10},
            {"label": "User Management", "page_index": 11},
            {"label": "Invoice Signature", "page_index": 12},
            {"label": "Import Sales", "action": "import_sales"},
            {"label": "Import Purchase", "action": "import_purchase"},
            {"label": "Import Pay/Rec", "action": "import_payment"}
        ]
    }
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
        self._import_sales_btn = None
        self._import_purchase_btn = None
        self._import_payment_btn = None
        self._page_to_nav_item = {}

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

        self._page_to_nav_item = {}

        for idx, item in enumerate(NAV_ITEMS):
            icon, label, hint = item["icon"], item["label"], item.get("hint", "")
            has_sub = "sub_items" in item
            btn = _NavButton(icon, label, hint, idx, has_sub=has_sub)
            
            # Save page index mapping for top level items
            page_idx = item.get("page_index", -1)
            btn._page_index = page_idx
            
            if page_idx >= 0 and not has_sub:
                self._page_to_nav_item[page_idx] = {"btn": btn}
            
            nav_layout.addWidget(btn)
            self._nav_buttons.append(btn)

            # Handle sub-items
            if has_sub:
                if page_idx >= 0:
                    self._page_to_nav_item[page_idx] = {"btn": btn}
                    
                btn.clicked.connect(lambda checked=False, i=idx: self._on_nav_click(i))
                
                sub_container = QWidget()
                sub_container.setObjectName("SubContainer")
                sub_container.setVisible(False)
                sub_lay = QVBoxLayout(sub_container)
                sub_lay.setContentsMargins(42, 0, 8, 4)
                sub_lay.setSpacing(1)
                
                btn._sub_buttons_map = {}
                for sub_item in item["sub_items"]:
                    sub_label = sub_item["label"]
                    sub_btn = QPushButton(f"{sub_label}")
                    sub_btn.setObjectName("subNavItem")
                    sub_btn.setFixedHeight(30)
                    sub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    sub_btn.setStyleSheet(self._sub_nav_style())
                    
                    is_nav_action = "page_index" in sub_item or sub_item.get("action") in ["voucher", "gstr"]
                    if is_nav_action:
                        sub_btn.setCheckable(True)
                    
                    sub_btn.clicked.connect(lambda checked=False, s=sub_item: self._on_sub_nav_click(s))
                    sub_lay.addWidget(sub_btn)
                    btn._sub_buttons_map[sub_label] = sub_btn
                    
                    sub_page_idx = sub_item.get("page_index", -1)
                    if sub_page_idx >= 0:
                        self._page_to_nav_item[sub_page_idx] = {"parent": btn, "sub_btn": sub_btn}
                        
                    action = sub_item.get("action")
                    if action == "import_sales":
                        self._import_sales_btn = sub_btn
                    elif action == "import_purchase":
                        self._import_purchase_btn = sub_btn
                    elif action == "import_payment":
                        self._import_payment_btn = sub_btn
                
                nav_layout.addWidget(sub_container)
                btn._sub_container = sub_container
            else:
                btn.clicked.connect(lambda checked=False, i=idx: self._on_nav_click(i))

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
            if btn is not None:
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
            label = btn._label
            
            if label == "Dashboard":
                btn.setVisible(True)
                
            elif label == "Companies":
                btn.setVisible(session.is_super_admin)
                
            elif label == "Masters":
                has_visible_child = False
                if hasattr(btn, "_sub_buttons_map"):
                    # Ledgers
                    ledgers_visible = session.has_permission("ledger", "view")
                    btn._sub_buttons_map["Ledgers"].setVisible(ledgers_visible)
                    if ledgers_visible:
                        has_visible_child = True
                        
                    # Inventory
                    inventory_visible = session.has_permission("item", "view")
                    btn._sub_buttons_map["Inventory"].setVisible(inventory_visible)
                    if inventory_visible:
                        has_visible_child = True
                        
                    # Transporters
                    transporters_visible = session.has_permission("ledger", "view")
                    btn._sub_buttons_map["Transporters"].setVisible(transporters_visible)
                    if transporters_visible:
                        has_visible_child = True
                        
                btn.setVisible(has_visible_child)
                
            elif label == "Voucher Entry":
                has_visible_child = False
                if hasattr(btn, "_sub_buttons_map"):
                    for vtype, sub_btn in btn._sub_buttons_map.items():
                        visible = session.has_permission(vtype, "view")
                        sub_btn.setVisible(visible)
                        if visible:
                            has_visible_child = True
                btn.setVisible(has_visible_child)
                
            elif label == "Reports":
                has_visible_child = False
                reports_visible = session.has_permission("ledger", "view")
                if hasattr(btn, "_sub_buttons_map"):
                    for rep_name, sub_btn in btn._sub_buttons_map.items():
                        sub_btn.setVisible(reports_visible)
                        if reports_visible:
                            has_visible_child = True
                btn.setVisible(has_visible_child)
                
            elif label == "GSTR Report":
                has_sales_view = session.has_permission("sales", "view")
                has_purch_view = session.has_permission("purchase", "view")
                visible = has_sales_view or has_purch_view
                btn.setVisible(visible)
                if hasattr(btn, "_sub_buttons_map"):
                    for sub_btn in btn._sub_buttons_map.values():
                        sub_btn.setVisible(visible)
                        
            elif label == "Settings":
                has_visible_child = False
                if hasattr(btn, "_sub_buttons_map"):
                    # Backup
                    backup_visible = session.is_super_admin
                    btn._sub_buttons_map["Backup"].setVisible(backup_visible)
                    if backup_visible:
                        has_visible_child = True
                        
                    # User Management
                    um_visible = session.is_super_admin
                    btn._sub_buttons_map["User Management"].setVisible(um_visible)
                    if um_visible:
                        has_visible_child = True
                        
                    # Invoice Signature
                    is_visible = session.has_permission("settings", "view")
                    btn._sub_buttons_map["Invoice Signature"].setVisible(is_visible)
                    if is_visible:
                        has_visible_child = True
                        
                    # Import Sales
                    import_sales_visible = session.has_permission("sales", "edit")
                    btn._sub_buttons_map["Import Sales"].setVisible(import_sales_visible)
                    if import_sales_visible:
                        has_visible_child = True
                        
                    # Import Purchase
                    import_purchase_visible = session.has_permission("purchase", "edit")
                    btn._sub_buttons_map["Import Purchase"].setVisible(import_purchase_visible)
                    if import_purchase_visible:
                        has_visible_child = True
                        
                    # Import Pay/Rec
                    can_pay = session.has_permission("payment", "edit")
                    can_rec = session.has_permission("receipt", "edit")
                    import_payment_visible = can_pay or can_rec
                    btn._sub_buttons_map["Import Pay/Rec"].setVisible(import_payment_visible)
                    if import_payment_visible:
                        has_visible_child = True
                        
                btn.setVisible(has_visible_child)

    def _on_company_chip_clicked(self):
        self.company_toggle_requested.emit()

    def select_page(self, index: int):
        """Programmatically select a nav item (0-based page index)."""
        # Uncheck all top-level buttons and sub buttons
        for btn in self._nav_buttons:
            btn.setChecked(False)
            if hasattr(btn, "_sub_buttons_map"):
                for sub_btn in btn._sub_buttons_map.values():
                    sub_btn.setChecked(False)

        if index in self._page_to_nav_item:
            nav_info = self._page_to_nav_item[index]
            if "btn" in nav_info:
                # Top level item
                btn = nav_info["btn"]
                btn.setChecked(True)
                if hasattr(btn, "_sub_container"):
                    btn._sub_container.setVisible(True)
                # Hide other sub containers
                for other_btn in self._nav_buttons:
                    if other_btn != btn and hasattr(other_btn, "_sub_container"):
                        other_btn._sub_container.setVisible(False)
            else:
                # Sub item
                parent = nav_info["parent"]
                sub_btn = nav_info["sub_btn"]
                parent.setChecked(True)
                sub_btn.setChecked(True)
                if hasattr(parent, "_sub_container"):
                    parent._sub_container.setVisible(True)
                # Hide other sub containers
                for other_btn in self._nav_buttons:
                    if other_btn != parent and hasattr(other_btn, "_sub_container"):
                        other_btn._sub_container.setVisible(False)
        self._current_index = index

    def select_page_by_action(self, parent_label: str, sub_label: str):
        # Uncheck all
        for btn in self._nav_buttons:
            btn.setChecked(False)
            if hasattr(btn, "_sub_buttons_map"):
                for sub_btn in btn._sub_buttons_map.values():
                    sub_btn.setChecked(False)
        # Check parent and specific sub item
        for btn in self._nav_buttons:
            if btn._label == parent_label:
                btn.setChecked(True)
                if hasattr(btn, "_sub_buttons_map") and sub_label in btn._sub_buttons_map:
                    sub_btn = btn._sub_buttons_map[sub_label]
                    sub_btn.setChecked(True)
                if hasattr(btn, "_sub_container"):
                    btn._sub_container.setVisible(True)
            elif hasattr(btn, "_sub_container"):
                btn._sub_container.setVisible(False)

    # ── private helpers ───────────────────────────────────────────────
    def _on_nav_click(self, index: int):
        btn = self._nav_buttons[index]
        page_idx = getattr(btn, "_page_index", -1)
        
        if page_idx >= 0:
            self.nav_item_changed.emit(page_idx)
            self.select_page(page_idx)
        else:
            # Accordion menu with no direct page mapping (e.g. Masters, Reports, Settings)
            if hasattr(btn, "_sub_container"):
                if not self._expanded:
                    self.toggle()
                visible = btn._sub_container.isVisible()
                btn._sub_container.setVisible(not visible)
            # Restore check state of category header button to match active page
            active_info = self._page_to_nav_item.get(self._current_index, {})
            should_be_checked = (active_info.get("parent") == btn or active_info.get("btn") == btn)
            btn.setChecked(should_be_checked)

    def _on_sub_nav_click(self, sub_item: dict):
        label = sub_item["label"]
        action = sub_item.get("action")
        page_idx = sub_item.get("page_index", -1)
        
        if page_idx >= 0:
            self.nav_item_changed.emit(page_idx)
            self.select_page(page_idx)
        elif action == "voucher":
            self.nav_item_changed.emit(3)
            window = self.window()
            if hasattr(window, "page_list"):
                voucher_page = window.page_list[3]
                from frontend.pages.voucher import VoucherPage
                if isinstance(voucher_page, VoucherPage):
                    voucher_page._open_voucher(label)
            self.select_page_by_action("Voucher Entry", label)
        elif action == "gstr":
            self.nav_item_changed.emit(9)
            window = self.window()
            if hasattr(window, "page_list"):
                gstr_page = window.page_list[9]
                from frontend.pages.gstr_report import GSTRReportPage
                if isinstance(gstr_page, GSTRReportPage):
                    gstr_page.switch_tab(label)
            self.select_page_by_action("GSTR Report", label)
        elif action == "import_sales":
            self.import_requested.emit()
        elif action == "import_purchase":
            self.import_purchase_requested.emit()
        elif action == "import_payment":
            self.import_payment_requested.emit()

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
            QPushButton#subNavItem:checked {{
                color: #FFFFFF;
                background: rgba(59,130,246,0.18);
                font-weight: 600;
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
