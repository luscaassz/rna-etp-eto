import os
import json
import shutil

import ee
import geemap
import geopandas as gpd
import numpy as np
import rasterio

from shapely.geometry import mapping


# =========================================================
# CONFIGURAÇÕES GERAIS
# =========================================================

EE_PROJECT = "qgis-493503"

MAPBIOMAS_ASSET_ID = (
    "projects/mapbiomas-public/assets/brazil/lulc/collection10/"
    "mapbiomas_brazil_collection10_coverage_v2"
)

# Escalas oficiais do Landsat Collection 2 Level-2.
# Reflectância de superfície:
#   reflectance = DN * 0.0000275 - 0.2
# Temperatura de superfície:
#   Kelvin = DN * 0.00341802 + 149.0
SR_SCALE = 0.0000275
SR_OFFSET = -0.2

ST_SCALE = 0.00341802
ST_OFFSET = 149.0

LANDSAT_MODEL_BANDS = ["b2", "b3", "b4", "b5", "b6", "b7"]


# =========================================================
# LOG AUXILIAR
# =========================================================
def log_message(logger, message):
    if logger:
        logger(str(message))


# =========================================================
# INICIALIZA EARTH ENGINE
# =========================================================
def initialize_ee(logger=None):
    try:
        ee.Initialize(project=EE_PROJECT)
        log_message(logger, "Earth Engine inicializado.")
    except Exception:
        log_message(logger, "Autenticando Earth Engine...")
        ee.Authenticate()
        ee.Initialize(project=EE_PROJECT)
        log_message(logger, "Earth Engine autenticado.")


# =========================================================
# CONVERTE SHAPEFILE PARA GEOMETRIA EE
# =========================================================
def shapefile_to_ee_geometry(shp_path, logger=None):
    log_message(logger, "Lendo shapefile...")

    gdf = gpd.read_file(shp_path)

    if gdf.empty:
        raise ValueError("Shapefile vazio.")

    if gdf.crs is None:
        raise ValueError("Shapefile sem CRS.")

    gdf = gdf.to_crs(epsg=4326)

    geom = gdf.union_all()

    if geom.is_empty:
        raise ValueError("Geometria vazia.")

    geom = geom.simplify(
        tolerance=0.0005,
        preserve_topology=True,
    )

    ee_geom = ee.Geometry(mapping(geom))

    log_message(logger, "Geometria convertida.")

    return ee_geom


# =========================================================
# SALVAR CÓPIA DA ÁREA DE INTERESSE
# =========================================================
def salvar_aoi_local(shp_path, pasta_saida, ano, logger=None):
    aoi_dir = os.path.join(
        pasta_saida,
        str(ano),
        "AOI",
    )

    os.makedirs(aoi_dir, exist_ok=True)

    base = os.path.splitext(shp_path)[0]

    extensoes = [
        ".shp",
        ".shx",
        ".dbf",
        ".prj",
        ".cpg",
        ".qpj",
    ]

    for ext in extensoes:
        origem = base + ext

        if os.path.exists(origem):
            destino = os.path.join(
                aoi_dir,
                "aoi" + ext,
            )

            shutil.copy2(origem, destino)

    aoi_path = os.path.join(
        aoi_dir,
        "aoi.shp",
    )

    if not os.path.exists(aoi_path):
        raise FileNotFoundError(
            "Não foi possível copiar a AOI para a pasta do ano:\n"
            f"{aoi_path}"
        )

    log_message(logger, "AOI salva em:")
    log_message(logger, aoi_path)

    return aoi_path


