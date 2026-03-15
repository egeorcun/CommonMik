"""
CommonMik — Ses motoru cekirdegi.

WASAPI uzerinden uygulama bazli ses yakalama, mikrofon girisi,
karistirma ve sanal cihaza cikis.

Tum sesler 48kHz float32 stereo pipeline'dan gecer.
WASAPI shared mode + FIFO ring buffer + sinc resample.
"""

import threading
import numpy as np
import sounddevice as sd
import logging
from dataclasses import dataclass, field
from core.loopback import ProcessCapture

logger = logging.getLogger("mik.audio")

SAMPLE_RATE = 48000
BLOCK_SIZE = 960   # 20ms @ 48kHz
CHANNELS = 2
DTYPE = "float32"

# FIFO: 200ms kapasite, 100ms max latency
FIFO_CAPACITY = SAMPLE_RATE // 5   # 9600 frames
FIFO_MAX_LATENCY = SAMPLE_RATE // 10  # 4800 frames


# ── WASAPI device helper ──

def _get_wasapi_host_api_index() -> int | None:
    """WASAPI host API index'ini dondurur."""
    for i, api in enumerate(sd.query_hostapis()):
        if "WASAPI" in api["name"]:
            return i
    return None

def _find_wasapi_device(name_fragment: str, is_input: bool) -> dict | None:
    """WASAPI API'sindeki eslesen cihazi bulur."""
    wasapi_idx = _get_wasapi_host_api_index()
    if wasapi_idx is None:
        return None
    for i, dev in enumerate(sd.query_devices()):
        if dev["hostapi"] != wasapi_idx:
            continue
        if is_input and dev["max_input_channels"] == 0:
            continue
        if not is_input and dev["max_output_channels"] == 0:
            continue
        if name_fragment.lower() in dev["name"].lower():
            return {"index": i, **dev}
    return None


# ── Sinc resampler ──

