"""Minimal deployment inputs; large county rasters never enter the bundle."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "sentinel2_20261111_clip/red.tif",
    "sentinel2_20261111_clip/nir.tif",
    "sentinel2_20261111_clip/scl.tif",
    "sentinel2_20261111_clip/swir16.tif",
    "sentinel2_item_20261111.json",
    "cdl_2025_five_points_clip.tif",
    "cdl_2025_fresno_06019.csv",
    "dwr_fields_2024.geojson",
    "nasa_power_20261001_20261118.json",
    "ssurgo_point.json",
    "clip_summary.json",
)


def missing_files(directory):
    return [name for name in FILES if not (directory / name).is_file()]
