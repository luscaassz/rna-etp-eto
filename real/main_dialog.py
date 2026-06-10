import os

from PyQt5.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
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

    # =========================================================
    # CONFIGURAÇÕES INICIAIS
    # =========================================================
    def configure_ui(self):

        # Configuração do spinbox de ano
        self.ui.spinBoxYear.setMinimum(1985)
        self.ui.spinBoxYear.setMaximum(2025)
        self.ui.spinBoxYear.setValue(2024)

        # Percentual de nuvem
        self.ui.spinBoxCloud.setMinimum(0)
        self.ui.spinBoxCloud.setMaximum(100)
        self.ui.spinBoxCloud.setValue(20)

        # Coleções Landsat
        self.ui.comboBoxCollection.clear()
        self.ui.comboBoxCollection.addItems([
            "Landsat 5",
            "Landsat 7",
            "Landsat 8",
            "Landsat 9",
        ])

        # Progress bar
        self.ui.progressBar.setValue(0)

        # Log inicial
        self.log("Plugin iniciado.")

    # =========================================================
    # CONEXÕES DOS BOTÕES
    # =========================================================
    def connect_signals(self):

        self.ui.pushButtonShape.clicked.connect(
            self.select_shapefile
        )

        self.ui.pushButtonOutput.clicked.connect(
            self.select_output_folder
        )

        self.ui.pushButtonCollect.clicked.connect(
            self.collect_data
        )

        self.ui.pushButtonRun.clicked.connect(
            self.run_model
        )

    # =========================================================
    # LOG
    # =========================================================
    def log(self, message):

        self.ui.plainTextEditLog.appendPlainText(
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

    # =========================================================
    # SELECIONAR PASTA DE SAÍDA
    # =========================================================
    def select_output_folder(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta de saída"
        )

        if folder:

            self.ui.lineEditOutput.setText(folder)

            self.log(f"Pasta de saída:")
            self.log(folder)

    # =========================================================
    # VALIDAR ENTRADAS
    # =========================================================
    def validate_inputs(self):

        shp_path = self.ui.lineEditShape.text().strip()
        output_folder = self.ui.lineEditOutput.text().strip()

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

            self.ui.progressBar.setValue(0)

            shp_path, output_folder = self.validate_inputs()

            year = int(
                self.ui.spinBoxYear.value()
            )

            cloud = int(
                self.ui.spinBoxCloud.value()
            )

            collection = (
                self.ui.comboBoxCollection.currentText()
            )

            self.log("===================================")
            self.log("Iniciando coleta de dados...")
            self.log(f"Ano: {year}")
            self.log(f"Coleção: {collection}")
            self.log(f"Nuvem máxima: {cloud}%")

            self.ui.progressBar.setValue(10)

            coletar_dados(
                shp_path=shp_path,
                output_folder=output_folder,
                year=year,
                collection=collection,
                cloud=cloud,
                logger=self.log,
            )

            self.ui.progressBar.setValue(100)

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

            self.ui.progressBar.setValue(0)

            output_folder = (
                self.ui.lineEditOutput.text().strip()
            )

            year = int(
                self.ui.spinBoxYear.value()
            )

            year_folder = os.path.join(
                output_folder,
                str(year)
            )

            if not os.path.exists(year_folder):

                raise ValueError(
                    "Pasta do ano não encontrada."
                )

            self.log("===================================")
            self.log("Executando modelo RNA...")

            self.ui.progressBar.setValue(20)

            raster_output = executar_modelo(
                pasta_ano=year_folder,
                ano=year,
                logger=self.log,
            )

            self.ui.progressBar.setValue(100)

            self.log("Modelo executado com sucesso.")
            self.log(f"Raster gerado:")
            self.log(raster_output)

            QMessageBox.information(
                self,
                "Sucesso",
                "Inferência concluída."
            )

        except Exception as e:

            self.log("ERRO:")
            self.log(str(e))

            QMessageBox.critical(
                self,
                "Erro",
                str(e)
            )