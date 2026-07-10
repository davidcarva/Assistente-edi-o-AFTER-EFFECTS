"""Geração de voz com ElevenLabs (text-to-speech).

Usado em canais faceless: você fornece um roteiro (texto) e recebe um .mp3 com a
voz escolhida. Esse áudio entra no pipeline normal (transcrição -> beats -> ...).
"""
from __future__ import annotations

import os


def list_voices(api_key: str | None = None) -> list[tuple[str, str]]:
    """Retorna [(voice_id, nome), ...] das vozes disponíveis na conta."""
    from elevenlabs.client import ElevenLabs
    key = api_key or os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("Chave da ElevenLabs ausente (ELEVENLABS_API_KEY / elevenlabs_api_key).")
    client = ElevenLabs(api_key=key)
    resp = client.voices.get_all()
    voices = getattr(resp, "voices", resp)
    out = []
    for v in voices:
        vid = getattr(v, "voice_id", None) or getattr(v, "id", None)
        name = getattr(v, "name", vid)
        if vid:
            out.append((vid, name))
    return out


def synthesize(text: str, out_path: str, voice_id: str,
               model_id: str = "eleven_multilingual_v2",
               api_key: str | None = None, log=print) -> str:
    """Gera a voz do `text` e salva em `out_path` (.mp3). Retorna o caminho."""
    from elevenlabs.client import ElevenLabs
    key = api_key or os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("Chave da ElevenLabs ausente (ELEVENLABS_API_KEY / elevenlabs_api_key).")
    if not voice_id:
        raise RuntimeError("Nenhuma voz (voice_id) selecionada para a ElevenLabs.")

    client = ElevenLabs(api_key=key)
    log(f"[ElevenLabs] Gerando voz ({model_id}, voz {voice_id})...")
    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id=model_id,
        text=text,
        output_format="mp3_44100_128",
    )
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as f:
        if isinstance(audio, (bytes, bytearray)):
            f.write(audio)
        else:
            for chunk in audio:           # SDK retorna um iterador de bytes
                if chunk:
                    f.write(chunk)
    log(f"[ElevenLabs] Áudio salvo: {out_path}")
    return out_path
