"""Materialize ignored fixture data before Vercel packages the Python function."""
import hashlib
from io import BytesIO
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen
import zipfile

try:
    from .fixture_bundle import FILES, ROOT, missing_files
except ImportError:
    from fixture_bundle import FILES, ROOT, missing_files

MAX_ARCHIVE_BYTES = 8_000_000
MAX_EXPANDED_BYTES = 16_000_000


def install_archive(content, destination, checksum):
    if len(content) > MAX_ARCHIVE_BYTES:
        raise ValueError("Fixture archive exceeds the 8 MB compressed budget")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", checksum or ""):
        raise ValueError("AGRIFORGE_DATA_SHA256 must be the archive's 64-character SHA-256")
    if hashlib.sha256(content).hexdigest() != checksum.lower():
        raise ValueError("Fixture archive SHA-256 mismatch")
    with zipfile.ZipFile(BytesIO(content)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or set(names) != set(FILES):
            raise ValueError("Fixture archive must contain exactly the 11 allowlisted files; use npm run fixtures:pack")
        if sum(entry.file_size for entry in entries) > MAX_EXPANDED_BYTES:
            raise ValueError("Fixture archive exceeds the 16 MB expanded budget")
        if any(stat.S_ISLNK(entry.external_attr >> 16) for entry in entries):
            raise ValueError("Fixture archive cannot contain symbolic links")
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
            for name in FILES:
                path = Path(staging) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.read(name))
            for name in FILES:
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(Path(staging) / name, target)


def prepare(destination=None, environ=None):
    environ = os.environ if environ is None else environ
    destination = Path(destination or environ.get("AGRIFORGE_DATA") or ROOT / "data/five_points")
    url = environ.get("AGRIFORGE_DATA_URL")
    if url:
        if urlparse(url).scheme != "https":
            raise ValueError("AGRIFORGE_DATA_URL must use HTTPS")
        try:
            with urlopen(url, timeout=45) as response:
                if urlparse(response.geturl()).scheme != "https":
                    raise ValueError("Fixture download cannot redirect to HTTP")
                content = response.read(MAX_ARCHIVE_BYTES + 1)
        except OSError:
            raise ValueError("Fixture download failed. Check AGRIFORGE_DATA_URL and host access; see docs/vercel.md.") from None
        install_archive(content, destination, environ.get("AGRIFORGE_DATA_SHA256", ""))
    missing = missing_files(destination)
    if missing:
        raise ValueError("Deployment fixtures are missing. Set AGRIFORGE_DATA_URL and AGRIFORGE_DATA_SHA256 in Vercel, "
                         "or upload the local fixtures with the Vercel CLI. See docs/vercel.md. Missing: " + ", ".join(missing))
    return len(FILES)


if __name__ == "__main__":
    try:
        print(f"Deployment fixtures ready: {prepare()} minimal files (large county raster excluded).")
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        raise SystemExit(str(error)) from None
