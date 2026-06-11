import os

from PyQt5.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QVBoxLayout,
)

from ui.ui_rna_mpl import Ui_MainWindow

# Importa scripts do plugin
from coleta_gee import coletar_dados
from executar_modelo import executar_modelo


class MainDialog(QMainWindow):

    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.configure_ui()
        self.connect_signals()

        self.resize(500, 600)
        self.apply_style()

    # =========================================================
    # CONFIGURAÇÕES INICIAIS
    # =========================================================
    def configure_ui(self):

        # Coleta
        self.ui.spinBoxYearCollect.setValue(2024)
        
        # Execução
        self.ui.spinBoxYearRun.setValue(2024)

        self.ui.spinBoxCloud.setMinimum(0)
        self.ui.spinBoxCloud.setMaximum(100)
        self.ui.spinBoxCloud.setValue(20)

        self.ui.progressBarCollect.setValue(0)
        self.ui.progressBarRun.setValue(0)

        layout = QVBoxLayout(self.ui.centralwidget)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(self.ui.tabWidget)
        self.ui.tabWidget.setGeometry(0, 0, 0, 0)

        self.ui.pushButtonCollect.setEnabled(False)

        self.ui.pushButtonCollect.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: #BBBBBB;
                border-radius: 6px;
                padding: 6px;
            }
        """)

        self.update_collect_button()

        self.log("Plugin iniciado.")

    def apply_style(self):
        self.setStyleSheet("""

        QMainWindow {
            background-color: #1e1e2e;
        }

        QWidget {
            font-size: 10pt;
            color: white;
            font-family: Segoe UI;
        }

        QGroupBox {
            border: 2px solid #3b4261;
            border-radius: 12px;
            margin-top: 10px;
            padding-top: 15px;
            background-color: #25273a;
            font-weight: bold;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }

        QLineEdit {
            background-color: #31344a;
            border: 1px solid #4c566a;
            border-radius: 6px;
            padding: 6px;
        }

        QSpinBox {
            background-color: #31344a;
            border: 1px solid #4c566a;
            border-radius: 6px;
            padding: 4px;
        }

        QComboBox {
            background-color: #31344a;
            border: 1px solid #4c566a;
            border-radius: 6px;
            padding: 4px;
        }

        QPushButton {
            background-color: #4F46E5;
            border-radius: 8px;
            padding: 8px;
            color: white;
            font-weight: bold;
        }

        QPushButton:hover {
            background-color: #6366F1;
        }

        QPushButton:pressed {
            background-color: #4338CA;
        }

        QProgressBar {
            border: none;
            border-radius: 6px;
            text-align: center;
            background-color: #31344a;
        }

        QProgressBar::chunk {
            background-color: #22c55e;
            border-radius: 6px;
        }

        QPlainTextEdit {
            background-color: #111827;
            border: 1px solid #374151;
            border-radius: 8px;
            color: #10B981;
            font-family: Consolas;
        }

        QTabWidget::pane {
            border: 1px solid #374151;
            background: #25273a;
        }

        QTabBar::tab {
            background: #31344a;
            padding: 10px;
            min-width: 120px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }

        QTabBar::tab:selected {
            background: #4F46E5;
        }

        """)

    # =========================================================
    # CONEXÕES DOS BOTÕES
    # =========================================================
    def connect_signals(self):

        self.ui.pushButtonShape.clicked.connect(
            self.select_shapefile
        )

        self.ui.pushButtonOutputFolder.clicked.connect(
            self.select_output_folder
        )

        self.ui.pushButtonCollect.clicked.connect(
            self.collect_data
        )

        self.ui.pushButtonDataFolder.clicked.connect(
            self.select_data_folder
        )

        self.ui.pushButtonRunModel.clicked.connect(
            self.run_model
        )

    def update_collect_button(self):

        shp = self.ui.lineEditShape.text().strip()

        if (
            shp
            and os.path.exists(shp)
            and self.ui.lineEditOutputFolder.text().strip()
        ):

            self.ui.pushButtonCollect.setEnabled(True)

            self.ui.pushButtonCollect.setStyleSheet("""
                QPushButton {
                    background-color: #4F46E5;
                    color: white;
                    border-radius: 6px;
                    padding: 6px;
                    font-weight: bold;
                }

                QPushButton:hover {
                    background-color: #6366F1;
                }
            """)

        else:

            self.ui.pushButtonCollect.setEnabled(False)

            self.ui.pushButtonCollect.setStyleSheet("""
                QPushButton {
                    background-color: #555555;
                    color: #BBBBBB;
                    border-radius: 6px;
                    padding: 6px;
                }
            """)

    # =========================================================
    # LOG
    # =========================================================
    def log(self, message):

        self.ui.plainTextEditLog.appendPlainText(
            str(message)
        )
    
    def log_run(self, message):

        self.ui.plainTextEditRunLog.appendPlainText(
            str(message)
        )

    # =========================================================
    # SELECIONAR SHAPEFILE
    # =========================================================
    def select_shapefile(self):

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Shapefile",
            "",
            "Shapefile (*.shp)"
        )

        if file_path:

            self.ui.lineEditShape.setText(file_path)

            self.log(f"Shapefile selecionado:")
            self.log(file_path)

            self.update_collect_button()
            

    # =========================================================
    # SELECIONAR PASTA DE SAÍDA
    # =========================================================
    def select_output_folder(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta de saída"
        )

        if folder:

            self.ui.lineEditOutputFolder.setText(folder)

            self.log(f"Pasta de saída:")
            self.log(folder)

            self.update_collect_button()
    
    def select_data_folder(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta de dados"
        )

        if folder:

            self.ui.lineEditDataFolder.setText(folder)

            self.log_run("Pasta de dados:")
            self.log_run(folder)

    # =========================================================
    # VALIDAR ENTRADAS
    # =========================================================
    def validate_inputs(self):

        shp_path = self.ui.lineEditShape.text().strip()
        output_folder = self.ui.lineEditOutputFolder.text().strip()

        if not shp_path:
            raise ValueError(
                "Selecione um shapefile."
            )

        if not os.path.exists(shp_path):
            raise ValueError(
                "O shapefile não existe."
            )

        if not shp_path.lower().endswith(".shp"):
            raise ValueError(
                "Arquivo inválido."
            )

        base = os.path.splitext(shp_path)[0]

        required_files = [
            ".shx",
            ".dbf",
            ".prj",
        ]

        for ext in required_files:

            aux_file = base + ext

            if not os.path.exists(aux_file):

                raise ValueError(
                    f"Arquivo auxiliar não encontrado: {ext}"
                )

        if not output_folder:

            raise ValueError(
                "Selecione uma pasta de saída."
            )

        return shp_path, output_folder

    # =========================================================
    # COLETAR DADOS
    # =========================================================
    def collect_data(self):

        try:

            self.ui.progressBarCollect.setValue(0)

            shp_path, output_folder = self.validate_inputs()

            year = int(
                self.ui.spinBoxYearCollect.value()
            )

            cloud = int(
                self.ui.spinBoxCloud.value()
            )

            collection = (
                self.ui.comboBoxLandsat.currentText()
            )

            self.log("===================================")
            self.log("Iniciando coleta de dados...")
            self.log(f"Ano: {year}")
            self.log(f"Coleção: {collection}")
            self.log(f"Nuvem máxima: {cloud}%")

            self.ui.progressBarCollect.setValue(10)

            coletar_dados(
                shp_path=shp_path,
                output_folder=output_folder,
                year=year,
                collection=collection,
                cloud=cloud,
                logger=self.log,
            )

            self.ui.progressBarCollect.setValue(100)

            self.log("Coleta finalizada com sucesso.")

            QMessageBox.information(
                self,
                "Sucesso",
                "Coleta concluída."
            )

        except Exception as e:

            self.log("ERRO:")
            self.log(str(e))

            QMessageBox.critical(
                self,
                "Erro",
                str(e)
            )

    # =========================================================
    # EXECUTAR MODELO
    # =========================================================
    def run_model(self):

        try:

            self.ui.progressBarRun.setValue(0)

            data_folder = (
                self.ui.lineEditDataFolder.text().strip()
            )

            year = int(
                self.ui.spinBoxYearRun.value()
            )

            year_folder = os.path.join(
                data_folder,
                str(year)
            )

            if not os.path.exists(year_folder):

                raise ValueError(
                    "Pasta do ano não encontrada."
                )
            
            landsat = os.path.join(
                year_folder,
                "Landsat",
                f"landsat_{year}.tif"
            )

            mapbiomas = os.path.join(
                year_folder,
                "Mapbiomas",
                f"mapbiomas_{year}.tif"
            )

            if not os.path.exists(landsat):
                raise ValueError(
                    f"Landsat não encontrado:\n{landsat}"
                )

            if not os.path.exists(mapbiomas):
                raise ValueError(
                    f"MapBiomas não encontrado:\n{mapbiomas}"
                )

            self.log_run("===================================")
            self.log_run("Executando modelo RNA...")

            self.ui.progressBarRun.setValue(20)

            raster_output = executar_modelo(
                pasta_ano=year_folder,
                ano=year,
                logger=self.log_run,
            )

            self.ui.progressBarRun.setValue(100)

            self.log_run("Modelo executado com sucesso.")
            self.log_run("Raster gerado:")
            self.log_run(raster_output)

            QMessageBox.information(
                self,
                "Sucesso",
                "Inferência concluída."
            )

        except Exception as e:

            self.log_run("ERRO:")
            self.log_run(str(e))

            QMessageBox.critical(
                self,
                "Erro",
                str(e)
            )