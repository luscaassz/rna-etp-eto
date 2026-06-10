import os
import sys
import traceback
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QMessageBox,
)

import ee
import geemap
import geopandas as gpd
from shapely.geometry import mapping

# Import gerado pelo pyuic5 a partir do seu .ui
# Exemplo:
# pyuic5 seu_formulario.ui -o ui_mapbiomas.py
from ui_mapbiomas import Ui_MainWindow

class DownloadWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    state_signal = pyqtSignal(str)

    def __init__(self, shp_path, output_path, year=2024, product="cobertura_uso"):
        super().__init__()
        self.shp_path = shp_path
        self.output_path = output_path
        self.year = year
        self.product = product
        self._running = True
        self._progress = 0

    def update_progress(self, target):
        while self._progress < target and self._running:
            self._progress += 1
            self.progress_signal.emit(self._progress)
            self.msleep(20)  # suaviza animação

    def run(self):
        try:
            self.state_signal.emit("start")
            self.log_signal.emit("Inicializando Google Earth Engine...")
            self.initialize_ee()
            self.update_progress(20)

            self.log_signal.emit("Lendo shapefile...")
            gdf = gpd.read_file(self.shp_path)
            self.update_progress(40)

            if gdf.empty:
                raise ValueError("O shapefile está vazio.")

            if gdf.crs is None:
                raise ValueError("O shapefile não possui sistema de coordenadas (CRS).")

            # Reprojeta para WGS84, que é o mais seguro para Earth Engine
            gdf = gdf.to_crs(epsg=4326)

            # Une todas as geometrias em uma só
            geom = gdf.unary_union

            if geom.is_empty:
                raise ValueError("A geometria resultante do shapefile está vazia.")

            ee_geom = ee.Geometry(mapping(geom))

            self.log_signal.emit("Carregando imagem do MapBiomas...")
            image = self.get_mapbiomas_image(self.year, self.product)
            self.update_progress(60)

            self.log_signal.emit("Recortando imagem pela área do shapefile...")
            clipped = image.clip(ee_geom)
            self.update_progress(80)

            self.log_signal.emit("Exportando GeoTIFF local...")
            self.export_image(clipped, ee_geom, self.output_path)
            self.update_progress(100)


            self.state_signal.emit("end")
            self.finished_signal.emit(
                f"Download concluído com sucesso.\nArquivo salvo em:\n{self.output_path}"
            )

        except Exception as e:
            error_msg = f"{str(e)}\n\n{traceback.format_exc()}"
            self.error_signal.emit(error_msg)

    def initialize_ee(self):
        """
        Inicializa o Earth Engine.
        Se não estiver autenticado, tenta autenticar.
        """
        try:
            ee.Initialize(project="qgis-493503")
            self.log_signal.emit("Earth Engine inicializado com sucesso.")
        except Exception:
            self.log_signal.emit("Earth Engine não autenticado. Solicitando autenticação...")
            ee.Authenticate()
            ee.Initialize(project="qgis-493503")
            self.log_signal.emit("Earth Engine autenticado e inicializado com sucesso.")

    def get_mapbiomas_image(self, year, product):
        """
        Retorna uma imagem do MapBiomas conforme o produto selecionado.
        Ajuste aqui se quiser incluir outros assets.
        """
        if product == "cobertura_uso":
            # Asset oficial MapBiomas Brasil - Collection 10 Coverage v2
            asset_id = (
                "projects/mapbiomas-public/assets/brazil/lulc/collection10/"
                "mapbiomas_brazil_collection10_coverage_v2"
            )
            band_name = f"classification_{year}"
            image = ee.Image(asset_id).select(band_name)
            return image

        elif product == "desmatamento":
            asset_id = (
                "projects/mapbiomas-public/assets/brazil/lulc/collection10/"
                "mapbiomas_brazil_collection10_deforestation_secondary_vegetation_v2"
            )
            # Aqui você precisa confirmar a banda disponível no asset
            # Ajuste conforme seu uso real no GEE
            band_name = f"desmatamento_{year}"
            image = ee.Image(asset_id).select(band_name)
            return image

        elif product == "agua":
            asset_id = (
                "projects/mapbiomas-public/assets/brazil/water/collection3/"
                "mapbiomas_water_annual_water_coverage_v1"
            )
            band_name = f"classification_{year}"
            image = ee.Image(asset_id).select(band_name)
            return image

        else:
            raise ValueError(f"Produto não suportado: {product}")

    def export_image(self, image, region, output_path):
        """
        Exporta a imagem para GeoTIFF local.
        """
        output_dir = os.path.dirname(output_path)
        output_name = os.path.splitext(os.path.basename(output_path))[0]

        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # geemap cria o arquivo localmente
        geemap.ee_export_image(
            image,
            filename=output_path,
            scale=30,
            region=region,
            file_per_band=False,
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.worker = None

        self.connect_signals()
        self.configure_defaults()

        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f6f7;
            }

            QGroupBox {
                font-weight: bold;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                margin-top: 10px;
                padding: 5px;
                background-color: white;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }

            QPushButton {
                background-color: #2c7be5;
                color: white;
                border-radius: 5px;
                padding: 6px;
            }

            QPushButton:hover {
                background-color: #1a5fd1;
            }

            QPushButton:disabled {
                background-color: #9bbcf5;
            }

            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
            }

            QComboBox, QSpinBox {
                padding: 3px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }

            QProgressBar {
                border: 1px solid #bbb;
                border-radius: 4px;
                text-align: center;
                background-color: #eaeaea;
            }

            QProgressBar::chunk {
                background-color: #2c7be5;
            }

            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #dcdcdc;
                font-family: Consolas;
                border-radius: 4px;
            }
            """)

    def connect_signals(self):
        self.ui.pushButtonShape.clicked.connect(self.select_shapefile)
        self.ui.pushButtonOutput.clicked.connect(self.select_output_file)
        self.ui.pushButtonDownload.clicked.connect(self.start_download)

    def handle_state(self, state):
        if state == "start":
            self.ui.pushButtonDownload.setEnabled(False)

        elif state == "end":
            self.ui.pushButtonDownload.setEnabled(True)

    def configure_defaults(self):
        if hasattr(self.ui, "spinBoxYear"):
            self.ui.spinBoxYear.setMinimum(1985)
            self.ui.spinBoxYear.setMaximum(2024)
            self.ui.spinBoxYear.setValue(2024)

        if hasattr(self.ui, "comboBoxProduct"):
            self.ui.comboBoxProduct.clear()
            self.ui.comboBoxProduct.addItems([
                "cobertura_uso",
                "agua",
                # "desmatamento",  # habilite quando confirmar a banda do asset
            ])

    def log(self, message):
        if hasattr(self.ui, "plainTextEditLog"):
            self.ui.plainTextEditLog.appendPlainText(message)
        else:
            print(message)

    def set_progress(self, value):
        if hasattr(self.ui, "progressBarDownload"):
            self.ui.progressBarDownload.setValue(value)

    def select_shapefile(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar shapefile",
            "",
            "Shapefile (*.shp)"
        )
        if file_path:
            self.ui.lineEditShape.setText(file_path)
            self.log(f"Shapefile selecionado: {file_path}")

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar raster como",
            "mapbiomas_recorte.tif",
            "GeoTIFF (*.tif)"
        )
        if file_path:
            if not file_path.lower().endswith(".tif"):
                file_path += ".tif"
            self.ui.lineEditOutput.setText(file_path)
            self.log(f"Arquivo de saída: {file_path}")

    def validate_inputs(self):
        shp_path = self.ui.lineEditShape.text().strip()
        output_path = self.ui.lineEditOutput.text().strip()

        if not shp_path:
            raise ValueError("Selecione um arquivo shapefile.")
        if not os.path.exists(shp_path):
            raise ValueError("O shapefile selecionado não existe.")
        if not shp_path.lower().endswith(".shp"):
            raise ValueError("O arquivo selecionado não é um shapefile (.shp).")

        if not output_path:
            raise ValueError("Defina o local do arquivo de saída.")

        # Verifica se existem arquivos auxiliares básicos do shapefile
        base = os.path.splitext(shp_path)[0]
        required_ext = [".shx", ".dbf"]
        for ext in required_ext:
            aux = base + ext
            if not os.path.exists(aux):
                raise ValueError(
                    f"Arquivo auxiliar do shapefile não encontrado: {os.path.basename(aux)}"
                )

        return shp_path, output_path

    def start_download(self):
        try:
            shp_path, output_path = self.validate_inputs()

            year = 2024
            if hasattr(self.ui, "spinBoxYear"):
                year = int(self.ui.spinBoxYear.value())

            product = "cobertura_uso"
            if hasattr(self.ui, "comboBoxProduct"):
                product = self.ui.comboBoxProduct.currentText()

            self.ui.pushButtonDownload.setEnabled(False)
            self.log("Iniciando processo de download...")

            self.worker = DownloadWorker(
                shp_path=shp_path,
                output_path=output_path,
                year=year,
                product=product
            )
            self.worker.log_signal.connect(self.log)
            self.worker.finished_signal.connect(self.download_finished)
            self.worker.error_signal.connect(self.download_error)
            self.worker.progress_signal.connect(self.ui.progressBarDownload.setValue)
            self.worker.state_signal.connect(self.handle_state)
            self.worker.start()

        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))

    def download_finished(self, message):
        self.ui.pushButtonDownload.setEnabled(True)
        self.log("Processo finalizado.")
        QMessageBox.information(self, "Sucesso", message)

    def download_error(self, error_message):
        self.ui.pushButtonDownload.setEnabled(True)
        self.log("Erro no processo.")
        self.log(error_message)
        QMessageBox.critical(self, "Erro no download", error_message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
