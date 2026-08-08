from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QDoubleSpinBox, QDialogButtonBox,
    QMessageBox, QHeaderView
)
from PySide6.QtCore import Qt, QSize, QEvent
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMessageBox as MessageBox
import frontend.api_client as api
from frontend.utils import setup_enter_nav, SearchableComboBox, wire_create_new, wire_edit_selected, get_icon, wire_state_combo, format_indian_number
from frontend.components.cards import PillActionButton, IconActionButton
import frontend.session as session



# ─────────────────────────────────────────────────────────────────────────────
#  Quick Group creation dialog (used inline from LedgerDialog)
# ─────────────────────────────────────────────────────────────────────────────
class _QuickGroupDialog(QDialog):
    """Minimal dialog to create a new ledger group on-the-fly."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Group")
        self.setMinimumWidth(340)
        form = QFormLayout(self)
        self.name_edit = QLineEdit()
        self.nature_cb = SearchableComboBox()
        self.nature_cb.addItem("Select Nature", None)
        self.nature_cb.addItems(["Asset", "Liability", "Income", "Expense"])
        form.addRow("Group Name *:", self.name_edit)
        form.addRow("Nature *:", self.nature_cb)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)
        setup_enter_nav(self, [self.name_edit, self.nature_cb])

    def _accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Error", "Group name is required")
            return
        self.accept()

    def get_data(self):
        nature = self.nature_cb.currentText()
        if nature.startswith("Select"): nature = ""
        return {"name": self.name_edit.text().strip(),
                "nature": nature}


class LedgerDialog(QDialog):
    def __init__(self, parent=None, groups=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Ledger")
        self.setMinimumWidth(420)
        self.data = data or {}
        groups = groups or []
        self._groups = {g["_id"]: g for g in groups}   # id → group dict
        form = QFormLayout(self)

        self.name = QLineEdit(self.data.get("name", ""))
        self.group_cb = SearchableComboBox()
        self.group_cb.addItem("Select Group", None)
        for g in groups:
            self.group_cb.addItem(g["name"], g["_id"])
        if self.data.get("group"):
            # data["group"] is a string _id — match by item data
            for i in range(self.group_cb.count()):
                if str(self.group_cb.itemData(i)) == str(self.data["group"]):
                    self.group_cb.setCurrentIndex(i)
                    break

        # "Create New Group" option
        def _create_group():
            dlg = _QuickGroupDialog(self)
            if dlg.exec():
                d = dlg.get_data()
                try:
                    resp = api.create_group(d)
                    new_id = resp.get("id", "")
                    return (d["name"], new_id)
                except Exception as ex:
                    QMessageBox.warning(self, "Error", str(ex))
            return None
        wire_create_new(self.group_cb, _create_group)

        def _edit_group(group_id):
            """Ctrl+Enter: edit the currently selected group."""
            try:
                all_groups = api.list_groups()
            except Exception:
                all_groups = []
            group = next((g for g in all_groups if str(g["_id"]) == str(group_id)), None)
            if not group:
                return None
            dlg = _QuickGroupDialog(self)
            dlg.setWindowTitle("Edit Group")
            dlg.name_edit.setText(group.get("name", ""))
            nature = group.get("nature", "Asset")
            idx = dlg.nature_cb.findText(nature)
            if idx >= 0:
                dlg.nature_cb.setCurrentIndex(idx)
            if dlg.exec():
                data = dlg.get_data()
                try:
                    api.update_group(group_id, data)
                    return (data["name"], group_id)
                except Exception as ex:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(self, "Error", str(ex))
            return None
        wire_edit_selected(self.group_cb, _edit_group)

        self.opening = QDoubleSpinBox()
        self.opening.setRange(-99999999, 99999999)
        self.opening.setDecimals(2)
        self.opening.setValue(self.data.get("opening_balance", 0.0))

        self.btype_cb = SearchableComboBox()
        self.btype_cb.addItem("Select Balance Type", None)
        self.btype_cb.addItems(["Dr", "Cr"])
        if self.data.get("balance_type") == "Cr":
            self.btype_cb.setCurrentIndex(2)
        elif self.data.get("balance_type") == "Dr":
            self.btype_cb.setCurrentIndex(1)

        # ── Tax Rate (visible only for Duties & Taxes group) ──────────────────
        self._tax_label = QLabel("Tax Rate %")
        self.tax_rate = QDoubleSpinBox()
        self.tax_rate.setRange(0, 100)
        self.tax_rate.setDecimals(2)
        self.tax_rate.setSuffix(" %")
        self.tax_rate.setValue(self.data.get("tax_rate", 0.0))
        self.tax_rate.setToolTip(
            "Applied automatically when this ledger is used in a voucher's "
            "Tax/Adjustment row (Amount = Sub-Total × Tax Rate / 100)"
        )

        self.phone = QLineEdit(self.data.get("phone", ""))
        self.email = QLineEdit(self.data.get("email", ""))
        self.address = QLineEdit(self.data.get("address", ""))
        self.state   = SearchableComboBox()
        self.state.addItem("Select State", None)
        wire_state_combo(self.state, self.data.get("state", ""))
        self.gst_no = QLineEdit(self.data.get("gst_no", ""))

        self.transporter_cb = SearchableComboBox()
        self.transporter_cb.addItem("Select Transporter", None)
        try:
            transports = api.list_transports()
        except Exception:
            transports = []
        for t in transports:
            self.transporter_cb.addItem(t["name"], t["_id"])
        if self.data.get("transporter"):
            for i in range(self.transporter_cb.count()):
                if str(self.transporter_cb.itemData(i)) == str(self.data["transporter"]):
                    self.transporter_cb.setCurrentIndex(i)
                    break

        def _create_transporter():
            from frontend.pages.transport import TransportDialog
            dlg = TransportDialog(self)
            if dlg.exec():
                d = dlg.get_data()
                try:
                    resp = api.create_transporter(d)
                    new_id = resp.get("id", "")
                    transports.append({**d, "_id": new_id})
                    return (d["name"], new_id)
                except Exception as ex:
                    QMessageBox.warning(self, "Error", str(ex))
            return None
        wire_create_new(self.transporter_cb, _create_transporter)

        def _edit_transporter(transporter_id):
            from frontend.pages.transport import TransportDialog
            t = next((x for x in transports if str(x["_id"]) == str(transporter_id)), None)
            if not t:
                return None
            dlg = TransportDialog(self, data=t)
            if dlg.exec():
                d = dlg.get_data()
                try:
                    api.update_transporter(transporter_id, d)
                    t.update(d)
                    return (d["name"], transporter_id)
                except Exception as ex:
                    QMessageBox.warning(self, "Error", str(ex))
            return None
        wire_edit_selected(self.transporter_cb, _edit_transporter)

        # ── Bank Details (visible only for Bank Accounts group) ───────────────
        self.bank_name = QLineEdit(self.data.get("bank_name", ""))
        self.acc_holder = QLineEdit(self.data.get("account_holder_name", ""))
        self.acc_no = QLineEdit(self.data.get("account_number", ""))
        self.ifsc = QLineEdit(self.data.get("ifsc_code", ""))
        self.branch = QLineEdit(self.data.get("branch_name", ""))
        self.acc_type = SearchableComboBox()
        self.acc_type.addItems(["Select Type", "Savings", "Current"])
        if self.data.get("account_type") in ["Savings", "Current"]:
            self.acc_type.setCurrentText(self.data["account_type"])

        # Set placeholders/tooltips
        self.acc_holder.setPlaceholderText("e.g. Jiske naam par account hai")
        self.bank_name.setPlaceholderText("e.g. State Bank of India, HDFC Bank")
        self.acc_no.setPlaceholderText("e.g. 1234567890")
        self.ifsc.setPlaceholderText("e.g. SBIN0001234")
        self.branch.setPlaceholderText("e.g. Kanpur Main Branch")

        form.addRow("Name *", self.name)
        form.addRow("Group *", self.group_cb)
        form.addRow("Opening Balance", self.opening)
        form.addRow("Balance Type", self.btype_cb)
        form.addRow(self._tax_label, self.tax_rate)
        form.addRow("Phone", self.phone)
        form.addRow("Email", self.email)
        form.addRow("Address", self.address)
        form.addRow("State", self.state)
        form.addRow("GST No", self.gst_no)
        form.addRow("Transporter", self.transporter_cb)
        
        # Bank rows
        form.addRow("Account Holder", self.acc_holder)
        form.addRow("Bank Name", self.bank_name)
        form.addRow("Account Number", self.acc_no)
        form.addRow("IFSC Code", self.ifsc)
        form.addRow("Branch Name", self.branch)
        form.addRow("Account Type", self.acc_type)

        setup_enter_nav(self, [
            self.name, self.group_cb, self.opening, self.btype_cb,
            self.tax_rate, self.phone, self.email, self.address, self.state, self.gst_no,
            self.transporter_cb,
            self.acc_holder, self.bank_name, self.acc_no, self.ifsc, self.branch, self.acc_type
        ])

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

        # Wire group change → show/hide Tax Rate row
        self.group_cb.currentIndexChanged.connect(self._on_group_changed)
        self._on_group_changed(self.group_cb.currentIndex())   # initial state

    # ── helpers ────────────────────────────────────────────────────────────────
    def _is_duties_and_taxes_group(self, group_id: str) -> bool:
        """Return True if group_id is 'Duties & Taxes' itself or a direct child."""
        g = self._groups.get(str(group_id))
        if not g:
            return False
        name   = g.get("name", "")
        parent = g.get("parent", "") or ""
        return name == "Duties & Taxes" or parent == "Duties & Taxes"

    def _is_party_group(self, group_id: str) -> bool:
        """Return True if group_id is 'Sundry Debtors' or 'Sundry Creditors'."""
        g = self._groups.get(str(group_id))
        if not g:
            return False
        name   = g.get("name", "")
        parent = g.get("parent", "") or ""
        targets = ["Sundry Debtors", "Sundry Creditors"]
        return name in targets or parent in targets

    def _is_bank_group(self, group_id: str) -> bool:
        """Return True if group_id is 'Bank Accounts' itself or a direct child."""
        g = self._groups.get(str(group_id))
        if not g:
            return False
        name   = g.get("name", "")
        parent = g.get("parent", "") or ""
        return name == "Bank Accounts" or parent == "Bank Accounts"

    def _on_group_changed(self, idx):
        group_id = self.group_cb.itemData(idx) if idx >= 0 else None
        
        # Tax Rate visibility
        dt_visible = bool(group_id and self._is_duties_and_taxes_group(str(group_id)))
        self._tax_label.setVisible(dt_visible)
        self.tax_rate.setVisible(dt_visible)
        if not dt_visible:
            self.tax_rate.setValue(0.0)

        # State and GST visibility
        party_visible = bool(group_id and self._is_party_group(str(group_id)))
        layout = self.layout()
        if isinstance(layout, QFormLayout):
            lbl_state = layout.labelForField(self.state)
            if lbl_state: lbl_state.setVisible(party_visible)
            
            lbl_gst = layout.labelForField(self.gst_no)
            if lbl_gst: lbl_gst.setVisible(party_visible)
            
            lbl_trans = layout.labelForField(self.transporter_cb)
            if lbl_trans: lbl_trans.setVisible(party_visible)
            
        self.state.setVisible(party_visible)
        self.gst_no.setVisible(party_visible)
        self.transporter_cb.setVisible(party_visible)

        if not party_visible:
            self.state.setCurrentIndex(0)
            self.gst_no.clear()
            self.transporter_cb.setCurrentIndex(0)

        # Bank visibility
        bank_visible = bool(group_id and self._is_bank_group(str(group_id)))
        bank_widgets = [self.acc_holder, self.bank_name, self.acc_no, self.ifsc, self.branch, self.acc_type]
        for w in bank_widgets:
            w.setVisible(bank_visible)
            label = layout.labelForField(w)
            if label: label.setVisible(bank_visible)
        
        if not bank_visible:
            for w in bank_widgets:
                if isinstance(w, QLineEdit): w.clear()
                elif isinstance(w, SearchableComboBox): w.setCurrentIndex(0)

    def _accept(self):
        if not self.name.text().strip():
            MessageBox.warning(self, "Error", "Ledger name is required"); return
        if not self.group_cb.currentData():
            MessageBox.warning(self, "Error", "Group is required"); return
        reply = MessageBox.question(
            self, "Confirm Save",
            f"Save ledger '{self.name.text().strip()}'?",
            MessageBox.StandardButton.Yes | MessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.accept()

    def get_data(self):
        def _val(cb):
            t = cb.currentText()
            return "" if t.startswith("Select ") else t

        group_id = self.group_cb.currentData()
        return {
            "name": self.name.text().strip(),
            "group": str(group_id) if group_id else "",
            "opening_balance": self.opening.value(),
            "balance_type": _val(self.btype_cb),
            "tax_rate": self.tax_rate.value(),
            "phone": self.phone.text().strip(),
            "email": self.email.text().strip(),
            "address": self.address.text().strip(),
            "state": _val(self.state),
            "gst_no": self.gst_no.text().strip(),
            "transporter": str(transporter_id) if (transporter_id := self.transporter_cb.currentData()) else "",
            "bank_name": self.bank_name.text().strip(),
            "account_holder_name": self.acc_holder.text().strip(),
            "account_number": self.acc_no.text().strip(),
            "ifsc_code": self.ifsc.text().strip(),
            "branch_name": self.branch.text().strip(),
            "account_type": _val(self.acc_type),
        }


class LedgerPage(QWidget):
    def __init__(self):
        super().__init__()
        self._groups = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("Ledgers")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1565C0;")
        add_btn = QPushButton("  Create Ledger  [Alt+A]")
        add_btn.setIcon(get_icon("frontend/assets/icons/plus.svg", "#ffffff"))
        add_btn.setIconSize(QSize(16, 16))
        add_btn.setFixedHeight(36)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setShortcut("Alt+A")
        add_btn.setToolTip("Create Ledger  (Alt+A)")
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
        self.search.setPlaceholderText("Search ledger...")
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Name", "Group", "Opening Balance", "Balance Type", "Tax %", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().resizeSection(5, 180)
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
                if 0 <= row < len(self._ledgers):
                    self._edit(self._ledgers[row])
                    return True
        return super().eventFilter(obj, event)

    def _load(self):
        try:
            self._groups = api.list_groups()
            self._ledgers = api.list_ledgers()
        except Exception as ex:
            QMessageBox.warning(self, "Error", str(ex))
            return
        self._display(self._ledgers)

    def _display(self, ledgers):
        # build id→name lookup
        grp_name = {g["_id"]: g["name"] for g in self._groups}
        # build id→group dict for parent lookup
        grp_map  = {g["_id"]: g for g in self._groups}

        def _is_duties(group_id):
            g = grp_map.get(group_id, {})
            name   = g.get("name", "")
            parent = g.get("parent", "") or ""
            return name == "Duties & Taxes" or parent == "Duties & Taxes"

        # Block signals to prevent sorting while populating
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for row, l in enumerate(ledgers):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(l.get("name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(grp_name.get(l.get("group", ""), l.get("group", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(format_indian_number(l.get('opening_balance', 0))))
            self.table.setItem(row, 3, QTableWidgetItem(l.get("balance_type", "Dr")))

            # Tax % column — only show for Duties & Taxes ledgers
            tax_rate = l.get("tax_rate", 0.0) or 0.0
            if _is_duties(l.get("group", "")) and tax_rate > 0:
                tax_text = f"{tax_rate:.2f} %"
            else:
                tax_text = "—"
            tax_item = QTableWidgetItem(tax_text)
            tax_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, tax_item)

            # ── Action cell ──────────────────────────────────────────────
            cell = QWidget()
            cell_lay = QHBoxLayout(cell)
            cell_lay.setContentsMargins(6, 0, 6, 0)
            cell_lay.setSpacing(6)

            edit_btn = IconActionButton("frontend/assets/icons/edit.svg", "Edit ledger", variant="edit")
            del_btn  = IconActionButton("frontend/assets/icons/trash.svg", "Delete ledger", variant="danger")

            edit_btn.clicked.connect(lambda *a, ld=l: self._edit(ld))
            del_btn.clicked.connect(lambda *a, lid=l["_id"]: self._delete(lid))

            cell_lay.addWidget(edit_btn)
            cell_lay.addWidget(del_btn)
            cell_lay.addStretch()
            self.table.setCellWidget(row, 5, cell)

        self.table.setSortingEnabled(True)
        if self.table.rowCount() > 0:
            self.table.setCurrentCell(0, 0)
            self.table.setFocus()

    def _filter(self, text):
        if not hasattr(self, "_ledgers"):
            return
        filtered = [l for l in self._ledgers if text.lower() in l.get("name", "").lower()]
        self._display(filtered)

    def _add(self):
        if not session.has_permission("ledger", "edit"):
            QMessageBox.warning(self, "Permission Denied", "You do not have permission to create Ledgers.")
            return
        dlg = LedgerDialog(self, self._groups)
        if dlg.exec():
            data = dlg.get_data()
            if not data["name"] or not data["group"]:
                QMessageBox.warning(self, "Error", "Name and Group required")
                return
            try:
                api.create_ledger(data)
                self._load()
            except Exception as ex:
                QMessageBox.warning(self, "Error", str(ex))

    def _edit(self, ledger: dict):
        if not session.has_permission("ledger", "update"):
            QMessageBox.warning(self, "Permission Denied", "You do not have permission to edit Ledgers.")
            return
        dlg = LedgerDialog(self, self._groups, data=ledger)
        if dlg.exec():
            data = dlg.get_data()
            if not data["name"] or not data["group"]:
                QMessageBox.warning(self, "Error", "Name and Group required")
                return
            try:
                api.update_ledger(ledger["_id"], data)
                self._load()
            except Exception as ex:
                QMessageBox.warning(self, "Error", str(ex))

    def _delete(self, lid):
        if not session.has_permission("ledger", "delete"):
            QMessageBox.warning(self, "Permission Denied", "You do not have permission to delete Ledgers.")
            return
        reply = MessageBox.question(self, "Confirm", "Delete this ledger?")
        if reply == QMessageBox.StandardButton.Yes:
            try:
                api.delete_ledger(lid)
                self._load()
            except Exception as ex:
                QMessageBox.warning(self, "Error", str(ex))
