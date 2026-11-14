"""
Limitin Desktop — Build Script

Builds the application into a distributable .exe using PyInstaller.

Usage:
    python build.py

Output:
    dist/LimitinDesktop/LimitinDesktop.exe
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


ROOT = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(ROOT, "dist")
BUILD_DIR = os.path.join(ROOT, "build")
SPEC_FILE = os.path.join(ROOT, "limitin.spec")


def clean() -> None:
    """Remove previous build artefacts."""
    for d in (DIST_DIR, BUILD_DIR):
        if os.path.isdir(d):
            print(f"  Cleaning {d}")
            shutil.rmtree(d, ignore_errors=True)


def build() -> None:
    """Run PyInstaller with the spec file."""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        SPEC_FILE,
    ]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print(f"\n  BUILD FAILED (exit code {result.returncode})")
        sys.exit(result.returncode)


def post_build() -> None:
    """Copy config files and create required directories in the dist."""
    dist_app = os.path.join(DIST_DIR, "LimitinDesktop")
    if not os.path.isdir(dist_app):
        print("  WARNING: dist/LimitinDesktop not found — skipping post-build")
        return

    # Ensure the data and logs directories exist
    for subdir in ("data", "logs"):
        d = os.path.join(dist_app, subdir)
        os.makedirs(d, exist_ok=True)
        print(f"  Created {subdir}/")

    # Ensure config exists
    config_dir = os.path.join(dist_app, "config")
    if not os.path.isdir(config_dir):
        src = os.path.join(ROOT, "config")
        if os.path.isdir(src):
            shutil.copytree(src, config_dir)
            print("  Copied config/")


def main() -> None:
    """Run the full build pipeline."""
    print("=" * 60)
    print("  Limitin Desktop — Build")
    print("=" * 60)

    print("\n[1/3] Cleaning previous builds...")
    clean()

    print("\n[2/3] Building with PyInstaller...")
    build()

    print("\n[3/3] Post-build setup...")
    post_build()

    exe_path = os.path.join(DIST_DIR, "LimitinDesktop", "LimitinDesktop.exe")
    if os.path.isfile(exe_path):
        print(f"\n  BUILD SUCCESSFUL")
        print(f"  Output: {exe_path}")
        print(f"  Size:   {os.path.getsize(exe_path) / (1024 * 1024):.1f} MB")
    else:
        print("\n  BUILD COMPLETED but .exe not found at expected path")

    print("=" * 60)


if __name__ == "__main__":
    main()
