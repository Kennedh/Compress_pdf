# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata

project = Path(SPECPATH)
sys.path.insert(0, str(project))
from app_version import VERSION

datas, binaries, hiddenimports = collect_all(
    "pymupdf",
    include_py_files=False,
    exclude_datas=["**/layout/**"],
    filter_submodules=lambda name: name != "pymupdf.__main__" and not name.startswith("pymupdf.layout"),
)
datas += copy_metadata("PyMuPDF")
datas += [(str(project / "README.md"), "."), (str(project / "THIRD_PARTY_NOTICES.md"), ".")]

a = Analysis(
    [str(project / "compress_pdf.py")],
    pathex=[str(project)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pymupdf.layout", "pymupdf4llm", "onnxruntime", "numpy", "pandas",
        "matplotlib", "PIL", "fontTools", "lxml", "PySide6", "PyQt6", "PyQt5",
        "kivy", "pytest", "IPython",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="CompressPDF",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=sys.platform not in ("win32", "darwin"),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="CompressPDF")
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="CompressPDF.app",
        bundle_identifier="com.kennedh.compresspdf",
        info_plist={
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
        },
    )
