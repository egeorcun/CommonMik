<p align="center">
  <img src="screenshot.png" alt="CommonMik" width="500"/>
</p>

<h1 align="center">CommonMik</h1>

<p align="center">
  Windows için uygulama bazlı ses karıştırıcı
  <br/>
  <a href="README.md">🇬🇧 English</a>
</p>

---

Spotify, Chrome, oyun gibi uygulamaların sesini yakalar, mikrofonunla karıştırır ve Discord/Zoom'da sanal mikrofon olarak kullanmanı sağlar.

## Özellikler

- **Uygulama bazlı ses yakalama** — Hangi uygulamaların sesini alacağını sen seçersin (WASAPI Process Loopback)
- **Mikrofon karıştırma** — Mikrofon + uygulama sesleri tek sanal mikrofona birleştirilir
- **Bağımsız ses kontrolleri** — Her kaynağın sesini ayrı ayrı ayarla, gerçek zamanlı seviye göstergesi
- **Sanal mikrofon çıkışı** — VB-Audio Virtual Cable üzerinden çalışır
- **WASAPI modu** — 48kHz native pipeline, sıfır resampling
- **Sinc resampling** — Farklı sample rate'lerde yüksek kaliteli dönüşüm
- **Sistem tepsisi** — Pencereyi kapat, arka planda çalışmaya devam etsin
- **Otomatik ayar kaydetme** — Çıkış cihazı, kaynaklar, ses seviyeleri otomatik kaydedilir
- **Çoklu dil** — İngilizce ve Türkçe arayüz
- **Native Windows uygulaması** — WebView2 kullanır, tarayıcı gerekmez
- **Koyu tema arayüz** — Glassmorphism tasarım, gerçek zamanlı ses metre

## Nasıl Çalışır

```
Spotify  ───────┐
Chrome   ───────┤──→  CommonMik  ──→  CABLE Input  ──→  Discord mikrofon
Mikrofon ───────┘     (karıştırıcı)   (sanal kablo)     (CABLE Output seç)
```

Windows ses çıkışın kulaklığında kalır — CommonMik, uygulamaların sesini WASAPI ile yakalar, sistem çıkışını değiştirmez.

## Gereksinimler

- Windows 10 sürüm 2004+ / Windows 11
- [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) (ücretsiz)

## Kurulum

### Hazır Exe (Önerilen)

1. [Releases](https://github.com/egeorcun/CommonMik/releases) sayfasından son sürümü indir
2. [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) kur
3. `CommonMik.exe` çalıştır

### Kaynak Koddan

```bash
git clone https://github.com/egeorcun/CommonMik.git
cd CommonMik
pip install -r requirements.txt
python main.py
```

### Exe Derleme

```bash
pip install -r requirements.txt
pyinstaller build.spec
# Çıktı: dist/CommonMik/CommonMik.exe
```

## Kullanım

1. **Çıkış cihazı seç** — `CABLE Input (VB-Audio Virtual Cable) [WASAPI]` seç
2. **Kaynak ekle** — ➕ butonuna bas, mikrofon ve/veya uygulama ekle
3. **Motoru başlat** — Başlat butonuna bas
4. **Discord'da** — Giriş cihazı olarak `CABLE Output (VB-Audio Virtual Cable)` seç

### İpuçları

- Tüm ses seviyelerini **%100** tut — en temiz sinyal. Sesi kaynakta (Spotify) veya hedefte (Discord) ayarla
- Her zaman **WASAPI** cihazlarını seç — en düşük gecikme, en iyi kalite
- Pencereyi kapatmak uygulamayı kapatmaz — sistem tepsisine küçülür. Tamamen kapatmak için tray ikonuna sağ tıkla → Kapat

## Lisans

MIT
