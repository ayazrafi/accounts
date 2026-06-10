import json
import os
import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QDateEdit, QTabWidget, QFrame, QFormLayout,
    QGridLayout, QScrollArea, QDialog, QMenu
)
from PySide6.QtCore import Qt, QDate, QSize, QThread, Signal
from PySide6.QtGui import QFont, QIcon, QAction
import frontend.api_client as api
from frontend.utils import get_icon, format_inr, format_indian_number

class GSTRReportPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        # Premium Main Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(16)

        # Title
        title = QLabel("GST Returns & Reports")
        title.setStyleSheet("font-size:24px;font-weight:bold;color:#1e3a5f;")
        self.layout.addWidget(title)

        # Period Filter Bar
        self.filter_bar = QFrame()
        self.filter_bar.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; }")
        filter_lay = QHBoxLayout(self.filter_bar)
        filter_lay.setContentsMargins(16, 12, 16, 12)
        filter_lay.setSpacing(12)

        filter_lay.addWidget(QLabel("<b>Period From:</b>"))
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addMonths(-1))
        self.from_date.setDisplayFormat("dd-MMM-yyyy")
        self.from_date.setStyleSheet("padding: 5px; border-radius: 4px; border: 1px solid #cbd5e1;")
        filter_lay.addWidget(self.from_date)

        filter_lay.addWidget(QLabel("<b>To:</b>"))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        self.to_date.setDisplayFormat("dd-MMM-yyyy")
        self.to_date.setStyleSheet("padding: 5px; border-radius: 4px; border: 1px solid #cbd5e1;")
        filter_lay.addWidget(self.to_date)

        self.btn_refresh = QPushButton(" Refresh")
        self.btn_refresh.setIcon(get_icon("frontend/assets/icons/refresh-cw.svg", "#ffffff"))
        self.btn_refresh.setStyleSheet("background: #2563eb; color: #ffffff; font-weight: bold; border-radius: 6px; padding: 6px 14px;")
        self.btn_refresh.clicked.connect(self.load_data)
        filter_lay.addWidget(self.btn_refresh)

        filter_lay.addStretch()

        # Action Buttons
        self.btn_json = QPushButton(" Generate JSON")
        self.btn_json.setStyleSheet("background: #0ea5e9; color: white; font-weight: bold; padding: 6px 12px; border-radius: 6px;")
        json_menu = QMenu(self)
        json_menu.setStyleSheet("""
            QMenu { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 6px 16px; border-radius: 4px; color: #0f172a; }
            QMenu::item:selected { background-color: #f1f5f9; color: #2563eb; }
        """)
        action_gstr1_json = QAction("GSTR-1 JSON", self)
        action_gstr1_json.triggered.connect(self.generate_gstr1_json)
        json_menu.addAction(action_gstr1_json)
        action_iff_json = QAction("IFF JSON", self)
        action_iff_json.triggered.connect(self.generate_iff_json)
        json_menu.addAction(action_iff_json)
        self.btn_json.setMenu(json_menu)
        filter_lay.addWidget(self.btn_json)

        self.btn_excel = QPushButton(" Export Excel")
        self.btn_excel.setStyleSheet("background: #16a34a; color: white; font-weight: bold; padding: 6px 12px; border-radius: 6px;")
        excel_menu = QMenu(self)
        excel_menu.setStyleSheet("""
            QMenu { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 6px 16px; border-radius: 4px; color: #0f172a; }
            QMenu::item:selected { background-color: #f1f5f9; color: #2563eb; }
        """)
        action_gstr1_excel = QAction("GSTR-1 Excel", self)
        action_gstr1_excel.triggered.connect(self.export_gstr1_excel)
        excel_menu.addAction(action_gstr1_excel)
        action_iff_excel = QAction("IFF Excel", self)
        action_iff_excel.triggered.connect(self.export_iff_excel)
        excel_menu.addAction(action_iff_excel)
        self.btn_excel.setMenu(excel_menu)
        filter_lay.addWidget(self.btn_excel)

        self.btn_import = QPushButton(" Import GSTR-1")
        self.btn_import.setStyleSheet("background: #7c3aed; color: white; font-weight: bold; padding: 6px 12px; border-radius: 6px;")
        self.btn_import.clicked.connect(self.import_gstr1_data)
        filter_lay.addWidget(self.btn_import)

        self.layout.addWidget(self.filter_bar)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #cbd5e1; background: #ffffff; border-radius: 8px; }
            QTabBar::tab { background: #f1f5f9; color: #475569; padding: 10px 20px; font-weight: bold; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: #ffffff; color: #2563eb; border-bottom: 2px solid #2563eb; }
        """)

        # 1. GSTR-1 Tab
        self.tab_gstr1 = QWidget()
        self._build_gstr1_tab()
        self.tabs.addTab(self.tab_gstr1, "GSTR-1 (Outward Supplies)")

        # 2. GSTR-3B Tab
        self.tab_gstr3b = QWidget()
        self._build_gstr3b_tab()
        self.tabs.addTab(self.tab_gstr3b, "GSTR-3B (Tax Computation)")

        # 3. GST Summary Tab
        self.tab_summary = QWidget()
        self._build_summary_tab()
        self.tabs.addTab(self.tab_summary, "GST Summary (ITC vs Liability)")

        self.layout.addWidget(self.tabs)
        
        # Load initially
        self.load_data()

    def _build_gstr1_tab(self):
        lay = QVBoxLayout(self.tab_gstr1)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # GSTR-1 Sub-tabs
        self.gstr1_subtabs = QTabWidget()
        self.gstr1_subtabs.setStyleSheet("QTabWidget::pane { border: 1px solid #e2e8f0; }")

        # B2B Table
        self.table_b2b = self._create_standard_table(["Invoice No", "Date", "Receiver GSTIN", "Receiver Name", "Place of Supply", "Taxable Value", "CGST", "SGST", "IGST", "Invoice Value"])
        self.gstr1_subtabs.addTab(self.table_b2b, "B2B Invoices")

        # B2CS Table
        self.table_b2cs = self._create_standard_table(["Invoice No", "Date", "Receiver Name", "Place of Supply", "Taxable Value", "CGST", "SGST", "IGST", "Invoice Value"])
        self.gstr1_subtabs.addTab(self.table_b2cs, "B2C Small")

        # B2CL Table
        self.table_b2cl = self._create_standard_table(["Invoice No", "Date", "Place of Supply", "Taxable Value", "CGST", "SGST", "IGST", "Invoice Value"])
        self.gstr1_subtabs.addTab(self.table_b2cl, "B2C Large")

        # Credit/Debit Notes
        self.table_cdn = self._create_standard_table(["Voucher No", "Date", "GSTIN", "Receiver Name", "Note Type", "Taxable Value", "CGST", "SGST", "IGST", "Invoice Value"])
        self.gstr1_subtabs.addTab(self.table_cdn, "Credit / Debit Notes")

        # HSN Summary
        self.table_hsn = self._create_standard_table(["HSN/SAC", "Description", "UQC", "Total Qty", "Taxable Value", "CGST", "SGST", "IGST", "Total Value"])
        self.gstr1_subtabs.addTab(self.table_hsn, "HSN Summary")

        lay.addWidget(self.gstr1_subtabs)

        # Summary Row below tables
        self.gstr1_summary = QFrame()
        self.gstr1_summary.setStyleSheet("background: #f8fafc; border-top: 1px solid #cbd5e1; border-radius: 4px;")
        g_lay = QHBoxLayout(self.gstr1_summary)
        g_lay.setContentsMargins(12, 8, 12, 8)
        self.lbl_gstr1_summary = QLabel("<b>Summary:</b> Total Invoices: 0 | Total Taxable: ₹0.00 | CGST: ₹0.00 | SGST: ₹0.00 | IGST: ₹0.00")
        self.lbl_gstr1_summary.setStyleSheet("font-size: 13px; color: #1e293b;")
        g_lay.addWidget(self.lbl_gstr1_summary)
        lay.addWidget(self.gstr1_summary)

    def _build_gstr3b_tab(self):
        lay = QVBoxLayout(self.tab_gstr3b)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        c_lay = QVBoxLayout(content)
        c_lay.setSpacing(20)

        # Section 3.1: Outward supplies
        sec31_frame = QFrame()
        sec31_frame.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;")
        sec31_lay = QVBoxLayout(sec31_frame)
        sec31_lay.setContentsMargins(16, 16, 16, 16)
        
        lbl_31 = QLabel("3.1 Details of Outward Supplies and inward supplies liable to reverse charge")
        lbl_31.setStyleSheet("font-size:14px;font-weight:bold;color:#1e3a5f;")
        sec31_lay.addWidget(lbl_31)

        self.table_31 = QTableWidget(1, 5)
        self.table_31.setHorizontalHeaderLabels(["Nature of Supplies", "Total Taxable Value", "Integrated Tax (IGST)", "Central Tax (CGST)", "State/UT Tax (SGST)"])
        self.table_31.setItem(0, 0, QTableWidgetItem("(a) Outward taxable supplies (other than zero rated, nil rated/exempted)"))
        self.table_31.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_31.setFixedHeight(80)
        self.table_31.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        sec31_lay.addWidget(self.table_31)

        c_lay.addWidget(sec31_frame)

        # Section 4: Eligible ITC
        sec4_frame = QFrame()
        sec4_frame.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;")
        sec4_lay = QVBoxLayout(sec4_frame)
        sec4_lay.setContentsMargins(16, 16, 16, 16)

        lbl_4 = QLabel("4. Eligible Input Tax Credit (ITC)")
        lbl_4.setStyleSheet("font-size:14px;font-weight:bold;color:#1e3a5f;")
        sec4_lay.addWidget(lbl_4)

        self.table_4 = QTableWidget(1, 5)
        self.table_4.setHorizontalHeaderLabels(["Details", "Total Taxable Value", "Integrated Tax (IGST)", "Central Tax (CGST)", "State/UT Tax (SGST)"])
        self.table_4.setItem(0, 0, QTableWidgetItem("(A)(5) All other ITC (Purchases)"))
        self.table_4.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_4.setFixedHeight(80)
        self.table_4.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        sec4_lay.addWidget(self.table_4)

        c_lay.addWidget(sec4_frame)
        c_lay.addStretch()

        scroll.setWidget(content)
        lay.addWidget(scroll)

    def _build_summary_tab(self):
        lay = QVBoxLayout(self.tab_summary)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(20)

        # KPI Cards (Output, ITC, Net Payable)
        kpi_bar = QHBoxLayout()
        kpi_bar.setSpacing(16)

        # Output Card
        self.card_output = self._create_kpi_card("TOTAL OUTPUT LIABILITY", "₹ 0.00", "#1e3a5f")
        kpi_bar.addWidget(self.card_output)

        # ITC Card
        self.card_itc = self._create_kpi_card("TOTAL ELIGIBLE ITC", "₹ 0.00", "#16a34a")
        kpi_bar.addWidget(self.card_itc)

        # Net Card
        self.card_net = self._create_kpi_card("NET GST PAYABLE", "₹ 0.00", "#dc2626")
        kpi_bar.addWidget(self.card_net)

        lay.addLayout(kpi_bar)

        # Reconciliation Table
        recon_frame = QFrame()
        recon_frame.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px;")
        recon_lay = QVBoxLayout(recon_frame)
        recon_lay.setContentsMargins(16, 16, 16, 16)
        recon_lay.setSpacing(12)

        recon_lbl = QLabel("Tax Reconciliation & Payable Summary")
        recon_lbl.setStyleSheet("font-size:15px;font-weight:bold;color:#1e3a5f;")
        recon_lay.addWidget(recon_lbl)

        self.table_recon = QTableWidget(4, 4)
        self.table_recon.setHorizontalHeaderLabels(["Tax Component", "Outward Liability (Output)", "Input Tax Credit (ITC)", "Net Payable / (Refundable)"])
        self.table_recon.setItem(0, 0, QTableWidgetItem("Central Tax (CGST)"))
        self.table_recon.setItem(1, 0, QTableWidgetItem("State/UT Tax (SGST)"))
        self.table_recon.setItem(2, 0, QTableWidgetItem("Integrated Tax (IGST)"))
        self.table_recon.setItem(3, 0, QTableWidgetItem("TOTAL"))
        
        self.table_recon.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_recon.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_recon.setFixedHeight(180)
        recon_lay.addWidget(self.table_recon)

        lay.addWidget(recon_frame)
        lay.addStretch()

    def _create_standard_table(self, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setStyleSheet("""
            QTableWidget { background: white; border: none; gridline-color: #f1f5f9; }
            QHeaderView::section { background: #f8fafc; padding: 8px; border: none; border-bottom: 2px solid #e2e8f0; font-weight: bold; color: #475569; }
        """)
        return table

    def _create_kpi_card(self, title, val, color):
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumHeight(110)
        card.setStyleSheet(f"""
            QFrame#card {{
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-left: 5px solid {color};
                border-radius: 8px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748b; letter-spacing: 0.5px;")
        val_lbl = QLabel(val)
        val_lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")
        
        lay.addWidget(title_lbl)
        lay.addWidget(val_lbl)
        return card

    def load_data(self):
        f_dt = self.from_date.date().toString("yyyy-MM-dd")
        t_dt = self.to_date.date().toString("yyyy-MM-dd")

        try:
            # 1. GSTR-1 Data
            self.g1_data = api.gstr1(f_dt, t_dt)
            self._populate_gstr1(self.g1_data)

            # 2. GSTR-3B Data
            self.g3_data = api.gstr3b(f_dt, t_dt)
            self._populate_gstr3b(self.g3_data)

            # 3. GST Summary Data
            self.gsum_data = api.gst_summary(f_dt, t_dt)
            self._populate_gst_summary(self.gsum_data)

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load GSTR data: {str(e)}")

    def _populate_gstr1(self, data):
        # B2B
        b2b = data.get("b2b", [])
        self.table_b2b.setRowCount(0)
        for r in b2b:
            row = self.table_b2b.rowCount()
            self.table_b2b.insertRow(row)
            self.table_b2b.setItem(row, 0, QTableWidgetItem(r["invoice_no"]))
            self.table_b2b.setItem(row, 1, QTableWidgetItem(r["invoice_date"]))
            self.table_b2b.setItem(row, 2, QTableWidgetItem(r["gstin"]))
            self.table_b2b.setItem(row, 3, QTableWidgetItem(r["receiver_name"]))
            self.table_b2b.setItem(row, 4, QTableWidgetItem(r["place_of_supply"]))
            self.table_b2b.setItem(row, 5, QTableWidgetItem(format_indian_number(r["taxable_value"])))
            self.table_b2b.setItem(row, 6, QTableWidgetItem(format_indian_number(r["cgst"])))
            self.table_b2b.setItem(row, 7, QTableWidgetItem(format_indian_number(r["sgst"])))
            self.table_b2b.setItem(row, 8, QTableWidgetItem(format_indian_number(r["igst"])))
            self.table_b2b.setItem(row, 9, QTableWidgetItem(format_indian_number(r["invoice_value"])))

        # B2CS
        b2cs = data.get("b2cs", [])
        self.table_b2cs.setRowCount(0)
        for r in b2cs:
            row = self.table_b2cs.rowCount()
            self.table_b2cs.insertRow(row)
            self.table_b2cs.setItem(row, 0, QTableWidgetItem(r["invoice_no"]))
            self.table_b2cs.setItem(row, 1, QTableWidgetItem(r["invoice_date"]))
            self.table_b2cs.setItem(row, 2, QTableWidgetItem(r["receiver_name"]))
            self.table_b2cs.setItem(row, 3, QTableWidgetItem(r["place_of_supply"]))
            self.table_b2cs.setItem(row, 4, QTableWidgetItem(format_indian_number(r["taxable_value"])))
            self.table_b2cs.setItem(row, 5, QTableWidgetItem(format_indian_number(r["cgst"])))
            self.table_b2cs.setItem(row, 6, QTableWidgetItem(format_indian_number(r["sgst"])))
            self.table_b2cs.setItem(row, 7, QTableWidgetItem(format_indian_number(r["igst"])))
            self.table_b2cs.setItem(row, 8, QTableWidgetItem(format_indian_number(r["invoice_value"])))

        # B2CL
        b2cl = data.get("b2cl", [])
        self.table_b2cl.setRowCount(0)
        for r in b2cl:
            row = self.table_b2cl.rowCount()
            self.table_b2cl.insertRow(row)
            self.table_b2cl.setItem(row, 0, QTableWidgetItem(r["invoice_no"]))
            self.table_b2cl.setItem(row, 1, QTableWidgetItem(r["invoice_date"]))
            self.table_b2cl.setItem(row, 2, QTableWidgetItem(r["place_of_supply"]))
            self.table_b2cl.setItem(row, 3, QTableWidgetItem(format_indian_number(r["taxable_value"])))
            self.table_b2cl.setItem(row, 4, QTableWidgetItem(format_indian_number(r["cgst"])))
            self.table_b2cl.setItem(row, 5, QTableWidgetItem(format_indian_number(r["sgst"])))
            self.table_b2cl.setItem(row, 6, QTableWidgetItem(format_indian_number(r["igst"])))
            self.table_b2cl.setItem(row, 7, QTableWidgetItem(format_indian_number(r["invoice_value"])))

        # Credit / Debit Notes
        cdn = data.get("cdnr", []) + data.get("cdnur", [])
        self.table_cdn.setRowCount(0)
        for r in cdn:
            row = self.table_cdn.rowCount()
            self.table_cdn.insertRow(row)
            self.table_cdn.setItem(row, 0, QTableWidgetItem(r["invoice_no"]))
            self.table_cdn.setItem(row, 1, QTableWidgetItem(r["invoice_date"]))
            self.table_cdn.setItem(row, 2, QTableWidgetItem(r.get("gstin", "")))
            self.table_cdn.setItem(row, 3, QTableWidgetItem(r["receiver_name"]))
            self.table_cdn.setItem(row, 4, QTableWidgetItem(r.get("note_type", "C")))
            self.table_cdn.setItem(row, 5, QTableWidgetItem(format_indian_number(r["taxable_value"])))
            self.table_cdn.setItem(row, 6, QTableWidgetItem(format_indian_number(r["cgst"])))
            self.table_cdn.setItem(row, 7, QTableWidgetItem(format_indian_number(r["sgst"])))
            self.table_cdn.setItem(row, 8, QTableWidgetItem(format_indian_number(r["igst"])))
            self.table_cdn.setItem(row, 9, QTableWidgetItem(format_indian_number(r["invoice_value"])))

        # HSN Summary
        hsn = data.get("hsn", [])
        self.table_hsn.setRowCount(0)
        for r in hsn:
            row = self.table_hsn.rowCount()
            self.table_hsn.insertRow(row)
            self.table_hsn.setItem(row, 0, QTableWidgetItem(r["hsn_sc"]))
            self.table_hsn.setItem(row, 1, QTableWidgetItem(r["desc"]))
            self.table_hsn.setItem(row, 2, QTableWidgetItem(r["uqc"]))
            self.table_hsn.setItem(row, 3, QTableWidgetItem(str(r["qty"])))
            self.table_hsn.setItem(row, 4, QTableWidgetItem(format_indian_number(r["txval"])))
            self.table_hsn.setItem(row, 5, QTableWidgetItem(format_indian_number(r["camt"])))
            self.table_hsn.setItem(row, 6, QTableWidgetItem(format_indian_number(r["samt"])))
            self.table_hsn.setItem(row, 7, QTableWidgetItem(format_indian_number(r["iamt"])))
            self.table_hsn.setItem(row, 8, QTableWidgetItem(format_indian_number(r["val"])))

        # Overall summary text
        ds = data.get("doc_summary", {})
        self.lbl_gstr1_summary.setText(
            f"<b>Summary:</b> Total Vouchers: {ds.get('total_invoices', 0)} | "
            f"Total Taxable: {format_inr(ds.get('taxable_value', 0.0))} | "
            f"CGST: {format_inr(ds.get('cgst', 0.0))} | "
            f"SGST: {format_inr(ds.get('sgst', 0.0))} | "
            f"IGST: {format_inr(ds.get('igst', 0.0))} | "
            f"<b>Grand Total Value:</b> {format_inr(ds.get('total_value', 0.0))}"
        )

    def _populate_gstr3b(self, data):
        # Section 3.1
        o = data.get("outward_taxable", {})
        self.table_31.setItem(0, 1, QTableWidgetItem(format_indian_number(o.get("taxable_value", 0.0))))
        self.table_31.setItem(0, 2, QTableWidgetItem(format_indian_number(o.get("igst", 0.0))))
        self.table_31.setItem(0, 3, QTableWidgetItem(format_indian_number(o.get("cgst", 0.0))))
        self.table_31.setItem(0, 4, QTableWidgetItem(format_indian_number(o.get("sgst", 0.0))))

        # Section 4
        i = data.get("eligible_itc", {})
        self.table_4.setItem(0, 1, QTableWidgetItem(format_indian_number(i.get("taxable_value", 0.0))))
        self.table_4.setItem(0, 2, QTableWidgetItem(format_indian_number(i.get("igst", 0.0))))
        self.table_4.setItem(0, 3, QTableWidgetItem(format_indian_number(i.get("cgst", 0.0))))
        self.table_4.setItem(0, 4, QTableWidgetItem(format_indian_number(i.get("sgst", 0.0))))

    def _populate_gst_summary(self, data):
        o = data.get("output", {})
        i = data.get("itc", {})
        p = data.get("payable", {})
        t = data.get("totals", {})

        # Update Card values
        self.card_output.findChild(QLabel, "").setText(format_inr(t.get("output", 0.0)))
        self.card_itc.findChild(QLabel, "").setText(format_inr(t.get("itc", 0.0)))
        self.card_net.findChild(QLabel, "").setText(format_inr(p.get("net", 0.0)))

        # Update Recon table
        components = [
            ("cgst", 0),
            ("sgst", 1),
            ("igst", 2)
        ]
        for key, row_idx in components:
            self.table_recon.setItem(row_idx, 1, QTableWidgetItem(format_indian_number(o.get(key, 0.0))))
            self.table_recon.setItem(row_idx, 2, QTableWidgetItem(format_indian_number(i.get(key, 0.0))))
            self.table_recon.setItem(row_idx, 3, QTableWidgetItem(format_indian_number(p.get(key, 0.0))))

        # Total Row
        self.table_recon.setItem(3, 1, QTableWidgetItem(format_indian_number(t.get('output', 0.0))))
        self.table_recon.setItem(3, 2, QTableWidgetItem(format_indian_number(t.get('itc', 0.0))))
        self.table_recon.setItem(3, 3, QTableWidgetItem(format_indian_number(p.get('net', 0.0))))

        # Red styling for totals
        for col in [0, 1, 2, 3]:
            item = self.table_recon.item(3, col)
            if item:
                item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                item.setForeground(Qt.GlobalColor.black if col != 3 else Qt.GlobalColor.red)

    def switch_tab(self, tab_label):
        """Used by sidebar navigation shortcut triggers."""
        if tab_label == "GSTR-1":
            self.tabs.setCurrentIndex(0)
        elif tab_label == "GSTR-3B":
            self.tabs.setCurrentIndex(1)
        elif tab_label == "GST Summary":
            self.tabs.setCurrentIndex(2)
        self.load_data()

    # ──────────────────────────────────────────────────────────────────────────
    #  GSTR-1 JSON Generator
    # ──────────────────────────────────────────────────────────────────────────
    def generate_gstr1_json(self):
        """Generates GSTR-1 in the official government format."""
        if not hasattr(self, "g1_data") or not self.g1_data:
            QMessageBox.warning(self, "Warning", "No GSTR-1 data available. Click Refresh first.")
            return

        # Use the selected report period (to_date) for the default filename
        file_path, _ = QFileDialog.getSaveFileName(self, "Save GSTR-1 JSON", f"gstr1_{self.to_date.date().toString('yyyyMM')}.json", "JSON Files (*.json)")
        if not file_path:
            return

        # Determine filing period from the selected to_date (to match the report period)
        fp_period = self.to_date.date().toString("MMyyyy")

        # Get the selected company's own GSTIN
        import frontend.session as session
        try:
            company = api.get_company(session.company_id)
            company_gst = company.get("gst_no", "").strip() if company else ""
        except Exception:
            company_gst = ""
        if not company_gst:
            company_gst = "27AAAAA1111A1Z1"

        # Build official government GSTR-1 schema dictionary
        # https://www.gst.gov.in/
        gstr1_json = {
            "gstin": company_gst,
            "fp": fp_period,
            "cur_gt": self.g1_data.get("doc_summary", {}).get("total_value", 0.0),
            "b2b": []
        }

        # Format B2B invoices group by receiver GSTIN
        b2b_by_gstin = {}
        for r in self.g1_data.get("b2b", []):
            gstin = r["gstin"]
            if gstin not in b2b_by_gstin:
                b2b_by_gstin[gstin] = {
                    "ctin": gstin,
                    "inv": []
                }
            
            # Tax rate classification
            total_tax_rate = ((r["cgst"] + r["sgst"] + r["igst"]) / r["taxable_value"] * 100) if r["taxable_value"] > 0 else 18.0
            
            b2b_by_gstin[gstin]["inv"].append({
                "inum": r["invoice_no"],
                "idt": r["invoice_date"],
                "val": r["invoice_value"],
                "pos": r["place_of_supply"].split("-")[0] if "-" in r["place_of_supply"] else "27",
                "rchg": r["reverse_charge"],
                "inv_typ": "R",
                "itms": [
                    {
                        "num": 1,
                        "itm_det": {
                            "rt": round(total_tax_rate, 2),
                            "txval": r["taxable_value"],
                            "iamt": r["igst"],
                            "camt": r["cgst"],
                            "samt": r["sgst"],
                            "csamt": 0.0
                        }
                    }
                ]
            })

        gstr1_json["b2b"] = list(b2b_by_gstin.values())

        try:
            with open(file_path, "w") as f:
                json.dump(gstr1_json, f, indent=4)
            QMessageBox.information(self, "Success", f"GSTR-1 JSON generated successfully!\nSaved to: {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save JSON: {str(e)}")

    # ──────────────────────────────────────────────────────────────────────────
    #  GSTR-1 Excel Exporter
    # ──────────────────────────────────────────────────────────────────────────
    def export_gstr1_excel(self):
        """Generates a beautiful multi-sheet GSTR-1 Excel Workbook."""
        if not hasattr(self, "g1_data") or not self.g1_data:
            QMessageBox.warning(self, "Warning", "No data to export. Click Refresh first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save GSTR-1 Excel", f"gstr1_{QDate.currentDate().toString('yyyyMM')}.xlsx", "Excel Workbooks (*.xlsx)")
        if not file_path:
            return

        try:
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                # 1. B2B Sheet
                b2b = self.g1_data.get("b2b", [])
                if b2b:
                    pd.DataFrame(b2b).to_excel(writer, sheet_name="B2B Invoices", index=False)
                else:
                    pd.DataFrame([{"Message": "No B2B Invoices in this period"}]).to_excel(writer, sheet_name="B2B Invoices", index=False)

                # 2. B2CS Sheet
                b2cs = self.g1_data.get("b2cs", [])
                if b2cs:
                    pd.DataFrame(b2cs).to_excel(writer, sheet_name="B2C Small", index=False)

                # 3. Credit / Debit Notes Sheet
                cdn = self.g1_data.get("cdnr", []) + self.g1_data.get("cdnur", [])
                if cdn:
                    pd.DataFrame(cdn).to_excel(writer, sheet_name="Credit Debit Notes", index=False)

                # 4. HSN Summary Sheet
                hsn = self.g1_data.get("hsn", [])
                if hsn:
                    pd.DataFrame(hsn).to_excel(writer, sheet_name="HSN Summary", index=False)

            QMessageBox.information(self, "Success", f"GSTR-1 Excel exported successfully!\nSaved to: {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save Excel: {str(e)}")

    # ──────────────────────────────────────────────────────────────────────────
    #  GSTR-1 Import Functionality
    # ──────────────────────────────────────────────────────────────────────────
    def import_gstr1_data(self):
        """Imports GSTR-1 sales vouchers from a JSON/Excel file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Import GSTR-1 File", "", "GSTR-1 Files (*.json *.xlsx)")
        if not file_path:
            return

        try:
            imported_count = 0
            if file_path.endswith(".json"):
                # Parse GSTR-1 JSON
                with open(file_path, "r") as f:
                    data = json.load(f)

                b2b_list = data.get("b2b", [])
                for b2b_entry in b2b_list:
                    gstin = b2b_entry.get("ctin", "")
                    
                    # Try to locate existing customer ledger with this GSTIN
                    ledgers = api.list_ledgers()
                    customer_ledger = next((l for l in ledgers if l.get("gst_no", "").strip().lower() == gstin.strip().lower()), None)

                    if not customer_ledger:
                        # Auto-create customer ledger if it doesn't exist
                        groups = api.list_groups()
                        sundry_debtors_grp = next((g for g in groups if "debtors" in g["name"].lower()), None)
                        grp_id = sundry_debtors_grp["_id"] if sundry_debtors_grp else groups[0]["_id"]

                        ledger_data = {
                            "name": f"Imported Customer ({gstin})",
                            "group": grp_id,
                            "gst_no": gstin,
                            "opening_balance": 0.0,
                            "balance_type": "Dr"
                        }
                        res = api.create_ledger(ledger_data)
                        customer_ledger_id = res.get("id", "")
                        customer_name = ledger_data["name"]
                    else:
                        customer_ledger_id = customer_ledger["_id"]
                        customer_name = customer_ledger["name"]

                    # Import invoices
                    for inv in b2b_entry.get("inv", []):
                        inv_no = inv.get("inum", "")
                        inv_date = inv.get("idt", "")
                        
                        # Standardize date from DD-MM-YYYY to YYYY-MM-DD if needed
                        if "-" in inv_date:
                            parts = inv_date.split("-")
                            if len(parts[0]) == 4:
                                formatted_date = inv_date
                            else:
                                formatted_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                        else:
                            formatted_date = QDate.currentDate().toString("yyyy-MM-dd")

                        inv_val = float(inv.get("val", 0.0))
                        
                        # Retrieve first tax/item details
                        itms = inv.get("itms", [{}])
                        itm_det = itms[0].get("itm_det", {})
                        taxable_val = float(itm_det.get("txval", inv_val / 1.18))
                        cgst = float(itm_det.get("camt", 0.0))
                        sgst = float(itm_det.get("samt", 0.0))
                        igst = float(itm_det.get("iamt", 0.0))

                        # Setup entries list
                        entries = [
                            {"ledger_id": customer_ledger_id, "ledger_name": customer_name, "dr_cr": "Dr", "amount": inv_val}
                        ]

                        # Add Sales income ledger
                        sales_ledgers = [l for l in ledgers if "sales" in l["name"].lower() and "tax" not in l["name"].lower()]
                        sales_ledger_id = sales_ledgers[0]["_id"] if sales_ledgers else customer_ledger_id
                        sales_name = sales_ledgers[0]["name"] if sales_ledgers else "Sales Account"
                        entries.append({"ledger_id": sales_ledger_id, "ledger_name": sales_name, "dr_cr": "Cr", "amount": taxable_val})

                        # Setup tax ledgers
                        if cgst > 0:
                            cgst_ledgers = [l for l in ledgers if "cgst" in l["name"].lower()]
                            cg_id = cgst_ledgers[0]["_id"] if cgst_ledgers else customer_ledger_id
                            cg_name = cgst_ledgers[0]["name"] if cgst_ledgers else "CGST Input"
                            entries.append({"ledger_id": cg_id, "ledger_name": cg_name, "dr_cr": "Cr", "amount": cgst})
                        if sgst > 0:
                            sgst_ledgers = [l for l in ledgers if "sgst" in l["name"].lower()]
                            sg_id = sgst_ledgers[0]["_id"] if sgst_ledgers else customer_ledger_id
                            sg_name = sgst_ledgers[0]["name"] if sgst_ledgers else "SGST Input"
                            entries.append({"ledger_id": sg_id, "ledger_name": sg_name, "dr_cr": "Cr", "amount": sgst})
                        if igst > 0:
                            igst_ledgers = [l for l in ledgers if "igst" in l["name"].lower()]
                            ig_id = igst_ledgers[0]["_id"] if igst_ledgers else customer_ledger_id
                            ig_name = igst_ledgers[0]["name"] if igst_ledgers else "IGST Input"
                            entries.append({"ledger_id": ig_id, "ledger_name": ig_name, "dr_cr": "Cr", "amount": igst})

                        # Balancing Check
                        dr_sum = sum(e["amount"] for e in entries if e["dr_cr"] == "Dr")
                        cr_sum = sum(e["amount"] for e in entries if e["dr_cr"] == "Cr")
                        diff = dr_sum - cr_sum
                        if abs(diff) > 0.01:
                            # Add round-off
                            ro_ledgers = [l for l in ledgers if "round" in l["name"].lower()]
                            ro_id = ro_ledgers[0]["_id"] if ro_ledgers else customer_ledger_id
                            ro_name = ro_ledgers[0]["name"] if ro_ledgers else "Round Off"
                            entries.append({"ledger_id": ro_id, "ledger_name": ro_name, "dr_cr": "Cr" if diff > 0 else "Dr", "amount": abs(diff)})

                        voucher_data = {
                            "voucher_type": "Sales",
                            "date": formatted_date,
                            "narration": f"Imported GSTR-1 Invoice {inv_no}",
                            "entries": entries,
                            "company_id": api._cid()
                        }
                        api.create_voucher(voucher_data)
                        imported_count += 1

            elif file_path.endswith(".xlsx"):
                # Simple Excel import format
                df = pd.read_excel(file_path)
                # Check for standard columns
                required_cols = ["Invoice No", "Date", "Receiver GSTIN", "Receiver Name", "Taxable Value", "CGST", "SGST", "IGST", "Invoice Value"]
                missing = [c for c in required_cols if c not in df.columns]
                if missing:
                    QMessageBox.warning(self, "Invalid File", f"Excel is missing columns: {', '.join(missing)}")
                    return

                ledgers = api.list_ledgers()
                groups = api.list_groups()
                sundry_debtors_grp = next((g for g in groups if "debtors" in g["name"].lower()), None)
                grp_id = sundry_debtors_grp["_id"] if sundry_debtors_grp else groups[0]["_id"]

                for _, row in df.iterrows():
                    inv_no = str(row["Invoice No"])
                    inv_date = str(row["Date"])[:10]  # yyyy-mm-dd
                    gstin = str(row["Receiver GSTIN"]).strip()
                    recv_name = str(row["Receiver Name"]).strip()
                    tax_val = float(row["Taxable Value"])
                    cgst = float(row["CGST"]) if not pd.isna(row["CGST"]) else 0.0
                    sgst = float(row["SGST"]) if not pd.isna(row["SGST"]) else 0.0
                    igst = float(row["IGST"]) if not pd.isna(row["IGST"]) else 0.0
                    inv_val = float(row["Invoice Value"])

                    # Resolve Customer Ledger
                    customer_ledger = next((l for l in ledgers if l.get("gst_no", "").strip().lower() == gstin.lower()), None)
                    if not customer_ledger:
                        ledger_data = {
                            "name": recv_name if recv_name else f"Customer ({gstin})",
                            "group": grp_id,
                            "gst_no": gstin,
                            "opening_balance": 0.0,
                            "balance_type": "Dr"
                        }
                        res = api.create_ledger(ledger_data)
                        customer_ledger_id = res.get("id", "")
                        customer_name = ledger_data["name"]
                    else:
                        customer_ledger_id = customer_ledger["_id"]
                        customer_name = customer_ledger["name"]

                    entries = [
                        {"ledger_id": customer_ledger_id, "ledger_name": customer_name, "dr_cr": "Dr", "amount": inv_val}
                    ]

                    sales_ledgers = [l for l in ledgers if "sales" in l["name"].lower() and "tax" not in l["name"].lower()]
                    sales_ledger_id = sales_ledgers[0]["_id"] if sales_ledgers else customer_ledger_id
                    sales_name = sales_ledgers[0]["name"] if sales_ledgers else "Sales Account"
                    entries.append({"ledger_id": sales_ledger_id, "ledger_name": sales_name, "dr_cr": "Cr", "amount": tax_val})

                    # Setup tax ledgers
                    if cgst > 0:
                        cgst_ledgers = [l for l in ledgers if "cgst" in l["name"].lower()]
                        cg_id = cgst_ledgers[0]["_id"] if cgst_ledgers else customer_ledger_id
                        cg_name = cgst_ledgers[0]["name"] if cgst_ledgers else "CGST Input"
                        entries.append({"ledger_id": cg_id, "ledger_name": cg_name, "dr_cr": "Cr", "amount": cgst})
                    if sgst > 0:
                        sgst_ledgers = [l for l in ledgers if "sgst" in l["name"].lower()]
                        sg_id = sgst_ledgers[0]["_id"] if sgst_ledgers else customer_ledger_id
                        sg_name = sgst_ledgers[0]["name"] if sgst_ledgers else "SGST Input"
                        entries.append({"ledger_id": sg_id, "ledger_name": sg_name, "dr_cr": "Cr", "amount": sgst})
                    if igst > 0:
                        igst_ledgers = [l for l in ledgers if "igst" in l["name"].lower()]
                        ig_id = igst_ledgers[0]["_id"] if igst_ledgers else customer_ledger_id
                        ig_name = igst_ledgers[0]["name"] if igst_ledgers else "IGST Input"
                        entries.append({"ledger_id": ig_id, "ledger_name": ig_name, "dr_cr": "Cr", "amount": igst})

                    # Balancing check & Round-off
                    dr_sum = sum(e["amount"] for e in entries if e["dr_cr"] == "Dr")
                    cr_sum = sum(e["amount"] for e in entries if e["dr_cr"] == "Cr")
                    diff = dr_sum - cr_sum
                    if abs(diff) > 0.01:
                        ro_ledgers = [l for l in ledgers if "round" in l["name"].lower()]
                        ro_id = ro_ledgers[0]["_id"] if ro_ledgers else customer_ledger_id
                        ro_name = ro_ledgers[0]["name"] if ro_ledgers else "Round Off"
                        entries.append({"ledger_id": ro_id, "ledger_name": ro_name, "dr_cr": "Cr" if diff > 0 else "Dr", "amount": abs(diff)})

                    voucher_data = {
                        "voucher_type": "Sales",
                        "date": inv_date,
                        "narration": f"Imported Excel Invoice {inv_no}",
                        "entries": entries,
                        "company_id": api._cid()
                    }
                    api.create_voucher(voucher_data)
                    imported_count += 1

            QMessageBox.information(self, "Success", f"Successfully imported {imported_count} Sales Vouchers from GSTR-1!")
            self.load_data()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to import data: {str(e)}")

    # ──────────────────────────────────────────────────────────────────────────
    #  IFF JSON Generator
    # ──────────────────────────────────────────────────────────────────────────
    def generate_iff_json(self):
        """Generates IFF (Invoice Furnishing Facility) in the official government format."""
        if not hasattr(self, "g1_data") or not self.g1_data:
            QMessageBox.warning(self, "Warning", "No GSTR-1 data available. Click Refresh first.")
            return

        # Use the selected report period (to_date) for the default filename
        file_path, _ = QFileDialog.getSaveFileName(self, "Save IFF JSON", f"iff_{self.to_date.date().toString('yyyyMM')}.json", "JSON Files (*.json)")
        if not file_path:
            return

        # Determine filing period from the selected to_date (to match the report period)
        fp_period = self.to_date.date().toString("MMyyyy")

        # Get the selected company's own GSTIN
        import frontend.session as session
        try:
            company = api.get_company(session.company_id)
            company_gst = company.get("gst_no", "").strip() if company else ""
        except Exception:
            company_gst = ""
        if not company_gst:
            company_gst = "27AAAAA1111A1Z1"

        from datetime import datetime

        def format_date_dmy(date_str):
            try:
                # Expecting YYYY-MM-DD
                return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d-%m-%Y")
            except Exception:
                return date_str

        # Format B2B invoices group by receiver GSTIN
        b2b_by_gstin = {}
        for r in self.g1_data.get("b2b", []):
            gstin = r["gstin"]
            if gstin not in b2b_by_gstin:
                b2b_by_gstin[gstin] = {
                    "ctin": gstin,
                    "inv": []
                }
            
            total_tax_rate = ((r["cgst"] + r["sgst"] + r["igst"]) / r["taxable_value"] * 100) if r["taxable_value"] > 0 else 18.0
            
            itm_det = {
                "rt": round(total_tax_rate, 2) if total_tax_rate != 0 else 0,
                "txval": round(r["taxable_value"], 2)
            }
            if r.get("igst", 0.0) > 0:
                itm_det["iamt"] = round(r["igst"], 2)
            else:
                itm_det["camt"] = round(r["cgst"], 2)
                itm_det["samt"] = round(r["sgst"], 2)
            itm_det["csamt"] = 0

            # Pad state code to 2 digits for pos
            pos_code = r["place_of_supply"].split("-")[0].strip() if "-" in r["place_of_supply"] else "27"
            if pos_code.isdigit():
                pos_code = f"{int(pos_code):02d}"

            b2b_by_gstin[gstin]["inv"].append({
                "idt": format_date_dmy(r["invoice_date"]),
                "inum": r["invoice_no"],
                "inv_typ": "R",
                "itms": [
                    {
                        "itm_det": itm_det,
                        "num": 1
                    }
                ],
                "pos": pos_code,
                "rchrg": r.get("reverse_charge", "N"),
                "val": round(r["invoice_value"], 2)
            })

        # Format CDNR (Credit/Debit Notes for Registered) grouped by receiver GSTIN (ctin)
        cdnr_by_gstin = {}
        for r in self.g1_data.get("cdnr", []):
            gstin = r["gstin"]
            if gstin not in cdnr_by_gstin:
                cdnr_by_gstin[gstin] = {
                    "ctin": gstin,
                    "nt": []
                }
            
            total_tax_rate = ((r["cgst"] + r["sgst"] + r["igst"]) / r["taxable_value"] * 100) if r["taxable_value"] > 0 else 18.0
            
            itm_det = {
                "rt": round(total_tax_rate, 2) if total_tax_rate != 0 else 0,
                "txval": round(r["taxable_value"], 2)
            }
            if r.get("igst", 0.0) > 0:
                itm_det["iamt"] = round(r["igst"], 2)
            else:
                itm_det["camt"] = round(r["cgst"], 2)
                itm_det["samt"] = round(r["sgst"], 2)
            itm_det["csamt"] = 0

            pos_code = r["place_of_supply"].split("-")[0].strip() if "-" in r["place_of_supply"] else "27"
            if pos_code.isdigit():
                pos_code = f"{int(pos_code):02d}"

            cdnr_by_gstin[gstin]["nt"].append({
                "ntty": r.get("note_type", "C"),
                "nt_num": r["invoice_no"],
                "nt_dt": format_date_dmy(r["invoice_date"]),
                "val": round(r["invoice_value"], 2),
                "pos": pos_code,
                "rchrg": r.get("reverse_charge", "N"),
                "itms": [
                    {
                        "itm_det": itm_det,
                        "num": 1
                    }
                ]
            })

        # Build official government IFF schema dictionary matching user format exactly
        iff_json = {}
        iff_json["b2b"] = list(b2b_by_gstin.values())
        if cdnr_by_gstin:
            iff_json["cdnr"] = list(cdnr_by_gstin.values())
        iff_json["fp"] = fp_period
        iff_json["gstin"] = company_gst
        iff_json["hash"] = "hash"
        iff_json["version"] = "GST3.2.4"

        # Credit/Debit Notes for Unregistered Persons (CDNUR) are not allowed in IFF (quarterly return monthly payment).
        # We check if there are any CDNUR notes and warn the user, but exclude them from the IFF JSON.
        cdnur_data = self.g1_data.get("cdnur", [])
        has_cdnur = len(cdnur_data) > 0

        try:
            with open(file_path, "w") as f:
                json.dump(iff_json, f, indent=4)
            
            msg = "IFF JSON generated successfully!"
            if has_cdnur:
                msg += f"\n\nNote: {len(cdnur_data)} Credit/Debit Note(s) for Unregistered Persons (CDNUR) were excluded because unregistered notes are not allowed in the Invoice Furnishing Facility (IFF). Please file them in the quarterly GSTR-1."
            msg += f"\n\nSaved to: {file_path}"
            
            QMessageBox.information(self, "Success", msg)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save JSON: {str(e)}")

    # ──────────────────────────────────────────────────────────────────────────
    #  IFF Excel Exporter
    # ──────────────────────────────────────────────────────────────────────────
    def export_iff_excel(self):
        """Generates a multi-sheet IFF Excel Workbook containing B2B and Credit/Debit Notes."""
        if not hasattr(self, "g1_data") or not self.g1_data:
            QMessageBox.warning(self, "Warning", "No data to export. Click Refresh first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save IFF Excel", f"iff_{QDate.currentDate().toString('yyyyMM')}.xlsx", "Excel Workbooks (*.xlsx)")
        if not file_path:
            return

        try:
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                b2b = self.g1_data.get("b2b", [])
                if b2b:
                    pd.DataFrame(b2b).to_excel(writer, sheet_name="B2B Invoices", index=False)
                else:
                    pd.DataFrame([{"Message": "No B2B Invoices in this period"}]).to_excel(writer, sheet_name="B2B Invoices", index=False)

                cdn = self.g1_data.get("cdnr", []) + self.g1_data.get("cdnur", [])
                if cdn:
                    pd.DataFrame(cdn).to_excel(writer, sheet_name="Credit Debit Notes", index=False)
                else:
                    pd.DataFrame([{"Message": "No Credit/Debit Notes in this period"}]).to_excel(writer, sheet_name="Credit Debit Notes", index=False)

            QMessageBox.information(self, "Success", f"IFF Excel exported successfully!\nSaved to: {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save Excel: {str(e)}")
