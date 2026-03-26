# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for EdgeDesk.
#
# Build:
#   uv run pyinstaller edgedesk.spec
#
# The resulting executable lands in dist/edgedesk/ (one-dir) or dist/edgedesk.exe
# (one-file, requires --onefile flag below to be un-commented).
#
# Requirements before building:
#   - Tesseract must be installed; update TESSERACT_PATH below.
#   - sentence-transformers model cache should be in ~/.cache/huggingface
#     (it is bundled as a datas entry pointing to the cache dir).

import sys
from pathlib import Path

ROOT = Path(SPECPATH)  # noqa: F821 — PyInstaller injects this

# ---------------------------------------------------------------------------
# Hidden imports (dynamic imports that PyInstaller's static analyser misses)
# ---------------------------------------------------------------------------

HIDDEN_IMPORTS = [
    # SQLAlchemy dialects
    "sqlalchemy.dialects.sqlite",
    "aiosqlite",
    # LangChain / LangGraph
    "langchain_ollama",
    "langchain_community",
    "langgraph.prebuilt",
    "langchain.agents",
    # Sentence-transformers & FAISS
    "sentence_transformers",
    "faiss",
    # PyQt6 extras
    "PyQt6.QtSvg",
    "PyQt6.QtNetwork",
    "qtawesome",
    # Misc
    "keyboard",
    "pyperclip",
    "pyautogui",
    "mss",
    "pytesseract",
    "plyer.platforms.win.notification",
    "watchdog.observers",
    "watchdog.events",
    "apscheduler.schedulers.asyncio",
    "apscheduler.triggers.cron",
    "apscheduler.triggers.interval",
    "apscheduler.triggers.date",
    "qasync",
    "loguru",
]

# ---------------------------------------------------------------------------
# Data files to bundle
# ---------------------------------------------------------------------------

DATAS = [
    # UI assets
    (str(ROOT / "ui" / "assets"), "ui/assets"),
    # dotenv example (users can copy and fill in)
    (str(ROOT / ".env.example"), "."),
]

# Tesseract data files (Windows default install path — adjust if needed)
TESSERACT_PATH = Path(r"C:\Program Files\Tesseract-OCR")
if TESSERACT_PATH.exists():
    DATAS += [(str(TESSERACT_PATH / "tessdata"), "tessdata")]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=DATAS,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "IPython",
        "jupyter",
        "notebook",
        "scipy",
        "sklearn",
        "pandas",
        "PIL",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # one-dir mode
    name="edgedesk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # add an .ico path here if you have one
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="edgedesk",
)
