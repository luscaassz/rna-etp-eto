import csv
import json
import os

import geopandas as gpd
import joblib
import numpy as np
import rasterio

from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.warp import (
    calculate_default_transform,
    reproject,
    Resampling,
)
from tensorflow.keras.models import load_model


NODATA_VALUE = -9999.0

# Escalas oficiais do Landsat Collection 2 Level-2.
SR_SCALE = 0.0000275
SR_OFFSET = -0.2

ST_SCALE = 0.00341802
ST_OFFSET = 149.0

LANDSAT_MODEL_BANDS = ["b2", "b3", "b4", "b5", "b6", "b7"]

# Valores médios anuais aproximados observados no dataset original.
# Use isto apenas como fallback. Para resultado científico, passe precipitação real.
PRECIP_ANUAL_REFERENCIA = {
    1986: 1576.9680,
    1994: 1482.2783,
    2001: 1290.4790,
    2007: 1168.7373,
    2014: 1046.8929,
    2021: 905.3584,
    2024: 1373.9116,
}


# =========================================================
# LOG E PROGRESSO
# =========================================================
def log_message(logger, message):
    if logger:
        logger(str(message))


def set_progress(progress, value):
    if progress:
        progress(int(value))


# =========================================================
# CAMINHOS DO MODELO
# =========================================================
def get_model_paths():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_dir = os.path.join(base_dir, "modelo")

    return {
        "model_dir": model_dir,
        "model": os.path.join(model_dir, "modelo_etp.h5"),
        "scaler_x": os.path.join(model_dir, "scaler_X.pkl"),
        "scaler_y": os.path.join(model_dir, "scaler_y.pkl"),
        "features_json": os.path.join(model_dir, "feature_columns.json"),
        "features_csv": os.path.join(model_dir, "features_modelo.csv"),
    }


