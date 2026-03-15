"""
WASAPI Process Loopback — Uygulama bazli ses yakalama.

Windows 10 2004+ API: ActivateAudioInterfaceAsync ile
belirli bir uygulamanin sesini yakalar (Spotify, Chrome vs.).
"""

import numpy as np
import threading
import time
import logging
import ctypes
from ctypes import (
    Structure, POINTER, c_float, c_uint32, c_uint64,
    c_byte, c_ulong, c_ushort, c_void_p,
    cast, byref, sizeof, WinDLL, windll,
)
from ctypes.wintypes import DWORD, LPCWSTR

logger = logging.getLogger("mik.loopback")

AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_BUFFERFLAGS_SILENT = 0x2


def _define_com_interfaces():
    """Gerekli COM arayuzlerini tanimlar."""
    import comtypes
    from comtypes import GUID as COMGUID, HRESULT, COMMETHOD, IUnknown

    class IAudioCaptureClient(IUnknown):
        _iid_ = COMGUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetBuffer",
                      (["out"], POINTER(c_void_p), "ppData"),
                      (["out"], POINTER(c_uint32), "pNumFramesAvailable"),
                      (["out"], POINTER(DWORD), "pdwFlags"),
                      (["out"], POINTER(c_uint64), "pu64DevicePosition"),
                      (["out"], POINTER(c_uint64), "pu64QPCPosition")),
            COMMETHOD([], HRESULT, "ReleaseBuffer",
                      (["in"], c_uint32, "NumFramesRead")),
            COMMETHOD([], HRESULT, "GetNextPacketSize",
                      (["out"], POINTER(c_uint32), "pNumFramesInNextPacket")),
        ]

    class IActivateAudioInterfaceAsyncOperation(IUnknown):
        _iid_ = COMGUID("{72A22D78-CDE4-431D-B8CC-843A71199B6D}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetActivateResult",
                      (["out"], POINTER(HRESULT), "activateResult"),
                      (["out"], POINTER(POINTER(IUnknown)), "activatedInterface")),
        ]

    class IActivateAudioInterfaceCompletionHandler(IUnknown):
        _iid_ = COMGUID("{41D949AB-9862-444A-80F6-C261334DA5EB}")
        _methods_ = [
            COMMETHOD([], HRESULT, "ActivateCompleted",
                      (["in"], POINTER(IActivateAudioInterfaceAsyncOperation), "op")),
        ]

    class IAgileObject(IUnknown):
        _iid_ = COMGUID("{94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90}")
        _methods_ = []

    return IAudioCaptureClient, IActivateAudioInterfaceAsyncOperation, IActivateAudioInterfaceCompletionHandler, IAgileObject


class AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS(Structure):
    _fields_ = [("TargetProcessId", c_uint32), ("ProcessLoopbackMode", c_uint32)]

class AUDIOCLIENT_ACTIVATION_PARAMS(Structure):
    _fields_ = [("ActivationType", c_uint32),
                ("ProcessLoopbackParams", AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS)]

class BLOB(Structure):
    _fields_ = [("cbSize", c_ulong), ("pBlobData", POINTER(c_byte))]

class PROPVARIANT(Structure):
    _fields_ = [("vt", c_ushort), ("r1", c_ushort), ("r2", c_ushort), ("r3", c_ushort),
                ("blob", BLOB)]


