# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Limitin Desktop.

Build command:
    pyinstaller limitin.spec

Or with the build script:
    python build.py
"""

import os
import sys
import importlib

# ── Paths ──────────────────────────────────────────────────────────────────
block_cipher = None
ROOT = os.path.abspath(".")

# Find customtkinter package path for data files
ctk_path = os.path.dirname(importlib.import_module("customtkinter").__file__)

a = Analysis(
    ["main.py"],
    pathex=[ROOT],
    binaries=[],
    datas=[
        # CustomTkinter theme data
        (ctk_path, "customtkinter"),
        # App config
        (os.path.join(ROOT, "config"), "config"),
        # Themes
        (os.path.join(ROOT, "themes"), "themes"),
    ],
    hiddenimports=[
        "customtkinter",
        "pystray",
        "pystray._win32",
        "PIL",
        "PIL._tkinter_finder",
        "psutil",
        "win32gui",
        "win32process",
        "win32api",
        "win32con",
        "matplotlib",
        "matplotlib.backends.backend_tkagg",
        "numpy",
        "icoextract",
        "sqlite3",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest", "unittest", "test", "tests",
        "tkinter.test",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LimitinDesktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/limitin.ico",  # Uncomment if you have an icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LimitinDesktop",
)
