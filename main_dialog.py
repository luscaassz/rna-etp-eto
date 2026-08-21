import os

try:
    from qgis.PyQt.QtCore import QSettings, Qt
    from qgis.PyQt.QtGui import QBrush, QColor
    from qgis.PyQt.QtWidgets import (
        QMainWindow,
        QFileDialog,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QStyledItemDelegate,
        QStyle,
        QVBoxLayout,
        QApplication,
    )
except ImportError:
    from PyQt5.QtCore import QSettings, Qt
    from PyQt5.QtGui import QBrush, QColor
    from PyQt5.QtWidgets import (
        QMainWindow,
        QFileDialog,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QStyledItemDelegate,
        QStyle,
        QVBoxLayout,
        QApplication,
    )

try:
    from qgis.core import QgsProject, QgsRasterLayer
except ImportError:
    QgsProject = None
    QgsRasterLayer = None

try:
    from .ui.ui_rna_mpl import Ui_MainWindow
except ImportError:
    from ui.ui_rna_mpl import Ui_MainWindow


MESSAGE_BOX_STYLE = """
QMessageBox {
    background-color: #ffffff;
}

QMessageBox QLabel {
    color: #111827;
    font-size: 10pt;
    font-family: Segoe UI;
}

QMessageBox QPushButton {
    background-color: #4F46E5;
    color: #ffffff;
    border-radius: 6px;
    padding: 6px 14px;
    min-width: 72px;
    font-weight: bold;
}

QMessageBox QPushButton:hover {
    background-color: #6366F1;
}
"""


def import_coletar_dados():
    if __package__:
        from .coleta_gee import coletar_dados
    else:
        from coleta_gee import coletar_dados

    return coletar_dados


def import_executar_modelo():
    if __package__:
        from .executar_modelo import executar_modelo
    else:
        from executar_modelo import executar_modelo

    return executar_modelo


def import_ee():
    import ee

    return ee


class ComboItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        text = str(index.data(Qt.DisplayRole) or "")
        is_selected = bool(option.state & QStyle.State_Selected)
        is_hovered = bool(option.state & QStyle.State_MouseOver)

        if is_selected:
            background = QColor("#31344a")
            foreground = QColor("#ffffff")
        elif is_hovered:
            background = QColor("#E0E7FF")
            foreground = QColor("#111827")
        else:
            background = QColor("#ffffff")
            foreground = QColor("#111827")

        painter.save()
        painter.fillRect(option.rect, background)
        painter.setPen(foreground)
        text_rect = option.rect.adjusted(8, 0, -8, 0)
        painter.drawText(
            text_rect,
            Qt.AlignVCenter | Qt.AlignLeft,
            text,
        )
        painter.restore()


