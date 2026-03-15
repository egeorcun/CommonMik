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
