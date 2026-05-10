import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QTextEdit, QLabel, QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from frontend import api_client as api
import frontend.session as session
import re

class ImportWorker(QThread):
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
                return float(v) if v is not None and str(v).lower() != "nan" else 0.0
            except: return 0.0

        try:
            self.log.emit("Reading Excel file: " + self.file_path)
            df = pd.read_excel(self.file_path)
            
            # Basic validation
            required = ['Date', 'Particulars', 'Voucher No']
            for col in required:
                if col not in df.columns:
                    self.finished.emit(False, f"Missing required column: {col}")
                    return

            self.log.emit("Fetching existing data for mapping...")
            groups = api.list_groups()
            g_map = {g['name']: str(g['_id']) for g in groups}
            
            # Required Groups
            debtors_gid = g_map.get("Sundry Debtors")
            sales_gid = g_map.get("Sales Accounts")
            taxes_gid = g_map.get("Duties & Taxes")
            expenses_gid = g_map.get("Expenses (Indirect)")

            if not all([debtors_gid, sales_gid, taxes_gid, expenses_gid]):
                self.finished.emit(False, "Essential accounting groups (Sundry Debtors, Sales Accounts, Duties & Taxes, Expenses (Indirect)) not found.")
                return

            ledgers = api.list_ledgers()
            l_map = {l['name']: str(l['_id']) for l in ledgers}
            
            # Ensure Round Off ledger exists
            round_off_name = "Round Off"
            if round_off_name not in l_map:
                self.log.emit(f"Creating '{round_off_name}' ledger...")
                l_res = api.create_ledger({
                    "name": round_off_name,
                    "group": expenses_gid,
                    "opening_balance": 0,
                    "dr_cr": "Dr"
                })
                l_map[round_off_name] = str(l_res['_id'])

            items = api.list_stock_items()
            i_map = {i['name']: str(i['_id']) for i in items}
            
            units = api.list_units()
            u_map = {u['name']: str(u['_id']) for u in units}

            # Parse vouchers
            vouchers = []
            current_v = None
            
            for index, row in df.iterrows():
                # Date handling: convert to yyyy-mm-dd string
                raw_date = row.get('Date')
                if pd.notnull(raw_date):
                    if hasattr(raw_date, 'strftime'):
                        date_val = raw_date.strftime('%Y-%m-%d')
                    else:
                        date_val = str(raw_date).split(' ')[0].strip()
                else:
                    date_val = 'nan'

                v_no = str(row.get('Voucher No', '')).strip()
                particulars = str(row.get('Particulars', '')).strip()
                
                # If Date and Voucher No are present, it's a new voucher row
                if date_val and date_val != 'nan' and v_no and v_no != 'nan':
                    if current_v:
                        vouchers.append(current_v)
                    
                    current_v = {
                        "date": date_val,
                        "v_no": v_no,
                        "party_name": particulars,
                        "gstin": str(row.get('GSTIN/UIN', '')).strip(),
                        "items": [],
                        "tax_details": {
                            "cgst_9": _clean(row.get('CGST 9%', 0)),
                            "sgst_9": _clean(row.get('SGST 9%', 0)),
                            "cgst_14": _clean(row.get('Cgst 14%', 0)),
                            "sgst_14": _clean(row.get('Sgst 14%', 0)),
                            "round_off": _clean(row.get('ROUND OFF', 0)),
                            "gross_total": _clean(row.get('Gross Total', 0)),
                            "sale_value": _clean(row.get('Sale', 0))
                        }
                    }
                elif particulars and particulars != 'nan' and current_v:
                    # Item row
                    qty_str = str(row.get('Quantity', '')).strip()
                    val = row.get('Value', 0)
                    
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
                    
                    current_v["items"].append({
                        "name": particulars,
                        "qty": _clean(qty),
                        "unit": unit,
                        "value": _clean(val)
                    })
            
            if current_v:
                vouchers.append(current_v)

            total_v = len(vouchers)
            self.log.emit(f"Found {total_v} vouchers to import.")

            # Process Import
            for i, v in enumerate(vouchers):
                self.progress.emit(i + 1, total_v)
                self.log.emit(f"Importing Voucher {v['v_no']} for {v['party_name']}...")
                
                # 1. Ensure Party Ledger
                party_id = l_map.get(v['party_name'])
                if not party_id:
                    self.log.emit(f"Creating Party Ledger: {v['party_name']}")
                    p_res = api.create_ledger({
                        "name": v['party_name'],
                        "group": debtors_gid,
                        "gstin": v['gstin'] if v['gstin'] != 'nan' else "",
                        "opening_balance": 0,
                        "dr_cr": "Dr"
                    })
                    party_id = str(p_res['id'])
                    l_map[v['party_name']] = party_id

                # 2. Ensure Items
                voucher_items = []
                for it in v['items']:
                    item_id = i_map.get(it['name'])
                    if not item_id:
                        self.log.emit(f"Creating Item: {it['name']}")
                        
                        # Extract Group (e.g. '9405' from '9405 ELECTRICAL GOODS')
                        m = re.match(r"^(\d+)\s+(.*)", it['name'])
                        group_name = "General"
                        if m:
                            group_name = m.group(1)
                        
                        # Ensure group
                        g_res_list = api.list_stock_groups()
                        sg_map = {sg['name']: str(sg['_id']) for sg in g_res_list}
                        if group_name not in sg_map:
                            self.log.emit(f"Creating Stock Group: {group_name}")
                            sg_res = api.create_stock_group({"name": group_name})
                            sg_id = str(sg_res['id'])
                        else:
                            sg_id = sg_map[group_name]

                        # Ensure unit
                        if it['unit'] not in u_map:
                            u_res = api.create_unit({"name": it['unit']})
                            u_map[it['unit']] = str(u_res['id'])
                        
                        i_res = api.create_stock_item({
                            "name": it['name'],
                            "unit": u_map[it['unit']],
                            "stock_group": sg_id,
                            "opening_qty": 0,
                            "standard_rate": 0
                        })
                        item_id = str(i_res['id'])
                        i_map[it['name']] = item_id
                    
                    # Calculate rate for voucher
                    rate = it['value'] / it['qty'] if it['qty'] > 0 else 0
                    voucher_items.append({
                        "item_id": item_id,
                        "item_name": it['name'],
                        "qty": it['qty'],
                        "unit": u_map.get(it['unit'], it['unit']),
                        "rate": rate,
                        "amount": it['value']
                    })

                # 3. Build Entries
                entries = []
                # Party Dr
                entries.append({
                    "ledger_id": party_id,
                    "ledger_name": v['party_name'],
                    "dr_cr": "Dr",
                    "amount": v['tax_details']['gross_total']
                })
                
                # Sales Cr (Total Sale)
                # Ensure a default Sales Ledger exists or create one based on 'Sale' column logic if needed
                sales_ledger_name = "Sales"
                if sales_ledger_name not in l_map:
                    s_res = api.create_ledger({"name": sales_ledger_name, "group": sales_gid, "dr_cr": "Cr"})
                    l_map[sales_ledger_name] = str(s_res['id'])
                
                entries.append({
                    "ledger_id": l_map[sales_ledger_name],
                    "ledger_name": sales_ledger_name,
                    "dr_cr": "Cr",
                    "amount": v['tax_details']['sale_value']
                })

                # Taxes Cr
                for tax_key, tax_val in v['tax_details'].items():
                    if tax_key == 'gross_total' or tax_key == 'sale_value' or tax_key == 'round_off':
                        continue
                    if tax_val and tax_val != 0:
                        tax_name = tax_key.replace('_', '@').upper() + "%" # e.g. CGST@9%
                        if tax_name not in l_map:
                            t_res = api.create_ledger({"name": tax_name, "group": taxes_gid, "dr_cr": "Cr"})
                            l_map[tax_name] = str(t_res['id'])
                        
                        entries.append({
                            "ledger_id": l_map[tax_name],
                            "ledger_name": tax_name,
                            "dr_cr": "Cr",
                            "amount": abs(tax_val)
                        })

                # Round Off
                roff = v['tax_details']['round_off']
                if roff and abs(roff) > 0.005:
                    # If GrossTotal = Sale + Tax + RoundOff, then RoundOff is a Credit (like Sales/Tax)
                    # Party(Dr) = Sales(Cr) + Tax(Cr) + RoundOff(Cr)
                    # So if roff > 0, it's a Cr.
                    entries.append({
                        "ledger_id": l_map[round_off_name],
                        "ledger_name": round_off_name,
                        "dr_cr": "Cr" if roff > 0 else "Dr",
                        "amount": abs(roff)
                    })

                # Create Voucher
                api.create_voucher({
                    "voucher_type": "Sales",
                    "v_no": str(v['v_no']),
                    "date": v['date'],
                    "narration": f"Imported from Excel - {v['party_name']}",
                    "entries": entries,
                    "invoice_items": voucher_items,
                    "grand_total": _clean(v['tax_details']['gross_total'])
                })

            self.finished.emit(True, f"Successfully imported {total_v} vouchers.")

        except Exception as e:
            self.log.emit(f"Error: {str(e)}")
            self.finished.emit(False, str(e))

class ImportSalesVoucherDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Sales Vouchers from Excel")
        self.setMinimumSize(600, 400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("<h3>Sales Voucher Import (Excel)</h3>")
        layout.addWidget(header)

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
        self.log_box.setPlaceholderText("Import logs will appear here...")
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
        self.progress.setValue(0)
        self.log_box.clear()

        self.worker = ImportWorker(path)
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
            QMessageBox.information(self, "Import Successful", message)
            self.accept()
        else:
            QMessageBox.warning(self, "Import Failed", f"An error occurred during import:\n\n{message}")
