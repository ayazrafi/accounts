from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QDoubleSpinBox, QDialogButtonBox,
    QMessageBox, QHeaderView, QTabWidget, QSpinBox, QFrame, QInputDialog
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
import frontend.api_client as api
from frontend.utils import setup_enter_nav, SearchableComboBox, wire_create_new, get_icon, CREATE_NEW_LABEL, format_indian_number, format_inr
from frontend.components.cards import PillActionButton, IconActionButton


class StockCategoryDialog(QDialog):
    def __init__(self, parent=None, category=None):
        super().__init__(parent)
        self.setWindowTitle("Stock Category" if not category else "Edit Stock Category")
        self.setMinimumWidth(440)
        self._category = category
        try:
            self._groups = api.list_stock_groups()
        except Exception:
            self._groups = [{"name": "General"}]
        
        form = QFormLayout(self)
        self.name = QLineEdit(category["name"] if category else "")
        self.group_cb = SearchableComboBox()
        for g in self._groups: self.group_cb.addItem(g["name"])
        if category: self.group_cb.setCurrentText(category.get("stock_group", "General"))
        
        # "Create New Stock Group" option
        def _create_stock_group():
            name, ok = QInputDialog.getText(self, "New Stock Group", "Stock Group Name:")
            if ok and name.strip():
                try:
                    api.create_stock_group({"name": name.strip()})
                    self._groups.append({"name": name.strip()})
                    return (name.strip(), name.strip())
                except Exception as ex:
                    QMessageBox.warning(self, "Error", str(ex))
            return None
        wire_create_new(self.group_cb, _create_stock_group)
        
        self.price = QDoubleSpinBox(); self.price.setRange(0, 9999999); self.price.setDecimals(2)
        self.super_net = QDoubleSpinBox(); self.super_net.setRange(0, 9999999); self.super_net.setDecimals(2)
        self.net = QDoubleSpinBox(); self.net.setRange(0, 9999999); self.net.setDecimals(2)
        self.dhara = QDoubleSpinBox(); self.dhara.setRange(0, 9999999); self.dhara.setDecimals(2)
        self.cgst = QDoubleSpinBox(); self.cgst.setRange(0, 100); self.cgst.setSuffix(" %")
        self.sgst = QDoubleSpinBox(); self.sgst.setRange(0, 100); self.sgst.setSuffix(" %")
        self.igst = QDoubleSpinBox(); self.igst.setRange(0, 100); self.igst.setSuffix(" %")
        
        if category:
            self.price.setValue(category.get("price", 0))
            self.super_net.setValue(category.get("super_net", 0))
            self.net.setValue(category.get("net", 0))
            self.dhara.setValue(category.get("dhara", 0))
            self.cgst.setValue(category.get("cgst", 0))
            self.sgst.setValue(category.get("sgst", 0))
            self.igst.setValue(category.get("igst", 0))
            
        form.addRow("Category Name *:", self.name)
        form.addRow("Stock Group:", self.group_cb)
        form.addRow("Price:", self.price)
        form.addRow("Super Net:", self.super_net)
        form.addRow("Net:", self.net)
        form.addRow("Dhara:", self.dhara)
        form.addRow("CGST %:", self.cgst)
        form.addRow("SGST %:", self.sgst)
        form.addRow("IGST %:", self.igst)
        
        setup_enter_nav(self, [
            self.name, self.group_cb, self.price, self.super_net,
            self.net, self.dhara, self.cgst, self.sgst, self.igst,
        ])
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept); btns.rejected.connect(self.reject)
        form.addRow(btns)

    def _accept(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, "Error", "Name is required"); return
        self.accept()

    def get_data(self):
        return {
            "name": self.name.text().strip(),
            "stock_group": self.group_cb.currentText(),
            "price": self.price.value(),
            "super_net": self.super_net.value(),
            "net": self.net.value(),
            "dhara": self.dhara.value(),
            "cgst": self.cgst.value(),
            "sgst": self.sgst.value(),
            "igst": self.igst.value(),
        }


