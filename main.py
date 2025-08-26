# main.py
import sys
from PyQt6.QtWidgets import QApplication
# Import from the NEW PyQt6 GUI file
from gui_qt import VideoProcessingApp

if __name__ == "__main__":
    # Standard PyQt6 application startup
    app = QApplication(sys.argv)
    ex = VideoProcessingApp()
    ex.show()
    sys.exit(app.exec())