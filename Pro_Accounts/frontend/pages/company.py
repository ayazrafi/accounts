from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
    QMessageBox, QFrame, QScrollArea, QSizePolicy, QTableWidgetItem
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QDate, QSize, QEvent
import frontend.api_client as api
import frontend.session as session
from frontend.utils import setup_enter_nav, DateEdit, SearchableComboBox, get_icon, wire_state_combo
from frontend.components.cards import (
    ModernTable, PrimaryButton, DangerButton, SuccessButton,
    FAB, SectionTitle, Card, IconActionButton, PillActionButton
)
from frontend.theme import THEME


class CompanyDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Company")
        self.setMinimumWidth(440)
        self.data = data or {}
        form = QFormLayout(self)

        self.name    = QLineEdit(self.data.get("name", ""))
        self.address = QLineEdit(self.data.get("address", ""))
        self.phone   = QLineEdit(self.data.get("phone", ""))
        self.email   = QLineEdit(self.data.get("email", ""))
        self.gst     = QLineEdit(self.data.get("gst_no", ""))
        self.pan     = QLineEdit(self.data.get("pan", ""))
        self.state   = SearchableComboBox()
        wire_state_combo(self.state, self.data.get("state", ""))

        # Bank Details
        self.bank_name = QLineEdit(self.data.get("bank_name", ""))
        self.ifsc      = QLineEdit(self.data.get("ifsc_code", ""))
        self.branch    = QLineEdit(self.data.get("branch_name", ""))
        self.acc_no    = QLineEdit(self.data.get("account_number", ""))

        # Fiscal year — default: 1 Apr current year → 31 Mar next year
        today = QDate.currentDate()
        fy_start_default = QDate(today.year() if today.month() >= 4 else today.year() - 1, 4, 1)
        fy_end_default   = QDate(fy_start_default.year() + 1, 3, 31)

        self.fy_from = DateEdit()
        self.fy_from.setCalendarPopup(True)
        self.fy_from.setDisplayFormat("d-MMM-yyyy")
        fy_from_str = self.data.get("fiscal_year_from", "")
        self.fy_from.setDate(QDate.fromString(fy_from_str, "yyyy-MM-dd")
                             if fy_from_str else fy_start_default)

        self.fy_to = DateEdit()
        self.fy_to.setCalendarPopup(True)
        self.fy_to.setDisplayFormat("d-MMM-yyyy")
        fy_to_str = self.data.get("fiscal_year_to", "")
        self.fy_to.setDate(QDate.fromString(fy_to_str, "yyyy-MM-dd")
                           if fy_to_str else fy_end_default)

        form.addRow("Company Name *:", self.name)
        form.addRow("Address:", self.address)
        form.addRow("Phone:", self.phone)
        form.addRow("Email:", self.email)
        form.addRow("GST No:", self.gst)
        form.addRow("PAN:", self.pan)
        form.addRow("State:", self.state)
        form.addRow("Bank Name:", self.bank_name)
        form.addRow("IFSC Code:", self.ifsc)
        form.addRow("Branch Name:", self.branch)
        form.addRow("Account No:", self.acc_no)
        form.addRow("Fiscal Year From:", self.fy_from)
        form.addRow("Fiscal Year To:", self.fy_to)

        setup_enter_nav(self, [
            self.name, self.address, self.phone, self.email,
            self.gst, self.pan, self.state, 
            self.bank_name, self.ifsc, self.branch, self.acc_no,
            self.fy_from, self.fy_to,
        ])

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def _accept(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, "Error", "Company name is required"); return
        reply = QMessageBox.question(
            self, "Confirm Save",
            f"Save company '{self.name.text().strip()}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.accept()

    def get_data(self):
        return {
            "name": self.name.text().strip(),
            "address": self.address.text().strip(),
            "phone": self.phone.text().strip(),
            "email": self.email.text().strip(),
            "gst_no": self.gst.text().strip(),
            "pan": self.pan.text().strip(),
            "state": self.state.currentText().strip(),
            "bank_name": self.bank_name.text().strip(),
            "ifsc_code": self.ifsc.text().strip(),
            "branch_name": self.branch.text().strip(),
            "account_number": self.acc_no.text().strip(),
            "fiscal_year_from": self.fy_from.date().toString("yyyy-MM-dd"),
            "fiscal_year_to":   self.fy_to.date().toString("yyyy-MM-dd"),
        }


class CompanyPage(QWidget):
    def __init__(self):
        super().__init__()
        self._companies: list[dict] = []
        self._build()

    def _build(self):
        # Outer scroll for small screens
        outer = QScrollArea(self)
        outer.setWidgetResizable(True)
        outer.setFrameShape(QFrame.Shape.NoFrame)
        outer.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setStyleSheet(f"background: {THEME['bg']};")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)

        # ── Header row ─────────────────────────────────────────────────
        add_btn = PrimaryButton("  Add Company  [Alt+A]")
        add_btn.setIcon(get_icon("frontend/assets/icons/plus.svg", "#ffffff"))
        add_btn.setIconSize(QSize(16, 16))
        add_btn.setShortcut("Alt+A")
        add_btn.setToolTip("Add Company  (Alt+A)")
        add_btn.clicked.connect(self._add)

        layout.addWidget(SectionTitle(
            "Companies",
            "Manage your companies and set the active one.",
            add_btn,
        ))

        # ── Active company card ────────────────────────────────────────
        self._active_card = QWidget()
        self._active_card.setObjectName("ActiveCard")
        self._active_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._active_card.setFixedHeight(64)
        self._active_card.setStyleSheet(f"""
            #ActiveCard {{
                background: #DBEAFE;
                border: 1.5px solid {THEME['primary']};
                border-radius: 10px;
            }}
        """)
        ac_layout = QHBoxLayout(self._active_card)
        ac_layout.setContentsMargins(18, 0, 18, 0)

        ac_icon = QLabel()
        ac_icon.setPixmap(get_icon("frontend/assets/icons/company.svg", THEME['primary']).pixmap(24, 24))
        ac_icon.setStyleSheet("background:transparent;")

        self._active_lbl = QLabel("No company selected")
        self._active_lbl.setStyleSheet(
            f"font-size:14px;font-weight:700;color:{THEME['primary_dark']};background:transparent;"
        )

        ac_layout.addWidget(ac_icon)
        ac_layout.addSpacing(10)
        ac_layout.addWidget(self._active_lbl)
        ac_layout.addStretch()
        layout.addWidget(self._active_card)

        # ── Table ──────────────────────────────────────────────────────
        self.table = ModernTable(
            0, 6,
            ["Company Name", "Fiscal Year", "GST No", "Phone", "Email", "Actions"],
        )
        # Actions column: fixed width so it doesn't stretch
        self.table.horizontalHeader().setSectionResizeMode(
            5, self.table.horizontalHeader().ResizeMode.Fixed
        )
        self.table.setColumnWidth(5, 140)
        self.table.installEventFilter(self)
        layout.addWidget(self.table, 1)

        outer.setWidget(container)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(outer)

        self._load()

    def showEvent(self, e):
        self._load()
        super().showEvent(e)
        self.table.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.table and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                row = self.table.currentRow()
                if 0 <= row < len(self._companies):
                    self._set_active(self._companies[row])
                    return True
        return super().eventFilter(obj, event)

    # ── Data ───────────────────────────────────────────────────────────
    def _load(self):
        self.table.set_row_count_reset()
        try:
            companies = api.list_companies()
        except Exception as ex:
            QMessageBox.warning(self, "Error", str(ex))
            return
        self._companies = companies

        active_name = session.company_name
        self._active_lbl.setText(
            f"Active Company:  {active_name}" if active_name else "No company selected"
        )

        for row, c in enumerate(companies):
            self.table.insertRow(row)

            name = c.get("name", "")
            is_active = c["_id"] == session.company_id

            name_item = QTableWidgetItem(name)
            if is_active:
                name_item.setIcon(get_icon("frontend/assets/icons/star.svg", "#F59E0B"))
                name_item.setForeground(Qt.GlobalColor.darkBlue)
            self.table.setItem(row, 0, name_item)

            fy = (
                f"{c.get('fiscal_year_from','')[:7]}  →  "
                f"{c.get('fiscal_year_to','')[:7]}"
            )
            self.table.setItem(row, 1, QTableWidgetItem(fy))
            self.table.setItem(row, 2, QTableWidgetItem(c.get("gst_no", "")))
            self.table.setItem(row, 3, QTableWidgetItem(c.get("phone", "")))
            self.table.setItem(row, 4, QTableWidgetItem(c.get("email", "")))

            # ── Action buttons cell ────────────────────────────────────
            action_widget = QWidget()
            action_widget.setStyleSheet("background: transparent;")
            a_layout = QHBoxLayout(action_widget)
            a_layout.setContentsMargins(8, 0, 8, 0)
            a_layout.setSpacing(8)
            a_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

            edit_btn = IconActionButton("frontend/assets/icons/edit.svg", "Edit Company", variant="edit")
            edit_btn.clicked.connect(lambda *_, comp=c: self._edit(comp))

            setact_btn = IconActionButton("frontend/assets/icons/check.svg", "Set Active", variant="success")
            setact_btn.clicked.connect(lambda *_, comp=c: self._set_active(comp))

            del_btn = IconActionButton("frontend/assets/icons/trash.svg", "Delete Company", variant="danger")
            del_btn.clicked.connect(lambda *_, cid=c["_id"]: self._delete(cid))

            a_layout.addWidget(edit_btn)
            a_layout.addWidget(setact_btn)
            a_layout.addWidget(del_btn)
            a_layout.addStretch()
            self.table.setCellWidget(row, 5, action_widget)

            self.table.setRowHeight(row, 48)

        if self.table.rowCount() > 0:
            self.table.setCurrentCell(0, 0)
            self.table.setFocus()

    # ── Actions ────────────────────────────────────────────────────────
    def _edit(self, comp: dict):
        dlg = CompanyDialog(self, data=comp)
        if dlg.exec():
            data = dlg.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Error", "Company name is required")
                return
            try:
                api.update_company(comp["_id"], data)
                # If we just edited the active company, refresh session display
                if comp["_id"] == session.company_id:
                    session.set_company(
                        cid=comp["_id"],
                        name=data["name"],
                        fy_from=data["fiscal_year_from"],
                        fy_to=data["fiscal_year_to"],
                    )
                    mw = self.window()
                    if hasattr(mw, "refresh_company_header"):
                        mw.refresh_company_header()
                self._load()
            except Exception as ex:
                QMessageBox.warning(self, "Error", str(ex))

    def _set_active(self, comp: dict):
        session.set_company(
            cid=comp["_id"], name=comp["name"],
            fy_from=comp.get("fiscal_year_from", ""),
            fy_to=comp.get("fiscal_year_to", ""),
        )
        mw = self.window()
        if hasattr(mw, "refresh_company_header"):
            mw.refresh_company_header()
        self._load()
        QMessageBox.information(
            self, "Active Company",
            f"'{comp['name']}' is now the active company.",
        )

    def _add(self):
        dlg = CompanyDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Error", "Company name is required")
                return
            try:
                api.create_company(data)
                self._load()
            except Exception as ex:
                QMessageBox.warning(self, "Error", str(ex))

    def _delete(self, cid: str):
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Are you sure you want to delete this company?\n"
            "All associated data will be removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                api.delete_company(cid)
                self._load()
            except Exception as ex:
                QMessageBox.warning(self, "Error", str(ex))
