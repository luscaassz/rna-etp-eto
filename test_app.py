import os
import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

from main_dialog import MainDialog


def main():
    app = QApplication(sys.argv)
    window = MainDialog()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
