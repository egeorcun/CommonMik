"""PyInstaller runtime hook — pythonnet icin ortam hazirla."""
import os
import sys

if getattr(sys, 'frozen', False):
    base = sys._MEIPASS
    # pythonnet'in Python DLL'ini bulabilmesi icin
    python_dll = f'python{sys.version_info.major}{sys.version_info.minor}.dll'
    os.environ['PYTHONNET_PYDLL'] = os.path.join(base, python_dll)
    # CLR'nin bagimliliklari bulabilmesi icin _MEIPASS'i PATH'e ekle
    os.environ['PATH'] = base + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(base)
