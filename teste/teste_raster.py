import rasterio
import numpy as np

raster_path = r"C:\Users\lucas\OneDrive\Documentos\GitHub\QGISPlugin\teste\shapes\sorocaba\2024\Resultado\etp_eto_2024.tif"

with rasterio.open(raster_path) as src:
    arr = src.read(1).astype(np.float32)
    nodata = src.nodata

    if nodata is not None:
        valid = arr[arr != nodata]
    else:
        valid = arr[np.isfinite(arr)]

    valid = valid[np.isfinite(valid)]

    print("Shape:", arr.shape)
    print("CRS:", src.crs)
    print("Nodata:", nodata)
    print("Pixels válidos:", valid.size)

    print("Min:", np.min(valid))
    print("Max:", np.max(valid))
    print("Média:", np.mean(valid))
    print("Desvio padrão:", np.std(valid))
    print("Percentil 1:", np.percentile(valid, 1))
    print("Percentil 50:", np.percentile(valid, 50))
    print("Percentil 99:", np.percentile(valid, 99))