def carregar_feature_columns(paths):
    if os.path.exists(paths["features_json"]):
        with open(paths["features_json"], "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError(
                "feature_columns.json deve conter uma lista de nomes de features."
            )

        return [str(x) for x in data]

    if os.path.exists(paths["features_csv"]):
        with open(paths["features_csv"], "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if "feature" not in reader.fieldnames:
                raise ValueError(
                    "features_modelo.csv precisa ter uma coluna chamada 'feature'."
                )
            return [str(row["feature"]) for row in reader]

    raise FileNotFoundError(
        "Arquivo de features não encontrado.\n"
        "Coloque um destes arquivos na pasta modelo:\n"
        f"- {paths['features_json']}\n"
        f"- {paths['features_csv']}"
    )


# =========================================================
# CARREGAR MODELO E METADADOS
# =========================================================
def carregar_modelo_e_scalers(logger=None):
    paths = get_model_paths()

    missing = []
    for key in ["model", "scaler_x", "scaler_y"]:
        if not os.path.exists(paths[key]):
            missing.append(paths[key])

    if missing:
        raise FileNotFoundError(
            "Arquivos obrigatórios do modelo não encontrados:\n"
            + "\n".join(missing)
        )

    log_message(logger, "Carregando modelo RNA...")
    model = load_model(paths["model"], compile=False)
    log_message(logger, "Modelo carregado.")

    scaler_x = joblib.load(paths["scaler_x"])
    log_message(logger, "scaler_X carregado.")

    scaler_y = joblib.load(paths["scaler_y"])
    log_message(logger, "scaler_y carregado.")

    feature_columns = carregar_feature_columns(paths)
    log_message(
        logger,
        f"Features carregadas com {len(feature_columns)} variáveis.",
    )

    model_input_dim = int(model.input_shape[-1])
    if len(feature_columns) != model_input_dim:
        raise ValueError(
            "Incompatibilidade entre modelo e features.\n"
            f"Modelo espera {model_input_dim} variáveis.\n"
            f"Arquivo de features possui {len(feature_columns)} variáveis."
        )

    if hasattr(scaler_x, "mean_") and len(scaler_x.mean_) != len(feature_columns):
        raise ValueError(
            "Incompatibilidade entre scaler_X e features.\n"
            f"scaler_X espera {len(scaler_x.mean_)} variáveis.\n"
            f"Arquivo de features possui {len(feature_columns)} variáveis."
        )

    return model, scaler_x, scaler_y, feature_columns


# =========================================================
# PRECIPITAÇÃO
# =========================================================
def obter_precipitacao_anual(ano, precip=None, logger=None):
    """
    Retorna a precipitação anual a ser usada no modelo.

    Se precip for informado, usa esse valor.
    Se não for informado, usa média/interpolação baseada nos anos do treinamento.
    """

    if precip is not None:
        valor = float(precip)
        log_message(logger, f"Precipitação informada pelo usuário: {valor:.2f} mm")
        return valor

    if ano in PRECIP_ANUAL_REFERENCIA:
        valor = float(PRECIP_ANUAL_REFERENCIA[ano])
        log_message(
            logger,
            f"Precipitação fallback para {ano}: {valor:.2f} mm",
        )
        return valor

    anos = np.array(sorted(PRECIP_ANUAL_REFERENCIA.keys()), dtype=np.float32)
    valores = np.array(
        [PRECIP_ANUAL_REFERENCIA[int(a)] for a in anos],
        dtype=np.float32,
    )

    valor = float(np.interp(float(ano), anos, valores))

    log_message(
        logger,
        f"Aviso: precipitação real de {ano} não foi informada. "
        f"Usando valor interpolado: {valor:.2f} mm",
    )

    return valor


# =========================================================
# CRS / REPROJEÇÃO
# =========================================================
def estimar_crs_utm_por_aoi(aoi_path, logger=None):
    """
    Estima um CRS UTM adequado pela posição do centroide da AOI.

    Para áreas do Brasil no hemisfério sul, usa SIRGAS 2000 / UTM:
        EPSG = 31960 + zona
    Exemplo:
        Zona 23S -> EPSG:31983

    Para outras regiões, usa WGS84 / UTM:
        hemisfério norte -> EPSG:326xx
        hemisfério sul   -> EPSG:327xx
    """

    if not os.path.exists(aoi_path):
        raise FileNotFoundError(
            f"Shapefile da AOI não encontrado:\n{aoi_path}"
        )

    gdf = gpd.read_file(aoi_path)

    if gdf.empty:
        raise ValueError("AOI vazia.")

    if gdf.crs is None:
        raise ValueError("AOI sem CRS definido.")

    gdf_4326 = gdf.to_crs("EPSG:4326")
    geom = gdf_4326.union_all()
    centroid = geom.centroid

    lon = float(centroid.x)
    lat = float(centroid.y)

    zone = int((lon + 180.0) / 6.0) + 1

    # Brasil em geral fica entre as zonas 18 e 25.
    # No hemisfério sul, SIRGAS 2000 / UTM zona 23S = EPSG:31983.
    is_brazil_like = (-75.0 <= lon <= -30.0) and (-35.0 <= lat <= 6.0)

    if is_brazil_like and lat < 0 and 18 <= zone <= 25:
        epsg = 31960 + zone
    else:
        if lat < 0:
            epsg = 32700 + zone
        else:
            epsg = 32600 + zone

    target_crs = f"EPSG:{epsg}"

    log_message(logger, "CRS UTM estimado automaticamente:")
    log_message(logger, f"  Longitude centroide: {lon:.6f}")
    log_message(logger, f"  Latitude centroide: {lat:.6f}")
    log_message(logger, f"  Zona UTM: {zone}")
    log_message(logger, f"  CRS usado para X/Y: {target_crs}")

    return target_crs


def reprojetar_dataset_para_crs(
    src_ds,
    target_crs,
    resampling=Resampling.bilinear,
    resolucao=30,
    logger=None,
):
    if src_ds.crs is None:
        raise ValueError("Raster sem CRS. Não é possível reprojetar.")

    if str(src_ds.crs).upper() == str(target_crs).upper():
        log_message(logger, f"Raster já está em {target_crs}.")
        return None, src_ds

    log_message(
        logger,
        f"Reprojetando raster de {src_ds.crs} para {target_crs}...",
    )

    transform, width, height = calculate_default_transform(
        src_ds.crs,
        target_crs,
        src_ds.width,
        src_ds.height,
        *src_ds.bounds,
        resolution=resolucao,
    )

    src_nodata = src_ds.nodata
    if src_nodata is None:
        src_nodata = NODATA_VALUE

    profile = src_ds.profile.copy()
    profile.update({
        "driver": "GTiff",
        "crs": target_crs,
        "transform": transform,
        "width": width,
        "height": height,
        "nodata": src_nodata,
    })

    memfile = MemoryFile()
    dst_ds = memfile.open(**profile)

    for band_idx in range(1, src_ds.count + 1):
        reproject(
            source=rasterio.band(src_ds, band_idx),
            destination=rasterio.band(dst_ds, band_idx),
            src_transform=src_ds.transform,
            src_crs=src_ds.crs,
            dst_transform=transform,
            dst_crs=target_crs,
            resampling=resampling,
            src_nodata=src_nodata,
            dst_nodata=src_nodata,
        )

    log_message(logger, f"Raster reprojetado: {height} x {width}")

    return memfile, dst_ds


def preencher_outliers_por_mediana(
    array,
    invalid_mask,
    max_iter=5,
    logger=None
):
    """
    Preenche pixels inválidos usando a mediana dos vizinhos 3x3.

    Corrige outliers locais sem usar outros pixels inválidos como vizinhos.
    """

    arr = array.astype(np.float32).copy()
    invalid_mask = invalid_mask.copy()

    for iteration in range(max_iter):

        current_invalid = invalid_mask.copy()

        if not np.any(current_invalid):
            break

        arr_novo = arr.copy()
        preenchidos_coords = []

        linhas, colunas = np.where(current_invalid)

        for r, c in zip(linhas, colunas):

            r0 = max(0, r - 1)
            r1 = min(arr.shape[0], r + 2)
            c0 = max(0, c - 1)
            c1 = min(arr.shape[1], c + 2)

            janela = arr[r0:r1, c0:c1]
            janela_invalidos = current_invalid[r0:r1, c0:c1]

            valores_validos = janela[
                np.isfinite(janela)
                & (janela != NODATA_VALUE)
                & (~janela_invalidos)
                & (janela >= 0.0)
            ]

            if valores_validos.size > 0:
                arr_novo[r, c] = np.median(valores_validos)
                preenchidos_coords.append((r, c))

        arr = arr_novo

        for r, c in preenchidos_coords:
            invalid_mask[r, c] = False

        if logger:
            logger(
                f"Preenchimento por mediana - iteração {iteration + 1}: "
                f"{len(preenchidos_coords)} pixels corrigidos."
            )

        if len(preenchidos_coords) == 0:
            break

    arr[invalid_mask] = NODATA_VALUE

    return arr


def corrigir_predicao_fisica_et(
    array,
    et_min=0.0,
    et_max=1600.0,
    preencher=True,
    logger=None
):
    """
    Corrige valores fisicamente incoerentes da predição de ET.

    - Valores negativos são inválidos.
    - Valores acima de et_max são tratados como outliers.
    - Opcionalmente preenche pequenos buracos pela mediana dos vizinhos.
    """

    arr = array.astype(np.float32).copy()

    mascara_valida = (
        np.isfinite(arr)
        & (arr != NODATA_VALUE)
    )

    mascara_incoerente = (
        mascara_valida
        & (
            (arr < et_min)
            | (arr > et_max)
        )
    )

    total_validos = int(np.sum(mascara_valida))
    total_incoerentes = int(np.sum(mascara_incoerente))

    if logger:
        perc = (
            total_incoerentes / total_validos * 100.0
            if total_validos > 0
            else 0.0
        )

        logger("Correção física da predição:")
        logger(f"  ET mínimo permitido: {et_min:.2f}")
        logger(f"  ET máximo permitido: {et_max:.2f}")
        logger(f"  Pixels válidos antes: {total_validos:,}")
        logger(
            f"  Pixels incoerentes encontrados: "
            f"{total_incoerentes:,} ({perc:.4f}%)"
        )

    if total_incoerentes == 0:
        return arr

    if preencher:
        arr = preencher_outliers_por_mediana(
            array=arr,
            invalid_mask=mascara_incoerente.copy(),
            max_iter=5,
            logger=logger
        )
    else:
        arr[mascara_incoerente] = NODATA_VALUE

    negativos_restantes = (
        np.isfinite(arr)
        & (arr != NODATA_VALUE)
        & (arr < et_min)
    )

    if np.any(negativos_restantes):
        qtd = int(np.sum(negativos_restantes))

        if logger:
            logger(
                f"Aviso: ainda restaram {qtd} pixels abaixo do limite. "
                "Convertendo para NoData."
            )

        arr[negativos_restantes] = NODATA_VALUE

    validos_depois = arr[
        np.isfinite(arr)
        & (arr != NODATA_VALUE)
    ]

    if logger and validos_depois.size > 0:
        logger(
            "  Após correção: "
            f"min={np.min(validos_depois):.2f}, "
            f"média={np.mean(validos_depois):.2f}, "
            f"max={np.max(validos_depois):.2f}, "
            f"desvio={np.std(validos_depois):.2f}"
        )

    return arr


# =========================================================
# LER / ALINHAR RASTERS
# =========================================================
def ler_raster(path, logger=None):
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    log_message(logger, "Lendo raster:")
    log_message(logger, path)

    dataset = rasterio.open(path)
    data = dataset.read()

    log_message(logger, f"Shape lido: {data.shape}")
    log_message(logger, f"CRS: {dataset.crs}")

    return dataset, data


def alinhar_mapbiomas(mapbiomas_ds, landsat_ds, logger=None):
    log_message(logger, "Alinhando MapBiomas à grade do Landsat...")

    src_nodata = mapbiomas_ds.nodata
    if src_nodata is None:
        src_nodata = 0

    destino = np.full(
        (landsat_ds.height, landsat_ds.width),
        NODATA_VALUE,
        dtype=np.float32,
    )

    reproject(
        source=rasterio.band(mapbiomas_ds, 1),
        destination=destino,
        src_transform=mapbiomas_ds.transform,
        src_crs=mapbiomas_ds.crs,
        dst_transform=landsat_ds.transform,
        dst_crs=landsat_ds.crs,
        resampling=Resampling.nearest,
        src_nodata=src_nodata,
        dst_nodata=NODATA_VALUE,
    )

    return destino


# =========================================================
# COORDENADAS X/Y
# =========================================================
def gerar_coordenadas(ds):
    height = ds.height
    width = ds.width
    transform = ds.transform

    cols, rows = np.meshgrid(
        np.arange(width),
        np.arange(height),
    )

    xs = (
        transform.c
        + cols * transform.a
        + rows * transform.b
        + transform.a / 2.0
    )

    ys = (
        transform.f
        + cols * transform.d
        + rows * transform.e
        + transform.e / 2.0
    )

    return xs.astype(np.float32), ys.astype(np.float32)


# =========================================================
# ESCALA E DIAGNÓSTICO DAS BANDAS
# =========================================================
def _valores_validos(arr):
    values = arr.astype(np.float32).ravel()
    values = values[np.isfinite(values)]
    values = values[values != NODATA_VALUE]
    return values


def _resumo(arr):
    values = _valores_validos(arr)

    if values.size == 0:
        return None

    return {
        "min": float(np.nanmin(values)),
        "max": float(np.nanmax(values)),
        "mean": float(np.nanmean(values)),
        "std": float(np.nanstd(values)),
        "p01": float(np.nanpercentile(values, 1)),
        "p50": float(np.nanpercentile(values, 50)),
        "p99": float(np.nanpercentile(values, 99)),
    }


def escalar_reflectancia_se_necessario(arr, band_name, logger=None):
    """
    Se a banda veio bruta do Earth Engine, converte para reflectância.
    Se já veio processada pelo coleta_gee corrigido, mantém.
    """

    arr = arr.astype(np.float32)
    stats = _resumo(arr)

    if stats is None:
        return arr

    # GeoTIFF antigo com SR bruto costuma ter valores muito maiores que 1.
    if stats["p99"] > 2.0:
        log_message(
            logger,
            f"Aviso: {band_name} parece estar bruta. Aplicando escala Landsat SR.",
        )
        arr = arr * SR_SCALE + SR_OFFSET
        arr = np.clip(arr, 0.0, 1.0).astype(np.float32)

    return arr


def escalar_temperatura_se_necessario(arr, logger=None):
    """
    b6 deve representar uma variável térmica/temperatura para este modelo.

    Se vier do coleta_gee corrigido, já estará em graus Celsius.
    Se vier bruta como ST_B6/ST_B10, converte para Celsius.
    Se vier como reflectância por causa de coleta antiga, mantém, mas avisa.
    """

    arr = arr.astype(np.float32)
    stats = _resumo(arr)

    if stats is None:
        return arr

    # ST bruto do Landsat C2 costuma estar na ordem de dezenas de milhares.
    if stats["p50"] > 20000:
        log_message(
            logger,
            "Aviso: b6 parece ser temperatura bruta ST_B6/ST_B10. "
            "Convertendo para Celsius.",
        )
        arr = arr * ST_SCALE + ST_OFFSET - 273.15
        return arr.astype(np.float32)

    # SR bruto, quando usado por engano como b6, costuma ficar na ordem de milhares.
    if stats["p50"] > 2.0 and stats["p50"] <= 20000:
        log_message(
            logger,
            "Aviso: b6 está com valores altos, mas não parece ST bruto. "
            "Mantendo os valores para não destruir a escala aprendida pelo modelo. "
            "Se o resultado sair incoerente, refaça a coleta com o coleta_gee corrigido.",
        )
        return arr.astype(np.float32)

    if -80.0 <= stats["mean"] <= 120.0:
        return arr.astype(np.float32)

    log_message(
        logger,
        f"Aviso: b6 tem estatísticas incomuns: {stats}. "
        "Confira se a coleta Landsat foi feita com o script corrigido.",
    )

    return arr.astype(np.float32)


def preparar_bandas_landsat(landsat_data, logger=None):
    if landsat_data.shape[0] < 6:
        raise ValueError(
            "O raster Landsat precisa ter 6 bandas na ordem "
            "b2, b3, b4, b5, b6, b7."
        )

    band_map = {
        "b2": escalar_reflectancia_se_necessario(landsat_data[0], "b2", logger),
        "b3": escalar_reflectancia_se_necessario(landsat_data[1], "b3", logger),
        "b4": escalar_reflectancia_se_necessario(landsat_data[2], "b4", logger),
        "b5": escalar_reflectancia_se_necessario(landsat_data[3], "b5", logger),
        "b6": escalar_temperatura_se_necessario(landsat_data[4], logger),
        "b7": escalar_reflectancia_se_necessario(landsat_data[5], "b7", logger),
    }

    return band_map


def diagnosticar_feature(
    name,
    arr,
    valid_mask_2d,
    feature_columns,
    scaler_x,
    logger=None,
):
    stats = _resumo(arr[valid_mask_2d])

    if stats is None:
        log_message(logger, f"  {name}: sem valores válidos.")
        return

    msg = (
        f"  {name}: "
        f"min={stats['min']:.4f}, "
        f"média={stats['mean']:.4f}, "
        f"max={stats['max']:.4f}"
    )

    if scaler_x is not None and hasattr(scaler_x, "mean_") and name in feature_columns:
        idx = feature_columns.index(name)
        expected_mean = float(scaler_x.mean_[idx])
        expected_scale = float(scaler_x.scale_[idx])

        if expected_scale > 0:
            z_mean = abs(stats["mean"] - expected_mean) / expected_scale
            msg += f" | z_média={z_mean:.2f}"

            if z_mean > 5:
                msg += "  <-- ATENÇÃO: fora da distribuição do treinamento"

    log_message(logger, msg)


# =========================================================
# CRIAR FEATURES
# =========================================================
def preparar_features(
    landsat_data,
    mapbiomas_array,
    landsat_ds,
    ano,
    model,
    scaler_x,
    feature_columns,
    precip=None,
    logger=None,
):
    log_message(logger, "Preparando entrada do modelo...")

    n_bands, height, width = landsat_data.shape

    mapbiomas_array = np.squeeze(mapbiomas_array).astype(np.float32)

    if mapbiomas_array.shape != (height, width):
        raise ValueError(
            "MapBiomas com formato incompatível.\n"
            f"Esperado: {(height, width)}\n"
            f"Recebido: {mapbiomas_array.shape}"
        )

    band_map = preparar_bandas_landsat(landsat_data, logger)

    xs, ys = gerar_coordenadas(landsat_ds)

    precip_value = obter_precipitacao_anual(
        ano=ano,
        precip=precip,
        logger=logger,
    )

    base_features = {
        **band_map,
        "Ano": np.full((height, width), float(ano), dtype=np.float32),
        "X": xs.astype(np.float32),
        "Y": ys.astype(np.float32),
        "precip": np.full((height, width), precip_value, dtype=np.float32),
        "mapbiomas": mapbiomas_array,
    }

    model_input_dim = int(model.input_shape[-1])
    if len(feature_columns) != model_input_dim:
        raise ValueError(
            "Número de variáveis incompatível com o modelo.\n"
            f"Modelo espera: {model_input_dim}\n"
            f"Features carregadas: {len(feature_columns)}"
        )

    valid_mask_2d = np.ones((height, width), dtype=bool)

    # MapBiomas 0 ou NoData são tratados como inválidos.
    valid_mask_2d &= np.isfinite(mapbiomas_array)
    valid_mask_2d &= mapbiomas_array != NODATA_VALUE
    valid_mask_2d &= mapbiomas_array > 0

    arrays = []

    for col in feature_columns:
        if col in base_features:
            arr = base_features[col].astype(np.float32)

        elif col.startswith("uso_"):
            class_text = col.replace("uso_", "")

            try:
                class_value = float(class_text)
            except ValueError:
                raise ValueError(
                    f"Coluna de uso do solo inválida: {col}"
                )

            arr = np.isclose(
                mapbiomas_array,
                class_value,
            ).astype(np.float32)

        else:
            raise ValueError(
                f"Variável exigida pelo modelo não encontrada: {col}"
            )

        if arr.shape != (height, width):
            raise ValueError(
                "Feature com formato incompatível:\n"
                f"Coluna: {col}\n"
                f"Formato esperado: {(height, width)}\n"
                f"Formato recebido: {arr.shape}"
            )

        valid_mask_2d &= np.isfinite(arr)
        valid_mask_2d &= arr != NODATA_VALUE

        arrays.append(arr)

    log_message(logger, "Diagnóstico das principais features:")
    for name in ["b2", "b3", "b4", "b5", "b6", "b7", "precip", "Ano", "X", "Y"]:
        if name in base_features:
            diagnosticar_feature(
                name=name,
                arr=base_features[name],
                valid_mask_2d=valid_mask_2d,
                feature_columns=feature_columns,
                scaler_x=scaler_x,
                logger=logger,
            )

    stack = np.stack(arrays, axis=-1)

    X = stack.reshape(-1, len(feature_columns)).astype(np.float32)
    valid_mask = valid_mask_2d.reshape(-1)

    log_message(logger, f"Entrada preparada: {X.shape}")
    log_message(logger, f"Pixels válidos: {int(valid_mask.sum()):,} / {len(valid_mask):,}")
    log_message(logger, f"CRS usado para X/Y: {landsat_ds.crs}")
    log_message(logger, f"Variáveis usadas: {feature_columns}")

    if valid_mask.sum() == 0:
        raise ValueError("Nenhum pixel válido encontrado após montar as features.")

    return X, valid_mask, height, width, band_map, mapbiomas_array


# =========================================================
# EXECUTAR PREDIÇÃO
# =========================================================
def predizer(model, X, valid_mask, scaler_x, scaler_y, logger=None):
    log_message(logger, "Executando predição...")

    y = np.full((X.shape[0], 1), NODATA_VALUE, dtype=np.float32)

    X_valid = X[valid_mask]

    if X_valid.size == 0:
        raise ValueError("Nenhum pixel válido encontrado para inferência.")

    X_valid_scaled = scaler_x.transform(X_valid)

    y_valid_scaled = model.predict(
        X_valid_scaled,
        batch_size=8192,
        verbose=0,
    )

    y_valid = scaler_y.inverse_transform(y_valid_scaled)

    y[valid_mask] = y_valid.astype(np.float32)

    stats = _resumo(y[valid_mask])
    if stats is not None:
        log_message(
            logger,
            (
                "Estatísticas da predição antes do recorte: "
                f"min={stats['min']:.2f}, "
                f"média={stats['mean']:.2f}, "
                f"max={stats['max']:.2f}, "
                f"desvio={stats['std']:.2f}"
            ),
        )

        # Não bloqueia a execução, mas avisa sobre valores muito fora da escala
        # observada no treinamento.
        if stats["mean"] < 100 or stats["mean"] > 2000 or stats["max"] > 3000:
            log_message(
                logger,
                "ATENÇÃO: a saída ainda está fora da faixa esperada para ET. "
                "Verifique precipitação, CRS, bandas Landsat e domínio do modelo.",
            )

    log_message(logger, "Predição concluída.")

    return y


# =========================================================
# SALVAR E RECORTAR RASTER
# =========================================================
def salvar_raster(output_path, array, reference_dataset, logger=None):
    log_message(logger, "Salvando raster temporário...")

    profile = reference_dataset.profile.copy()

    profile.update(
        dtype=rasterio.float32,
        count=1,
        nodata=NODATA_VALUE,
        compress="lzw",
    )

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(array.astype(np.float32), 1)

    log_message(logger, "Raster temporário salvo:")
    log_message(logger, output_path)


def recortar_raster_por_aoi(
    input_raster,
    output_raster,
    aoi_path,
    logger=None,
):
    log_message(logger, "Recortando raster pela área de interesse...")

    if not os.path.exists(aoi_path):
        raise FileNotFoundError(
            f"Shapefile da AOI não encontrado:\n{aoi_path}"
        )

    with rasterio.open(input_raster) as src:
        gdf = gpd.read_file(aoi_path)

        if gdf.empty:
            raise ValueError("Shapefile da AOI está vazio.")

        if gdf.crs is None:
            raise ValueError("Shapefile da AOI não possui CRS.")

        gdf = gdf.to_crs(src.crs)

        geometrias = [
            geom
            for geom in gdf.geometry
            if geom is not None and not geom.is_empty
        ]

        if not geometrias:
            raise ValueError("Nenhuma geometria válida encontrada na AOI.")

        out_image, out_transform = mask(
            src,
            geometrias,
            crop=True,
            nodata=NODATA_VALUE,
        )

        out_meta = src.meta.copy()
        out_meta.update({
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
            "nodata": NODATA_VALUE,
            "compress": "lzw",
        })

    with rasterio.open(output_raster, "w", **out_meta) as dst:
        dst.write(out_image)

    stats = _resumo(out_image[0])
    if stats is not None:
        log_message(
            logger,
            (
                "Estatísticas do raster final recortado: "
                f"min={stats['min']:.2f}, "
                f"média={stats['mean']:.2f}, "
                f"max={stats['max']:.2f}, "
                f"desvio={stats['std']:.2f}"
            ),
        )

    log_message(logger, "Raster recortado salvo:")
    log_message(logger, output_raster)


# =========================================================
# METADADOS
# =========================================================
def verificar_metadados_landsat(landsat_path, logger=None):
    metadata_path = os.path.splitext(landsat_path)[0] + "_metadata.json"

    if not os.path.exists(metadata_path):
        log_message(
            logger,
            "Aviso: metadados do Landsat processado não encontrados. "
            "Se este raster foi coletado com script antigo, refaça a coleta.",
        )
        return None

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    if not metadata.get("processed_for_model", False):
        log_message(
            logger,
            "Aviso: o arquivo de metadados não indica processamento para o modelo.",
        )

    log_message(logger, "Metadados Landsat encontrados.")
    log_message(
        logger,
        "Bandas esperadas: " + ", ".join(metadata.get("bands_order", [])),
    )

    return metadata


# =========================================================
# FUNÇÃO PRINCIPAL
# =========================================================
def executar_modelo(
    pasta_ano,
    ano,
    logger=None,
    progress=None,
    precip=None,
):
    set_progress(progress, 5)

    landsat_path = os.path.join(
        pasta_ano,
        "Landsat",
        f"landsat_{ano}.tif",
    )

    mapbiomas_path = os.path.join(
        pasta_ano,
        "Mapbiomas",
        f"mapbiomas_{ano}.tif",
    )

    aoi_path = os.path.join(
        pasta_ano,
        "AOI",
        "aoi.shp",
    )

    output_dir = os.path.join(
        pasta_ano,
        "Resultado",
    )

    os.makedirs(output_dir, exist_ok=True)

    output_raster = os.path.join(
        output_dir,
        f"etp_eto_{ano}.tif",
    )

    temp_raster = os.path.join(
        output_dir,
        f"temp_etp_eto_{ano}.tif",
    )

    for path in [landsat_path, mapbiomas_path, aoi_path]:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Arquivo obrigatório não encontrado:\n{path}"
            )

    set_progress(progress, 10)

    log_message(logger, "Gerando raster pela RNA...")

    verificar_metadados_landsat(landsat_path, logger)

    target_crs = estimar_crs_utm_por_aoi(
        aoi_path=aoi_path,
        logger=logger,
    )

    set_progress(progress, 20)

    model, scaler_x, scaler_y, feature_columns = carregar_modelo_e_scalers(
        logger,
    )

    landsat_raw = None
    mapbiomas_raw = None
    landsat_mem = None
    landsat_ds = None

    try:
        set_progress(progress, 30)

        landsat_raw, _ = ler_raster(landsat_path, logger)
        mapbiomas_raw, _ = ler_raster(mapbiomas_path, logger)

        set_progress(progress, 40)

        landsat_mem, landsat_ds = reprojetar_dataset_para_crs(
            src_ds=landsat_raw,
            target_crs=target_crs,
            resampling=Resampling.bilinear,
            resolucao=30,
            logger=logger,
        )

        landsat_data = landsat_ds.read()

        set_progress(progress, 50)

        mapbiomas_alinhado = alinhar_mapbiomas(
            mapbiomas_ds=mapbiomas_raw,
            landsat_ds=landsat_ds,
            logger=logger,
        )

        set_progress(progress, 65)

        X, valid_mask, height, width, band_map, mapbiomas_alinhado = preparar_features(
            landsat_data=landsat_data,
            mapbiomas_array=mapbiomas_alinhado,
            landsat_ds=landsat_ds,
            ano=ano,
            model=model,
            scaler_x=scaler_x,
            feature_columns=feature_columns,
            logger=logger
        )

        set_progress(progress, 75)

        y = predizer(
            model=model,
            X=X,
            valid_mask=valid_mask,
            scaler_x=scaler_x,
            scaler_y=scaler_y,
            logger=logger,
        )

        resultado = y.reshape(height, width)

        diagnosticar_pixels_negativos(
            resultado=resultado,
            band_map=band_map,
            mapbiomas_array=mapbiomas_alinhado,
            logger=logger
        )

        resultado = corrigir_predicao_fisica_et(
            resultado,
            et_min=0.0,
            et_max=1600.0,
            preencher=True,
            logger=logger
        )

        set_progress(progress, 85)

        salvar_raster(
            output_path=temp_raster,
            array=resultado,
            reference_dataset=landsat_ds,
            logger=logger,
        )

    finally:
        if landsat_ds is not None and landsat_ds is not landsat_raw:
            landsat_ds.close()

        if landsat_mem is not None:
            landsat_mem.close()

        if landsat_raw is not None:
            landsat_raw.close()

        if mapbiomas_raw is not None:
            mapbiomas_raw.close()

    set_progress(progress, 90)

    recortar_raster_por_aoi(
        input_raster=temp_raster,
        output_raster=output_raster,
        aoi_path=aoi_path,
        logger=logger,
    )

    if os.path.exists(temp_raster):
        os.remove(temp_raster)

    set_progress(progress, 100)

    log_message(logger, "Processamento finalizado.")

    return output_raster


