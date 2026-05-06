"""
Pro Accounts — Main Entry Point
1. Auto-starts MongoDB if not running on configured port
2. Starts Flask backend in a background thread
3. Launches PySide6 desktop app
"""
import sys
import time
import threading
import os

os.environ.setdefault("FLASK_PORT", "5050")

from dotenv import load_dotenv
load_dotenv()


def _parse_mongo_port() -> int:
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    try:
        return int(uri.rstrip("/").split(":")[-1])
    except ValueError:
        return 27017


def start_flask():
    from backend.app import run_server
    run_server()


def wait_for_server(port: int, timeout: int = 20):
    import requests
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def main():
    flask_port = int(os.getenv("FLASK_PORT", 5050))
    mongo_port = _parse_mongo_port()

    # ── PySide6 app must run in main thread ──────────────────────────────────
    from PySide6.QtWidgets import QApplication, QSplashScreen, QMessageBox
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap, QColor, QPainter, QFont

    # Required for QtWebEngine (used in PDF viewer)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("Bestie Accounts")
    app.setStyle("Fusion")

    # ── Splash screen — must be drawn BEFORE applying the global theme
    #   so no active QPainter is alive when setFont / setStyleSheet fires.
    splash_pix = QPixmap(480, 220)
    splash_pix.fill(QColor("#ffffff"))
    painter = QPainter(splash_pix)
    painter.setPen(QColor("#1565C0"))
    font = QFont("Segoe UI", 22, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(30, 85, "Bestie Accounts")
    painter.setPen(QColor("#546e7a"))
    font2 = QFont("Segoe UI", 11)
    painter.setFont(font2)
    painter.drawText(30, 115, "Smart Accounting Software")
    painter.setPen(QColor("#1565C0"))
    painter.drawLine(30, 130, 450, 130)
    painter.end()                       # ← must finish BEFORE apply_global_style

    splash = QSplashScreen(splash_pix)
    splash.show()
    app.processEvents()

    # Apply the centralised theme AFTER the painter is fully closed
    from frontend.theme import apply_global_style
    apply_global_style(app)

    def update_splash(msg: str):
        splash.showMessage(
            f"  {msg}",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
            QColor("#89b4fa"),
        )
        app.processEvents()

    # ── Step 1: Ensure MongoDB is running ────────────────────────────────────
    update_splash(f"Checking MongoDB on port {mongo_port}...")
    from backend.mongo_manager import ensure_mongodb_running
    mongo_ok = ensure_mongodb_running(port=mongo_port, status_callback=update_splash)

    if not mongo_ok:
        QMessageBox.critical(
            None,
            "MongoDB Error",
            f"Could not start MongoDB on port {mongo_port}.\n\n"
            "Please ensure:\n"
            "  • MongoDB is installed\n"
            "  • OR update MONGO_URI in .env to the correct port\n\n"
            "Check logs\\mongod.log for details.",
        )
        sys.exit(1)

    # ── Step 2: Start Flask backend ──────────────────────────────────────────
    update_splash("Starting backend server...")
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    update_splash("Waiting for backend to be ready...")
    if not wait_for_server(flask_port):
        QMessageBox.critical(
            None,
            "Backend Error",
            "Could not connect to the backend server.\nPlease restart the application.",
        )
        sys.exit(1)

    # ── Step 3: Launch main window ───────────────────────────────────────────
    update_splash("Loading application...")
    from frontend.company_selector import CompanySelectorDialog
    selector = CompanySelectorDialog()
    splash.finish(selector)
    if selector.exec() != selector.DialogCode.Accepted:
        sys.exit(0)

    from frontend.main_window import MainWindow
    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
