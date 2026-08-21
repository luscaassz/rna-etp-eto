from qgis.PyQt.QtWidgets import QAction

from .main_dialog import MainDialog


class RnaEtpPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None
        self.menu_name = "RNA ETP/ETO"

    def initGui(self):
        self.action = QAction("RNA ETP/ETO", self.iface.mainWindow())
        self.action.setObjectName("rnaEtpEtoAction")
        self.action.triggered.connect(self.run)

        self.iface.addPluginToMenu(self.menu_name, self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removePluginMenu(self.menu_name, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

        self.dialog = None

    def run(self):
        if self.dialog is None:
            self.dialog = MainDialog(iface=self.iface)

        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
