from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QWidget
)
from PySide6.QtGui import QKeySequence, QShortcut, QIcon, QPixmap

from frontend.theme import THEME
from frontend.utils import get_icon


class SearchBar(QLineEdit):
    """Ctrl+K activates this search bar from anywhere in the window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Search…  (Ctrl+K)")
        self.setObjectName("HeaderSearch")
        self.setFixedWidth(240)
        self.setFixedHeight(34)
        self.setStyleSheet(f"""
            QLineEdit#HeaderSearch {{
                background: {THEME['bg']};
                border: 1.5px solid {THEME['border_dark']};
                border-radius: 17px;
                padding: 0 14px 0 36px;
                color: {THEME['text_primary']};
                font-size: 13px;
            }}
            QLineEdit#HeaderSearch:focus {{
                border-color: {THEME['primary']};
                background: {THEME['card']};
            }}
        """)
        # Search icon via QAction
        self.addAction(get_icon("frontend/assets/icons/search.svg", THEME['text_primary']), QLineEdit.ActionPosition.LeadingPosition)


class HeaderBar(QFrame):
    """Top application header bar."""

    theme_toggled = Signal(bool)       # True → dark mode
    logout_requested = Signal()
    company_toggle_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        self.setFixedHeight(58)
        self._dark_mode = False
        self._build()
        self._apply_style()

    # ── construction ──────────────────────────────────────────────────
    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(12)

        # Breadcrumb  (page title + optional sub-title)
        breadcrumb_box = QWidget()
        breadcrumb_box.setObjectName("BreadcrumbBox")
        bc_layout = QVBoxLayout(breadcrumb_box)
        bc_layout.setContentsMargins(0, 0, 0, 0)
        bc_layout.setSpacing(0)

        self._page_title = QLabel("Dashboard")
        self._page_title.setObjectName("PageTitle")

        self._breadcrumb = QLabel("Home")
        self._breadcrumb.setObjectName("Breadcrumb")

        bc_layout.addWidget(self._breadcrumb)
        bc_layout.addWidget(self._page_title)
        layout.addWidget(breadcrumb_box)

        layout.addStretch()

        # Active company badge
        self._company_badge = QPushButton("")
        self._company_badge.setObjectName("CompanyBadge")
        self._company_badge.setVisible(False)
        self._company_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._company_badge.clicked.connect(self._on_company_badge_clicked)
        layout.addWidget(self._company_badge)

        # Active user badge
        self._user_badge = QLabel("")
        self._user_badge.setObjectName("UserBadge")
        layout.addWidget(self._user_badge)

        # Search
        self._search = SearchBar()
        layout.addWidget(self._search)

        # Dark mode toggle
        self._dark_toggle = QPushButton()
        self._dark_toggle.setIcon(get_icon("frontend/assets/icons/moon.svg", THEME['text_primary']))
        self._dark_toggle.setIconSize(QSize(20, 20))
        self._dark_toggle.setObjectName("DarkToggle")
        self._dark_toggle.setFixedSize(36, 36)
        self._dark_toggle.setToolTip("Toggle dark / light mode")
        self._dark_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dark_toggle.clicked.connect(self._on_theme_toggle)
        layout.addWidget(self._dark_toggle)

        # Logout
        self._logout_btn = QPushButton()
        self._logout_btn.setIcon(get_icon("frontend/assets/icons/logout.svg", THEME['danger']))
        self._logout_btn.setIconSize(QSize(18, 18))
        self._logout_btn.setObjectName("LogoutBtn")
        self._logout_btn.setFixedSize(36, 36)
        self._logout_btn.setToolTip("Logout  (Ctrl+L)")
        self._logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._logout_btn.clicked.connect(self.logout_requested.emit)
        layout.addWidget(self._logout_btn)

    # ── public API ────────────────────────────────────────────────────
    def set_page(self, title: str, breadcrumb: str = "Home"):
        self._page_title.setText(title)
        self._breadcrumb.setText(breadcrumb)

    def set_company(self, name: str, fy_from: str = "", fy_to: str = "", p_from: str = "", p_to: str = ""):
        if name:
            text = f" {name}"
            if fy_from and fy_to:
                text += f"  |  FY: {fy_from[:7]} → {fy_to[:7]}"
            if p_from and p_to and (p_from != fy_from or p_to != fy_to):
                text += f"  |  Period: {p_from[:7]} → {p_to[:7]}"
            self._company_badge.setText(text)
            self._company_badge.setVisible(True)
        else:
            self._company_badge.setVisible(False)

    def set_user(self, username: str):
        if username:
            self._user_badge.setText(f"👤  {username}")
            self._user_badge.setVisible(True)
        else:
            self._user_badge.setVisible(False)

    def focus_search(self):
        self._search.setFocus()
        self._search.selectAll()

    def _on_company_badge_clicked(self):
        self.company_toggle_requested.emit()

    # ── private ───────────────────────────────────────────────────────
    def _on_theme_toggle(self):
        self._dark_mode = not self._dark_mode
        icon = "sun.svg" if self._dark_mode else "moon.svg"
        color = "#ffffff" if self._dark_mode else THEME['text_primary']
        self._dark_toggle.setIcon(get_icon(f"frontend/assets/icons/{icon}", color))
        self.theme_toggled.emit(self._dark_mode)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QFrame#HeaderBar {{
                background: {THEME['header_bg']};
                border-bottom: 1px solid {THEME['header_border']};
            }}
            QLabel#PageTitle {{
                font-size: 17px;
                font-weight: 700;
                color: {THEME['text_primary']};
            }}
            QLabel#Breadcrumb {{
                font-size: 11px;
                color: {THEME['text_muted']};
            }}
            QPushButton#CompanyBadge {{
                font-size: 12px;
                color: {THEME['primary_dark']};
                background: #DBEAFE;
                border: none;
                border-radius: 12px;
                padding: 4px 12px;
                font-weight: 600;
            }}
            QPushButton#CompanyBadge:hover {{
                background: #BFDBFE;
            }}
            QLabel#UserBadge {{
                font-size: 12px;
                color: #047857;
                background: #D1FAE5;
                border-radius: 12px;
                padding: 4px 12px;
                font-weight: 600;
            }}
            QPushButton#DarkToggle {{
                background: {THEME['bg']};
                border: 1px solid {THEME['border']};
                border-radius: 18px;
                font-size: 15px;
            }}
            QPushButton#DarkToggle:hover {{
                background: {THEME['border']};
            }}
            QPushButton#LogoutBtn {{
                background: transparent;
                border: 1px solid {THEME['border']};
                border-radius: 18px;
            }}
            QPushButton#LogoutBtn:hover {{
                background: #FEE2E2;
                border-color: {THEME['danger']};
            }}
        """)


# ── Dark mode stylesheet override ─────────────────────────────────────────────
DARK_QSS = """
QWidget { background: #0F172A; color: #E2E8F0; }
QFrame#HeaderBar { background: #1E293B; border-bottom: 1px solid #334155; }
QLabel#PageTitle { color: #F1F5F9; }
QLabel#Breadcrumb { color: #64748B; }
QLabel#CompanyBadge { background: #1E3A5F; color: #93C5FD; }
QTableWidget { background: #1E293B; border-color: #334155; gridline-color: #334155; }
QTableWidget::item { color: #E2E8F0; }
QTableWidget::item:selected { background: #1E40AF; color: #FFFFFF; }
QHeaderView::section { background: #0F172A; color: #94A3B8; border-bottom-color: #334155; }
QLineEdit, QDateEdit, QDoubleSpinBox, QSpinBox, QTextEdit, QComboBox {
    background: #1E293B; border-color: #334155; color: #E2E8F0;
}
QLineEdit:focus, QDateEdit:focus, QDoubleSpinBox:focus { border-color: #3B82F6; }
QDialog { background: #1E293B; }
QScrollArea { background: transparent; }
QWidget#AppRoot { background: #0F172A; }
"""
