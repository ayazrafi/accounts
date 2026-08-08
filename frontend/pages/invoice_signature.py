import base64
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox,
    QHeaderView, QLineEdit, QDialog, QFormLayout, QDialogButtonBox
)
from PySide6.QtGui import QFont, QPixmap, QIcon
from PySide6.QtCore import Qt, QSize, QByteArray, QEvent
import frontend.api_client as api
from frontend.utils import get_icon, setup_enter_nav
from frontend.theme import THEME


class UploadSignatureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upload Signature")
        self.setMinimumWidth(420)
        self.image_base64 = ""
        self._build_ui()

    def _build_ui(self):
        form = QFormLayout(self)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Authorized Signatory, Director")
        self.name_edit.setMinimumHeight(30)
        form.addRow("Label/Name *:", self.name_edit)

        self.file_lbl = QLabel("No image selected")
        self.file_lbl.setStyleSheet("color: #64748b; font-style: italic;")
        
        self.preview_lbl = QLabel()
        self.preview_lbl.setFixedSize(180, 80)
        self.preview_lbl.setStyleSheet("border: 1px dashed #cbd5e1; border-radius: 4px; background: #f8fafc;")
        self.preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        select_btn = QPushButton("Select Image...")
        select_btn.setStyleSheet(f"background: {THEME['primary']}; color: white; border: none; border-radius: 4px; padding: 4px 12px; font-weight: bold;")
        select_btn.clicked.connect(self._select_image)

        file_lay = QHBoxLayout()
        file_lay.addWidget(self.file_lbl, 1)
        file_lay.addWidget(select_btn)
        form.addRow("Signature Image *:", file_lay)
        form.addRow("Preview:", self.preview_lbl)

        self.btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.btns.accepted.connect(self._accept)
        self.btns.rejected.connect(self.reject)
        form.addRow(self.btns)

        setup_enter_nav(self, [self.name_edit])

    def _select_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Signature Image", "", 
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            try:
                self.file_lbl.setText(path.split('/')[-1])
                with open(path, "rb") as f:
                    data = f.read()
                self.image_base64 = base64.b64encode(data).decode("utf-8")
                
                # Show preview
                ba = QByteArray.fromBase64(self.image_base64.encode('utf-8'))
                pixmap = QPixmap()
                pixmap.loadFromData(ba)
                scaled = pixmap.scaled(self.preview_lbl.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.preview_lbl.setPixmap(scaled)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load image: {e}")

    def _accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "Label/Name is required."); return
        if not self.image_base64:
            QMessageBox.warning(self, "Validation Error", "Please select a signature image file."); return
        self.accept()

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "image_data": self.image_base64
        }


class InvoiceSignaturePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InvoiceSignaturePage")
        self._signatures = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title_v = QVBoxLayout()
        title = QLabel("Invoice Signatures")
        title.setStyleSheet(f"font-size:22px;font-weight:bold;color:{THEME['text_primary']};")
        subtitle = QLabel("Upload and select the active signature to display on your Tax Invoices.")
        subtitle.setStyleSheet(f"font-size:13px;color:{THEME['text_secondary']};")
        title_v.addWidget(title)
        title_v.addWidget(subtitle)
        hdr.addLayout(title_v)
        hdr.addStretch()

        self.upload_btn = QPushButton("  Upload Signature")
        self.upload_btn.setIcon(get_icon("frontend/assets/icons/upload.svg", "#ffffff"))
        self.upload_btn.setIconSize(QSize(16, 16))
        self.upload_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {THEME['primary_dark']}; }}
        """)
        self.upload_btn.clicked.connect(self._on_upload)
        hdr.addWidget(self.upload_btn)
        layout.addLayout(hdr)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Status", "Label Name", "Signature Image Preview", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in [0, 2, 3]:
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(74) # taller rows for image preview
        
        self.table.installEventFilter(self)
        self.table.itemDoubleClicked.connect(self._on_double_click)

        layout.addWidget(self.table)
        self._load()

    def showEvent(self, event):
        self._load()
        super().showEvent(event)
        self.table.setFocus()

    def _load(self):
        self.table.setRowCount(0)
        try:
            self._signatures = api.list_signatures()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load signatures: {e}")
            return

        for row, sig in enumerate(self._signatures):
            self.table.insertRow(row)
            
            # Status (Active indicator)
            is_active = sig.get("is_active", False)
            status_widget = QWidget()
            status_lay = QHBoxLayout(status_widget)
            status_lay.setContentsMargins(10, 0, 10, 0)
            status_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            status_lbl = QLabel("ACTIVE" if is_active else "Inactive")
            if is_active:
                status_lbl.setStyleSheet("color: #16a34a; font-weight: bold; background: #dcfce7; border: 1px solid #bbf7d0; border-radius: 4px; padding: 4px 10px; font-size: 10px;")
            else:
                status_lbl.setStyleSheet("color: #64748b; background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 4px; padding: 4px 10px; font-size: 10px;")
            status_lay.addWidget(status_lbl)
            self.table.setCellWidget(row, 0, status_widget)

            # Name
            name_item = QTableWidgetItem(sig.get("name", ""))
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            name_item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold if is_active else QFont.Weight.Normal))
            self.table.setItem(row, 1, name_item)

            # Preview Thumbnail
            preview_widget = QWidget()
            preview_lay = QHBoxLayout(preview_widget)
            preview_lay.setContentsMargins(6, 4, 6, 4)
            preview_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            img_lbl = QLabel()
            img_lbl.setFixedSize(140, 54)
            img_lbl.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 4px; background: white;")
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            try:
                ba = QByteArray.fromBase64(sig["image_data"].encode('utf-8'))
                pixmap = QPixmap()
                pixmap.loadFromData(ba)
                scaled = pixmap.scaled(img_lbl.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                img_lbl.setPixmap(scaled)
            except Exception:
                img_lbl.setText("No Preview")
            
            preview_lay.addWidget(img_lbl)
            self.table.setCellWidget(row, 2, preview_widget)

            # Actions
            act_widget = QWidget()
            act_lay = QHBoxLayout(act_widget)
            act_lay.setContentsMargins(6, 0, 6, 0)
            act_lay.setSpacing(10)
            act_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

            if not is_active:
                act_btn = QPushButton("Activate")
                act_btn.setStyleSheet("QPushButton { background: #3b82f6; color: white; border: none; border-radius: 4px; padding: 3px 10px; font-size: 11px; font-weight: bold; } QPushButton:hover { background: #2563eb; }")
                act_btn.clicked.connect(lambda *a, sid=sig["_id"]: self._on_activate(sid))
                act_lay.addWidget(act_btn)

            del_btn = QPushButton()
            del_btn.setIcon(get_icon("frontend/assets/icons/trash.svg", "#c62828"))
            del_btn.setFixedSize(28, 28)
            del_btn.setStyleSheet("QPushButton { border:none; background:transparent; } QPushButton:hover { background:#fee2e2; border-radius:4px; }")
            del_btn.clicked.connect(lambda *a, sid=sig["_id"]: self._on_delete(sid))
            act_lay.addWidget(del_btn)
            
            self.table.setCellWidget(row, 3, act_widget)

        if self.table.rowCount() > 0:
            self.table.setCurrentCell(0, 0)

    def _on_upload(self):
        dlg = UploadSignatureDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                api.upload_signature(data["name"], data["image_data"])
                self._load()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to upload signature: {e}")

    def _on_activate(self, sig_id):
        try:
            api.activate_signature(sig_id)
            self._load()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to activate signature: {e}")

    def _on_delete(self, sig_id):
        if QMessageBox.question(self, "Confirm Delete", "Are you sure you want to delete this signature?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                api.delete_signature(sig_id)
                self._load()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete signature: {e}")

    def _activate_selected(self):
        row = self.table.currentRow()
        if 0 <= row < len(self._signatures):
            sig = self._signatures[row]
            if sig.get("is_active"):
                return
            self._on_activate(sig["_id"])

    def _on_double_click(self, item):
        self._activate_selected()

    def eventFilter(self, obj, event):
        if obj is self.table and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._activate_selected()
                return True
        return super().eventFilter(obj, event)