class ProcessCapture:
    """Tek bir uygulamanin sesini WASAPI Process Loopback ile yakalar."""

    def __init__(self, pid: int, name: str = "", fifo=None):
        self.pid = pid
        self.name = name
        self._fifo = fifo          # AudioFIFO — engine tarafindan verilir
        self._running = False
        self._thread: threading.Thread | None = None
        self._channels = 2
        self._sample_rate = 48000
        self._peak = 0.0

    @property
    def peak(self) -> float:
        return self._peak

    @property
    def channels(self) -> int:
        return self._channels

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info(f"Process capture started: {self.name} (PID={self.pid})")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info(f"Process capture stopped: {self.name}")

    def _activate_process_loopback(self):
        """Process-specific loopback icin IAudioClient aktive eder."""
        import comtypes
        from comtypes import GUID as COMGUID

        _, IAsyncOp, ICompletionHandler, IAgileObject = _define_com_interfaces()

        class CompletionHandler(comtypes.COMObject):
            _com_interfaces_ = [ICompletionHandler, IAgileObject]
            def __init__(self):
                super().__init__()
                self.op = None
                self._event = windll.kernel32.CreateEventW(None, True, False, None)
            def ActivateCompleted(self, op):
                self.op = op
                windll.kernel32.SetEvent(self._event)
                return 0
            def wait(self, ms=5000):
                return windll.kernel32.WaitForSingleObject(self._event, ms) == 0
            def close(self):
                windll.kernel32.CloseHandle(self._event)

        act = AUDIOCLIENT_ACTIVATION_PARAMS()
        act.ActivationType = 1
        act.ProcessLoopbackParams.TargetProcessId = self.pid
        act.ProcessLoopbackParams.ProcessLoopbackMode = 0

        prop = PROPVARIANT()
        prop.vt = 65
        prop.blob.cbSize = sizeof(act)
        prop.blob.pBlobData = cast(byref(act), POINTER(c_byte))

        handler = CompletionHandler()
        handler_unk = handler.QueryInterface(ICompletionHandler)
        handler_raw = ctypes.cast(handler_unk, c_void_p)

        mmdevapi = WinDLL("mmdevapi")
        func = mmdevapi.ActivateAudioInterfaceAsync
        func.restype = ctypes.HRESULT
        func.argtypes = [LPCWSTR, POINTER(COMGUID), POINTER(PROPVARIANT), c_void_p, POINTER(c_void_p)]

        async_op_ptr = c_void_p()
        iid = COMGUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")

        hr = func("VAD\\Process_Loopback", byref(iid), byref(prop), handler_raw, byref(async_op_ptr))
        if hr != 0:
            raise RuntimeError(f"ActivateAudioInterfaceAsync failed: 0x{hr & 0xFFFFFFFF:08X}")

        if not handler.wait(5000):
            raise RuntimeError("ActivateAudioInterfaceAsync timeout")

        act_hr, activated = handler.op.GetActivateResult()
        if act_hr != 0:
            raise RuntimeError(f"Activation failed: 0x{act_hr & 0xFFFFFFFF:08X}")

        return activated, handler, handler_unk

    def _capture_loop(self):
        """Ana yakalama dongusu — ayri thread'de calisir."""
        import comtypes
        from comtypes import GUID as COMGUID
        from pycaw.pycaw import AudioUtilities, IAudioClient

        try:
            comtypes.CoInitialize()
        except Exception:
            pass

        IAudioCaptureClient = _define_com_interfaces()[0]
        _refs = []
        audio_client = None

        try:
            # Varsayilan cikis cihazindan format bilgisini al
            speakers = AudioUtilities.GetSpeakers()
            dev = speakers._dev
            IID_AC = COMGUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")
            unk = dev.Activate(IID_AC, 23, None)
            speaker_ac = unk.QueryInterface(IAudioClient)
            fmt = speaker_ac.GetMixFormat()
            _refs.extend([speakers, dev, unk, speaker_ac, fmt])

            self._channels = fmt.contents.nChannels
            self._sample_rate = fmt.contents.nSamplesPerSec
            logger.info(f"Format: {self._sample_rate}Hz, {self._channels}ch")

            # Process loopback aktive et
            activated, handler, handler_unk = self._activate_process_loopback()
            audio_client = activated.QueryInterface(IAudioClient)
            _refs.extend([activated, handler, handler_unk, audio_client])

            # Initialize: speaker formati + LOOPBACK flag
            audio_client.Initialize(
                AUDCLNT_SHAREMODE_SHARED,
                AUDCLNT_STREAMFLAGS_LOOPBACK,
                1_000_000,  # 100ms buffer
                0,
                fmt,
                None,
            )

            # IAudioCaptureClient al
            IID_CC = COMGUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")
            cc_unk = audio_client.GetService(IID_CC)
            capture_client = cc_unk.QueryInterface(IAudioCaptureClient)
            _refs.extend([cc_unk, capture_client])

            audio_client.Start()
            logger.info(f"Process loopback active: {self.name} (PID={self.pid})")

            # Event-driven reading with WaitForSingleObject
            # yerine daha basit tight poll — 10ms'den kisa uyku
            while self._running:
                try:
                    packet_size = capture_client.GetNextPacketSize()

                    while packet_size > 0 and self._running:
                        data_ptr, num_frames, flags, _, _ = capture_client.GetBuffer()

                        if num_frames > 0:
                            if flags & AUDCLNT_BUFFERFLAGS_SILENT:
                                audio_data = np.zeros(
                                    (num_frames, self._channels), dtype=np.float32
                                )
                            else:
                                total = num_frames * self._channels
                                arr_type = c_float * total
                                raw = cast(data_ptr, POINTER(arr_type)).contents
                                audio_data = np.frombuffer(
                                    raw, dtype=np.float32
                                ).reshape(num_frames, self._channels).copy()

                            self._peak = float(np.max(np.abs(audio_data)))

                            # Kanal uyumu: capture channels -> 2ch
                            if self._channels > 2:
                                audio_data = audio_data[:, :2]
                            elif self._channels == 1:
                                audio_data = np.column_stack([audio_data[:, 0], audio_data[:, 0]])

                            # FIFO'ya push
                            if self._fifo is not None:
                                self._fifo.push(audio_data)

                        capture_client.ReleaseBuffer(num_frames)
                        packet_size = capture_client.GetNextPacketSize()

                except Exception as e:
                    if self._running:
                        logger.debug(f"Read error: {e}")

                time.sleep(0.003)  # 3ms — WASAPI 10ms paketler gonderir

        except Exception as e:
            logger.error(f"Process capture error ({self.name}): {e}")
        finally:
            if audio_client:
                try:
                    audio_client.Stop()
                except Exception:
                    pass
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass
