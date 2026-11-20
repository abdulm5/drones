"""Bundle system libraries required by GDAL but absent from Vercel's runtime."""
import ctypes
from pathlib import Path
import platform
import shutil
import sysconfig

ROOT = Path(__file__).resolve().parents[1]
LIBRARIES = ("libexpat.so.1",)


def find_library(filename):
    directories = [Path(path) for path in [
        "/usr/lib64", "/lib64", "/usr/lib/x86_64-linux-gnu", "/lib/x86_64-linux-gnu",
        "/usr/lib/aarch64-linux-gnu", "/lib/aarch64-linux-gnu", "/usr/lib", "/lib",
        sysconfig.get_config_var("LIBDIR") or "/usr/local/lib",
    ]]
    for directory in directories:
        candidate = directory / filename
        if candidate.is_file():
            return candidate.resolve()
    # Also support build images with libraries under a nonstandard loader path.
    ctypes.CDLL(filename)
    for line in Path("/proc/self/maps").read_text().splitlines():
        path = line.split()[-1]
        if path.startswith("/") and Path(path).name.startswith(filename):
            return Path(path).resolve()
    raise FileNotFoundError(f"Cannot locate {filename} in the Linux build image")


def prepare():
    if platform.system() != "Linux":
        print("Native-library packaging runs on Vercel's Linux build image.")
        return
    destination = ROOT / "vendor/native"
    destination.mkdir(parents=True, exist_ok=True)
    for filename in LIBRARIES:
        source = find_library(filename)
        if source.read_bytes()[:4] != b"\x7fELF":
            raise ValueError(f"{filename} is not a Linux shared library")
        shutil.copyfile(source, destination / filename)
        print(f"Bundled GDAL runtime dependency: {filename}")
    for directory in [Path("/usr/share/licenses/expat"), Path("/usr/share/doc/libexpat1")]:
        if directory.is_dir():
            for name in ["COPYING", "LICENSE", "copyright"]:
                if (directory / name).is_file():
                    shutil.copyfile(directory / name, destination / "EXPAT-LICENSE.txt")


if __name__ == "__main__":
    prepare()
