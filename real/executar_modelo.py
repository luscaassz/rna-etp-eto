import os
import json
import numpy as np
import rasterio
import joblib

from rasterio.warp import reproject, Resampling
from tensorflow.keras.models import load_model
import geopandas as gpd

from rasterio.mask import mask


NODATA_VALUE = -9999.0


# =========================================================
# LOG
# =========================================================
def log_message(logger, message):
    if logger:
        logger(str(message))


# =========================================================
# CAMINHOS DO MODELO
# =========================================================
def get_model_paths():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_dir = os.path.join(base_dir, "modelo")

    return {
        "model": os.path.join(model_dir, "modelo_etp.h5"),
        "scaler_x": os.path.join(model_dir, "scaler_X.pkl"),
        "scaler_y": os.path.join(model_dir, "scaler_y.pkl"),
        "features": os.path.join(model_dir, "feature_columns.json"),
    }


# =========================================================
# CARREGAR MODELO E METADADOS
# =========================================================
def carregar_modelo_e_scalers(logger=None):
    paths = get_model_paths()

    if not os.path.exists(paths["model"]):
        raise FileNotFoundError(
            f"Modelo não encontrado:\n{paths['model']}"
        )

    log_message(logger, "Carregando modelo RNA...")
    model = load_model(paths["model"])
    log_message(logger, "Modelo carregado.")

    scaler_x = None
    scaler_y = None
    feature_columns = None

    if os.path.exists(paths["scaler_x"]):
        scaler_x = joblib.load(paths["scaler_x"])
        log_message(logger, "scaler_X carregado.")
    else:
        log_message(logger, "Aviso: scaler_X.pkl não encontrado. A entrada não será padronizada.")

    if os.path.exists(paths["scaler_y"]):
        scaler_y = joblib.load(paths["scaler_y"])
        log_message(logger, "scaler_y carregado.")
    else:
        log_message(logger, "Aviso: scaler_y.pkl não encontrado. A saída não será desnormalizada.")

    if os.path.exists(paths["features"]):
        with open(paths["features"], "r", encoding="utf-8") as f:
            feature_columns = json.load(f)

        log_message(logger, f"feature_columns.json carregado com {len(feature_columns)} variáveis.")
    else:
        log_message(logger, "Aviso: feature_columns.json não encontrado. Usando entrada inferida.")

    return model, scaler_x, scaler_y, feature_columns


# =========================================================
# LER RASTER
# =========================================================
def ler_raster(path, logger=None):
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    log_message(logger, "Lendo raster:")
    log_message(logger, path)

    dataset = rasterio.open(path)
    data = dataset.read()

    log_message(logger, f"Shape lido: {data.shape}")

    return dataset, data

# =========================================================
# RECORTAR RASTER PELO SHAPEFILE
# =========================================================
def recortar_raster_por_aoi(
    input_raster,
    output_raster,
    aoi_path,
    logger=None
):

    if logger:
        logger("Recortando raster pela área de interesse...")

    if not os.path.exists(aoi_path):
        raise FileNotFoundError(
            f"Shapefile da AOI não encontrado:\n{aoi_path}"
        )

    with rasterio.open(input_raster) as src:

        gdf = gpd.read_file(aoi_path)

        if gdf.empty:
            raise ValueError(
                "Shapefile da AOI está vazio."
            )

        if gdf.crs is None:
            raise ValueError(
                "Shapefile da AOI não possui CRS."
            )

        gdf = gdf.to_crs(src.crs)

        geometrias = [
            geom
            for geom in gdf.geometry
            if geom is not None and not geom.is_empty
        ]

        if not geometrias:
            raise ValueError(
                "Nenhuma geometria válida encontrada na AOI."
            )

        out_image, out_transform = mask(
            src,
            geometrias,
            crop=True,
            nodata=-9999.0
        )

        out_meta = src.meta.copy()

        out_meta.update({
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
            "nodata": -9999.0,
            "compress": "lzw"
        })

    with rasterio.open(
        output_raster,
        "w",
        **out_meta
    ) as dst:

        dst.write(out_image)

    if logger:
        logger("Raster recortado salvo:")
        logger(output_raster)

