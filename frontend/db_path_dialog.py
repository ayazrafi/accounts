import os
import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from frontend.theme import THEME
from frontend.utils import get_icon

class DbPathDialog(QDialog):
    def __init__(self, parent=None, retry_mode=False):
        super().__init__(parent)
        self.retry_mode = retry_mode
        self.setWindowTitle("Database Connection Setup")
        self.setFixedWidth(520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build_ui()
        self._load_current_path()

    def _build_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: white;
            }}
            QLabel {{
                color: {THEME['text_primary']};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Icon and Title
        header_lay = QHBoxLayout()
        header_lay.setSpacing(12)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon("frontend/assets/icons/database.svg", THEME['primary']).pixmap(36, 36))
        header_lay.addWidget(icon_lbl)

        title_lbl = QLabel("Database Configuration" if not self.retry_mode else "Database Startup Failed")
        title_color = THEME['primary'] if not self.retry_mode else "#dc2626"
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {title_color};")
        header_lay.addWidget(title_lbl, 1)
        layout.addLayout(header_lay)

        # Description
        if not self.retry_mode:
            desc_text = (
                "Please configure the local directory path where your database data files are stored. "
                "Click Connect to start the database server."
            )
        else:
            desc_text = (
                "Could not connect to or start MongoDB on the configured path. "
                "This usually happens if the folder path is incorrect or write-protected. "
                "Please check and correct the folder path below:"
            )

        desc_lbl = QLabel(desc_text)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"color: {THEME['text_secondary']}; line-height: 1.5; font-size: 13px;")
        layout.addWidget(desc_lbl)

        # Path Form Input + Browse
        form_lay = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 10px;
                border: 1px solid {THEME['border']};
                border-radius: 6px;
                background: white;
                font-size: 13px;
                color: {THEME['text_primary']};
            }}
        """)
        self.path_input.setMinimumHeight(40)
        form_lay.addWidget(self.path_input, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.setMinimumHeight(40)
        browse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #f1f5f9;
                color: #0f172a;
                border: 1px solid {THEME['border']};
                border-radius: 6px;
                padding: 0 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: #e2e8f0; }}
        """)
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._on_browse)
        form_lay.addWidget(browse_btn)
        layout.addLayout(form_lay)

        # Spacer
        layout.addSpacing(10)

        # Action Buttons (Cancel / Connect)
        btn_lay = QHBoxLayout()
        btn_lay.addStretch()

        cancel_btn = QPushButton("Cancel & Exit")
        cancel_btn.setMinimumHeight(38)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {THEME['text_secondary']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: #f8fafc; color: {THEME['text_primary']}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_lay.addWidget(cancel_btn)

        save_btn = QPushButton("Connect" if not self.retry_mode else "Save & Retry")
        save_btn.setMinimumHeight(38)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {THEME['primary_dark']}; }}
        """)
        save_btn.clicked.connect(self._on_save)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_lay.addWidget(save_btn)

        layout.addLayout(btn_lay)

    def _load_current_path(self):
        from backend.config import load_env
        load_env()
        path = os.getenv("MONGO_DBPATH")
        if not path:
            try:
                import backend.mongo_manager as mm
                path = mm.DATA_DIR
            except Exception:
                path = r"C:\data\db"
        self.path_input.setText(os.path.normpath(path))

    def _on_browse(self):
        current = self.path_input.text()
        dir_path = QFileDialog.getExistingDirectory(self, "Select Database Directory", current)
        if dir_path:
            self.path_input.setText(os.path.normpath(dir_path))

    def _on_save(self):
        new_path = self.path_input.text().strip()
        if not new_path:
            QMessageBox.warning(self, "Validation Error", "Database path cannot be empty.")
            return

        try:
            # Write to .env Directly
            from backend.config import get_env_path
            env_file = get_env_path()

            lines = []
            if os.path.exists(env_file):
                with open(env_file, "r") as f:
                    lines = f.readlines()

            found = False
            new_lines = []
            for line in lines:
                if line.strip().startswith("MONGO_DBPATH="):
                    new_lines.append(f"MONGO_DBPATH={new_path}\n")
                    found = True
                else:
                    new_lines.append(line)

            if not found:
                if new_lines and not new_lines[-1].endswith("\n"):
                    new_lines[-1] += "\n"
                new_lines.append(f"MONGO_DBPATH={new_path}\n")

            with open(env_file, "w") as f:
                f.writelines(new_lines)

            # Reload environment variable
            os.environ["MONGO_DBPATH"] = new_path
            from backend.config import load_env
            load_env()

            # Update mongo_manager DATA_DIR
            import backend.mongo_manager as mm
            mm.DATA_DIR = new_path

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Write Error", f"Failed to save environment path:\n{e}")
