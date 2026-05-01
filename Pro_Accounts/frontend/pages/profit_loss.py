from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QSplitter, QFrame
)
from PySide6.QtCore import QDate, Qt, QSize
from PySide6.QtGui import QIcon
import frontend.api_client as api
from frontend.utils import DateEdit, get_icon, format_indian_number, format_inr


class ProfitLossPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("Profit & Loss")
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

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Income
        income_frame = QFrame()
        income_layout = QVBoxLayout(income_frame)
        income_layout.addWidget(QLabel("INCOME"))
        self.income_table = QTableWidget(0, 2)
        self.income_table.setHorizontalHeaderLabels(["Account", "Amount"])
        self.income_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.income_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        income_layout.addWidget(self.income_table)
        self.income_total = QLabel()
        self.income_total.setStyleSheet("color: #16a34a; font-weight: bold;")
        income_layout.addWidget(self.income_total)
        splitter.addWidget(income_frame)

        # Expense
        expense_frame = QFrame()
        expense_layout = QVBoxLayout(expense_frame)
        expense_layout.addWidget(QLabel("EXPENSES"))
        self.expense_table = QTableWidget(0, 2)
        self.expense_table.setHorizontalHeaderLabels(["Account", "Amount"])
        self.expense_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.expense_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        expense_layout.addWidget(self.expense_table)
        self.expense_total = QLabel()
        self.expense_total.setStyleSheet("color: #dc2626; font-weight: bold;")
        expense_layout.addWidget(self.expense_total)
        splitter.addWidget(expense_frame)

        layout.addWidget(splitter)

        self.net_label = QLabel()
        self.net_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #546e7a;")
        self.net_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.net_label)

    def showEvent(self, e):
        self._load()
        super().showEvent(e)

    def _load(self):
        self.income_table.setRowCount(0)
        self.expense_table.setRowCount(0)
        try:
            data = api.profit_loss(
                **{"from": self.from_date.date().toString("yyyy-MM-dd"),
                   "to": self.to_date.date().toString("yyyy-MM-dd")}
            )
        except Exception as ex:
            QMessageBox.warning(self, "Error", str(ex))
            return

        for i, (acc, amt) in enumerate(data.get("income", {}).items()):
            self.income_table.insertRow(i)
            self.income_table.setItem(i, 0, QTableWidgetItem(acc))
            self.income_table.setItem(i, 1, QTableWidgetItem(format_indian_number(amt)))

        for i, (acc, amt) in enumerate(data.get("expense", {}).items()):
            self.expense_table.insertRow(i)
            self.expense_table.setItem(i, 0, QTableWidgetItem(acc))
            self.expense_table.setItem(i, 1, QTableWidgetItem(format_indian_number(amt)))

        ti = data.get("total_income", 0)
        te = data.get("total_expense", 0)
        self.income_total.setText(f"Total Income: {format_indian_number(ti)}")
        self.expense_total.setText(f"Total Expense: {format_indian_number(te)}")

        if "net_profit" in data:
            self.net_label.setText(f"Net Profit: {format_inr(data['net_profit'])}")
            self.net_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #16a34a;")
        elif "net_loss" in data:
            self.net_label.setText(f"Net Loss: {format_inr(data['net_loss'])}")
            self.net_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #dc2626;")
        else:
            self.net_label.setText("No data")