class StockItemDialog(QDialog):
    def __init__(self, parent=None, item=None):
        super().__init__(parent)
        self.setWindowTitle("Stock Item" if not item else "Edit Stock Item")
        self.setMinimumWidth(480)
        self._item = item
        try:
            self._units  = api.list_units()   # list of strings
            self._groups = api.list_stock_groups()  # list of dicts
        except Exception:
            self._units  = ["PCS"]
            self._groups = [{"name": "General"}]
        form = QFormLayout(self)
        self.name   = QLineEdit(item["name"]  if item else "")
        self.hsn    = QLineEdit(item.get("hsn_sac", "")  if item else "")
        
        self.price     = QDoubleSpinBox(); self.price.setRange(0, 1e9); self.price.setValue(item.get("price", 0) if item else 0)
        self.super_net = QDoubleSpinBox(); self.super_net.setRange(0, 1e9); self.super_net.setValue(item.get("super_net", 0) if item else 0)
        self.net       = QDoubleSpinBox(); self.net.setRange(0, 1e9); self.net.setValue(item.get("net", 0) if item else 0)
        self.dhara     = QDoubleSpinBox(); self.dhara.setRange(0, 1e9); self.dhara.setValue(item.get("dhara", 0) if item else 0)
        
        self.cgst = QDoubleSpinBox(); self.cgst.setRange(0, 100); self.cgst.setValue(item.get("cgst", 0) if item else 0)
        self.sgst = QDoubleSpinBox(); self.sgst.setRange(0, 100); self.sgst.setValue(item.get("sgst", 0) if item else 0)
        self.igst = QDoubleSpinBox(); self.igst.setRange(0, 100); self.igst.setValue(item.get("igst", 0) if item else 0)

        self.gst_rate = QDoubleSpinBox()
        self.gst_rate.setRange(0, 28); self.gst_rate.setSuffix(" %")
        self.gst_rate.setValue(item.get("gst_rate", 18) if item else 18)
        self.unit_cb = SearchableComboBox()
        self.unit_cb.addItem("Select Unit", None)
        for u in self._units: self.unit_cb.addItem(u if isinstance(u, str) else u["name"])
        if item: self.unit_cb.setCurrentText(item.get("unit", ""))
        else: self.unit_cb.setCurrentIndex(0)
        
        self.group_cb = SearchableComboBox()
        self.group_cb.addItem("Select Stock Group", None)
        for g in self._groups: self.group_cb.addItem(g["name"])
        if item: self.group_cb.setCurrentText(item.get("stock_group", ""))
        else: self.group_cb.setCurrentIndex(0)
        
        self.cat_cb = SearchableComboBox()
        self.group_cb.currentIndexChanged.connect(self._refresh_categories)
        
        def _create_stock_cat():
            dlg = StockCategoryDialog(self)
            dlg.group_cb.setCurrentText(self.group_cb.currentText())
            if dlg.exec():
                data = dlg.get_data()
                try:
                    api.create_stock_category(data)
                    return (data["name"], data)
                except Exception as ex:
                    QMessageBox.warning(self, "Error", str(ex))
            return None

        def _on_cat_changed():
            data = self.cat_cb.currentData()
            if isinstance(data, dict):
                self.price.setValue(data.get("price", 0.0))
                self.super_net.setValue(data.get("super_net", 0.0))
                self.net.setValue(data.get("net", 0.0))
                self.dhara.setValue(data.get("dhara", 0.0))
                self.cgst.setValue(data.get("cgst", 0.0))
                self.sgst.setValue(data.get("sgst", 0.0))
                self.igst.setValue(data.get("igst", 0.0))
                
                # Auto-fill main GST rate
                c, s, i = data.get("cgst", 0), data.get("sgst", 0), data.get("igst", 0)
                self.gst_rate.setValue(c + s if c + s > 0 else i)
        
        self.cat_cb.currentIndexChanged.connect(_on_cat_changed)
        wire_create_new(self.cat_cb, _create_stock_cat)

        # "Create New Stock Group" option
        def _create_stock_group():
            name, ok = QInputDialog.getText(self, "New Stock Group", "Stock Group Name:")
            if ok and name.strip():
                try:
                    api.create_stock_group({"name": name.strip()})
                    self._groups.append({"name": name.strip()})
                    return (name.strip(), name.strip())
                except Exception as ex:
                    QMessageBox.warning(self, "Error", str(ex))
            return None
        wire_create_new(self.group_cb, _create_stock_group)

        # "Create New Unit" option
        def _create_unit():
            name, ok = QInputDialog.getText(
                self, "New Unit", "Unit Name (e.g. NOS, KG, MTR):")
            if ok and name.strip():
                uname = name.strip().upper()
                try:
                    api.create_unit({"name": uname})
                    self._units.append(uname)
                    return (uname, uname)
                except Exception as ex:
                    QMessageBox.warning(self, "Error", str(ex))
            return None
        wire_create_new(self.unit_cb, _create_unit)

        self.op_qty   = QDoubleSpinBox(); self.op_qty.setRange(0, 9999999); self.op_qty.setDecimals(3)
        self.op_rate  = QDoubleSpinBox(); self.op_rate.setRange(0, 9999999); self.op_rate.setDecimals(2)
        self.op_value = QDoubleSpinBox(); self.op_value.setRange(0, 9999999); self.op_value.setDecimals(2)
        if item:
            self.op_qty.setValue(item.get("opening_qty", 0))
            self.op_rate.setValue(item.get("opening_rate", 0))
            self.op_value.setValue(item.get("opening_value", 0))
        self.op_qty.valueChanged.connect(self._calc_value)
        self.op_rate.valueChanged.connect(self._calc_value)
        form.addRow("Name *:", self.name)
        form.addRow("Stock Group:", self.group_cb)
        form.addRow("Stock Category:", self.cat_cb)
        form.addRow("Unit:", self.unit_cb)
        form.addRow("HSN / SAC:", self.hsn)
        
        # Pricing Section
        form.addRow(QLabel("<b>Pricing & Details</b>"))
        form.addRow("Price:", self.price)
        form.addRow("Super Net:", self.super_net)
        form.addRow("Net:", self.net)
        form.addRow("Dhara:", self.dhara)
        
        # Tax Section
        form.addRow(QLabel("<b>Taxation</b>"))
        form.addRow("CGST %:", self.cgst)
        form.addRow("SGST %:", self.sgst)
        form.addRow("IGST %:", self.igst)
        form.addRow("Total GST %:", self.gst_rate)
        form.addRow("Opening Qty:", self.op_qty)
        form.addRow("Opening Rate (₹):", self.op_rate)
        form.addRow("Opening Value (₹):", self.op_value)

        setup_enter_nav(self, [
            self.name, self.group_cb, self.cat_cb, self.unit_cb, self.hsn,
            self.price, self.super_net, self.net, self.dhara,
            self.cgst, self.sgst, self.igst, self.gst_rate,
            self.op_qty, self.op_rate, self.op_value,
        ])

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept); btns.rejected.connect(self.reject)
        form.addRow(btns)
        
        self._refresh_categories()
        if item: self.cat_cb.setCurrentText(item.get("category", ""))

    def _refresh_categories(self):
        self.cat_cb.blockSignals(True)
        try:
            self.cat_cb.clear()
            self.cat_cb.addItem("Select Stock Category", None)
            group_name = self.group_cb.currentText()
            if not group_name or "Select" in group_name:
                self.cat_cb.addItem(CREATE_NEW_LABEL)
                return
            try:
                cats = api.list_stock_categories(stock_group=group_name)
                for c in cats:
                    self.cat_cb.addItem(c["name"], c)
            except Exception:
                pass
            self.cat_cb.addItem(CREATE_NEW_LABEL)
        finally:
            self.cat_cb.blockSignals(False)

    def _calc_value(self):
        self.op_value.setValue(round(self.op_qty.value() * self.op_rate.value(), 2))

    def _accept(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, "Error", "Name is required"); return
        reply = QMessageBox.question(
            self, "Confirm Save",
            f"Save stock item '{self.name.text().strip()}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.accept()

    def get_data(self):
        def _val(cb):
            t = cb.currentText()
            return "" if t.startswith("Select ") else t

        return {
            "name": self.name.text().strip(),
            "stock_group": _val(self.group_cb),
            "category": _val(self.cat_cb),
            "unit": _val(self.unit_cb),
            "hsn_sac": self.hsn.text().strip(),
            "gst_rate": self.gst_rate.value(),
            "price": self.price.value(),
            "super_net": self.super_net.value(),
            "net": self.net.value(),
            "dhara": self.dhara.value(),
            "cgst": self.cgst.value(),
            "sgst": self.sgst.value(),
            "igst": self.igst.value(),
            "opening_qty": self.op_qty.value(),
            "opening_rate": self.op_rate.value(),
            "opening_value": self.op_value.value(),
        }


class StockSummaryTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        hdr = QHBoxLayout()
        title = QLabel("Stock Summary")
        title.setStyleSheet("font-size:16px;font-weight:bold;color:#1565C0;")
        refresh_btn = QPushButton(" Refresh")
        refresh_btn.setIcon(get_icon("frontend/assets/icons/refresh.svg", "#1565C0"))
        refresh_btn.setIconSize(QSize(16, 16))
        refresh_btn.clicked.connect(self._load)
        hdr.addWidget(title); hdr.addStretch(); hdr.addWidget(refresh_btn)
        layout.addLayout(hdr)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Particulars","Unit","Qty","Rate (₹)","Value (₹)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        self.total_lbl = QLabel("Grand Total: ₹ 0.00")
        self.total_lbl.setStyleSheet("font-size:14px;font-weight:bold;color:#1565C0;text-align:right;")
        self.total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.total_lbl)
        self._load()

    def showEvent(self, e):
        self._load(); super().showEvent(e)

    def _load(self):
        self.table.setRowCount(0)
        try:
            resp = api.stock_summary()
            items = resp.get("rows", []) if isinstance(resp, dict) else resp
        except Exception as ex:
            QMessageBox.warning(self, "Error", str(ex)); return
        grand_total = 0.0
        for row, item in enumerate(items):
            self.table.insertRow(row)
            value = item.get("value", 0.0)
            grand_total += value
            self.table.setItem(row, 0, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("unit", "")))
            qty_item = QTableWidgetItem(f"{item.get('qty', 0):.3f}")
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            rate_item = QTableWidgetItem(format_indian_number(item.get('rate', 0)))
            rate_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val_item = QTableWidgetItem(format_indian_number(value))
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 2, qty_item)
            self.table.setItem(row, 3, rate_item)
            self.table.setItem(row, 4, val_item)
        self.total_lbl.setText(f"Grand Total: {format_inr(grand_total)}")


class StockItemsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        hdr = QHBoxLayout()
        title = QLabel("Stock Items")
        title.setStyleSheet("font-size:16px;font-weight:bold;color:#1565C0;")
        add_btn = QPushButton("  New Stock Item")
        add_btn.setIcon(get_icon("frontend/assets/icons/plus.svg", "#ffffff"))
        add_btn.setIconSize(QSize(16, 16))
        add_btn.setFixedHeight(36)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background: #1565C0; color: #fff;
                border: none; border-radius: 8px;
                font-size: 13px; font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover  { background: #1976D2; }
            QPushButton:pressed { background: #0D47A1; }
        """)
        add_btn.clicked.connect(self._add)
        hdr.addWidget(title); hdr.addStretch(); hdr.addWidget(add_btn)
        layout.addLayout(hdr)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Name","Group","Unit","HSN/SAC","GST%","Opening Qty","Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in range(2, 6):
            self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().resizeSection(6, 100)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(48)
        layout.addWidget(self.table)
        self._load()

    def showEvent(self, e):
        self._load(); super().showEvent(e)

    def _load(self):
        self.table.setRowCount(0)
        try: items = api.list_stock_items()
        except Exception as ex:
            QMessageBox.warning(self, "Error", str(ex)); return
        for row, item in enumerate(items):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("stock_group", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("unit", "")))
            self.table.setItem(row, 3, QTableWidgetItem(item.get("hsn_sac", "")))
            self.table.setItem(row, 4, QTableWidgetItem(str(item.get("gst_rate", 0)) + "%"))
            self.table.setItem(row, 5, QTableWidgetItem(str(item.get("opening_qty", 0))))

            # ── Action cell ──────────────────────────────────────────────
            cell = QWidget()
            cell_lay = QHBoxLayout(cell)
            cell_lay.setContentsMargins(6, 0, 6, 0)
            cell_lay.setSpacing(6)
            edit_btn = IconActionButton("frontend/assets/icons/edit.svg", "Edit item", variant="edit")
            del_btn  = IconActionButton("frontend/assets/icons/trash.svg", "Delete item", variant="danger")
            edit_btn.clicked.connect(lambda *a, it=item: self._edit(it))
            del_btn.clicked.connect(lambda *a, iid=item["_id"]: self._delete(iid))
            cell_lay.addWidget(edit_btn)
            cell_lay.addWidget(del_btn)
            cell_lay.addStretch()
            self.table.setCellWidget(row, 6, cell)

    def _add(self):
        dlg = StockItemDialog(self)
        if dlg.exec():
            try: api.create_stock_item(dlg.get_data()); self._load()
            except Exception as ex: QMessageBox.warning(self, "Error", str(ex))

    def _edit(self, item):
        dlg = StockItemDialog(self, item)
        if dlg.exec():
            try: api.update_stock_item(item["_id"], dlg.get_data()); self._load()
            except Exception as ex: QMessageBox.warning(self, "Error", str(ex))

    def _delete(self, iid):
        if QMessageBox.question(self, "Confirm", "Delete this stock item?") == QMessageBox.StandardButton.Yes:
            try: api.delete_stock_item(iid); self._load()
            except Exception as ex: QMessageBox.warning(self, "Error", str(ex))


class StockCategoriesTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        hdr = QHBoxLayout()
        title = QLabel("Stock Categories")
        title.setStyleSheet("font-size:16px;font-weight:bold;color:#1565C0;")
        add_btn = QPushButton("  New Stock Category")
        add_btn.setIcon(get_icon("frontend/assets/icons/plus.svg", "#ffffff"))
        add_btn.setIconSize(QSize(16, 16))
        add_btn.setFixedHeight(36)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background: #1565C0; color: #fff;
                border: none; border-radius: 8px;
                font-size: 13px; font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover  { background: #1976D2; }
            QPushButton:pressed { background: #0D47A1; }
        """)
        add_btn.clicked.connect(self._add)
        hdr.addWidget(title); hdr.addStretch(); hdr.addWidget(add_btn)
        layout.addLayout(hdr)
        
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Group", "Price", "Net", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().resizeSection(4, 100)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        self._load()

    def showEvent(self, e):
        self._load(); super().showEvent(e)

    def _load(self):
        self.table.setRowCount(0)
        try:
            cats = api.list_stock_categories()
        except Exception as ex:
            QMessageBox.warning(self, "Error", str(ex)); return
        for row, c in enumerate(cats):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(c.get("name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(c.get("stock_group", "")))
            self.table.setItem(row, 2, QTableWidgetItem(format_indian_number(c.get('price', 0))))
            self.table.setItem(row, 3, QTableWidgetItem(format_indian_number(c.get('net', 0))))
            
            cell = QWidget()
            cell_lay = QHBoxLayout(cell)
            cell_lay.setContentsMargins(6, 0, 6, 0)
            cell_lay.setSpacing(6)
            edit_btn = IconActionButton("frontend/assets/icons/edit.svg", "Edit category", variant="edit")
            del_btn = IconActionButton("frontend/assets/icons/trash.svg", "Delete category", variant="danger")
            edit_btn.clicked.connect(lambda *a, cat=c: self._edit(cat))
            del_btn.clicked.connect(lambda *a, cid=c["_id"]: self._delete(cid))
            cell_lay.addWidget(edit_btn); cell_lay.addWidget(del_btn); cell_lay.addStretch()
            self.table.setCellWidget(row, 4, cell)

    def _add(self):
        dlg = StockCategoryDialog(self)
        if dlg.exec():
            try:
                api.create_stock_category(dlg.get_data())
                self._load()
            except Exception as ex:
                QMessageBox.warning(self, "Error", str(ex))

    def _edit(self, category):
        dlg = StockCategoryDialog(self, category)
        if dlg.exec():
            try:
                api.update_stock_category(category["_id"], dlg.get_data())
                self._load()
            except Exception as ex:
                QMessageBox.warning(self, "Error", str(ex))

    def _delete(self, cid):
        if QMessageBox.question(self, "Confirm", "Delete this stock category?") == QMessageBox.StandardButton.Yes:
            try:
                api.delete_stock_category(cid)
                self._load()
            except Exception as ex:
                QMessageBox.warning(self, "Error", str(ex))


class InventoryPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24); layout.setSpacing(16)
        title = QLabel("Inventory")
        title.setStyleSheet("font-size:22px;font-weight:bold;color:#1565C0;")
        layout.addWidget(title)
        tabs = QTabWidget()
        tabs.addTab(StockSummaryTab(), "Stock Summary")
        tabs.addTab(StockCategoriesTab(), "Stock Categories")
        tabs.addTab(StockItemsTab(),   "Stock Items")
        layout.addWidget(tabs)