# =========================================================
# REAMOSTRAR MAPBIOMAS PARA A GRADE DO LANDSAT
# =========================================================
def alinhar_mapbiomas(mapbiomas_ds, landsat_ds, logger=None):
    log_message(logger, "Alinhando MapBiomas à grade do Landsat...")

    destino = np.zeros(
        (landsat_ds.height, landsat_ds.width),
        dtype=np.float32
    )

    reproject(
        source=rasterio.band(mapbiomas_ds, 1),
        destination=destino,
        src_transform=mapbiomas_ds.transform,
        src_crs=mapbiomas_ds.crs,
        dst_transform=landsat_ds.transform,
        dst_crs=landsat_ds.crs,
        resampling=Resampling.nearest
    )

    return destino


# =========================================================
# COORDENADAS X/Y
# =========================================================
def gerar_coordenadas(ds):
    rows, cols = np.indices((ds.height, ds.width))

    xs, ys = rasterio.transform.xy(
        ds.transform,
        rows,
        cols,
        offset="center"
    )

    xs = np.array(xs, dtype=np.float32)
    ys = np.array(ys, dtype=np.float32)

    return xs, ys


# =========================================================
# CRIAR FEATURES
# =========================================================
def preparar_features(
    landsat_data,
    mapbiomas_array,
    landsat_ds,
    ano,
    model,
    feature_columns=None,
    logger=None
):
    log_message(logger, "Preparando entrada do modelo...")

    n_bands, height, width = landsat_data.shape

    # Landsat exportado pelo coleta_gee:
    # SR_B2, SR_B3, SR_B4, SR_B5, SR_B6, SR_B7
    band_map = {}

    if n_bands >= 1:
        band_map["b2"] = landsat_data[0].astype(np.float32)
    if n_bands >= 2:
        band_map["b3"] = landsat_data[1].astype(np.float32)
    if n_bands >= 3:
        band_map["b4"] = landsat_data[2].astype(np.float32)
    if n_bands >= 4:
        band_map["b5"] = landsat_data[3].astype(np.float32)
    if n_bands >= 5:
        band_map["b6"] = landsat_data[4].astype(np.float32)
    if n_bands >= 6:
        band_map["b7"] = landsat_data[5].astype(np.float32)

    # Normalização simples das bandas.
    # Mantenha isso igual ao treinamento.
    for key in band_map:
        band_map[key] = band_map[key] / 10000.0

    xs, ys = gerar_coordenadas(landsat_ds)

    base_features = {
        **band_map,
        "mapbiomas": mapbiomas_array.astype(np.float32),
        "Ano": np.full((height, width), float(ano), dtype=np.float32),
        "X": xs.astype(np.float32),
        "Y": ys.astype(np.float32),
    }

    # Caso o treinamento tenha usado "precip", mas você ainda não tenha raster de precipitação.
    # Isso permite testar, mas cientificamente o ideal é inserir a precipitação real.
    base_features["precip"] = np.zeros((height, width), dtype=np.float32)

    model_input_dim = int(model.input_shape[-1])

    if feature_columns is None:
        if model_input_dim == 5 and n_bands >= 4:
            feature_columns = ["b2", "b3", "b4", "b5", "mapbiomas"]
        elif model_input_dim == 7 and n_bands >= 6:
            feature_columns = ["b2", "b3", "b4", "b5", "b6", "b7", "mapbiomas"]
        elif model_input_dim == 10 and n_bands >= 6:
            feature_columns = ["b2", "b3", "b4", "b5", "b6", "b7", "precip", "Ano", "X", "Y"]
        else:
            raise ValueError(
                "Não foi possível inferir automaticamente as entradas do modelo.\n"
                f"O modelo espera {model_input_dim} variáveis, mas não existe feature_columns.json.\n"
                "Crie um arquivo modelo/feature_columns.json com a lista exata das colunas do treinamento."
            )

    if len(feature_columns) != model_input_dim:
        raise ValueError(
            "Número de variáveis incompatível com o modelo.\n"
            f"Modelo espera: {model_input_dim}\n"
            f"feature_columns.json possui: {len(feature_columns)}"
        )

    arrays = []

    for col in feature_columns:
        if col in base_features:
            arrays.append(base_features[col])

        elif col.startswith("uso_"):
            # Exemplo: uso_12 vira uma variável binária:
            # 1 quando MapBiomas == 12, senão 0.
            class_value = col.replace("uso_", "")

            try:
                class_value = int(class_value)
            except ValueError:
                raise ValueError(
                    f"Coluna de uso do solo inválida: {col}"
                )

            arrays.append(
                (mapbiomas_array == class_value).astype(np.float32)
            )

        else:
            raise ValueError(
                f"Variável exigida pelo modelo não encontrada: {col}"
            )

    stack = np.stack(arrays, axis=-1)

    X = stack.reshape(-1, len(feature_columns)).astype(np.float32)

    log_message(logger, f"Entrada preparada: {X.shape}")
    log_message(logger, f"Variáveis usadas: {feature_columns}")

    return X, height, width, feature_columns


