import os
import ee
import geemap
import geopandas as gpd
import shutil

from shapely.geometry import mapping


# =========================================================
# INICIALIZA EARTH ENGINE
# =========================================================
def initialize_ee(logger=None):

    try:

        ee.Initialize(project="qgis-493503")

        if logger:
            logger("Earth Engine inicializado.")

    except Exception:

        if logger:
            logger("Autenticando Earth Engine...")

        ee.Authenticate()

        ee.Initialize(project="qgis-493503")

        if logger:
            logger("Earth Engine autenticado.")


# =========================================================
# CONVERTE SHAPEFILE PARA GEOMETRIA EE
# =========================================================
def shapefile_to_ee_geometry(shp_path, logger=None):

    if logger:
        logger("Lendo shapefile...")

    gdf = gpd.read_file(shp_path)

    if gdf.empty:
        raise ValueError("Shapefile vazio.")

    if gdf.crs is None:
        raise ValueError("Shapefile sem CRS.")

    # Reprojetar para WGS84
    gdf = gdf.to_crs(epsg=4326)

    # Junta geometrias
    geom = gdf.union_all()

    if geom.is_empty:
        raise ValueError("Geometria vazia.")

    # Simplificação para evitar erro de payload
    geom = geom.simplify(
        tolerance=0.0005,
        preserve_topology=True
    )

    ee_geom = ee.Geometry(mapping(geom))

    if logger:
        logger("Geometria convertida.")

    return ee_geom

# =========================================================
# SALVAR CÓPIA DA ÁREA DE INTERESSE
# =========================================================
def salvar_aoi_local(shp_path, pasta_saida, ano, logger=None):

    aoi_dir = os.path.join(
        pasta_saida,
        str(ano),
        "AOI"
    )

    os.makedirs(
        aoi_dir,
        exist_ok=True
    )

    base = os.path.splitext(shp_path)[0]

    extensoes = [
        ".shp",
        ".shx",
        ".dbf",
        ".prj",
        ".cpg"
    ]

    for ext in extensoes:

        origem = base + ext

        if os.path.exists(origem):

            destino = os.path.join(
                aoi_dir,
                "aoi" + ext
            )

            shutil.copy2(
                origem,
                destino
            )

    aoi_path = os.path.join(
        aoi_dir,
        "aoi.shp"
    )

    if logger:
        logger("AOI salva em:")
        logger(aoi_path)

    return aoi_path

# =========================================================
# MAPBIOMAS
# =========================================================
def baixar_mapbiomas(
    ee_geom,
    pasta_saida,
    ano,
    logger=None
):

    if logger:
        logger("Baixando MapBiomas...")

    mapbiomas_dir = os.path.join(
        pasta_saida,
        str(ano),
        "Mapbiomas"
    )

    os.makedirs(
        mapbiomas_dir,
        exist_ok=True
    )

    output_tif = os.path.join(
        mapbiomas_dir,
        f"mapbiomas_{ano}.tif"
    )

    asset_id = (
        "projects/mapbiomas-public/assets/brazil/lulc/collection10/"
        "mapbiomas_brazil_collection10_coverage_v2"
    )

    band_name = f"classification_{ano}"

    image = (
        ee.Image(asset_id)
        .select(band_name)
        .clip(ee_geom)
    )

    geemap.ee_export_image(
        image,
        filename=output_tif,
        scale=30,
        region=ee_geom,
        file_per_band=False,
    )

    if logger:
        logger(f"MapBiomas salvo:")
        logger(output_tif)

    return output_tif


