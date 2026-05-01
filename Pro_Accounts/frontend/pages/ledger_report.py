from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox
)
from PySide6.QtCore import QDate, QSize
from PySide6.QtGui import QIcon
import frontend.api_client as api
from frontend.utils import SearchableComboBox, DateEdit, get_icon, format_indian_number


class LedgerReportPage(QWidget):
    def __init__(self):
        super().__init__()
        self._ledgers = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("Ledger Statement")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1565C0;")
        hdr.addWidget(title)
        hdr.addStretch()

        hdr.addWidget(QLabel("Ledger:"))
        self.ledger_cb = SearchableComboBox()
        self.ledger_cb.setMinimumWidth(200)
        hdr.addWidget(self.ledger_cb)

        hdr.addWidget(QLabel("From:"))
        self.from_date = DateEdit(QDate(QDate.currentDate().year(), 4, 1))
        self.from_date.setCalendarPopup(True)
        self.from_date.setDisplayFormat("yyyy-MM-dd")
        hdr.addWidget(self.from_date)

        hdr.addWidget(QLabel("To:"))
        self.to_date = DateEdit(QDate.currentDate())
        self.to_date.setCalendarPopup(True)
        self.to_date.setDisplayFormat("yyyy-MM-dd")
        hdr.addWidget(self.to_date)

        run_btn = QPushButton("  Show")
        run_btn.setIcon(get_icon("frontend/assets/icons/refresh.svg", "#1565C0"))
        run_btn.setIconSize(QSize(16, 16))
        run_btn.clicked.connect(self._load)
        hdr.addWidget(run_btn)
        layout.addLayout(hdr)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "Voucher", "No", "Narration", "Dr/Cr", "Amount", ])
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Date", "Voucher Type", "No", "Narration", "Dr/Cr", "Amount", "Balance"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        self.balance_label = QLabel()
        self.balance_label.setStyleSheet("font-weight: bold; color: #1565C0; font-size: 14px;")
        layout.addWidget(self.balance_label)

    def showEvent(self, e):
        self._refresh_ledgers()
        super().showEvent(e)

    def _refresh_ledgers(self):
        try:
            self._ledgers = api.list_ledgers()
        except Exception:
            return
        self.ledger_cb.clear()
        for l in self._ledgers:
            self.ledger_cb.addItem(l["name"], l["_id"])

    def _load(self):
        self.table.setRowCount(0)
        idx = self.ledger_cb.currentIndex()
        if idx < 0 or not self._ledgers:
            return
        lid = self._ledgers[idx]["_id"]
        try:
            entries = api.ledger_statement(
                lid,
                **{"from": self.from_date.date().toString("yyyy-MM-dd"),
                   "to": self.to_date.date().toString("yyyy-MM-dd")}
            )
        except Exception as ex:
            QMessageBox.warning(self, "Error", str(ex))
            return

        for row, e in enumerate(entries):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(e.get("date", "")))
            self.table.setItem(row, 1, QTableWidgetItem(e.get("voucher_type", "")))
            self.table.setItem(row, 2, QTableWidgetItem(e.get("voucher_no", "")))
            self.table.setItem(row, 3, QTableWidgetItem(e.get("narration", "")))
            self.table.setItem(row, 4, QTableWidgetItem(e.get("dr_cr", "")))
            self.table.setItem(row, 5, QTableWidgetItem(format_indian_number(e.get('amount', 0))))
            self.table.setItem(row, 6, QTableWidgetItem(
                f"{format_indian_number(e.get('balance', 0))} {e.get('balance_type', '')}"))

        if entries:
            last = entries[-1]
            self.balance_label.setText(
                f"Closing Balance: {format_indian_number(last['balance'])} {last['balance_type']}"
            )
        else:
            self.balance_label.setText("No transactions found")
