import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QTextEdit, QLabel, QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from frontend import api_client as api
import frontend.session as session
import re

class ImportPurchaseWorker(QThread):
    progress = Signal(int, int)  # current, total
    log = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        def _clean(v):
            import math
            try:
                if isinstance(v, (int, float)) and math.isnan(v): return 0.0
                v_str = str(v).strip().lower()
                if not v_str or v_str == "nan": return 0.0
                # Remove 'Dr' or 'Cr' if present in the string
                v_str = v_str.replace('dr', '').replace('cr', '').strip()
                return float(v_str)
            except: return 0.0

        try:
            self.log.emit("Reading Excel file: " + self.file_path)
            
            # 1. Dynamically find the header row
            # We read the first 20 rows and check which one looks like a header
            header_df = pd.read_excel(self.file_path, nrows=20, header=None)
            header_row_idx = 0
            for i, row in header_df.iterrows():
                row_vals = [str(x).strip().upper() for x in row.values if pd.notnull(x)]
                if 'DATE' in row_vals and 'PARTICULARS' in row_vals:
                    header_row_idx = i
                    self.log.emit(f"Detected header at row {i+1}")
                    break
            
            df = pd.read_excel(self.file_path, header=header_row_idx) 
            
            # Clean column names (strip whitespace)
            df.columns = [str(c).strip() for c in df.columns]

            # 2. Basic validation with flexible names
            # Map provide names to columns in df
            def get_col_name(targets):
                for t in targets:
                    for c in df.columns:
                        if c.strip().upper() == t.strip().upper():
                            return c
                return None

            col_date = get_col_name(['Date'])
            col_part = get_col_name(['Particulars'])
            col_vno = get_col_name(['Voucher No.', 'Voucher No'])
            
            if not col_date or not col_part:
                self.log.emit(f"Error: Could not find 'Date' or 'Particulars' columns.")
                self.finished.emit(False, "Could not find 'Date' or 'Particulars' columns. Please check Excel headers.")
                return
            
            self.log.emit("Fetching existing data for mapping...")
            groups = api.list_groups()
            g_map = {g['name']: str(g['_id']) for g in groups}
            
            # Required Groups
            creditors_gid = g_map.get("Sundry Creditors")
            purchase_gid = g_map.get("Purchase Accounts")
            taxes_gid = g_map.get("Duties & Taxes")
            direct_exp_gid = g_map.get("Direct Expenses")

            if not all([creditors_gid, purchase_gid, taxes_gid, direct_exp_gid]):
                self.finished.emit(False, "Essential accounting groups (Sundry Creditors, Purchase Accounts, Duties & Taxes, Direct Expenses) not found.")
                return

            ledgers = api.list_ledgers()
            l_map = {l['name']: str(l['_id']) for l in ledgers}
            
            # Ensure Round Off ledger exists
            round_off_name = "Round Off"
            if round_off_name not in l_map:
                self.log.emit(f"Creating '{round_off_name}' ledger...")
                l_res = api.create_ledger({
                    "name": round_off_name,
                    "group": g_map.get("Expenses (Indirect)", direct_exp_gid),
                    "opening_balance": 0,
                    "dr_cr": "Dr"
                })
                l_map[round_off_name] = str(l_res.get('id', l_res.get('_id')))

            items = api.list_stock_items()
            i_map = {i['name']: str(i['_id']) for i in items}
            
            units = api.list_units()
            u_map = {u['name']: str(u['_id']) for u in units}

            col_qty = get_col_name(['Quantity'])
            col_rate = get_col_name(['Rate'])
            col_val = get_col_name(['Value'])
            col_gstin = get_col_name(['GSTIN/UIN'])
            col_inv_no = get_col_name(['Supplier Invoice No.'])
            col_inv_date = get_col_name(['Supplier Invoice Date'])

            # Parse vouchers
            vouchers = []
            current_v = None
            
            for index, row in df.iterrows():
                # Date handling
                raw_date = row.get(col_date)
                if pd.notnull(raw_date):
                    if hasattr(raw_date, 'strftime'):
                        date_val = raw_date.strftime('%Y-%m-%d')
                    else:
                        date_val = str(raw_date).split(' ')[0].strip()
                else:
                    date_val = None

                v_no = str(row.get(col_vno or 'Voucher No', '')).strip()
                particulars = str(row.get(col_part, '')).strip()
                
                # Determine if this is a new voucher or an item row
                is_new_voucher = (date_val is not None and date_val != 'nan' and v_no != 'nan' and v_no != '')
                
                if is_new_voucher:
                    if current_v:
                        vouchers.append(current_v)
                    
                    # New Voucher Row
                    tax_details = {}
                    target_columns = [
                        'Purchase 18%', 'CGST 9%', 'SGST 9%', 'ROUND OFF', 
                        'Purchase 28%', 'Cgst 14%', 'Sgst 14%', 'Purchase', 
                        'Freight Charges', 'Gross Total', 'Value'
                    ]
                    for col in target_columns:
                        real_col = get_col_name([col])
                        if real_col:
                            tax_details[col] = _clean(row.get(real_col, 0))

                    raw_inv_date = row.get(col_inv_date or 'Supplier Invoice Date')
                    inv_date_val = ""
                    if pd.notnull(raw_inv_date):
                        if hasattr(raw_inv_date, 'strftime'):
                            inv_date_val = raw_inv_date.strftime('%Y-%m-%d')
                        else:
                            inv_date_val = str(raw_inv_date).split(' ')[0].strip()

                    current_v = {
                        "date": date_val,
                        "v_no": v_no,
                        "party_name": particulars,
                        "supplier_inv_no": str(row.get(col_inv_no or 'Supplier Invoice No.', '')).strip(),
                        "supplier_inv_date": inv_date_val,
                        "gstin": str(row.get(col_gstin or 'GSTIN/UIN', '')).strip(),
                        "items": [],
                        "tax_details": tax_details
                    }
                elif current_v and particulars and particulars != 'nan':
                    # Item Row (Date is blank, but we have a voucher in progress)
                    qty_str = str(row.get(col_qty or 'Quantity', '')).strip()
                    val = _clean(row.get(col_val or 'Value', 0))
                    raw_rate = str(row.get(col_rate or 'Rate', '0')).split('/')[0]
                    rate_val = _clean(raw_rate)
                    
                    qty = 0
                    unit = "NOS"
                    if qty_str and qty_str != 'nan':
                        parts = qty_str.split(' ')
                        try:
                            qty = float(parts[0])
                            if len(parts) > 1:
                                unit = parts[1]
                        except:
                            pass
                    
                    # Inclusive/Exclusive check: qty * rate vs value
                    is_inclusive = False
                    if qty > 0 and rate_val > 0:
                        if (qty * rate_val) > (val + 1): 
                            is_inclusive = True

                    current_v["items"].append({
                        "name": particulars,
                        "qty": _clean(qty),
                        "unit": unit,
                        "value": val,
                        "rate": rate_val,
                        "is_inclusive": is_inclusive
                    })
            
            if current_v:
                vouchers.append(current_v)

            total_v = len(vouchers)
            self.log.emit(f"Found {total_v} purchase vouchers to import.")

            # Process Import
            for i, v in enumerate(vouchers):
                self.progress.emit(i + 1, total_v)
                self.log.emit(f"Importing Purchase Voucher {v['v_no']} for {v['party_name']}...")
                
                # 1. Ensure Party Ledger (Sundry Creditor)
                party_id = l_map.get(v['party_name'])
                if not party_id:
                    self.log.emit(f"Creating Party Ledger: {v['party_name']}")
                    p_res = api.create_ledger({
                        "name": v['party_name'],
                        "group": creditors_gid,
                        "gstin": v['gstin'] if v['gstin'] != 'nan' else "",
                        "opening_balance": 0,
                        "dr_cr": "Cr"
                    })
                    party_id = str(p_res['id'])
                    l_map[v['party_name']] = party_id

                # 2. Ensure Items
                voucher_items = []
                for it in v['items']:
                    item_id = i_map.get(it['name'])
                    if not item_id:
                        self.log.emit(f"Creating Item: {it['name']}")
                        m = re.match(r"^(\d+)\s+(.*)", it['name'])
                        group_name = m.group(1) if m else "General"
                        
                        g_res_list = api.list_stock_groups()
                        sg_map = {sg['name']: str(sg['_id']) for sg in g_res_list}
                        if group_name not in sg_map:
                            sg_res = api.create_stock_group({"name": group_name})
                            sg_id = str(sg_res['id'])
                            sg_map[group_name] = sg_id
                        else:
                            sg_id = sg_map[group_name]

                        if it['unit'] not in u_map:
                            u_res = api.create_unit({"name": it['unit']})
                            u_map[it['unit']] = str(u_res['id'])
                        
                        i_res = api.create_stock_item({
                            "name": it['name'],
                            "unit": u_map[it['unit']],
                            "stock_group": sg_id,
                            "opening_qty": 0
                        })
                        item_id = str(i_res['id'])
                        i_map[it['name']] = item_id
                    
                    rate = it['rate']
                    voucher_items.append({
                        "item_id": item_id,
                        "item_name": it['name'],
                        "qty": it['qty'],
                        "unit": u_map.get(it['unit'], it['unit']),
                        "rate": rate if not it['is_inclusive'] else (it['value'] / it['qty'] if it['qty'] > 0 else 0),
                        "final_rate": rate if it['is_inclusive'] else 0,
                        "amount": it['value']
                    })

                # Process tax_details to build accounting entries
                entries = []
                gross_total = v['tax_details'].get('Gross Total', 0)
                round_off = v['tax_details'].get('ROUND OFF', 0)
                freight = v['tax_details'].get('Freight Charges', 0)
                
                for col, val in v['tax_details'].items():
                    if val == 0: continue
                    if col in ['Gross Total', 'ROUND OFF', 'Freight Charges', 'Value']:
                        continue
                    
                    c_up = col.upper()
                    # Purchase Ledgers (Purchase 18%, Purchase 28%, Purchase)
                    if 'PURCHASE' in c_up:
                        if col not in l_map:
                            l_res = api.create_ledger({"name": col, "group": purchase_gid, "dr_cr": "Dr"})
                            l_map[col] = str(l_res['id'])
                        entries.append({"ledger_id": l_map[col], "ledger_name": col, "dr_cr": "Dr", "amount": abs(val)})
                    
                    # GST Ledgers (CGST 9%, SGST 9%, etc.)
                    elif any(t in c_up for t in ['CGST', 'SGST', 'IGST']):
                        if col not in l_map:
                            l_res = api.create_ledger({"name": col, "group": taxes_gid, "dr_cr": "Dr"})
                            l_map[col] = str(l_res['id'])
                        entries.append({"ledger_id": l_map[col], "ledger_name": col, "dr_cr": "Dr", "amount": abs(val)})

                # Freight Inward (Freight Charges)
                if freight != 0:
                    freight_name = "Freight Inward"
                    if freight_name not in l_map:
                        l_res = api.create_ledger({"name": freight_name, "group": direct_exp_gid, "dr_cr": "Dr"})
                        l_map[freight_name] = str(l_res['id'])
                    entries.append({"ledger_id": l_map[freight_name], "ledger_name": freight_name, "dr_cr": "Dr", "amount": abs(freight)})

                # Auto-Balance Logic:
                # We calculate the difference between Dr (Purchase, Tax, Freight) and Cr (Party)
                # and put it into Round Off.
                dr_sum = sum(e["amount"] for e in entries if e["dr_cr"] == "Dr")
                # Add the party Cr to cr_sum
                cr_sum = abs(gross_total)
                
                diff = dr_sum - cr_sum
                if abs(diff) > 0.001:
                    # If dr_sum > cr_sum, we need a Cr entry in Round Off to balance
                    # If dr_sum < cr_sum, we need a Dr entry in Round Off to balance
                    self.log.emit(f"  * Auto-adjusting Round Off by {abs(diff):.2f} to balance voucher.")
                    entries.append({
                        "ledger_id": l_map[round_off_name],
                        "ledger_name": round_off_name,
                        "dr_cr": "Cr" if diff > 0 else "Dr",
                        "amount": round(abs(diff), 2)
                    })

                # Party Cr (Add it last)
                entries.append({
                    "ledger_id": party_id,
                    "ledger_name": v['party_name'],
                    "dr_cr": "Cr",
                    "amount": abs(gross_total)
                })

                # Log the generated entries for debugging
                self.log.emit(f"Generated {len(entries)} entries for voucher {v['v_no']}")
                for e in entries:
                    self.log.emit(f"  - {e['ledger_name']} ({e['dr_cr']}): {e['amount']}")

                # Create Voucher
                payload = {
                    "voucher_type": "Purchase",
                    "date": v['date'],
                    "narration": f"Imported Purchase from Excel - {v['party_name']}",
                    "entries": entries,
                    "invoice_items": voucher_items,
                    "grand_total": abs(gross_total),
                    "metadata": {
                        "excel_v_no": str(v['v_no']),
                        "supplier_inv_no": v['supplier_inv_no'],
                        "supplier_inv_date": v['supplier_inv_date'],
                        "import_source": "Excel"
                    }
                }
                api.create_voucher(payload)

            self.finished.emit(True, f"Successfully imported {total_v} purchase vouchers.")

        except Exception as e:
            import traceback
            self.log.emit(f"Error: {str(e)}\n{traceback.format_exc()}")
            self.finished.emit(False, str(e))

class ImportPurchaseVoucherDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Purchase Vouchers from Excel")
        self.setMinimumSize(600, 400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h3>Purchase Voucher Import (Excel)</h3>"))
        file_lay = QHBoxLayout()
        self.path_lbl = QLabel("No file selected")
        self.path_lbl.setStyleSheet("color: #64748b; font-style: italic;")
        btn_select = QPushButton("Select Excel File...")
        btn_select.clicked.connect(self._select_file)
        file_lay.addWidget(self.path_lbl, 1)
        file_lay.addWidget(btn_select)
        layout.addLayout(file_lay)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.btn_import = QPushButton("Start Import")
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self._start_import)
        layout.addWidget(self.btn_import)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Excel File", "", "Excel Files (*.xlsx *.xls)")
        if path:
            self.path_lbl.setText(path)
            self.btn_import.setEnabled(True)

    def _start_import(self):
        path = self.path_lbl.text()
        self.btn_import.setEnabled(False)
        self.progress.setVisible(True)
        self.log_box.clear()
        self.worker = ImportPurchaseWorker(path)
        self.worker.log.connect(self._append_log); self.worker.progress.connect(self._update_progress)
        self.worker.finished.connect(self._on_finished); self.worker.start()

    def _append_log(self, text): self.log_box.append(text)
    def _update_progress(self, current, total): self.progress.setMaximum(total); self.progress.setValue(current)
    def _on_finished(self, success, message):
        self.progress.setVisible(False); self.btn_import.setEnabled(True)
        if success: QMessageBox.information(self, "Success", message); self.accept()
        else: QMessageBox.warning(self, "Error", message)
