"""PyInstaller runtime hook — pythonnet netfx icin ortam hazirla.

Problem 1: Frozen exe'de pythonnet python312.dll'i bulamiyor.
Problem 2: Internet'ten indirilen zip dosyalarindan cikan DLL'ler
           Zone.Identifier ADS ile engelleniyor, .NET Framework yukleyemiyor.

Cozum:
- _MEIPASS altindaki tum DLL'lerin Zone.Identifier ADS'ini temizle
- PYTHONNET_PYDLL env var ile python312.dll yolunu ver
"""
import os
import sys

# netfx kullan (varsayilan)
for key in ['PYTHONNET_RUNTIME', 'PYTHONNET_CORECLR_DOTNET_ROOT',
            'DOTNET_ROOT', 'PYTHONNET_CORECLR_RUNTIME_CONFIG']:
    os.environ.pop(key, None)

def _unblock_dlls(root):
    """Internet'ten indirilen DLL'lerin Zone.Identifier ADS'ini sil.
    Windows .NET Framework bu isaretli DLL'leri yukleyemiyor."""
    count = 0
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith('.dll'):
                ads = os.path.join(dirpath, fn) + ':Zone.Identifier'
                try:
                    os.remove(ads)
                    count += 1
                except (OSError, FileNotFoundError):
                    pass
    return count

if getattr(sys, 'frozen', False):
    base = sys._MEIPASS

    # Zone.Identifier temizle
    _unblocked = _unblock_dlls(base)

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
        f.write(f'unblocked_dlls={_unblocked}\n')
