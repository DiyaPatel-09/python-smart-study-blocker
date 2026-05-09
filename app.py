"""
app.py - Entry point for Smart Study Distraction Blocker

Run with:
    python app.py

Requirements:
    pip install -r requirements.txt
"""

import sys
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)


def main():
    logger.info("Starting Smart Study Distraction Blocker")

    app = QApplication(sys.argv)
    app.setApplicationName("Smart Study Distraction Blocker")
    app.setOrganizationName("StudyBlocker")

    # High-DPI support (attribute names vary by PyQt5 version)
    try:
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except AttributeError:
        pass

    from gui import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
