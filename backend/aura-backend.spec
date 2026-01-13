# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Aura Backend

Builds a standalone executable that runs the FastAPI server.
Usage: pyinstaller aura-backend.spec
"""

import sys
from pathlib import Path

# Get the backend directory
backend_dir = Path(SPECPATH)

a = Analysis(
    ['main.py'],
    pathex=[str(backend_dir)],
    binaries=[],
    datas=[
        # Include all Python packages
        ('agent', 'agent'),
        ('services', 'services'),
    ],
    hiddenimports=[
        # FastAPI and dependencies
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
        'fastapi',
        'starlette',
        'pydantic',
        'pydantic_core',
        'pydantic_ai',
        'sse_starlette',
        
        # HTTP and async
        'httpx',
        'httpcore',
        'anyio',
        'sniffio',
        'h11',
        'certifi',
        
        # Anthropic
        'anthropic',
        
        # Research tools
        'arxiv',
        'fitz',  # PyMuPDF
        
        # Docker
        'docker',
        
        # Git
        'git',
        'gitdb',
        
        # Utils
        'dotenv',
        'multipart',
        
        # Agent modules
        'agent.pydantic_agent',
        'agent.streaming',
        'agent.compression',
        'agent.hitl',
        'agent.steering',
        'agent.planning',
        'agent.vibe_state',
        'agent.colorist',
        'agent.providers',
        'agent.providers.colorist',
        'agent.subagents',
        'agent.subagents.base',
        'agent.subagents.research',
        'agent.subagents.compiler',
        'agent.subagents.planner',
        'agent.tools',
        'agent.tools.pdf_reader',
        
        # Services
        'services.docker',
        'services.project',
        'services.memory',
        'services.semantic_scholar',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_disable_logfire.py'],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        # Exclude logfire - causes source inspection issues with PyInstaller
        'logfire',
        'logfire.integrations',
        'logfire.integrations.pydantic',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='aura-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for logging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
