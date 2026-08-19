# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

block_cipher = None

# Project root (backend/)
backend_root = Path(os.path.abspath(SPECPATH))

a = Analysis(
    [str(backend_root / 'app' / 'main.py')],
    pathex=[str(backend_root)],
    binaries=[],
    datas=[
        # System prompts and templates
        (str(backend_root / '_system'), '_system'),
        (str(backend_root / '_templates'), '_templates'),
        # Skill definitions
        (str(backend_root / 'skills'), 'skills'),
        # Environment file (if exists)
        ('.env', '.'),
    ],
    hiddenimports=[
        # Uvicorn
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',

        # FastAPI and dependencies
        'fastapi',
        'starlette',
        'pydantic',
        'pydantic_settings',

        # Database
        'aiosqlite',
        'sqlite3',

        # ChromaDB and embeddings
        'chromadb',
        'sentence_transformers',

        # Auth
        'jwt',
        'passlib',
        'passlib.hash',
        'bcrypt',

        # HTTP client
        'httpx',
        'aiohttp',

        # File handling
        'python_multipart',

        # App core
        'app.core.config',
        'app.core.database',
        'app.core.events',
        'app.core.exceptions',
        'app.core.dependencies',
        'app.shared.logger',
        'app.shared.id_utils',

        # Feature routers (explicit imports for PyInstaller)
        'app.features.auth.router',
        'app.features.auth.service',
        'app.features.auth.repository',
        'app.features.auth.schemas',
        'app.features.projects.router',
        'app.features.projects.service',
        'app.features.projects.repository',
        'app.features.projects.schemas',
        'app.features.ingestion.router',
        'app.features.ingestion.service',
        'app.features.ingestion.repository',
        'app.features.ingestion.schemas',
        'app.features.processing.router',
        'app.features.processing.service',
        'app.features.processing.repository',
        'app.features.processing.schemas',
        'app.features.embedding.router',
        'app.features.embedding.service',
        'app.features.embedding.repository',
        'app.features.embedding.schemas',
        'app.features.documents.router',
        'app.features.documents.service',
        'app.features.documents.repository',
        'app.features.documents.schemas',
        'app.features.search.router',
        'app.features.search.service',
        'app.features.search.repository',
        'app.features.search.schemas',
        'app.features.chat.router',
        'app.features.chat.service',
        'app.features.chat.repository',
        'app.features.chat.schemas',
        'app.features.chat.prompt_builder',
        'app.features.chat.web_search',
        'app.features.graph.router',
        'app.features.graph.service',
        'app.features.graph.repository',
        'app.features.graph.schemas',
        'app.features.literature.router',
        'app.features.literature.service',
        'app.features.literature.repository',
        'app.features.literature.schemas',
        'app.features.literature.metadata',
        'app.features.models.router',
        'app.features.models.service',
        'app.features.models.repository',
        'app.features.models.schemas',
        'app.features.skills.router',
        'app.features.skills.service',
        'app.features.skills.repository',
        'app.features.skills.schemas',
        'app.features.settings.router',
        'app.features.settings.service',
        'app.features.settings.repository',
        'app.features.settings.schemas',
        'app.features.actions.router',
        'app.features.actions.service',
        'app.features.actions.repository',
        'app.features.actions.schemas',

        # Web search
        'bs4',
        'lxml',

        # Logger
        'colorlog',

        # UUID
        'uuid',

        # JSON
        'json',

        # Datetime
        'datetime',

        # Re (regex)
        're',

        # collections
        'collections',

        # hashlib
        'hashlib',

        # Optional: fastembed (may fail to import)
        'fastembed',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude tkinter (not needed)
        'tkinter',
        'tkinter.Tk',
        'tkinter.ttk',
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
    name='notebook-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='notebook-backend',
)