# =========================================================
# MAPBIOMAS
# =========================================================
def baixar_mapbiomas(
    ee_geom,
    pasta_saida,
    ano,
    logger=None,
):
    log_message(logger, "Baixando MapBiomas...")

    mapbiomas_dir = os.path.join(
        pasta_saida,
        str(ano),
        "Mapbiomas",
    )

    os.makedirs(mapbiomas_dir, exist_ok=True)

    output_tif = os.path.abspath(
        os.path.join(
            mapbiomas_dir,
            f"mapbiomas_{ano}.tif",
        )
    )

    if os.path.exists(output_tif):
        os.remove(output_tif)

    band_name = f"classification_{ano}"

    image = (
        ee.Image(MAPBIOMAS_ASSET_ID)
        .select(band_name)
        .clip(ee_geom)
        .toInt16()
    )

    try:
        geemap.ee_export_image(
            image,
            filename=output_tif,
            scale=30,
            region=ee_geom,
            file_per_band=False,
        )
    except Exception as e:
        raise RuntimeError(
            f"Erro ao exportar MapBiomas:\n{str(e)}"
        )

    validar_arquivo_raster(output_tif, "MapBiomas")

    log_message(logger, "MapBiomas salvo:")
    log_message(logger, output_tif)

    return output_tif


# =========================================================
# VALIDAÇÃO LANDSAT POR ANO
# =========================================================
def validar_landsat_ano(collection, ano):
    if collection == "Landsat 5" and not (1985 <= ano <= 2012):
        raise ValueError(
            f"{collection} não está disponível para o ano {ano}."
        )

    if collection == "Landsat 7" and ano < 1999:
        raise ValueError(
            f"{collection} não está disponível para o ano {ano}."
        )

    if collection == "Landsat 8" and ano < 2013:
        raise ValueError(
            f"{collection} não está disponível para o ano {ano}."
        )

    if collection == "Landsat 9" and ano < 2021:
        raise ValueError(
            f"{collection} não está disponível para o ano {ano}."
        )


def get_landsat_config(collection):
    if collection == "Landsat 5":
        return {
            "collection_id": "LANDSAT/LT05/C02/T1_L2",
            "thermal_band": "ST_B6",
        }

    if collection == "Landsat 7":
        return {
            "collection_id": "LANDSAT/LE07/C02/T1_L2",
            "thermal_band": "ST_B6",
        }

    if collection == "Landsat 8":
        return {
            "collection_id": "LANDSAT/LC08/C02/T1_L2",
            "thermal_band": "ST_B10",
        }

    if collection == "Landsat 9":
        return {
            "collection_id": "LANDSAT/LC09/C02/T1_L2",
            "thermal_band": "ST_B10",
        }

    raise ValueError(f"Coleção inválida: {collection}")


# =========================================================
# MÁSCARA E PRÉ-PROCESSAMENTO LANDSAT
# =========================================================
def mascarar_landsat_c2_l2(image):
    """
    Remove pixels problemáticos usando QA_PIXEL e QA_RADSAT.
    Bits usados em QA_PIXEL:
    1 = Dilated Cloud
    2 = Cirrus
    3 = Cloud
    4 = Cloud Shadow
    5 = Snow
    """

    qa_pixel = image.select("QA_PIXEL")

    mask = (
        qa_pixel.bitwiseAnd(1 << 1).eq(0)
        .And(qa_pixel.bitwiseAnd(1 << 2).eq(0))
        .And(qa_pixel.bitwiseAnd(1 << 3).eq(0))
        .And(qa_pixel.bitwiseAnd(1 << 4).eq(0))
        .And(qa_pixel.bitwiseAnd(1 << 5).eq(0))
    )

    # Remove pixels saturados, quando a banda existe.
    mask = mask.And(image.select("QA_RADSAT").eq(0))

    return image.updateMask(mask)


def preparar_landsat_modelo(image, collection):
    """
    Prepara uma imagem Landsat para ficar compatível com as entradas
    esperadas pelo modelo.

    Saída sempre com 6 bandas na ordem:
        b2, b3, b4, b5, b6, b7

    Onde:
        b2, b3, b4, b5 e b7 = reflectância de superfície, 0-1
        b6 = temperatura de superfície em graus Celsius
    """

    config = get_landsat_config(collection)
    thermal_band = config["thermal_band"]

    image = mascarar_landsat_c2_l2(image)

    reflectancia = (
        image
        .select(
            ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7"],
            ["b2", "b3", "b4", "b5", "b7"],
        )
        .multiply(SR_SCALE)
        .add(SR_OFFSET)
        .clamp(0.0, 1.0)
    )

    temperatura_celsius = (
        image
        .select(thermal_band)
        .multiply(ST_SCALE)
        .add(ST_OFFSET)
        .subtract(273.15)
        .rename("b6")
    )

    output = (
        reflectancia
        .addBands(temperatura_celsius)
        .select(LANDSAT_MODEL_BANDS)
        .toFloat()
    )

    return output


