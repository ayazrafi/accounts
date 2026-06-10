"""
Import Payment / Receipt vouchers from Excel.

Expected Excel structure (auto-detected header row):
  Date | Particulars | Voucher Type | Voucher No. | Gross Total | <Ledger1> | <Ledger2> | ...

- Particulars      : Name of the Cash/Bank ledger (e.g. "State Bank of India")
- Voucher Type     : "Payment" or "Receipt"
- Gross Total      : Grand total (may be negative for Payments — abs() is taken)
- Remaining cols   : Contra-ledger columns, column name = ledger name, value = amount
                     (negative values are treated as zero / skipped)

Accounting entries generated:
  Payment  → Cash/Bank  Cr  |  Contra ledger(s)  Dr
  Receipt  → Cash/Bank  Dr  |  Contra ledger(s)  Cr
"""

import math
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QTextEdit, QLabel, QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QPixmap
from frontend import api_client as api
from frontend.utils import get_icon

# Fixed known-metadata columns that are NOT ledger-amount columns
_META_COLS = {
    "date", "particulars", "voucher type", "voucher no", "voucher no.",
    "voucher number", "gross total", "narration", "ref no", "ref. no"
}


def _clean(v):
    """Convert a cell value to a clean float, returning 0.0 for blanks/NaN."""
    try:
        if isinstance(v, (int, float)) and math.isnan(v):
            return 0.0
        v_str = str(v).strip().lower().replace('dr', '').replace('cr', '').strip()
        if not v_str or v_str == "nan":
            return 0.0
        return float(v_str)
    except Exception:
        return 0.0


