import os
import tempfile
import shutil
from html import escape
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QMessageBox, QFileDialog, QLabel)
from PySide6.QtGui import QPageLayout, QPageSize
from PySide6.QtCore import Qt, QMarginsF, QSize, QSizeF, QEventLoop
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWebEngineCore import QWebEnginePage
from frontend.utils import format_indian_number, format_inr

class InvoicePdfViewer(QDialog):
    def __init__(self, voucher_data, company_data=None, parent=None, invoice_type="A", copy_type="Single"):
        super().__init__(parent)
        vno = voucher_data.get('voucher_no', 'New')
        self.setWindowTitle(f"Invoice Viewer - {vno}")
        self.setWindowState(Qt.WindowState.WindowMaximized)
        self.setStyleSheet("QDialog { background-color: #f1f5f9; }")
        
        self.voucher_data = voucher_data
        self.company_data = company_data or {}
        self.invoice_type = (invoice_type or "A").upper()
        if self.invoice_type not in {"A", "B", "C"}:
            self.invoice_type = "A"
        self.copy_type = "Multiple" if copy_type == "Multiple" else "Single"
        
        vid = voucher_data.get('_id', 'temp')
        self.pdf_path = os.path.join(tempfile.gettempdir(), f"invoice_{vid}_{self.invoice_type}_{self.copy_type}.pdf")
        
        self._generate_pdf()
        self._setup_ui()
        
    def _copy_labels(self):
        if self.copy_type == "Multiple":
            return ["Original Copy", "Duplicate Copy", "Triplicate Copy"]
        return ["Original Copy"]

    def _combine_pages(self, page_docs):
        if len(page_docs) == 1:
            return page_docs[0]

        style = ""
        body_parts = []
        for doc in page_docs:
            if "<style>" in doc and "</style>" in doc and not style:
                style = doc.split("<style>", 1)[1].split("</style>", 1)[0]
            if "<body>" in doc and "</body>" in doc:
                body_parts.append(doc.split("<body>", 1)[1].split("</body>", 1)[0])
            else:
                body_parts.append(doc)

        pages = "\n".join(f'<div class="print-page">{part}</div>' for part in body_parts)
        return f"""
        <html>
        <head>
            <style>
                {style}
                .print-page {{ page-break-after: always; break-after: page; }}
                .print-page:last-child {{ page-break-after: auto; break-after: auto; }}
            </style>
        </head>
        <body>{pages}</body>
        </html>
        """

    def _generate_html(self):
        docs = []
        for label in self._copy_labels():
            if self.invoice_type == "B":
                docs.append(self._generate_format_b_html(label))
            elif self.invoice_type == "C":
                docs.append(self._generate_format_c_html(label))
            else:
                docs.append(self._generate_format_a_html(label))
        return self._combine_pages(docs)

    def _generate_format_a_html(self, copy_label="Original Copy"):
        v = self.voucher_data
        c = self.company_data
        items = v.get("invoice_items", [])

        accounting_items = v.get("items", [])
        party_name = ""; party_address = "N/A"; party_gstin = "N/A"
        adj_ledgers = []   # all non-party, non-sales/purchase entries (tax, discount, expense, etc.)
        grand_total = 0.0

        is_sales = v.get("voucher_type") == "Sales"
        party_dr_cr   = "Dr" if is_sales else "Cr"   
        sp_dr_cr      = "Cr" if is_sales else "Dr"   

        for e in accounting_items:
            dr_cr = e.get("dr_cr")
            gname = (e.get("group_name") or "").upper()
            
            if dr_cr == party_dr_cr and not party_name:
                party_name    = e.get("ledger_name", "")
                grand_total   = e.get("amount", 0.0)
                party_address = e.get("ledger_address", "")
                party_gstin   = e.get("ledger_gst_no", "")
            elif any(x in gname for x in ["DUTIES", "TAX", "EXPENSE", "INCOME", "DISCOUNT"]):
                # Explicitly include these groups in adjustments regardless of Dr/Cr side
                name = e.get("ledger_name", "")
                amt  = e.get("amount", 0.0)
                if name and amt:
                    adj_ledgers.append([name, amt, dr_cr])
            elif dr_cr == sp_dr_cr and any(x in gname for x in ["SALES", "PURCHASE"]):
                # Main Sales/Purchase ledger - skip it
                pass  
            else:
                # Fallback for any other adjustments
                name = e.get("ledger_name", "")
                amt  = e.get("amount", 0.0)
                if name and amt:
                    adj_ledgers.append([name, amt, dr_cr])

        # Gross Subtotal = sum of (Qty * Rate) before any item-level discounts
        gross_subtotal = sum(it.get("qty", 0.0) * it.get("rate", 0.0) for it in items)

        # Aggregate item-level discounts and schemes
        total_item_disc = 0.0
        total_item_scheme = 0.0
        for it in items:
            q = it.get("qty", 0.0)
            r = it.get("rate", 0.0)
            d_p = it.get("discount", 0.0)
            s_v = it.get("scheme", 0.0)
            total_item_disc += (q * r * d_p / 100.0)
            total_item_scheme += s_v

        # Add aggregated item adjustments if they exist and aren't already represented as ledgers
        if total_item_disc > 0.005:
            adj_ledgers.append(["Total Discount (Item-wise)", total_item_disc, "Cr" if is_sales else "Dr"])
        if total_item_scheme > 0.005:
            adj_ledgers.append(["Total Scheme (Item-wise)", total_item_scheme, "Cr" if is_sales else "Dr"])

        # STRICT SORTING: Duties & Taxes -> Expenses -> Discounts
        def adj_sort_key(item_list):
            name = item_list[0].upper().strip()
            # 1. Duties & Taxes (Top)
            if any(t in name for t in ["CGST", "SGST", "IGST", "UTGST", "TAX", "DUTY", "VAT", "GST", "CESS", "SURCHARGE", "TDS", "TCS"]):
                return 0
            # 2. Expenses (Mid)
            if any(e in name for e in ["FREIGHT", "PACKING", "FORWARDING", "EXPENSE", "CHARGE", "ROUND", "INSURANCE", "TRANSPORT", "HANDLING", "POSTAGE", "COURIER", "ADJUSTMENT"]):
                return 1
            # 3. Discounts & Schemes (Bottom)
            if any(d in name for d in ["DISCOUNT", "SCHEME", "LESS", "CASH DISC", "REBATE", "OFFER", "DEDUCTION"]):
                return 2
            return 1 # Default to middle for unknown ledgers

        adj_ledgers.sort(key=adj_sort_key)

        def num_to_words(n):
            if n == 0: return "Zero"
            units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
                     "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
                     "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
            tens  = ["", "", "Twenty", "Thirty", "Forty", "Fifty",
                     "Sixty", "Seventy", "Eighty", "Ninety"]
            def convert(num):
                if num < 20:      return units[int(num)]
                if num < 100:     return tens[int(num // 10)] + (" " + units[int(num % 10)] if num % 10 else "")
                if num < 1000:    return units[int(num // 100)] + " Hundred" + (" and " + convert(num % 100) if num % 100 else "")
                if num < 100000:  return convert(num // 1000) + " Thousand" + (" " + convert(num % 1000) if num % 1000 else "")
                if num < 10000000: return convert(num // 100000) + " Lakh" + (" " + convert(num % 100000) if num % 100000 else "")
                return convert(num // 10000000) + " Crore" + (" " + convert(num % 10000000) if num % 10000000 else "")
            try:
                ip = int(n)
                fp = int(round((n - ip) * 100))
                words = convert(ip)
                if fp > 0: words += " and " + convert(fp) + " Paise"
                return words.strip()
            except Exception:
                return str(n)

        amt_words = num_to_words(grand_total)

        html = f"""
        <html>
        <head>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
                html, body {{
                    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
                    padding: 0; margin: 0; width: 100%; color: #263238;
                }}
                .invoice-container {{
                    width: 100% !important; border: 2px solid #000;
                    border-collapse: collapse; margin: 0; table-layout: fixed;
                }}
                .section-header {{
                    background-color: #eceff1; font-weight: bold;
                    text-transform: uppercase; font-size: 10px; padding: 4px 8px;
                    border-bottom: 1px solid #000; border-top: 1px solid #000;
                }}
                .company-name {{ font-size: 28px; font-weight: 900; color: #000; text-transform: uppercase; line-height: 1; }}
                .tax-invoice-label {{
                    font-size: 18px; font-weight: bold; border: 2px solid #000;
                    padding: 4px 12px; display: inline-block; background: #000; color: #fff;
                }}
                .table-head {{ background-color: #cfd8dc; font-weight: bold; font-size: 9px; text-transform: uppercase; }}
                .full-width-table {{ width: 100% !important; border-collapse: collapse; table-layout: fixed; }}
                th, td {{ word-wrap: break-word; border: 1px solid #000; }}
                .no-border {{ border: none !important; }}
                .text-right  {{ text-align: right; }}
                .text-center {{ text-align: center; }}
                .padding-xs  {{ padding: 2px 4px; }}
                .padding-sm  {{ padding: 5px 8px; }}
            </style>
        </head>
        <body>
            <table class="invoice-container" cellpadding="0" cellspacing="0">
                <!-- Header -->
                <tr>
                    <td colspan="3" class="text-center" style="padding: 10px; border-bottom: 2px solid #000; position: relative;">
                        <div style="position:absolute; right:10px; top:8px; font-size:11px; font-style:italic; font-weight:normal;">{copy_label}</div>
                        <div class="tax-invoice-label">TAX INVOICE</div>
                    </td>
                </tr>
                <tr>
                    <td colspan="2" style="padding: 15px; vertical-align: top; width: 65%;">
                        <div class="company-name">{c.get('name', 'Company Name')}</div>
                        <div style="font-size: 12px; margin-top: 8px; line-height: 1.4;">
                            {c.get('address', 'Address')}<br>
                            <b>GSTIN:</b> {c.get('gst_no', '')}<br>
                            <b>PAN:</b> {c.get('pan', '')}
                        </div>
                    </td>
                    <td style="padding: 0; vertical-align: top; width: 35%;">
                        <table class="full-width-table" style="height: 100%;">
                            <tr>
                                <td class="padding-sm" style="border-top:none; border-left:none;">
                                    <div style="font-size: 10px; font-weight: bold; text-transform: uppercase;">Invoice No.</div>
                                    <div style="font-size: 14px; font-weight: bold; margin-top: 2px;">{v.get('voucher_no', '')}</div>
                                </td>
                                <td class="padding-sm" style="border-top:none; border-right:none;">
                                    <div style="font-size: 10px; font-weight: bold; text-transform: uppercase;">Dated</div>
                                    <div style="font-size: 14px; font-weight: bold; margin-top: 2px;">{v.get('date', '')}</div>
                                </td>
                            </tr>
                            <tr>
                                <td colspan="2" class="padding-sm" style="border-left:none; border-right:none; border-bottom:none;">
                                    <div style="font-size: 10px; font-weight: bold; text-transform: uppercase;">Mode/Terms of Payment</div>
                                    <div style="font-size: 12px; margin-top: 2px;">{v.get('payment_terms', 'Net 30')}</div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                <!-- Billing -->
                <tr>
                    <td style="width: 50%; vertical-align: top;">
                        <div class="section-header">Bill to</div>
                        <div style="padding: 8px; min-height: 80px;">
                            <div style="font-size: 14px; font-weight: bold; text-transform: uppercase;">{party_name}</div>
                            <div style="font-size: 11px; margin-top: 4px; line-height: 1.4;">
                                {party_address or '&nbsp;'}<br>
                                <b>GSTIN/UIN:</b> {party_gstin or 'N/A'}
                            </div>
                        </div>
                    </td>
                    <td colspan="2" style="width: 50%; vertical-align: top;">
                        <div class="section-header">Consignee (Ship to)</div>
                        <div style="padding: 8px; min-height: 80px;">
                            <div style="font-size: 14px; font-weight: bold; text-transform: uppercase;">{party_name}</div>
                            <div style="font-size: 11px; margin-top: 4px; line-height: 1.4;">
                                {party_address or '&nbsp;'}<br>
                                <b>GSTIN/UIN:</b> {party_gstin or 'N/A'}
                            </div>
                        </div>
                    </td>
                </tr>
                <!-- Items -->
                <tr>
                    <td colspan="3" style="padding: 0;">
                        <table class="full-width-table">
                            <thead class="table-head">
                                <tr>
                                    <th style="width:5%;"  class="padding-sm">Sl.</th>
                                    <th style="width:45%;" class="padding-sm">Description of Goods</th>
                                    <th style="width:12%;"  class="padding-sm text-center">HSN/SAC</th>
                                    <th style="width:8%;"  class="padding-sm text-center">Qty</th>
                                    <th style="width:8%;"  class="padding-sm text-center">Unit</th>
                                    <th style="width:10%;"  class="padding-sm text-center">Rate (₹)</th>
                                    <th style="width:12%;" class="padding-sm text-right">Amount (₹)</th>
                                </tr>
                            </thead>
                            <tbody>
        """

        for i, item in enumerate(items, 1):
            q = item.get('qty', 0); r = item.get('rate', 0)
            line_amt = q * r
            html += f"""
                                <tr>
                                    <td class="padding-xs text-center" style="font-size:11px;">{i}</td>
                                    <td class="padding-xs" style="font-size:11px;"><b>{item.get('item_name','')}</b></td>
                                    <td class="padding-xs text-center" style="font-size:11px;">{item.get('hsn_sac', item.get('hsn_code','')) or '—'}</td>
                                    <td class="padding-xs text-center" style="font-size:11px;">{q:g}</td>
                                    <td class="padding-xs text-center" style="font-size:11px;">{item.get('unit','')}</td>
                                    <td class="padding-xs text-right"  style="font-size:11px;">{format_indian_number(r)}</td>
                                    <td class="padding-xs text-right"  style="font-size:11px; font-weight:bold;">{format_indian_number(line_amt)}</td>
                                </tr>
            """

        html += """
                                <tr>
                                    <td class="padding-sm" colspan="7" style="height:50px;"></td>
                                </tr>
        """

        # Gross Total row
        html += f"""
                                <tr style="background-color:#f5f5f5;">
                                    <td colspan="6" class="padding-sm text-right"
                                        style="font-size:11px; font-weight:bold; text-transform:uppercase;">
                                        Gross Total
                                    </td>
                                    <td class="padding-sm text-right" style="font-size:12px; font-weight:bold;">{format_indian_number(gross_subtotal)}</td>
                                </tr>
        """

        # Adjustments list
        for lname, lamt, ldr_cr in adj_ledgers:
            # Determine if it's a deduction (Discount/Scheme) or Addition (Tax/Expense)
            # Sales: Dr Party, Cr Sales. Deductions are Dr (like Discount).
            # But in Sales voucher tax section, you typically select a Discount ledger and enter amount.
            # If Discount is Dr side in Sales, it's a deduction.
            is_deduction = False
            up_name = lname.upper()
            if any(d in up_name for d in ["DISCOUNT", "SCHEME", "LESS", "CASH DISC", "REBATE", "OFFER", "DEDUCTION"]):
                is_deduction = True
            
            disp_amt = f"({format_indian_number(lamt)})" if is_deduction else format_indian_number(lamt)
            html += f"""
                                <tr>
                                    <td colspan="6" class="padding-sm text-right"
                                        style="font-size:11px; font-weight:bold;">{lname}</td>
                                    <td class="padding-sm text-right" style="font-size:11px;">{disp_amt}</td>
                                </tr>
            """

        # Final Invoice Value
        html += f"""
                                <tr style="background-color:#cfd8dc;">
                                    <td colspan="6" class="padding-sm text-right"
                                        style="font-size:12px; font-weight:bold; text-transform:uppercase;">
                                        Total Invoice Value
                                    </td>
                                    <td class="padding-sm text-right"
                                        style="font-size:14px; font-weight:900; border-top:2px solid #000;">{format_indian_number(grand_total)}</td>
                                </tr>
                            </tbody>
                        </table>
                    </td>
                </tr>
                <tr>
                    <td colspan="3" style="padding:10px; border-bottom: 2px solid #000;">
                        <div style="font-size:10px; font-weight:bold; text-transform:uppercase; color:#546e7a;">Amount Chargeable (in words)</div>
                        <div style="font-size:13px; font-weight:bold; margin-top:4px;">Indian Rupees {amt_words} Only</div>
                    </td>
                </tr>
                <tr>
                    <td colspan="2" style="padding:15px; vertical-align:top;">
                        <div style="font-size:10px; font-weight:bold; text-transform:uppercase; margin-bottom:8px;">Declaration / Bank Details</div>
                        <div style="font-size:10px; line-height:1.5;">
                            We declare that this invoice shows the actual price of the goods described and that all particulars are true and correct.<br><br>
                            <b>Bank Name:</b> {c.get('bank_name','')}<br>
                            <b>A/c No.:</b>   {c.get('account_number','')}<br>
                            <b>Branch:</b>    {c.get('branch_name','')}<br>
                            <b>IFSC Code:</b> {c.get('ifsc_code','')}
                        </div>
                    </td>
                    <td style="padding:15px; vertical-align:bottom; text-align:right;">
                        <div style="font-size:11px; font-weight:bold; margin-bottom:50px;">For {c.get('name','Company Name')}</div>
                        <div style="font-size:11px; font-weight:bold; border-top: 1px solid #000; display: inline-block; padding-top: 5px;">Authorized Signatory</div>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        return html

    def _invoice_context(self):
        v = self.voucher_data
        c = self.company_data
        items = v.get("invoice_items", [])
        accounting_items = v.get("items", [])
        is_sales = v.get("voucher_type") == "Sales"
        party_dr_cr = "Dr" if is_sales else "Cr"

        party_name = ""
        party_address = ""
        party_gstin = ""
        grand_total = 0.0
        adjustments = []

        for e in accounting_items:
            dr_cr = e.get("dr_cr")
            gname = (e.get("group_name") or "").upper()
            name = e.get("ledger_name", "")
            amt = float(e.get("amount", 0.0) or 0.0)
            if dr_cr == party_dr_cr and not party_name:
                party_name = name
                party_address = e.get("ledger_address", "")
                party_gstin = e.get("ledger_gst_no", "")
                grand_total = amt
            elif amt and any(x in gname for x in ["DUTIES", "TAX", "EXPENSE", "INCOME", "DISCOUNT"]):
                adjustments.append((name, amt, dr_cr))

        taxable = sum(float(it.get("qty", 0.0) or 0.0) * float(it.get("rate", 0.0) or 0.0) for it in items)
        tax_total = sum(amt for name, amt, _ in adjustments if any(t in name.upper() for t in ["GST", "TAX", "CGST", "SGST", "IGST"]))
        if not grand_total:
            grand_total = taxable + sum(amt for _, amt, _ in adjustments)

        return {
            "v": v,
            "c": c,
            "items": items,
            "party_name": party_name,
            "party_address": party_address,
            "party_gstin": party_gstin,
            "grand_total": grand_total,
            "taxable": taxable,
            "tax_total": tax_total,
            "adjustments": adjustments,
            "is_sales": is_sales,
        }

    def _amount_words(self, n):
        if n == 0:
            return "Zero"
        units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
                 "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
                 "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
        tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty",
                "Sixty", "Seventy", "Eighty", "Ninety"]

        def convert(num):
            if num < 20:
                return units[int(num)]
            if num < 100:
                return tens[int(num // 10)] + (" " + units[int(num % 10)] if num % 10 else "")
            if num < 1000:
                return units[int(num // 100)] + " Hundred" + (" and " + convert(num % 100) if num % 100 else "")
            if num < 100000:
                return convert(num // 1000) + " Thousand" + (" " + convert(num % 1000) if num % 1000 else "")
            if num < 10000000:
                return convert(num // 100000) + " Lakh" + (" " + convert(num % 100000) if num % 100000 else "")
            return convert(num // 10000000) + " Crore" + (" " + convert(num % 10000000) if num % 10000000 else "")

        try:
            ip = int(n)
            fp = int(round((n - ip) * 100))
            words = convert(ip)
            if fp > 0:
                words += " and " + convert(fp) + " Paise"
            return words.strip()
        except Exception:
            return str(n)

    def _generate_format_b_html(self, copy_label="Original Copy"):
        ctx = self._invoice_context()
        v, c, items = ctx["v"], ctx["c"], ctx["items"]
        party_name = escape(ctx["party_name"] or "Party Name")
        party_address = escape(ctx["party_address"] or "")
        party_gstin = escape(ctx["party_gstin"] or "")
        company_name = escape(c.get("name", "Company Name"))
        company_address = escape(c.get("address", "Address"))
        company_gst = escape(c.get("gst_no", ""))
        grand_total = ctx["grand_total"]
        taxable = ctx["taxable"]
        words = self._amount_words(grand_total)

        rows = ""
        for i, item in enumerate(items, 1):
            qty = float(item.get("qty", 0.0) or 0.0)
            rate = float(item.get("rate", 0.0) or 0.0)
            amount = qty * rate
            rows += f"""
                <tr>
                    <td class="center">{i}</td>
                    <td><b>{escape(item.get('item_name', ''))}</b></td>
                    <td class="center">{escape(str(item.get('hsn_sac', item.get('hsn_code', '')) or ''))}</td>
                    <td class="right"><b>{qty:g}</b></td>
                    <td class="right">{format_indian_number(rate)}</td>
                    <td class="center">{escape(item.get('unit', ''))}</td>
                    <td class="right"><b>{format_indian_number(amount)}</b></td>
                </tr>
            """

        adjustment_rows = ""
        for name, amount, _ in ctx["adjustments"]:
            adjustment_rows += f"""
                <tr class="adjustment">
                    <td colspan="6" class="right"><b>{escape(name)}</b></td>
                    <td class="right"><b>{format_indian_number(amount)}</b></td>
                </tr>
            """

        return f"""
        <html>
        <head>
            <style>
                html, body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; color: #000; }}
                .copy-label {{ text-align: right; font-size: 11px; font-style: italic; margin-bottom: 4px; }}
                .title {{ text-align: center; font-weight: 700; font-size: 16px; margin-bottom: 14px; }}
                .invoice {{ width: 100%; border-collapse: collapse; table-layout: fixed; border: 1px solid #333; }}
                td, th {{ border: 1px solid #777; padding: 4px; vertical-align: top; font-size: 11px; }}
                .no-border {{ border: none; }}
                .company {{ font-size: 14px; font-weight: 700; }}
                .small {{ font-size: 10px; }}
                .center {{ text-align: center; }}
                .right {{ text-align: right; }}
                .items td {{ height: 22px; }}
                .blank-row td {{ height: 150px; }}
                .adjustment td {{ height: auto; padding-top: 2px; padding-bottom: 2px; }}
                .total {{ font-weight: 700; font-size: 12px; }}
                .footer-cell {{ height: 84px; }}
            </style>
        </head>
        <body>
            <div class="copy-label">{copy_label}</div>
            <div class="title">Tax Invoice</div>
            <table class="invoice">
                <tr>
                    <td rowspan="7" colspan="3">
                        <div class="company">{company_name}</div>
                        <div>{company_address}</div>
                        <div>{company_gst}</div>
                        <div><b>State Name:</b> {escape(c.get('state', ''))}</div>
                        <br>
                        <div>Buyer</div>
                        <div><b>{party_name}</b></div>
                        <div>{party_address}</div>
                        <div><b>GSTIN/UIN:</b> {party_gstin}</div>
                    </td>
                    <td colspan="2">Invoice No.<br><b>{escape(v.get('voucher_no', ''))}</b></td>
                    <td colspan="2">Dated<br><b>{escape(v.get('date', ''))}</b></td>
                </tr>
                <tr><td colspan="2">Delivery Note</td><td colspan="2">Mode/Terms of Payment</td></tr>
                <tr><td colspan="2">Supplier's Ref.</td><td colspan="2">Other Reference(s)</td></tr>
                <tr><td colspan="2">Buyer's Order No.</td><td colspan="2">Dated</td></tr>
                <tr><td colspan="2">Dispatch Document No.</td><td colspan="2">Delivery Note Date</td></tr>
                <tr><td colspan="2">Dispatched through</td><td colspan="2">Destination</td></tr>
                <tr><td colspan="4">Terms of Delivery</td></tr>
                <tr>
                    <th style="width:6%;">Sl<br>No.</th>
                    <th colspan="2">Description of Services</th>
                    <th>HSN/SAC</th>
                    <th>Quantity</th>
                    <th>Rate<br>per</th>
                    <th>Amount</th>
                </tr>
                <tbody class="items">{rows}<tr class="blank-row"><td colspan="7"></td></tr></tbody>
                {adjustment_rows}
                <tr class="total">
                    <td colspan="4" class="right">Total</td>
                    <td class="right">{sum(float(it.get('qty', 0.0) or 0.0) for it in items):g}</td>
                    <td></td>
                    <td class="right">{format_inr(grand_total, symbol='Rs ')}</td>
                </tr>
                <tr>
                    <td colspan="7">
                        <div class="small">Amount Chargeable (in words)</div>
                        <b>INR {escape(words)} Only</b>
                        <span style="float:right;">E. &amp; O.E</span>
                    </td>
                </tr>
                <tr>
                    <td colspan="2" class="center">HSN/SAC</td>
                    <td colspan="2" class="right">Taxable Value<br><b>{format_indian_number(taxable)}</b></td>
                    <td colspan="2" class="right">Total Tax<br><b>{format_indian_number(ctx['tax_total'])}</b></td>
                    <td class="right">Total<br><b>{format_indian_number(grand_total)}</b></td>
                </tr>
                <tr>
                    <td colspan="4" class="footer-cell">
                        <b>Declaration</b><br>
                        We declare that this invoice shows the actual price of the goods described and that all particulars are true and correct.
                    </td>
                    <td colspan="3" class="footer-cell right">
                        <b>for {company_name}</b><br><br><br><br>
                        Authorised Signatory
                    </td>
                </tr>
            </table>
            <div class="center small" style="margin-top:8px;">This is a Computer Generated Invoice</div>
        </body>
        </html>
        """

    def _generate_format_c_html(self, copy_label="Original Copy"):
        ctx = self._invoice_context()
        v, c, items = ctx["v"], ctx["c"], ctx["items"]
        company_name = escape(c.get("name", "Company Name"))
        party_name = escape(ctx["party_name"] or "Party Name")
        rows = ""
        for i, item in enumerate(items, 1):
            qty = float(item.get("qty", 0.0) or 0.0)
            rate = float(item.get("rate", 0.0) or 0.0)
            rows += f"""
                <tr>
                    <td class="center">{i}</td>
                    <td>{escape(item.get('item_name', ''))}</td>
                    <td class="center">{escape(str(item.get('hsn_sac', item.get('hsn_code', '')) or ''))}</td>
                    <td class="right">{qty:g}</td>
                    <td class="right">{format_indian_number(rate)}</td>
                    <td class="right">{format_indian_number(qty * rate)}</td>
                </tr>
            """

        for name, amount, _ in ctx["adjustments"]:
            rows += f'<tr><td colspan="5" class="right"><b>{escape(name)}</b></td><td class="right">{format_indian_number(amount)}</td></tr>'

        return f"""
        <html>
        <head>
            <style>
                html, body {{ margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; color: #111827; }}
                .wrap {{ border: 2px solid #111; padding: 10px; min-height: 1040px; }}
                .top {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #111; padding-bottom: 8px; }}
                .title {{ text-align: center; font-size: 20px; font-weight: 800; text-transform: uppercase; }}
                .copy {{ font-size: 11px; font-style: italic; }}
                .company {{ font-size: 24px; font-weight: 900; text-transform: uppercase; }}
                .meta {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
                .items {{ width: 100%; border-collapse: collapse; margin-top: 8px; table-layout: fixed; }}
                td, th {{ border: 1px solid #111; padding: 5px; font-size: 11px; vertical-align: top; }}
                th {{ background: #f3f4f6; text-transform: uppercase; }}
                .right {{ text-align: right; }}
                .center {{ text-align: center; }}
                .spacer td {{ height: 250px; }}
                .total {{ font-size: 14px; font-weight: 900; background: #eef2f7; }}
                .footer {{ display: grid; grid-template-columns: 1fr 1fr; border: 1px solid #111; border-top: none; }}
                .footer div {{ padding: 8px; min-height: 100px; font-size: 11px; }}
            </style>
        </head>
        <body>
            <div class="wrap">
                <div class="top">
                    <div>
                        <div class="title">Tax Invoice</div>
                        <div class="company">{company_name}</div>
                        <div>{escape(c.get('address', 'Address'))}</div>
                        <div><b>GSTIN:</b> {escape(c.get('gst_no', ''))}</div>
                    </div>
                    <div class="copy">{copy_label}</div>
                </div>
                <table class="meta">
                    <tr>
                        <td><b>Invoice No.</b><br>{escape(v.get('voucher_no', ''))}</td>
                        <td><b>Dated</b><br>{escape(v.get('date', ''))}</td>
                        <td><b>Place of Supply</b><br>{escape(c.get('state', ''))}</td>
                    </tr>
                    <tr>
                        <td colspan="2"><b>Billed to</b><br>{party_name}<br>{escape(ctx['party_address'] or '')}<br><b>GSTIN/UIN:</b> {escape(ctx['party_gstin'] or '')}</td>
                        <td><b>Shipped to</b><br>{party_name}<br>{escape(ctx['party_address'] or '')}</td>
                    </tr>
                </table>
                <table class="items">
                    <tr>
                        <th style="width:6%;">S.N.</th>
                        <th>Description of Goods</th>
                        <th style="width:14%;">HSN/SAC</th>
                        <th style="width:10%;">Qty</th>
                        <th style="width:12%;">Rate</th>
                        <th style="width:16%;">Amount</th>
                    </tr>
                    {rows}
                    <tr class="spacer"><td colspan="6"></td></tr>
                    <tr class="total"><td colspan="5" class="right">Grand Total</td><td class="right">{format_inr(ctx['grand_total'], symbol='Rs ')}</td></tr>
                </table>
                <div style="border:1px solid #111;border-top:none;padding:8px;font-size:12px;"><b>Rupees {escape(self._amount_words(ctx['grand_total']))} Only</b></div>
                <div class="footer">
                    <div><b>Terms &amp; Conditions</b><br>E. &amp; O.E.<br>Goods once sold will not be taken back.</div>
                    <div class="right"><b>for {company_name}</b><br><br><br><br>Authorised Signatory</div>
                </div>
            </div>
        </body>
        </html>
        """

    def _generate_pdf(self):
        html = self._generate_html()
        page = QWebEnginePage()
        layout = QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait, QMarginsF(12.7, 12.7, 12.7, 12.7))
        loop = QEventLoop()
        def on_load_finished(ok):
            if ok: page.printToPdf(self.pdf_path, layout)
            else: loop.quit()
        def on_pdf_finished(path, success): loop.quit()
        page.loadFinished.connect(on_load_finished)
        page.pdfPrintingFinished.connect(on_pdf_finished)
        page.setHtml(html)
        loop.exec()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        toolbar = QHBoxLayout()
        btn_base = "QPushButton { padding: 8px 20px; border-radius: 6px; font-weight: bold; color: white; border: none; min-width: 100px; }"
        save_btn = QPushButton("Save as PDF"); save_btn.setStyleSheet(btn_base + " QPushButton { background-color: #10b981; }")
        save_btn.clicked.connect(self._save_pdf)
        print_btn = QPushButton("Print Document"); print_btn.setStyleSheet(btn_base + " QPushButton { background-color: #3b82f6; }")
        print_btn.clicked.connect(self._print_pdf)
        zoom_in_btn = QPushButton("Zoom In (+)"); zoom_in_btn.setStyleSheet(btn_base + " QPushButton { background-color: #64748b; }")
        zoom_in_btn.clicked.connect(self._zoom_in)
        zoom_out_btn = QPushButton("Zoom Out (-)"); zoom_out_btn.setStyleSheet(btn_base + " QPushButton { background-color: #64748b; }")
        zoom_out_btn.clicked.connect(self._zoom_out)
        page_count = max(1, len(self._copy_labels()))
        page_lbl = QLabel(f"{page_count} copy" + ("" if page_count == 1 else "ies"))
        page_lbl.setStyleSheet("color: #475569; font-weight: bold; padding: 0 10px;")
        toolbar.addWidget(save_btn); toolbar.addWidget(print_btn); toolbar.addWidget(zoom_in_btn); toolbar.addWidget(zoom_out_btn); toolbar.addWidget(page_lbl); toolbar.addStretch()
        layout.addLayout(toolbar)
        self.doc = QPdfDocument(self); self.doc.load(self.pdf_path)
        self.view = QPdfView(self)
        self.view.setDocument(self.doc)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setPageSpacing(10)
        self.view.setZoomMode(QPdfView.ZoomMode.FitInView)
        layout.addWidget(self.view)
        
    def _save_pdf(self):
        vno = self.voucher_data.get('voucher_no', 'invoice')
        path, _ = QFileDialog.getSaveFileName(self, "Save Invoice PDF", f"Invoice_{vno}.pdf", "PDF Files (*.pdf)")
        if path: shutil.copy2(self.pdf_path, path); QMessageBox.information(self, "Success", "PDF saved.")
            
    def _print_pdf(self):
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            page = QWebEnginePage()
            loop = QEventLoop()
            def on_load_finished(ok):
                if ok: page.print(printer, lambda s: loop.quit())
                else: loop.quit()
            page.loadFinished.connect(on_load_finished)
            page.setHtml(self._generate_html())
            loop.exec()

    def _zoom_in(self):
        self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(self.view.zoomFactor() * 1.2)

    def _zoom_out(self):
        self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(self.view.zoomFactor() / 1.2)
