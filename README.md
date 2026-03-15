# Mik Audio

Per-application audio mixer for Windows. Capture audio from specific apps (Spotify, Chrome, games), mix with your microphone, and output to a virtual microphone for Discord, Zoom, or any voice chat.

## Features

- **Per-app audio capture** — Select exactly which applications to capture using WASAPI Process Loopback (Windows 10 2004+)
- **Microphone mixing** — Combine your mic input with app audio into a single virtual microphone output
- **Independent volume controls** — Adjust each source separately with real-time level meters
- **Virtual microphone output** — Routes mixed audio through VB-Audio Virtual Cable
- **WASAPI exclusive mode** — Native 48kHz pipeline, zero resampling when using WASAPI devices
- **Sinc resampling** — High-quality polyphase FIR resampling when sample rates differ
- **System tray** — Minimize to tray, keeps running in background
- **Auto-save settings** — Output device, sources, volumes, mute states persist across sessions
- **Native Windows app** — Uses WebView2 (Edge Chromium), no browser dependency
- **Dark theme UI** — Glassmorphism design with real-time audio meters

## How It Works

```
Spotify  ───────┐
Chrome   ───────┤──→  Mik Audio  ──→  CABLE Input  ──→  Discord mic input
Your mic ───────┘      (mixer)        (virtual cable)    (CABLE Output)
```

Windows audio output stays on your headphones — Mik Audio captures app audio via WASAPI Process Loopback without redirecting system output.

## Requirements

- Windows 10 version 2004+ / Windows 11
- [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) (free)

## Installation

### Pre-built (Recommended)

1. Download the latest release from [Releases](https://github.com/egeorcun/CommonMik/releases)
2. Install [VB-Audio Virtual Cable](https://vb-audio.com/Cable/)
3. Run `MikAudio.exe`

### From Source

```bash
git clone https://github.com/egeorcun/CommonMik.git
cd mik-audio
pip install -r requirements.txt
python main.py
```

### Build Executable

```bash
pip install -r requirements.txt
pyinstaller build.spec
# Output: dist/MikAudio/MikAudio.exe
```

## Usage

1. **Select output device** — Choose `CABLE Input (VB-Audio Virtual Cable) [WASAPI]` as the virtual microphone output
2. **Add sources** — Click ➕ to add your microphone and/or application audio
3. **Start engine** — Click the Start button
4. **In Discord** — Set your input device to `CABLE Output (VB-Audio Virtual Cable)`

### Tips

- Keep all volumes at **100% (1.0)** for cleanest signal — adjust volume at source (Spotify) or destination (Discord)
- Always select **WASAPI** devices for lowest latency and best quality
- Close the window to minimize to system tray — right-click tray icon to fully quit

## Architecture

```
core/
  audio_engine.py  — AudioFIFO ring buffer, AudioSource, AudioEngine mixer
  loopback.py      — WASAPI Process Loopback via ActivateAudioInterfaceAsync
ui/
  index.html       — Main UI layout
  style.css        — Dark glassmorphism theme
  app.js           — Frontend controller (pywebview JS API bridge)
main.py            — pywebview window + system tray + Python↔JS API
```

**Audio pipeline:** 48kHz float32 stereo throughout. Per-app capture via `ActivateAudioInterfaceAsync` COM API. Thread-safe FIFO ring buffers between capture threads and output callback. Sinc resampling (scipy `resample_poly`) when device sample rates differ.

## License

MIT

---

# Mik Audio (Türkçe)

Windows için uygulama bazlı ses karıştırıcı. Spotify, Chrome, oyun gibi uygulamaların sesini yakalar, mikrofonunla karıştırır ve Discord/Zoom'da sanal mikrofon olarak kullanmanı sağlar.

## Özellikler

- **Uygulama bazlı ses yakalama** — Hangi uygulamaların sesini alacağını sen seçersin (WASAPI Process Loopback)
- **Mikrofon karıştırma** — Mikrofon + uygulama sesleri tek sanal mikrofona birleştirilir
- **Bağımsız ses kontrolleri** — Her kaynağın sesini ayrı ayrı ayarla, gerçek zamanlı seviye göstergesi
- **Sanal mikrofon çıkışı** — VB-Audio Virtual Cable üzerinden çalışır
- **WASAPI modu** — 48kHz native pipeline, sıfır resampling
- **Sinc resampling** — Farklı sample rate'lerde yüksek kaliteli dönüşüm
- **Sistem tepsisi** — Pencereyi kapat, arka planda çalışmaya devam etsin
- **Otomatik ayar kaydetme** — Çıkış cihazı, kaynaklar, ses seviyeleri otomatik kaydedilir
- **Native Windows uygulaması** — WebView2 kullanır, tarayıcı gerekmez
- **Koyu tema arayüz** — Glassmorphism tasarım, gerçek zamanlı ses metre

## Nasıl Çalışır

```
Spotify  ───────┐
Chrome   ───────┤──→  Mik Audio  ──→  CABLE Input  ──→  Discord mikrofon
Mikrofon ───────┘     (karıştırıcı)   (sanal kablo)     (CABLE Output seç)
```

Windows ses çıkışın kulaklığında kalır — Mik Audio, uygulamaların sesini WASAPI ile yakalar, sistem çıkışını değiştirmez.

## Gereksinimler

- Windows 10 sürüm 2004+ / Windows 11
- [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) (ücretsiz)

## Kurulum

### Hazır Exe (Önerilen)

1. [Releases](https://github.com/egeorcun/CommonMik/releases) sayfasından son sürümü indir
2. [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) kur
3. `MikAudio.exe` çalıştır

### Kaynak Koddan

```bash
git clone https://github.com/egeorcun/CommonMik.git
cd mik-audio
pip install -r requirements.txt
python main.py
```

### Exe Derleme

```bash
pip install -r requirements.txt
pyinstaller build.spec
# Çıktı: dist/MikAudio/MikAudio.exe
```

## Kullanım

1. **Çıkış cihazı seç** — `CABLE Input (VB-Audio Virtual Cable) [WASAPI]` seç
2. **Kaynak ekle** — ➕ butonuna bas, mikrofon ve/veya uygulama ekle
3. **Motoru başlat** — Başlat butonuna bas
4. **Discord'da** — Giriş cihazı olarak `CABLE Output (VB-Audio Virtual Cable)` seç

### İpuçları

- Tüm ses seviyelerini **%100 (1.0)** tut — en temiz sinyal. Sesi kaynakta (Spotify) veya hedefte (Discord) ayarla
- Her zaman **WASAPI** cihazlarını seç — en düşük gecikme, en iyi kalite
- Pencereyi kapatmak uygulamayı kapatmaz — sistem tepsisine küçülür. Tamamen kapatmak için tray ikonuna sağ tıkla → Kapat

## Lisans

MIT
