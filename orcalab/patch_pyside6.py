import subprocess
from pathlib import Path
import shutil
import sys


def download_file(folder: Path):
    packs = list(folder.glob("libxcb-cursor0_*.deb"))
    if len(packs) > 0:
        return packs[0]

    subprocess.run(
        [
            "apt",
            "download",
            "libxcb-cursor0",
        ],
        check=True,
        cwd=str(folder),
    )

    packs = list(folder.glob("libxcb-cursor0_*.deb"))
    if len(packs) > 0:
        return packs[0]

    raise FileNotFoundError("Failed to download libxcb-cursor0 package")


def extract_deb(deb_file: Path, extract_to: Path):
    subprocess.run(
        [
            "dpkg-deb",
            "-x",
            str(deb_file),
            str(extract_to),
        ],
        check=True,
    )


def find_pyside6_paths():
    result = subprocess.run(
        [
            "python3",
            "-c",
            "import PySide6; import os; print(os.path.dirname(PySide6.__file__))",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    pyside6_path = Path(result.stdout.strip())
    return pyside6_path


def find_libxcb_cursor_path() -> bool:
    result = subprocess.run(
        [
            "apt",
            "list",
            "--installed",
            "libxcb-cursor0",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = result.stdout.strip().splitlines()
    for line in lines:
        if line.startswith("libxcb-cursor0/"):
            return True

    return False


def patch_pyside6():
    if sys.platform != "linux":
        return

    if find_libxcb_cursor_path():
        print("libxcb-cursor0 is already installed. No patching needed.")
        return

    pyside6_path = find_pyside6_paths()
    pyside6_libs_path = pyside6_path / "Qt" / "lib"

    files = list(pyside6_libs_path.glob("libxcb-cursor.so*"))
    if files:
        print("libxcb-cursor files already exist in PySide6. No patching needed.")
        return

    this_folder = Path(__file__).parent.resolve()

    temp_folder = this_folder / "temp_pyside6_patch"
    temp_folder.mkdir(exist_ok=True)

    deb_file = download_file(temp_folder)
    extract_deb(deb_file, temp_folder)

    files = list(
        (temp_folder / "usr" / "lib" / "x86_64-linux-gnu").glob("libxcb-cursor.so*")
    )
    if not files:
        raise FileNotFoundError(
            "No libxcb-cursor files found in the extracted package."
        )

    for file in files:
        target_file = pyside6_libs_path / file.name
        if not target_file.exists():
            shutil.copy(file, target_file)
            print(f"copy to {target_file}")

    shutil.rmtree(temp_folder)


if __name__ == "__main__":
    patch_pyside6()
