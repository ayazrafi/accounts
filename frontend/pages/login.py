from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, 
    QLabel, QFrame, QGraphicsDropShadowEffect, QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QColor, QFont, QIcon
from frontend.theme import THEME
import frontend.api_client as api
import frontend.session as session

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bestie Accounts - Login")
        self.setFixedSize(800, 500)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main Container
        container = QFrame()
        container.setObjectName("LoginContainer")
        container.setStyleSheet(f"""
            QFrame#LoginContainer {{
                background-color: white;
                border-radius: 20px;
            }}
        """)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 10)
        container.setGraphicsEffect(shadow)
        
        layout.addWidget(container)

        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Left Side - Image/Branding
        left_panel = QFrame()
        left_panel.setFixedWidth(350)
        left_panel.setStyleSheet("""
            QFrame {
                background-color: #1565C0;
                border-top-left-radius: 20px;
                border-bottom-left-radius: 20px;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        from frontend.utils import resolve_path
        bg_label = QLabel()
        bg_pixmap = QPixmap(resolve_path("frontend/assets/images/login_bg.png"))
        if not bg_pixmap.isNull():
            bg_label.setPixmap(bg_pixmap.scaled(350, 500, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        bg_label.setFixedSize(350, 500)
        bg_label.setStyleSheet("border-top-left-radius: 20px; border-bottom-left-radius: 20px;")
        
        # Overlay for branding
        overlay = QFrame(bg_label)
        overlay.setFixedSize(350, 500)
        overlay.setStyleSheet("background-color: rgba(21, 101, 192, 0.6); border-top-left-radius: 20px; border-bottom-left-radius: 20px;")
        
        brand_layout = QVBoxLayout(overlay)
        brand_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel("Bestie")
        title.setStyleSheet("color: white; font-size: 42px; font-weight: bold; background: transparent;")
        brand_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        
        subtitle = QLabel("Accounts")
        subtitle.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 24px; background: transparent;")
        brand_layout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignCenter)
        
        container_layout.addWidget(left_panel)

        # Right Side - Form
        right_panel = QFrame()
        right_panel.setStyleSheet("background-color: white; border-top-right-radius: 20px; border-bottom-right-radius: 20px;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(40, 40, 40, 40)
        right_layout.setSpacing(20)

        # Close Button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #999;
                font-size: 18px;
                border: none;
            }
            QPushButton:hover {
                color: #ff4444;
            }
        """)
        
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_layout.addWidget(close_btn)
        right_layout.addLayout(close_layout)
        
        # Welcome Text
        welcome = QLabel("Welcome Back")
        welcome.setStyleSheet("font-size: 28px; font-weight: bold; color: #333;")
        right_layout.addWidget(welcome)
        
        instr = QLabel("Please enter your credentials to login.")
        instr.setStyleSheet("color: #666; font-size: 14px;")
        right_layout.addWidget(instr)
        
        right_layout.addSpacing(10)

        # Inputs
        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")
        self.username.setMinimumHeight(45)
        self.username.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid #eee;
                border-radius: 10px;
                padding: 0 15px;
                font-size: 14px;
                color: #333;
            }}
            QLineEdit:focus {{
                border-color: {THEME['primary']};
            }}
        """)
        right_layout.addWidget(self.username)

        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setMinimumHeight(45)
        self.password.setStyleSheet(self.username.styleSheet())
        self.password.returnPressed.connect(self.handle_login)
        right_layout.addWidget(self.password)

        right_layout.addSpacing(10)

        # Login Button
        self.login_btn = QPushButton("LOGIN")
        self.login_btn.setMinimumHeight(50)
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.clicked.connect(self.handle_login)
        self.login_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['primary']};
                color: white;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {THEME['primary_hover']};
            }}
            QPushButton:pressed {{
                background-color: {THEME['primary_active']};
            }}
        """)
        right_layout.addWidget(self.login_btn)
        
        right_layout.addStretch()
        
        container_layout.addWidget(right_panel, 1)

    def handle_login(self):
        user = self.username.text().strip()
        pw = self.password.text().strip()
        
        if not user or not pw:
            QMessageBox.warning(self, "Login Error", "Please enter both username and password.")
            return

        try:
            res = api.login(user, pw)
            session.set_user(
                res['user']['id'],
                res['user']['username'],
                res['token'],
                res['user'].get('is_super_admin', False)
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Login Failed", str(e))
