"""PyInstaller runtime hook — pythonnet icin coreclr kullan (netfx frozen exe'de bozuk)."""
import os
import sys

# netfx (.NET Framework) frozen exe'de Python.Runtime.dll'i yukleyemiyor.
# coreclr (.NET Core) ile calismasini zorluyoruz.
os.environ['PYTHONNET_RUNTIME'] = 'coreclr'

if getattr(sys, 'frozen', False):
    base = sys._MEIPASS
    os.environ['PATH'] = base + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(base)

    # Debug: log dosyasina yaz
    _log_dir = os.path.join(os.environ.get('APPDATA', base), 'CommonMik')
    os.makedirs(_log_dir, exist_ok=True)
    with open(os.path.join(_log_dir, 'rthook.log'), 'w') as f:
        f.write(f'PYTHONNET_RUNTIME={os.environ.get("PYTHONNET_RUNTIME")}\n')
        f.write(f'_MEIPASS={base}\n')
        f.write(f'PATH includes _MEIPASS: {base in os.environ["PATH"]}\n')
