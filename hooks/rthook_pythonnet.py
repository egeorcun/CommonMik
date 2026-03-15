"""PyInstaller runtime hook — pythonnet netfx icin Python DLL yolunu ayarla.

Problem: Frozen exe'de pythonnet (netfx) Python.Runtime.dll'i yuklerken
python312.dll'i bulamiyor.

Cozum: PYTHONNET_PYDLL env var ile python312.dll yolunu ver.
netfx (.NET Framework 4.8) kullanilir — coreclr degil.
"""
import os
import sys

# coreclr sorunlu — netfx kullan (varsayilan, mudahale etme)
# PYTHONNET_RUNTIME'i ayarlamiyoruz, varsayilan 'netfx' kalsin
for key in ['PYTHONNET_RUNTIME', 'PYTHONNET_CORECLR_DOTNET_ROOT', 
            'DOTNET_ROOT', 'PYTHONNET_CORECLR_RUNTIME_CONFIG']:
    os.environ.pop(key, None)

if getattr(sys, 'frozen', False):
    base = sys._MEIPASS

    # Python DLL yolunu pythonnet'e bildir
    python_dll = f'python{sys.version_info.major}{sys.version_info.minor}.dll'
    python_dll_path = os.path.join(base, python_dll)
    if os.path.exists(python_dll_path):
        os.environ['PYTHONNET_PYDLL'] = python_dll_path

    # DLL arama yoluna _MEIPASS ekle
    os.environ['PATH'] = base + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(base)

    # Debug log
    _log_dir = os.path.join(os.environ.get('APPDATA', base), 'CommonMik')
    os.makedirs(_log_dir, exist_ok=True)
    with open(os.path.join(_log_dir, 'rthook.log'), 'w') as f:
        f.write(f'runtime=netfx (default)\n')
        f.write(f'PYTHONNET_PYDLL={os.environ.get("PYTHONNET_PYDLL", "not set")}\n')
        f.write(f'python_dll_exists={os.path.exists(python_dll_path)}\n')
        f.write(f'_MEIPASS={base}\n')
