# -*- mode: python ; coding: utf-8 -*-
"""
CommonMik — PyInstaller build spec.

Kullanim:
    pyinstaller build.spec
"""

import os

PROJECT_ROOT = os.path.abspath('.')

a = Analysis(
    ['main.py'],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        ('ui', 'ui'),
    ],
    hiddenimports=[
        'webview',
        'webview.platforms.edgechromium',
        'clr_loader',
        'pythonnet',
        'comtypes',
        'comtypes.stream',
        'pycaw',
        'pycaw.pycaw',
        'sounddevice',
        '_sounddevice_data',
        'core.loopback',
        'scipy',
        'scipy.signal',
        'pystray',
        'pystray._win32',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hooks/rthook_pythonnet.py'],
    excludes=[
        'tkinter',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CommonMik',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CommonMik',
)