# =========================================================
# VALIDAÇÃO DE ARQUIVO E ESTATÍSTICAS
# =========================================================
def validar_arquivo_raster(path, nome):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"O arquivo {nome} não foi criado:\n{path}\n\n"
            "Possíveis causas:\n"
            "- área grande demais;\n"
            "- problema de permissão na pasta;\n"
            "- falha silenciosa no geemap;\n"
            "- download interrompido;\n"
            "- pasta sincronizada pelo OneDrive."
        )

    if os.path.getsize(path) == 0:
        raise ValueError(
            f"O arquivo {nome} foi criado, mas está vazio:\n{path}"
        )


def _estatisticas_validas(array):
    arr = array.astype(np.float32)
    arr = arr[np.isfinite(arr)]

    if arr.size == 0:
        return None

    return {
        "min": float(np.nanmin(arr)),
        "max": float(np.nanmax(arr)),
        "mean": float(np.nanmean(arr)),
        "std": float(np.nanstd(arr)),
    }


def validar_landsat_processado(output_tif, logger=None):
    """
    Verifica se o GeoTIFF exportado está na escala esperada para o modelo.
    Isso evita passar valores brutos do Earth Engine para a RNA.
    """

    with rasterio.open(output_tif) as src:
        if src.count != 6:
            raise ValueError(
                "O raster Landsat precisa ter exatamente 6 bandas "
                f"na ordem {LANDSAT_MODEL_BANDS}, mas possui {src.count}."
            )

        log_message(logger, "Validação das bandas Landsat processadas:")

        for idx, band_name in enumerate(LANDSAT_MODEL_BANDS, start=1):
            arr = src.read(idx)
            stats = _estatisticas_validas(arr)

            if stats is None:
                raise ValueError(
                    f"A banda {band_name} não possui pixels válidos."
                )

            log_message(
                logger,
                (
                    f"  {band_name}: "
                    f"min={stats['min']:.4f}, "
                    f"média={stats['mean']:.4f}, "
                    f"max={stats['max']:.4f}"
                )
            )

            if band_name in ["b2", "b3", "b4", "b5", "b7"]:
                if stats["max"] > 1.5 or stats["min"] < -0.2:
                    raise ValueError(
                        f"A banda {band_name} parece estar fora da escala de "
                        "reflectância esperada. O esperado é aproximadamente 0-1.\n"
                        f"Estatísticas: {stats}"
                    )

            if band_name == "b6":
                # Como b6 é temperatura, aceitamos uma faixa mais ampla.
                # Valores muito extremos indicam que ST_B6/ST_B10 não foi processada corretamente.
                if stats["mean"] < -60 or stats["mean"] > 100:
                    raise ValueError(
                        "A banda b6 parece incoerente para temperatura de superfície "
                        "em graus Celsius.\n"
                        f"Estatísticas: {stats}"
                    )


def salvar_metadados_landsat(
    output_tif,
    ano,
    collection,
    cloud,
    image_count,
    logger=None,
):
    metadata_path = os.path.splitext(output_tif)[0] + "_metadata.json"

    metadata = {
        "processed_for_model": True,
        "year": int(ano),
        "collection": collection,
        "cloud_cover_threshold": float(cloud),
        "image_count": int(image_count),
        "bands_order": LANDSAT_MODEL_BANDS,
        "band_definitions": {
            "b2": "SR_B2 reflectance, scaled with DN * 0.0000275 - 0.2",
            "b3": "SR_B3 reflectance, scaled with DN * 0.0000275 - 0.2",
            "b4": "SR_B4 reflectance, scaled with DN * 0.0000275 - 0.2",
            "b5": "SR_B5 reflectance, scaled with DN * 0.0000275 - 0.2",
            "b6": "Surface temperature in Celsius from ST_B6 or ST_B10",
            "b7": "SR_B7 reflectance, scaled with DN * 0.0000275 - 0.2",
        },
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)

    log_message(logger, "Metadados Landsat salvos:")
    log_message(logger, metadata_path)


