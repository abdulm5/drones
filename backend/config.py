import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("AGRIFORGE_DATA", ROOT / "data/five_points"))
BBOX = [-120.116, 36.336, -120.100, 36.348]
CENTER = [-120.108177, 36.341988]
DEPOT = [-120.108177, 36.33615]
MISSING = ["root-zone nitrate", "irrigation-water nitrate", "prior applications", "growth stage", "approved product for this crop"]
ALTERNATIVES = ["crop stage", "water stress", "disease", "harvest", "soil background", "imaging artifact"]
