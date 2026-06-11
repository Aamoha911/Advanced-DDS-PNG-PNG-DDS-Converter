"""
Build a standalone .exe using PyInstaller.

Usage:
    pip install pyinstaller
    python build_exe.py

Output: dist/ImageConverter.exe
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path


def build():
    # ensure we're in the project root
    root = Path(__file__).resolve().parent
    os.chdir(root)

    # install the package in editable mode so PyInstaller can find it
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        check=True, capture_output=True
    )

    src_pkg = root / "src" / "img_converter"
    if not src_pkg.is_dir():
        print("ERROR: src/img_converter/ not found")
        sys.exit(1)

    icon_path = root / "icon.ico"
    icon_args = ["--icon", str(icon_path)] if icon_path.is_file() else []

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",  # no console window
        "--name", "ImageConverter",
        "--distpath", str(root / "dist"),
        "--workpath", str(root / "build_tmp"),
        "--specpath", str(root / "build_tmp"),
        "--add-data", f"{src_pkg}{os.pathsep}img_converter",
        "--hidden-import", "PyQt5.sip",
        "--hidden-import", "PIL._tkinter_finder",
        *icon_args,
        str(src_pkg / "__main__.py"),
    ]

    print("Running PyInstaller...")
    print(" ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)

    exe = root / "dist" / "ImageConverter.exe"
    if exe.is_file():
        print(f"\nSUCCESS: {exe}")
        print(f"  Size: {exe.stat().st_size / 1024 / 1024:.1f} MB")
    else:
        print("\nBuild completed but .exe not found in dist/")

    # cleanup temp build folder
    shutil.rmtree(root / "build_tmp", ignore_errors=True)


if __name__ == "__main__":
    build()
