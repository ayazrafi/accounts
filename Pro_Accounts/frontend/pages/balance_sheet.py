from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor, QIcon
import frontend.api_client as api
from frontend.utils import get_icon, format_indian_number, format_inr


def _money(val):
    return format_inr(val)


class BalanceSheetPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24); layout.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("Balance Sheet")
        title.setStyleSheet("font-size:22px;font-weight:bold;color:#1565C0;")
        refresh_btn = QPushButton("  Refresh")
        refresh_btn.setIcon(get_icon("frontend/assets/icons/refresh.svg", "#1565C0"))
        refresh_btn.setIconSize(QSize(16, 16))
        refresh_btn.clicked.connect(self._load)
        hdr.addWidget(title); hdr.addStretch(); hdr.addWidget(refresh_btn)
        layout.addLayout(hdr)

        # Two-column layout
        cols = QHBoxLayout(); cols.setSpacing(16)

        # Liabilities
        liab_frame = QWidget(); liab_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        liab_frame.setStyleSheet("background:#e3f2fd;border:1px solid #bbdefb;border-radius:8px;")
        liab_lay = QVBoxLayout(liab_frame)
        liab_title = QLabel("LIABILITIES")
        liab_title.setStyleSheet("font-size:13px;font-weight:bold;color:#1565C0;"
                                  "padding:4px;background:#bbdefb;border-radius:4px;")
        liab_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        liab_lay.addWidget(liab_title)
        self.liab_table = self._make_table()
        liab_lay.addWidget(self.liab_table)
        self.liab_total = QLabel("Total: ₹ 0.00")
        self.liab_total.setStyleSheet("font-weight:bold;color:#1565C0;font-size:13px;"
                                       "border-top:2px solid #1565C0;padding-top:4px;")
        self.liab_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        liab_lay.addWidget(self.liab_total)

        # Assets
        asset_frame = QWidget(); asset_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        asset_frame.setStyleSheet("background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;")
        asset_lay = QVBoxLayout(asset_frame)
        asset_title = QLabel("ASSETS")
        asset_title.setStyleSheet("font-size:13px;font-weight:bold;color:#15803d;"
                                   "padding:4px;background:#bbf7d0;border-radius:4px;")
        asset_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        asset_lay.addWidget(asset_title)
        self.asset_table = self._make_table()
        asset_lay.addWidget(self.asset_table)
        self.asset_total = QLabel("Total: ₹ 0.00")
        self.asset_total.setStyleSheet("font-weight:bold;color:#15803d;font-size:13px;"
                                        "border-top:2px solid #15803d;padding-top:4px;")
        self.asset_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        asset_lay.addWidget(self.asset_total)

        cols.addWidget(liab_frame, 1); cols.addWidget(asset_frame, 1)
        layout.addLayout(cols)
        self._load()

    def _make_table(self):
        t = QTableWidget(0, 2)
        t.setHorizontalHeaderLabels(["Group / Ledger", "Amount (₹)"])
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        return t

    def showEvent(self, e):
        self._load(); super().showEvent(e)

    def _load(self):
        self.liab_table.setRowCount(0)
        self.asset_table.setRowCount(0)
        try:
            data = api.balance_sheet()
        except Exception as ex:
            QMessageBox.warning(self, "Error", str(ex)); return

        liab_total = asset_total = 0.0

        for side, table, total_attr in [
            ("liabilities", self.liab_table, "liab_total"),
            ("assets",      self.asset_table, "asset_total"),
        ]:
            groups = data.get(side, [])
            total = 0.0
            bold_font = QFont(); bold_font.setBold(True)
            group_bg = QColor("#d0e8ff") if side == "liabilities" else QColor("#c6f7d4")
            empty_bg = QColor("#f5f5f5")
            for grp in groups:
                grp_name = grp.get("group", "")
                grp_total = grp.get("group_total", 0.0)
                ledgers = grp.get("ledgers", [])

                # Group header row
                row = table.rowCount(); table.insertRow(row)
                grp_item = QTableWidgetItem(grp_name)
                grp_item.setFont(bold_font)
                grp_item.setBackground(group_bg)
                grp_total_item = QTableWidgetItem(format_indian_number(grp_total) if grp_total else "")
                grp_total_item.setFont(bold_font)
                grp_total_item.setBackground(group_bg)
                grp_total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row, 0, grp_item)
                table.setItem(row, 1, grp_total_item)
                table.setRowHeight(row, 26)

                # Ledger sub-rows
                for led in ledgers:
                    row = table.rowCount(); table.insertRow(row)
                    led_item = QTableWidgetItem("    " + led.get("ledger", ""))
                    led_item.setForeground(QColor("#444"))
                    amt = led.get("balance", 0.0)
                    amt_item = QTableWidgetItem(format_indian_number(abs(amt)))
                    amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    table.setItem(row, 0, led_item)
                    table.setItem(row, 1, amt_item)

                if grp_total:
                    total += grp_total
            lbl = getattr(self, total_attr)
            lbl.setText(f"Total: {format_inr(total)}")
            if side == "liabilities": liab_total = total
            else: asset_total = total
