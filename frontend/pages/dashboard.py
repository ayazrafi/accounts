from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
import frontend.api_client as api
from frontend.components.cards import StatCard, Card, SectionTitle
from frontend.theme import THEME
from frontend.utils import get_icon


class _QuickLinkBtn(QFrame):
    """Small quick-action card used in the 'Quick Actions' row."""

    def __init__(self, icon_path: str, label: str, on_click=None, parent=None):
        super().__init__(parent)
        self.setObjectName("QuickLink")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(72)
        self.setMinimumWidth(120)
        self.setStyleSheet(f"""
            QFrame#QuickLink {{
                background: {THEME['card']};
                border: 1px solid {THEME['border']};
                border-radius: 10px;
            }}
            QFrame#QuickLink:hover {{
                background: #EFF6FF;
                border-color: {THEME['primary']};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel()
        if icon_path:
            icon_lbl.setPixmap(get_icon(icon_path, THEME['primary']).pixmap(20, 20))
        icon_lbl.setStyleSheet("background: transparent;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_lbl = QLabel(label)
        text_lbl.setStyleSheet(
            f"font-size:11px;color:{THEME['text_secondary']};font-weight:600;"
            "background: transparent;"
        )
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(icon_lbl)
        layout.addWidget(text_lbl)

        if on_click:
            # Store callable for mousePressEvent
            self._on_click = on_click

    def mousePressEvent(self, event):
        if hasattr(self, "_on_click"):
            self._on_click()
        super().mousePressEvent(event)


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        self._stat_cards: dict[str, StatCard] = {}
        self._build()

    def _build(self):
        # Outer scroll area so the page works on small screens
        outer = QScrollArea(self)
        outer.setWidgetResizable(True)
        outer.setFrameShape(QFrame.Shape.NoFrame)
        outer.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.setObjectName("DashScroll")

        container = QWidget()
        container.setObjectName("DashContainer")
        container.setStyleSheet(f"background: {THEME['bg']};")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(24)

        # ── Welcome label ──────────────────────────────────────────────
        self._welcome = QLabel("Good morning 👋")
        self._welcome.setStyleSheet(
            f"font-size:24px;font-weight:700;color:{THEME['text_primary']};background:transparent;"
        )
        layout.addWidget(self._welcome)

        # ── KPI cards ─────────────────────────────────────────────────
        kpi_section = SectionTitle("Overview")
        layout.addWidget(kpi_section)

        self._grid = QGridLayout()
        self._grid.setSpacing(16)
        layout.addLayout(self._grid)

        # ── Quick actions ──────────────────────────────────────────────
        qa_section = SectionTitle("Quick Actions")
        layout.addWidget(qa_section)

        qa_row = QHBoxLayout()
        qa_row.setSpacing(12)
        quick_actions = [
            ("frontend/assets/icons/company.svg", "New Company",    lambda: self._nav_to(1)),
            ("frontend/assets/icons/book.svg",    "New Ledger",     lambda: self._nav_to(2)),
            ("frontend/assets/icons/edit-file.svg", "New Voucher",  lambda: self._nav_to(3)),
            ("frontend/assets/icons/bar-chart.svg", "Trial Balance", lambda: self._nav_to(4)),
            ("frontend/assets/icons/pie-chart.svg", "Profit & Loss",  lambda: self._nav_to(5)),
            ("frontend/assets/icons/edit-file.svg", "Ledger Report",  lambda: self._nav_to(6)),
            ("frontend/assets/icons/settings.svg", "Settings",      lambda: self._nav_to(9)),
        ]
        for icon, label, fn in quick_actions:
            btn = _QuickLinkBtn(icon, label, fn)
            qa_row.addWidget(btn)
        qa_row.addStretch()
        layout.addLayout(qa_row)

        layout.addStretch()
        outer.setWidget(container)

        # Make the scroll area fill this page widget
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(outer)

    def showEvent(self, event):
        self._refresh()
        super().showEvent(event)

    def _refresh(self):
        # Clear existing stat cards
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._stat_cards.clear()

        try:
            companies = api.list_companies()
            ledgers   = api.list_ledgers()
            v_res     = api.list_vouchers()
            vouchers_count = v_res.get("total", 0)
        except Exception:
            companies, ledgers, vouchers_count = [], [], 0

        kpis = [
            ("Companies",   len(companies),  "frontend/assets/icons/company.svg", THEME["primary"]),
            ("Ledgers",     len(ledgers),    "frontend/assets/icons/book.svg", THEME["info"]),
            ("Vouchers",    vouchers_count,   "frontend/assets/icons/edit-file.svg", THEME["success"]),
            ("Voucher Types", 8,             "frontend/assets/icons/settings.svg", THEME["warning"]),
        ]
        for col, (title, val, icon, color) in enumerate(kpis):
            card = StatCard(title, val, icon, color)
            self._grid.addWidget(card, 0, col)
            self._stat_cards[title] = card

    def _nav_to(self, index: int):
        mw = self.window()
        if hasattr(mw, "_navigate_to"):
            mw._navigate_to(index)