class MainDialog(QMainWindow):

    def __init__(self, iface=None):
        super().__init__()

        self.iface = iface
        self.settings = QSettings("RNA_ETP_ETO", "QGISPlugin")
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

        self.configure_earth_engine_ui()

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

        self.update_landsat_options()
        self.update_collect_button()

        self.log("Plugin iniciado.")

    def style_landsat_combo(self):
        combo = self.ui.comboBoxLandsat
        combo.setItemDelegate(ComboItemDelegate(combo))

        combo.setStyleSheet("""
            QComboBox {
                background-color: #31344a;
                color: #ffffff;
                border: 1px solid #4c566a;
                border-radius: 6px;
                padding: 4px;
            }

            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #111827;
                selection-background-color: #31344a;
                selection-color: #ffffff;
                outline: 0;
            }
        """)

        combo.view().setStyleSheet("""
            QListView {
                background-color: #ffffff;
                color: #111827;
                border: 1px solid #4c566a;
                outline: 0;
            }

            QListView::item {
                background-color: #ffffff;
                color: #111827;
                min-height: 24px;
                padding: 4px 8px;
            }

            QListView::item:hover {
                background-color: #E0E7FF;
                color: #111827;
            }

            QListView::item:selected {
                background-color: #31344a;
                color: #ffffff;
            }
        """)

        for index in range(combo.count()):
            combo.setItemData(
                index,
                QBrush(QColor("#111827")),
                Qt.ForegroundRole,
            )
            combo.setItemData(
                index,
                QBrush(QColor("#ffffff")),
                Qt.BackgroundRole,
            )

    def configure_earth_engine_ui(self):
        self.ui.labelEeProject = QLabel(self.ui.groupBox)
        self.ui.labelEeProject.setText("Projeto Earth Engine:")
        self.ui.labelEeProject.setObjectName("labelEeProject")

        self.ui.lineEditEeProject = QLineEdit(self.ui.groupBox)
        self.ui.lineEditEeProject.setObjectName("lineEditEeProject")
        self.ui.lineEditEeProject.setPlaceholderText(
            "Ex.: abcd-123456"
        )
        self.ui.lineEditEeProject.setText(
            self.settings.value(
                "earth_engine/project_id",
                "",
                type=str,
            )
        )

        self.ui.pushButtonAuthenticateEe = QPushButton(self.ui.groupBox)
        self.ui.pushButtonAuthenticateEe.setObjectName(
            "pushButtonAuthenticateEe"
        )
        self.ui.pushButtonAuthenticateEe.setText(
            "Autenticar Earth Engine"
        )

        self.ui.gridLayout.addWidget(
            self.ui.labelEeProject,
            5,
            0,
            1,
            1,
        )
        self.ui.gridLayout.addWidget(
            self.ui.lineEditEeProject,
            5,
            1,
            1,
            2,
        )
        self.ui.gridLayout.addWidget(
            self.ui.pushButtonAuthenticateEe,
            5,
            3,
            1,
            1,
        )
        self.ui.gridLayout.addWidget(
            self.ui.pushButtonCollect,
            6,
            1,
            1,
            2,
        )
        self.ui.gridLayout.addWidget(
            self.ui.progressBarCollect,
            7,
            0,
            1,
            4,
        )
        self.ui.gridLayout.addWidget(
            self.ui.plainTextEditLog,
            8,
            0,
            1,
            4,
        )

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
            color: white;
            border: 1px solid #4c566a;
            border-radius: 6px;
            padding: 4px;
        }

        QComboBox QAbstractItemView {
            background-color: #ffffff;
            color: #111827;
            selection-background-color: #4F46E5;
            selection-color: #ffffff;
            border: 1px solid #4c566a;
        }

        QComboBox QAbstractItemView::item {
            background-color: #ffffff;
            color: #111827;
            min-height: 24px;
            padding: 4px 8px;
        }

        QComboBox QAbstractItemView::item:hover {
            background-color: #E0E7FF;
            color: #111827;
        }

        QComboBox QAbstractItemView::item:selected {
            background-color: #4F46E5;
            color: #ffffff;
        }

        QListView {
            background-color: #ffffff;
            color: #111827;
            selection-background-color: #4F46E5;
            selection-color: #ffffff;
        }

        QListView::item {
            background-color: #ffffff;
            color: #111827;
            min-height: 24px;
            padding: 4px 8px;
        }

        QListView::item:hover {
            background-color: #E0E7FF;
            color: #111827;
        }

        QListView::item:selected {
            background-color: #4F46E5;
            color: #ffffff;
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

        QMessageBox {
            background-color: #ffffff;
        }

        QMessageBox QLabel {
            color: #111827;
        }

        QMessageBox QPushButton {
            background-color: #4F46E5;
            color: #ffffff;
            border-radius: 6px;
            padding: 6px 14px;
            min-width: 72px;
        }

        """)

    def show_message(self, icon, title, message):
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(str(message))
        box.setStyleSheet(MESSAGE_BOX_STYLE)
        box.exec_()

    def show_success(self, message):
        self.show_message(
            QMessageBox.Information,
            "Sucesso",
            message,
        )

    def show_error(self, message):
        self.show_message(
            QMessageBox.Critical,
            "Erro",
            message,
        )

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

        self.ui.pushButtonAuthenticateEe.clicked.connect(
            self.authenticate_earth_engine
        )

        self.ui.lineEditEeProject.editingFinished.connect(
            self.save_ee_project
        )

        self.ui.pushButtonDataFolder.clicked.connect(
            self.select_data_folder
        )

        self.ui.pushButtonRunModel.clicked.connect(
            self.run_model
        )

        self.ui.spinBoxYearCollect.valueChanged.connect(
            self.update_landsat_options
        )

    # =========================================================
    # DISPONIBILIDADE LANDSAT POR ANO
    # =========================================================
    def get_available_landsat_collections(self, year):

        available = []

        # Landsat 5: operação aproximada até 2012/2013
        if 1985 <= year <= 2012:
            available.append("Landsat 5")

        # Landsat 7: disponível a partir de 1999
        if year >= 1999:
            available.append("Landsat 7")

        # Landsat 8: disponível a partir de 2013
        if year >= 2013:
            available.append("Landsat 8")

        # Landsat 9: disponível a partir de 2021
        if year >= 2021:
            available.append("Landsat 9")

        return available


    def update_landsat_options(self):

        year = int(
            self.ui.spinBoxYearCollect.value()
        )

        current_collection = (
            self.ui.comboBoxLandsat.currentText()
        )

        available = self.get_available_landsat_collections(
            year
        )

        self.ui.comboBoxLandsat.blockSignals(True)

        self.ui.comboBoxLandsat.clear()

        self.ui.comboBoxLandsat.addItems(
            available
        )

        if current_collection in available:

            index = self.ui.comboBoxLandsat.findText(
                current_collection
            )

            self.ui.comboBoxLandsat.setCurrentIndex(
                index
            )

        elif available:

            self.ui.comboBoxLandsat.setCurrentIndex(0)

        self.ui.comboBoxLandsat.blockSignals(False)

        self.style_landsat_combo()
        self.update_collect_button()

    def update_collect_button(self):

        shp = self.ui.lineEditShape.text().strip()

        if (
            shp
            and os.path.exists(shp)
            and self.ui.lineEditOutputFolder.text().strip()
            and self.ui.comboBoxLandsat.count() > 0
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

    def get_ee_project(self):
        project = self.ui.lineEditEeProject.text().strip()

        if project:
            return project

        for env_var in [
            "EARTHENGINE_PROJECT",
            "GOOGLE_CLOUD_PROJECT",
            "EE_PROJECT",
        ]:
            value = os.environ.get(env_var)
            if value:
                value = value.strip()
                if value:
                    return value

        return ""

    def save_ee_project(self):
        project = self.ui.lineEditEeProject.text().strip()
        self.settings.setValue(
            "earth_engine/project_id",
            project,
        )

    def authenticate_earth_engine(self):
        try:
            project = self.get_ee_project()

            if not project:
                raise ValueError(
                    "Informe o Project ID do Google Cloud/Earth Engine."
                )

            self.ui.lineEditEeProject.setText(project)
            self.save_ee_project()

            self.log("===================================")
            self.log("Autenticando Earth Engine...")
            self.log(f"Projeto: {project}")

            QApplication.processEvents()

            ee = import_ee()
            ee.Authenticate(auth_mode="localhost")
            ee.Initialize(project=project)

            self.log("Earth Engine autenticado com sucesso.")
            self.show_success(
                "Earth Engine autenticado com sucesso."
            )

        except Exception as e:
            self.log("ERRO NA AUTENTICACAO:")
            self.log(str(e))
            self.show_error(str(e))

    def add_raster_to_qgis_canvas(self, raster_path, layer_name):
        if self.iface is None:
            return

        if QgsProject is None or QgsRasterLayer is None:
            raise RuntimeError(
                "PyQGIS nao esta disponivel para carregar o raster no QGIS."
            )

        layer = QgsRasterLayer(
            raster_path,
            layer_name,
        )

        if not layer.isValid():
            raise RuntimeError(
                "Raster gerado, mas nao foi possivel carregar no QGIS:\n"
                f"{raster_path}"
            )

        QgsProject.instance().addMapLayer(layer)

        self.log_run("Raster adicionado ao QGIS:")
        self.log_run(raster_path)

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

            ee_project = self.get_ee_project()

            if ee_project:
                self.ui.lineEditEeProject.setText(ee_project)
                self.save_ee_project()

            self.log("===================================")
            self.log("Iniciando coleta de dados...")
            self.log(f"Ano: {year}")
            self.log(f"Coleção: {collection}")
            self.log(f"Nuvem máxima: {cloud}%")

            if ee_project:
                self.log(f"Projeto Earth Engine: {ee_project}")

            self.update_collect_progress(5)

            coletar_dados = import_coletar_dados()

            coletar_dados(
                shp_path=shp_path,
                output_folder=output_folder,
                year=year,
                collection=collection,
                cloud=cloud,
                logger=self.log,
                progress=self.update_collect_progress,
                ee_project=ee_project or None,
            )

            self.update_collect_progress(100)

            self.log("Coleta finalizada com sucesso.")
            self.show_success("Coleta concluida.")
            return

            QMessageBox.information(
                self,
                "Sucesso",
                "Coleta concluída."
            )

        except Exception as e:

            self.log("ERRO:")
            self.log(str(e))
            self.show_error(str(e))
            return

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

            self.update_run_progress(5)

            executar_modelo = import_executar_modelo()

            raster_output = executar_modelo(
                pasta_ano=year_folder,
                ano=year,
                logger=self.log_run,
                progress=self.update_run_progress,
            )

            self.update_run_progress(100)

            self.log_run("Modelo executado com sucesso.")
            self.log_run("Raster gerado:")
            self.log_run(raster_output)

            self.add_raster_to_qgis_canvas(
                raster_path=raster_output,
                layer_name=f"ETP/ETO {year}",
            )

            self.show_success("Inferencia concluida.")
            return

            QMessageBox.information(
                self,
                "Sucesso",
                "Inferência concluída."
            )

        except Exception as e:

            self.log_run("ERRO:")
            self.log_run(str(e))
            self.show_error(str(e))
            return

            QMessageBox.critical(
                self,
                "Erro",
                str(e)
            )
    
    # =========================================================
    # PROGRESSO
    # =========================================================
    def update_collect_progress(self, value):

        self.ui.progressBarCollect.setValue(value)
        QApplication.processEvents()


    def update_run_progress(self, value):

        self.ui.progressBarRun.setValue(value)
        QApplication.processEvents()
