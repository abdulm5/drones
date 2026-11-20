"""Preview entrypoint for the repaired observation service."""
from pathlib import Path
import sys

root = str(Path(__file__).resolve().parents[1])
if root not in sys.path:
    sys.path.insert(0, root)

from deployment.observation_entry import app
