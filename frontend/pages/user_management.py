from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QDialog, QFormLayout, QLineEdit, QCheckBox, QComboBox,
    QDialogButtonBox, QFrame, QTabWidget
)
from PySide6.QtCore import Qt, QSize
import frontend.api_client as api
import frontend.session as session
from frontend.utils import get_icon, SearchableComboBox

class UserManagementPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("UserManagementPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        
        # Header
        hdr = QHBoxLayout()
        title = QLabel("User Management")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1565C0;")
        hdr.addWidget(title)
        hdr.addStretch()
        
        self.add_user_btn = QPushButton("  Create New User")
        self.add_user_btn.setIcon(get_icon("frontend/assets/icons/plus.svg", "#ffffff"))
        self.add_user_btn.setIconSize(QSize(16, 16))
        self.add_user_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_user_btn.setStyleSheet("""
            QPushButton {
                background: #1565C0; color: #fff;
                border: none; border-radius: 8px;
                font-size: 13px; font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover { background: #1976D2; }
        """)
        self.add_user_btn.clicked.connect(self._create_user)
        hdr.addWidget(self.add_user_btn)
        layout.addLayout(hdr)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(CompanyAccessTab(), "Company Access")
        self.tabs.addTab(GlobalUsersTab(), "All Users")
        self.tabs.addTab(RolesPermissionsTab(), "Roles & Permissions")
        layout.addWidget(self.tabs)
        
        if not session.is_super_admin:
            self.setEnabled(False)
            title.setText("User Management (Restricted)")

    def _create_user(self):
        dlg = UserDialog(self)
        if dlg.exec():
            # Refresh both tabs
            self.tabs.widget(0)._load()
            self.tabs.widget(1)._load()


class CompanyAccessTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Filter Bar
        flt_bar = QHBoxLayout()
        flt_bar.addWidget(QLabel("Select Company to Manage Access:"))
        self.company_cb = SearchableComboBox()
        self.company_cb.setMinimumWidth(250)
        self.company_cb.currentIndexChanged.connect(self._load)
        flt_bar.addWidget(self.company_cb)
        
        flt_bar.addStretch()
        
        self.add_mapping_btn = QPushButton("  Map User to this Company")
        self.add_mapping_btn.setIcon(get_icon("frontend/assets/icons/plus.svg", "#1565C0"))
        self.add_mapping_btn.setIconSize(QSize(16, 16))
        self.add_mapping_btn.setStyleSheet("color: #1565C0; font-weight: 600; border: 1px solid #1565C0; padding: 6px 12px; border-radius: 6px;")
        self.add_mapping_btn.clicked.connect(self._add_mapping)
        flt_bar.addWidget(self.add_mapping_btn)
        
        layout.addLayout(flt_bar)
        
        # Table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Username", "Role", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(48)
        layout.addWidget(self.table)
        
        self._load_companies()

    def _load_companies(self):
        try:
            self.company_cb.clear()
            self.company_cb.addItem("Select a Company...", None)
            companies = api.list_all_companies()
            for c in companies:
                self.company_cb.addItem(c['name'], c['id'])
        except Exception:
            pass

    def _load(self):
        cid = self.company_cb.currentData()
        self.table.setRowCount(0)
        if not cid:
            return
        
        try:
            mappings = api.list_mappings(company_id=cid)
            for m in mappings:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(m['username']))
                self.table.setItem(row, 1, QTableWidgetItem(m['role']))
                
                del_btn = QPushButton("Remove Access")
                del_btn.setStyleSheet("color: #ef4444; border: none; font-weight: 500; background: transparent;")
                del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                del_btn.clicked.connect(lambda *a, mid=m['id']: self._remove_mapping(mid))
                self.table.setCellWidget(row, 2, del_btn)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _add_mapping(self):
        cid = self.company_cb.currentData()
        if not cid:
            QMessageBox.warning(self, "Required", "Please select a company first.")
            return
        
        dlg = MappingDialog(self, company_id=cid)
        if dlg.exec():
            self._load()

    def _remove_mapping(self, mid):
        if QMessageBox.question(self, "Confirm", "Remove this user's access to this company?") == QMessageBox.StandardButton.Yes:
            try:
                api.delete_mapping(mid)
                self._load()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))


class GlobalUsersTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Username", "Role", "Status", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(48)
        layout.addWidget(self.table)
        
        self._load()

    def _load(self):
        try:
            users = api.list_users()
            self.table.setRowCount(0)
            for u in users:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(u['username']))
                self.table.setItem(row, 1, QTableWidgetItem("Super Admin" if u['is_super_admin'] else "Standard User"))
                self.table.setItem(row, 2, QTableWidgetItem("Active" if u['is_active'] else "Inactive"))
                
                btn_lay = QHBoxLayout()
                btn_lay.setContentsMargins(4, 4, 4, 4)
                
                map_btn = QPushButton("Map to Company")
                map_btn.setStyleSheet("color: #3b82f6; border: none; font-weight: 500; background: transparent;")
                map_btn.clicked.connect(lambda *a, u_id=u['id']: self._map_to_company(u_id))
                
                widget = QWidget()
                widget.setLayout(btn_lay)
                btn_lay.addWidget(map_btn)
                btn_lay.addStretch()
                self.table.setCellWidget(row, 3, widget)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _map_to_company(self, user_id):
        dlg = MappingDialog(self, user_id=user_id)
        if dlg.exec():
            # Refresh mapping tab if possible
            pass


class UserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create User")
        self.setFixedWidth(400)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.is_admin = QCheckBox("Super Admin (Access to all companies)")
        
        form.addRow("Username:", self.username)
        form.addRow("Password:", self.password)
        form.addRow("", self.is_admin)
        
        layout.addLayout(form)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self):
        data = {
            "username": self.username.text().strip(),
            "password": self.password.text().strip(),
            "is_super_admin": self.is_admin.isChecked()
        }
        if not data['username'] or not data['password']:
            QMessageBox.warning(self, "Error", "Username and password are required")
            return
        
        try:
            api.create_user(data)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


class MappingDialog(QDialog):
    def __init__(self, parent, user_id=None, company_id=None):
        super().__init__(parent)
        self.user_id = user_id
        self.company_id = company_id
        self.setWindowTitle("Map User to Company")
        self.setFixedWidth(420)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.user_cb = SearchableComboBox()
        self.company_cb = SearchableComboBox()
        self.role_cb = SearchableComboBox()
        
        try:
            if not user_id:
                users = api.list_users()
                for u in users:
                    if not u['is_super_admin']: # Super admins don't need mapping
                        self.user_cb.addItem(u['username'], u['id'])
            else:
                self.user_cb.addItem("Current User", user_id)
                self.user_cb.setEnabled(False)
                
            if not company_id:
                companies = api.list_all_companies()
                for c in companies:
                    self.company_cb.addItem(c['name'], c['id'])
            else:
                self.company_cb.addItem("Current Company", company_id)
                self.company_cb.setEnabled(False)
            
            roles = api.list_roles()
            for r in roles:
                self.role_cb.addItem(r['name'], r['id'])
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.reject()
            return
            
        form.addRow("User:", self.user_cb)
        form.addRow("Company:", self.company_cb)
        form.addRow("Role:", self.role_cb)
        
        layout.addLayout(form)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self):
        data = {
            "user_id": self.user_cb.currentData(),
            "company_id": self.company_cb.currentData(),
            "role_id": self.role_cb.currentData()
        }
        if not data['user_id'] or not data['company_id'] or not data['role_id']:
            QMessageBox.warning(self, "Error", "All fields are required")
            return
            
        try:
            api.create_mapping(data)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


class RolesPermissionsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # Select Role
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Select Role to Configure Permissions:"))
        self.role_cb = SearchableComboBox()
        self.role_cb.setMinimumWidth(200)
        self.role_cb.currentIndexChanged.connect(self._on_role_changed)
        hdr.addWidget(self.role_cb)
        hdr.addStretch()
        layout.addLayout(hdr)
        
        # Permissions Grid
        self.perms_table = QTableWidget(10, 5)
        self.perms_table.setHorizontalHeaderLabels(["Module", "View", "Edit (Create)", "Delete", "Update (Modify)"])
        self.perms_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.perms_table.verticalHeader().setVisible(False)
        self.perms_table.verticalHeader().setDefaultSectionSize(36)
        layout.addWidget(self.perms_table)
        
        self.modules = [
            ("Sales", "sales"),
            ("Purchase", "purchase"),
            ("Debit Note", "debit note"),
            ("Credit Note", "credit note"),
            ("Payment", "payment"),
            ("Receipt", "receipt"),
            ("Contra", "contra"),
            ("Journal", "journal"),
            ("Ledger", "ledger"),
            ("Item", "item")
        ]
        
        self.checkbox_map = {}
        for idx, (label, key) in enumerate(self.modules):
            self.perms_table.setItem(idx, 0, QTableWidgetItem(label))
            
            self.checkbox_map[key] = {}
            for col_idx, action in enumerate(["view", "edit", "delete", "update"], start=1):
                cb = QCheckBox()
                w = QWidget()
                lay = QHBoxLayout(w)
                lay.setContentsMargins(0, 0, 0, 0)
                lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lay.addWidget(cb)
                
                self.perms_table.setCellWidget(idx, col_idx, w)
                self.checkbox_map[key][action] = cb
                
        # Save Button
        btn_lay = QHBoxLayout()
        self.save_btn = QPushButton("Save Role Permissions")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: #16a34a; color: #fff;
                border: none; border-radius: 6px;
                font-weight: bold; font-size: 13px;
                padding: 8px 20px;
            }
            QPushButton:hover { background: #15803d; }
        """)
        self.save_btn.clicked.connect(self._save)
        btn_lay.addStretch()
        btn_lay.addWidget(self.save_btn)
        layout.addLayout(btn_lay)
        
        self._load_roles()

    def _load_roles(self):
        try:
            self.role_cb.blockSignals(True)
            self.role_cb.clear()
            self.role_cb.addItem("Select Role...", None)
            roles = api.list_roles()
            for r in roles:
                self.role_cb.addItem(r['name'], r['id'])
        except Exception:
            pass
        finally:
            self.role_cb.blockSignals(False)

    def _on_role_changed(self, idx):
        role_id = self.role_cb.currentData()
        # Reset all checkboxes first
        for key in self.checkbox_map:
            for action in self.checkbox_map[key]:
                self.checkbox_map[key][action].setChecked(False)
                
        if not role_id:
            return
            
        try:
            res = api.get_role_permissions(role_id)
            perms = res.get("permissions", {})
            for key in self.checkbox_map:
                mod_perms = perms.get(key, {})
                for action in self.checkbox_map[key]:
                    self.checkbox_map[key][action].setChecked(mod_perms.get(action, False))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load role permissions: {e}")

    def _save(self):
        role_id = self.role_cb.currentData()
        if not role_id:
            QMessageBox.warning(self, "Role Required", "Please select a Role first.")
            return
            
        perms_data = {}
        for key in self.checkbox_map:
            perms_data[key] = {
                action: cb.isChecked() for action, cb in self.checkbox_map[key].items()
            }
            
        try:
            api.save_role_permissions({"role_id": role_id, "permissions": perms_data})
            QMessageBox.information(self, "Success", "Role permissions saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save role permissions: {e}")
