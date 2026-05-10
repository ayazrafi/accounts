"""
Keyboard navigation and widget utilities for PySide6 form dialogs.

setup_enter_nav(dialog, widgets)
    Enter key moves focus through fields; Enter on the last field submits the dialog.

SearchableComboBox
    A QComboBox replacement that shows a search/filter box at the top of its
    popup so the user can type to narrow down a long list.
"""
from PySide6.QtWidgets import (
    QComboBox, QListView, QLineEdit, QWidget, QVBoxLayout, QHBoxLayout,
    QAbstractItemView, QFrame, QSizePolicy, QDateEdit,
    QDialog, QDialogButtonBox, QLabel, QPushButton, QGridLayout,
    QSpinBox, QDoubleSpinBox,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor, QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import (
    QObject, Qt, QEvent, QSortFilterProxyModel, QTimer, QPoint, QSize, QDate,
    QByteArray
)
import warnings
import os


def format_indian_number(value, decimals=2):
    """Format a number with Indian digit grouping, e.g. 12,34,567.89."""
    try:
        num = float(value or 0)
    except (TypeError, ValueError):
        num = 0.0

    sign = "-" if num < 0 else ""
    rounded = f"{abs(num):.{decimals}f}"
    whole, _, fraction = rounded.partition(".")

    if len(whole) > 3:
        last_three = whole[-3:]
        remaining = whole[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        whole = ",".join(groups + [last_three])

    if decimals <= 0:
        return f"{sign}{whole}"
    return f"{sign}{whole}.{fraction}"


def format_inr(value, decimals=2, symbol="₹ "):
    return f"{symbol}{format_indian_number(value, decimals)}"


# ──────────────────────────────────────────────────────────────────────────────
#  Icon utilities
# ──────────────────────────────────────────────────────────────────────────────

def get_icon(path: str, color: str = "#000000") -> QIcon:
    """
    Returns a QIcon tinted with the specified hex color.
    Expects SVG file with stroke='currentColor' or fill='currentColor'.
    """
    if not os.path.exists(path):
        return QIcon()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            svg_data = f.read()
        
        # Replace currentColor with hex color
        svg_data = svg_data.replace('currentColor', color)
        
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
        if not renderer.isValid():
            return QIcon(path)
            
        # Create a high-res pixmap (128x128) for the icon to ensure crisp scaling
        pixmap = QPixmap(128, 128)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)
    except Exception:
        return QIcon(path)


# ──────────────────────────────────────────────────────────────────────────────
#  Enter-key navigation
# ──────────────────────────────────────────────────────────────────────────────

class _KeyboardNavFilter(QObject):
    """
    Event filter for smart keyboard navigation:
    - Enter/Return: Focus next available widget or accept dialog.
    - Backspace: Focus previous available widget if current widget is 'blank'.
    """

    def __init__(self, widgets, index, accept_fn):
        super().__init__()
        self._widgets = widgets
        self._index = index
        self._accept = accept_fn

    def _get_next(self):
        """Find the next visible and enabled widget in the sequence."""
        for i in range(self._index + 1, len(self._widgets)):
            w = self._widgets[i]
            if w.isVisible() and w.isEnabled():
                return w
        return None

    def _get_prev(self):
        """Find the previous visible and enabled widget in the sequence."""
        for i in range(self._index - 1, -1, -1):
            w = self._widgets[i]
            if w.isVisible() and w.isEnabled():
                return w
        return None

    def _should_go_back(self, w):
        if isinstance(w, QLineEdit):
            return w.cursorPosition() == 0
        if isinstance(w, (QComboBox, SearchableComboBox)):
            if hasattr(w, "view") and w.view().isVisible():
                return False
            if isinstance(w, SearchableComboBox) and w._popup and w._popup.isVisible():
                return False
            return True
        if isinstance(w, (QSpinBox, QDoubleSpinBox, QDateEdit)):
            return True
        return False

    def _focus_and_select(self, w):
        if not w:
            return
        w.setFocus()
        if isinstance(w, (QLineEdit, QSpinBox, QDoubleSpinBox)):
            w.selectAll()

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Type.KeyPress:
            return False

        key = event.key()
        
        # Forward navigation (Enter)
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            nxt = self._get_next()
            if nxt:
                self._focus_and_select(nxt)
            elif self._accept:
                self._accept()
            return True

        # Backward navigation (Backspace when blank/numeric/date)
        if key == Qt.Key.Key_Backspace:
            if self._should_go_back(obj):
                prv = self._get_prev()
                if prv:
                    self._focus_and_select(prv)
                    return True

        return False


def setup_enter_nav(dialog, widgets, accept_callback=None):
    """
    Wire Enter key navigation through *widgets* inside *dialog*.

    • QLineEdit        → uses the built-in returnPressed signal
    • SearchableComboBox / QComboBox / others → event filter
    • Last visible widget → calls accept_callback or dialog._accept() / dialog.accept()

    Call this after creating all widgets but before showing the dialog.
    """
    accept_fn = accept_callback or getattr(dialog, "_accept", None) or getattr(dialog, "accept", None)
    if not hasattr(dialog, "_enter_filters"):
        dialog._enter_filters = []

    # Remove previous filters if any to avoid duplicates
    for f_item in dialog._enter_filters:
        try:
            if isinstance(f_item, tuple):
                w, f = f_item
                w.removeEventFilter(f)
        except:
            pass
    dialog._enter_filters = []

    for i, w in enumerate(widgets):
        # Use event filter for ALL navigation to ensure consistency (Backspace + Enter)
        f = _KeyboardNavFilter(widgets, i, accept_fn)
        w.installEventFilter(f)
        dialog._enter_filters.append((w, f))

    # Automatically focus the first available widget when the dialog opens
    def _initial_focus():
        for w in widgets:
            if not w.isHidden() and w.isEnabled():
                w.setFocus()
                break
    QTimer.singleShot(0, _initial_focus)


# ──────────────────────────────────────────────────────────────────────────────
#  SearchableComboBox
# ──────────────────────────────────────────────────────────────────────────────

class _SearchPopup(QWidget):
    """
    Floating popup shown below the combo: a QLineEdit search box on top,
    and a filtered QListView below.
    """
    def __init__(self, combo: "SearchableComboBox"):
        super().__init__(combo.window(), Qt.WindowType.Popup |
                         Qt.WindowType.FramelessWindowHint)
        self._combo = combo
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(
            "QWidget { border: 1px solid #90caf9; border-radius: 4px; "
            "background: #ffffff; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.addAction(get_icon("frontend/assets/icons/search.svg", "#475569"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setStyleSheet(
            "QLineEdit { border: 1px solid #90caf9; border-radius: 3px; "
            "padding: 3px 6px; font-size: 12px; }"
        )
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)

        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(combo._model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(0)

        self.list_view = QListView()
        self.list_view.setModel(self.proxy)
        self.list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_view.setStyleSheet(
            "QListView { border: none; font-size: 13px; outline: none; }"
            "QListView::item { padding: 5px 8px; }"
            "QListView::item:selected { background: #1565C0; color: #fff; }"
            "QListView::item:hover    { background: #e3f2fd; }"
        )
        layout.addWidget(self.list_view)

        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.list_view.clicked.connect(self._on_clicked)
        self.search.returnPressed.connect(self._select_first_or_current)
        self.list_view.installEventFilter(self)
        self.search.installEventFilter(self)   # intercept Alt+V before QLineEdit eats it

        # pre-select current item
        self._highlight_current()

    # ------------------------------------------------------------------
    def _highlight_current(self):
        idx = self._combo.currentIndex()
        if idx >= 0:
            si = self._combo._model.index(idx, 0)
            pi = self.proxy.mapFromSource(si)
            if pi.isValid():
                self.list_view.setCurrentIndex(pi)
                self.list_view.scrollTo(pi)

    def _on_clicked(self, proxy_index):
        src_index = self.proxy.mapToSource(proxy_index)
        row = src_index.row()
        self._combo.setCurrentIndex(row)
        self._combo.activated.emit(row)
        self.hide()
        self._combo.setFocus()

    def _select_first_or_current(self):
        cur = self.list_view.currentIndex()
        if cur.isValid():
            self._on_clicked(cur)
        else:
            fi = self.proxy.index(0, 0)
            if fi.isValid():
                self._on_clicked(fi)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            # Alt+V from either the search box OR the list view → trigger edit
            if (key == Qt.Key.Key_V and
                    event.modifiers() & Qt.KeyboardModifier.AltModifier):
                self.hide()
                self._combo.setFocus()
                self._combo._trigger_edit()
                return True   # consume — do NOT let QLineEdit type 'v'
            if obj is self.list_view:
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._select_first_or_current()
                    return True
                if key == Qt.Key.Key_Escape:
                    self.hide()
                    self._combo.setFocus()
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.hide()
            self._combo.setFocus()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._select_first_or_current()
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            # forward arrow navigation to list
            self.list_view.setFocus()
        else:
            # forward other keys to search box
            self.search.setFocus()
            self.search.event(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.search.clear()
        self.proxy.setFilterFixedString("")
        self._highlight_current()
        QTimer.singleShot(0, self.search.setFocus)


class SearchableComboBox(QComboBox):
    """
    Drop-in replacement for QComboBox that shows a search box inside
    the popup when the user opens it (click or keyboard).

    API is intentionally compatible with QComboBox so existing code
    (addItem, addItems, currentText, currentIndex, currentData,
    setCurrentIndex, setCurrentText, findText, clear, currentIndexChanged,
    currentTextChanged) works unchanged.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # We manage our own model so the proxy can filter it
        self._model = QStandardItemModel(0, 1, self)
        self.setModel(self._model)
        self._popup: _SearchPopup | None = None
        # Prevent the native popup from showing
        self.setEditable(False)

    # ──────────── model helpers ────────────────────────────────────────

    def addItem(self, text, userData=None):          # noqa: N802
        item = QStandardItem(text)
        if userData is not None:
            item.setData(userData, Qt.ItemDataRole.UserRole)
        self._model.appendRow(item)

    def addItems(self, texts):                        # noqa: N802
        for t in texts:
            self.addItem(t)

    def insertItem(self, index, text, userData=None): # noqa: N802
        item = QStandardItem(text)
        if userData is not None:
            item.setData(userData, Qt.ItemDataRole.UserRole)
        self._model.insertRow(index, item)

    def clear(self):
        self._model.clear()

    def count(self):
        return self._model.rowCount()

    def itemText(self, index):                        # noqa: N802
        item = self._model.item(index, 0)
        return item.text() if item else ""

    def itemData(self, index, role=Qt.ItemDataRole.UserRole): # noqa: N802
        item = self._model.item(index, 0)
        return item.data(role) if item else None

    def currentText(self):                            # noqa: N802
        return self.itemText(self.currentIndex())

    def currentData(self, role=Qt.ItemDataRole.UserRole): # noqa: N802
        return self.itemData(self.currentIndex(), role)

    def setCurrentText(self, text):                   # noqa: N802
        idx = self.findText(text)
        if idx >= 0:
            self.setCurrentIndex(idx)

    def setCurrentData(self, data):                   # noqa: N802
        idx = self.findData(data)
        if idx >= 0:
            self.setCurrentIndex(idx)

    def findData(self, data, role=Qt.ItemDataRole.UserRole): # noqa: N802
        for i in range(self._model.rowCount()):
            item = self._model.item(i, 0)
            if item:
                # Comparison should be robust for string vs object ids
                val = item.data(role)
                if str(val) == str(data):
                    return i
        return -1

    def findText(self, text,                          # noqa: N802
                 flags=Qt.MatchFlag.MatchFixedString | Qt.MatchFlag.MatchCaseSensitive):
        for i in range(self._model.rowCount()):
            item = self._model.item(i, 0)
            if item and item.text() == text:
                return i
        return -1

    # ──────────── popup handling ───────────────────────────────────────

    def showPopup(self):                              # noqa: N802
        if self._popup is None:
            self._popup = _SearchPopup(self)

        # position popup directly below the combo
        pos = self.mapToGlobal(QPoint(0, self.height()))
        width = max(self.width(), 260)
        height = min(300, 44 + self._model.rowCount() * 28)
        self._popup.setFixedWidth(width)
        self._popup.setFixedHeight(height)
        self._popup.move(pos)
        self._popup.show()
        self._popup.raise_()

    def hidePopup(self):                              # noqa: N802
        if self._popup:
            self._popup.hide()

    def mousePressEvent(self, event):                 # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if self._popup and self._popup.isVisible():
                self.hidePopup()
            else:
                self.showPopup()
        else:
            super().mousePressEvent(event)

    def _trigger_edit(self):                           # noqa: N802
        """Fire the registered edit callback (Alt+V handler)."""
        edit_fn = getattr(self, "_es_edit_fn", None)
        if not edit_fn:
            return
        idx = self.currentIndex()
        data = self.currentData()
        text = self.currentText()
        # Skip placeholder items (no data, or index 0 that looks like a placeholder)
        if data is None or not text:
            return
        result = edit_fn(data)
        if result:
            new_text, new_data = result
            item = self._model.item(idx, 0)
            if item:
                item.setText(new_text)
                if new_data is not None:
                    item.setData(new_data, Qt.ItemDataRole.UserRole)

    def keyPressEvent(self, event):                   # noqa: N802
        key = event.key()
        if (key == Qt.Key.Key_V and
                event.modifiers() & Qt.KeyboardModifier.AltModifier):
            self._trigger_edit()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter,
                     Qt.Key.Key_Space, Qt.Key.Key_Down):
            self.showPopup()
        elif key == Qt.Key.Key_Escape:
            if self._popup and self._popup.isVisible():
                self.hidePopup()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    # ──────────── size hint ────────────────────────────────────────────

    def sizeHint(self):                               # noqa: N802
        sh = super().sizeHint()
        return QSize(max(sh.width(), 160), sh.height())


# ──────────────────────────────────────────────────────────────────────────────
#  "Create New" sentinel helper
# ──────────────────────────────────────────────────────────────────────────────

CREATE_NEW_LABEL = "➕  Create New..."


def wire_edit_selected(combo: "SearchableComboBox", edit_fn):
    """
    Register an edit callback on *combo*.

    When the user presses **Alt+V** while the combo (or its popup) is focused
    and a real item is selected, *edit_fn(current_data)* is called.

    *edit_fn* must accept the current item's ``UserRole`` data and return
    ``(display_text, user_data)`` on success, or ``None`` on cancel.
    On success the item text/data is updated in-place inside the model.
    """
    combo._es_edit_fn = edit_fn


def wire_create_new(combo: "SearchableComboBox", open_fn):
    """
    Append a '➕ Create New...' sentinel item to *combo*.

    When the user selects it, *open_fn()* is called (with no arguments).
    *open_fn* must return ``(display_text, user_data)`` on success, or
    ``None`` on cancel.  On success the new item is inserted before the
    sentinel and auto-selected; on cancel the previous selection is restored.
    """
    combo.addItem(CREATE_NEW_LABEL)
    combo._cn_prev_index = max(combo.count() - 2, 0)

    def _on_changed(idx):
        if combo.itemText(idx) == CREATE_NEW_LABEL:
            prev = combo._cn_prev_index

            def _open():
                result = open_fn()
                if result:
                    text, data = result
                    pos = combo.count() - 1          # insert before sentinel
                    combo.insertItem(pos, text, data)
                    combo.setCurrentIndex(pos)
                else:
                    combo.setCurrentIndex(prev)

            QTimer.singleShot(0, _open)
        else:
            combo._cn_prev_index = idx

    combo.activated.connect(_on_changed)
    combo.currentIndexChanged.connect(lambda idx: setattr(combo, "_cn_prev_index", idx) if combo.itemText(idx) != CREATE_NEW_LABEL else None)


# ──────────────────────────────────────────────────────────────────────────────
#  State Dropdown helper
# ──────────────────────────────────────────────────────────────────────────────

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
]


def wire_state_combo(combo: "SearchableComboBox", initial_state=""):
    """Populate combo with Indian states and add 'Create New'."""
    combo.addItems(INDIAN_STATES)
    if initial_state:
        if initial_state not in INDIAN_STATES:
            combo.insertItem(0, initial_state)
        combo.setCurrentText(initial_state)

    def _create_state():
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(combo.window(), "New State", "Enter State Name:")
        if ok and name.strip():
            return (name.strip(), name.strip())
        return None

    wire_create_new(combo, _create_state)


# ──────────────────────────────────────────────────────────────────────────────
#  Custom Calendar Picker  — fully hand-built, modern flat design
#  Frameless card with drop-shadow, circular day cells, Today shortcut
# ──────────────────────────────────────────────────────────────────────────────

_MONTHS = ["", "January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]


class _CalendarDialog(QDialog):
    """Modern frameless modal date-picker."""

    # ── palette ────────────────────────────────────────────────────────
    _HDR_BG      = "#1565C0"
    _HDR_FG      = "#ffffff"
    _YEAR_FG     = "#90caf9"
    _NAV_HOVER   = "rgba(255,255,255,0.15)"
    _BODY_BG     = "#ffffff"
    _CARD_BDR    = "#dde3ea"
    _WKDAY_FG    = "#78909c"
    _WKEND_FG    = "#e53935"
    _DAY_FG      = "#37474f"
    _DAY_HOVER   = "#e8f0fe"
    _DAY_HOV_FG  = "#1565C0"
    _TODAY_FG    = "#1565C0"
    _TODAY_BDR   = "#1565C0"
    _SEL_BG      = "#1565C0"
    _SEL_FG      = "#ffffff"
    _SEL_HOVER   = "#0d47a1"
    _FOOT_BG     = "#f0f4f8"
    _OK_BG       = "#1565C0"
    _OK_FG       = "#ffffff"
    _OK_HOV      = "#0d47a1"
    _CAN_BG      = "#e0e7ef"
    _CAN_FG      = "#546e7a"
    _CAN_HOV     = "#cfd8dc"
    _TOD_BG      = "#e8f0fe"
    _TOD_FG      = "#1565C0"
    _TOD_HOV     = "#c5cae9"

    def __init__(self, date):
        super().__init__(None)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        # WA_TranslucentBackground removed — it is the root cause of
        # "QPainter::end: Painter ended with N saved states" on Windows.
        # Depth is now achieved via CSS border instead of drop-shadow.
        self.selected_date = date
        self._view_year  = date.year()
        self._view_month = date.month()
        self._day_btns   = []
        self._drag_pos   = None

        # ── master stylesheet ──────────────────────────────────────────
        # Every rule is explicit – qt_material cannot win a specificity fight
        self.setStyleSheet(f"""
            QDialog {{ background-color: {self._BODY_BG}; }}

            #card {{
                background-color: {self._BODY_BG};
                border: 1px solid {self._CARD_BDR};
                border-bottom: 3px solid #B0BEC5;
                border-right: 2px solid #B0BEC5;
                border-radius: 14px;
            }}
            #hdr {{
                background-color: {self._HDR_BG};
                border-top-left-radius: 13px;
                border-top-right-radius: 13px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                border: none;
            }}
            #body {{
                background-color: {self._BODY_BG};
                border: none;
            }}
            QFrame#sep {{
                background-color: #e0e0e0;
                border: none;
                max-height: 1px;
                min-height: 1px;
            }}
            #foot {{
                background-color: {self._FOOT_BG};
                border-top: 1px solid {self._CARD_BDR};
                border-bottom-left-radius: 13px;
                border-bottom-right-radius: 13px;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
            }}

            QLabel {{ background-color: transparent; border: none; padding: 0px; }}
            QPushButton {{ background-color: transparent; border: none; padding: 0px; }}
            QPushButton:disabled {{ background-color: transparent; color: transparent; border: none; }}

            QPushButton#nav_btn {{
                color: {self._HDR_FG};
                font-size: 18px;
                font-weight: bold;
                border-radius: 16px;
            }}
            QPushButton#nav_btn:hover {{
                background-color: {self._NAV_HOVER};
            }}
            QPushButton#close_btn {{
                color: rgba(255,255,255,0.65);
                font-size: 13px;
                border-radius: 10px;
            }}
            QPushButton#close_btn:hover {{
                background-color: rgba(255,255,255,0.18);
                color: {self._HDR_FG};
            }}
            QPushButton#today_btn {{
                background-color: {self._TOD_BG};
                color: {self._TOD_FG};
                font-size: 11px;
                font-weight: bold;
                border-radius: 6px;
                padding: 4px 12px;
            }}
            QPushButton#today_btn:hover {{ background-color: {self._TOD_HOV}; }}
            QPushButton#ok_btn {{
                background-color: {self._OK_BG};
                color: {self._OK_FG};
                font-size: 12px;
                font-weight: bold;
                border-radius: 6px;
                padding: 5px 22px;
            }}
            QPushButton#ok_btn:hover {{ background-color: {self._OK_HOV}; }}
            QPushButton#cancel_btn {{
                background-color: {self._CAN_BG};
                color: {self._CAN_FG};
                font-size: 12px;
                font-weight: bold;
                border-radius: 6px;
                padding: 5px 14px;
            }}
            QPushButton#cancel_btn:hover {{ background-color: {self._CAN_HOV}; }}
        """)

        # ── outer layout (padding for visual breathing room) ──────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        # ── card ───────────────────────────────────────────────────────
        card = QWidget(); card.setObjectName("card")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # No QGraphicsDropShadowEffect — border-bottom/right simulate depth
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(0, 0, 0, 0)
        card_lay.setSpacing(0)
        outer.addWidget(card)

        # ── header ─────────────────────────────────────────────────────
        hdr = QWidget(); hdr.setObjectName("hdr")
        hdr.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hdr_lay = QVBoxLayout(hdr)
        hdr_lay.setContentsMargins(14, 10, 14, 12)
        hdr_lay.setSpacing(4)

        # top micro-row: year label + close button
        top_row = QHBoxLayout(); top_row.setSpacing(0)
        self._year_lbl = QLabel(str(self._view_year))
        self._year_lbl.setStyleSheet(
            f"color:{self._YEAR_FG};font-size:11px;font-weight:bold;"
        )
        close_btn = QPushButton("\u2715"); close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        top_row.addWidget(self._year_lbl)
        top_row.addStretch()
        top_row.addWidget(close_btn)
        hdr_lay.addLayout(top_row)

        # nav row: ◀  Month  ▶
        nav_row = QHBoxLayout(); nav_row.setSpacing(4)
        self._prev_btn = QPushButton("\u276e"); self._prev_btn.setObjectName("nav_btn")
        self._prev_btn.setFixedSize(32, 32)
        self._prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_btn.clicked.connect(self._prev_month)

        self._next_btn = QPushButton("\u276f"); self._next_btn.setObjectName("nav_btn")
        self._next_btn.setFixedSize(32, 32)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.clicked.connect(self._next_month)

        self._title_lbl = QLabel()
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setStyleSheet(
            f"color:{self._HDR_FG};font-size:16px;font-weight:bold;"
        )
        nav_row.addWidget(self._prev_btn)
        nav_row.addWidget(self._title_lbl, 1)
        nav_row.addWidget(self._next_btn)
        hdr_lay.addLayout(nav_row)
        card_lay.addWidget(hdr)

        # ── body ───────────────────────────────────────────────────────
        body = QWidget(); body.setObjectName("body")
        body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(10, 8, 10, 6)
        body_lay.setSpacing(4)

        # weekday headers: M T W T F S S
        wk_row = QHBoxLayout(); wk_row.setSpacing(0)
        for i, d in enumerate(["M", "T", "W", "T", "F", "S", "S"]):
            lbl = QLabel(d)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedWidth(40)
            c = self._WKEND_FG if i >= 5 else self._WKDAY_FG
            lbl.setStyleSheet(f"color:{c};font-size:11px;font-weight:bold;")
            wk_row.addWidget(lbl)
        body_lay.addLayout(wk_row)

        sep = QFrame(); sep.setObjectName("sep")
        body_lay.addWidget(sep)

        # day grid container – cells rebuilt in _render
        self._grid_frame = QWidget(); self._grid_frame.setObjectName("body")
        self._grid_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._grid = QGridLayout(self._grid_frame)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(3)
        body_lay.addWidget(self._grid_frame)
        card_lay.addWidget(body, 1)

        # ── footer ─────────────────────────────────────────────────────
        foot = QWidget(); foot.setObjectName("foot")
        foot.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        foot_lay = QHBoxLayout(foot)
        foot_lay.setContentsMargins(10, 8, 10, 10)
        foot_lay.setSpacing(6)

        today_btn = QPushButton("Today"); today_btn.setObjectName("today_btn")
        today_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        today_btn.clicked.connect(self._go_today)

        cancel_btn = QPushButton("Cancel"); cancel_btn.setObjectName("cancel_btn")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("OK"); ok_btn.setObjectName("ok_btn")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)

        foot_lay.addWidget(today_btn)
        foot_lay.addStretch()
        foot_lay.addWidget(cancel_btn)
        foot_lay.addWidget(ok_btn)
        card_lay.addWidget(foot)

        self._render()

    # ── frameless window drag ───────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_pos and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(self.pos() + event.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ── navigation ─────────────────────────────────────────────────────
    def _prev_month(self):
        if self._view_month == 1:
            self._view_month = 12; self._view_year -= 1
        else:
            self._view_month -= 1
        self._render()

    def _next_month(self):
        if self._view_month == 12:
            self._view_month = 1; self._view_year += 1
        else:
            self._view_month += 1
        self._render()

    def _go_today(self):
        t = QDate.currentDate()
        self._view_year  = t.year()
        self._view_month = t.month()
        self.selected_date = t
        self._render()

    # ── grid renderer ──────────────────────────────────────────────────
    def _render(self):
        for btn in self._day_btns:
            self._grid.removeWidget(btn)
            btn.deleteLater()
        self._day_btns.clear()

        self._year_lbl.setText(str(self._view_year))
        self._title_lbl.setText(_MONTHS[self._view_month])

        import calendar
        today = QDate.currentDate()
        weeks = calendar.monthcalendar(self._view_year, self._view_month)

        for row, week in enumerate(weeks):
            for col, day in enumerate(week):
                btn = QPushButton("" if day == 0 else str(day))
                btn.setFixedSize(40, 36)
                btn.setEnabled(day != 0)
                btn.setCursor(
                    Qt.CursorShape.PointingHandCursor if day != 0
                    else Qt.CursorShape.ArrowCursor
                )

                is_today    = (day != 0
                               and today.year()  == self._view_year
                               and today.month() == self._view_month
                               and today.day()   == day)
                is_selected = (day != 0
                               and self.selected_date.year()  == self._view_year
                               and self.selected_date.month() == self._view_month
                               and self.selected_date.day()   == day)
                is_weekend  = col >= 5

                if is_selected and is_today:
                    # filled circle + white ring inside
                    css = (f"QPushButton{{background-color:{self._SEL_BG};"
                           f"color:{self._SEL_FG};border:2px solid #90caf9;"
                           f"border-radius:18px;font-size:12px;font-weight:bold;}}"
                           f"QPushButton:hover{{background-color:{self._SEL_HOVER};}}")
                elif is_selected:
                    css = (f"QPushButton{{background-color:{self._SEL_BG};"
                           f"color:{self._SEL_FG};border:none;"
                           f"border-radius:18px;font-size:12px;font-weight:bold;}}"
                           f"QPushButton:hover{{background-color:{self._SEL_HOVER};}}")
                elif is_today:
                    css = (f"QPushButton{{background-color:transparent;"
                           f"color:{self._TODAY_FG};"
                           f"border:2px solid {self._TODAY_BDR};"
                           f"border-radius:18px;font-size:12px;font-weight:bold;}}"
                           f"QPushButton:hover{{background-color:{self._DAY_HOVER};}}")
                elif day == 0:
                    css = "QPushButton{background-color:transparent;color:transparent;border:none;}"
                elif is_weekend:
                    css = (f"QPushButton{{background-color:transparent;"
                           f"color:{self._WKEND_FG};"
                           f"border:none;border-radius:18px;font-size:12px;}}"
                           f"QPushButton:hover{{background-color:{self._DAY_HOVER};"
                           f"color:{self._WKEND_FG};}}")
                else:
                    css = (f"QPushButton{{background-color:transparent;"
                           f"color:{self._DAY_FG};"
                           f"border:none;border-radius:18px;font-size:12px;}}"
                           f"QPushButton:hover{{background-color:{self._DAY_HOVER};"
                           f"color:{self._DAY_HOV_FG};}}")

                btn.setStyleSheet(css)

                if day != 0:
                    btn.clicked.connect(lambda _=False, d=day: self._pick(d))

                self._grid.addWidget(btn, row, col)
                self._day_btns.append(btn)

    def _pick(self, day):
        self.selected_date = QDate(self._view_year, self._view_month, day)
        self._render()


class DateEdit(QDateEdit):
    """Drop-in for QDateEdit — opens the custom calendar picker."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCalendarPopup(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Try to tint the calendar icon if the internal button is found
        # (This is often a QToolButton with no text)
        self._tint_timer = QTimer(self)
        self._tint_timer.setSingleShot(True)
        self._tint_timer.timeout.connect(self._apply_icon)
        self._tint_timer.start(0)

    def _apply_icon(self):
        from PySide6.QtWidgets import QToolButton
        btn = self.findChild(QToolButton)
        if btn:
            # We don't have THEME here, but we can assume white for our blue headers
            # or just use a standard dark color. 
            # Actually, most our DateEdits are in the blue header (Voucher, Reports).
            # I'll use white.
            btn.setIcon(get_icon("frontend/assets/icons/calendar.svg", "#ffffff"))
            btn.setIconSize(QSize(16, 16))
            btn.setStyleSheet("border: none; background: transparent;")

    def showPopup(self):          # noqa: N802
        dlg = _CalendarDialog(self.date())
        if dlg.exec():
            self.setDate(dlg.selected_date)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.showPopup()
        else:
            super().mousePressEvent(event)
