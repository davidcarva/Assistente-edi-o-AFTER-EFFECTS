"""Detecta 'beats' da fala (momentos com intenção) e atribui um visual sob medida
a cada beat. Cada beat tem início, fim e um brief de imagem. É o motor de
audio+vídeo casado do modo Gerador.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from .ai_client import structured

INTENTS = ["revelation", "contrast", "number", "quote", "action", "atmosphere", "cta", "other"]
VISUAL_TYPES = ["photo", "generated", "color_card"]

SYSTEM = (
    "Você é um editor expert de vídeos curtos (30-60s, Reels/Shorts). "
    "Receberá uma transcrição numerada com tempos. Sua tarefa é segmentar a fala "
    "em BEATS — momentos distintos que merecem um visual único. "
    "Para CADA beat, devolva:\n"
    "- line_start, line_end: índices da primeira e última linha do beat (inclusive).\n"
    "- intent: uma de [" + ", ".join(INTENTS) + "].\n"
    "- query_en: busca de imagem CURTA e CONCRETA em INGLÊS (substantivos visuais).\n"
    "- sd_prompt: prompt cinematográfico em inglês para gerar a imagem por IA.\n"
    "- visual_type: photo | generated | color_card.\n\n"
    "Regras:\n"
    "- Mire 6-10 beats no total (1 a cada ~4-7s de fala).\n"
    "- Cada beat dura 2-6s; sem sobreposição; cobertura total quando possível.\n"
    "- O visual deve ilustrar a INTENÇÃO do beat, não a palavra literal.\n"
    "- Varie tipos de visual; evite repetir o mesmo conceito em beats consecutivos.\n"
    "- 'color_card' para beats abstratos sem boa imagem (fundo de cor com texto)."
)


class _Beat(BaseModel):
    line_start: int = Field(description="primeira linha do beat (inclusive)")
    line_end: int = Field(description="última linha do beat (inclusive)")
    intent: str
    query_en: str
    sd_prompt: str
    visual_type: str = "photo"


class _BeatsPlan(BaseModel):
    beats: list[_Beat]


@dataclass
class Beat:
    start: float
    end: float
    query: str
    prompt: str
    intent: str = "other"
    visual_type: str = "photo"

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def plan_beats(lines: list, provider: str = "openai", api_key: str | None = None,
               target_duration: float | None = None) -> list[Beat]:
    """Retorna beats em ORDEM cronológica, em tempo da comp.

    `lines` são as captions (objetos com .start e .end e .text) na timeline cortada.
    `target_duration` (opcional) é um alvo de duração total (s) — informativo no prompt.
    """
    if not lines:
        return []
    numbered = "\n".join(f"[{i}] ({l.start:.1f}s-{l.end:.1f}s) {l.text}" for i, l in enumerate(lines))
    total = lines[-1].end - lines[0].start
    target_hint = f" Alvo de duração do vídeo: ~{target_duration:.0f}s." if target_duration else ""
    user = (
        f"Transcrição ({len(lines)} linhas, ~{total:.1f}s de fala).{target_hint}\n\n"
        f"{numbered}\n\nGere os beats agora."
    )

    plan = structured(provider, SYSTEM, user, _BeatsPlan, api_key=api_key, max_tokens=4096)

    beats: list[Beat] = []
    for b in plan.beats:
        ls, le = max(0, b.line_start), min(len(lines) - 1, b.line_end)
        if le < ls:
            continue
        start = lines[ls].start
        end = lines[le].end
        vt = b.visual_type if b.visual_type in VISUAL_TYPES else "photo"
        intent = b.intent if b.intent in INTENTS else "other"
        beats.append(Beat(start=start, end=end, query=b.query_en.strip(),
                          prompt=b.sd_prompt.strip(), intent=intent, visual_type=vt))

    beats.sort(key=lambda x: x.start)
    return beats
