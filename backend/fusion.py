"""Windowed, source-attributed observations. No browser-side spectral math."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
import csv
import json
import logging

import httpx
import numpy as np
from PIL import Image
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.warp import reproject, transform_bounds, transform_geom
from rasterio.windows import Window, from_bounds
from shapely.geometry import box, mapping, shape

from .config import ALTERNATIVES, BBOX, CENTER, DATA, MISSING

log = logging.getLogger("agriforge")


def load_json(name):
    return json.loads((DATA / name).read_text())


def read_band(path, reference=None, bbox=None, categorical=False):
    """Only window-read remote COGs; reproject ancillary grids onto red's grid."""
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_TIMEOUT="15",
                      GDAL_HTTP_CONNECTTIMEOUT="8", GDAL_HTTP_MAX_RETRY="1",
                      CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", VSI_CACHE=True):
        with rasterio.open(path) as src:
            window = None
            if bbox:
                bounds = transform_bounds("EPSG:4326", src.crs, *bbox, densify_pts=21)
                window = from_bounds(*bounds, src.transform).round_offsets().round_lengths()
                window = window.intersection(Window(0, 0, src.width, src.height))
                if window.width * window.height > 200_000:
                    raise ValueError("Window exceeds the Five Points read budget")
            values = src.read(1, window=window)
            grid = dict(transform=src.window_transform(window) if window else src.transform,
                        crs=src.crs, shape=values.shape)
            if reference is not None:
                out = np.full(reference["shape"], np.nan, dtype="float32")
                reproject(values, out, src_transform=grid["transform"], src_crs=src.crs,
                          dst_transform=reference["transform"], dst_crs=reference["crs"],
                          src_nodata=src.nodata if src.nodata is not None else 0,
                          dst_nodata=np.nan,
                          resampling=Resampling.nearest if categorical else Resampling.bilinear)
                return out, reference
            return values.astype("float32"), grid


def normalized_difference(a, b):
    denominator = a + b
    return np.divide(a - b, denominator, out=np.full(a.shape, np.nan, dtype="float32"),
                     where=(denominator > 0.00001) & np.isfinite(a) & np.isfinite(b))


def process_scene(item, fixture=False):
    assets = item["assets"]
    def path(band):
        return str(DATA / f"sentinel2_20261111_clip/{band}.tif") if fixture else assets[band]["href"]
    window = None if fixture else BBOX
    red_dn, grid = read_band(path("red"), bbox=window)
    nir_dn, _ = read_band(path("nir"), grid, bbox=window)
    scl, _ = read_band(path("scl"), grid, bbox=window, categorical=True)
    swir_dn, _ = read_band(path("swir16"), grid, bbox=window)
    def reflectance(dn, band):
        meta = assets[band].get("raster:bands", [{}])[0]
        if "scale" not in meta or "offset" not in meta:
            raise ValueError(f"Missing reflectance scale/offset for {band}")
        return np.where(dn > 0, dn * meta["scale"] + meta["offset"], np.nan)
    red, nir, swir = (reflectance(dn, band) for dn, band in
                       [(red_dn, "red"), (nir_dn, "nir"), (swir_dn, "swir16")])
    clear = np.isin(scl, [4, 5]) & np.isfinite(red) & np.isfinite(nir)
    ndvi = np.where(clear, normalized_difference(nir, red), np.nan)
    ndmi = np.where(clear, normalized_difference(nir, swir), np.nan)
    return dict(grid=grid, ndvi=ndvi, ndmi=ndmi, scl=scl, clear=clear)


def validate_fixture():
    result = process_scene(load_json("sentinel2_item_20261111.json"), fixture=True)
    mean = float(np.nanmean(result["ndvi"]))
    if not 0.29 <= mean <= 0.31:
        raise ValueError(f"STOP: Sentinel-2 reflectance check failed: {mean:.5f}, expected 0.30")
    return {"passed": True, "clear_ndvi_mean": round(mean, 6), "expected": 0.30,
            "source": "Sentinel-2 fixture 2026-11-11", "formula": "DN × 0.0001 − 0.1"}