# =========================================================
# EXECUTAR PREDIÇÃO
# =========================================================
def predizer(model, X, scaler_x=None, scaler_y=None, logger=None):
    log_message(logger, "Executando predição...")

    valid_mask = np.all(np.isfinite(X), axis=1)

    y = np.full((X.shape[0], 1), NODATA_VALUE, dtype=np.float32)

    X_valid = X[valid_mask]

    if X_valid.size == 0:
        raise ValueError("Nenhum pixel válido encontrado para inferência.")

    if scaler_x is not None:
        X_valid = scaler_x.transform(X_valid)

    y_valid = model.predict(
        X_valid,
        batch_size=8192,
        verbose=0
    )

    if scaler_y is not None:
        y_valid = scaler_y.inverse_transform(y_valid)

    y[valid_mask] = y_valid.astype(np.float32)

    log_message(logger, "Predição concluída.")

    return y


# =========================================================
# SALVAR RASTER
# =========================================================
def salvar_raster(output_path, array, reference_dataset, logger=None):
    log_message(logger, "Salvando raster final...")

    profile = reference_dataset.profile.copy()

    profile.update(
        dtype=rasterio.float32,
        count=1,
        nodata=NODATA_VALUE,
        compress="lzw"
    )

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(array.astype(np.float32), 1)

    log_message(logger, "Raster salvo:")
    log_message(logger, output_path)

def set_progress(progress, value):

    if progress:
        progress(value)

# =========================================================
# FUNÇÃO PRINCIPAL
# =========================================================
def executar_modelo(
    pasta_ano,
    ano,
    logger=None,
    progress=None
):
    
    set_progress(progress, 5)

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
    
    temp_raster = os.path.join(
        output_dir,
        f"temp_etp_eto_{ano}.tif"
    )

    aoi_path = os.path.join(
        pasta_ano,
        "AOI",
        "aoi.shp"
    )

    set_progress(progress, 10)

    if not os.path.exists(landsat_path):
        raise ValueError(
            "Raster Landsat não encontrado."
        )

    if not os.path.exists(mapbiomas_path):
        raise ValueError(
            "Raster MapBiomas não encontrado."
        )

    set_progress(progress, 20)

    landsat_ds, landsat_data = ler_raster(
        landsat_path,
        logger
    )

    set_progress(progress, 35)

    mapbiomas_ds, mapbiomas_data = ler_raster(
        mapbiomas_path,
        logger
    )

    logger("Gerando raster pela RNA...")
    set_progress(progress, 45)

    model, scaler_x, scaler_y, feature_columns = carregar_modelo_e_scalers(
        logger
    )

    set_progress(progress, 55)

    mapbiomas_alinhado = alinhar_mapbiomas(
        mapbiomas_ds,
        landsat_ds,
        logger
    )

    set_progress(progress, 65)

    X, height, width, _ = preparar_features(
        landsat_data=landsat_data,
        mapbiomas_array=mapbiomas_alinhado,
        landsat_ds=landsat_ds,
        ano=ano,
        model=model,
        feature_columns=feature_columns,
        logger=logger
    )

    set_progress(progress, 75)

    y = predizer(
        model=model,
        X=X,
        scaler_x=scaler_x,
        scaler_y=scaler_y,
        logger=logger
    )

    resultado = y.reshape(height, width)

    set_progress(progress, 85)

    salvar_raster(
        temp_raster,
        resultado,
        landsat_ds,
        logger
    )

    recortar_raster_por_aoi(
        input_raster=temp_raster,
        output_raster=output_raster,
        aoi_path=aoi_path,
        logger=logger
    )

    if os.path.exists(temp_raster):
        os.remove(temp_raster)

    set_progress(progress, 95)

    if logger:
        logger("Processamento finalizado.")

    set_progress(progress, 100)

    return output_raster