def _resample_sinc(data: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Polifaz sinc resample — yuksek kalite, dusuk CPU."""
    if src_rate == dst_rate or len(data) < 2:
        return data

    from math import gcd
    g = gcd(src_rate, dst_rate)
    up = dst_rate // g
    down = src_rate // g

    # Kucuk ratio'larda numpy linspace + sinc kernel
    # Buyuk ratio'larda scipy varsa onu kullan
    try:
        from scipy.signal import resample_poly
        return resample_poly(data, up, down, axis=0).astype(np.float32)
    except ImportError:
        pass

    # Fallback: yuksek kaliteli interpolasyon (4-tap cubic)
    out_len = int(len(data) * dst_rate / src_rate)
    if out_len < 1:
        out_len = 1
    indices = np.linspace(0, len(data) - 1, out_len)
    idx = np.floor(indices).astype(int)
    frac = (indices - idx).reshape(-1, 1).astype(np.float32)

    # Cubic Hermite interpolation (4-tap)
    n = len(data)
    i0 = np.clip(idx - 1, 0, n - 1)
    i1 = np.clip(idx, 0, n - 1)
    i2 = np.clip(idx + 1, 0, n - 1)
    i3 = np.clip(idx + 2, 0, n - 1)

    y0 = data[i0]; y1 = data[i1]; y2 = data[i2]; y3 = data[i3]
    t = frac; t2 = t * t; t3 = t2 * t

    # Catmull-Rom spline
    result = (
        0.5 * (
            (2.0 * y1) +
            (-y0 + y2) * t +
            (2.0 * y0 - 5.0 * y1 + 4.0 * y2 - y3) * t2 +
            (-y0 + 3.0 * y1 - 3.0 * y2 + y3) * t3
        )
    )
    return result.astype(np.float32)


# ── Audio FIFO ──

class AudioFIFO:
    """
    Thread-safe FIFO ring buffer.

    Producer (capture/mic callback) -> push()
    Consumer (output callback)      -> pull()

    Her frame tam olarak bir kez okunur.
    """

    __slots__ = ("_buf", "_cap", "_ch", "_wp", "_rp", "_count", "_lock", "_peak")

    def __init__(self, capacity: int, channels: int):
        self._buf = np.zeros((capacity, channels), dtype=np.float32)
        self._cap = capacity
        self._ch = channels
        self._wp = 0
        self._rp = 0
        self._count = 0
        self._lock = threading.Lock()
        self._peak = 0.0

    @property
    def available(self) -> int:
        return self._count

    @property
    def peak(self) -> float:
        return self._peak

    def push(self, data: np.ndarray):
        n = len(data)
        if n == 0:
            return

        self._peak = float(np.max(np.abs(data)))

        with self._lock:
            if n >= self._cap:
                data = data[-self._cap:]
                n = self._cap
                self._buf[:n] = data
                self._wp = n % self._cap
                self._rp = self._wp
                self._count = self._cap
                return

            wp = self._wp
            if wp + n <= self._cap:
                self._buf[wp:wp + n] = data
            else:
                first = self._cap - wp
                self._buf[wp:] = data[:first]
                self._buf[:n - first] = data[first:]
            self._wp = (wp + n) % self._cap

            self._count += n
            if self._count > self._cap:
                overflow = self._count - self._cap
                self._rp = (self._rp + overflow) % self._cap
                self._count = self._cap

    def pull(self, num_frames: int) -> np.ndarray:
        with self._lock:
            avail = self._count
            if avail == 0:
                return np.zeros((num_frames, self._ch), dtype=np.float32)

            to_read = min(num_frames, avail)
            rp = self._rp

            if rp + to_read <= self._cap:
                out = self._buf[rp:rp + to_read].copy()
            else:
                first = self._cap - rp
                out = np.empty((to_read, self._ch), dtype=np.float32)
                out[:first] = self._buf[rp:]
                out[first:] = self._buf[:to_read - first]

            self._rp = (rp + to_read) % self._cap
            self._count -= to_read

            if to_read < num_frames:
                result = np.zeros((num_frames, self._ch), dtype=np.float32)
                result[:to_read] = out
                return result
            return out

    def trim_excess(self, target: int):
        with self._lock:
            if self._count > target:
                skip = self._count - target
                self._rp = (self._rp + skip) % self._cap
                self._count = target


# ── Audio Source ──

@dataclass
class AudioSource:
    name: str
    source_type: str
    device_index: int | None = None
    volume: float = 1.0
    muted: bool = False
    active: bool = False
    peak_level: float = 0.0
    _fifo: AudioFIFO = field(default=None, repr=False)
    _loopback: "ProcessCapture | None" = field(default=None, repr=False)

    def __post_init__(self):
        if self._fifo is None:
            self._fifo = AudioFIFO(FIFO_CAPACITY, CHANNELS)

    def get_audio(self, frames: int) -> np.ndarray:
        if self.muted:
            if self._fifo.available > 0:
                self._fifo.pull(self._fifo.available)
            return np.zeros((frames, CHANNELS), dtype=DTYPE)

        data = self._fifo.pull(frames)
        self.peak_level = self._fifo.peak
        self._fifo.trim_excess(FIFO_MAX_LATENCY)
        return data * self.volume

    def push_audio(self, data: np.ndarray):
        if data.ndim == 1:
            data = np.column_stack([data, data])
        elif data.shape[1] == 1:
            data = np.column_stack([data[:, 0], data[:, 0]])
        elif data.shape[1] > CHANNELS:
            data = data[:, :CHANNELS]

        self._fifo.push(data)
        self.peak_level = self._fifo.peak
        self.active = True


# ── Engine ──

class AudioEngine:
    def __init__(self):
        self.sources: dict[str, AudioSource] = {}
        self.output_device: int | None = None
        self.master_volume: float = 1.0
        self.running: bool = False
        self._streams: dict[str, sd.InputStream | sd.OutputStream] = {}
        self._lock = threading.Lock()
        self._output_stream: sd.OutputStream | None = None
        self._master_peak: float = 0.0
        self._output_rate: int = SAMPLE_RATE

    def get_input_devices(self) -> list[dict]:
        """Giris cihazlari — WASAPI tercihli, fallback MME."""
        wasapi_idx = _get_wasapi_host_api_index()
        seen_names = set()
        devices = []

        # Once WASAPI cihazlarini ekle
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0 and dev["hostapi"] == wasapi_idx:
                base = dev["name"].split("(")[0].strip()
                if base not in seen_names:
                    seen_names.add(base)
                    devices.append({
                        "index": i,
                        "name": dev["name"],
                        "channels": dev["max_input_channels"],
                        "sample_rate": dev["default_samplerate"],
                        "api": "WASAPI",
                    })

        # Sonra diger API'leri (WASAPI'de olmayan cihazlar)
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0 and dev["hostapi"] != wasapi_idx:
                base = dev["name"].split("(")[0].strip()
                if base not in seen_names:
                    seen_names.add(base)
                    api_name = sd.query_hostapis(dev["hostapi"])["name"]
                    devices.append({
                        "index": i,
                        "name": dev["name"],
                        "channels": dev["max_input_channels"],
                        "sample_rate": dev["default_samplerate"],
                        "api": api_name,
                    })

        return devices

    def get_output_devices(self) -> list[dict]:
        """Cikis cihazlari — WASAPI tercihli."""
        wasapi_idx = _get_wasapi_host_api_index()
        seen_names = set()
        devices = []

        for i, dev in enumerate(sd.query_devices()):
            if dev["max_output_channels"] > 0 and dev["hostapi"] == wasapi_idx:
                base = dev["name"].split("(")[0].strip()
                if base not in seen_names:
                    seen_names.add(base)
                    devices.append({
                        "index": i,
                        "name": dev["name"],
                        "channels": dev["max_output_channels"],
                        "sample_rate": dev["default_samplerate"],
                        "api": "WASAPI",
                    })

        for i, dev in enumerate(sd.query_devices()):
            if dev["max_output_channels"] > 0 and dev["hostapi"] != wasapi_idx:
                base = dev["name"].split("(")[0].strip()
                if base not in seen_names:
                    seen_names.add(base)
                    api_name = sd.query_hostapis(dev["hostapi"])["name"]
                    devices.append({
                        "index": i,
                        "name": dev["name"],
                        "channels": dev["max_output_channels"],
                        "sample_rate": dev["default_samplerate"],
                        "api": api_name,
                    })

        return devices

    def add_microphone(self, device_index: int, name: str = "") -> str:
        dev_info = sd.query_devices(device_index)
        if not name:
            name = dev_info["name"]

        source_id = f"mic_{device_index}"
        source = AudioSource(name=name, source_type="microphone", device_index=device_index)

        with self._lock:
            self.sources[source_id] = source
        if self.running:
            self._start_input_stream(source_id, source)

        logger.info(f"Mic added: {name} (index={device_index})")
        return source_id

    def add_loopback(self, device_index: int = -1, name: str = "Sistem Sesi",
                     pid: int | None = None) -> str:
        if pid is None or pid <= 0:
            return ""

        source_id = f"app_{pid}"
        if source_id in self.sources:
            return source_id

        fifo = AudioFIFO(FIFO_CAPACITY, CHANNELS)
        capture = ProcessCapture(pid=pid, name=name, fifo=fifo)
        source = AudioSource(
            name=name, source_type="loopback", device_index=pid,
            _fifo=fifo, _loopback=capture,
        )

        with self._lock:
            self.sources[source_id] = source
        if self.running:
            capture.start()
            source.active = True

        logger.info(f"App capture added: {name} (PID={pid})")
        return source_id

    def remove_source(self, source_id: str):
        with self._lock:
            if source_id in self._streams:
                try:
                    self._streams[source_id].stop()
                    self._streams[source_id].close()
                except Exception:
                    pass
                del self._streams[source_id]
            if source_id in self.sources:
                src = self.sources[source_id]
                if src._loopback:
                    src._loopback.stop()
                del self.sources[source_id]
        logger.info(f"Source removed: {source_id}")

    def set_volume(self, source_id: str, volume: float):
        with self._lock:
            if source_id in self.sources:
                self.sources[source_id].volume = max(0.0, min(2.0, volume))

    def set_mute(self, source_id: str, muted: bool):
        with self._lock:
            if source_id in self.sources:
                self.sources[source_id].muted = muted

    def set_output_device(self, device_index: int):
        self.output_device = device_index
        if self.running:
            self._restart_output_stream()
        logger.info(f"Output device: {device_index}")

    def get_levels(self) -> dict:
        levels = {}
        with self._lock:
            for sid, source in self.sources.items():
                levels[sid] = {
                    "peak": source.peak_level,
                    "volume": source.volume,
                    "muted": source.muted,
                    "name": source.name,
                    "type": source.source_type,
                    "active": source.active,
                }
        levels["master"] = {"peak": self._master_peak, "volume": self.master_volume}
        return levels

    def start(self):
        if self.running:
            return
        self.running = True

        with self._lock:
            for sid, source in self.sources.items():
                if source.source_type == "microphone":
                    self._start_input_stream(sid, source)
                elif source.source_type == "loopback" and source._loopback:
                    source._loopback.start()
                    source.active = True

        self._start_output_stream()
        logger.info("Engine started")

    def stop(self):
        self.running = False
        for sid, stream in list(self._streams.items()):
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        self._streams.clear()

        with self._lock:
            for source in self.sources.values():
                if source._loopback:
                    source._loopback.stop()
                source.active = False

        if self._output_stream:
            try:
                self._output_stream.stop()
                self._output_stream.close()
            except Exception:
                pass
            self._output_stream = None
        logger.info("Engine stopped")

    def _start_input_stream(self, source_id: str, source: AudioSource):
        try:
            dev_info = sd.query_devices(source.device_index)
            dev_ch = dev_info["max_input_channels"]
            channels = min(CHANNELS, dev_ch)
            dev_rate = int(dev_info["default_samplerate"])

            need_resample = (dev_rate != SAMPLE_RATE)
            if need_resample:
                ratio = SAMPLE_RATE / dev_rate
                mic_block = max(64, int(BLOCK_SIZE / ratio))
                logger.info(f"Mic resample: {dev_rate} -> {SAMPLE_RATE}")
            else:
                mic_block = BLOCK_SIZE

            def callback(indata, frames, time_info, status):
                if status:
                    logger.debug(f"Input status ({source.name}): {status}")
                data = indata.copy()
                if need_resample and len(data) > 1:
                    data = _resample_sinc(data, dev_rate, SAMPLE_RATE)
                source.push_audio(data)

            stream = sd.InputStream(
                device=source.device_index,
                samplerate=dev_rate,
                blocksize=mic_block,
                channels=channels,
                dtype=DTYPE,
                callback=callback,
            )
            stream.start()
            self._streams[source_id] = stream
            logger.info(f"Input stream started: {source.name} @ {dev_rate}Hz")
        except Exception as e:
            logger.error(f"Input stream error ({source.name}): {e}")
            source.active = False

    def _start_output_stream(self):
        if self.output_device is None:
            logger.warning("No output device selected")
            return

        try:
            dev_info = sd.query_devices(self.output_device)
            channels = min(CHANNELS, dev_info["max_output_channels"])
            dev_rate = int(dev_info["default_samplerate"])
            self._output_rate = dev_rate

            need_resample = (dev_rate != SAMPLE_RATE)
            if need_resample:
                logger.info(f"Output resample: {SAMPLE_RATE} -> {dev_rate}")

            out_block = int(BLOCK_SIZE * dev_rate / SAMPLE_RATE) if need_resample else BLOCK_SIZE

            def callback(outdata, frames, time_info, status):
                if status:
                    logger.debug(f"Output status: {status}")

                # FIFO'dan ne kadar kaynak frame lazim
                src_frames = int(frames * SAMPLE_RATE / dev_rate) if need_resample else frames

                mixed = np.zeros((src_frames, channels), dtype=DTYPE)
                with self._lock:
                    for source in self.sources.values():
                        audio = source.get_audio(src_frames)
                        if audio.shape[1] > channels:
                            audio = audio[:, :channels]
                        elif audio.shape[1] < channels:
                            audio = np.column_stack([audio[:, 0]] * channels)
                        if len(audio) > src_frames:
                            audio = audio[:src_frames]
                        elif len(audio) < src_frames:
                            padded = np.zeros((src_frames, channels), dtype=DTYPE)
                            padded[:len(audio)] = audio
                            audio = padded
                        mixed += audio

                mixed *= self.master_volume
                np.clip(mixed, -1.0, 1.0, out=mixed)

                if need_resample and len(mixed) > 1:
                    resampled = _resample_sinc(mixed, SAMPLE_RATE, dev_rate)
                    n = min(frames, len(resampled))
                    outdata[:n] = resampled[:n]
                    if n < frames:
                        outdata[n:] = 0
                else:
                    n = min(frames, len(mixed))
                    outdata[:n] = mixed[:n]
                    if n < frames:
                        outdata[n:] = 0

                self._master_peak = float(np.max(np.abs(outdata))) if frames > 0 else 0.0

            self._output_stream = sd.OutputStream(
                device=self.output_device,
                samplerate=dev_rate,
                blocksize=out_block,
                channels=channels,
                dtype=DTYPE,
                callback=callback,
                latency="low",
            )
            self._output_stream.start()
            logger.info(f"Output stream started: {dev_info['name']} @ {dev_rate}Hz")
        except Exception as e:
            logger.error(f"Output stream error: {e}")

    def _restart_output_stream(self):
        if self._output_stream:
            try:
                self._output_stream.stop()
                self._output_stream.close()
            except Exception:
                pass
            self._output_stream = None
        self._start_output_stream()
