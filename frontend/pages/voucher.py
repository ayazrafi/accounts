from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QDoubleSpinBox, QDialogButtonBox,
    QMessageBox, QHeaderView, QScrollArea, QFrame, QTextEdit,
    QGridLayout, QSizePolicy, QCheckBox, QComboBox
)
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt, QDate, QSize, Signal, QTimer, QEvent
import frontend.api_client as api
from frontend.utils import setup_enter_nav, SearchableComboBox, wire_create_new, wire_edit_selected, DateEdit, get_icon, format_indian_number, format_inr
import frontend.session as session
from frontend.utils.excel_export import export_sales_register

INVOICE_TYPES = {"Sales", "Purchase", "Credit Note", "Debit Note"}
JOURNAL_TYPES = {"Payment", "Receipt", "Journal", "Contra"}

from frontend.pages.invoice_voucher import InvoiceVoucherDialog
# from frontend.pages.credit_note import CreditNoteDialog




class InvoicePrintOptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Invoice Print Options")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self):
        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(10)

        self.invoice_type = QComboBox()
        self.invoice_type.addItems(["A", "B", "C"])
        
        self.copy_type = QComboBox()
        self.copy_type.addItems(["Single", "Multiple (3 Copies)"])

        form.addRow("Invoice Type", self.invoice_type)
        form.addRow("Copy Type", self.copy_type)

        self.btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)
        form.addRow(self.btns)

        setup_enter_nav(self, [self.invoice_type, self.copy_type], self.accept)

    def get_data(self):
        # Convert "Multiple (3 Copies)" back to "Multiple" for backend/pdf compatibility
        copy = "Multiple" if "Multiple" in self.copy_type.currentText() else "Single"
        return {
            "invoice_type": self.invoice_type.currentText(),
            "copy_type": copy,
        }

# Simplified restoration of classes to ensure I don't miss anything.
# I will just apply the validation logic to the existing classes.

class JournalEntryRow(QWidget):
    def __init__(self, ledgers, dr_cr_default="Dr", parent=None):
        super().__init__(parent)
        self._ledgers = ledgers
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0,2,0,2); layout.setSpacing(6)
        self.by_to = QLabel("By" if dr_cr_default == "Dr" else "To")
        self.by_to.setFixedWidth(24)
        self.by_to.setStyleSheet("font-weight:bold;color:#1565C0;")
        self.dr_cr = SearchableComboBox(); self.dr_cr.addItems(["Dr","Cr"])
        self.dr_cr.setCurrentText(dr_cr_default); self.dr_cr.setFixedWidth(55)
        self.dr_cr.currentTextChanged.connect(
            lambda t: self.by_to.setText("By" if t == "Dr" else "To"))
        self.ledger_cb = SearchableComboBox(); self.ledger_cb.setMinimumWidth(220)
        for l in ledgers: self.ledger_cb.addItem(l["name"], l["_id"])
        self.ledger_cb.currentIndexChanged.connect(self._show_balance)

        # "Create New Ledger" option
        def _create_ledger():
            from frontend.pages.ledger import LedgerDialog
            try:
                groups = api.list_groups()
            except Exception:
                groups = []
            dlg = LedgerDialog(self.window(), groups)
            if dlg.exec():
                data = dlg.get_data()
                try:
                    resp = api.create_ledger(data)
                    new_l = {"_id": resp.get("id", ""), "name": data["name"]}
                    self._ledgers.append(new_l)
                    return (data["name"], new_l["_id"])
                except Exception as ex:
                    QMessageBox.warning(self.window(), "Error", str(ex))
            return None
        wire_create_new(self.ledger_cb, _create_ledger)

        def _edit_journal_ledger(ledger_id):
            from frontend.pages.ledger import LedgerDialog
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
            dlg = LedgerDialog(self.window(), groups, data=ledger)
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
                    QMessageBox.warning(self.window(), "Error", str(ex))
            return None
        wire_edit_selected(self.ledger_cb, _edit_journal_ledger)

        self.balance_lbl = QLabel("")
        self.balance_lbl.setStyleSheet("color:#0277BD;font-size:11px;font-style:italic;")
        self.balance_lbl.setFixedWidth(160)
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 999999999); self.amount.setDecimals(2)
        self.amount.setFixedWidth(130); self.amount.setPrefix("\u20b9 ")
        layout.addWidget(self.by_to); layout.addWidget(self.dr_cr)
        layout.addWidget(self.ledger_cb, 1); layout.addWidget(self.balance_lbl)
        layout.addWidget(QLabel("Amount:")); layout.addWidget(self.amount)
        setup_enter_nav(self, [self.dr_cr, self.ledger_cb, self.amount])

    def _show_balance(self, idx):
        if idx < 0 or idx >= len(self._ledgers): return
        try:
            bal = api.ledger_balance(self._ledgers[idx]["_id"])
            self.balance_lbl.setText(f"Cur Bal: {format_indian_number(bal['balance'])} {bal['type']}")
        except Exception: self.balance_lbl.setText("")

    def get_entry(self):
        idx = self.ledger_cb.currentIndex()
        if idx < 0 or idx >= len(self._ledgers) or self.amount.value() == 0: return None
        l = self._ledgers[idx]
        return {"ledger_id": l["_id"], "ledger_name": l["name"],
                "dr_cr": self.dr_cr.currentText(), "amount": self.amount.value()}
    def set_entry(self, entry):
        self.dr_cr.setCurrentText(entry.get("dr_cr", "Dr"))
        self.ledger_cb.setCurrentData(entry.get("ledger_id"))
        self.amount.setValue(entry.get("amount", 0))


