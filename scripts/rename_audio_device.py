"""
Sanal ses cihazının Windows'taki görünen ismini değiştirir.

Bu script, MMDevice registry'sindeki cihaz adını programmatik olarak günceller.
Değişiklik kalıcıdır — reboot sonrası da geçerlidir.
Discord, Windows Ses Ayarları ve tüm uygulamalarda yeni isim görünür.

Yönetici hakları gerektirir (HKLM registry yazma).

Kullanım:
    python rename_audio_device.py                    # Etkileşimli mod
    python rename_audio_device.py --list             # Tüm cihazları listele
    python rename_audio_device.py --target "VB-Audio Virtual Cable" --name "Mik Audio"
"""

import winreg
import sys
import argparse
import ctypes
import os

# Türkçe karakter desteği
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# MMDevice registry sabitleri
MMDEVICES_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture"
# PKEY_Device_DeviceDesc — Windows Ses Ayarları'nda görünen açıklama
PKEY_DEVICE_DESC = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"
# PKEY_DeviceInterface_FriendlyName — arayüz/donanım adı
PKEY_IFACE_NAME = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"
# PKEY_Device_FriendlyName — tam görünen isim ("Mikrofon (VB-Audio Virtual Cable)")
PKEY_FRIENDLY_NAME = "{a45c254e-df1c-4efd-8020-67d146a850e0},14"


