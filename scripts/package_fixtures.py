"""Create the small, ignored archive for Git-based Vercel builds."""
import argparse
import hashlib
import zipfile
from pathlib import Path

try:
    from .fixture_bundle import FILES, ROOT, missing_files
except ImportError:
    from fixture_bundle import FILES, ROOT, missing_files


def package(source, output):
    missing = missing_files(source)
    if missing:
        raise ValueError("Missing fixture files: " + ", ".join(missing))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            # Fixed timestamps/permissions make the archive checksum reproducible.
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (source / name).read_bytes())
    return hashlib.sha256(output.read_bytes()).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "data/five_points")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/five-points-fixtures.zip")
    args = parser.parse_args()
    try:
        checksum = package(args.source, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
    print(f"Archive: {args.output} ({args.output.stat().st_size:,} bytes)")
    print(f"AGRIFORGE_DATA_SHA256={checksum}")
