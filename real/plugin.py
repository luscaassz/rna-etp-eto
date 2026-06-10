from qgis.PyQt.QtWidgets import QAction

from .main_dialog import MainDialog


class RNAPlugin:

    def __init__(self, iface):

        # Interface do QGIS
        self.iface = iface

        # Janela principal
        self.window = None

        # Ação do menu
        self.action = None

    # =========================================================
    # INICIALIZA GUI
    # =========================================================
    def initGui(self):

        self.action = QAction(
            "RNA ETP/ETO",
            self.iface.mainWindow()
        )

        self.action.triggered.connect(
            self.run
        )

        # Adiciona no menu Plugins
        self.iface.addPluginToMenu(
            "&RNA ETP/ETO",
            self.action
        )

        # Adiciona na toolbar
        self.iface.addToolBarIcon(
            self.action
        )

    # =========================================================
    # REMOVE PLUGIN
    # =========================================================
    def unload(self):

        self.iface.removePluginMenu(
            "&RNA ETP/ETO",
            self.action
        )

        self.iface.removeToolBarIcon(
            self.action
        )

    # =========================================================
    # ABRE JANELA
    # =========================================================
    def run(self):

        if self.window is None:

            self.window = MainDialog()

        self.window.show()

        self.window.raise_()

        self.window.activateWindow()