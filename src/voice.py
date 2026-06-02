"""Captura um comando falado pelo microfone e devolve o texto transcrito."""
from __future__ import annotations

import os
import tempfile

from . import transcribe as T


def record_command(
    model_name: str = "large-v3",
    device: str = "cuda",
    compute_type: str = "float16",
    language: str = "pt",
    samplerate: int = 16000,
) -> str:
    """Grava do microfone até o usuário apertar Enter, transcreve e retorna o texto."""
    import sounddevice as sd
    import soundfile as sf

    print("Gravando comando... fale e aperte ENTER para parar.")
    frames: list = []

    def callback(indata, frames_count, time_info, status):
        frames.append(indata.copy())

    with sd.InputStream(samplerate=samplerate, channels=1, callback=callback):
        input()

    if not frames:
        return ""

    import numpy as np
    audio = np.concatenate(frames, axis=0)

    tmp = os.path.join(tempfile.gettempdir(), "comando_voz.wav")
    sf.write(tmp, audio, samplerate)

    words = T.transcribe(
        tmp, model_name=model_name, device=device,
        compute_type=compute_type, language=language,
    )
    return "".join(w.text for w in words).strip()


class Recorder:
    """Gravação start/stop para uso em interface gráfica (sem depender de Enter)."""

    def __init__(self, samplerate: int = 16000):
        self.samplerate = samplerate
        self.frames: list = []
        self.stream = None

    def start(self) -> None:
        import sounddevice as sd
        self.frames = []
        self.stream = sd.InputStream(
            samplerate=self.samplerate, channels=1,
            callback=lambda indata, n, t, s: self.frames.append(indata.copy()),
        )
        self.stream.start()

    def stop_and_transcribe(self, **kw) -> str:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if not self.frames:
            return ""
        import numpy as np
        import soundfile as sf
        audio = np.concatenate(self.frames, axis=0)
        tmp = os.path.join(tempfile.gettempdir(), "comando_voz.wav")
        sf.write(tmp, audio, self.samplerate)
        words = T.transcribe(tmp, **kw)
        return "".join(w.text for w in words).strip()