def is_admin() -> bool:
    """Yönetici hakları ile çalışıp çalışmadığını kontrol eder."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def list_capture_devices() -> list[dict]:
    """Tüm kayıt (capture) cihazlarını listeler."""
    devices = []
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MMDEVICES_PATH)
    except OSError as e:
        print(f"Registry açılamadı: {e}")
        return devices

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
        except OSError:
            continue

        device = {"guid": guid}
        for field, key in [
            ("desc", PKEY_DEVICE_DESC),
            ("interface", PKEY_IFACE_NAME),
            ("friendly", PKEY_FRIENDLY_NAME),
        ]:
            try:
                device[field] = winreg.QueryValueEx(props, key)[0]
            except OSError:
                device[field] = ""

        winreg.CloseKey(props)
        devices.append(device)

    winreg.CloseKey(root)
    return devices


def find_device_by_interface(devices: list[dict], target: str) -> dict | None:
    """Arayüz adına göre cihaz bulur (büyük/küçük harf duyarsız, kısmi eşleşme)."""
    target_lower = target.lower()
    for dev in devices:
        if target_lower in dev.get("interface", "").lower():
            return dev
    return None


def rename_device(guid: str, new_desc: str, new_interface: str | None = None) -> bool:
    """
    Cihaz ismini registry'de günceller.

    Args:
        guid: Cihazın MMDevice GUID'i
        new_desc: Yeni cihaz açıklaması (ör. "Mik Audio Input")
        new_interface: Yeni arayüz adı (ör. "Mik Audio"). None ise değiştirilmez.

    Returns:
        True başarılıysa
    """
    props_path = f"{MMDEVICES_PATH}\\{guid}\\Properties"

    try:
        props = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            props_path,
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_READ,
        )
    except PermissionError:
        print("Hata: Yönetici hakları gerekli. Programı yönetici olarak çalıştırın.")
        return False
    except OSError as e:
        print(f"Registry anahtarı açılamadı: {e}")
        return False

    try:
        # Cihaz açıklamasını güncelle
        winreg.SetValueEx(props, PKEY_DEVICE_DESC, 0, winreg.REG_SZ, new_desc)
        print(f"  DeviceDesc -> {new_desc}")

        # Arayüz adını güncelle
        if new_interface:
            winreg.SetValueEx(props, PKEY_IFACE_NAME, 0, winreg.REG_SZ, new_interface)
            print(f"  InterfaceName -> {new_interface}")

        # Tam görünen ismi güncelle: "Desc (Interface)"
        iface = new_interface
        if not iface:
            try:
                iface = winreg.QueryValueEx(props, PKEY_IFACE_NAME)[0]
            except OSError:
                iface = ""
        if iface:
            full_name = f"{new_desc} ({iface})"
        else:
            full_name = new_desc
        winreg.SetValueEx(props, PKEY_FRIENDLY_NAME, 0, winreg.REG_SZ, full_name)
        print(f"  FriendlyName -> {full_name}")

    except OSError as e:
        print(f"Registry yazma hatası: {e}")
        winreg.CloseKey(props)
        return False

    winreg.CloseKey(props)
    return True


def interactive_mode(devices: list[dict]) -> None:
    """Kullanıcıya cihaz seçtirip yeni isim sorar."""
    print("\n Kayıt (Capture) Cihazları:")
    print("-" * 60)
    for idx, dev in enumerate(devices):
        desc = dev.get("desc", "?")
        iface = dev.get("interface", "?")
        print(f"  [{idx + 1}] {desc} — {iface}")
    print("-" * 60)

    try:
        choice = int(input("\nİsmi değiştirilecek cihazın numarası: ")) - 1
        if choice < 0 or choice >= len(devices):
            print("Geçersiz seçim.")
            return
    except (ValueError, EOFError):
        print("Geçersiz giriş.")
        return

    dev = devices[choice]
    print(f"\nSeçilen: {dev['desc']} — {dev['interface']}")

    try:
        new_name = input("Yeni cihaz ismi (ör. 'Mik Audio'): ").strip()
    except EOFError:
        return

    if not new_name:
        print("İsim boş olamaz.")
        return

    print(f"\nDeğiştiriliyor...")
    if rename_device(dev["guid"], new_name, new_name):
        print(f"\n✓ Başarılı! Cihaz artık '{new_name}' olarak görünecek.")
        print("  Not: Bazı uygulamalarda değişikliğin görünmesi için")
        print("  uygulamayı yeniden başlatmanız gerekebilir.")
    else:
        print("\n✗ İsim değiştirilemedi.")


def main():
    parser = argparse.ArgumentParser(
        description="Windows ses cihazı ismini değiştirir"
    )
    parser.add_argument("--list", action="store_true", help="Cihazları listele")
    parser.add_argument("--target", type=str, help="Hedef cihazın mevcut adı (kısmi eşleşme)")
    parser.add_argument("--name", type=str, help="Yeni cihaz adı")
    args = parser.parse_args()

    if not is_admin() and not args.list:
        print("⚠ Bu script yönetici hakları gerektirir.")
        print("  Sağ tık → 'Yönetici olarak çalıştır' ile açın.")
        print("  Veya: --list ile sadece cihazları listeleyebilirsiniz.\n")
        # Listeleme izinsiz de çalışır, devam et
        if not args.list and not args.target:
            sys.exit(1)

    devices = list_capture_devices()
    if not devices:
        print("Hiç kayıt cihazı bulunamadı.")
        sys.exit(1)

    if args.list:
        print(f"\n{len(devices)} kayıt cihazı bulundu:\n")
        for dev in devices:
            desc = dev.get("desc", "?")
            iface = dev.get("interface", "?")
            friendly = dev.get("friendly", "")
            print(f"  • {desc} — {iface}")
            if friendly:
                print(f"    Tam ad: {friendly}")
            print(f"    GUID: {dev['guid']}")
            print()
        return

    if args.target and args.name:
        dev = find_device_by_interface(devices, args.target)
        if not dev:
            print(f"'{args.target}' içeren cihaz bulunamadı.")
            print("Mevcut cihazlar:")
            for d in devices:
                print(f"  • {d.get('interface', '?')}")
            sys.exit(1)

        print(f"Cihaz bulundu: {dev['desc']} — {dev['interface']}")
        print(f"Yeni isim: {args.name}")
        if rename_device(dev["guid"], args.name, args.name):
            print(f"\n✓ Başarılı!")
        else:
            sys.exit(1)
        return

    # Etkileşimli mod
    interactive_mode(devices)


if __name__ == "__main__":
    main()
