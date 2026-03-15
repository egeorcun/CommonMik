"""
Mik Audio — Ana giris noktasi.

pywebview native pencere + system tray + Python ses motoru.
Tek instance: ayni anda sadece bir MikAudio calisiyor olabilir.
"""

import os
import sys
import logging
import json
import threading
import ctypes

# ── Single instance mutex ──
_mutex = None

def _ensure_single_instance():
    """Ayni anda sadece bir instance calismasini saglar."""
    global _mutex
    kernel32 = ctypes.windll.kernel32
    _mutex = kernel32.CreateMutexW(None, True, "MikAudio_SingleInstance_Mutex")
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        # Zaten calisiyor — mevcut pencereyi one getirmeyi dene
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, "Mik Audio")
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        sys.exit(0)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mik")

# Proje kokunu Python path'e ekle
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.audio_engine import AudioEngine

# ── Globals ──
engine = AudioEngine()

# ── Settings path ──
SETTINGS_DIR = os.path.join(os.environ.get("APPDATA", PROJECT_ROOT), "MikAudio")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")


def _save_settings(settings: dict):
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        logger.info(f"Settings saved")
    except Exception as e:
        logger.error(f"Settings save error: {e}")


def _load_settings() -> dict | None:
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Settings load error: {e}")
    return None


# ═══════════════════════════════════════
#  pywebview JS API — JS'den cagrilir
# ═══════════════════════════════════════

class Api:
    """pywebview expose — her metod JS'den window.pywebview.api.xxx() ile cagrilir."""

    def get_audio_apps(self):
        try:
            from pycaw.pycaw import AudioUtilities
            sessions = AudioUtilities.GetAllSessions()
            apps = []
            seen = set()
            for s in sessions:
                if s.Process and s.Process.name() not in seen:
                    name = s.Process.name()
                    if name.lower() in ("audiodg.exe", "svchost.exe"):
                        continue
                    seen.add(name)
                    apps.append({
                        "pid": s.ProcessId,
                        "name": name.replace(".exe", ""),
                        "exe": name,
                    })
            return apps
        except Exception as e:
            logger.error(f"get_audio_apps: {e}")
            return []

    def get_input_devices(self):
        try:
            return engine.get_input_devices()
        except Exception as e:
            logger.error(f"get_input_devices: {e}")
            return []

    def get_output_devices(self):
        try:
            return engine.get_output_devices()
        except Exception as e:
            logger.error(f"get_output_devices: {e}")
            return []

    def add_microphone(self, device_index, name=""):
        try:
            source_id = engine.add_microphone(int(device_index), name)
            return {"ok": True, "id": source_id}
        except Exception as e:
            logger.error(f"add_microphone: {e}")
            return {"ok": False, "error": str(e)}

    def add_loopback(self, device_index=-1, name="Sistem Sesi", pid=None):
        try:
            if pid is not None:
                pid = int(pid)
            source_id = engine.add_loopback(int(device_index), name, pid=pid)
            if not source_id:
                return {"ok": False, "error": "PID belirtilmedi"}
            return {"ok": True, "id": source_id}
        except Exception as e:
            logger.error(f"add_loopback: {e}")
            return {"ok": False, "error": str(e)}

    def remove_source(self, source_id):
        try:
            engine.remove_source(source_id)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def set_volume(self, source_id, volume):
        try:
            engine.set_volume(source_id, float(volume))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def set_mute(self, source_id, muted):
        try:
            engine.set_mute(source_id, bool(muted))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def set_master_volume(self, volume):
        try:
            engine.master_volume = max(0.0, min(2.0, float(volume)))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def set_output_device(self, device_index):
        try:
            engine.set_output_device(int(device_index))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def start_engine(self):
        try:
            engine.start()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def stop_engine(self):
        try:
            engine.stop()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_levels(self):
        try:
            return engine.get_levels()
        except Exception:
            return {}

    def get_status(self):
        return {
            "running": engine.running,
            "source_count": len(engine.sources),
            "output_device": engine.output_device,
            "master_volume": engine.master_volume,
        }

    def save_settings(self):
        try:
            import sounddevice as sd

            output_name = None
            if engine.output_device is not None:
                try:
                    dev = sd.query_devices(engine.output_device)
                    output_name = dev["name"]
                except Exception:
                    pass

            sources = []
            for sid, src in engine.sources.items():
                entry = {
                    "id": sid,
                    "name": src.name,
                    "type": src.source_type,
                    "volume": src.volume,
                    "muted": src.muted,
                }
                if src.source_type == "microphone":
                    try:
                        dev = sd.query_devices(src.device_index)
                        entry["device_name"] = dev["name"]
                    except Exception:
                        entry["device_name"] = src.name
                elif src.source_type == "loopback":
                    entry["exe_name"] = src.name + ".exe"
                sources.append(entry)

            # Mevcut ayarlari oku (lang korumak icin)
            existing = _load_settings() or {}

            settings = {
                "output_device_name": output_name,
                "master_volume": engine.master_volume,
                "sources": sources,
                "lang": existing.get("lang", "en"),
            }
            _save_settings(settings)
            return {"ok": True}
        except Exception as e:
            logger.error(f"save_settings: {e}")
            return {"ok": False, "error": str(e)}

    def save_lang(self, lang):
        """Dil tercihini kaydeder."""
        try:
            settings = _load_settings() or {}
            settings["lang"] = lang
            _save_settings(settings)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def load_settings(self):
        try:
            settings = _load_settings()
            if not settings:
                return {"ok": False, "error": "no_settings"}

            import sounddevice as sd

            result = {
                "ok": True,
                "output_device_index": None,
                "output_device_name": settings.get("output_device_name", ""),
                "master_volume": settings.get("master_volume", 1.0),
                "lang": settings.get("lang", "en"),
                "sources": [],
            }

            out_name = settings.get("output_device_name")
            if out_name:
                for i, dev in enumerate(sd.query_devices()):
                    if dev["max_output_channels"] > 0 and dev["name"] == out_name:
                        result["output_device_index"] = i
                        break

            for entry in settings.get("sources", []):
                restored = {
                    "name": entry["name"],
                    "type": entry["type"],
                    "volume": entry.get("volume", 1.0),
                    "muted": entry.get("muted", False),
                    "found": False,
                }

                if entry["type"] == "microphone":
                    dev_name = entry.get("device_name", "")
                    for i, dev in enumerate(sd.query_devices()):
                        if dev["max_input_channels"] > 0 and dev["name"] == dev_name:
                            restored["device_index"] = i
                            restored["found"] = True
                            break

                elif entry["type"] == "loopback":
                    exe = entry.get("exe_name", entry["name"] + ".exe")
                    try:
                        from pycaw.pycaw import AudioUtilities
                        for s in AudioUtilities.GetAllSessions():
                            if s.Process and s.Process.name().lower() == exe.lower():
                                restored["pid"] = s.ProcessId
                                restored["found"] = True
                                break
                    except Exception:
                        pass

                result["sources"].append(restored)

            return result
        except Exception as e:
            logger.error(f"load_settings: {e}")
            return {"ok": False, "error": str(e)}

    def rename_audio_device(self, target_name, new_name):
        import winreg
        MMDEVICES_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture"
        PKEY_DEVICE_DESC = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"
        PKEY_IFACE_NAME = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"
        PKEY_FRIENDLY_NAME = "{a45c254e-df1c-4efd-8020-67d146a850e0},14"
        try:
            root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MMDEVICES_PATH)
            found_guid = None
            i = 0
            while True:
                try:
                    guid = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                props_path = f"{MMDEVICES_PATH}\\{guid}\\Properties"
                try:
                    props = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, props_path)
                    try:
                        iface = winreg.QueryValueEx(props, PKEY_IFACE_NAME)[0]
                    except OSError:
                        iface = ""
                    try:
                        desc = winreg.QueryValueEx(props, PKEY_DEVICE_DESC)[0]
                    except OSError:
                        desc = ""
                    winreg.CloseKey(props)
                    if target_name.lower() in iface.lower() or target_name.lower() in desc.lower():
                        found_guid = guid
                        break
                except OSError:
                    continue
            winreg.CloseKey(root)

            if not found_guid:
                return {"ok": False, "error": f"'{target_name}' not found"}

            props_path = f"{MMDEVICES_PATH}\\{found_guid}\\Properties"
            props = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, props_path, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ,
            )
            winreg.SetValueEx(props, PKEY_DEVICE_DESC, 0, winreg.REG_SZ, new_name)
            winreg.SetValueEx(props, PKEY_IFACE_NAME, 0, winreg.REG_SZ, new_name)
            winreg.SetValueEx(props, PKEY_FRIENDLY_NAME, 0, winreg.REG_SZ, f"{new_name} ({new_name})")
            winreg.CloseKey(props)
            return {"ok": True, "guid": found_guid}
        except PermissionError:
            return {"ok": False, "error": "Admin required"}
        except Exception as e:
            logger.error(f"rename_audio_device: {e}")
            return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════
