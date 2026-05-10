from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QDoubleSpinBox, QDialogButtonBox,
    QMessageBox, QHeaderView, QScrollArea, QFrame, QTextEdit,
    QGridLayout, QSizePolicy, QCheckBox
)
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt, QDate, QSize, Signal, QTimer, QEvent, QObject
import frontend.api_client as api
from frontend.utils import setup_enter_nav, SearchableComboBox, wire_create_new, wire_edit_selected, DateEdit, get_icon, format_indian_number, format_inr

INVOICE_TYPES = {"Sales", "Purchase", "Credit Note", "Debit Note"}
JOURNAL_TYPES = {"Payment", "Receipt", "Journal", "Contra"}


# ─────────────────────────────────────────────────────────────────────────────
#  Invoice Item Row (Sales / Purchase)
# ─────────────────────────────────────────────────────────────────────────────
class InvoiceItemRow(QWidget):
    def __init__(self, items, units, parent=None):
        super().__init__(parent)
        self._items = items
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        self.item_cb = SearchableComboBox()
        self.item_cb.setMinimumWidth(200)
        self.item_cb.addItem("-- Select Item --", None)
        for it in items:
            self.item_cb.addItem(it["name"], it)
        self.item_cb.currentIndexChanged.connect(self._on_item_changed)

        # "Create New Item" option
        def _create_item():
            from frontend.pages.inventory import StockItemDialog
            dlg = StockItemDialog(self.window())
            if dlg.exec():
                data = dlg.get_data()
                try:
                    resp = api.create_stock_item(data)
                    new_item = {**data, "_id": resp.get("id", "")}
                    self._items.append(new_item)
                    return (data["name"], new_item)
                except Exception as ex:
                    QMessageBox.warning(self.window(), "Error", str(ex))
            return None
        wire_create_new(self.item_cb, _create_item)

        def _edit_item_row(item_data):
            from frontend.pages.inventory import StockItemDialog
            # Fetch full item record to ensure all fields are present
            try:
                full_item = api.get_stock_item(item_data["_id"])
            except Exception:
                full_item = item_data
            dlg = StockItemDialog(self.window(), full_item)
            if dlg.exec():
                data = dlg.get_data()
                try:
                    api.update_stock_item(item_data["_id"], data)
                    updated = {**item_data, **data}
                    for i, it in enumerate(self._items):
                        if it["_id"] == item_data["_id"]:
                            self._items[i] = updated
                            break
                    return (data["name"], updated)
                except Exception as ex:
                    QMessageBox.warning(self.window(), "Error", str(ex))
            return None
        wire_edit_selected(self.item_cb, _edit_item_row)

        self.qty = QDoubleSpinBox()
        self.qty.setRange(0, 9999999)
        self.qty.setDecimals(3)
        self.qty.setFixedWidth(90)
        self.qty.valueChanged.connect(self._calc)

        self.unit = SearchableComboBox()
        self.unit.addItem("Select Unit", None)
        for u in units:
            self.unit.addItem(u["name"], str(u["_id"]))
        self.unit.setFixedWidth(70)

        def _create_unit_row():
            from PySide6.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(
                self.window(), "New Unit", "Unit Name (e.g. NOS, KG):")
            if ok and name.strip():
                uname = name.strip().upper()
                try:
                    api.create_unit({"name": uname})
                    return (uname, uname)
                except Exception as ex:
                    QMessageBox.warning(self.window(), "Error", str(ex))
            return None
        wire_create_new(self.unit, _create_unit_row)

        self.rate = QDoubleSpinBox()
        self.rate.setRange(0, 9999999)
        self.rate.setDecimals(2)
        self.rate.setFixedWidth(100)
        self.rate.valueChanged.connect(self._calc)

        self.amount = QLineEdit("0.00")
        self.amount.setReadOnly(True)
        self.amount.setFixedWidth(110)
        self.amount.setStyleSheet("background: #e3f2fd; color: #1565C0; font-weight: bold;")

        self.gst_rate = QDoubleSpinBox()
        self.gst_rate.setRange(0, 28)
        self.gst_rate.setDecimals(2)
        self.gst_rate.setVisible(False)  # Hidden as requested
        self.gst_rate.valueChanged.connect(self._calc)

        layout.addWidget(self.item_cb, 2)
        layout.addWidget(QLabel("Qty:"))
        layout.addWidget(self.qty)
        layout.addWidget(self.unit)
        layout.addWidget(QLabel("Rate:"))
        layout.addWidget(self.rate)
        layout.addWidget(QLabel("Amt:"))
        layout.addWidget(self.amount)

        # Enter navigates: item → qty → unit → rate → next row
        setup_enter_nav(self, [self.item_cb, self.qty, self.unit, self.rate])

    def _on_item_changed(self, idx):
        self._current_item = None
        if idx > 0:
            item = self.item_cb.currentData()
            if isinstance(item, dict):
                self._current_item = item
                self.gst_rate.setValue(item.get("gst_rate", 0))
                self.rate.setValue(item.get("price", 0))
                self.unit.setCurrentData(str(item.get("unit", "")))
        self._calc()

    changed = Signal()

    def _calc(self):
        amt = self.qty.value() * self.rate.value()
        self.amount.setText(format_indian_number(amt))
        self.changed.emit()

    def get_data(self):
        item = self.item_cb.currentData()
        unit_id = self.unit.currentData()
        if not item or self.qty.value() == 0 or not unit_id:
            return None
        
        qty  = self.qty.value()
        rate = self.rate.value()
        amt  = round(qty * rate, 2)
        
        # Get specific tax percentages from the item record (which we added to Item master)
        cgst_p = item.get("cgst", 0)
        sgst_p = item.get("sgst", 0)
        igst_p = item.get("igst", 0)
        
        # Fallback: if item only has the total gst_rate field, split it 50/50
        if cgst_p == 0 and sgst_p == 0 and item.get("gst_rate", 0) > 0:
            cgst_p = sgst_p = item["gst_rate"] / 2
            igst_p = item["gst_rate"]
        
        return {
            "item_id":   item["_id"],
            "item_name": item["name"],
            "unit":      unit_id,
            "qty":       qty,
            "rate":      rate,
            "amount":    amt,
            "gst_rate":  item.get("gst_rate", 0),
            "cgst_p":    cgst_p,
            "sgst_p":    sgst_p,
            "igst_p":    igst_p,
            "cgst":      round(amt * cgst_p / 100, 2),
            "sgst":      round(amt * sgst_p / 100, 2),
            "igst":      round(amt * igst_p / 100, 2),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Item Entry Dialog  (modal for adding / editing a single invoice item line)
# ─────────────────────────────────────────────────────────────────────────────
class ItemEntryDialog(QDialog):
    def __init__(self, parent, items, units, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Item" if existing else "Add Item")
        self.setMinimumWidth(460)
        self._items = items
        form = QFormLayout(self)

        self.item_cb = SearchableComboBox()
        self.item_cb.addItem("-- Select Item --", None)
        for it in items:
            self.item_cb.addItem(it["name"], it)
        self.item_cb.currentIndexChanged.connect(self._on_item_changed)

        def _create_item():
            from frontend.pages.inventory import StockItemDialog
            dlg = StockItemDialog(self)
            if dlg.exec():
                data = dlg.get_data()
                try:
                    resp = api.create_stock_item(data)
                    new_item = {**data, "_id": resp.get("id", "")}
                    self._items.append(new_item)
                    return (data["name"], new_item)
                except Exception as ex:
                    QMessageBox.warning(self, "Error", str(ex))
            return None
        wire_create_new(self.item_cb, _create_item)

        def _edit_item_dlg(item_data):
            from frontend.pages.inventory import StockItemDialog
            # Fetch full item record to ensure all fields are present
            try:
                full_item = api.get_stock_item(item_data["_id"])
            except Exception:
                full_item = item_data
            dlg = StockItemDialog(self, full_item)
            if dlg.exec():
                data = dlg.get_data()
                try:
                    api.update_stock_item(item_data["_id"], data)
                    updated = {**item_data, **data}
                    for i, it in enumerate(self._items):
                        if it["_id"] == item_data["_id"]:
                            self._items[i] = updated
                            break
                    return (data["name"], updated)
                except Exception as ex:
                    QMessageBox.warning(self, "Error", str(ex))
            return None
        wire_edit_selected(self.item_cb, _edit_item_dlg)

        self.qty = QDoubleSpinBox()
        self.qty.setRange(0.001, 9999999); self.qty.setDecimals(3)
        self.qty.setValue(1.0)
        self.qty.valueChanged.connect(self._calc)

        self.unit_cb = SearchableComboBox()
        self.unit_cb.addItem("Select Unit", None)
        for u in units:
            self.unit_cb.addItem(u["name"], str(u["_id"]))

        def _create_unit_dlg():
            from PySide6.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(
                self.window(), "New Unit", "Unit Name (e.g. NOS, KG):")
            if ok and name.strip():
                uname = name.strip().upper()
                try:
                    api.create_unit({"name": uname})
                    return (uname, uname)
                except Exception as ex:
                    QMessageBox.warning(self.window(), "Error", str(ex))
            return None
        wire_create_new(self.unit_cb, _create_unit_dlg)

        self.rate = QDoubleSpinBox()
        self.rate.setRange(0, 9999999); self.rate.setDecimals(2)
        self.rate.valueChanged.connect(self._calc)

        self.gst_spin = QDoubleSpinBox()
        self.gst_spin.setRange(0, 28); self.gst_spin.setDecimals(2)
        self.gst_spin.setVisible(False)
        self.gst_spin.valueChanged.connect(self._calc)

        self.discount = QDoubleSpinBox()
        self.discount.setRange(0, 100); self.discount.setDecimals(2); self.discount.setSuffix(" %")
        self.discount.valueChanged.connect(self._calc)

        self.scheme = QDoubleSpinBox()
        self.scheme.setRange(0, 9999999); self.scheme.setDecimals(2); self.scheme.setPrefix("₹ ")
        self.scheme.valueChanged.connect(self._calc)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 99999999); self.amount_spin.setDecimals(2); self.amount_spin.setPrefix("₹ ")
        self.amount_spin.setStyleSheet("font-weight:bold;color:#1565C0;background:#e3f2fd;")
        self.amount_spin.valueChanged.connect(self._on_amount_changed)

        form.addRow("Item *:", self.item_cb)
        form.addRow("Qty *:", self.qty)
        form.addRow("Unit:", self.unit_cb)
        form.addRow("Rate (\u20b9):", self.rate)
        form.addRow("Discount %:", self.discount)
        form.addRow("Scheme (₹):", self.scheme)
        # form.addRow("GST %:", self.gst_spin) # Hidden
        form.addRow("Taxable Amount:", self.amount_spin)

        setup_enter_nav(self, [
            self.item_cb, self.qty, self.unit_cb, self.rate, self.discount, self.scheme, self.amount_spin
        ], accept_callback=self._accept)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

        if existing:
            for i, it in enumerate(self._items):
                if it["_id"] == existing["item_id"]:
                    self.item_cb.setCurrentIndex(i + 1)
                    break
            self.qty.setValue(existing["qty"])
            self.unit_cb.setCurrentText(existing["unit"])
            self.rate.setValue(existing["rate"])
            self.discount.setValue(existing.get("discount", 0))
            self.scheme.setValue(existing.get("scheme", 0))
            self.gst_spin.setValue(existing["gst_rate"])
            self._calc()

    def _on_item_changed(self, idx):
        if idx > 0:
            item = self.item_cb.currentData()
            if item:
                self.gst_spin.setValue(item.get("gst_rate", 0))
                # Auto-fill from item master
                self.rate.setValue(item.get("price", 0.0))
                self.unit_cb.setCurrentData(str(item.get("unit", "")))
        self._calc()

    def _calc(self):
        if hasattr(self, "_calculating") and self._calculating: return
        self._calculating = True
        try:
            base = self.qty.value() * self.rate.value()
            disc = base * self.discount.value() / 100.0
            amt = base - disc - self.scheme.value()
            self.amount_spin.setValue(max(0, amt))
        finally:
            self._calculating = False

    def _on_amount_changed(self):
        if hasattr(self, "_calculating") and self._calculating: return
        self._calculating = True
        try:
            # Reverse calculation: Rate = (Amount + Scheme) / (Qty * (1 - Discount/100))
            amt = self.amount_spin.value()
            qty = self.qty.value()
            disc_p = self.discount.value()
            scheme = self.scheme.value()
            
            if qty > 0:
                multiplier = (1 - disc_p / 100.0)
                if multiplier > 0:
                    new_rate = (amt + scheme) / (qty * multiplier)
                    self.rate.setValue(new_rate)
        finally:
            self._calculating = False

    def _accept(self):
        if self.item_cb.currentIndex() <= 0:
            QMessageBox.warning(self, "Error", "Please select an item"); return
        if self.qty.value() <= 0:
            QMessageBox.warning(self, "Error", "Qty must be greater than 0"); return
        self.accept()

    def get_data(self):
        idx  = self.item_cb.currentIndex()
        if idx <= 0: return None
        item = self.item_cb.currentData()
        qty   = self.qty.value()
        rate  = self.rate.value()
        disc_p = self.discount.value()
        scheme = self.scheme.value()
        
        base_amt = qty * rate
        disc_amt = base_amt * disc_p / 100.0
        taxable_amt = round(base_amt - disc_amt - scheme, 2)
        taxable_amt = max(0, taxable_amt)

        # Get specific tax percentages from the item record
        cgst_p = item.get("cgst", 0)
        sgst_p = item.get("sgst", 0)
        igst_p = item.get("igst", 0)
        
        if cgst_p == 0 and sgst_p == 0 and item.get("gst_rate", 0) > 0:
            cgst_p = sgst_p = item["gst_rate"] / 2
            igst_p = item["gst_rate"]
        
        return {
            "item_id":   item["_id"],
            "item_name": item["name"],
            "hsn_sac":   item.get("hsn_sac", ""),
            "unit":      self.unit_cb.currentData(),
            "qty":       qty,
            "rate":      rate,
            "discount":  disc_p,
            "scheme":    scheme,
            "amount":    taxable_amt,
            "gst_rate":  item.get("gst_rate", 0),
            "cgst_p":    cgst_p,
            "sgst_p":    sgst_p,
            "igst_p":    igst_p,
            "cgst":      round(taxable_amt * cgst_p / 100, 2),
            "sgst":      round(taxable_amt * sgst_p / 100, 2),
            "igst":      round(taxable_amt * igst_p / 100, 2),
        }


class InvoiceVoucherDialog(QDialog):
    def __init__(self, parent, vtype, existing=None):
        super().__init__(parent)
        self.vtype    = vtype
        self._vid     = existing["_id"] if existing else None  # voucher id when editing
        self.setWindowTitle(f"Edit {vtype} Voucher" if existing else f"{vtype} Voucher")

        # ── Dynamic 1-inch margin based on screen DPI ─────────────────────────
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        # logicalDotsPerInchY gives DPI-aware pixels-per-inch for the Y axis
        dpi = screen.logicalDotsPerInchY() if screen else 96.0
        _inch_px = max(60, int(dpi))   # 1 inch in pixels; floor at 60 for tiny screens

        self.setMinimumSize(880, 540 + 2 * _inch_px)   # base height + 2 × 1 inch
        self.showMaximized()

        try:
            self._ledgers = api.list_ledgers()
            self._items   = api.list_stock_items()
            self._units   = api.list_units()
            _groups       = api.list_groups()
        except Exception:
            self._ledgers = []; self._items = []; self._units = ["PCS"]; _groups = []
        
        self._group_map = {str(g["_id"]): g["name"] for g in _groups}
        self._group_nature = {str(g["_id"]): g["nature"] for g in _groups}
        self._dt_group_id = next((str(g["_id"]) for g in _groups if g["name"] == "Duties & Taxes"), None)
        self._unit_map = {str(u["_id"]): u["name"] for u in self._units}
        
        # Which groups are Duties & Taxes (or a direct child of it)
        self._is_dt_group  = {
            str(g["_id"]): (
                g["name"] == "Duties & Taxes"
                or (g.get("parent") or "") == "Duties & Taxes"
                or str(g.get("parent", "")) == self._dt_group_id
            )
            for g in _groups
        }
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)  # normal inner padding
        root.setSpacing(10)
        hdr = QWidget(); hdr.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hdr.setStyleSheet("background:#1565C0;border-radius:6px;padding:4px;")
        hdr_lay = QHBoxLayout(hdr)
        vt_lbl = QLabel(vtype.upper())
        vt_lbl.setStyleSheet("color:#fff;font-size:16px;font-weight:bold;")
        hdr_lay.addWidget(vt_lbl); hdr_lay.addStretch()
        self.date_edit = DateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True); self.date_edit.setDisplayFormat("d-MMM-yy")
        
        self.date_edit.setStyleSheet("""
QToolButton#qt_calendar_prevmonth {
    qproperty-icon: url(frontend/assets/icons/chevron-left.svg);
}
QToolButton#qt_calendar_nextmonth {
    qproperty-icon: url(frontend/assets/icons/chevron-right.svg);
}
""")

        hdr_lay.addWidget(QLabel("<span style='color:#bbdefb'>Date:</span>"))
        hdr_lay.addWidget(self.date_edit)
        root.addWidget(hdr)
        # Party + Ledger
        grid = QGridLayout()
        grid.setContentsMargins(0,6,0,6)
        if vtype == "Sales":
            party_label, ledger_label = "Party A/c Name (Debtor)", "Sales Ledger"
        elif vtype == "Purchase":
            party_label, ledger_label = "Party A/c Name (Creditor)", "Purchase Ledger"
        elif vtype == "Credit Note":
            party_label, ledger_label = "Party A/c Name (Customer)", "Sales Return Ledger"
        elif vtype == "Debit Note":
            party_label, ledger_label = "Party A/c Name (Supplier)", "Purchase Return Ledger"
        else:
            party_label, ledger_label = "Party A/c Name", "Ledger Account"
        
        grid.addWidget(QLabel(f"{party_label}:"), 0, 0)
        grid.addWidget(QLabel(f"{ledger_label}:"), 1, 0)

        self.party_cb = SearchableComboBox(); self.party_cb.setMinimumWidth(280)
        self.party_cb.addItem(f"Select {party_label}", None)
        
        # Populate party_cb with filtered ledgers
        for l in self._ledgers:
            g_id = str(l.get("group", ""))
            g_name = self._group_map.get(g_id, "")
            
            show = False
            if vtype == "Sales":
                if g_name in ["Sundry Debtors", "Cash-in-Hand", "Bank Accounts"]: show = True
            elif vtype == "Purchase":
                if g_name in ["Sundry Creditors", "Cash-in-Hand", "Bank Accounts"]: show = True
            elif vtype == "Credit Note":
                if g_name == "Sundry Debtors": show = True
            elif vtype == "Debit Note":
                if g_name == "Sundry Creditors": show = True
            else:
                show = True # fallback
            
            if show:
                self.party_cb.addItem(l["name"], l["_id"])

        self.party_cb.currentIndexChanged.connect(lambda i: self._show_bal(i, self.party_bal))
        grid.addWidget(self.party_cb, 0, 1)
        self.party_bal = QLabel(""); self.party_bal.setStyleSheet("color:#1565C0;font-style:italic;font-size:11px;")
        grid.addWidget(self.party_bal, 0, 2)

        self.ledger_cb = SearchableComboBox(); self.ledger_cb.setMinimumWidth(280)
        self.ledger_cb.addItem(f"Select {ledger_label}", None)

        # Populate ledger_cb with filtered ledgers (Sales Accounts / Purchase Accounts)
        for l in self._ledgers:
            g_id = str(l.get("group", ""))
            g_name = self._group_map.get(g_id, "")
            
            show = False
            if vtype in ["Sales", "Credit Note"]:
                if g_name == "Sales Accounts": show = True
            elif vtype in ["Purchase", "Debit Note"]:
                if g_name == "Purchase Accounts": show = True
            else:
                show = True
            
            if show:
                self.ledger_cb.addItem(l["name"], l["_id"])

        self.ledger_cb.currentIndexChanged.connect(lambda i: self._show_bal(i, self.ledger_bal))
        grid.addWidget(self.ledger_cb, 1, 1)
        self.ledger_bal = QLabel(""); self.ledger_bal.setStyleSheet("color:#0277BD;font-style:italic;font-size:11px;")
        grid.addWidget(self.ledger_bal, 1, 2)

        # "Create New Ledger" option for both party and ledger combos
        def _make_ledger_creator(target_combo):
            def _create_ledger():
                from frontend.pages.ledger import LedgerDialog
                try:
                    groups = api.list_groups()
                except Exception:
                    groups = []
                dlg = LedgerDialog(self, groups)
                if dlg.exec():
                    data = dlg.get_data()
                    try:
                        resp = api.create_ledger(data)
                        new_l = {"_id": resp.get("id", ""), "name": data["name"]}
                        self._ledgers.append(new_l)
                        return (data["name"], new_l["_id"])
                    except Exception as ex:
                        QMessageBox.warning(self, "Error", str(ex))
                return None
            return _create_ledger
        wire_create_new(self.party_cb,  _make_ledger_creator(self.party_cb))
        wire_create_new(self.ledger_cb, _make_ledger_creator(self.ledger_cb))

        def _make_ledger_editor(target_combo):
            def _edit_ledger(ledger_id):
                from frontend.pages.ledger import LedgerDialog
                # Fetch the FULL ledger record so all fields are pre-filled
                try:
                    ledger = api.get_ledger(ledger_id)
                except Exception:
                    ledger = next((l for l in self._ledgers if l["_id"] == ledger_id), None)
                if not ledger:
                    return None
                try:
                    groups = api.list_groups()
                except Exception:
                    groups = []
                dlg = LedgerDialog(self, groups, data=ledger)
                if dlg.exec():
                    data = dlg.get_data()
                    try:
                        api.update_ledger(ledger_id, data)
                        updated = {**ledger, **data, "_id": ledger_id}
                        for i, l in enumerate(self._ledgers):
                            if l["_id"] == ledger_id:
                                self._ledgers[i] = updated
                                break
                        return (data["name"], ledger_id)
                    except Exception as ex:
                        QMessageBox.warning(self, "Error", str(ex))
                return None
            return _edit_ledger

        wire_edit_selected(self.party_cb,  _make_ledger_editor(self.party_cb))
        wire_edit_selected(self.ledger_cb, _make_ledger_editor(self.ledger_cb))
        root.addLayout(grid)
        # Items
        items_hdr = QHBoxLayout()
        items_lbl = QLabel("Items")
        items_lbl.setStyleSheet("font-weight:bold;color:#37474f;")
        self.add_item_btn = QPushButton("+ Add Item  [Alt+I]")
        self.add_item_btn.clicked.connect(self._add_item_row)
        self.add_item_btn.setShortcut("Alt+I")
        items_hdr.addWidget(items_lbl); items_hdr.addStretch(); items_hdr.addWidget(self.add_item_btn)
        root.addLayout(items_hdr)
        self._invoice_items = []
        self.items_table = QTableWidget(0, 11)
        self.items_table.setHorizontalHeaderLabels(
            ["Item", "Qty", "Unit", "Rate (₹)", "Disc %", "Scheme (₹)", "CGST (₹)", "SGST (₹)", "IGST (₹)", "Taxable (₹)", ""])
        self.items_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.items_table.itemDoubleClicked.connect(self._edit_item_row)
        root.addWidget(self.items_table)
        
        # Quantity Total Label
        self.qty_total_lbl = QLabel("Total Qty: 0")
        self.qty_total_lbl.setStyleSheet("font-weight:bold;color:#1565C0;font-size:12px;margin-bottom:4px;")
        root.addWidget(self.qty_total_lbl)

        for _c in range(1, 10):
            self.items_table.horizontalHeader().setSectionResizeMode(
                _c, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(10, QHeaderView.ResizeMode.Fixed)
        self.items_table.setColumnWidth(10, 40)
        self.items_table.setMinimumHeight(160)
        self.items_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # ── Tax / Adjustment Ledgers (dynamic) ────────────────────────────────
        tax_hdr_lay = QHBoxLayout()
        tax_title = QLabel("Tax / Adjustment Ledgers")
        tax_title.setStyleSheet("font-weight:bold;color:#37474f;font-size:12px;")
        self.add_tax_btn = QPushButton("+ Add Ledger  [Alt+L]")
        self.add_tax_btn.setShortcut("Alt+L")
        self.add_tax_btn.setStyleSheet(
            "QPushButton{background:#1565C0;color:#fff;border:none;"
            "border-radius:4px;padding:3px 10px;font-size:11px;font-weight:bold;}"
            "QPushButton:hover{background:#1976D2;}"
        )
        self.add_tax_btn.clicked.connect(self._add_ledger_row_and_focus)
        tax_hdr_lay.addWidget(tax_title)
        tax_hdr_lay.addStretch()
        tax_hdr_lay.addWidget(self.add_tax_btn)
        root.addLayout(tax_hdr_lay)

        self._tax_rows = []
        self._tax_container = QWidget()
        self._tax_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._tax_container.setStyleSheet(
            "background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;"
        )
        self._tax_v_lay = QVBoxLayout(self._tax_container)
        self._tax_v_lay.setContentsMargins(8, 6, 8, 6)
        self._tax_v_lay.setSpacing(4)
        self._tax_v_lay.addStretch()  # push rows to top

        # Wrap in a QScrollArea so rows never shrink when many are added
        self._tax_scroll = QScrollArea()
        self._tax_scroll.setWidgetResizable(True)
        self._tax_scroll.setWidget(self._tax_container)
        self._tax_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._tax_scroll.setMinimumHeight(80)
        # No MaximumHeight cap — allow the tax section to grow with the dialog
        self._tax_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tax_scroll.setStyleSheet(
            "QScrollArea { background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; }"
            "QScrollBar:vertical { width:6px; background:transparent; }"
            "QScrollBar::handle:vertical { background:#cbd5e1; border-radius:3px; }"
        )
        root.addWidget(self._tax_scroll, 1)  # stretch factor 1 — equal height with items section

        # State tracking
        import frontend.session as session
        self._company_state = ""
        self._party_state = ""
        try:
            comp = api.get_company(session.company_id)
            self._company_state = comp.get("state", "").strip().lower()
        except Exception:
            pass

        self.party_cb.currentIndexChanged.connect(self._on_party_changed)

        summary = QWidget()
        summary.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        summary.setStyleSheet("background:#fafafa;border:1px solid #e0e0e0;border-radius:6px;padding:6px;")
        sum_lay = QHBoxLayout(summary)
        self.subtotal_lbl = QLabel("Sub-Total: \u20b9 0.00")
        self.subtotal_lbl.setStyleSheet("color:#546e7a;font-weight:bold;")
        sum_lay.addWidget(self.subtotal_lbl)
        
        # Dynamic tax tags container
        self.tax_summary_container = QWidget()
        self.tax_summary_lay = QHBoxLayout(self.tax_summary_container)
        self.tax_summary_lay.setContentsMargins(10, 0, 10, 0)
        self.tax_summary_lay.setSpacing(8)
        sum_lay.addWidget(self.tax_summary_container)
        
        sum_lay.addStretch()
        self.grand_lbl = QLabel("Grand Total: \u20b9 0.00")
        self.grand_lbl.setStyleSheet("font-weight:bold;color:#1565C0;font-size:14px;")
        sum_lay.addWidget(self.grand_lbl)
        root.addWidget(summary)
        form2 = QFormLayout()
        self.narration = QLineEdit(); self.narration.setPlaceholderText("Narration")
        form2.addRow("Narration:", self.narration); root.addLayout(form2)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept); btns.rejected.connect(self.reject)
        root.addWidget(btns)

        # Enter nav: date → party → ledger → narration → submit
        setup_enter_nav(self, [
            self.date_edit, self.party_cb, self.ledger_cb, self.narration,
        ])
        self._refresh_totals()

        # ── Pre-populate when editing ──────────────────────────────────────────
        if existing:
            self._populate_existing(existing)

    def _populate_existing(self, existing):
        """Pre-fill the dialog from a fetched voucher dict."""
        from PySide6.QtCore import QDate
        # Date
        try:
            d = QDate.fromString(existing["date"], "yyyy-MM-dd")
            if d.isValid():
                self.date_edit.setDate(d)
        except Exception:
            pass

        # Narration
        self.narration.setText(existing.get("narration", ""))

        # Ledger entries: first entry = party (Dr for Sales), second = sales ledger (Cr)
        items = existing.get("items", [])
        # Determine party and ledger entries based on vtype
        if self.vtype in ["Sales", "Debit Note"]:
            party_entry  = next((e for e in items if e["dr_cr"] == "Dr"), None)
            ledger_entry = next((e for e in items if e["dr_cr"] == "Cr" and e != party_entry), None)
        else:
            ledger_entry = next((e for e in items if e["dr_cr"] == "Dr"), None)
            party_entry  = next((e for e in items if e["dr_cr"] == "Cr" and e != ledger_entry), None)

        if party_entry:
            self.party_cb.setCurrentData(party_entry["ledger_id"])
        if ledger_entry:
            self.ledger_cb.setCurrentData(ledger_entry["ledger_id"])

        # Invoice items from stock transactions
        inv_items = existing.get("invoice_items", [])
        if inv_items:
            # Ensure cgst/sgst are present (stock txns may lack them)
            for it in inv_items:
                if "cgst" not in it:
                    gst = it.get("gst_rate", 0)
                    amt = it.get("amount", 0)
                    it["cgst"] = round(amt * gst / 200, 2)
                    it["sgst"] = round(amt * gst / 200, 2)
            self._invoice_items = inv_items
            self._refresh_items_table()

        # Tax rows: remaining entries (skip party + sales/purchase ledger)
        skip_ids = set()
        if party_entry:  skip_ids.add(party_entry["ledger_id"])
        if ledger_entry: skip_ids.add(ledger_entry["ledger_id"])
        # Also skip auto-fill (cgst/sgst) amounts — they will be re-computed from items
        # Remove the 4 default pre-added rows first, then re-add from saved entries
        for row in list(self._tax_rows):
            self._tax_v_lay.removeWidget(row["widget"])
            row["widget"].deleteLater()
        self._tax_rows.clear()

        auto_fill_count = 0
        for e in items:
            if e["ledger_id"] in skip_ids:
                continue
            # Check if this is an auto-fill (CGST/SGST) row by looking at group nature
            l = next((x for x in self._ledgers if x["_id"] == e["ledger_id"]), None)
            is_tax = False
            if l:
                nature = self._group_nature.get(l.get("group", ""), "")
                is_tax = nature in ("Liability",) and auto_fill_count < 2
            if is_tax:
                self._add_tax_row(auto_fill=True)
                auto_fill_count += 1
            else:
                self._add_tax_row()
            row = self._tax_rows[-1]
            # Set ledger combo
            cb = row["ledger_cb"]
            for i in range(1, cb.count()):
                if cb.itemData(i) == e["ledger_id"] or (
                        hasattr(cb, 'itemData') and str(cb.itemData(i)) == str(e["ledger_id"])):
                    cb.setCurrentIndex(i)
                    break
            # Set amount (flip to negative if dr_cr doesn't match base)
            val = e["amount"]
            if l:
                base_dr_cr = self._dr_cr_for_ledger(l)
                if e["dr_cr"] != base_dr_cr:
                    val = -val
            row["amt_spin"].setValue(val)

        self._refresh_totals()

    def _dr_cr_for_ledger(self, ledger_dict):
        """
        Return the 'base' direction for the adjustment/tax section.
        In Sales/Debit Note, 'Cr' entries add to the Grand Total.
        In Purchase/Credit Note, 'Dr' entries add to the Grand Total.
        By using this as a base, a positive input will always ADD and a negative input will always SUBTRACT.
        """
        return "Cr" if self.vtype in ["Sales", "Debit Note"] else "Dr"

    def _add_tax_row(self, placeholder="-- Select Ledger --", auto_fill=False):
        row_w = QFrame()
        row_w.setStyleSheet("background:transparent;border:none;")
        row_lay = QHBoxLayout(row_w)
        row_lay.setContentsMargins(0, 1, 0, 1)
        row_lay.setSpacing(6)

        if auto_fill:
            icon = QLabel("⟳")
            icon.setFixedWidth(16)
            icon.setStyleSheet("color:#1565C0;font-size:11px;background:transparent;")
            row_lay.addWidget(icon)

        ledger_cb = SearchableComboBox()
        ledger_cb.setMinimumWidth(200)
        ledger_cb.addItem(placeholder)
        for l in self._ledgers:
            ledger_cb.addItem(l["name"], l["_id"])
        ledger_cb.currentIndexChanged.connect(self._refresh_totals)

        def _create_ledger_fn():
            from frontend.pages.ledger import LedgerDialog
            try:
                groups = api.list_groups()
            except Exception:
                groups = []
            dlg = LedgerDialog(self, groups)
            if dlg.exec():
                data = dlg.get_data()
                try:
                    resp = api.create_ledger(data)
                    new_l = {
                        "_id":      resp.get("id", ""),
                        "name":     data["name"],
                        "group":    data.get("group", ""),
                        "tax_rate": data.get("tax_rate", 0.0),
                    }
                    self._ledgers.append(new_l)
                    # data["group"] is now a group _id string
                    if data.get("group") and data["group"] not in self._group_nature:
                        try:
                            for g in api.list_groups():
                                if g["_id"] == data["group"]:
                                    self._group_nature[g["_id"]] = g["nature"]
                                    break
                        except Exception:
                            pass
                    return (data["name"], new_l["_id"])
                except Exception as ex:
                    QMessageBox.warning(self, "Error", str(ex))
            return None
        wire_create_new(ledger_cb, _create_ledger_fn)

        def _edit_tax_ledger(ledger_id):
            from frontend.pages.ledger import LedgerDialog
            # Fetch full ledger record so all fields (including group) are pre-filled
            try:
                ledger = api.get_ledger(ledger_id)
            except Exception:
                ledger = next((l for l in self._ledgers if l["_id"] == ledger_id), None)
            if not ledger:
                return None
            try:
                groups = api.list_groups()
            except Exception:
                groups = []
            dlg = LedgerDialog(self, groups, data=ledger)
            if dlg.exec():
                data = dlg.get_data()
                try:
                    api.update_ledger(ledger_id, data)
                    updated = {**ledger, **data, "_id": ledger_id}
                    for i, l in enumerate(self._ledgers):
                        if l["_id"] == ledger_id:
                            self._ledgers[i] = updated
                            break
                    return (data["name"], ledger_id)
                except Exception as ex:
                    QMessageBox.warning(self, "Error", str(ex))
            return None
        wire_edit_selected(ledger_cb, _edit_tax_ledger)

        amt_spin = QDoubleSpinBox()
        amt_spin.setRange(-9999999, 9999999)
        amt_spin.setDecimals(2)
        amt_spin.setFixedWidth(120)
        amt_spin.setPrefix("₹ ")
        if auto_fill:
            amt_spin.setReadOnly(True)
            amt_spin.setStyleSheet("background:#e3f2fd;color:#1565C0;")
        else:
            amt_spin.valueChanged.connect(self._refresh_totals)

        # Label that shows the configured tax % — REPLACED by an editable rate_spin
        rate_spin = QDoubleSpinBox()
        rate_spin.setRange(0, 100)
        rate_spin.setDecimals(2)
        rate_spin.setSuffix(" %")
        rate_spin.setFixedWidth(72)
        rate_spin.setToolTip("Tax rate applied to Sub-Total (editable per voucher)")
        rate_spin.setVisible(False)   # shown only when a D&T ledger is selected
        rate_spin.setStyleSheet(
            "QDoubleSpinBox { background:#fffde7; color:#5d4037; "
            "border:1px solid #f9a825; border-radius:4px; padding:2px 4px; }"
        )

        del_btn = QPushButton()
        del_btn.setIcon(get_icon("frontend/assets/icons/trash.svg", "#c62828"))
        del_btn.setIconSize(QSize(16, 16))
        del_btn.setFixedWidth(26)
        del_btn.setStyleSheet(
            "QPushButton{color:#c62828;font-weight:bold;border:none;"
            "background:transparent;font-size:13px;padding:0px;}"
            "QPushButton:hover{background:#fee2e2;}"
        )

        row_dict = {
            "widget":        row_w,
            "ledger_cb":     ledger_cb,
            "amt_spin":      amt_spin,
            "rate_spin":     rate_spin,    # editable % for D&T ledgers
            "auto_fill":     auto_fill,
            "tax_rate_auto": False,        # True when a D&T ledger is picked
        }
        del_btn.clicked.connect(lambda: self._remove_tax_row(row_dict))

        # ── React to ledger selection: fetch live tax_rate, fill rate_spin ──
        def _on_ledger_selected(idx, _row=row_dict):
            is_dt = False
            configured_rate = 0.0

            if 0 < idx <= len(self._ledgers):
                ledger = self._ledgers[idx - 1]
                group_id = ledger.get("group", "")
                is_dt = self._is_dt_group.get(group_id, False)

                if is_dt:
                    # Fetch the LIVE tax_rate from the server so we always
                    # get the up-to-date value (stale in-memory cache may be 0).
                    try:
                        fresh = api.get_ledger(ledger["_id"])
                        if fresh:
                            configured_rate = fresh.get("tax_rate", 0.0) or 0.0
                            # Update in-memory cache for subsequent refreshes
                            self._ledgers[idx - 1]["tax_rate"] = configured_rate
                    except Exception:
                        configured_rate = ledger.get("tax_rate", 0.0) or 0.0

            if is_dt:
                _row["tax_rate_auto"] = True
                _row["rate_spin"].setVisible(True)
                # Fill rate_spin with fetched tax_rate; user can override per-voucher
                _row["rate_spin"].setValue(configured_rate)
                _row["amt_spin"].setReadOnly(True)
                _row["amt_spin"].setStyleSheet("background:#e3f2fd;color:#1565C0;")
                # Compute immediately
                subtotal = sum(d["amount"] for d in self._invoice_items)
                _row["amt_spin"].setValue(round(subtotal * configured_rate / 100, 2))
            else:
                _row["tax_rate_auto"] = False
                _row["rate_spin"].setVisible(False)
                _row["rate_spin"].setValue(0.0)
                if not _row["auto_fill"]:
                    _row["amt_spin"].setReadOnly(False)
                    _row["amt_spin"].setStyleSheet("")
            self._refresh_totals()

        # ── rate_spin changed — recompute amount immediately ──
        def _on_rate_changed(pct, _row=row_dict):
            if _row.get("tax_rate_auto"):
                subtotal = sum(d["amount"] for d in self._invoice_items)
                _row["amt_spin"].setValue(round(subtotal * pct / 100, 2))
                self._refresh_totals()
        rate_spin.valueChanged.connect(_on_rate_changed)

        # Disconnect the generic refresh and use our enhanced handler instead
        ledger_cb.currentIndexChanged.disconnect(self._refresh_totals)
        ledger_cb.currentIndexChanged.connect(_on_ledger_selected)

        row_lay.addWidget(ledger_cb, 1)
        row_lay.addWidget(rate_spin)
        row_lay.addWidget(amt_spin)
        row_lay.addWidget(del_btn)

        # Insert widget BEFORE the stretch item at the end
        stretch_idx = self._tax_v_lay.count() - 1
        self._tax_v_lay.insertWidget(stretch_idx, row_w)
        self._tax_rows.append(row_dict)

        # Wire Enter navigation within the row (and across rows)
        self._rewire_nav()

        # Only refresh if NOT called from within _refresh_totals itself
        if not auto_fill and hasattr(self, "subtotal_lbl"):
            self._refresh_totals()

        # Scroll to bottom to show the newly added row
        QTimer.singleShot(50, lambda: self._tax_scroll.verticalScrollBar().setValue(
            self._tax_scroll.verticalScrollBar().maximum()
        ))
    def _remove_tax_row(self, row_dict):
        if row_dict in self._tax_rows:
            self._tax_rows.remove(row_dict)
            row_dict["widget"].deleteLater()
            self._refresh_totals()
            self._rewire_nav()

    def _rewire_nav(self):
        widgets = [self.date_edit, self.party_cb, self.ledger_cb]
        for row in self._tax_rows:
            widgets.append(row["ledger_cb"])
            widgets.append(row["rate_spin"])
            widgets.append(row["amt_spin"])
        widgets.append(self.narration)
        setup_enter_nav(self, widgets)


    def _add_ledger_row_and_focus(self):
        """Add a new Tax/Ledger row and set focus to its ledger combobox (first column)."""
        self._add_tax_row()
        if self._tax_rows:
            new_row = self._tax_rows[-1]
            cb = new_row["ledger_cb"]
            # Defer focus until Qt has finished laying out the new widget
            QTimer.singleShot(0, lambda: (cb.setFocus(), cb.showPopup()))

    def _add_item_row(self):
        dlg = ItemEntryDialog(self, self._items, self._units)
        if dlg.exec():
            data = dlg.get_data()
            if data:
                self._invoice_items.append(data)
                self._refresh_items_table()
                self._refresh_totals()

    def _edit_item_row(self, index=None):
        if index is not None:
            row = index.row()
        else:
            row = self.items_table.currentRow()
            
        if 0 <= row < len(self._invoice_items):
            existing = self._invoice_items[row]
            dlg = ItemEntryDialog(self, self._items, self._units, existing=existing)
            if dlg.exec():
                data = dlg.get_data()
                if data:
                    self._invoice_items[row] = data
                    self._refresh_items_table()
                    self._refresh_totals()

    def _remove_item(self, idx):
        if 0 <= idx < len(self._invoice_items):
            self._invoice_items.pop(idx)
            self._refresh_items_table()
            self._refresh_totals()

    def _on_item_row_changed(self):
        # Triggered from row widgets (if used)
        self._refresh_totals()

    def _refresh_items_table(self):
        self.items_table.setRowCount(0)
        for i, d in enumerate(self._invoice_items):
            r = self.items_table.rowCount()
            self.items_table.insertRow(r)
            self.items_table.setItem(r, 0, QTableWidgetItem(d["item_name"]))
            self.items_table.setItem(r, 1, QTableWidgetItem(f"{d['qty']:g}"))
            u_name = self._unit_map.get(d["unit"], d["unit"])
            self.items_table.setItem(r, 2, QTableWidgetItem(u_name))
            self.items_table.setItem(r, 3, QTableWidgetItem(format_indian_number(d['rate'])))
            self.items_table.setItem(r, 4, QTableWidgetItem(f"{d.get('discount', 0):g}%"))
            self.items_table.setItem(r, 5, QTableWidgetItem(format_indian_number(d.get('scheme', 0))))
            self.items_table.setItem(r, 6, QTableWidgetItem(format_indian_number(d.get('cgst', 0))))
            self.items_table.setItem(r, 7, QTableWidgetItem(format_indian_number(d.get('sgst', 0))))
            self.items_table.setItem(r, 8, QTableWidgetItem(format_indian_number(d.get('igst', 0))))
            self.items_table.setItem(r, 9, QTableWidgetItem(format_indian_number(d['amount'])))
            
            # Delete button (at column index 10)
            del_btn = QPushButton()
            del_btn.setIcon(get_icon("frontend/assets/icons/trash.svg", "#c62828"))
            del_btn.setIconSize(QSize(16, 16))
            del_btn.setFixedWidth(34)
            del_btn.setToolTip("Remove item row")
            del_btn.setStyleSheet("QPushButton { border:none; background:transparent; } QPushButton:hover { background:#fee2e2; border-radius:4px; }")
            del_btn.clicked.connect(lambda *a, idx=i: self._remove_item(idx))
            self.items_table.setCellWidget(r, 10, del_btn)
        
        # Update Total Qty
        t_qty = sum(d["qty"] for d in self._invoice_items)
        self.qty_total_lbl.setText(f"Total Qty: {t_qty:g}")

    def _on_party_changed(self, idx):
        if idx >= 0:
            ledger_id = self.party_cb.itemData(idx)
            # Find the full ledger object to get the state
            ledger = None
            try:
                ledger = api.get_ledger(ledger_id)
            except Exception:
                pass
            
            if not ledger:
                ledger = next((l for l in self._ledgers if l["_id"] == ledger_id), None)
            
            self._party_state = ledger.get("state", "").strip().lower() if ledger else ""
        else:
            self._party_state = ""
        self._refresh_totals()

    def _find_ledger_by_name(self, name):
        # 1. Exact match
        for l in self._ledgers:
            if l["name"].strip().lower() == name.strip().lower():
                return l
                
        # 2. Loose match for tax ledgers (e.g., "Output CGST@9%", "CGST 9%")
        lname_upper = name.strip().upper()
        if "CGST" in lname_upper or "SGST" in lname_upper or "IGST" in lname_upper:
            parts = lname_upper.split()
            if len(parts) > 1:
                prefix = parts[0] # "SALES" or "PURCHASE"
                tax_suffix = parts[-1] # "CGST@9%"
                for l in self._ledgers:
                    l_upper = l["name"].strip().upper()
                    if tax_suffix in l_upper:
                        # Prevent picking Purchase tax for Sales and vice-versa
                        if prefix == "SALES" and ("PURCHASE" in l_upper or "INPUT" in l_upper):
                            continue
                        if prefix == "PURCHASE" and ("SALES" in l_upper or "OUTPUT" in l_upper):
                            continue
                        return l
        return None

    def _on_item_row_changed(self):
        # Update the internal item list from the current row widgets
        # However, it's easier to just trigger a full refresh of totals
        # But we need to get the current data from the rows first.
        # Actually, let's collect all current row data
        self._invoice_items = []
        # Wait, the rows are in self.items_v_lay? No, the user adds them.
        # I need a way to track the row widgets.
        pass

    def _refresh_totals(self):
        subtotal = 0.0
        # Summarize by COMPONENT rates: { (type, rate): amount }
        # type is 'cgst', 'sgst', 'igst'
        tax_summary = {} 
        
        for d in self._invoice_items:
            subtotal += d["amount"]
            
            # CGST component
            cp = d.get("cgst_p", 0)
            if cp > 0:
                key = ("CGST", cp)
                tax_summary[key] = tax_summary.get(key, 0.0) + d.get("cgst", 0.0)
            
            # SGST component
            sp = d.get("sgst_p", 0)
            if sp > 0:
                key = ("SGST", sp)
                tax_summary[key] = tax_summary.get(key, 0.0) + d.get("sgst", 0.0)

            # IGST component
            ip = d.get("igst_p", 0)
            if ip > 0:
                key = ("IGST", ip)
                tax_summary[key] = tax_summary.get(key, 0.0) + d.get("igst", 0.0)

        # Intra-state vs Inter-state
        is_intra = (self._company_state == self._party_state) or not self._company_state or not self._party_state
        
        # Identify which tax ledgers we NEED
        needed_ledgers = [] # list of (ledger_dict, amount)
        prefix = "Sales" if self.vtype in ["Sales", "Credit Note"] else "Purchase"
        
        for (ttype, trate), tamount in tax_summary.items():
            if (is_intra and ttype in ("CGST", "SGST")) or (not is_intra and ttype == "IGST"):
                lname = f"{prefix} {ttype}@{trate:g}%"
                l = self._find_ledger_by_name(lname)
                
                if not l:
                    # Auto-create tax ledger if missing
                    if self._dt_group_id:
                        try:
                            # Determine type (Cr for Sales/Debit Note, Dr for Purchase/Credit Note)
                            l_type = "Cr" if self.vtype in ["Sales", "Debit Note"] else "Dr"
                            resp = api.create_ledger({
                                "name": lname,
                                "group": self._dt_group_id,
                                "tax_rate": trate,
                                "opening_balance": 0,
                                "type": l_type
                            })
                            l = {
                                "_id": resp.get("id", ""),
                                "name": lname,
                                "group": self._dt_group_id,
                                "tax_rate": trate
                            }
                            self._ledgers.append(l)
                            self._is_dt_group[str(l["_id"])] = True
                        except Exception as e:
                            print(f"Error auto-creating tax ledger {lname}: {e}")
                
                if l:
                    needed_ledgers.append((l, round(tamount, 2)))

        # Sync _tax_rows with needed_ledgers
        # First, remove existing auto-fill tax rows that are NOT in needed_ledgers
        for row in list(self._tax_rows):
            if row.get("is_auto_tax"):
                l_id = row["ledger_cb"].currentData()
                still_needed = False
                for nl, namt in needed_ledgers:
                    if nl["_id"] == l_id:
                        still_needed = True
                        # Update amount
                        row["amt_spin"].setValue(namt)
                        needed_ledgers.remove((nl, namt))
                        break
                if not still_needed:
                    self._remove_tax_row(row)

        # Add remaining needed_ledgers as new rows
        for nl, namt in needed_ledgers:
            self._add_tax_row(auto_fill=True)
            row = self._tax_rows[-1]
            row["is_auto_tax"] = True
            # Set ledger combo
            cb = row["ledger_cb"]
            for i in range(1, cb.count()):
                if cb.itemData(i) == nl["_id"]:
                    cb.setCurrentIndex(i)
                    break
            row["amt_spin"].setValue(namt)

        # ── Pass 2: compute grand total ───────────────────────────────────────
        grand = subtotal
        for row in self._tax_rows:
            amt = row["amt_spin"].value()
            idx = row["ledger_cb"].currentIndex()
            if idx > 0:
                l_id = row["ledger_cb"].itemData(idx)
                l = next((x for x in self._ledgers if x["_id"] == l_id), None)
                if l:
                    dr_cr = self._dr_cr_for_ledger(l)
                    if self.vtype in ["Sales", "Debit Note"]:
                        grand += amt if dr_cr == "Cr" else -amt
                    else:
                        grand += amt if dr_cr == "Dr" else -amt
                else:
                    if row["auto_fill"]: grand += amt
            elif row["auto_fill"]:
                grand += amt
                
        gross_sum = sum(i["qty"] * i["rate"] for i in self._invoice_items)
        self.subtotal_lbl.setText(f"Gross Total: {format_inr(gross_sum)}")
        
        # ── Pass 3: Update dynamic tax tags in summary ────────────────────────
        while self.tax_summary_lay.count():
            child = self.tax_summary_lay.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        
        for row in self._tax_rows:
            amt = row["amt_spin"].value()
            if abs(amt) < 0.005: continue
            idx = row["ledger_cb"].currentIndex()
            if idx <= 0: continue
            l_id = row["ledger_cb"].itemData(idx)
            ledger = next((l for l in self._ledgers if l["_id"] == l_id), None)
            if not ledger: continue
            
            group_id = ledger.get("group", "")
            if self._is_dt_group.get(group_id, False):
                name = ledger["name"]
                rate = row["rate_spin"].value() if row.get("tax_rate_auto") else 0
                label_text = f"{name}"
                if rate > 0: label_text += f" ({rate:g}%)"
                label_text += f": {format_inr(amt)}"
                lbl = QLabel(label_text)
                lbl.setStyleSheet("color:#1565C0;background:#e3f2fd;border:1px solid #bbdefb;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:bold;")
                self.tax_summary_lay.addWidget(lbl)

        self.grand_lbl.setText(f"Grand Total: {format_inr(grand)}")

    def _show_bal(self, idx, label):
        if idx <= 0:
            label.setText("")
            return
        
        # Get data from the combo itself instead of assuming index matches self._ledgers
        cb = self.sender() if isinstance(self.sender(), SearchableComboBox) else None
        if not cb:
            # Fallback if called directly (e.g. from lambda)
            # Find which label it is to guess the combo
            if label == self.party_bal: cb = self.party_cb
            elif label == self.ledger_bal: cb = self.ledger_cb
        
        if cb:
            l_id = cb.itemData(idx)
            if l_id:
                try:
                    bal = api.ledger_balance(l_id)
                    label.setText(f"Bal: {format_indian_number(bal['balance'])} {bal['type']}")
                except Exception:
                    label.setText("")
            else:
                label.setText("")

    def _on_accept(self):
        items = self._invoice_items
        if not items:
            QMessageBox.warning(self, "Error", "Add at least one item with Qty > 0"); return
        # Date Validation
        import frontend.session as session
        ok, err = session.is_date_in_period(self.date_edit.date())
        if not ok:
            QMessageBox.warning(self, "Out of Range", err); return

        reply = QMessageBox.question(
            self, "Confirm Save",
            f"Save {self.vtype} voucher?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.accept()

    def get_data(self):
        items    = self._invoice_items
        subtotal = sum(i["amount"] for i in items)
        cgst     = sum(i["cgst"]   for i in items)
        sgst     = sum(i["sgst"]   for i in items)

        # Recompute grand total the same way _refresh_totals does
        grand = subtotal
        for row in self._tax_rows:
            amt   = row["amt_spin"].value()
            l_id  = row["ledger_cb"].currentData()
            if not l_id:
                continue
            l = next((x for x in self._ledgers if x["_id"] == l_id), None)
            if not l:
                continue
            dr_cr = self._dr_cr_for_ledger(l)
            if self.vtype in ["Sales", "Debit Note"]:
                grand += amt if dr_cr == "Cr" else -amt
            else:
                grand += amt if dr_cr == "Dr" else -amt
        grand = round(grand, 2)

        party_id   = self.party_cb.currentData() or ""
        party_name = self.party_cb.currentText()
        ledger_id  = self.ledger_cb.currentData() or ""
        ledger_name= self.ledger_cb.currentText()
        date_str   = self.date_edit.date().toString("yyyy-MM-dd")

        if self.vtype in ["Sales", "Debit Note"]:
            entries = [
                {"ledger_id": party_id,  "ledger_name": party_name,  "dr_cr": "Dr", "amount": grand},
                {"ledger_id": ledger_id, "ledger_name": ledger_name, "dr_cr": "Cr", "amount": subtotal},
            ]
        else:
            entries = [
                {"ledger_id": ledger_id, "ledger_name": ledger_name, "dr_cr": "Dr", "amount": subtotal},
                {"ledger_id": party_id,  "ledger_name": party_name,  "dr_cr": "Cr", "amount": grand},
            ]

        # Dynamic tax / adjustment ledger entries
        for row in self._tax_rows:
            amt  = round(row["amt_spin"].value(), 2)
            if amt == 0:
                continue
            l_id = row["ledger_cb"].currentData()
            if not l_id:
                continue
            l = next((x for x in self._ledgers if x["_id"] == l_id), None)
            if not l:
                continue
            base_dr_cr = self._dr_cr_for_ledger(l)
            final_dr_cr = base_dr_cr
            final_amt = amt
            if amt < 0:
                # Flip Dr/Cr if amount is negative
                final_dr_cr = "Cr" if base_dr_cr == "Dr" else "Dr"
                final_amt = abs(amt)

            entries.append({
                "ledger_id":   l["_id"],
                "ledger_name": l["name"],
                "dr_cr":       final_dr_cr,
                "amount":      final_amt,
            })

        return {
            "voucher_type": self.vtype, "date": date_str,
            "narration": self.narration.text().strip(),
            "entries": entries, "invoice_items": items,
            "subtotal": subtotal, "cgst": cgst, "sgst": sgst, "grand_total": grand,
        }

