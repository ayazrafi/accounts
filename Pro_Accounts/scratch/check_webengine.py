try:
    from PySide6.QtWebEngineCore import QWebEnginePage
    print("QtWebEngine is available")
except ImportError:
    print("QtWebEngine is NOT available")