#  System Tray
# ═══════════════════════════════════════

_window = None
_tray_icon = None


def _create_tray_icon():
    """Sistem tepsisi ikonu olusturur."""
    global _tray_icon
    try:
        import pystray
        from PIL import Image, ImageDraw

        # Basit ikon ciz — mor daire
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, 60, 60], fill=(139, 92, 246, 255))
        draw.ellipse([18, 18, 46, 46], fill=(30, 30, 50, 255))

        def on_show(icon, item):
            if _window:
                _window.show()

        def on_quit(icon, item):
            engine.stop()
            icon.stop()
            if _window:
                _window.destroy()

        menu = pystray.Menu(
            pystray.MenuItem("Mik Audio", on_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Kapat", on_quit),
        )

        _tray_icon = pystray.Icon("MikAudio", img, "Mik Audio", menu)
        _tray_icon.run()
    except Exception as e:
        logger.error(f"Tray icon error: {e}")


def _on_closing():
    """Pencere kapatildiginda gizle, cikmak icin tray'den."""
    if _window:
        _window.hide()
    return False  # Pencereyi yok etme


# ═══════════════════════════════════════
#  Main
# ═══════════════════════════════════════

def main():
    global _window
    _ensure_single_instance()
    import webview

    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = PROJECT_ROOT

    ui_dir = os.path.join(base_dir, "ui")
    index_path = os.path.join(ui_dir, "index.html")

    logger.info("Mik Audio starting...")

    api = Api()

    _window = webview.create_window(
        "Mik Audio",
        url=index_path,
        js_api=api,
        width=520,
        height=700,
        resizable=True,
        min_size=(400, 500),
        background_color="#0a0a0f",
        text_select=False,
    )

    _window.events.closing += _on_closing

    # Tray icon'u ayri thread'de baslat
    tray_thread = threading.Thread(target=_create_tray_icon, daemon=True)
    tray_thread.start()

    webview.start(debug=False)


if __name__ == "__main__":
    main()
