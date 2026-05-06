from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PySide6.QtCore import QDate, QSize
from PySide6.QtGui import QIcon
import frontend.api_client as api
from frontend.utils import DateEdit, get_icon, format_indian_number


class TrialBalancePage(QWidget):
    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("Trial Balance")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1565C0;")
        hdr.addWidget(title)
        hdr.addStretch()

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

        run_btn = QPushButton("  Generate")
        run_btn.setIcon(get_icon("frontend/assets/icons/refresh.svg", "#1565C0"))
        run_btn.setIconSize(QSize(16, 16))
        run_btn.clicked.connect(self._load)
        hdr.addWidget(run_btn)
        layout.addLayout(hdr)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Ledger", "Debit (Dr)", "Credit (Cr)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        self.total_label = QLabel()
        self.total_label.setStyleSheet("font-weight: bold; color: #16a34a; font-size: 14px;")
        layout.addWidget(self.total_label)

    def showEvent(self, e):
        self._load()
        super().showEvent(e)

    def _load(self):
        self.table.setRowCount(0)
        try:
            data = api.trial_balance(
                **{"from": self.from_date.date().toString("yyyy-MM-dd"),
                   "to": self.to_date.date().toString("yyyy-MM-dd")}
            )
        except Exception as ex:
            QMessageBox.warning(self, "Error", str(ex))
            return

        rows = data.get("rows", [])
        for row, r in enumerate(rows):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(r.get("ledger_name", "")))
            dr = r.get("Dr", 0)
            cr = r.get("Cr", 0)
            self.table.setItem(row, 1, QTableWidgetItem(format_indian_number(dr) if dr else ""))
            self.table.setItem(row, 2, QTableWidgetItem(format_indian_number(cr) if cr else ""))

        tdr = data.get("total_dr", 0)
        tcr = data.get("total_cr", 0)
        self.total_label.setText(f"Total Dr: {format_indian_number(tdr)}    Total Cr: {format_indian_number(tcr)}")
