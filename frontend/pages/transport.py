from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QDialogButtonBox, QMessageBox, QHeaderView
)
from PySide6.QtCore import Qt, QSize, QEvent
import frontend.api_client as api
from frontend.utils import setup_enter_nav, get_icon
from frontend.components.cards import IconActionButton
import frontend.session as session


class TransportDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Transporter")
        self.setMinimumWidth(380)
        self.data = data or {}
        form = QFormLayout(self)

        self.name = QLineEdit(self.data.get("name", ""))
        self.gst_no = QLineEdit(self.data.get("gst_no", ""))
        self.address = QLineEdit(self.data.get("address", ""))

        self.name.setPlaceholderText("e.g. Safe Express, DTDC")
        self.gst_no.setPlaceholderText("GSTIN (Optional)")
        self.address.setPlaceholderText("Address (Optional)")

        form.addRow("Transporter Name *", self.name)
        form.addRow("GSTNo", self.gst_no)
        form.addRow("Address", self.address)

        setup_enter_nav(self, [self.name, self.gst_no, self.address])

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def _accept(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, "Error", "Transporter name is required")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Save",
            f"Save transporter '{self.name.text().strip()}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.accept()

    def get_data(self):
        return {
            "name": self.name.text().strip(),
            "gst_no": self.gst_no.text().strip(),
            "address": self.address.text().strip(),
        }


class TransportPage(QWidget):
    def __init__(self):
        super().__init__()
        self._transporters = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("Transporters")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1565C0;")
        
        add_btn = QPushButton("  Create Transporter  [Alt+A]")
        add_btn.setIcon(get_icon("frontend/assets/icons/plus.svg", "#ffffff"))
        add_btn.setIconSize(QSize(16, 16))
        add_btn.setFixedHeight(36)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setShortcut("Alt+A")
        add_btn.setToolTip("Create Transporter (Alt+A)")
        add_btn.setStyleSheet("""
            QPushButton {
                background: #1565C0; color: #fff;
                border: none; border-radius: 8px;
                font-size: 13px; font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover  { background: #1976D2; }
            QPushButton:pressed { background: #0D47A1; }
        """)
        add_btn.clicked.connect(self._add)
        
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(add_btn)
        layout.addLayout(hdr)

        # Search
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search transporter by name or GSTNo...")
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Transporter Name", "GSTNo", "Address", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().resizeSection(3, 120)
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.installEventFilter(self)
        layout.addWidget(self.table)

        self._load()

    def showEvent(self, e):
        self._load()
        super().showEvent(e)
        self.table.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.table and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                row = self.table.currentRow()
                if 0 <= row < len(self._transporters):
                    self._edit(self._transporters[row])
                    return True
        return super().eventFilter(obj, event)

    def _load(self):
        try:
            self._transporters = api.list_transports()
        except Exception as ex:
            QMessageBox.warning(self, "Error", str(ex))
            return
        self._display(self._transporters)

    def _display(self, transporters):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for row, t in enumerate(transporters):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(t.get("name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(t.get("gst_no", "")))
            self.table.setItem(row, 2, QTableWidgetItem(t.get("address", "")))

            # Actions
            cell = QWidget()
            cell_lay = QHBoxLayout(cell)
            cell_lay.setContentsMargins(6, 0, 6, 0)
            cell_lay.setSpacing(6)

            edit_btn = IconActionButton("frontend/assets/icons/edit.svg", "Edit transporter", variant="edit")
            del_btn  = IconActionButton("frontend/assets/icons/trash.svg", "Delete transporter", variant="danger")

            edit_btn.clicked.connect(lambda *a, tr=t: self._edit(tr))
            del_btn.clicked.connect(lambda *a, tid=t["_id"]: self._delete(tid))

            cell_lay.addWidget(edit_btn)
            cell_lay.addWidget(del_btn)
            cell_lay.addStretch()
            self.table.setCellWidget(row, 3, cell)

        self.table.setSortingEnabled(True)
        if self.table.rowCount() > 0:
            self.table.setCurrentCell(0, 0)
            self.table.setFocus()

    def _filter(self, text):
        if not hasattr(self, "_transporters"):
            return
        filtered = []
        for t in self._transporters:
            name = t.get("name", "").lower()
            gst = t.get("gst_no", "").lower()
            if text.lower() in name or text.lower() in gst:
                filtered.append(t)
        self._display(filtered)

    def _add(self):
        if not session.has_permission("ledger", "edit"):
            QMessageBox.warning(self, "Permission Denied", "You do not have permission to create transporters.")
            return
        dlg = TransportDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                api.create_transporter(data)
                self._load()
            except Exception as ex:
                QMessageBox.warning(self, "Error", str(ex))

    def _edit(self, transporter: dict):
        if not session.has_permission("ledger", "update"):
            QMessageBox.warning(self, "Permission Denied", "You do not have permission to update transporters.")
            return
        dlg = TransportDialog(self, data=transporter)
        if dlg.exec():
            data = dlg.get_data()
            try:
                api.update_transporter(transporter["_id"], data)
                self._load()
            except Exception as ex:
                QMessageBox.warning(self, "Error", str(ex))

    def _delete(self, tid):
        if not session.has_permission("ledger", "delete"):
            QMessageBox.warning(self, "Permission Denied", "You do not have permission to delete transporters.")
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Are you sure you want to delete this transporter?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                api.delete_transporter(tid)
                self._load()
            except Exception as ex:
                QMessageBox.warning(self, "Error", str(ex))
