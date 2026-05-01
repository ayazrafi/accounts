"""
Reusable card and table widgets used across pages.

Classes
-------
Card            — Rounded white card with optional title and shadow
StatCard        — KPI metric card (icon + value + title)
SectionTitle    — Bold page-section title with optional action button
ModernTable     — Styled QTableWidget with zebra rows, hover, rounded border
PrimaryButton   — Styled primary action button
SecondaryButton — Ghost / outline action button
DangerButton    — Red destructive action button
SuccessButton   — Green confirm action button
FAB             — Floating action button (circle, fixed size)
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QSizePolicy,
    QTableWidget, QVBoxLayout, QWidget
)
from PySide6.QtGui import QColor, QFont, QIcon

from frontend.theme import THEME
from frontend.utils import get_icon


# ─────────────────────────────────────────────────────────────────────────────
#  Card
# ─────────────────────────────────────────────────────────────────────────────
class Card(QFrame):
    """A white rounded card with drop shadow."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setStyleSheet(f"""
            QFrame#Card {{
                background: {THEME['card']};
                border-radius: 12px;
                border: 1px solid {THEME['border']};
                border-bottom: 2px solid #D1D5DB;
                border-right: 1.5px solid #D1D5DB;
            }}
        """)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(20, 16, 20, 16)
        self._outer.setSpacing(12)

        if title:
            lbl = QLabel(title)
            lbl.setStyleSheet(
                f"font-size:13px;font-weight:600;color:{THEME['text_secondary']};"
                "text-transform:uppercase;letter-spacing:0.5px;"
            )
            self._outer.addWidget(lbl)

    @property
    def content_layout(self) -> QVBoxLayout:
        return self._outer


# ─────────────────────────────────────────────────────────────────────────────
#  StatCard
# ─────────────────────────────────────────────────────────────────────────────
class StatCard(QFrame):
    """Dashboard KPI card:  icon on left, value + title on right."""

    def __init__(self, title: str, value: str | int, icon_path: str = "",
                 accent: str = THEME["primary"], parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setFixedHeight(100)
        self.setMinimumWidth(160)
        self.setStyleSheet(f"""
            QFrame#StatCard {{
                background: {THEME['card']};
                border-radius: 12px;
                border: 1px solid {THEME['border']};
                border-bottom: 2px solid #D1D5DB;
                border-right: 1.5px solid #D1D5DB;
            }}
            QFrame#StatCard:hover {{
                border: 1.5px solid {accent};
                border-bottom: 2px solid {accent};
                border-right: 1.5px solid {accent};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        # Icon container
        icon_lbl = QLabel()
        if icon_path:
            # Use the accent color for the icon in the StatCard
            icon_lbl.setPixmap(get_icon(icon_path, accent).pixmap(24, 24))
        icon_lbl.setFixedSize(44, 44)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            f"background:{accent}22;border-radius:22px;"
        )
        layout.addWidget(icon_lbl)

        # Text
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self._val_lbl = QLabel(str(value))
        self._val_lbl.setStyleSheet(
            f"font-size:26px;font-weight:700;color:{accent};"
        )

        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet(
            f"font-size:12px;color:{THEME['text_secondary']};font-weight:500;"
        )

        text_col.addWidget(self._val_lbl)
        text_col.addWidget(self._title_lbl)
        layout.addLayout(text_col)
        layout.addStretch()

    def update_value(self, value: str | int):
        self._val_lbl.setText(str(value))


# ─────────────────────────────────────────────────────────────────────────────
#  SectionTitle
# ─────────────────────────────────────────────────────────────────────────────
class SectionTitle(QWidget):
    """Page-level heading with optional right-side action widget."""

    def __init__(self, title: str, subtitle: str = "", action_widget=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size:20px;font-weight:700;color:{THEME['text_primary']};"
        )
        text_col.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet(
                f"font-size:12px;color:{THEME['text_muted']};"
            )
            text_col.addWidget(sub_lbl)

        layout.addLayout(text_col)
        layout.addStretch()
        if action_widget:
            layout.addWidget(action_widget)


