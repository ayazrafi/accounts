from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QFormLayout, QLineEdit,
    QDoubleSpinBox, QDialogButtonBox, QMessageBox, QHeaderView,
    QFrame, QComboBox, QGroupBox, QGridLayout, QScrollArea, QWidget, QSplitter, QSizePolicy
)
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt, QDate, Signal
import frontend.api_client as api
from frontend.utils import SearchableComboBox, DateEdit, format_indian_number, format_inr, setup_enter_nav
import frontend.session as session

REASONS = [
    ("Sales Return", "Invoice Items Return"),
    ("Partial Return", "Invoice Items Return"),
    ("Short Supply", "Invoice Value Adjustment (Inclusive)"),
    ("Overbilling Correction", "Invoice Value Adjustment (Inclusive)"),
    ("Wrong Price / Rate", "Invoice Value Adjustment (Exclusive)"),
    ("Wrong GST Rate", "Full Invoice Return"),
    ("Pre-agreed Discount", "Invoice Value Adjustment (Exclusive)"),
    ("Post-supply Discount", "Invoice Value Adjustment (Exclusive)"),
    ("Specific Item Discount", "Invoice Items Return"),
    ("Cancelled Sale", "Full Invoice Return"),
]

class CreditNoteDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle("GST Credit Note - Sales Return / Adjustment")
        self.setMinimumSize(1100, 750)
        self._existing = existing
        self._items_data = []
        self._items = []
        self._original_invoice = None
        self._ledgers = []
        self._units = []
        self._tax_rows = []
        
        self._setup_ui()
        self._load_data()
        
        if existing:
            self._populate_existing(existing)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Header
        header = QFrame()
        header.setStyleSheet("background: #1e3a8a; border-radius: 8px; padding: 10px;")
        header_layout = QHBoxLayout(header)
        title = QLabel("CREDIT NOTE (GST COMPLIANT)")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        self.date_edit = DateEdit(QDate.currentDate())
        header_layout.addWidget(QLabel("<span style='color: #bfdbfe'>Date:</span>"))
        header_layout.addWidget(self.date_edit)
        layout.addWidget(header)

        # 1. Selection & Info
        sel_group = QGroupBox("Invoice & Binding")
        sel_lay = QGridLayout(sel_group)
        
        sel_lay.addWidget(QLabel("<b>Original Sales Invoice:</b>"), 0, 0)
        self.invoice_cb = SearchableComboBox()
        self.invoice_cb.addItem("-- Select Invoice --", None)
        self.invoice_cb.currentIndexChanged.connect(self._on_invoice_selected)
        sel_lay.addWidget(self.invoice_cb, 0, 1)
        
        sel_lay.addWidget(QLabel("<b>Reason:</b>"), 0, 2)
        self.reason_cb = SearchableComboBox()
        self.reason_cb.addItem("-- Select Reason --")
        for r, t in REASONS:
            self.reason_cb.addItem(r, t)
        self.reason_cb.currentIndexChanged.connect(self._on_reason_changed)
        sel_lay.addWidget(self.reason_cb, 0, 3)

        sel_lay.addWidget(QLabel("<b>Party A/c Name:</b>"), 1, 0)
        self.party_cb = SearchableComboBox()
        self.party_cb.addItem("-- Select Party --", None)
        for l in self._ledgers: self.party_cb.addItem(l["name"], l["_id"])
        sel_lay.addWidget(self.party_cb, 1, 1)

        sel_lay.addWidget(QLabel("<b>Sales Return Ledger:</b>"), 1, 2)
        self.ledger_cb = SearchableComboBox()
        self.ledger_cb.addItem("-- Select Ledger --", None)
        for l in self._ledgers: self.ledger_cb.addItem(l["name"], l["_id"])
        sel_lay.addWidget(self.ledger_cb, 1, 3)

        # Read-only binding info
        self.binding_info = QLabel("<i>Select an invoice to auto-bind details</i>")
        self.binding_info.setStyleSheet("color: #1e40af; font-weight: 500;")
        sel_lay.addWidget(self.binding_info, 2, 0, 1, 4)
        layout.addWidget(sel_group)

        # 2. Input Area (Value Adjustment)
        self.input_group = QGroupBox("Adjustment Value")
        input_lay = QHBoxLayout(self.input_group)
        self.reduction_label = QLabel("Reduction Amount:")
        self.reduction_amt = QDoubleSpinBox()
        self.reduction_amt.setRange(0, 99999999); self.reduction_amt.setDecimals(2)
        self.reduction_amt.setPrefix("₹ "); self.reduction_amt.setMinimumWidth(150)
        self.reduction_amt.valueChanged.connect(self._recalculate)
        input_lay.addWidget(self.reduction_label)
        input_lay.addWidget(self.reduction_amt)
        input_lay.addStretch()
        self.input_group.hide()
        layout.addWidget(self.input_group)

        # 3. Main Content Splitter
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Items Section
        item_group = QGroupBox("Items")
        item_lay = QVBoxLayout(item_group)
        
        btn_lay = QHBoxLayout()
        self.add_item_btn = QPushButton("+ Add Item [Alt+I]")
        self.add_item_btn.setShortcut("Alt+I")
        self.add_item_btn.clicked.connect(self._add_manual_item)
        btn_lay.addStretch()
        btn_lay.addWidget(self.add_item_btn)
        item_lay.addLayout(btn_lay)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Item Name", "Orig. Qty", "Return Qty", "Rate (₹)", "Taxable Value", "GST %", "Total (₹)", "Action"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._on_table_item_changed)
        item_lay.addWidget(self.table)
        self.splitter.addWidget(item_group)

        # 4. Tax Ledgers
        tax_section = QGroupBox("Tax / Adjustment Ledgers")
        tax_lay = QVBoxLayout(tax_section)
        
        self.tax_scroll = QScrollArea()
        self.tax_scroll.setWidgetResizable(True)
        self.tax_container = QWidget()
        self.tax_v_lay = QVBoxLayout(self.tax_container)
        self.tax_v_lay.setContentsMargins(5, 5, 5, 5)
        self.tax_v_lay.setSpacing(5)
        self.tax_v_lay.addStretch()
        self.tax_scroll.setWidget(self.tax_container)
        tax_lay.addWidget(self.tax_scroll)
        
        self.add_tax_btn = QPushButton("+ Add Ledger")
        self.add_tax_btn.clicked.connect(lambda: self._add_tax_row())
        tax_lay.addWidget(self.add_tax_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.splitter.addWidget(tax_section)
        
        layout.addWidget(self.splitter, 1)

        # 5. Summary & Narration
        summary = QFrame()
        summary.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;")
        sum_lay = QHBoxLayout(summary)
        
        v_sum = QVBoxLayout()
        self.taxable_lbl = QLabel("Total Taxable: ₹ 0.00")
        self.gst_total_lbl = QLabel("Total GST: ₹ 0.00")
        self.grand_lbl = QLabel("GRAND TOTAL: ₹ 0.00")
        self.grand_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e3a8a;")
        v_sum.addWidget(self.taxable_lbl)
        v_sum.addWidget(self.gst_total_lbl)
        v_sum.addWidget(self.grand_lbl)
        sum_lay.addLayout(v_sum)
        
        sum_lay.addStretch()
        
        nar_lay = QVBoxLayout()
        nar_lay.addWidget(QLabel("Narration:"))
        self.narration = QLineEdit()
        self.narration.setPlaceholderText("Enter transaction details...")
        self.narration.setMinimumWidth(400)
        nar_lay.addWidget(self.narration)
        sum_lay.addLayout(nar_lay)
        layout.addWidget(summary)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load_data(self):
        try:
            self._ledgers = api.list_ledgers()
            self._items = api.list_stock_items()
            self._units = api.list_units()
            _groups = api.list_groups()
            self._is_dt_group = {g["_id"]: (g["name"] == "Duties & Taxes" or g.get("parent") == "Duties & Taxes") for g in _groups}
            
            # Find group IDs
            debtor_group_ids = [g["_id"] for g in _groups if g["name"] == "Sundry Debtors" or g.get("parent") == "Sundry Debtors"]
            sales_group_ids = [g["_id"] for g in _groups if g["name"] == "Sales Accounts" or g.get("parent") == "Sales Accounts"]

            # Filter Party Combo (Sundry Debtors only)
            self.party_cb.clear()
            self.party_cb.addItem("-- Select Party --", None)
            for l in self._ledgers:
                if l.get("group") in debtor_group_ids:
                    self.party_cb.addItem(l["name"], l["_id"])

            # Sales Return Combo (Sales Accounts only)
            self.ledger_cb.clear()
            self.ledger_cb.addItem("-- Select Ledger --", None)
            default_sales_return = None
            for l in self._ledgers:
                if l.get("group") in sales_group_ids:
                    self.ledger_cb.addItem(l["name"], l["_id"])
                    if not default_sales_return: default_sales_return = l["_id"]
            
            if default_sales_return:
                self.ledger_cb.setCurrentData(default_sales_return)

            # Only Sales Invoices
            invoices = api.list_vouchers(vtype="Sales", company_id=session.company_id)
            for inv in invoices:
                # Format: [Date] No - Party - Amount
                label = f"[{inv['date']}] {inv.get('voucher_no', 'N/A')} - {inv.get('party_name', 'N/A')} (₹{format_indian_number(inv.get('amount', 0))})"
                self.invoice_cb.addItem(label, inv)
            
        except Exception as e:
            QMessageBox.critical(self, "Data Error", f"Failed to load data: {str(e)}")

    def _on_invoice_selected(self, idx):
        if idx <= 0:
            self._original_invoice = None
            self._reset_ui()
            return
        
        inv_summary = self.invoice_cb.currentData()
        try:
            # Fetch full invoice AND stock transactions
            self._original_invoice = api.get_voucher(inv_summary["_id"])
            self._original_invoice["invoice_items"] = api.get_voucher_stock_txns(inv_summary["_id"])
            self._bind_invoice_data()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to fetch invoice details: {str(e)}")

    def _bind_invoice_data(self):
        inv = self._original_invoice
        
        # Identify Party and Sales Ledger from items if not present
        party_entry = next((it for it in inv.get("items", []) if it.get("dr_cr") == "Dr"), {})
        sales_entry = next((it for it in inv.get("items", []) if it.get("dr_cr") == "Cr" and "GST" not in it.get("ledger_name", "").upper()), {})
        
        party_name = inv.get("party_name")
        if not party_name or party_name == "N/A":
            party_name = party_entry.get("ledger_name", "N/A")
            
        party_id = inv.get("party_ledger_id") or party_entry.get("ledger_id")
        
        sales_ledger = inv.get("ledger_name")
        if not sales_ledger or sales_ledger == "Sales":
            sales_ledger = sales_entry.get("ledger_name", "Sales")
            
        sales_id = inv.get("sales_ledger_id") or sales_entry.get("ledger_id")
        
        # Cache them back for easier access and safety in _on_accept
        inv["party_name"] = party_name
        inv["party_ledger_id"] = party_id
        inv["ledger_name"] = sales_ledger
        inv["sales_ledger_id"] = sales_id
        
        self.party_cb.setCurrentData(party_id)
        self.ledger_cb.setCurrentData(sales_id)
        
        # Find GST type from entries if not in inv
        gst_type = inv.get("gst_type")
        if not gst_type:
            gst_type = "IGST" if any("IGST" in e.get("ledger_name", "").upper() for e in inv.get("items", [])) else "CGST+SGST"
        
        info_text = f"<b>GST Type:</b> {gst_type} | <b>Place of Supply:</b> {inv.get('place_of_supply', 'N/A')}"
        self.binding_info.setText(info_text)
        self._original_invoice["gst_type_calc"] = gst_type
        
        self._items_data = inv.get("invoice_items", [])
        self._refresh_table()
        
        # Clear and auto-detect tax ledgers from original invoice entries
        for r in list(self._tax_rows): self._remove_tax_row(r)
        
        # Auto-detect GST ledgers from original invoice entries
        tax_ledgers = [it for it in inv.get("items", []) if it.get("group_name") == "Duties & Taxes" or "GST" in it.get("ledger_name", "").upper()]
        for tl in tax_ledgers:
            self._add_tax_row(ledger_id=tl["ledger_id"])
            
        self._recalculate()

    def _on_reason_changed(self, idx):
        if idx <= 0:
            self.input_group.hide()
            return
        
        return_type = self.reason_cb.currentData()
        if "Value Adjustment" in return_type:
            self.input_group.show()
            self.reduction_label.setText("Total Reduction (Inclusive):" if "Inclusive" in return_type else "Taxable Reduction (Exclusive):")
        else:
            self.input_group.hide()
        
        self._recalculate()

    def _add_tax_row(self, ledger_id=None):
        row_w = QFrame()
        row_lay = QHBoxLayout(row_w)
        row_lay.setContentsMargins(0, 0, 0, 0)
        
        cb = SearchableComboBox()
        cb.addItem("-- Select Tax Ledger --", None)
        for l in self._ledgers:
            cb.addItem(l["name"], l["_id"])
        
        if ledger_id:
            cb.setCurrentData(ledger_id)
            
        amt = QDoubleSpinBox()
        amt.setRange(-99999999, 99999999); amt.setDecimals(2); amt.setPrefix("₹ ")
        amt.valueChanged.connect(self._update_summary_labels)
        
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet("color: red; font-weight: bold; border: none;")
        
        row_lay.addWidget(cb, 1)
        row_lay.addWidget(amt)
        row_lay.addWidget(del_btn)
        
        row_data = {"widget": row_w, "cb": cb, "amt": amt}
        del_btn.clicked.connect(lambda: self._remove_tax_row(row_data))
        
        self.tax_v_lay.insertWidget(len(self._tax_rows), row_w)
        self._tax_rows.append(row_data)
        return row_data

    def _remove_tax_row(self, row_data):
        if row_data in self._tax_rows:
            self._tax_rows.remove(row_data)
            row_data["widget"].deleteLater()
            self._update_summary_labels()

    def _refresh_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for item in self._items_data:
            self._add_row_from_data(item)
        self.table.blockSignals(False)

    def _add_row_from_data(self, item):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(item.get("item_name", "")))
        
        orig_qty = item.get("qty", 0)
        it_orig = QTableWidgetItem(str(orig_qty)); it_orig.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.table.setItem(row, 1, it_orig)
        
        self.table.setItem(row, 2, QTableWidgetItem("0"))
        self.table.setItem(row, 3, QTableWidgetItem(str(item.get("rate", 0))))
        self.table.setItem(row, 4, QTableWidgetItem("0.00"))
        
        gst_p = item.get("gst_rate", 0)
        it_gst = QTableWidgetItem(f"{gst_p}%"); it_gst.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.table.setItem(row, 5, it_gst)
        self.table.setItem(row, 6, QTableWidgetItem("0.00"))
        
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet("color: red; font-weight: bold; border: none;")
        del_btn.clicked.connect(lambda: self._remove_row(row))
        self.table.setCellWidget(row, 7, del_btn)

    def _remove_row(self, row):
        self.table.removeRow(row)
        self._recalculate()

    def _add_manual_item(self):
        # Open Item Entry Dialog similar to Sales Voucher
        from frontend.pages.invoice_voucher import ItemEntryDialog
        dlg = ItemEntryDialog(self, self._items, self._units)
        if dlg.exec():
            data = dlg.get_data()
            if data:
                # Map Sales Voucher Item format to Credit Note Table format
                item = {
                    "item_id": data["item_id"],
                    "item_name": data["item_name"],
                    "qty": 0, # Manual item has no "original" invoice qty context
                    "rate": data["rate"],
                    "gst_rate": data["gst_rate"],
                    "amount": data["amount"]
                }
                self.table.blockSignals(True)
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(item["item_name"]))
                it_orig = QTableWidgetItem("0"); it_orig.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(row, 1, it_orig)
                self.table.setItem(row, 2, QTableWidgetItem(str(data["qty"])))
                self.table.setItem(row, 3, QTableWidgetItem(str(data["rate"])))
                self.table.setItem(row, 4, QTableWidgetItem(str(data["amount"])))
                it_gst = QTableWidgetItem(f"{item['gst_rate']}%"); it_gst.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(row, 5, it_gst)
                self.table.setItem(row, 6, QTableWidgetItem(str(data["amount"] + data["cgst"] + data["sgst"] + data["igst"])))
                
                del_btn = QPushButton("✕")
                del_btn.setFixedSize(24, 24)
                del_btn.setStyleSheet("color: red; font-weight: bold; border: none;")
                del_btn.clicked.connect(lambda: self._remove_row(row))
                self.table.setCellWidget(row, 7, del_btn)
                
                self.table.blockSignals(False)
                self._recalculate()

    def _on_table_item_changed(self, item):
        self._recalculate()

    def _recalculate(self):
        if not self._original_invoice: return
        return_type = self.reason_cb.currentData()
        if not return_type: return
        
        total_taxable = 0
        tax_map = {} # Key: (type, rate), Value: amount
        
        self.table.blockSignals(True)
        
        if return_type == "Full Invoice Return":
            for i, item in enumerate(self._items_data):
                qty, rate, gst_p = item.get("qty", 0), item.get("rate", 0), item.get("gst_rate", 0)
                taxable = round(qty * rate, 2)
                gst_amt = round(taxable * gst_p / 100, 2)
                self.table.item(i, 2).setText(str(qty))
                self.table.item(i, 4).setText(f"{taxable:.2f}")
                self.table.item(i, 6).setText(f"{(taxable + gst_amt):.2f}")
                total_taxable += taxable
                self._distribute_gst(tax_map, gst_amt)

        elif "Value Adjustment" in return_type:
            X = self.reduction_amt.value()
            is_inc = "Inclusive" in return_type
            
            total_orig = sum(it.get("amount", 0) for it in self._items_data)
            if total_orig > 0:
                rows_to_process = []
                for i in range(self.table.rowCount()):
                    item_name = self.table.item(i, 0).text()
                    orig_item = next((it for it in self._items_data if it["item_name"] == item_name), None)
                    if orig_item:
                        rows_to_process.append((i, orig_item))
                
                accumulated_total_inc = 0 # Track running total of (taxable + gst)
                
                for idx, (i, orig_item) in enumerate(rows_to_process):
                    ratio = orig_item.get("amount", 0) / total_orig
                    alloc = X * ratio # Total share (inclusive if is_inc)
                    gst_p = orig_item.get("gst_rate", 0)
                    
                    if is_inc:
                        # Ensure sum(taxable + gst) == X exactly
                        if idx == len(rows_to_process) - 1:
                            target_inc_item = round(X - accumulated_total_inc, 2)
                        else:
                            target_inc_item = round(alloc, 2)
                        
                        # Taxable = Total / (1 + Rate/100)
                        taxable = round(target_inc_item / (1 + gst_p / 100), 2)
                        gst_amt = round(target_inc_item - taxable, 2)
                        accumulated_total_inc += round(taxable + gst_amt, 2)
                    else:
                        taxable = round(alloc, 2)
                        gst_amt = round(taxable * gst_p / 100, 2)
                            
                    self.table.item(i, 4).setText(f"{taxable:.2f}")
                    self.table.item(i, 6).setText(f"{(taxable + gst_amt):.2f}")
                    total_taxable += taxable
                    self._distribute_gst(tax_map, gst_amt, gst_p)

        elif return_type == "Invoice Items Return":
            for i in range(self.table.rowCount()):
                try:
                    qty_item = self.table.item(i, 2)
                    qty = float(qty_item.text() if qty_item else 0)
                    rate_item = self.table.item(i, 3)
                    rate = float(rate_item.text() if rate_item else 0)
                    
                    # Find GST rate from original items data by item name
                    item_name = self.table.item(i, 0).text()
                    orig_item = next((it for it in self._items_data if it["item_name"] == item_name), None)
                    gst_p = orig_item.get("gst_rate", 0) if orig_item else 0
                    
                    taxable = round(qty * rate, 2)
                    gst_amt = round(taxable * gst_p / 100, 2)
                    self.table.item(i, 4).setText(f"{taxable:.2f}")
                    self.table.item(i, 6).setText(f"{(taxable + gst_amt):.2f}")
                    total_taxable += taxable
                    self._distribute_gst(tax_map, gst_amt, gst_p)
                except (ValueError, AttributeError): pass

        self.table.blockSignals(False)
        
        # Auto-update or auto-add tax rows based on tax_map
        # Reset existing tax row amounts first (only those we manage)
        for r in self._tax_rows: r["amt"].setValue(0)
        
        def _get_or_add_tax_row(type_part, rate):
            rate_val = float(rate)
            rate_str = str(int(rate_val)) if rate_val == int(rate_val) else str(rate_val)
            
            # 1. Search existing rows for a match (by type and rate in name)
            for row in self._tax_rows:
                l_name = row["cb"].currentText().upper()
                if type_part in l_name and rate_str in l_name:
                    return row
            
            # 2. Search master ledgers for a matching name in D&T group
            for l in self._ledgers:
                l_name = l["name"].upper()
                if type_part in l_name and rate_str in l_name and self._is_dt_group.get(l.get("group")):
                    return self._add_tax_row(ledger_id=l["_id"])
            
            # 3. Fallback to generic if no rate-specific found (but don't overwrite another rate's ledger)
            for l in self._ledgers:
                l_name = l["name"].upper()
                if type_part in l_name and self._is_dt_group.get(l.get("group")):
                    if not any(c.isdigit() for c in l_name): # Basic check for generic
                        return self._add_tax_row(ledger_id=l["_id"])
            return None

        for (t_type, t_rate), amount in tax_map.items():
            if amount <= 0: continue
            row = _get_or_add_tax_row(t_type, t_rate)
            if row:
                row["amt"].setValue(row["amt"].value() + amount)
            
        self._update_summary_labels()

    def _distribute_gst(self, tax_map, total_gst, gst_rate):
        gst_type = self._original_invoice.get("gst_type_calc", "CGST+SGST")
        if gst_type == "IGST":
            key = ("IGST", gst_rate)
            tax_map[key] = tax_map.get(key, 0) + total_gst
        else:
            half_rate = gst_rate / 2
            key_c = ("CGST", half_rate)
            key_s = ("SGST", half_rate)
            tax_map[key_c] = tax_map.get(key_c, 0) + total_gst / 2
            tax_map[key_s] = tax_map.get(key_s, 0) + total_gst / 2

    def _update_summary_labels(self):
        total_taxable = 0
        for i in range(self.table.rowCount()):
            try: total_taxable += float(self.table.item(i, 4).text() or 0)
            except: pass
            
        total_gst = sum(r["amt"].value() for r in self._tax_rows)
        grand = total_taxable + total_gst
        
        self.taxable_lbl.setText(f"Total Taxable: {format_inr(total_taxable)}")
        self.gst_total_lbl.setText(f"Total GST: {format_inr(total_gst)}")
        self.grand_lbl.setText(f"GRAND TOTAL: {format_inr(grand)}")

    def _reset_ui(self):
        self.binding_info.setText("<i>Select an invoice to auto-bind details</i>")
        self.party_cb.setCurrentIndex(0)
        self.ledger_cb.setCurrentIndex(0)
        self.table.setRowCount(0)
        for r in list(self._tax_rows): self._remove_tax_row(r)
        self._update_summary_labels()

    def _on_accept(self):
        if not self._original_invoice:
            QMessageBox.warning(self, "Validation", "Select an original invoice"); return
        if self.reason_cb.currentIndex() <= 0:
            QMessageBox.warning(self, "Validation", "Select a reason"); return
            
        inv = self._original_invoice
        total_taxable = 0
        for i in range(self.table.rowCount()):
            try: total_taxable += float(self.table.item(i, 4).text() or 0)
            except: pass
        total_gst = sum(r["amt"].value() for r in self._tax_rows)
        grand_total = round(total_taxable + total_gst, 2)
        
        invoice_items = []
        for i in range(self.table.rowCount()):
            try:
                qty = float(self.table.item(i, 2).text() or 0)
                if qty <= 0 and self.reduction_amt.value() <= 0: continue
                rate = float(self.table.item(i, 3).text() or 0)
                taxable = float(self.table.item(i, 4).text() or 0)
                orig = self._items_data[i]
                invoice_items.append({
                    "item_id": orig["item_id"], "item_name": orig["item_name"],
                    "qty": qty, "rate": rate, "amount": taxable, "gst_rate": orig.get("gst_rate", 0)
                })
            except: continue

        if not invoice_items and grand_total <= 0:
            QMessageBox.warning(self, "Validation", "No items or reduction value calculated."); return

        # Entries
        party_id = self.party_cb.currentData()
        party_name = self.party_cb.currentText()
        if not party_id:
            QMessageBox.warning(self, "Validation", "Select a Party ledger"); return
            
        sales_id = self.ledger_cb.currentData()
        sales_name = self.ledger_cb.currentText()
        if not sales_id:
            QMessageBox.warning(self, "Validation", "Select a Sales Return ledger"); return
        
        entries = [
            {"ledger_id": party_id, "ledger_name": party_name, "dr_cr": "Cr", "amount": grand_total},
            {"ledger_id": sales_id, "ledger_name": sales_name, "dr_cr": "Dr", "amount": total_taxable}
        ]
        for r in self._tax_rows:
            if abs(r["amt"].value()) > 0.01:
                entries.append({"ledger_id": r["cb"].currentData(), "ledger_name": r["cb"].currentText(), "dr_cr": "Dr", "amount": r["amt"].value()})

        payload = {
            "voucher_type": "Credit Note", "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "narration": f"{self.reason_cb.currentText()} against Inv#{inv.get('voucher_no')} | {self.narration.text()}",
            "entries": entries, "company_id": session.company_id, "grand_total": grand_total,
            "invoice_items": invoice_items,
            "linking": {"reference_type": "Against Reference", "references": [{"voucher_id": inv["_id"], "amount": grand_total}]},
            "metadata": {"original_invoice_id": str(inv["_id"]), "reason": self.reason_cb.currentText(), "timestamp": QDate.currentDate().toString(Qt.DateFormat.ISODate)}
        }
        try:
            if self._existing: api.update_voucher(self._existing["_id"], payload)
            else: api.create_voucher(payload)
            self.accept()
        except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def _populate_existing(self, existing):
        try:
            self.date_edit.setDate(QDate.fromString(existing["date"], "yyyy-MM-dd"))
            self.narration.setText(existing.get("narration", ""))
            meta = existing.get("metadata", {})
            for i in range(1, self.invoice_cb.count()):
                if str(self.invoice_cb.itemData(i)["_id"]) == str(meta.get("original_invoice_id")):
                    self.invoice_cb.setCurrentIndex(i); break
            idx = self.reason_cb.findText(meta.get("reason", ""))
            if idx >= 0: self.reason_cb.setCurrentIndex(idx)
        except Exception as e: print(e)