def diagnosticar_pixels_negativos(
    resultado,
    band_map,
    mapbiomas_array,
    logger=None
):
    """
    Diagnostica pixels onde a predição de ET ficou negativa.
    """

    if logger is None:
        return

    mask_neg = (
        np.isfinite(resultado)
        & (resultado != NODATA_VALUE)
        & (resultado < 0)
    )

    total_neg = int(np.sum(mask_neg))

    if total_neg == 0:
        logger("Nenhum pixel negativo encontrado.")
        return

    total_validos = int(
        np.sum(
            np.isfinite(resultado)
            & (resultado != NODATA_VALUE)
        )
    )

    perc = total_neg / total_validos * 100.0

    logger("Diagnóstico dos pixels negativos:")
    logger(f"  Pixels negativos: {total_neg:,} ({perc:.4f}%)")

    for nome, arr in band_map.items():
        valores = arr[mask_neg]

        valores = valores[
            np.isfinite(valores)
            & (valores != NODATA_VALUE)
        ]

        if valores.size > 0:
            logger(
                f"  {nome} nos negativos: "
                f"min={np.min(valores):.4f}, "
                f"média={np.mean(valores):.4f}, "
                f"max={np.max(valores):.4f}"
            )

    usos = mapbiomas_array[mask_neg]
    usos = usos[np.isfinite(usos)]

    if usos.size > 0:
        classes, counts = np.unique(
            usos.astype(int),
            return_counts=True
        )

        ordem = np.argsort(counts)[::-1]

        logger("  Classes MapBiomas nos pixels negativos:")

        for idx in ordem[:10]:
            classe = classes[idx]
            qtd = counts[idx]
            pct = qtd / total_neg * 100.0

            logger(
                f"    Classe {classe}: {qtd:,} pixels ({pct:.2f}%)"
            )