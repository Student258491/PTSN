import sys
from PyQt6.QtWidgets import QApplication
from database import init_db
from gui import AppWindow


def main():
    # Initialize the database schema and establish persistence
    init_db()

    # Bootstrap the main application GUI
    app = QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()