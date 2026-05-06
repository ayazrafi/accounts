from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFileDialog, QMessageBox, QFrame, QGridLayout, QComboBox,
    QInputDialog, QDialog, QDateEdit, QFormLayout, QDialogButtonBox,
    QLineEdit
)
from PySide6.QtCore import Qt, QSize, QDate
from frontend.theme import THEME
from frontend.utils import get_icon
import frontend.api_client as api
import frontend.session as session
import os
from datetime import datetime
from frontend.encryption import encrypt_data, decrypt_data, compress_data, decompress_data

class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsPage")
        self._companies = []
        self._build_ui()

    def _build_ui(self):
        # Clear layout if rebuilding
        if self.layout():
            QWidget().setLayout(self.layout())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # ── Header ──────────────────────────────────────────────────────
        header_lay = QHBoxLayout()
        title_v = QVBoxLayout()
        title_lbl = QLabel("System Settings")
        title_lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {THEME['text_primary']};")
        title_v.addWidget(title_lbl)

        subtitle_lbl = QLabel("Manage your company data, backups, and financial periods.")
        subtitle_lbl.setStyleSheet(f"font-size: 14px; color: {THEME['text_secondary']};")
        title_v.addWidget(subtitle_lbl)
        header_lay.addLayout(title_v)
        header_lay.addStretch()

        # Company Selector (Context)
        selector_v = QVBoxLayout()
        sel_label = QLabel("Active Company Context:")
        sel_label.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {THEME['text_muted']};")
        selector_v.addWidget(sel_label)
        
        self.company_cb = QComboBox()
        self.company_cb.setMinimumWidth(280)
        self.company_cb.setMinimumHeight(40)
        self.company_cb.setStyleSheet(f"""
            QComboBox {{
                padding: 8px 12px;
                border: 2px solid {THEME['border']};
                border-radius: 8px;
                background: white;
                font-weight: bold;
            }}
            QComboBox:hover {{ border-color: {THEME['primary']}; }}
        """)
        self.company_cb.currentIndexChanged.connect(self._on_company_context_changed)
        selector_v.addWidget(self.company_cb)
        
        # Financial Year Display (Readonly)
        fy_lay = QHBoxLayout()
        fy_title = QLabel("Financial Year:")
        fy_title.setStyleSheet(f"font-size: 11px; color: {THEME['text_muted']};")
        self.fy_val = QLabel(f"{session.fiscal_year_from} to {session.fiscal_year_to}")
        self.fy_val.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {THEME['text_primary']};")
        fy_lay.addWidget(fy_title)
        fy_lay.addWidget(self.fy_val)
        fy_lay.addStretch()
        selector_v.addLayout(fy_lay)

        # Period Selection
        period_lay = QHBoxLayout()
        period_title = QLabel("Active Period:")
        period_title.setStyleSheet(f"font-size: 11px; color: {THEME['text_muted']};")
        
        self.p_from = QDateEdit()
        self.p_from.setCalendarPopup(True)
        self.p_from.setFixedWidth(110)
        self.p_from.setDate(QDate.fromString(session.period_from, "yyyy-MM-dd"))
        self.p_from.dateChanged.connect(self._on_period_changed)

        sep = QLabel("to")
        sep.setStyleSheet(f"color: {THEME['text_muted']};")

        self.p_to = QDateEdit()
        self.p_to.setCalendarPopup(True)
        self.p_to.setFixedWidth(110)
        self.p_to.setDate(QDate.fromString(session.period_to, "yyyy-MM-dd"))
        self.p_to.dateChanged.connect(self._on_period_changed)

        period_lay.addWidget(period_title)
        period_lay.addWidget(self.p_from)
        period_lay.addWidget(sep)
        period_lay.addWidget(self.p_to)
        selector_v.addLayout(period_lay)

        header_lay.addLayout(selector_v)
        
        layout.addLayout(header_lay)
        layout.addSpacing(20)

        # ── Main Grid ──────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(24)
        
        # 1. Backup Card
        backup_card = self._create_card(
            "Database Backup",
            "Export all records (Ledgers, Vouchers, Inventory) to a secure JSON file.",
            "frontend/assets/icons/download.svg",
            "Backup Now",
            self._on_backup
        )
        grid.addWidget(backup_card, 0, 0)

        # 2. Restore Card
        restore_card = self._create_card(
            "Restore Data",
            "Import company records from a backup into a NEW company container.",
            "frontend/assets/icons/upload.svg",
            "Restore to New",
            self._on_restore_to_new,
            is_accent=True
        )
        grid.addWidget(restore_card, 0, 1)

        layout.addLayout(grid)
        layout.addStretch()

    def _create_card(self, title, desc, icon_path, btn_text, callback, is_accent=False):
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid {THEME['border']};
                border-radius: 12px;
                padding: 24px;
            }}
            QFrame:hover {{ border-color: {THEME['primary']}; background-color: #fafafa; }}
        """)
        
        card_lay = QVBoxLayout(card)
        card_lay.setSpacing(15)

        # Header
        head_lay = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon(icon_path, THEME['primary']).pixmap(32, 32))
        head_lay.addWidget(icon_lbl)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {THEME['text_primary']};")
        head_lay.addWidget(title_lbl, 1)
        card_lay.addLayout(head_lay)

        # Description
        desc_lbl = QLabel(desc)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"color: {THEME['text_secondary']}; line-height: 1.5; font-size: 13px;")
        card_lay.addWidget(desc_lbl)

        card_lay.addStretch()

        # Action Button
        btn = QPushButton(btn_text)
        bg_color = THEME['primary'] if not is_accent else "#065f46"
        hover_color = THEME['primary_dark'] if not is_accent else "#047857"
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {hover_color}; }}
        """)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(callback)
        card_lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignRight)
        
        return card

    def _on_period_changed(self):
        f = self.p_from.date().toString("yyyy-MM-dd")
        t = self.p_to.date().toString("yyyy-MM-dd")
        session.period_from = f
        session.period_to = t
        
        # Update MW header if possible
        mw = self.window()
        if hasattr(mw, "refresh_company_header"):
            mw.refresh_company_header()

    def showEvent(self, event):
        self._refresh_companies()
        super().showEvent(event)

    def _refresh_companies(self):
        try:
            self.company_cb.blockSignals(True)
            self._companies = api.list_companies()
            self.company_cb.clear()
            current_cid = session.company_id
            select_idx = -1
            for i, c in enumerate(self._companies):
                self.company_cb.addItem(c["name"], c["_id"])
                if str(c["_id"]) == str(current_cid):
                    select_idx = i
            if select_idx >= 0:
                self.company_cb.setCurrentIndex(select_idx)
            self.company_cb.blockSignals(False)
        except Exception: pass

    def _get_selected_company(self):
        idx = self.company_cb.currentIndex()
        if idx >= 0:
            return self._companies[idx]
        return None

    def _on_company_context_changed(self):
        comp = self._get_selected_company()
        if comp:
            session.set_company(
                cid=comp["_id"],
                name=comp["name"],
                fy_from=comp.get("fiscal_year_from", ""),
                fy_to=comp.get("fiscal_year_to", ""),
            )
            # Rebuild UI to show updated FY and Period
            self._build_ui()
            self._refresh_companies()
            # Refresh main window header
            mw = self.window()
            if hasattr(mw, "refresh_company_header"):
                mw.refresh_company_header()

    def _on_backup(self):
        comp = self._get_selected_company()
        if not comp:
            QMessageBox.warning(self, "No Context", "Please select a company context first.")
            return
        cid = comp["_id"]
        name = comp["name"]

        # Prompt for Encryption Key
        password, ok = QInputDialog.getText(
            self, "Backup Encryption", 
            "Enter a secret key to encrypt the backup:",
            QLineEdit.EchoMode.Password
        )
        if not ok or not password:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Encrypted Backup", 
            f"backup_{name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.enc",
            "Encrypted Files (*.enc)"
        )
        if not file_path: return

        try:
            content, _ = api.backup_company(cid)
            
            # Step 1: Compress
            json_filename = f"backup_{name.replace(' ', '_')}.json"
            compressed = compress_data(content, json_filename)
            
            # Step 2: Encrypt (AES-256-CBC)
            encrypted = encrypt_data(compressed, password)
            
            with open(file_path, "wb") as f:
                f.write(encrypted)
                
            QMessageBox.information(self, "Backup Successful", f"Encrypted backup for '{name}' created successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Backup failed: {e}")

    def _on_restore_to_new(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Encrypted Backup", "", "Encrypted Files (*.enc);;JSON Files (*.json)")
        if not file_path: return

        # Prompt for Decryption Key if it's an .enc file
        is_encrypted = file_path.endswith(".enc")
        password = ""
        if is_encrypted:
            password, ok = QInputDialog.getText(
                self, "Backup Decryption", 
                "Enter the secret key to decrypt the backup:",
                QLineEdit.EchoMode.Password
            )
            if not ok or not password:
                return

        new_name, ok = QInputDialog.getText(self, "Restore to New", "Enter Name for the New Restored Company:")
        if not ok or not new_name.strip(): return

        temp_json = None
        try:
            with open(file_path, "rb") as f:
                raw_data = f.read()
            
            if is_encrypted:
                # Step 1: Decrypt
                compressed = decrypt_data(raw_data, password)
                # Step 2: Decompress
                json_content = decompress_data(compressed)
            else:
                json_content = raw_data

            # Create a temporary JSON file for api.restore_company
            temp_json = f"temp_restore_{datetime.now().strftime('%H%M%S')}.json"
            with open(temp_json, "wb") as f:
                f.write(json_content)

            # Create container
            new_co = {
                "name": new_name.strip(),
                "financial_year_from": "2024-04-01",
                "books_beginning_from": "2024-04-01",
                "state": "Maharashtra"
            }
            resp = api.create_company(new_co)
            new_cid = resp.get("id")
            if not new_cid: raise Exception("Failed to create company container.")

            # Restore
            api.restore_company(new_cid, temp_json)
            QMessageBox.information(self, "Success", f"Data restored successfully into new company '{new_name}'.")
            self._refresh_companies()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Restore failed: {e}")
        finally:
            if temp_json and os.path.exists(temp_json):
                os.remove(temp_json)
