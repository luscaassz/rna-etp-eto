import os
import ee
import geemap
import geopandas as gpd

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

    # =====================================================
    # DEFINIR COLEÇÃO
    # =====================================================
    if collection == "Landsat 5":

        collection_id = (
            "LANDSAT/LT05/C02/T1_L2"
        )

    elif collection == "Landsat 7":

        collection_id = (
            "LANDSAT/LE07/C02/T1_L2"
        )

    elif collection == "Landsat 8":

        collection_id = (
            "LANDSAT/LC08/C02/T1_L2"
        )

    elif collection == "Landsat 9":

        collection_id = (
            "LANDSAT/LC09/C02/T1_L2"
        )

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
            "Nenhuma imagem encontrada."
        )

    if logger:
        logger(f"Imagens encontradas: {count}")

    # =====================================================
    # MOSAICO
    # =====================================================
    image = (
        landsat
        .median()
        .clip(ee_geom)
    )

    # =====================================================
    # EXPORTAÇÃO
    # =====================================================
    geemap.ee_export_image(
        image,
        filename=output_tif,
        scale=30,
        region=ee_geom,
        file_per_band=False,
    )

    if logger:
        logger(f"Landsat salvo:")
        logger(output_tif)

    return output_tif


# =========================================================
# FUNÇÃO PRINCIPAL
# =========================================================
def coletar_dados(
    shp_path,
    output_folder,
    year,
    collection,
    cloud,
    logger=None
):

    initialize_ee(logger)

    ee_geom = shapefile_to_ee_geometry(
        shp_path,
        logger
    )

    # =====================================================
    # MAPBIOMAS
    # =====================================================
    baixar_mapbiomas(
        ee_geom=ee_geom,
        pasta_saida=output_folder,
        ano=year,
        logger=logger
    )

    # =====================================================
    # LANDSAT
    # =====================================================
    baixar_landsat(
        ee_geom=ee_geom,
        pasta_saida=output_folder,
        ano=year,
        collection=collection,
        cloud=cloud,
        logger=logger
    )

    if logger:
        logger("Coleta concluída.")