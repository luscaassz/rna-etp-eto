import os
import numpy as np
import rasterio

from rasterio.transform import from_origin

# TensorFlow / Keras
#from tensorflow.keras.models import load_model

# QGIS
#from qgis.core import QgsRasterLayer
#from qgis.core import QgsProject


# =========================================================
# LER RASTER
# =========================================================
def ler_raster(path, logger=None):

    if logger:
        logger(f"Lendo raster:")
        logger(path)

    dataset = rasterio.open(path)

    data = dataset.read()

    return dataset, data


# =========================================================
# PREPARAR ENTRADAS
# =========================================================
def preparar_entrada(
    landsat_data,
    mapbiomas_data,
    logger=None
):

    if logger:
        logger("Preparando entrada da RNA...")

    # =====================================================
    # EXEMPLO:
    # Landsat:
    # [bandas, linhas, colunas]
    #
    # Vamos pegar:
    # banda 1
    # banda 2
    # banda 3
    # banda 4
    #
    # + MapBiomas
    # =====================================================

    banda1 = landsat_data[0]
    banda2 = landsat_data[1]
    banda3 = landsat_data[2]
    banda4 = landsat_data[3]

    mapbiomas = mapbiomas_data[0]

    # =====================================================
    # STACK
    # =====================================================
    stack = np.stack([
        banda1,
        banda2,
        banda3,
        banda4,
        mapbiomas
    ], axis=-1)

    linhas, colunas, bandas = stack.shape

    # =====================================================
    # NORMALIZAÇÃO
    # =====================================================
    stack = stack.astype(np.float32)

    stack /= 10000.0

    # =====================================================
    # FORMATO DA RNA
    # =====================================================
    X = stack.reshape(
        linhas * colunas,
        bandas
    )

    if logger:
        logger(f"Entrada RNA:")
        logger(str(X.shape))

    return X, linhas, colunas


# =========================================================
# EXECUTAR INFERÊNCIA
# =========================================================
def inferencia(
    modelo,
    X,
    logger=None
):

    if logger:
        logger("Executando inferência...")

    y_pred = modelo.predict(
        X,
        verbose=0
    )

    if logger:
        logger("Inferência concluída.")

    return y_pred


# =========================================================
# SALVAR RASTER
# =========================================================
def salvar_raster(
    output_path,
    array,
    reference_dataset,
    logger=None
):

    if logger:
        logger("Salvando raster final...")

    profile = reference_dataset.profile

    profile.update(
        dtype=rasterio.float32,
        count=1,
        compress='lzw'
    )

    with rasterio.open(
        output_path,
        'w',
        **profile
    ) as dst:

        dst.write(
            array.astype(np.float32),
            1
        )

    if logger:
        logger("Raster salvo:")
        logger(output_path)


# =========================================================
# ADICIONAR NO QGIS
# =========================================================
'''def adicionar_no_qgis(
    raster_path,
    nome_layer,
    logger=None
):

    layer = QgsRasterLayer(
        raster_path,
        nome_layer
    )

    if not layer.isValid():

        raise ValueError(
            "Erro ao adicionar layer no QGIS."
        )

    QgsProject.instance().addMapLayer(
        layer
    )

    if logger:
        logger("Layer adicionada no QGIS.")'''


# =========================================================
# FUNÇÃO PRINCIPAL
# =========================================================
def executar_modelo(
    pasta_ano,
    ano,
    logger=None
):

    landsat_path = os.path.join(
        pasta_ano,
        "Landsat",
        f"landsat_{ano}.tif"
    )

    mapbiomas_path = os.path.join(
        pasta_ano,
        "Mapbiomas",
        f"mapbiomas_{ano}.tif"
    )

    output_dir = os.path.join(
        pasta_ano,
        "Resultado"
    )

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    output_raster = os.path.join(
        output_dir,
        f"etp_eto_{ano}.tif"
    )

    if not os.path.exists(landsat_path):
        raise ValueError(
            "Raster Landsat não encontrado."
        )

    if not os.path.exists(mapbiomas_path):
        raise ValueError(
            "Raster MapBiomas não encontrado."
        )

    # ======================================
    # LEITURA DOS RASTERS
    # ======================================

    landsat_ds, landsat_data = ler_raster(
        landsat_path,
        logger
    )

    mapbiomas_ds, mapbiomas_data = ler_raster(
        mapbiomas_path,
        logger
    )

    if logger:
        logger("Gerando raster de teste...")

    # ======================================
    # TESTE SIMPLES
    # ======================================

    banda1 = landsat_data[0].astype(np.float32)

    resultado = banda1 / 10000.0

    # ======================================
    # SALVAR
    # ======================================

    salvar_raster(
        output_raster,
        resultado,
        landsat_ds,
        logger
    )

    if logger:
        logger("Processamento finalizado.")

    return output_raster