def fetch_scene():
    """Earth Search uses grid:code for Collection 1's MGRS tile filter."""
    from pystac_client import Client
    from pystac_client.stac_api_io import StacApiIO
    end = datetime.now(timezone.utc).isoformat()
    api = Client.open("https://earth-search.aws.element84.com/v1",
                      stac_io=StacApiIO(timeout=12, max_retries=0))
    search = api.search(collections=["sentinel-2-c1-l2a"], bbox=BBOX,
                        datetime=f"{date.today() - timedelta(days=90)}T00:00:00Z/{end}",
                        query={"eo:cloud_cover": {"lt": 15}, "grid:code": {"eq": "MGRS-10SGF"}},
                        sortby=[{"field": "properties.datetime", "direction": "desc"}],
                        max_items=1, limit=1, method="POST")
    items = list(search.items())
    if not items:
        raise ValueError("Earth Search returned no clear 10SGF scenes in the last 90 days")
    item = items[0].to_dict()
    return item, process_scene(item)


def fetch_power():
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=110)
    response = httpx.get("https://power.larc.nasa.gov/api/temporal/daily/point",
        params={"parameters": "PRECTOTCORR,T2M", "community": "AG", "longitude": CENTER[0],
                "latitude": CENTER[1], "start": start.strftime("%Y%m%d"),
                "end": end.strftime("%Y%m%d"), "format": "JSON"}, timeout=18)
    response.raise_for_status()
    data = response.json()
    if not data.get("properties", {}).get("parameter", {}).get("T2M"):
        raise ValueError("POWER response has no temperature series")
    return data


def fetch_aerial():
    try:
        response = httpx.post("https://planetarycomputer.microsoft.com/api/stac/v1/search",
            json={"collections": ["naip"], "bbox": BBOX, "limit": 100,
                  "sortby": [{"field": "properties.datetime", "direction": "desc"}]}, timeout=10)
        response.raise_for_status()
        features = response.json()["features"]
        covering = [f for f in features if shape(f["geometry"]).covers(box(*BBOX))]
        candidates = covering or features
        feature = max(candidates, key=lambda f: f["properties"].get("datetime") or f["properties"].get("start_datetime", ""))
        return {"source": "USDA NAIP / Planetary Computer", "item_id": feature["id"],
                "date": feature["properties"].get("datetime", feature["properties"].get("start_datetime")),
                "resolution_m": feature["properties"].get("gsd", 0.6), "mode": "NAIP",
                "url": f"https://planetarycomputer.microsoft.com/api/data/v1/item/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png?collection=naip&item={feature['id']}&assets=image&bidx=1&bidx=2&bidx=3&rescale=0%2C255"}
    except Exception as exc:
        return {"source": "Esri World Imagery", "mode": "WORLD_IMAGERY", "date": None,
                "resolution_m": None, "note": "Local acquisition date/resolution unverified",
                "fallback_reason": str(exc)[:200]}


def power_context(raw, scene_date):
    end = date.fromisoformat(scene_date[:10]) - timedelta(days=1)
    start = end - timedelta(days=13)
    parameters = raw["properties"]["parameter"]
    days = []
    for i in range(14):
        day = start + timedelta(days=i)
        record = {"date": day.isoformat()}
        for key, label in [("PRECTOTCORR", "rain_mm"), ("T2M", "temperature_c")]:
            value = parameters.get(key, {}).get(day.strftime("%Y%m%d"))
            record[label] = None if value is None or value == -999 else value
        days.append(record)
    rain = [d["rain_mm"] for d in days if d["rain_mm"] is not None]
    temp = [d["temperature_c"] for d in days if d["temperature_c"] is not None]
    return {"source": "NASA POWER daily point", "resolution": "~0.5° regional cell",
            "start": start.isoformat(), "end": end.isoformat(), "days": days,
            "rain_mm": round(sum(rain), 2) if rain else None,
            "temperature_c": round(float(np.mean(temp)), 2) if temp else None,
            "missing_values": sum(v is None for d in days for k, v in d.items() if k != "date"),
            "rain_days_present": len(rain), "temperature_days_present": len(temp),
            "limitation": "Regional context cannot explain one side of a field."}


def stats(values):
    values = values[np.isfinite(values)]
    if not values.size:
        return {"mean": None, "p10": None, "p20": None, "p90": None, "count": 0}
    return dict(zip(["mean", "p10", "p20", "p90", "count"],
                    [round(float(np.mean(values)), 4), *[round(float(np.quantile(values, q)), 4)
                     for q in [.1, .2, .9]], int(values.size)]))