# =========================================================
# LANDSAT
# =========================================================
def baixar_landsat(
    ee_geom,
    pasta_saida,
    ano,
    collection,
    cloud,
    logger=None
):

    if logger:
        logger("Baixando Landsat...")

    landsat_dir = os.path.join(
        pasta_saida,
        str(ano),
        "Landsat"
    )

    os.makedirs(
        landsat_dir,
        exist_ok=True
    )

    output_tif = os.path.join(
        landsat_dir,
        f"landsat_{ano}.tif"
    )

    output_tif = os.path.abspath(output_tif)

    if os.path.exists(output_tif):
        os.remove(output_tif)

    # =====================================================
    # DEFINIR COLEÇÃO E BANDAS
    # =====================================================
    if collection == "Landsat 5":

        collection_id = "LANDSAT/LT05/C02/T1_L2"

        bands = [
            "SR_B1",
            "SR_B2",
            "SR_B3",
            "SR_B4",
            "SR_B5",
            "SR_B7",
        ]

    elif collection == "Landsat 7":

        collection_id = "LANDSAT/LE07/C02/T1_L2"

        bands = [
            "SR_B1",
            "SR_B2",
            "SR_B3",
            "SR_B4",
            "SR_B5",
            "SR_B7",
        ]

    elif collection == "Landsat 8":

        collection_id = "LANDSAT/LC08/C02/T1_L2"

        bands = [
            "SR_B2",
            "SR_B3",
            "SR_B4",
            "SR_B5",
            "SR_B6",
            "SR_B7",
        ]

    elif collection == "Landsat 9":

        collection_id = "LANDSAT/LC09/C02/T1_L2"

        bands = [
            "SR_B2",
            "SR_B3",
            "SR_B4",
            "SR_B5",
            "SR_B6",
            "SR_B7",
        ]

    else:

        raise ValueError(
            f"Coleção inválida: {collection}"
        )

    # =====================================================
    # FILTRAR IMAGENS
    # =====================================================
    start_date = f"{ano}-01-01"
    end_date = f"{ano}-12-31"

    landsat = (
        ee.ImageCollection(collection_id)
        .filterBounds(ee_geom)
        .filterDate(start_date, end_date)
        .filter(
            ee.Filter.lt(
                "CLOUD_COVER",
                cloud
            )
        )
    )

    count = landsat.size().getInfo()

    if count == 0:

        raise ValueError(
            f"Nenhuma imagem Landsat encontrada para {ano} "
            f"com nuvem menor que {cloud}%."
        )

    if logger:
        logger(f"Imagens encontradas: {count}")
        logger(f"Bandas usadas: {bands}")

    # =====================================================
    # MOSAICO
    # =====================================================
    image = (
        landsat
        .median()
        .select(bands)
        .clip(ee_geom)
    )

    # =====================================================
    # EXPORTAÇÃO
    # =====================================================
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

    # =====================================================
    # VERIFICAÇÃO REAL DO ARQUIVO
    # =====================================================
    if not os.path.exists(output_tif):

        raise FileNotFoundError(
            "O Earth Engine/geemap finalizou sem erro, "
            "mas o arquivo Landsat não foi criado:\n"
            f"{output_tif}\n\n"
            "Possíveis causas:\n"
            "- área grande demais;\n"
            "- problema de permissão na pasta;\n"
            "- falha silenciosa no geemap;\n"
            "- download interrompido;\n"
            "- pasta sincronizada pelo OneDrive."
        )

    if os.path.getsize(output_tif) == 0:

        raise ValueError(
            f"O arquivo Landsat foi criado, mas está vazio:\n{output_tif}"
        )

    if logger:
        logger("Landsat salvo:")
        logger(output_tif)

    return output_tif

# =========================================================
# FUNÇÃO AUXILIAR DE PROGRESSO
# =========================================================
def set_progress(progress, value):

    if progress:
        progress(value)

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
    progress=None
):

    set_progress(progress, 5)

    if logger:
        logger("Inicializando Earth Engine...")

    initialize_ee(logger)

    set_progress(progress, 15)

    if logger:
        logger("Convertendo shapefile para geometria...")

    ee_geom = shapefile_to_ee_geometry(
        shp_path,
        logger
    )

    salvar_aoi_local(
        shp_path=shp_path,
        pasta_saida=output_folder,
        ano=year,
        logger=logger
    )

    set_progress(progress, 30)

    # =====================================================
    # MAPBIOMAS
    # =====================================================
    if logger:
        logger("Iniciando download do MapBiomas...")

    baixar_mapbiomas(
        ee_geom=ee_geom,
        pasta_saida=output_folder,
        ano=year,
        logger=logger
    )

    set_progress(progress, 60)

    # =====================================================
    # LANDSAT
    # =====================================================
    if logger:
        logger("Iniciando download do Landsat...")

    baixar_landsat(
        ee_geom=ee_geom,
        pasta_saida=output_folder,
        ano=year,
        collection=collection,
        cloud=cloud,
        logger=logger
    )

    set_progress(progress, 95)

    if logger:
        logger("Coleta concluída.")

    set_progress(progress, 100)

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