class ImportPaymentWorker(QThread):
    progress = Signal(int, int)   # current, total
    log      = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path

    # ── helpers ──────────────────────────────────────────────────────────────
    def _find_col(self, df, *names):
        """Case-insensitive column lookup. Returns first matching real column name."""
        for n in names:
            for c in df.columns:
                if c.strip().lower() == n.strip().lower():
                    return c
        return None

    # ── main ─────────────────────────────────────────────────────────────────
    def run(self):
        try:
            self.log.emit("Reading Excel file: " + self.file_path)

            # ── 1. Detect header row ─────────────────────────────────────────
            header_df = pd.read_excel(self.file_path, nrows=25, header=None)
            header_row_idx = 0
            for i, row in header_df.iterrows():
                row_vals = [str(x).strip().upper() for x in row.values if pd.notnull(x)]
                if "DATE" in row_vals and "PARTICULARS" in row_vals:
                    header_row_idx = i
                    self.log.emit(f"Header detected at row {i + 1}")
                    break

            df = pd.read_excel(self.file_path, header=header_row_idx)
            df.columns = [str(c).strip() for c in df.columns]
            self.log.emit(f"Columns found: {list(df.columns)}")

            # ── 2. Identify key columns ──────────────────────────────────────
            col_date    = self._find_col(df, "Date")
            col_part    = self._find_col(df, "Particulars")
            col_vtype   = self._find_col(df, "Voucher Type", "VoucherType")
            col_vno     = self._find_col(df, "Voucher No.", "Voucher No", "Voucher Number")
            col_gross   = self._find_col(df, "Gross Total", "GrossTotal", "Amount", "Total")

            if not col_date or not col_part:
                self.finished.emit(False, "Could not find 'Date' or 'Particulars' columns.")
                return

            # Ledger-amount columns = everything that is NOT a meta column
            ledger_cols = [
                c for c in df.columns
                if c.strip().lower() not in _META_COLS
            ]
            self.log.emit(f"Ledger columns: {ledger_cols}")

            # ── 3. Fetch master data ─────────────────────────────────────────
            self.log.emit("Fetching ledgers and groups…")
            all_ledgers = api.list_ledgers()
            groups      = api.list_groups()
            group_map   = {str(g["_id"]): g["name"] for g in groups}

            # ledger lookup by name (case-insensitive)
            ledger_by_name = {l["name"].strip().lower(): l for l in all_ledgers}

            # round-off ledger
            round_off_ledger = next(
                (l for l in all_ledgers if "round" in l["name"].lower()), None
            )
            round_off_id   = str(round_off_ledger["_id"]) if round_off_ledger else None
            round_off_name = round_off_ledger["name"]     if round_off_ledger else "Round Off"

            # Pre-resolve groups for auto-creation
            susp_group      = next((g for g in groups if "suspense" in g["name"].lower()), None)
            creditors_group = next((g for g in groups if g["name"].strip().lower() == "sundry creditors"), None)
            dt_group        = next((g for g in groups if g["name"].strip().lower() in ("duties & taxes", "duties and taxes")), None)

            def _is_suspense_col(col_name: str) -> bool:
                """Return True if this column should be created under Suspense A/c."""
                n = col_name.strip().lower()
                return "suspense" in n

            def _is_gst_col(col_name: str) -> bool:
                """Return True if this column is a GST/Duties&Taxes-type ledger."""
                n = col_name.strip().lower()
                return any(kw in n for kw in ("gst", "igst", "cgst", "sgst", "tds", "tcs", "deposit"))

            def _resolve_or_create_ledger(lname: str):
                """Find ledger by name. If missing, auto-create in correct group."""
                ledger = ledger_by_name.get(lname.strip().lower())
                if ledger:
                    return ledger

                # Determine which group to use
                if _is_suspense_col(lname) and susp_group:
                    target_group = susp_group
                    group_label  = "Suspense A/c"
                elif _is_gst_col(lname) and dt_group:
                    target_group = dt_group
                    group_label  = "Duties & Taxes"
                elif creditors_group:
                    # Regular party payment → Sundry Creditors
                    target_group = creditors_group
                    group_label  = "Sundry Creditors"
                else:
                    self.log.emit(f"  ✗  No suitable group found to create ledger '{lname}'")
                    return None

                self.log.emit(f"  ℹ  Ledger '{lname}' not found — creating under {group_label}")
                try:
                    resp = api.create_ledger({
                        "name":  lname,
                        "group": str(target_group["_id"]),
                    })
                    new_l = {"_id": resp["id"], "name": lname, "group": str(target_group["_id"])}
                    ledger_by_name[lname.strip().lower()] = new_l
                    all_ledgers.append(new_l)
                    return new_l
                except Exception as ex:
                    self.log.emit(f"  ✗  Could not create ledger '{lname}': {ex}")
                    return None


            # Pre-load group name for every ledger so we can quickly classify them
            ledger_group_name = {}
            for l in all_ledgers:
                gn = group_map.get(str(l.get("group", "")), "")
                ledger_group_name[str(l["_id"])] = gn

            _CASH_BANK_GROUPS  = {"Cash-in-Hand", "Bank Accounts"}
            debtors_group  = next((g for g in groups if g["name"].strip().lower() == "sundry debtors"),  None)

            def _is_cash_bank(ledger_dict) -> bool:
                """Return True if this ledger belongs to a Cash/Bank group."""
                gn = group_map.get(str(ledger_dict.get("group", "")), "")
                return gn in _CASH_BANK_GROUPS

            def _resolve_or_create_party(lname: str, vtype_local: str):
                """
                Find or create a party ledger.
                Receipt  → Sundry Debtors  (customer paying us)
                Payment  → Sundry Creditors (vendor/party we pay)
                """
                ledger = ledger_by_name.get(lname.strip().lower())
                if ledger:
                    return ledger
                target = debtors_group if vtype_local == "Receipt" else creditors_group
                group_label = "Sundry Debtors" if vtype_local == "Receipt" else "Sundry Creditors"
                if not target:
                    self.log.emit(f"  ✗  '{group_label}' group not found — cannot create '{lname}'")
                    return None
                self.log.emit(f"  ℹ  Creating party ledger '{lname}' under {group_label}")
                try:
                    resp = api.create_ledger({"name": lname, "group": str(target["_id"])})
                    new_l = {"_id": resp["id"], "name": lname, "group": str(target["_id"])}
                    ledger_by_name[lname.strip().lower()] = new_l
                    all_ledgers.append(new_l)
                    ledger_group_name[str(new_l["_id"])] = group_label
                    return new_l
                except Exception as ex:
                    self.log.emit(f"  ✗  Could not create ledger '{lname}': {ex}")
                    return None

            # ── 4. Parse rows ────────────────────────────────────────────────
            total_v = 0
            total_rows = len(df)

            for idx, row in df.iterrows():
                self.progress.emit(idx + 1, total_rows)

                # Date
                raw_date = row.get(col_date)
                if pd.isnull(raw_date):
                    continue
                if hasattr(raw_date, "strftime"):
                    date_str = raw_date.strftime("%Y-%m-%d")
                else:
                    date_str = str(raw_date).split(" ")[0].strip()

                if not date_str or date_str.lower() == "nan":
                    continue

                # Particulars (either Cash/Bank or Party name)
                part_name = str(row.get(col_part, "")).strip()
                if not part_name or part_name.lower() == "nan":
                    continue

                # Voucher type
                vtype = str(row.get(col_vtype or "", "Payment")).strip()
                if vtype.lower() not in ("payment", "receipt"):
                    vtype = "Payment"

                # Gross total (abs — Tally exports Payment as negative)
                gross = abs(_clean(row.get(col_gross, 0))) if col_gross else 0.0

                # ── Step 1: Decide role of Particulars (Party vs Cash/Bank) ──
                # Rule: if ANY ledger-column that is a Cash/Bank account has a
                # non-zero value in this row → Particulars is the PARTY.
                # Otherwise → Particulars is the Cash/Bank account.
                part_ledger = ledger_by_name.get(part_name.lower())

                has_bank_col_value = False
                for _col in ledger_cols:
                    _amt = abs(_clean(row.get(_col, 0)))
                    if _amt <= 0:
                        continue
                    _lname = _col.strip()
                    _col_ledger = ledger_by_name.get(_lname.lower())
                    if _col_ledger and _is_cash_bank(_col_ledger):
                        has_bank_col_value = True
                        break

                # Particulars is a Party when a Cash/Bank column carries the amount
                part_is_bank = not has_bank_col_value

                entries       = []
                contra_total  = 0.0

                if part_is_bank:
                    # ── Case A: Particulars = Cash/Bank ─────────────────────
                    # Receipt: Dr Particulars (bank)  | Cr column-ledgers
                    # Payment: Cr Particulars (bank)  | Dr column-ledgers
                    cb_ledger = part_ledger
                    if not cb_ledger:
                        self.log.emit(f"  ⚠  Cash/Bank ledger '{part_name}' not found in database — skipping row {idx+1}")
                        continue
                    cb_id     = str(cb_ledger["_id"])
                    cb_dr_cr  = "Dr" if vtype == "Receipt" else "Cr"

                    for col in ledger_cols:
                        amt = abs(_clean(row.get(col, 0)))
                        if amt <= 0:
                            continue
                        lname  = col.strip()
                        ledger = _resolve_or_create_ledger(lname)
                        if not ledger:
                            continue
                        contra_dr_cr = "Cr" if vtype == "Receipt" else "Dr"
                        entries.append({
                            "ledger_id":   str(ledger["_id"]),
                            "ledger_name": lname,
                            "dr_cr":       contra_dr_cr,
                            "amount":      round(amt, 2),
                        })
                        contra_total += amt

                    if not entries:
                        self.log.emit(f"  ⚠  No contra amounts found for row {idx+1} — skipping")
                        continue

                    if gross <= 0:
                        gross = contra_total

                    # Auto Round Off
                    diff = round(abs(contra_total - gross), 2)
                    if diff > 0.001 and round_off_id:
                        self.log.emit(f"  * Auto Round Off: {diff:.2f}")
                        ro_dr_cr = "Cr" if vtype == "Receipt" else "Dr"
                        entries.append({
                            "ledger_id":   round_off_id,
                            "ledger_name": round_off_name,
                            "dr_cr":       ro_dr_cr,
                            "amount":      diff,
                        })
                        gross = contra_total  # use contra sum as the authoritative amount

                    # Cash/Bank entry
                    entries.append({
                        "ledger_id":   cb_id,
                        "ledger_name": part_name,
                        "dr_cr":       cb_dr_cr,
                        "amount":      round(gross, 2),
                    })

                else:
                    # ── Case B: Particulars = Party (not a bank account) ─────
                    # Receipt: Cr Party   | Dr column that is Cash/Bank
                    # Payment: Dr Party   | Cr column that is Cash/Bank
                    #
                    # Any column with a value could be Cash/Bank or another contra.
                    # We detect Cash/Bank columns by checking their group.

                    party_ledger = part_ledger or _resolve_or_create_party(part_name, vtype)
                    if not party_ledger:
                        self.log.emit(f"  ✗  Cannot resolve party '{part_name}' — skipping row {idx+1}")
                        continue

                    party_dr_cr = "Cr" if vtype == "Receipt" else "Dr"
                    cb_total    = 0.0  # total in cash/bank columns

                    for col in ledger_cols:
                        amt = abs(_clean(row.get(col, 0)))
                        if amt <= 0:
                            continue
                        lname     = col.strip()
                        col_ledger = ledger_by_name.get(lname.lower())

                        if col_ledger and _is_cash_bank(col_ledger):
                            # This column IS the Cash/Bank side
                            cb_dr_cr_local = "Dr" if vtype == "Receipt" else "Cr"
                            entries.append({
                                "ledger_id":   str(col_ledger["_id"]),
                                "ledger_name": lname,
                                "dr_cr":       cb_dr_cr_local,
                                "amount":      round(amt, 2),
                            })
                            cb_total     += amt
                            contra_total += amt
                        else:
                            # Regular contra ledger (Suspense, GST, etc.)
                            ledger = _resolve_or_create_ledger(lname)
                            if not ledger:
                                continue
                            contra_dr_cr = "Cr" if vtype == "Receipt" else "Dr"
                            # For Payment to party, the non-bank columns are also Dr
                            # For Receipt from party, the non-bank columns are also Cr
                            entries.append({
                                "ledger_id":   str(ledger["_id"]),
                                "ledger_name": lname,
                                "dr_cr":       "Dr" if vtype == "Payment" else "Cr",
                                "amount":      round(amt, 2),
                            })
                            contra_total += amt

                    if not entries:
                        self.log.emit(f"  ⚠  No column amounts found for row {idx+1} — skipping")
                        continue

                    if gross <= 0:
                        gross = contra_total

                    # Auto Round Off
                    diff = round(abs(contra_total - gross), 2)
                    if diff > 0.001 and round_off_id:
                        self.log.emit(f"  * Auto Round Off: {diff:.2f}")
                        ro_dr_cr = "Cr" if vtype == "Receipt" else "Dr"
                        entries.append({
                            "ledger_id":   round_off_id,
                            "ledger_name": round_off_name,
                            "dr_cr":       ro_dr_cr,
                            "amount":      diff,
                        })
                        gross = contra_total

                    # Party entry (Cr for Receipt, Dr for Payment)
                    entries.append({
                        "ledger_id":   str(party_ledger["_id"]),
                        "ledger_name": part_name,
                        "dr_cr":       party_dr_cr,
                        "amount":      round(gross, 2),
                    })

                # ── Final balance check ──────────────────────────────────────
                dr_sum = sum(e["amount"] for e in entries if e["dr_cr"] == "Dr")
                cr_sum = sum(e["amount"] for e in entries if e["dr_cr"] == "Cr")
                if abs(dr_sum - cr_sum) > 0.01:
                    self.log.emit(
                        f"  ✗  Row {idx+1}: unbalanced (Dr={dr_sum:.2f} Cr={cr_sum:.2f}) — skipping"
                    )
                    continue

                # ── Log entries ──────────────────────────────────────────────
                self.log.emit(f"Voucher {vtype} | {date_str} | {part_name} | ₹{gross:,.2f}")
                for e in entries:
                    self.log.emit(f"  {e['dr_cr']:2s}  {e['ledger_name']}  {e['amount']:,.2f}")

                # ── Save voucher ─────────────────────────────────────────────
                v_no = str(row.get(col_vno or "", "")).strip()
                payload = {
                    "voucher_type": vtype,
                    "date":         date_str,
                    "narration":    str(row.get("Narration", f"Imported {vtype}")).strip(),
                    "entries":      entries,
                    "grand_total":  gross,
                    "metadata": {
                        "excel_v_no":    v_no,
                        "import_source": "Excel",
                    },
                }
                try:
                    api.create_accounting_voucher(payload)
                    total_v += 1
                except Exception as ex:
                    self.log.emit(f"  ✗  API error row {idx+1}: {ex}")

            self.finished.emit(True, f"Successfully imported {total_v} vouchers.")

        except Exception as e:
            import traceback
            self.log.emit(f"Error: {e}\n{traceback.format_exc()}")
            self.finished.emit(False, str(e))


class ImportPaymentReceiptDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Payment / Receipt Vouchers from Excel")
        self.setMinimumSize(680, 450)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Title row with SVG icon
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            get_icon("frontend/assets/icons/refresh-cw.svg", "#1565C0").pixmap(22, 22)
        )
        icon_lbl.setFixedSize(26, 26)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addWidget(icon_lbl)

        title = QLabel("Import Payment / Receipt from Excel")
        title.setStyleSheet("font-size:15px;font-weight:bold;color:#1565C0;")
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        info = QLabel(
            "Excel must have columns: <b>Date, Particulars, Voucher Type, Voucher No., "
            "Gross Total</b>, followed by one column per contra ledger (column name = ledger name)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#546e7a;font-size:11px;")
        layout.addWidget(info)

        # File picker
        file_row = QHBoxLayout()
        self.file_lbl = QLabel("No file selected")
        self.file_lbl.setStyleSheet(
            "background:#f5f5f5;border:1px solid #ddd;border-radius:4px;padding:6px;"
            "color:#455a64;"
        )
        btn_browse = QPushButton("Browse…")
        btn_browse.setStyleSheet(
            "QPushButton{background:#1565C0;color:#fff;border:none;border-radius:4px;"
            "padding:6px 14px;font-weight:bold;}"
            "QPushButton:hover{background:#1976D2;}"
        )
        btn_browse.clicked.connect(self._browse)
        file_row.addWidget(self.file_lbl, 1)
        file_row.addWidget(btn_browse)
        layout.addLayout(file_row)

        # Progress
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setStyleSheet(
            "QProgressBar{border:1px solid #ddd;border-radius:4px;background:#f5f5f5;}"
            "QProgressBar::chunk{background:#1565C0;border-radius:4px;}"
        )
        layout.addWidget(self.progress)

        # Log
        log_lbl = QLabel("Import Log")
        log_lbl.setStyleSheet("font-weight:bold;color:#37474f;font-size:11px;")
        layout.addWidget(log_lbl)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet(
            "background:#1e272e;color:#a8d8a8;font-family:monospace;font-size:11px;"
            "border-radius:6px;padding:8px;"
        )
        layout.addWidget(self.log_box, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_import = QPushButton("Import")
        self.btn_import.setEnabled(False)
        self.btn_import.setStyleSheet(
            "QPushButton{background:#2e7d32;color:#fff;border:none;border-radius:4px;"
            "padding:8px 22px;font-weight:bold;font-size:13px;}"
            "QPushButton:disabled{background:#ccc;color:#888;}"
            "QPushButton:hover:!disabled{background:#388e3c;}"
        )
        self.btn_import.clicked.connect(self._start_import)
        btn_row.addWidget(self.btn_import)
        layout.addLayout(btn_row)

        self._file_path = None

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Excel File", "", "Excel Files (*.xlsx *.xls *.xlsm)"
        )
        if path:
            self._file_path = path
            self.file_lbl.setText(path)
            self.btn_import.setEnabled(True)

    def _start_import(self):
        if not self._file_path:
            return
        self.btn_import.setEnabled(False)
        self.progress.setVisible(True)
        self.log_box.clear()
        self.worker = ImportPaymentWorker(self._file_path)
        self.worker.log.connect(self._append_log)
        self.worker.progress.connect(self._update_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _append_log(self, text):
        self.log_box.append(text)

    def _update_progress(self, current, total):
        self.progress.setMaximum(total)
        self.progress.setValue(current)

    def _on_finished(self, success, message):
        self.progress.setVisible(False)
        self.btn_import.setEnabled(True)
        if success:
            QMessageBox.information(self, "Success", message)
            self.accept()
        else:
            QMessageBox.warning(self, "Error", message)