class PaymentReceiptDialog(QDialog):
    def __init__(self, parent, vtype, existing=None):
        super().__init__(parent)
        self.vtype = vtype
        self.existing = existing
        self._vid = existing["_id"] if existing else None
        self.setWindowTitle(f"{'Edit ' if existing else ''}{vtype} Voucher")
        self.setMinimumSize(750, 600)
        self.setStyleSheet("QDialog { background: #ffffff; }")
        
        try:
            self._ledgers = api.list_ledgers()
            groups = api.list_groups()
            self._group_map = {g["_id"]: g["name"] for g in groups}
        except Exception:
            self._ledgers = []; self._group_map = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        
        # ── Header ────────────────────────────────────────────────────────────
        self.hdr = QFrame()
        self.hdr.setObjectName("hdr")
        self.hdr.setMinimumHeight(80); self.hdr.setMaximumHeight(80)
        color1 = "#1e3a5f" if vtype == "Payment" else "#065f46"
        color2 = "#3b82f6" if vtype == "Payment" else "#10b981"
        self.hdr.setStyleSheet(f"QFrame#hdr {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color1}, stop:1 {color2}); }}")
        hdr_lay = QHBoxLayout(self.hdr)
        hdr_lay.setContentsMargins(24, 0, 24, 0)
        
        v_icon = QLabel()
        v_icon.setPixmap(get_icon("frontend/assets/icons/file-text.svg", "#ffffff").pixmap(32, 32))
        hdr_lay.addWidget(v_icon)
        
        v_title_lay = QVBoxLayout()
        v_title_lay.setSpacing(0); v_title_lay.setContentsMargins(8, 0, 0, 0)
        vt_lbl = QLabel(vtype.upper())
        vt_lbl.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold; letter-spacing: 1px;")
        v_subtitle = QLabel("Accounting Voucher")
        v_subtitle.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 11px;")
        v_title_lay.addStretch(); v_title_lay.addWidget(vt_lbl); v_title_lay.addWidget(v_subtitle); v_title_lay.addStretch()
        hdr_lay.addLayout(v_title_lay); hdr_lay.addStretch()
        
        # Date Pill
        self.date_pill = QFrame()
        self.date_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.date_pill.setStyleSheet("background: rgba(255,255,255,0.1); border-radius: 8px; padding: 4px 12px;")
        date_lay = QHBoxLayout(self.date_pill)
        cal_icon = QLabel()
        cal_icon.setPixmap(get_icon("frontend/assets/icons/calendar.svg", "#ffffff").pixmap(18, 18))
        date_lay.addWidget(cal_icon)
        
        initial_date = QDate.currentDate()
        if existing and existing.get("date"):
            initial_date = QDate.fromString(existing["date"], "yyyy-MM-dd")
        
        self.date_edit = DateEdit(initial_date)
        self.date_edit.setCalendarPopup(True); self.date_edit.setDisplayFormat("d-MMM-yy")
        self.date_edit.setFixedWidth(110)
        self.date_edit.setStyleSheet("background: transparent; color: #ffffff; border: none; font-weight: bold; font-size: 14px;")
        date_lay.addWidget(self.date_edit)
        hdr_lay.addWidget(self.date_pill)
        self.date_pill.mousePressEvent = lambda e: self.date_edit.showPopup()
        root.addWidget(self.hdr)

        # ── Form Content ──────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(24, 24, 24, 24); content_lay.setSpacing(20)
        
        def _add_section(title, widget):
            box = QVBoxLayout()
            box.setSpacing(6)
            lbl = QLabel(title)
            lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748b; letter-spacing: 0.5px;")
            box.addWidget(lbl); box.addWidget(widget)
            content_lay.addLayout(box)

        # 1. Cash/Bank
        self.cb_ledger = SearchableComboBox(); self.cb_ledger.setMinimumHeight(42)
        self.cb_ledger.addItem("-- Select Cash/Bank --", None)
        for l in self._ledgers:
            g_name = self._group_map.get(str(l.get("group", "")), "")
            if g_name in ["Cash-in-Hand", "Bank Accounts"]:
                self.cb_ledger.addItem(l["name"], l["_id"])
        _add_section("CASH / BANK ACCOUNT", self.cb_ledger)

        # 2. Party
        party_title = "CUSTOMER (DEBTOR)" if vtype == "Receipt" else "SUPPLIER / EXPENSE"
        self.party_ledger = SearchableComboBox(); self.party_ledger.setMinimumHeight(42)
        self.party_ledger.addItem("-- Select Party --", None)
        
        # Groups that are never valid for the party side of a Payment/Receipt
        _cb_groups = {"Cash-in-Hand", "Bank Accounts"}             # always on the cash/bank side
        _invalid_groups = {"Sales Accounts", "Purchase Accounts"}  # blocked by AccountingEngine
        # Note: 'Duties & Taxes' is allowed — e.g. GST Deposit is a valid Payment

        for l in self._ledgers:
            g_name = self._group_map.get(str(l.get("group", "")), "")
            if g_name in _cb_groups or g_name in _invalid_groups:
                continue  # skip cash/bank and invalid ledgers
            if vtype == "Receipt":
                # Receipt: show Debtors + Suspense A/c (for unclassified receipts)
                if g_name in ["Sundry Debtors", "Suspense A/c", "Suspense Account", "Suspense"]:
                    self.party_ledger.addItem(l["name"], l["_id"])
            else:
                # Payment: show all valid ledgers (Creditors, Expenses, Suspense, Capital, Loans, etc.)
                self.party_ledger.addItem(l["name"], l["_id"])
        self.party_ledger.currentIndexChanged.connect(self._on_party_changed)
        _add_section(party_title, self.party_ledger)

        # 3. Amount
        self.amount = QDoubleSpinBox(); self.amount.setRange(0, 999999999); self.amount.setDecimals(2)
        self.amount.setMinimumHeight(52); self.amount.setPrefix("₹ ")
        self.amount.setStyleSheet("font-size: 20px; font-weight: bold; color: #1e3a5f; border: 2px solid #e2e8f0; border-radius: 8px; padding: 0 12px; background: #f8fafc;")
        _add_section("AMOUNT", self.amount)

        # 3.5 Reference Type
        self.ref_type = SearchableComboBox(); self.ref_type.setMinimumHeight(42)
        self.ref_type.addItems(["On Account", "Against Reference"])
        self.ref_type.currentTextChanged.connect(self._on_ref_type_changed)
        _add_section("REFERENCE TYPE", self.ref_type)

        # 4. Linking
        self.link_frame = QFrame(); self.link_frame.setObjectName("link_frame")
        self.link_frame.setStyleSheet("QFrame#link_frame { background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 10px; }")
        self.link_frame.setVisible(False)
        link_lay = QVBoxLayout(self.link_frame); link_lay.setContentsMargins(16, 12, 16, 16)
        link_title = QLabel("BILL-WISE DETAILS (AGAINST REFERENCE)")
        link_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #475569;")
        link_lay.addWidget(link_title)
        
        self.link_table = QTableWidget(0, 6)
        self.link_table.setHorizontalHeaderLabels(["Select", "Type", "Voucher No.", "Date", "Outstanding", "Amt to Settle"])
        self.link_table.setColumnWidth(0, 50)
        self.link_table.setColumnWidth(1, 80)
        self.link_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.link_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.link_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.link_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.link_table.setMinimumHeight(200)
        self.link_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.link_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.link_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.link_table.setStyleSheet("""
            QTableWidget { background: white; border-radius: 4px; border: 1px solid #cbd5e1; gridline-color: #f1f5f9; }
            QTableWidget::item:hover { background: #f8fafc; }
            QHeaderView::section { background: #f8fafc; padding: 6px; border: none; border-bottom: 1px solid #e2e8f0; font-weight: bold; color: #475569; }
        """)
        self.link_table.verticalHeader().setVisible(False)
        self.link_table.verticalHeader().setDefaultSectionSize(36)
        self.link_table.cellClicked.connect(self._on_cell_clicked)
        link_lay.addWidget(self.link_table)
        
        self.remainder_lbl = QLabel("On Account: ₹ 0.00")
        self.remainder_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #1e3a5f; margin-top: 4px;")
        link_lay.addWidget(self.remainder_lbl, 0, Qt.AlignmentFlag.AlignRight)
        
        content_lay.addWidget(self.link_frame)

        # Connect amount changes to re-allocation
        self.amount.valueChanged.connect(self._on_total_amount_changed)

        # Narration
        self.narration = QLineEdit(); self.narration.setPlaceholderText("Enter transaction details...")
        self.narration.setMinimumHeight(40); self.narration.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px; background: #ffffff;")
        _add_section("NARRATION", self.narration)

        content_lay.addStretch(); scroll.setWidget(content); root.addWidget(scroll)

        # Buttons
        btn_bar = QFrame(); btn_bar.setStyleSheet("background: #f8fafc; border-top: 1px solid #e2e8f0;")
        btn_lay = QHBoxLayout(btn_bar); btn_lay.setContentsMargins(24, 12, 24, 12); btn_lay.addStretch()
        cancel_btn = QPushButton("Cancel"); cancel_btn.setFixedSize(100, 36); cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("QPushButton { background: white; color: #475569; border: 1px solid #cbd5e1; border-radius: 6px; font-weight: bold; } QPushButton:hover { background: #f8fafc; }")
        ok_btn = QPushButton("Save Voucher"); ok_btn.setFixedSize(140, 36); ok_btn.clicked.connect(self._on_accept)
        ok_btn.setStyleSheet(f"QPushButton {{ background: {color1}; color: white; border-radius: 6px; font-weight: bold; }}")
        btn_lay.addWidget(cancel_btn); btn_lay.addWidget(ok_btn)
        root.addWidget(btn_bar)

        # ── Populate Existing ─────────────────────────────────────────────────
        if existing:
            self.narration.setText(existing.get("narration", ""))
            items = existing.get("items", [])
            self.party_ledger.blockSignals(True)
            self.ref_type.blockSignals(True)
            for e in items:
                lid = e.get("ledger_id")
                g_name = e.get("group_name", "")
                if g_name in ["Cash-in-Hand", "Bank Accounts"]:
                    self.cb_ledger.setCurrentData(lid)
                    self.amount.setValue(e.get("amount", 0))
                else:
                    self.party_ledger.setCurrentData(lid)
            linking = existing.get("linking", {})
            ref_type = linking.get("reference_type", "On Account")
            self.ref_type.setCurrentText(ref_type)
            self.party_ledger.blockSignals(False)
            self.ref_type.blockSignals(False)
            if ref_type == "Against Reference":
                self.link_frame.setVisible(True)
                self._load_outstanding(
                    self.party_ledger.currentData(),
                    linking.get("references", []),
                    include_vid=self._vid
                )

        wire_create_new(self.cb_ledger, self._open_ledger_creation)
        wire_create_new(self.party_ledger, self._open_ledger_creation)
        setup_enter_nav(self, [self.date_edit, self.cb_ledger, self.party_ledger, self.amount, self.ref_type, self.narration], accept_callback=self._on_accept)

    def _on_cell_clicked(self, row, col):
        if col in [1, 2, 3, 4]:
            cb_widget = self.link_table.cellWidget(row, 0)
            if cb_widget:
                chk = cb_widget.findChild(QCheckBox)
                if chk:
                    chk.setChecked(not chk.isChecked())

    def _open_ledger_creation(self):
        from frontend.pages.ledger import LedgerDialog
        try:
            groups = api.list_groups()
        except Exception:
            groups = []
        dlg = LedgerDialog(self.window(), groups=groups)
        if dlg.exec():
            data = dlg.get_data()
            try:
                resp = api.create_ledger(data)
                ledger_id = resp.get("id", "")
                try: self._ledgers = api.list_ledgers()
                except: pass
                return (data["name"], ledger_id)
            except Exception as ex:
                QMessageBox.warning(self, "Error", str(ex))
        return None

    def _on_ref_type_changed(self, text):
        if text == "Against Reference":
            if self.party_ledger.currentIndex() > 0:
                self.link_frame.setVisible(True)
                QTimer.singleShot(100, lambda: self._load_outstanding(self.party_ledger.currentData(), include_vid=self._vid))
        else:
            self.link_frame.setVisible(False)

    def _on_party_changed(self, idx):
        if idx <= 0:
            self.link_frame.setVisible(False)
            self.ref_type.setCurrentText("On Account")
            return
        l_id = self.party_ledger.currentData()
        ledger = next((l for l in self._ledgers if l["_id"] == l_id), None)
        if not ledger: return
        gid = ledger.get("group", "")
        if not isinstance(gid, str): gid = str(gid)
        g_name = self._group_map.get(gid, "")
        target_groups = ["sundry debtors", "sundry creditors", "debtors", "creditors", "customers", "suppliers"]
        if g_name.lower() in target_groups:
            self.ref_type.setCurrentText("Against Reference")
            self.link_frame.setVisible(True)
            QTimer.singleShot(100, lambda: self._load_outstanding(l_id, include_vid=self._vid))
        else:
            self.ref_type.setCurrentText("On Account")
            self.link_frame.setVisible(False)

    def _load_outstanding(self, ledger_id, existing_links=None, include_vid=None):
        try:
            vouchers = api.list_outstanding(ledger_id, include_vid=include_vid)
            rel_type = "Sales" if self.vtype == "Receipt" else "Purchase"
            vouchers.sort(key=lambda x: (0 if x["voucher_type"] == rel_type else 1, x["date"]))
            self.link_table.setRowCount(0)
            for v in vouchers:
                row = self.link_table.rowCount()
                self.link_table.insertRow(row)
                vid = v["_id"]
                existing_ref = next((ref for ref in existing_links if str(ref["voucher_id"]) == str(vid)), None) if existing_links else None
                cb_widget = QWidget()
                cb_lay = QHBoxLayout(cb_widget)
                cb_lay.setContentsMargins(0, 0, 0, 0); cb_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
                chk = QCheckBox(); chk.setCursor(Qt.CursorShape.PointingHandCursor)
                chk.setStyleSheet("QCheckBox::indicator { width: 18px; height: 18px; }")
                if existing_ref or (existing_links is None):
                    chk.setChecked(True)
                cb_lay.addWidget(chk)
                self.link_table.setCellWidget(row, 0, cb_widget)
                chk.stateChanged.connect(lambda: self._reallocate_receipt())
                v_type_item = QTableWidgetItem(v["voucher_type"])
                v_type_item.setForeground(Qt.GlobalColor.darkBlue if v["voucher_type"] == rel_type else Qt.GlobalColor.darkRed)
                self.link_table.setItem(row, 1, v_type_item)
                item_no = QTableWidgetItem(v["voucher_no"])
                item_no.setData(Qt.ItemDataRole.UserRole, vid)
                self.link_table.setItem(row, 2, item_no)
                self.link_table.setItem(row, 3, QTableWidgetItem(v["date"]))
                vamt = v["amount"]
                item_vamt = QTableWidgetItem(format_indian_number(vamt))
                item_vamt.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item_vamt.setData(Qt.ItemDataRole.UserRole, v["amount"])
                self.link_table.setItem(row, 4, item_vamt)
                amt_spin = QDoubleSpinBox()
                max_val = v["amount"]
                amt_spin.setRange(0, max_val); amt_spin.setDecimals(2)
                amt_spin.setValue(existing_ref["amount"] if existing_ref else 0.0)
                amt_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
                amt_spin.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 4px; padding: 2px; background: #ffffff;")
                amt_spin.valueChanged.connect(lambda v: self._update_remainder_label())
                self.link_table.setCellWidget(row, 5, amt_spin)
            if existing_links is None:
                self._reallocate_receipt()
            else:
                self._update_remainder_label()
        except Exception as ex:
            print(f"Error loading outstanding: {ex}")

    def _on_total_amount_changed(self):
        rel_type = "Sales" if self.vtype == "Receipt" else "Purchase"
        for r in range(self.link_table.rowCount()):
            v_type = self.link_table.item(r, 1).text()
            if v_type == rel_type:
                cb_widget = self.link_table.cellWidget(r, 0)
                if cb_widget:
                    chk = cb_widget.findChild(QCheckBox)
                    if chk:
                        chk.blockSignals(True); chk.setChecked(True); chk.blockSignals(False)
        self._reallocate_receipt()

    def _reallocate_receipt(self):
        total_receipt = self.amount.value()
        remaining = total_receipt
        for r in range(self.link_table.rowCount()):
            cb_widget = self.link_table.cellWidget(r, 0)
            if not cb_widget: continue
            chk = cb_widget.findChild(QCheckBox)
            amt_spin = self.link_table.cellWidget(r, 5)
            if not chk or not amt_spin: continue
            chk.blockSignals(True)
            if chk.isChecked() and remaining > 0.005:
                outstanding = self.link_table.item(r, 4).data(Qt.ItemDataRole.UserRole)
                allocated = min(remaining, outstanding)
                amt_spin.setValue(allocated)
                remaining -= allocated
            else:
                chk.setChecked(False); amt_spin.setValue(0.0)
            chk.blockSignals(False)
        self._update_remainder_label()

    def _update_remainder_label(self):
        total_receipt = self.amount.value()
        total_allocated = sum(self.link_table.cellWidget(r, 5).value() for r in range(self.link_table.rowCount()) if self.link_table.cellWidget(r, 5))
        remainder = total_receipt - total_allocated
        if remainder < -0.005:
            self.remainder_lbl.setText(f"Excess Allocated: {format_inr(abs(remainder))}")
            self.remainder_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #dc2626; margin-top: 4px;")
        else:
            self.remainder_lbl.setText(f"On Account: {format_inr(remainder)}")
            self.remainder_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #1e3a5f; margin-top: 4px;")

    def _on_accept(self):
        if self.cb_ledger.currentIndex() <= 0:
            QMessageBox.warning(self, "Error", "Select Cash/Bank account"); return
        if self.party_ledger.currentIndex() <= 0:
            QMessageBox.warning(self, "Error", "Select Party/Ledger"); return
        if self.amount.value() <= 0:
            QMessageBox.warning(self, "Error", "Amount must be > 0"); return
        total_linked = 0.0
        if self.ref_type.currentText() == "Against Reference" and self.link_table.rowCount() > 0:
            total_linked = sum(self.link_table.cellWidget(r, 5).value() for r in range(self.link_table.rowCount()) if self.link_table.cellWidget(r, 5))
            if total_linked > self.amount.value() + 0.01:
                QMessageBox.warning(self, "Error", "Linked amount cannot exceed total amount"); return

        # Date Validation
        ok, err = session.is_date_in_period(self.date_edit.date())
        if not ok:
            QMessageBox.warning(self, "Out of Range", err); return

        reply = QMessageBox.question(self, "Confirm Save", f"Are you sure you want to save this {self.vtype} Voucher?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.accept()

    def get_data(self):
        cb_id = self.cb_ledger.currentData()
        party_id = self.party_ledger.currentData()
        amt = self.amount.value()
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        entries = []
        if self.vtype == "Receipt":
            entries.append({"ledger_id": cb_id, "ledger_name": self.cb_ledger.currentText(), "dr_cr": "Dr", "amount": amt})
            entries.append({"ledger_id": party_id, "ledger_name": self.party_ledger.currentText(), "dr_cr": "Cr", "amount": amt})
        else:
            entries.append({"ledger_id": party_id, "ledger_name": self.party_ledger.currentText(), "dr_cr": "Dr", "amount": amt})
            entries.append({"ledger_id": cb_id, "ledger_name": self.cb_ledger.currentText(), "dr_cr": "Cr", "amount": amt})
        ref_choice = self.ref_type.currentText()
        linking = {"reference_type": ref_choice, "references": []}
        if ref_choice == "Against Reference" and self.link_table.rowCount() > 0:
            total_allocated = 0.0
            for r in range(self.link_table.rowCount()):
                l_amt = self.link_table.cellWidget(r, 5).value()
                if l_amt > 0.01:
                    vid = self.link_table.item(r, 2).data(Qt.ItemDataRole.UserRole)
                    linking["references"].append({"voucher_id": vid, "amount": l_amt, "reference_type": "Against Reference"})
                    total_allocated += l_amt
            remainder = amt - total_allocated
            if remainder > 0.005:
                linking["references"].append({"voucher_id": None, "amount": remainder, "reference_type": "On Account"})
        elif ref_choice == "On Account":
            linking["references"].append({"voucher_id": None, "amount": amt, "reference_type": "On Account"})
        return {
            "voucher_type": self.vtype, "date": date_str,
            "narration": self.narration.text().strip(), "entries": entries, "linking": linking
        }


class JournalVoucherDialog(QDialog):
    def __init__(self, parent, vtype, existing=None):
        super().__init__(parent)
        self.vtype = vtype
        self.existing = existing
        self.setWindowTitle(f"{'Edit ' if existing else ''}{vtype} Voucher"); self.setMinimumSize(700, 480)
        try: self._ledgers = api.list_ledgers()
        except Exception: self._ledgers = []
        root = QVBoxLayout(self)
        hdr = QWidget(); hdr.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hdr.setStyleSheet("background:#1565C0;border-radius:6px;padding:4px;")
        hdr_lay = QHBoxLayout(hdr)
        vt_lbl = QLabel(vtype.upper())
        vt_lbl.setStyleSheet("color:#fff;font-size:15px;font-weight:bold;")
        hdr_lay.addWidget(vt_lbl); hdr_lay.addStretch()
        initial_date = QDate.currentDate()
        if existing and existing.get("date"):
            initial_date = QDate.fromString(existing["date"], "yyyy-MM-dd")
        self.date_edit = DateEdit(initial_date)
        self.date_edit.setCalendarPopup(True); self.date_edit.setDisplayFormat("d-MMM-yy")
        self.date_edit.setStyleSheet("color:#fff;background:#1976D2;border-radius:4px;padding:3px 6px;")
        hdr_lay.addWidget(QLabel("<span style='color:#bbdefb'>Date:</span>"))
        hdr_lay.addWidget(self.date_edit); root.addWidget(hdr)
        root.addWidget(QLabel("Entries  (By = Debit,  To = Credit):"))
        self.entry_frame = QFrame()
        self.entry_layout = QVBoxLayout(self.entry_frame); self.entry_layout.setContentsMargins(0,0,0,0); self.entry_layout.setSpacing(2)
        self._rows = []
        self.balance_indicator = QLabel("Dr Total: \u20b9 0.00   |   Cr Total: \u20b9 0.00")
        self.balance_indicator.setStyleSheet("color:#546e7a;font-size:12px;")
        root.addWidget(self.entry_frame); root.addWidget(self.balance_indicator)
        if existing:
            for e in existing.get("items", []):
                self._add_row(e.get("dr_cr", "Dr")); self._rows[-1].set_entry(e)
        else:
            self._add_row("Dr"); self._add_row("Cr")
        form = QFormLayout()
        self.narration = QLineEdit(); self.narration.setPlaceholderText("Narration")
        if existing: self.narration.setText(existing.get("narration", ""))
        form.addRow("Narration:", self.narration); root.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept); btns.rejected.connect(self.reject)
        root.addWidget(btns)
        setup_enter_nav(self, [self.date_edit, self.narration])

    def _on_accept(self):
        entries = [r.get_entry() for r in self._rows if r.get_entry()]
        if not entries:
            QMessageBox.warning(self, "Error", "Add at least one entry with Amount > 0"); return
        
        # Date Validation
        ok, err = session.is_date_in_period(self.date_edit.date())
        if not ok:
            QMessageBox.warning(self, "Out of Range", err); return

        reply = QMessageBox.question(self, "Confirm Save", f"Save {self.vtype} voucher?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.accept()

    def _add_row(self, dc="Dr"):
        row = JournalEntryRow(self._ledgers, dc, self.entry_frame)
        row.amount.valueChanged.connect(self._update_balance); row.dr_cr.currentTextChanged.connect(self._update_balance)
        self.entry_layout.addWidget(row); self._rows.append(row); self.entry_frame.adjustSize(); self._update_balance()

    def _update_balance(self):
        dr = cr = 0.0
        for row in self._rows:
            if row.amount.value() > 0:
                if row.dr_cr.currentText() == "Dr": dr += row.amount.value()
                else: cr += row.amount.value()
        diff = abs(dr - cr); color = "#16a34a" if diff < 0.01 else "#dc2626"
        self.balance_indicator.setStyleSheet(f"color:{color};font-size:12px;font-weight:bold;")
        self.balance_indicator.setText(f"Dr Total: {format_inr(dr)}   |   Cr Total: {format_inr(cr)}" + ("   \u2713 Balanced" if diff < 0.01 else f"   \u2717 Diff: {format_indian_number(diff)}"))

    def get_data(self):
        entries = [r.get_entry() for r in self._rows if r.get_entry()]
        return {"voucher_type": self.vtype, "date": self.date_edit.date().toString("yyyy-MM-dd"),
                "narration": self.narration.text().strip(), "entries": entries}


class VoucherPage(QWidget):
    def __init__(self):
        super().__init__()
        self.current_page = 1
        self.page_limit = 50
        self.total_count = 0
        self._build()



    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24); layout.setSpacing(16)
        title = QLabel("Voucher Entry")
        title.setStyleSheet("font-size:22px;font-weight:bold;color:#1e3a5f;")
        layout.addWidget(title)
        btn_bar = QWidget(); btn_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        btn_bar.setStyleSheet("background:#f1f5f9;border:1px solid #e2e8f0;border-radius:8px;padding:6px;")
        btn_lay = QHBoxLayout(btn_bar); btn_lay.setSpacing(8)
        self._vtype_btns = {}
        shortcuts = [("Contra","F4"),("Payment","F5"),("Receipt","F6"),("Journal","F7"),("Sales","F8"),("Purchase","F9"),("Debit Note","Alt+F5"),("Credit Note","Alt+F6")]
        for vtype, key in shortcuts:
            btn = QPushButton(f"{vtype}\n{key}"); btn.setFixedHeight(52); btn.setCheckable(True); btn.setShortcut(key)
            btn.setStyleSheet("QPushButton{background:#fff;border:1px solid #cbd5e1;border-radius:6px;color:#1e3a5f;font-size:11px;font-weight:bold;} QPushButton:hover{background:#dbeafe;border-color:#2563eb;} QPushButton:checked{background:#2563eb;color:#fff;border-color:#2563eb;}")
            btn.clicked.connect(lambda *a, v=vtype: self._open_voucher(v))
            if not session.has_permission(vtype, "edit"):
                btn.setEnabled(False)
                btn.setStyleSheet("QPushButton { background: #e2e8f0; color: #94a3b8; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 11px; font-weight: bold; }")
            self._vtype_btns[vtype] = btn; btn_lay.addWidget(btn)
        layout.addWidget(btn_bar)
        flt = QHBoxLayout(); flt.addWidget(QLabel("Filter:"))
        allowed_types = [s[0] for s in shortcuts if session.has_permission(s[0], "view")]
        self.type_filter = SearchableComboBox(); self.type_filter.addItem("All"); self.type_filter.addItems(allowed_types)
        self.type_filter.currentTextChanged.connect(self._on_filter_changed); flt.addWidget(self.type_filter)
        
        self.export_btn = QPushButton("  Excel Export")
        self.export_btn.setIcon(get_icon("frontend/assets/icons/upload.svg", "#1565C0"))
        self.export_btn.setIconSize(QSize(16, 16))
        self.export_btn.setStyleSheet("QPushButton { background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 12px; font-weight: bold; color: #1565C0; } QPushButton:hover { background: #e3f2fd; }")
        self.export_btn.clicked.connect(self._export_excel)
        flt.addWidget(self.export_btn)
        
        flt.addStretch(); layout.addLayout(flt)

        # Pagination Bar
        self.pager_bar = QHBoxLayout()
        self.pager_bar.setContentsMargins(0, 0, 0, 0)
        self.prev_btn = QPushButton("Previous")
        self.prev_btn.setFixedWidth(100)
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn = QPushButton("Next")
        self.next_btn.setFixedWidth(100)
        self.next_btn.clicked.connect(self._next_page)
        self.page_lbl = QLabel("Page 1")
        self.page_lbl.setStyleSheet("font-weight: bold; color: #1e3a5f;")
        
        self.limit_cb = QComboBox()
        self.limit_cb.addItems(["25", "50", "100", "200"])
        self.limit_cb.setCurrentText(str(self.page_limit))
        self.limit_cb.currentTextChanged.connect(self._on_limit_changed)
        
        self.pager_bar.addWidget(self.prev_btn)
        self.pager_bar.addStretch()
        self.pager_bar.addWidget(QLabel("Show:"))
        self.pager_bar.addWidget(self.limit_cb)
        self.pager_bar.addSpacing(10)
        self.pager_bar.addWidget(self.page_lbl)
        self.pager_bar.addStretch()
        self.pager_bar.addWidget(self.next_btn)
        layout.addLayout(self.pager_bar)

        self.table = QTableWidget(0, 8); self.table.setHorizontalHeaderLabels(["No.", "Type", "Date", "Narration", "Amount", "PDF", "Edit", "Del"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive); self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for i in [0,1,2,4,5,6,7]: self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(5, 40); self.table.setColumnWidth(6, 40); self.table.setColumnWidth(7, 40)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.setSortingEnabled(True); self.table.installEventFilter(self)
        layout.addWidget(self.table); self._load()

    def showEvent(self, e):
        self._load(); super().showEvent(e); self.table.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.table and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter): return self._activate_current_table_action()
        return super().eventFilter(obj, event)

    def _activate_current_table_action(self):
        row = self.table.currentRow(); col = self.table.currentColumn()
        if not hasattr(self, "_vouchers") or not (0 <= row < len(self._vouchers)): return False
        if col in (5, 6, 7):
            btn = self.table.cellWidget(row, col)
            if btn and btn.isEnabled(): btn.click(); return True
        v = self._vouchers[row]; self._edit_voucher(v["_id"], v.get("voucher_type", "")); return True

    def _open_voucher(self, vtype):
        if not session.has_permission(vtype, "edit"):
            QMessageBox.warning(self, "Permission Denied", f"You do not have permission to create {vtype} vouchers.")
            for b in self._vtype_btns.values(): b.setChecked(False)
            return
            
        for v, b in self._vtype_btns.items(): b.setChecked(v == vtype)
        if vtype == "Credit Note":
            self.window().open_credit_note()
            for b in self._vtype_btns.values(): b.setChecked(False)
            return
        elif vtype == "Debit Note":
            self.window().open_debit_note()
            for b in self._vtype_btns.values(): b.setChecked(False)
            return
        elif vtype in INVOICE_TYPES:
            dlg = InvoiceVoucherDialog(self, vtype)
        elif vtype in ["Payment", "Receipt"]:
            dlg = PaymentReceiptDialog(self, vtype)
        else:
            dlg = JournalVoucherDialog(self, vtype)
        
        if dlg.exec():
            data = dlg.get_data(); entries = data.get("entries", [])
            if not entries: QMessageBox.warning(self, "Error", "No entries."); return
            try:
                if vtype in ["Payment", "Receipt"]: result = api.create_accounting_voucher(data)
                else: result = api.create_voucher(data)
                self._load()
                
                # Automatically open print options to view the Tax Invoice PDF for Sales vouchers
                if vtype == "Sales" and result and isinstance(result, dict) and result.get("id"):
                    vid = result.get("id")
                    QTimer.singleShot(100, lambda: self._view_pdf(vid))
            except Exception as ex: QMessageBox.warning(self, "Error", str(ex))
        for b in self._vtype_btns.values(): b.setChecked(False)

    def _on_filter_changed(self, text):
        self.current_page = 1
        self._load()

    def _on_limit_changed(self, val):
        self.page_limit = int(val)
        self.current_page = 1
        self._load()

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._load()

    def _next_page(self):
        if self.current_page * self.page_limit < self.total_count:
            self.current_page += 1
            self._load()

    def _load(self):
        self.table.setRowCount(0); vtype = self.type_filter.currentText() if hasattr(self, "type_filter") else None
        kwargs = {"page": self.current_page, "limit": self.page_limit}
        if vtype and vtype != "All": kwargs["type"] = vtype
        try:
            result = api.list_vouchers(**kwargs)
            vouchers = result["data"]
            self.total_count = result["total"]
        except Exception as ex:
            QMessageBox.warning(self, "Error", str(ex))
            return
        
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self._vouchers = vouchers
        
        # Update pager UI
        self.page_lbl.setText(f"Page {self.current_page} of {max(1, (self.total_count + self.page_limit - 1) // self.page_limit)} (Total: {self.total_count})")
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page * self.page_limit < self.total_count)

        for row, v in enumerate(vouchers):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(v.get("voucher_no", "")))
            self.table.setItem(row, 1, QTableWidgetItem(v.get("voucher_type", "")))
            self.table.setItem(row, 2, QTableWidgetItem(v.get("date", "")))
            self.table.setItem(row, 3, QTableWidgetItem(v.get("narration", "")))
            amt_item = QTableWidgetItem(format_inr(v.get("amount", 0.0)))
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); amt_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.table.setItem(row, 4, amt_item)
            vt = v.get("voucher_type", "")
            if vt in INVOICE_TYPES:
                pdf_btn = QPushButton(); pdf_btn.setIcon(get_icon("frontend/assets/icons/file-text.svg", "#d32f2f")); pdf_btn.setFixedWidth(34); pdf_btn.setStyleSheet("QPushButton { border:none; background:transparent; } QPushButton:hover { background:#ffebee; border-radius:4px; }")
                pdf_btn.clicked.connect(lambda *a, vid=v["_id"]: self._view_pdf(vid)); self.table.setCellWidget(row, 5, pdf_btn)
            edit_btn = QPushButton(); edit_btn.setIcon(get_icon("frontend/assets/icons/edit.svg", "#1565C0")); edit_btn.setFixedWidth(34); edit_btn.setStyleSheet("QPushButton { border:none; background:transparent; } QPushButton:hover { background:#e3f2fd; border-radius:4px; }")
            edit_btn.clicked.connect(lambda *a, vid=v["_id"], vt=vt: self._edit_voucher(vid, vt)); self.table.setCellWidget(row, 6, edit_btn)
            del_btn = QPushButton(); del_btn.setIcon(get_icon("frontend/assets/icons/trash.svg", "#c62828")); del_btn.setFixedWidth(34); del_btn.setStyleSheet("QPushButton { border:none; background:transparent; } QPushButton:hover { background:#fee2e2; border-radius:4px; }")
            del_btn.clicked.connect(lambda *a, vid=v["_id"]: self._delete(vid)); self.table.setCellWidget(row, 7, del_btn)
        if self.table.rowCount() > 0: self.table.setSortingEnabled(True); self.table.setCurrentCell(0, 0); self.table.setFocus()

    def _delete(self, vid):
        try:
            v = api.get_voucher(vid)
            vtype = v.get("voucher_type")
        except Exception as ex:
            QMessageBox.warning(self, "Error", f"Failed to fetch voucher details: {ex}")
            return
            
        if not session.has_permission(vtype, "delete"):
            QMessageBox.warning(self, "Permission Denied", f"You do not have permission to delete {vtype} vouchers.")
            return
            
        if QMessageBox.question(self,"Confirm","Delete this voucher?") == QMessageBox.StandardButton.Yes:
            try: api.delete_voucher(vid); self._load()
            except Exception as ex: QMessageBox.warning(self, "Error", str(ex))

    def _view_pdf(self, vid):
        options_dlg = InvoicePrintOptionsDialog(self)
        if options_dlg.exec() != QDialog.DialogCode.Accepted: return
        options = options_dlg.get_data()
        try:
            voucher = api.get_voucher(vid); voucher["invoice_items"] = api.get_voucher_stock_txns(vid)
            try: company = api.get_company(session.company_id)
            except Exception: company = {}
            from frontend.components.pdf_viewer import InvoicePdfViewer
            InvoicePdfViewer(voucher, company, self, invoice_type=options["invoice_type"], copy_type=options["copy_type"]).exec()
        except Exception as ex: QMessageBox.warning(self, "Error", f"Failed to open PDF: {ex}")

    def _edit_voucher(self, vid, vtype):
        if not session.has_permission(vtype, "update"):
            QMessageBox.warning(self, "Permission Denied", f"You do not have permission to edit {vtype} vouchers.")
            return
            
        try: voucher = api.get_voucher(vid)
        except Exception as ex: QMessageBox.warning(self, "Error", str(ex)); return
        if vtype == "Credit Note":
            try:
                voucher["invoice_items"] = api.get_voucher_stock_txns(vid)
            except Exception:
                pass
            self.window().open_credit_note(voucher)
            return
        elif vtype == "Debit Note":
            try:
                voucher["invoice_items"] = api.get_voucher_stock_txns(vid)
            except Exception:
                pass
            self.window().open_debit_note(voucher)
            return
        elif vtype in INVOICE_TYPES:
            try:
                voucher["invoice_items"] = api.get_voucher_stock_txns(vid)
            except Exception:
                pass
            dlg = InvoiceVoucherDialog(self, vtype, existing=voucher)
        elif vtype in ["Payment", "Receipt"]:
            dlg = PaymentReceiptDialog(self, vtype, existing=voucher)
        else:
            dlg = JournalVoucherDialog(self, vtype, existing=voucher)
        if dlg.exec():
            data = dlg.get_data(); entries = data.get("entries", [])
            if not entries: QMessageBox.warning(self, "Error", "No entries."); return
            try:
                update_payload = {"date": data["date"], "narration": data["narration"], "entries": entries, "invoice_items": data.get("invoice_items")}
                if "grand_total" in data: update_payload["grand_total"] = data["grand_total"]
                if "linking" in data: update_payload["linking"] = data["linking"]
                api.update_voucher(vid, update_payload); self._load()
            except Exception as ex: QMessageBox.warning(self, "Error", str(ex))
    def _export_excel(self):
        vtype = self.type_filter.currentText()
        if vtype != "Sales":
            QMessageBox.information(self, "Export Info", "Currently, Excel export is specifically formatted for 'Sales' vouchers. Please filter by 'Sales' first.")
            return
            
        if not hasattr(self, "_vouchers") or not self._vouchers:
            QMessageBox.warning(self, "No Data", "No sales vouchers found to export.")
            return

        # Prepare data (fetch details for each voucher)
        try:
            # Fetch all vouchers for export (ignore pagination)
            kwargs = {"limit": 0}
            if vtype != "All": kwargs["type"] = vtype
            export_res = api.list_vouchers(**kwargs)
            export_vouchers = export_res.get("data", [])
            
            full_vouchers = []
            for v_summary in export_vouchers:
                vid = v_summary["_id"]
                # Fetch full details including entries and stock items
                v_full = api.get_voucher(vid)
                v_full["invoice_items"] = api.get_voucher_stock_txns(vid)
                
                # Get Party Name and GSTIN from entries if possible
                # Usually the first Cr entry for Sales is the Party
                v_full["party_name"] = "Unknown Party"
                v_full["gstin"] = ""
                for e in v_full.get("entries", []):
                    if e.get("dr_cr") == "Dr": # Party is Dr in Sales
                        v_full["party_name"] = e.get("ledger_name", "Unknown Party")
                        # Try to get GSTIN from ledger details (needs another API call or cached ledger info)
                        try:
                            l_detail = api.get_ledger(e["ledger_id"])
                            v_full["gstin"] = l_detail.get("gstin", "")
                        except:
                            pass
                        break
                
                full_vouchers.append(v_full)

            # Get company info
            try:
                company = api.get_company(session.company_id)
            except:
                company = {"name": "Bestie Accounts", "financial_year": session.get_financial_year_str()}

            date_range = f"{session.get_start_date().strftime('%d-%b-%y')} to {session.get_end_date().strftime('%d-%b-%y')}"
            
            export_sales_register(self, company, full_vouchers, date_range)
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to prepare export data: {e}")
