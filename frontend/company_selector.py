from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QWidget, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, QEvent
from PySide6.QtGui import QIcon
from frontend.utils import get_icon
import frontend.api_client as api
import frontend.session as session


class CompanySelectorDialog(QDialog):
    """
    Shown at startup.
    • If no companies exist → opens Create Company dialog immediately.
    • Otherwise lists companies and lets user select one.
    • Cannot be dismissed without selecting a company (or creating one).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bestie Accounts — Select Company")
        self.setMinimumSize(520, 400)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self._companies = []
        self._build()
        self._load()
        # Focus the list so user can use arrow keys immediately
        self.list_widget.setFocus()
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(16)

        # Header
        hdr = QWidget(); hdr.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hdr.setStyleSheet("background:#1565C0;border-radius:8px;padding:12px;")
        hdr_lay = QVBoxLayout(hdr)
        t1 = QLabel("Bestie Accounts")
        t1.setStyleSheet("color:#fff;font-size:20px;font-weight:bold;")
        t2 = QLabel("Select a company to continue")
        t2.setStyleSheet("color:#bbdefb;font-size:12px;")
        hdr_lay.addWidget(t1); hdr_lay.addWidget(t2)
        root.addWidget(hdr)

        root.addWidget(QLabel("Available Companies:"))

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget { border:1px solid #bbdefb; border-radius:6px;
                          font-size:14px; }
            QListWidget::item { padding:12px 16px; border-bottom:1px solid #e3f2fd; }
            QListWidget::item:selected { background:#e3f2fd; color:#1565C0;
                                         font-weight:bold; }
            QListWidget::item:hover { background:#f5f5f5; }
        """)
        self.list_widget.itemDoubleClicked.connect(self._select)
        self.list_widget.installEventFilter(self)
        root.addWidget(self.list_widget, 1)

        # Buttons
        btn_row = QHBoxLayout()
        self.create_btn = QPushButton("  Create New Company  [Alt+A]")
        self.create_btn.setShortcut("Alt+A")
        self.create_btn.setIcon(get_icon("frontend/assets/icons/plus.svg", "#1565C0"))
        self.create_btn.setIconSize(QSize(16, 16))
        self.create_btn.clicked.connect(self._create_new)
        self.open_btn = QPushButton("Open Selected")
        self.open_btn.setEnabled(False)
        self.open_btn.setStyleSheet(
            "QPushButton{background:#16a34a;color:#fff;border-radius:6px;"
            "padding:8px 20px;font-weight:bold;font-size:14px;}"
            "QPushButton:hover{background:#15803d;}"
            "QPushButton:disabled{background:#94a3b8;}"
        )
        self.open_btn.clicked.connect(self._select)
        self.list_widget.currentRowChanged.connect(
            lambda i: self.open_btn.setEnabled(i >= 0))
        btn_row.addWidget(self.create_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.open_btn)
        root.addLayout(btn_row)

    def eventFilter(self, obj, event):
        if obj is self.list_widget and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._select()
                return True
        return super().eventFilter(obj, event)

    def _load(self):
        self.list_widget.clear()
        try:
            self._companies = api.get_my_companies()
        except Exception as ex:
            QMessageBox.warning(self, "Error", f"Cannot reach backend:\n{ex}")
            return

        if not self._companies and session.is_super_admin:
            # No companies yet and is super admin — prompt to create one immediately
            r = QMessageBox.information(
                self, "No Companies Found",
                "No companies found.\nCreate your first company to get started.",
                QMessageBox.StandardButton.Ok
            )
            self._create_new()
            return
        elif not self._companies:
             QMessageBox.warning(self, "Access Denied", "No companies assigned to your account. Please contact administrator.")
             self.reject()
             return

        for c in self._companies:
            # Map API fields to UI
            # In get_my_companies, 'id' is returned as 'id', but in list_companies it was '_id'
            # Let's standardize on 'id'
            name = c.get('name', 'Unknown')
            role = c.get('role', 'User')
            item = QListWidgetItem(f"  {name}\n  Role: {role}")
            item.setIcon(get_icon("frontend/assets/icons/company.svg", "#475569"))
            item.setSizeHint(QSize(480, 60))
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            self.list_widget.setFocus()

    def _select(self):
        idx = self.list_widget.currentRow()
        if idx < 0 or idx >= len(self._companies):
            QMessageBox.warning(self, "Select Company", "Please select a company first.")
            return
        c = self._companies[idx]
        
        # If it's a regular user, we should fetch full company details to get FY
        try:
            full_c = api.get_company(c["id"])
            session.set_company(
                cid=c["id"],
                name=full_c["name"],
                fy_from=full_c.get("fiscal_year_from", ""),
                fy_to=full_c.get("fiscal_year_to", ""),
            )
            # Fetch and store permissions for this company
            perms = api.get_permissions(c["id"])
            session.permissions = perms
            self.accept()
        except Exception as ex:
             QMessageBox.warning(self, "Error", f"Failed to load company details: {ex}")

    def _create_new(self):
        from frontend.pages.company import CompanyDialog
        dlg = CompanyDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Error", "Company name is required"); return
            try:
                result = api.create_company(data)
                cid = result.get("id", "")
                session.set_company(
                    cid=cid,
                    name=data["name"],
                    fy_from=data.get("fiscal_year_from", ""),
                    fy_to=data.get("fiscal_year_to", ""),
                )
                self.accept()
            except Exception as ex:
                QMessageBox.warning(self, "Error", str(ex))
                self._load()
