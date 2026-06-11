import sys

from PyQt5.QtWidgets import QApplication

from main_dialog import MainDialog

app = QApplication(sys.argv)

window = MainDialog()
window.show()

sys.exit(app.exec_())