"""Transcrição local com faster-whisper (CUDA), com timestamps por palavra."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, asdict


def _register_cuda_dlls() -> None:
    """No Windows, as DLLs CUDA das wheels nvidia-* ficam dentro do site-packages
    e não no PATH. Registra esses diretórios para o ctranslate2 conseguir carregá-las."""
    if sys.platform != "win32":
        return
    try:
        import nvidia
    except ImportError:
        return
    extra = []
    for base in nvidia.__path__:
        for sub in ("cuda_runtime", "cublas", "cudnn", "cuda_nvrtc"):
            bin_dir = os.path.join(base, sub, "bin")
            if os.path.isdir(bin_dir):
                os.add_dll_directory(bin_dir)
                extra.append(bin_dir)
    # ctranslate2 carrega a cublas pelo loader nativo, que ignora add_dll_directory;
    # o PATH do processo é respeitado, então prependamos os diretórios nele também.
    if extra:
        os.environ["PATH"] = os.pathsep.join(extra) + os.pathsep + os.environ.get("PATH", "")


_register_cuda_dlls()


@dataclass
class Word:
    start: float
    end: float
    text: str


def transcribe(
    media_path: str,
    model_name: str = "large-v3",
    device: str = "cuda",
    compute_type: str = "float16",
    language: str | None = "pt",
) -> list[Word]:
    """Transcreve o áudio de `media_path` e retorna palavras com timestamps.

    Aceita arquivos de vídeo diretamente — o faster-whisper extrai o áudio
    via PyAV, sem precisar do binário do ffmpeg no PATH.
    """
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, _ = model.transcribe(
        media_path,
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )

    words: list[Word] = []
    for seg in segments:
        for w in seg.words or []:
            words.append(Word(start=w.start, end=w.end, text=w.word))
    return words


def words_to_dicts(words: list[Word]) -> list[dict]:
    return [asdict(w) for w in words]