def within_class_gaps(ndvi, classes, valid):
    """Exact leave-one-out 20th percentile per CDL class inside one field."""
    gaps = np.zeros(ndvi.shape, dtype="float32")
    for code in np.unique(classes[valid & np.isfinite(classes)]):
        mask = valid & (classes == code) & np.isfinite(ndvi)
        values = ndvi[mask]
        n = len(values)
        if n < 10:
            continue
        ordered = np.sort(values)
        ranks = np.searchsorted(ordered, values)
        q = .2 * (n - 2)
        lo, hi = int(np.floor(q)), int(np.ceil(q))
        lower = ordered[lo + (ranks <= lo).astype(int)]
        upper = ordered[hi + (ranks <= hi).astype(int)]
        threshold = lower + (q - lo) * (upper - lower)
        gaps[mask] = np.maximum(0, threshold - values)
    return gaps


def fuse(offline=False):
    check = validate_fixture()
    fixture_item = load_json("sentinel2_item_20261111.json")
    status = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        tasks = {} if offline else {"sentinel": pool.submit(fetch_scene),
                                   "power": pool.submit(fetch_power), "aerial": pool.submit(fetch_aerial)}
        try:
            if offline:
                raise ValueError("Offline mode explicitly requested")
            item, scene = tasks["sentinel"].result()
            status["sentinel"] = {"mode": "LIVE", "source": "Element84 Earth Search"}
        except Exception as exc:
            item, scene = fixture_item, process_scene(fixture_item, True)
            status["sentinel"] = {"mode": "FIXTURE", "source": "Sentinel-2 local clip", "reason": str(exc)[:240]}
        try:
            if offline:
                raise ValueError("Offline mode explicitly requested")
            weather = tasks["power"].result()
            status["power"] = {"mode": "LIVE", "source": "NASA POWER"}
        except Exception as exc:
            weather = load_json("nasa_power_20261001_20261118.json")
            status["power"] = {"mode": "FIXTURE", "source": "NASA POWER local extract", "reason": str(exc)[:240]}
        aerial = tasks["aerial"].result() if not offline else {
            "source": "Esri World Imagery", "mode": "WORLD_IMAGERY", "date": None, "resolution_m": None}
    scene_time = item["properties"]["datetime"]
    power_end = max(weather["properties"]["parameter"]["T2M"])
    status["sentinel"]["datetime"] = scene_time
    status["power"]["end_date"] = f"{power_end[:4]}-{power_end[4:6]}-{power_end[6:]}"
    log.warning("STAC datetime=%s [%s]; POWER end date=%s [%s]", scene_time,
                status["sentinel"]["mode"], status["power"]["end_date"], status["power"]["mode"])
    context = power_context(weather, scene_time)
    soil = load_json("ssurgo_point.json")
    surface = soil["horizons"][0]
    soil_context = {"source": soil["source"], "date": soil["retrieved"], "scope": "Whole bbox, center point",
                    "texture": surface["muname"], "component_pct": float(surface["comppct_r"]),
                    "sand_pct": float(surface["sandtotal_r"]), "silt_pct": float(surface["silttotal_r"]),
                    "clay_pct": float(surface["claytotal_r"]), "organic_matter_pct": float(surface["om_r"]),
                    "ph": float(surface["ph1to1h2o_r"]), "limitation": "Organic matter is not nitrate."}
    ndvi, grid = scene["ndvi"], scene["grid"]
    cdl, _ = read_band(str(DATA / "cdl_2025_five_points_clip.tif"), grid, categorical=True)
    labels = {}
    with (DATA / "cdl_2025_fresno_06019.csv").open() as f:
        for row in csv.DictReader(f, skipinitialspace=True):
            labels[int(row["Value"])] = row["Category"].strip()
    age = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(scene_time.replace("Z", "+00:00"))).days)
    fields = []
    for feature in load_json("dwr_fields_2024.geojson")["features"]:
        geom = shape(feature["geometry"]).intersection(box(*BBOX))
        if geom.is_empty or geom.area < 0.0000001 or geom.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        projected = transform_geom("EPSG:4326", grid["crs"], mapping(geom))
        inside = geometry_mask([projected], out_shape=ndvi.shape, transform=grid["transform"], invert=True)
        count = int(inside.sum())
        if count < 8:
            continue
        clear = inside & scene["clear"] & np.isfinite(ndvi)
        clear_count = int(clear.sum())
        fraction = clear_count / count
        codes, counts = np.unique(cdl[inside & np.isfinite(cdl)], return_counts=True)
        code = int(codes[np.argmax(counts)]) if codes.size else 0
        gaps = within_class_gaps(ndvi, cdl, clear)
        positive = gaps[gaps > 0]
        gap = float(positive.mean()) if positive.size else 0
        poor = age > 30 or fraction < .6 or clear_count < 20
        point = geom.representative_point()
        raw_counts, raw_n = np.unique(scene["scl"][inside & np.isfinite(scene["scl"])], return_counts=True)
        packet = {"polygon_id": f"DWR-{feature['id']}", "scene_datetime": scene_time,
                  "scene_id": item["id"], "scene_age_days": age, "state_fips": "06",
                  "field_source": "California DWR provisional crop mapping 2024; clipped to demo bbox",
                  "ndvi": stats(ndvi[clear]), "ndmi": stats(scene["ndmi"][clear]),
                  "measurement_resolution_m": 10, "ndmi_native_resolution_m": 20,
                  "clear_pixel_fraction": round(fraction, 4), "total_pixels": count,
                  "scl_counts": {str(int(k)): int(v) for k, v in zip(raw_counts, raw_n)},
                  "cdl": {"code": code, "name": labels.get(code, "Unknown"), "year": 2025,
                          "source": "USDA NASS Cropland Data Layer", "resolution_m": 30,
                          "note": "Annual class, not a live crop observation."},
                  "anomaly_gap": round(gap, 5), "anomaly_pixels": int(positive.size),
                  "score": round(gap * fraction, 5), "power": context, "ssurgo": soil_context,
                  "sources": status, "missing_agronomic_fields": MISSING,
                  "alternative_explanations": ALTERNATIVES,
                  "action": "defer_observation" if poor else "inspect_plot"}
        fields.append({"id": packet["polygon_id"], "geometry": mapping(geom),
                       "center": [point.x, point.y], "packet": packet})
    fields.sort(key=lambda f: f["packet"]["score"], reverse=True)
    for index, field in enumerate(fields):
        field["rank"] = index + 1
    bounds = rasterio.transform.array_bounds(*grid["shape"], grid["transform"])
    overlay_bounds = transform_bounds(grid["crs"], "EPSG:4326", *bounds, densify_pts=21)
    # Warp the measurement image to geographic coordinates before placing on Cesium.
    from rasterio.warp import calculate_default_transform
    dst_transform, width, height = calculate_default_transform(grid["crs"], "EPSG:4326",
                                                               grid["shape"][1], grid["shape"][0], *bounds)
    display = np.full((height, width), np.nan, dtype="float32")
    reproject(ndvi, display, src_transform=grid["transform"], src_crs=grid["crs"],
              dst_transform=dst_transform, dst_crs="EPSG:4326", src_nodata=np.nan,
              dst_nodata=np.nan, resampling=Resampling.nearest)
    overlay_bounds = rasterio.transform.array_bounds(height, width, dst_transform)
    t = np.clip((np.nan_to_num(display, nan=.1) - .1) / .45, 0, 1)
    low, mid, high = np.array([119, 77, 45]), np.array([230, 161, 92]), np.array([175, 220, 165])
    rgb = np.where((t < .5)[..., None], low + (mid - low) * (t * 2)[..., None],
                   mid + (high - mid) * ((t - .5) * 2)[..., None])
    rgba = np.dstack([rgb.astype("uint8"), np.where(np.isfinite(display), 200, 0).astype("uint8")])
    image = BytesIO()
    Image.fromarray(rgba).save(image, format="PNG")
    field_images = {}
    for field in fields:
        inside = geometry_mask([field["geometry"]], out_shape=(height, width), transform=dst_transform, invert=True)
        field_rgba = rgba.copy()
        field_rgba[~inside, 3] = 0
        buffer = BytesIO()
        Image.fromarray(field_rgba).save(buffer, format="PNG")
        field_images[field["id"]] = buffer.getvalue()
    return {"fields": fields, "status": status, "scene": {"id": item["id"], "datetime": scene_time,
            "age_days": age, "resolution_m": 10}, "aerial": aerial, "validation": check,
            "ndvi_bounds": list(overlay_bounds), "ndvi_png": image.getvalue(), "ndvi_fields": field_images,
            "generated_at": datetime.now(timezone.utc).isoformat()}