# =========================================================
# LANDSAT
# =========================================================
def baixar_landsat(
    ee_geom,
    pasta_saida,
    ano,
    collection,
    cloud,
    logger=None,
):
    log_message(logger, "Baixando Landsat...")

    validar_landsat_ano(collection, ano)

    config = get_landsat_config(collection)
    collection_id = config["collection_id"]

    landsat_dir = os.path.join(
        pasta_saida,
        str(ano),
        "Landsat",
    )

    os.makedirs(landsat_dir, exist_ok=True)

    output_tif = os.path.abspath(
        os.path.join(
            landsat_dir,
            f"landsat_{ano}.tif",
        )
    )

    if os.path.exists(output_tif):
        os.remove(output_tif)

    metadata_path = os.path.splitext(output_tif)[0] + "_metadata.json"
    if os.path.exists(metadata_path):
        os.remove(metadata_path)

    start_date = f"{ano}-01-01"
    end_date = f"{ano}-12-31"

    landsat = (
        ee.ImageCollection(collection_id)
        .filterBounds(ee_geom)
        .filterDate(start_date, end_date)
        .filter(
            ee.Filter.lt(
                "CLOUD_COVER",
                cloud,
            )
        )
    )

    count = int(landsat.size().getInfo())

    if count == 0:
        raise ValueError(
            f"Nenhuma imagem Landsat encontrada para {ano} "
            f"com nuvem menor que {cloud}%."
        )

    log_message(logger, f"Imagens encontradas: {count}")
    log_message(logger, f"Coleção usada: {collection_id}")
    log_message(
        logger,
        "Bandas exportadas na ordem do modelo: "
        + ", ".join(LANDSAT_MODEL_BANDS),
    )

    image = (
        landsat
        .map(lambda img: preparar_landsat_modelo(img, collection))
        .median()
        .clip(ee_geom)
        .toFloat()
    )

    try:
        geemap.ee_export_image(
            image,
            filename=output_tif,
            scale=30,
            region=ee_geom,
            file_per_band=False,
        )
    except Exception as e:
        raise RuntimeError(
            f"Erro ao exportar Landsat:\n{str(e)}"
        )

    validar_arquivo_raster(output_tif, "Landsat")
    validar_landsat_processado(output_tif, logger)

    salvar_metadados_landsat(
        output_tif=output_tif,
        ano=ano,
        collection=collection,
        cloud=cloud,
        image_count=count,
        logger=logger,
    )

    log_message(logger, "Landsat salvo:")
    log_message(logger, output_tif)

    return output_tif


# =========================================================
# FUNÇÃO AUXILIAR DE PROGRESSO
# =========================================================
def set_progress(progress, value):
    if progress:
        progress(int(value))


# =========================================================
# FUNÇÃO PRINCIPAL
# =========================================================
def coletar_dados(
    shp_path,
    output_folder,
    year,
    collection,
    cloud,
    logger=None,
    progress=None,
):
    set_progress(progress, 5)

    log_message(logger, "Inicializando Earth Engine...")
    initialize_ee(logger)

    set_progress(progress, 15)

    log_message(logger, "Convertendo shapefile para geometria...")
    ee_geom = shapefile_to_ee_geometry(
        shp_path,
        logger,
    )

    salvar_aoi_local(
        shp_path=shp_path,
        pasta_saida=output_folder,
        ano=year,
        logger=logger,
    )

    set_progress(progress, 30)

    log_message(logger, "Iniciando download do MapBiomas...")
    baixar_mapbiomas(
        ee_geom=ee_geom,
        pasta_saida=output_folder,
        ano=year,
        logger=logger,
    )

    set_progress(progress, 60)

    log_message(logger, "Iniciando download do Landsat processado...")
    baixar_landsat(
        ee_geom=ee_geom,
        pasta_saida=output_folder,
        ano=year,
        collection=collection,
        cloud=cloud,
        logger=logger,
    )

    set_progress(progress, 95)

    log_message(logger, "Coleta concluída.")

    set_progress(progress, 100)
