from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QFormLayout, QLineEdit,
    QDoubleSpinBox, QDialogButtonBox, QMessageBox, QHeaderView,
    QFrame, QComboBox, QGroupBox, QGridLayout, QScrollArea, QWidget, QSplitter, QSizePolicy
)
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt, QDate, Signal, QTimer
import frontend.api_client as api
from frontend.utils import SearchableComboBox, DateEdit, format_indian_number, format_inr, setup_enter_nav, wire_create_new
import frontend.session as session
import re

REASONS = [
    ("Purchase Return", "Invoice Items Return"),
    ("Partial Return", "Invoice Items Return"),
    ("Short Supply", "Invoice Value Adjustment (Inclusive)"),
    ("Overbilling Correction", "Invoice Value Adjustment (Inclusive)"),
    ("Wrong Price / Rate", "Invoice Value Adjustment (Exclusive)"),
    ("Wrong GST Rate", "Full Invoice Return"),
    ("Pre-agreed Discount", "Invoice Value Adjustment (Exclusive)"),
    ("Post-supply Discount", "Invoice Value Adjustment (Exclusive)"),
    ("Specific Item Discount", "Invoice Items Return"),
    ("Damaged Goods", "Invoice Items Return"),
    ("Cancelled Purchase", "Full Invoice Return"),
]

class DebitNoteDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Debit Note Entry")
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        self._existing = None
        self._items_data = []
        self._items = []
        self._original_invoice = None
        self._ledgers = []
        self._units = []
        self._tax_rows = []
        self._party_state = ""
        self._company_state = ""
        
        self._setup_ui()
        self._load_data()

    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()

    def set_voucher(self, voucher=None):
        self._reset_ui()
        self._existing = voucher
        if voucher:
            self.setWindowTitle(f"Edit Debit Note: {voucher.get('voucher_no')}")
            # Use singleShot to allow UI/Model to settle before populating
            QTimer.singleShot(100, lambda: self._populate_existing(voucher))
        else:
            self.date_edit.setDate(QDate.currentDate())
            self.narration.clear()
            self.invoice_cb.setCurrentIndex(0)
            self.reason_cb.setCurrentIndex(0)
            self.supplier_cn_no.clear()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header
        header = QFrame()
        header.setStyleSheet("background: #991b1b; border-radius: 8px; padding: 12px;") # Reddish for Debit Note / Purchase
        header_layout = QHBoxLayout(header)
        
        title = QLabel("DEBIT NOTE / PURCHASE RETURN")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: bold; margin-left: 10px;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        self.date_edit = DateEdit(QDate.currentDate())
        self.date_edit.setFixedWidth(120)
        header_layout.addWidget(QLabel("<span style='color: #fecaca'>Date:</span>"))
        header_layout.addWidget(self.date_edit)
        layout.addWidget(header)

        # Main Content Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content_w = QWidget()
        content_lay = QVBoxLayout(content_w)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(20)

        # 1. Selection & Info
        sel_group = QGroupBox("Invoice & Binding")
        sel_lay = QGridLayout(sel_group)
        sel_lay.setContentsMargins(15, 15, 15, 15)
        sel_lay.setSpacing(12)
        
        sel_lay.addWidget(QLabel("<b>Original Purchase Invoice:</b>"), 0, 0)
        self.invoice_cb = SearchableComboBox()
        self.invoice_cb.addItem("-- Select Invoice --", None)
        self.invoice_cb.currentIndexChanged.connect(self._on_invoice_selected)
        sel_lay.addWidget(self.invoice_cb, 0, 1)
        
        sel_lay.addWidget(QLabel("<b>Reason (Optional):</b>"), 0, 2)
        self.reason_cb = SearchableComboBox()
        self.reason_cb.addItem("-- Select Reason --")
        for r, t in REASONS:
            self.reason_cb.addItem(r, t)
        self.reason_cb.currentIndexChanged.connect(self._on_reason_changed)
        sel_lay.addWidget(self.reason_cb, 0, 3)

        sel_lay.addWidget(QLabel("<b>Supplier Name:</b>"), 1, 0)
        self.party_cb = SearchableComboBox()
        self.party_cb.addItem("-- Select Supplier --", None)
        self.party_cb.currentIndexChanged.connect(self._on_party_changed)
        sel_lay.addWidget(self.party_cb, 1, 1)

        sel_lay.addWidget(QLabel("<b>Purchase Return Ledger:</b>"), 1, 2)
        self.ledger_cb = SearchableComboBox()
        self.ledger_cb.addItem("-- Select Ledger --", None)
        sel_lay.addWidget(self.ledger_cb, 1, 3)

        sel_lay.addWidget(QLabel("<b>Supplier Credit Note No:</b>"), 2, 0)
        self.supplier_cn_no = QLineEdit()
        self.supplier_cn_no.setPlaceholderText("Ref. Supplier CN Number")
        sel_lay.addWidget(self.supplier_cn_no, 2, 1)

        self.binding_info = QLabel("<i>Select an invoice to auto-bind details</i>")
        self.binding_info.setStyleSheet("color: #991b1b; font-weight: 500; background: #fef2f2; padding: 8px; border-radius: 4px;")
        sel_lay.addWidget(self.binding_info, 3, 0, 1, 4)
        content_lay.addWidget(sel_group)

        # 2. Input Area (Value Adjustment)
        self.input_group = QGroupBox("Adjustment Value")
        input_lay = QHBoxLayout(self.input_group)
        input_lay.setContentsMargins(15, 15, 15, 15)
        self.reduction_label = QLabel("Reduction Amount:")
        self.reduction_amt = QDoubleSpinBox()
        self.reduction_amt.setRange(0, 99999999); self.reduction_amt.setDecimals(2)
        self.reduction_amt.setPrefix("₹ "); self.reduction_amt.setMinimumWidth(200)
        self.reduction_amt.setFixedHeight(36)
        self.reduction_amt.valueChanged.connect(self._recalculate)
        input_lay.addWidget(self.reduction_label)
        input_lay.addWidget(self.reduction_amt)
        input_lay.addStretch()
        self.input_group.hide()
        content_lay.addWidget(self.input_group)

        # 3. Items Section
        item_group = QGroupBox("Items")
        item_lay = QVBoxLayout(item_group)
        item_lay.setContentsMargins(15, 15, 15, 15)
        
        btn_lay = QHBoxLayout()
        self.add_item_btn = QPushButton("+ Add Manual &Item")
        self.add_item_btn.setStyleSheet("QPushButton { background: #991b1b; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px; } QPushButton:hover { background: #7f1d1d; }")
        self.add_item_btn.clicked.connect(self._add_manual_item)
        
        btn_lay.addStretch()
        btn_lay.addWidget(self.add_item_btn)
        item_lay.addLayout(btn_lay)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Item Name", "Orig. Qty", "Return Qty", "Rate (₹)", "Taxable Value", "GST %", "Total (₹)", "Action"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(250)
        self.table.itemChanged.connect(self._on_table_item_changed)
        item_lay.addWidget(self.table)
        content_lay.addWidget(item_group)

        # 4. Tax Ledgers
        tax_section = QGroupBox("Tax / Adjustment Ledgers")
        tax_lay = QVBoxLayout(tax_section)
        tax_lay.setContentsMargins(15, 15, 15, 15)
        
        self.tax_container = QWidget()
        self.tax_v_lay = QVBoxLayout(self.tax_container)
        self.tax_v_lay.setContentsMargins(0, 0, 0, 0)
        self.tax_v_lay.setSpacing(8)
        self.tax_v_lay.addStretch()
        tax_lay.addWidget(self.tax_container)
        
        self.add_tax_btn = QPushButton("+ Add Tax Ledger")
        self.add_tax_btn.setFixedWidth(150)
        self.add_tax_btn.setStyleSheet("QPushButton { background: #f1f5f9; border: 1px solid #cbd5e1; padding: 5px; border-radius: 4px; } QPushButton:hover { background: #e2e8f0; }")
        self.add_tax_btn.clicked.connect(lambda: self._add_tax_row())
        tax_lay.addWidget(self.add_tax_btn, 0, Qt.AlignmentFlag.AlignRight)
        content_lay.addWidget(tax_section)
        
        # 5. Summary & Narration
        summary_panel = QFrame()
        summary_panel.setStyleSheet("background: #fdf2f2; border: 1px solid #fee2e2; border-radius: 10px; padding: 20px;")
        sum_lay = QHBoxLayout(summary_panel)
        
        v_sum = QVBoxLayout()
        self.taxable_lbl = QLabel("Total Taxable: ₹ 0.00")
        self.taxable_lbl.setStyleSheet("font-size: 14px; color: #475569;")
        self.gst_total_lbl = QLabel("Total GST: ₹ 0.00")
        self.gst_total_lbl.setStyleSheet("font-size: 14px; color: #475569;")
        self.grand_lbl = QLabel("GRAND TOTAL: ₹ 0.00")
        self.grand_lbl.setStyleSheet("font-size: 24px; font-weight: bold; color: #991b1b;")
        v_sum.addWidget(self.taxable_lbl)
        v_sum.addWidget(self.gst_total_lbl)
        v_sum.addWidget(self.grand_lbl)
        sum_lay.addLayout(v_sum)
        
        sum_lay.addStretch()
        
        nar_lay = QVBoxLayout()
        nar_lay.addWidget(QLabel("<b>Narration:</b>"))
        self.narration = QLineEdit()
        self.narration.setPlaceholderText("Enter transaction details...")
        self.narration.setMinimumWidth(450)
        self.narration.setFixedHeight(40)
        self.narration.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px; background: white;")
        nar_lay.addWidget(self.narration)
        sum_lay.addLayout(nar_lay)
        content_lay.addWidget(summary_panel)

        self._rewire_nav()

        scroll.setWidget(content_w)
        layout.addWidget(scroll, 1)

        # Action Buttons
        actions_lay = QHBoxLayout()
        actions_lay.addStretch()
        
        self.cancel_btn = QPushButton("Discard Changes")
        self.cancel_btn.setFixedSize(140, 40)
        self.cancel_btn.setStyleSheet("QPushButton { background: white; color: #64748b; border: 1px solid #cbd5e1; border-radius: 6px; font-weight: bold; } QPushButton:hover { background: #f1f5f9; }")
        self.cancel_btn.clicked.connect(self.reject)
        actions_lay.addWidget(self.cancel_btn)
        
        self.save_btn = QPushButton("Save Debit Note")
        self.save_btn.setFixedSize(180, 40)
        self.save_btn.setStyleSheet("QPushButton { background: #991b1b; color: white; border-radius: 6px; font-weight: bold; font-size: 14px; } QPushButton:hover { background: #7f1d1d; }")
        self.save_btn.clicked.connect(self._on_accept)
        actions_lay.addWidget(self.save_btn)
        
        layout.addLayout(actions_lay)

    def _load_data(self):
        try:
            self._ledgers = api.list_ledgers()
            self._items = api.list_stock_items()
            self._units = api.list_units()
            _groups = api.list_groups()
            
            self._group_map = {str(g["_id"]): g["name"] for g in _groups}
            self._dt_group_id = next((str(g["_id"]) for g in _groups if g["name"] == "Duties & Taxes"), None)
            self._is_dt_group = {str(g["_id"]): (g["name"] == "Duties & Taxes" or (g.get("parent") or "") == "Duties & Taxes" or str(g.get("parent", "")) == self._dt_group_id) for g in _groups}
            
            self.party_cb.clear()
            self.party_cb.addItem("-- Select Supplier --", None)
            for l in self._ledgers:
                g_id = str(l.get("group", ""))
                g_name = self._group_map.get(g_id, "")
                if g_name == "Sundry Creditors":
                    self.party_cb.addItem(l["name"], l["_id"])

            self.ledger_cb.clear()
            self.ledger_cb.addItem("-- Select Ledger --", None)
            default_purchase_return = None
            for l in self._ledgers:
                g_id = str(l.get("group", ""))
                g_name = self._group_map.get(g_id, "")
                if g_name == "Purchase Accounts":
                    self.ledger_cb.addItem(l["name"], l["_id"])
                    if not default_purchase_return: default_purchase_return = l["_id"]
            
            if default_purchase_return:
                self.ledger_cb.setCurrentData(default_purchase_return)

            # "Create New Ledger" feature for party and ledger combos
            def _make_ledger_creator(target_combo):
                def _create_ledger():
                    from frontend.pages.ledger import LedgerDialog
                    try:
                        groups = api.list_groups()
                    except:
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
            
            try:
                comp = api.get_company(session.company_id)
                self._company_state = comp.get("state", "").strip().lower()
            except:
                self._company_state = ""

            res = api.list_vouchers(type="Purchase", company_id=session.company_id, limit=0)
            invoices = res.get("data", [])
            for inv in invoices:
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
            self._original_invoice = api.get_voucher(inv_summary["_id"])
            self._original_invoice["invoice_items"] = api.get_voucher_stock_txns(inv_summary["_id"])
            self._bind_invoice_data()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to fetch invoice details: {str(e)}")

    def _bind_invoice_data(self):
        inv = self._original_invoice
        v_entries = inv.get("entries") or inv.get("items") or []
        
        # Purchase Invoice: Party is Cr, Purchase is Dr
        party_entry = next((e for e in v_entries if e.get("dr_cr") == "Cr"), {})
        purchase_entry = next((e for e in v_entries if e.get("dr_cr") == "Dr" and "GST" not in e.get("ledger_name", "").upper()), {})
        
        party_name = inv.get("party_name") or party_entry.get("ledger_name", "N/A")
        party_id = inv.get("party_ledger_id") or party_entry.get("ledger_id")
        
        purchase_id = inv.get("purchase_ledger_id") or purchase_entry.get("ledger_id")
        
        if party_id:
            self.party_cb.setCurrentData(party_id)
        if purchase_id:
            self.ledger_cb.setCurrentData(purchase_id)
        
        # Display binding info
        self.binding_info.setText(f"<b>Linked to:</b> {inv.get('voucher_no')} | {party_name}")
        
        gst_type = inv.get("gst_type")
        if not gst_type:
            gst_type = "IGST" if any("IGST" in e.get("ledger_name", "").upper() for e in v_entries) else "CGST+SGST"
        
        info_text = f"<b>GST Type:</b> {gst_type} | <b>Place of Supply:</b> {inv.get('place_of_supply', 'N/A')}"
        self.binding_info.setText(info_text)
        self._original_invoice["gst_type_calc"] = gst_type
        
        self._items_data = inv.get("invoice_items", [])
        self._refresh_table()
        
        for r in list(self._tax_rows): self._remove_tax_row(r)
        
        tax_ledgers = [it for it in v_entries if it.get("group_name") == "Duties & Taxes" or "GST" in it.get("ledger_name", "").upper()]
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
        amt.setFixedHeight(32)
        amt.valueChanged.connect(self._update_summary_labels)
        
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet("color: red; font-weight: bold; border: none; background: transparent;")
        
        row_lay.addWidget(cb, 1)
        row_lay.addWidget(amt)
        row_lay.addWidget(del_btn)
        
        row_data = {"widget": row_w, "cb": cb, "amt": amt, "is_auto_tax": False}
        del_btn.clicked.connect(lambda: self._remove_tax_row(row_data))
        
        self.tax_v_lay.insertWidget(len(self._tax_rows), row_w)
        self._tax_rows.append(row_data)
        self._rewire_nav()
        return row_data

    def _remove_tax_row(self, row_data):
        if row_data in self._tax_rows:
            self._tax_rows.remove(row_data)
            row_data["widget"].deleteLater()
            self._update_summary_labels()
            self._rewire_nav()

    def _rewire_nav(self):
        widgets = [
            self.date_edit, self.invoice_cb, self.reason_cb,
            self.party_cb, self.ledger_cb, self.supplier_cn_no
        ]
        for row in self._tax_rows:
            widgets.append(row["cb"])
            widgets.append(row["amt"])
        widgets.append(self.reduction_amt)
        widgets.append(self.narration)
        setup_enter_nav(self, widgets)

    def _refresh_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for item in self._items_data:
            self._add_row_from_data(item)
        self.table.blockSignals(False)

    def _add_row_from_data(self, item):
        row = self.table.rowCount()
        self.table.insertRow(row)
        it_name = QTableWidgetItem(item.get("item_name", ""))
        it_name.setData(Qt.ItemDataRole.UserRole, item.get("item_id"))
        self.table.setItem(row, 0, it_name)
        
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
        del_btn.setStyleSheet("color: red; font-weight: bold; border: none; background: transparent;")
        del_btn.clicked.connect(lambda: self._remove_row(row))
        self.table.setCellWidget(row, 7, del_btn)

    def _remove_row(self, row):
        self.table.removeRow(row)
        self._recalculate()

    def _add_manual_item(self):
        from frontend.pages.invoice_voucher import ItemEntryDialog
        dlg = ItemEntryDialog(self, self._items, self._units)
        if dlg.exec():
            data = dlg.get_data()
            if data:
                item = {
                    "item_id": data["item_id"],
                    "item_name": data["item_name"],
                    "qty": 0,
                    "rate": data["rate"],
                    "gst_rate": data["gst_rate"],
                    "amount": data["amount"]
                }
                self.table.blockSignals(True)
                row = self.table.rowCount()
                self.table.insertRow(row)
                it_name = QTableWidgetItem(item["item_name"])
                it_name.setData(Qt.ItemDataRole.UserRole, item["item_id"])
                self.table.setItem(row, 0, it_name)
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
                del_btn.setStyleSheet("color: red; font-weight: bold; border: none; background: transparent;")
                del_btn.clicked.connect(lambda: self._remove_row(row))
                self.table.setCellWidget(row, 7, del_btn)
                
                self.table.blockSignals(False)
                self._recalculate()

    def _on_table_item_changed(self, item):
        self._recalculate()

    def _find_ledger_by_name(self, name):
        # 1. Exact match
        for l in self._ledgers:
            if l["name"].strip().lower() == name.strip().lower():
                return l
        
        # 2. Loose match for tax ledgers
        lname_upper = name.strip().upper()
        if any(x in lname_upper for x in ["CGST", "SGST", "IGST"]):
            target_type = None
            for t in ["CGST", "SGST", "IGST"]:
                if t in lname_upper:
                    target_type = t; break
            
            rate_match = re.search(r"(\d+\.?\d*)", lname_upper)
            target_rate = rate_match.group(1) if rate_match else None
            
            if target_type and target_rate:
                for l in self._ledgers:
                    if not self._is_dt_group.get(l.get("group")): continue
                    ln = l["name"].upper()
                    if target_type in ln and target_rate in ln:
                        # For Debit Note (Purchase Return), we reverse Input tax
                        if "SALES" in ln or "OUTPUT" in ln: continue
                        return l
        return None

    def _on_party_changed(self, idx):
        if idx <= 0:
            self._party_state = ""
            self._recalculate()
            return
        
        ledger_id = self.party_cb.currentData()
        try:
            ledger = api.get_ledger(ledger_id)
            self._party_state = ledger.get("state", "").strip().lower() if ledger else ""
        except:
            self._party_state = ""
        self._recalculate()

    def _recalculate(self):
        return_type = self.reason_cb.currentData()
        effective_return_type = return_type or "Invoice Items Return"
        
        if self._original_invoice:
            gst_type = self._original_invoice.get("gst_type_calc", "CGST+SGST")
        elif self._party_state:
            is_intra = (self._company_state == self._party_state) or not self._company_state or not self._party_state
            gst_type = "CGST+SGST" if is_intra else "IGST"
        else:
            gst_type = "CGST+SGST"
        
        total_taxable = 0
        tax_map = {}
        
        self.table.blockSignals(True)
        
        if effective_return_type == "Full Invoice Return" and self._original_invoice:
            for i, item in enumerate(self._items_data):
                qty, rate, gst_p = item.get("qty", 0), item.get("rate", 0), item.get("gst_rate", 0)
                taxable = round(qty * rate, 2)
                gst_amt = round(taxable * gst_p / 100, 2)
                self.table.item(i, 2).setText(str(qty))
                self.table.item(i, 4).setText(f"{taxable:.2f}")
                self.table.item(i, 6).setText(f"{(taxable + gst_amt):.2f}")
                total_taxable += taxable
                self._distribute_gst(tax_map, gst_amt, gst_p, gst_type)

        elif "Value Adjustment" in effective_return_type and self._original_invoice:
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
                
                accumulated_total_inc = 0
                
                for idx, (i, orig_item) in enumerate(rows_to_process):
                    ratio = orig_item.get("amount", 0) / total_orig
                    alloc = X * ratio
                    gst_p = orig_item.get("gst_rate", 0)
                    
                    if is_inc:
                        if idx == len(rows_to_process) - 1:
                            target_inc_item = round(X - accumulated_total_inc, 2)
                        else:
                            target_inc_item = round(alloc, 2)
                        
                        taxable = round(target_inc_item / (1 + gst_p / 100), 2)
                        gst_amt = round(target_inc_item - taxable, 2)
                        accumulated_total_inc += round(taxable + gst_amt, 2)
                    else:
                        taxable = round(alloc, 2)
                        gst_amt = round(taxable * gst_p / 100, 2)
                            
                    self.table.item(i, 4).setText(f"{taxable:.2f}")
                    self.table.item(i, 6).setText(f"{(taxable + gst_amt):.2f}")
                    total_taxable += taxable
                    self._distribute_gst(tax_map, gst_amt, gst_p, gst_type)

        elif effective_return_type == "Invoice Items Return" or not self._original_invoice:
            for i in range(self.table.rowCount()):
                try:
                    qty_item = self.table.item(i, 2)
                    qty = float(qty_item.text() if qty_item else 0)
                    rate_item = self.table.item(i, 3)
                    rate = float(rate_item.text() if rate_item else 0)
                    
                    item_name = self.table.item(i, 0).text()
                    orig_item = next((it for it in self._items_data if it["item_name"] == item_name), None)
                    if orig_item:
                        gst_p = orig_item.get("gst_rate", 0)
                    else:
                        try:
                            gst_text = self.table.item(i, 5).text().replace("%", "")
                            gst_p = float(gst_text)
                        except:
                            gst_p = 0
                    
                    taxable = round(qty * rate, 2)
                    gst_amt = round(taxable * gst_p / 100, 2)
                    self.table.item(i, 4).setText(f"{taxable:.2f}")
                    self.table.item(i, 6).setText(f"{(taxable + gst_amt):.2f}")
                    total_taxable += taxable
                    self._distribute_gst(tax_map, gst_amt, gst_p, gst_type)
                except (ValueError, AttributeError): pass

        self.table.blockSignals(False)
        
        # ── Sync Tax Rows ────────────────────────────────────────────────────
        needed_grouped = {} 
        prefix = "Purchase" # Debit Note is a Purchase Return
        
        for (ttype, trate), tamount in tax_map.items():
            if tamount <= 0: continue
            
            rate_val = float(trate)
            lname = f"{prefix} {ttype}@{rate_val:g}%"
            match = self._find_ledger_by_name(lname)
            
            if not match:
                rate_str = str(int(rate_val)) if rate_val == int(rate_val) else f"{rate_val:g}"
                for l in self._ledgers:
                    if not self._is_dt_group.get(str(l.get("group"))): continue
                    ln = l["name"].upper()
                    if ttype in ln and rate_str in ln and any(x in ln for x in ["PURCHASE", "INPUT"]):
                        match = l; break

            # Still no match? Auto-create
            if not match and self._dt_group_id:
                try:
                    # Debit Note is a Purchase Return, so we use Purchase tax ledgers (Input/Dr normally, but Credit in DN)
                    # But the ledger's NATURAL type should be Dr (as it's an Asset/Tax ledger)
                    resp = api.create_ledger({
                        "name": lname,
                        "group": self._dt_group_id,
                        "tax_rate": rate_val,
                        "opening_balance": 0,
                        "type": "Dr"
                    })
                    match = {
                        "_id": resp.get("id", ""),
                        "name": lname,
                        "group": self._dt_group_id,
                        "tax_rate": rate_val
                    }
                    self._ledgers.append(match)
                    self._is_dt_group[str(match["_id"])] = True
                except Exception as e:
                    print(f"Error auto-creating DN tax ledger {lname}: {e}")
            
            if match:
                lid = match["_id"]
                needed_grouped[lid] = (match, needed_grouped.get(lid, (match, 0))[1] + tamount)

        final_needed = list(needed_grouped.values())

        for row in list(self._tax_rows):
            l_id = row["cb"].currentData()
            match_data = next((x for x in final_needed if x[0]["_id"] == l_id), None)
            
            if match_data:
                nl, namt = match_data
                row["amt"].setValue(namt)
                row["is_auto_tax"] = True 
                final_needed.remove(match_data)
            elif row.get("is_auto_tax"):
                self._remove_tax_row(row)

        for nl, namt in final_needed:
            new_row = self._add_tax_row(ledger_id=nl["_id"])
            new_row["is_auto_tax"] = True
            new_row["amt"].setValue(namt)
            
        self._update_summary_labels()

    def _distribute_gst(self, tax_map, total_gst, gst_rate, gst_type):
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
        self.supplier_cn_no.clear()
        for r in list(self._tax_rows): self._remove_tax_row(r)
        self._update_summary_labels()

    def _on_accept(self):
        inv = self._original_invoice or {}
        reason = self.reason_cb.currentText() if self.reason_cb.currentIndex() > 0 else "Debit Note"
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
                
                # Validation: Return qty <= Orig qty
                orig_qty = float(self.table.item(i, 1).text() or 0)
                if self._original_invoice and qty > orig_qty:
                    QMessageBox.warning(self, "Validation", f"Return quantity for {self.table.item(i, 0).text()} exceeds original purchase quantity."); return

                rate = float(self.table.item(i, 3).text() or 0)
                taxable = float(self.table.item(i, 4).text() or 0)
                item_name = self.table.item(i, 0).text()
                item_id = self.table.item(i, 0).data(Qt.ItemDataRole.UserRole)
                
                gst_text = self.table.item(i, 5).text().replace("%", "")
                gst_rate = float(gst_text) if gst_text else 0
                
                if not item_id:
                    orig = next((it for it in self._items_data if it["item_name"] == item_name), None)
                    if orig:
                        item_id = orig["item_id"]
                        gst_rate = orig.get("gst_rate", 0)

                if item_id:
                    invoice_items.append({
                        "item_id": item_id, "item_name": item_name,
                        "qty": qty, "rate": rate, "amount": taxable, "gst_rate": gst_rate
                    })
            except Exception as e:
                print(f"Error extracting row {i}: {e}")
                continue

        if not invoice_items and grand_total <= 0:
            QMessageBox.warning(self, "Validation", "No items or reduction value calculated."); return

        # Validation: Debit Note amount <= Original invoice amount (or outstanding if preferred)
        if self._original_invoice:
            total_inv = self._original_invoice.get("amount", 0)
            # Use Original Total as the limit to allow returns on paid invoices
            limit = total_inv
            
            if self._existing: # If editing, we compare against original total
                pass 
                
            if grand_total > limit + 0.01:
                QMessageBox.warning(self, "Validation", f"Debit Note amount (₹{grand_total}) exceeds original invoice total (₹{limit})."); return

        party_id = self.party_cb.currentData()
        party_name = self.party_cb.currentText()
        if not party_id:
            QMessageBox.warning(self, "Validation", "Select a Supplier ledger"); return
            
        purchase_id = self.ledger_cb.currentData()
        purchase_name = self.ledger_cb.currentText()
        if not purchase_id:
            QMessageBox.warning(self, "Validation", "Select a Purchase Return ledger"); return
        
        # Accounting logic for Debit Note (Purchase Return):
        # Supplier A/c: Dr
        # Purchase Return: Cr
        # Tax Ledgers: Cr
        
        entries = [
            {"ledger_id": party_id, "ledger_name": party_name, "dr_cr": "Dr", "amount": grand_total},
            {"ledger_id": purchase_id, "ledger_name": purchase_name, "dr_cr": "Cr", "amount": total_taxable}
        ]
        
        for r in self._tax_rows:
            amt = r["amt"].value()
            if abs(amt) > 0.005:
                entries.append({
                    "ledger_id": r["cb"].currentData(),
                    "ledger_name": r["cb"].currentText(),
                    "dr_cr": "Dr" if amt < 0 else "Cr",
                    "amount": abs(amt)
                })

        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        
        # Meta info
        metadata = {
            "original_invoice_id": str(inv.get("_id")) if inv.get("_id") else None,
            "original_invoice_no": inv.get("voucher_no"),
            "supplier_cn_no": self.supplier_cn_no.text().strip(),
            "reason": reason,
            "reduction_amt": self.reduction_amt.value(),
            "return_type": self.reason_cb.currentData() or "Invoice Items Return"
        }
        
        payload = {
            "voucher_type": "Debit Note",
            "date": date_str,
            "narration": self.narration.text().strip() or f"Purchase return against Inv# {inv.get('voucher_no', 'N/A')}",
            "entries": entries,
            "invoice_items": invoice_items,
            "grand_total": grand_total,
            "metadata": metadata
        }

        if self._original_invoice:
            payload["reference_type"] = "Against Reference"
            payload["linking"] = {
                "reference_type": "Against Reference",
                "references": [
                    {"voucher_id": str(inv["_id"]), "amount": grand_total, "reference_type": "Against Reference"}
                ]
            }

        try:
            if self._existing:
                api.update_voucher(self._existing["_id"], payload)
                QMessageBox.information(self, "Success", "Debit Note updated successfully.")
            else:
                api.create_voucher(payload)
                QMessageBox.information(self, "Success", "Debit Note saved successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save Debit Note: {str(e)}")

    def _populate_existing(self, v):
        self.date_edit.setDate(QDate.fromString(v["date"], "yyyy-MM-dd"))
        self.narration.setText(v.get("narration", ""))
        
        meta = v.get("metadata", {})
        self.supplier_cn_no.setText(meta.get("supplier_cn_no", ""))
        
        reason = meta.get("reason", "")
        if reason:
            idx = self.reason_cb.findText(reason)
            if idx >= 0: self.reason_cb.setCurrentIndex(idx)
        
        self.reduction_amt.setValue(meta.get("reduction_amt", 0))
        
        orig_id = meta.get("original_invoice_id")
        if orig_id:
            # Find in invoice_cb
            for i in range(self.invoice_cb.count()):
                data = self.invoice_cb.itemData(i)
                if data and str(data.get("_id")) == str(orig_id):
                    self.invoice_cb.setCurrentIndex(i)
                    break
        else:
            # Manually set party and ledger if no original invoice linked
            self.party_cb.setCurrentData(v.get("party_ledger_id"))
            # Find purchase/purchase return ledger from entries
            for e in v.get("entries", []):
                if e["dr_cr"] == "Cr" and "GST" not in e["ledger_name"].upper():
                    self.ledger_cb.setCurrentData(e["ledger_id"])
                    break

        # Load items
        items = v.get("invoice_items", [])
        if items:
            self.table.blockSignals(True)
            self.table.setRowCount(0)
            for it in items:
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                # Check if we have original qty in meta or somewhere
                # For now just use it.qty as return qty
                it_name = QTableWidgetItem(it["item_name"])
                it_name.setData(Qt.ItemDataRole.UserRole, it["item_id"])
                self.table.setItem(row, 0, it_name)
                
                self.table.setItem(row, 1, QTableWidgetItem("0")) # Orig Qty unknown unless linked
                self.table.setItem(row, 2, QTableWidgetItem(str(it["qty"])))
                self.table.setItem(row, 3, QTableWidgetItem(str(it["rate"])))
                self.table.setItem(row, 4, QTableWidgetItem(str(it["amount"])))
                
                gst_p = it.get("gst_rate", 0)
                it_gst = QTableWidgetItem(f"{gst_p}%"); it_gst.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(row, 5, it_gst)
                self.table.setItem(row, 6, QTableWidgetItem(str(round(it["amount"] * (1 + gst_p/100), 2))))
                
                del_btn = QPushButton("✕")
                del_btn.setFixedSize(24, 24)
                del_btn.setStyleSheet("color: red; font-weight: bold; border: none; background: transparent;")
                del_btn.clicked.connect(lambda: self._remove_row(row))
                self.table.setCellWidget(row, 7, del_btn)
            self.table.blockSignals(False)

        # Load tax rows
        for r in list(self._tax_rows): self._remove_tax_row(r)
        
        # Determine main IDs to skip (party and purchase return)
        party_id = self.party_cb.currentData()
        purchase_id = self.ledger_cb.currentData()
        
        for e in v.get("entries", []):
            if e["ledger_id"] not in [party_id, purchase_id]:
                row = self._add_tax_row(ledger_id=e["ledger_id"])
                val = e["amount"]
                # For Debit Note, base direction for adjustments/taxes is Cr
                if e["dr_cr"] == "Dr":
                    val = -val
                row["amt"].setValue(val)
        
        self._recalculate()
