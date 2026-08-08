from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QStatusBar, QLabel, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
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
from frontend.pages.settings import SettingsPage
from frontend.pages.credit_note import CreditNoteDialog
from frontend.pages.debit_note import DebitNoteDialog
from frontend.components.sidebar import Sidebar
from frontend.components.header import HeaderBar, DARK_QSS
from frontend.components.company_drawer import CompanyDrawer
from frontend.theme import THEME, GLOBAL_QSS
import frontend.session as session
import frontend.api_client as api
from frontend.pages.import_sales import ImportSalesVoucherDialog
from frontend.pages.import_purchase import ImportPurchaseVoucherDialog
from frontend.pages.import_payment import ImportPaymentReceiptDialog
from frontend.pages.gstr_report import GSTRReportPage
from frontend.pages.user_management import UserManagementPage
from frontend.pages.invoice_signature import InvoiceSignaturePage
from frontend.pages.transport import TransportPage
from frontend.pages.stock_report import (
    StockGroupSummaryPage, StockCategorySummaryPage,
    StockMonthlySummaryPage, StockVouchersPage, StockQueryPage
)

# Page title / breadcrumb map (index → (title, breadcrumb))
_PAGE_META = {
    0: ("Dashboard",         "Home"),
    1: ("Companies",         "Home  ›  Companies"),
    2: ("Ledgers",           "Masters  ›  Ledgers"),
    3: ("Voucher Entry",     "Home  ›  Voucher Entry"),
    4: ("Trial Balance",     "Reports  ›  Trial Balance"),
    5: ("Profit & Loss",     "Reports  ›  Profit & Loss"),
    6: ("Ledger Statement",  "Reports  ›  Ledger Statement"),
    7: ("Inventory",         "Masters  ›  Inventory"),
    8: ("Balance Sheet",     "Reports  ›  Balance Sheet"),
    9: ("GSTR Report",       "Reports  ›  GSTR Report"),
    10: ("Backup",            "Settings  ›  Backup"),
    11: ("User Management",   "Settings  ›  User Management"),
    12: ("Invoice Signature", "Settings  ›  Invoice Signature"),
    13: ("Transporters",      "Masters  ›  Transporters"),
    14: ("Stock Group Summary",    "Reports  ›  Stock Group Summary"),
    15: ("Stock Category Summary", "Reports  ›  Stock Category Summary"),
    16: ("Stock Monthly Summary",  "Reports  ›  Stock Monthly Summary"),
    17: ("Stock Vouchers",         "Reports  ›  Stock Vouchers"),
    18: ("Stock Query",            "Reports  ›  Stock Query"),
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bestie Accounts")
        self.setMinimumSize(1200, 720)
        self._dark_mode = False
        self._build_ui()
        self._setup_shortcuts()
        self.header.set_user(session.username)
        self.refresh_company_header()
        self.sidebar.refresh_permissions()
        self._start_heartbeat()
        self._load_db_info()
        
        self.header.logout_requested.connect(self._on_logout_click)

    def _on_logout_click(self):
        reply = QMessageBox.question(
            self, "Confirm Logout",
            "Are you sure you want to logout and exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try: api.logout()
            except: pass
            self.force_logout()

    def _start_heartbeat(self):
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._validate_session)
        self._heartbeat_timer.start(60000) # Every 1 minute

    def _validate_session(self):
        try:
            api.validate_session()
        except Exception as e:
            self._heartbeat_timer.stop()
            QMessageBox.critical(self, "Session Expired", f"Your session has ended or your account was deactivated.\nReason: {e}")
            self.force_logout()

    def force_logout(self):
        session.clear()
        # In a real app, we might want to restart the process or show login again
        # For now, let's just close the window which will trigger a restart requirement
        self.close()

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
        self.sidebar.import_requested.connect(self.open_import_sales)
        self.sidebar.import_purchase_requested.connect(self.open_import_purchase)
        self.sidebar.import_payment_requested.connect(self.open_import_payment)
        self.sidebar.company_toggle_requested.connect(self.toggle_company_drawer)
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
        self.header.company_toggle_requested.connect(self.toggle_company_drawer)
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
            GSTRReportPage(),
            SettingsPage(),
            UserManagementPage(),
            InvoiceSignaturePage(),
            TransportPage(),
            StockGroupSummaryPage(),
            StockCategorySummaryPage(),
            StockMonthlySummaryPage(),
            StockVouchersPage(),
            StockQueryPage(),
        ]
        for p in self.page_list:
            self.pages.addWidget(p)
        
        right_layout.addWidget(self.pages, 1)

        root_layout.addWidget(right_panel, 1)

        # ── Company Drawer ────────────────────────────────────────────
        self.company_drawer = CompanyDrawer(self)
        self.company_drawer.setVisible(False)
        self.company_drawer.company_changed.connect(self._on_company_changed_in_drawer)
        self.company_drawer.close_requested.connect(lambda: self.company_drawer.setVisible(False))
        root_layout.addWidget(self.company_drawer)

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

        self._db_icon = QLabel()
        self._db_lbl = QLabel("")
        self._db_icon.setPixmap(get_icon("frontend/assets/icons/database.svg", THEME['text_secondary']).pixmap(16, 16))
        self._status_bar.addPermanentWidget(self._db_icon)
        self._status_bar.addPermanentWidget(self._db_lbl)

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
        sc_company.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_company.activated.connect(lambda: self._navigate_to(1))

        # Alt+V → navigate to Voucher Entry (index 3)
        sc_voucher = QShortcut(QKeySequence("Alt+V"), self)
        sc_voucher.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_voucher.activated.connect(lambda: self._navigate_to(3))

        # Alt+D → Dashboard
        sc_dash = QShortcut(QKeySequence("Alt+D"), self)
        sc_dash.activated.connect(lambda: self._navigate_to(0))

        # Alt+L → Ledgers
        sc_led = QShortcut(QKeySequence("Alt+L"), self)
        sc_led.activated.connect(lambda: self._navigate_to(2))

        # Alt+I → Inventory
        sc_inv = QShortcut(QKeySequence("Alt+I"), self)
        sc_inv.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_inv.activated.connect(lambda: self._navigate_to(7))

        # Alt+T → Trial Balance
        sc_tb = QShortcut(QKeySequence("Alt+T"), self)
        sc_tb.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_tb.activated.connect(lambda: self._navigate_to(4))

        # Alt+B → Balance Sheet
        sc_bs = QShortcut(QKeySequence("Alt+B"), self)
        sc_bs.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_bs.activated.connect(lambda: self._navigate_to(8))

        # Alt+P → Profit & Loss
        sc_pl = QShortcut(QKeySequence("Alt+P"), self)
        sc_pl.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_pl.activated.connect(lambda: self._navigate_to(5))

        # Alt+S → Ledger Statement (Report)
        sc_rep = QShortcut(QKeySequence("Alt+S"), self)
        sc_rep.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_rep.activated.connect(lambda: self._navigate_to(6))
        
        # Alt+R → GSTR Report
        sc_gstr = QShortcut(QKeySequence("Alt+R"), self)
        sc_gstr.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_gstr.activated.connect(lambda: self._navigate_to(9))
        
        # Alt+G → Settings
        sc_sett = QShortcut(QKeySequence("Alt+G"), self)
        sc_sett.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_sett.activated.connect(lambda: self._navigate_to(10))
        
        # Ctrl+M → Toggle Sidebar
        sc_side = QShortcut(QKeySequence("Ctrl+M"), self)
        sc_side.activated.connect(self.sidebar.toggle)

        # Ctrl+Alt+I → Import Sales Voucher
        sc_import = QShortcut(QKeySequence("Ctrl+Alt+I"), self)
        sc_import.activated.connect(self.open_import_sales)

        # Ctrl+Alt+P → Import Purchase Voucher
        sc_import_p = QShortcut(QKeySequence("Ctrl+Alt+P"), self)
        sc_import_p.activated.connect(self.open_import_purchase)

        # Ctrl+Alt+R → Import Payment / Receipt Voucher
        sc_import_r = QShortcut(QKeySequence("Ctrl+Alt+R"), self)
        sc_import_r.activated.connect(self.open_import_payment)

    def _should_navigate(self) -> bool:
        from PySide6.QtWidgets import QApplication, QDialog
        active_win = QApplication.activeWindow()
        if isinstance(active_win, QDialog):
            return False
            
        focused = QApplication.focusWidget()
        if focused:
            from frontend.utils import SearchableComboBox
            obj = focused
            while obj:
                if isinstance(obj, SearchableComboBox) or obj.__class__.__name__ == "_SearchPopup":
                    return False
                obj = obj.parent()
        return True

    # ──────────────────────────────────────────────────────────────────
    def _navigate_to(self, index: int):
        if not self._should_navigate():
            return
        self.sidebar.select_page(index)
        self.pages.setCurrentIndex(index)
        title, bc = _PAGE_META.get(index, ("", "Home"))
        self.header.set_page(title, bc)

    def _on_nav_changed(self, index: int):
        self.pages.setCurrentIndex(index)
        title, bc = _PAGE_META.get(index, ("", "Home"))
        self.header.set_page(title, bc)

    def toggle_company_drawer(self):
        if not self.company_drawer.isVisible():
            self.company_drawer.load_companies()
            self.company_drawer.setVisible(True)
        else:
            self.company_drawer.setVisible(False)

    def _on_company_changed_in_drawer(self):
        self.refresh_company_header()
        self.sidebar.refresh_permissions()
        
        # Reload current page if it supports it
        cur = self.pages.currentWidget()
        if cur and hasattr(cur, "_load"):
            cur._load()

    def open_credit_note(self, voucher=None):
        """Open CreditNoteDialog as a maximized modal dialog."""
        action = "update" if voucher else "edit"
        if not session.has_permission("Credit Note", action):
            QMessageBox.warning(self, "Permission Denied", f"You do not have permission to {action} Credit Notes.")
            return
            
        dlg = CreditNoteDialog(self)
        dlg.set_voucher(voucher)
        if dlg.exec():
            # If we are on the Voucher Entry page, refresh the list
            if self.pages.currentIndex() == 3:
                self.page_list[3]._load()

    def open_debit_note(self, voucher=None):
        """Open DebitNoteDialog as a maximized modal dialog."""
        action = "update" if voucher else "edit"
        if not session.has_permission("Debit Note", action):
            QMessageBox.warning(self, "Permission Denied", f"You do not have permission to {action} Debit Notes.")
            return
            
        dlg = DebitNoteDialog(self)
        dlg.set_voucher(voucher)
        if dlg.exec():
            # If we are on the Voucher Entry page, refresh the list
            if self.pages.currentIndex() == 3:
                self.page_list[3]._load()

    def open_import_sales(self):
        """Open ImportSalesVoucherDialog."""
        if not session.has_permission("Sales", "edit"):
            QMessageBox.warning(self, "Permission Denied", "You do not have permission to create/import Sales.")
            self.sidebar.clear_import_selection()
            return
            
        dlg = ImportSalesVoucherDialog(self)
        dlg.exec()
        self.sidebar.clear_import_selection()
        if self.pages.currentIndex() == 3:
            self.page_list[3]._load()

    def open_import_purchase(self):
        """Open ImportPurchaseVoucherDialog."""
        if not session.has_permission("Purchase", "edit"):
            QMessageBox.warning(self, "Permission Denied", "You do not have permission to create/import Purchases.")
            self.sidebar.clear_import_selection()
            return
            
        dlg = ImportPurchaseVoucherDialog(self)
        dlg.exec()
        self.sidebar.clear_import_selection()
        if self.pages.currentIndex() == 3:
            self.page_list[3]._load()

    def open_import_payment(self):
        """Open ImportPaymentReceiptDialog."""
        can_pay = session.has_permission("Payment", "edit")
        can_rec = session.has_permission("Receipt", "edit")
        if not can_pay and not can_rec:
            QMessageBox.warning(self, "Permission Denied", "You do not have permission to create/import Payments or Receipts.")
            self.sidebar.clear_import_selection()
            return
            
        dlg = ImportPaymentReceiptDialog(self)
        dlg.exec()
        self.sidebar.clear_import_selection()
        if self.pages.currentIndex() == 3:
            self.page_list[3]._load()

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
        p_from  = session.period_from or ""
        p_to    = session.period_to   or ""

        display_name = name or "No company selected"

        # Sidebar chip
        self.sidebar.set_active_company(display_name)

        # Top header badge
        self.header.set_company(name, fy_from, fy_to, p_from, p_to)

        # Window title
        self.setWindowTitle(
            f"Bestie Accounts  —  {name}" if name else "Bestie Accounts"
        )

        # Status bar
        self._co_lbl.setText(display_name)
        
        # In status bar, show Active Period
        if p_from and p_to:
            self._fy_lbl.setText(
                f" Period: {p_from[:10]} → {p_to[:10]}"
            )
            self._fy_icon.setVisible(True)
        else:
            self._fy_lbl.setText("")
            self._fy_icon.setVisible(False)

    def _load_db_info(self):
        try:
            info = api.get_db_info()
            db_path = info.get("db_path", "")
            mongo_uri = info.get("mongo_uri", "")
            
            if "localhost" in mongo_uri or "127.0.0.1" in mongo_uri:
                self._db_lbl.setText(f" DB Path: {db_path}")
            else:
                self._db_lbl.setText(f" DB: {mongo_uri}")
        except Exception:
            self._db_lbl.setText(" DB: Disconnected")