# ─────────────────────────────────────────────────────────────────────────────
#  ModernTable
# ─────────────────────────────────────────────────────────────────────────────
class ModernTable(QTableWidget):
    """QTableWidget styled with zebra rows, hover, rounded card look."""

    def __init__(self, rows: int, cols: int, headers: list[str], parent=None):
        super().__init__(rows, cols, parent)
        self.setHorizontalHeaderLabels(headers)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setSelectionBehavior(self.SelectionBehavior.SelectRows)
        self.setEditTriggers(self.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.horizontalHeader().setHighlightSections(False)
        self.setStyleSheet(f"""
            QTableWidget {{
                background: {THEME['card']};
                border: 1px solid {THEME['border']};
                border-radius: 12px;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 9px 14px;
                border: none;
            }}
            QTableWidget::item:alternate {{
                background: {THEME['bg']};
            }}
            QTableWidget::item:selected {{
                background: #DBEAFE;
                color: {THEME['primary_dark']};
            }}
            QTableWidget::item:hover:!selected {{
                background: #F0F7FF;
            }}
            QHeaderView::section {{
                background: {THEME['bg']};
                color: {THEME['text_secondary']};
                font-weight: 600;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 10px 14px;
                border: none;
                border-bottom: 2px solid {THEME['border']};
            }}
            QScrollBar:vertical {{
                width: 6px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: {THEME['border_dark']};
                border-radius: 3px;
            }}
        """)

    def set_row_count_reset(self):
        """Clear all rows (preserves column headers)."""
        self.setRowCount(0)


# ─────────────────────────────────────────────────────────────────────────────
#  Buttons
# ─────────────────────────────────────────────────────────────────────────────

def _btn_style(bg: str, hover: str, text: str = "#FFFFFF",
               ghost: bool = False, border: str = "") -> str:
    if ghost:
        return f"""
            QPushButton {{
                background: transparent;
                color: {bg};
                border: 1.5px solid {border or bg};
                border-radius: 7px;
                padding: 6px 16px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{ background: {bg}18; }}
            QPushButton:pressed {{ background: {bg}30; }}
            QPushButton:disabled {{ color: {THEME['text_muted']}; border-color: {THEME['border']}; }}
        """
    return f"""
        QPushButton {{
            background: {bg};
            color: {text};
            border: none;
            border-radius: 7px;
            padding: 7px 18px;
            font-weight: 600;
            font-size: 13px;
        }}
        QPushButton:hover   {{ background: {hover}; }}
        QPushButton:pressed {{ background: {hover}; }}
        QPushButton:disabled {{ background: {THEME['border']}; color: {THEME['text_muted']}; }}
    """


class PrimaryButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(_btn_style(THEME["primary"], THEME["primary_dark"]))


class SecondaryButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(_btn_style(THEME["primary"], THEME["primary_dark"], ghost=True))


class DangerButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(_btn_style(THEME["danger"], THEME["danger_dark"]))


class SuccessButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(_btn_style(THEME["success"], THEME["success_dark"]))


# ─────────────────────────────────────────────────────────────────────────────
#  IconActionButton  (icon-only square) + PillActionButton (icon + label)
# ─────────────────────────────────────────────────────────────────────────────

# Shared colour palette for action variants
_ACTION_VARIANTS: dict[str, dict] = {
    "edit": {
        "color":       "#2563EB",
        "bg":          "#EFF6FF",
        "border":      "#BFDBFE",
        "hover_bg":    "#2563EB",
        "hover_color": "#FFFFFF",
        "active_bg":   "#1D4ED8",
    },
    "success": {
        "color":       "#15803D",
        "bg":          "#F0FDF4",
        "border":      "#BBF7D0",
        "hover_bg":    "#16A34A",
        "hover_color": "#FFFFFF",
        "active_bg":   "#15803D",
    },
    "danger": {
        "color":       "#DC2626",
        "bg":          "#FEF2F2",
        "border":      "#FECACA",
        "hover_bg":    "#DC2626",
        "hover_color": "#FFFFFF",
        "active_bg":   "#B91C1C",
    },
    "neutral": {
        "color":       "#475569",
        "bg":          "#F8FAFC",
        "border":      "#E2E8F0",
        "hover_bg":    "#475569",
        "hover_color": "#FFFFFF",
        "active_bg":   "#334155",
    },
}


class IconActionButton(QPushButton):
    """
    Small rounded icon-only button for table action cells.
    Switches icon to white on hover for high contrast.
    """

    def __init__(self, icon_path: str, tooltip: str,
                 variant: str = "neutral", size: int = 32, parent=None):
        super().__init__(parent)
        self._v = _ACTION_VARIANTS.get(variant, _ACTION_VARIANTS["neutral"])
        self._icon_path = icon_path
        self._size = size
        
        if icon_path:
            self._icon_normal = get_icon(icon_path, self._v['color'])
            self._icon_hover = get_icon(icon_path, "#ffffff")
            self.setIcon(self._icon_normal)
            self.setIconSize(QSize(size // 2, size // 2))
        
        radius = size // 2
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self._apply_style()

    def _apply_style(self):
        v = self._v
        radius = self._size // 2
        self.setStyleSheet(f"""
            QPushButton {{
                background: {v['bg']};
                color: {v['color']};
                border: 1.5px solid {v['border']};
                border-radius: {radius}px;
                padding: 0;
                margin: 0;
            }}
            QPushButton:hover {{
                background: {v['hover_bg']};
                color: {v['hover_color']};
                border-color: {v['hover_bg']};
            }}
            QPushButton:pressed {{
                background: {v['active_bg']};
                border-color: {v['active_bg']};
            }}
        """)

    def enterEvent(self, event):
        if hasattr(self, "_icon_hover"):
            self.setIcon(self._icon_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if hasattr(self, "_icon_normal"):
            self.setIcon(self._icon_normal)
        super().leaveEvent(event)


class PillActionButton(QPushButton):
    """
    Pill-shaped button with a leading SVG icon and a text label.
    Designed for table row action columns.
    Switches icon to white on hover for high contrast.
    """

    def __init__(self, icon_path: str, label: str, tooltip: str,
                 variant: str = "neutral", parent=None):
        super().__init__(label, parent)
        self._v = _ACTION_VARIANTS.get(variant, _ACTION_VARIANTS["neutral"])
        self._icon_path = icon_path
        
        if icon_path:
            self._icon_normal = get_icon(icon_path, self._v['color'])
            self._icon_hover = get_icon(icon_path, "#ffffff")
            self.setIcon(self._icon_normal)
            self.setIconSize(QSize(14, 14))
            
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setFixedHeight(30)
        self._apply_style()

    def _apply_style(self):
        v = self._v
        self.setStyleSheet(f"""
            QPushButton {{
                background: {v['bg']};
                color: {v['color']};
                border: 1.5px solid {v['border']};
                border-radius: 15px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 14px;
                letter-spacing: 0.2px;
            }}
            QPushButton:hover {{
                background: {v['hover_bg']};
                color: {v['hover_color']};
                border-color: {v['hover_bg']};
            }}
            QPushButton:pressed {{
                background: {v['active_bg']};
                border-color: {v['active_bg']};
                color: #FFFFFF;
            }}
            QPushButton:disabled {{
                background: {THEME['border']};
                color: {THEME['text_muted']};
                border-color: {THEME['border']};
            }}
        """)

    def enterEvent(self, event):
        if hasattr(self, "_icon_hover"):
            self.setIcon(self._icon_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if hasattr(self, "_icon_normal"):
            self.setIcon(self._icon_normal)
        super().leaveEvent(event)


class FAB(QPushButton):
    """Floating Action Button — circular, prominent, uses SVG icon."""

    def __init__(self, icon_path: str, tooltip: str = "", parent=None):
        super().__init__(parent)
        if icon_path:
            self.setIcon(get_icon(icon_path, "#ffffff"))
            self.setIconSize(QSize(24, 24))
        self.setFixedSize(46, 46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)
        self.setStyleSheet(f"""
            QPushButton {{
                background: {THEME['primary']};
                color: #ffffff;
                border-radius: 23px;
                border: none;
            }}
            QPushButton:hover {{
                background: {THEME['primary_dark']};
            }}
            QPushButton:pressed {{
                background: #1D4ED8;
            }}
        """)
