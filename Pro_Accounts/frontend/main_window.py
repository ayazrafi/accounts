from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QStatusBar, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut, QIcon

from frontend.pages.dashboard import DashboardPage
from frontend.pages.company import CompanyPage
from frontend.pages.ledger import LedgerPage
from frontend.theme import THEME
from frontend.utils import get_icon
from frontend.pages.voucher import VoucherPage
from frontend.pages.trial_balance import TrialBalancePage
from frontend.pages.profit_loss import ProfitLossPage
from frontend.pages.ledger_report import LedgerReportPage
from frontend.pages.inventory import InventoryPage
from frontend.pages.balance_sheet import BalanceSheetPage
from frontend.components.sidebar import Sidebar
from frontend.components.header import HeaderBar, DARK_QSS
from frontend.theme import THEME, GLOBAL_QSS
import frontend.session as session

# Page title / breadcrumb map (index → (title, breadcrumb))
_PAGE_META = {
    0: ("Dashboard",        "Home"),
    1: ("Companies",        "Home  ›  Companies"),
    2: ("Ledgers",          "Home  ›  Ledgers"),
    3: ("Voucher Entry",    "Home  ›  Voucher Entry"),
    4: ("Trial Balance",    "Reports  ›  Trial Balance"),
    5: ("Profit & Loss",    "Reports  ›  Profit & Loss"),
    6: ("Ledger Statement", "Reports  ›  Ledger Statement"),
    7: ("Inventory",        "Home  ›  Inventory"),
    8: ("Balance Sheet",    "Reports  ›  Balance Sheet"),
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bestie Accounts")
        self.setMinimumSize(1200, 720)
        self._dark_mode = False
        self._build_ui()
        self._setup_shortcuts()
        self.refresh_company_header()

    # ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        central.setObjectName("AppRoot")
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────
        self.sidebar = Sidebar()
        self.sidebar.nav_item_changed.connect(self._on_nav_changed)
        root_layout.addWidget(self.sidebar)

        # ── Right panel (header + pages) ──────────────────────────────
        right_panel = QWidget()
        right_panel.setObjectName("RightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Header
        self.header = HeaderBar()
        self.header.theme_toggled.connect(self._on_theme_toggle)
        right_layout.addWidget(self.header)

        # Page stack
        self.pages = QStackedWidget()
        self.pages.setObjectName("PageStack")
        self.page_list = [
            DashboardPage(),
            CompanyPage(),
            LedgerPage(),
            VoucherPage(),
            TrialBalancePage(),
            ProfitLossPage(),
            LedgerReportPage(),
            InventoryPage(),
            BalanceSheetPage(),
        ]
        for p in self.page_list:
            self.pages.addWidget(p)
        right_layout.addWidget(self.pages, 1)

        root_layout.addWidget(right_panel, 1)

        # ── Status bar ────────────────────────────────────────────────
        self._status_bar = QStatusBar()
        self._status_bar.setObjectName("app_status_bar")
        self.setStatusBar(self._status_bar)
        self._co_icon = QLabel()
        self._co_lbl = QLabel("")
        self._fy_icon = QLabel()
        self._fy_lbl = QLabel("")
        
        self._co_icon.setPixmap(get_icon("frontend/assets/icons/company.svg", THEME['text_secondary']).pixmap(16, 16))
        self._fy_icon.setPixmap(get_icon("frontend/assets/icons/edit-file.svg", THEME['text_secondary']).pixmap(16, 16))
        
        self._status_bar.addWidget(self._co_icon)
        self._status_bar.addWidget(self._co_lbl, 1)
        self._status_bar.addPermanentWidget(self._fy_icon)
        self._status_bar.addPermanentWidget(self._fy_lbl)

        # Initial header page
        self._on_nav_changed(0)

    # ──────────────────────────────────────────────────────────────────
    def _setup_shortcuts(self):
        # Ctrl+\ → toggle sidebar
        sc_sidebar = QShortcut(QKeySequence("Ctrl+\\"), self)
        sc_sidebar.activated.connect(self.sidebar.toggle)

        # Ctrl+K → focus search
        sc_search = QShortcut(QKeySequence("Ctrl+K"), self)
        sc_search.activated.connect(self.header.focus_search)

        # Alt+C → navigate to Companies  (index 1)
        sc_company = QShortcut(QKeySequence("Alt+C"), self)
        sc_company.activated.connect(lambda: self._navigate_to(1))

        # Alt+V → navigate to Voucher Entry (index 3)
        sc_voucher = QShortcut(QKeySequence("Alt+V"), self)
        sc_voucher.activated.connect(lambda: self._navigate_to(3))

        # Alt+D → Dashboard
        sc_dash = QShortcut(QKeySequence("Alt+D"), self)
        sc_dash.activated.connect(lambda: self._navigate_to(0))

        # Alt+L → Ledgers
        sc_led = QShortcut(QKeySequence("Alt+L"), self)
        sc_led.activated.connect(lambda: self._navigate_to(2))

        # Alt+I → Inventory
        sc_inv = QShortcut(QKeySequence("Alt+I"), self)
        sc_inv.activated.connect(lambda: self._navigate_to(7))

        # Alt+T → Trial Balance
        sc_tb = QShortcut(QKeySequence("Alt+T"), self)
        sc_tb.activated.connect(lambda: self._navigate_to(4))

        # Alt+B → Balance Sheet
        sc_bs = QShortcut(QKeySequence("Alt+B"), self)
        sc_bs.activated.connect(lambda: self._navigate_to(8))

        # Alt+P → Profit & Loss
        sc_pl = QShortcut(QKeySequence("Alt+P"), self)
        sc_pl.activated.connect(lambda: self._navigate_to(5))

        # Alt+S → Ledger Statement (Report)
        sc_rep = QShortcut(QKeySequence("Alt+S"), self)
        sc_rep.activated.connect(lambda: self._navigate_to(6))
        
        # Ctrl+M → Toggle Sidebar
        sc_side = QShortcut(QKeySequence("Ctrl+M"), self)
        sc_side.activated.connect(self.sidebar.toggle)

    # ──────────────────────────────────────────────────────────────────
    def _navigate_to(self, index: int):
        self.sidebar.select_page(index)
        self.pages.setCurrentIndex(index)
        title, bc = _PAGE_META.get(index, ("", "Home"))
        self.header.set_page(title, bc)

    def _on_nav_changed(self, index: int):
        self.pages.setCurrentIndex(index)
        title, bc = _PAGE_META.get(index, ("", "Home"))
        self.header.set_page(title, bc)

    # ──────────────────────────────────────────────────────────────────
    def _on_theme_toggle(self, dark: bool):
        self._dark_mode = dark
        from PySide6.QtWidgets import QApplication
        from frontend.theme import GLOBAL_QSS
        app = QApplication.instance()
        if dark:
            app.setStyleSheet(GLOBAL_QSS + DARK_QSS)
        else:
            app.setStyleSheet(GLOBAL_QSS)

    # ──────────────────────────────────────────────────────────────────
    def refresh_company_header(self):
        name    = session.company_name or ""
        fy_from = session.fiscal_year_from or ""
        fy_to   = session.fiscal_year_to   or ""

        display_name = name or "No company selected"

        # Sidebar chip
        self.sidebar.set_active_company(display_name)

        # Top header badge
        self.header.set_company(name, fy_from, fy_to)

        # Window title
        self.setWindowTitle(
            f"Bestie Accounts  —  {name}" if name else "Bestie Accounts"
        )

        # Status bar
        self._co_lbl.setText(display_name)
        
        if fy_from and fy_to:
            self._fy_lbl.setText(
                f" FY: {fy_from[:7]} → {fy_to[:7]}"
            )
            self._fy_icon.setVisible(True)
        else:
            self._fy_lbl.setText("")
            self._fy_icon.setVisible(False)
