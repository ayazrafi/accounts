from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, Signal
from frontend.utils import get_icon
from frontend.theme import THEME
import frontend.api_client as api
import frontend.session as session

class CompanyDrawer(QFrame):
    company_changed = Signal()
    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CompanyDrawer")
        self.setFixedWidth(280)
        self._companies = []
        self._build()
        self._apply_style()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Select Company")
        title.setObjectName("DrawerTitle")
        
        close_btn = QPushButton("×")
        close_btn.setObjectName("DrawerCloseBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close_requested.emit)
        
        hdr.addWidget(title)
        hdr.addWidget(close_btn)
        layout.addLayout(hdr)

        # List of companies
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("DrawerList")
        self.list_widget.itemDoubleClicked.connect(self._select)
        layout.addWidget(self.list_widget, 1)

        # Active indicator
        self.active_lbl = QLabel("")
        self.active_lbl.setObjectName("DrawerActiveInfo")
        self.active_lbl.setWordWrap(True)
        layout.addWidget(self.active_lbl)

        # Open button
        self.open_btn = QPushButton("Switch Company")
        self.open_btn.setObjectName("DrawerOpenBtn")
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.clicked.connect(self._select)
        layout.addWidget(self.open_btn)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QFrame#CompanyDrawer {{
                background: {THEME['card']};
                border-left: 1px solid {THEME['border']};
            }}
            QLabel#DrawerTitle {{
                font-size: 16px;
                font-weight: bold;
                color: {THEME['primary_dark']};
            }}
            QPushButton#DrawerCloseBtn {{
                font-size: 24px;
                font-weight: bold;
                color: {THEME['text_muted']};
                background: transparent;
                border: none;
                padding-bottom: 4px;
            }}
            QPushButton#DrawerCloseBtn:hover {{
                color: {THEME['danger']};
            }}
            QListWidget#DrawerList {{
                background: transparent;
                border: 1px solid {THEME['border']};
                border-radius: 6px;
                font-size: 13px;
            }}
            QListWidget#DrawerList::item {{
                padding: 10px;
                border-bottom: 1px solid {THEME['border']};
            }}
            QListWidget#DrawerList::item:selected {{
                background: #E3F2FD;
                color: #1565C0;
                font-weight: bold;
            }}
            QListWidget#DrawerList::item:hover {{
                background: #F8FAFC;
            }}
            QLabel#DrawerActiveInfo {{
                font-size: 11px;
                color: {THEME['text_muted']};
                padding: 4px;
            }}
            QPushButton#DrawerOpenBtn {{
                background: {THEME['primary']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton#DrawerOpenBtn:hover {{
                background: {THEME['primary_dark']};
            }}
        """)

    def load_companies(self):
        self.list_widget.clear()
        try:
            self._companies = api.get_my_companies()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load companies: {e}")
            return

        active_id = session.company_id
        active_idx = -1

        for i, c in enumerate(self._companies):
            name = c.get('name', 'Unknown')
            role = c.get('role', 'User')
            item = QListWidgetItem(f"{name}\nRole: {role}")
            item.setSizeHint(QSize(200, 48))
            self.list_widget.addItem(item)
            if c['id'] == active_id:
                active_idx = i

        if active_idx >= 0:
            self.list_widget.setCurrentRow(active_idx)
            self.active_lbl.setText(f"Active: {session.company_name}")
        else:
            self.active_lbl.setText("No active company selected")

    def _select(self):
        idx = self.list_widget.currentRow()
        if idx < 0 or idx >= len(self._companies):
            return
        c = self._companies[idx]
        if c['id'] == session.company_id:
            self.close_requested.emit()
            return
            
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
            
            self.company_changed.emit()
            self.close_requested.emit()
        except Exception as ex:
             QMessageBox.warning(self, "Error", f"Failed to switch company: {ex}")
