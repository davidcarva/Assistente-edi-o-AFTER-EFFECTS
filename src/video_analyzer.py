"""Analisa um vídeo de referência com o Gemini e extrai um preset de estilo.

Gemini é o único modelo grande com suporte nativo a vídeo via API — analisa
diretamente o arquivo (não só frames). Retorna pacing, estilo de legenda, tom
do canal e uma sugestão de 'video_context' temático.
"""
from __future__ import annotations

import os
import time

from pydantic import BaseModel, Field


class _Pacing(BaseModel):
    silence_threshold: float = Field(description="quanto menor, mais apertado o corte (0.15-0.8)")
    min_segment: float = Field(default=0.4)
    padding: float = Field(default=0.04, description="folga em segundos (0.01-0.2)")


class _Captions(BaseModel):
    style: str = Field(description="'word' (palavra a palavra) ou 'line' (frase inteira)")
    color_hex: str = Field(description="cor predominante das legendas em hex, ex: #FFD700")
    position: str = Field(description="'top', 'middle' ou 'bottom'")
    scale: float = Field(default=1.0, description="tamanho relativo (0.6-2.0)")


class VideoStyle(BaseModel):
    name: str = Field(description="nome curto sugerido para o estilo")
    summary: str = Field(description="2-3 frases descrevendo o estilo de edição")
    pacing: _Pacing
    captions: _Captions
    video_context_hint: str = Field(
        description="1-2 frases sobre o tema/contexto do vídeo (para guiar futuras buscas)"
    )
    channel_tone: str = Field(description="tom do canal (ex: dark, energético, factual, cômico)")


GEMINI_MODEL = "gemini-2.5-flash"

PROMPT = (
    "Você é um diretor de edição de vídeo analisando uma referência. "
    "Examine este vídeo e extraia o ESTILO DE EDIÇÃO em JSON.\n\n"
    "Avalie:\n"
    "- Ritmo: cortes muito apertados (silence_threshold ~0.2), médios (~0.4) ou soltos (~0.7).\n"
    "- Legendas: aparecem 1-2 palavras por vez (style='word', tipo Reels) ou frases inteiras "
    "('line'). Cor predominante em hex. Posição na tela. Tamanho relativo.\n"
    "- video_context_hint: descreva em 1-2 frases do que o vídeo trata, em PT-BR, "
    "de um jeito útil pra direcionar buscas/IA de B-roll em vídeos do mesmo canal.\n"
    "- channel_tone: tom geral (ex: 'dark/curiosidades', 'comédia rápida', 'tutorial calmo').\n"
    "Retorne SOMENTE o JSON do schema."
)


def analyze_video(path: str, api_key: str | None = None, log=print) -> dict:
    """Faz upload do vídeo pro Gemini, analisa e retorna um dict pronto pra virar Style."""
    from google import genai
    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Chave do Gemini ausente. Defina GEMINI_API_KEY ou gemini_api_key.")

    client = genai.Client(api_key=key)
    log(f"[Gemini] Enviando '{os.path.basename(path)}'...")
    myfile = client.files.upload(file=path)

    # aguarda processamento
    state = getattr(getattr(myfile, "state", None), "name", "ACTIVE")
    while state == "PROCESSING":
        time.sleep(2)
        myfile = client.files.get(name=myfile.name)
        state = getattr(getattr(myfile, "state", None), "name", "ACTIVE")
    if state not in ("ACTIVE", "SUCCEEDED"):
        raise RuntimeError(f"Upload do vídeo falhou: state={state}")

    log("[Gemini] Analisando o vídeo...")
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[myfile, PROMPT],
        config={
            "response_mime_type": "application/json",
            "response_schema": VideoStyle,
        },
    )
    style: VideoStyle = response.parsed
    log(f"[Gemini] Estilo identificado: {style.name} ({style.channel_tone})")
    return _to_style_dict(style)


def _to_style_dict(s: VideoStyle) -> dict:
    r, g, b = _hex_to_rgb(s.captions.color_hex)
    return {
        "name": s.name,
        "summary": s.summary,
        "tone": s.channel_tone,
        "style": {
            "silence_threshold": _clamp(s.pacing.silence_threshold, 0.15, 0.8),
            "min_segment": _clamp(s.pacing.min_segment, 0.2, 1.0),
            "padding": _clamp(s.pacing.padding, 0.01, 0.2),
            "caption_font": "SofiaPro-Bold",
            "caption_style": s.captions.style if s.captions.style in ("word", "line") else "word",
            "caption_color": [r, g, b],
            "caption_pos": s.captions.position if s.captions.position in ("top", "middle", "bottom") else "bottom",
            "caption_scale": _clamp(s.captions.scale, 0.6, 2.0),
            "captions_enabled": True,
            "video_context": s.video_context_hint,
        },
    }


def _hex_to_rgb(hx: str) -> tuple[float, float, float]:
    h = (hx or "").lstrip("#")
    if len(h) != 6:
        return (1.0, 1.0, 1.0)
    try:
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except Exception:
        return (1.0, 1.0, 1.0)


def _clamp(x: float, lo: float, hi: float) -> float:
    try:
        return float(max(lo, min(hi, x)))
    except Exception:
        return float((lo + hi) / 2)
