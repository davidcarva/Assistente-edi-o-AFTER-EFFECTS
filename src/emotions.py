"""Classifica a emoção do avatar ao longo da fala (via IA) e monta a linha do
tempo de emoções na comp cortada, com intervalo mínimo de troca (anti-flicker)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .ai_client import structured

# Conjunto de emoções (= nomes dos arquivos PNG que o usuário fornece: neutro.png, feliz.png, ...)
EMOTIONS = [
    "neutro", "feliz", "empolgado", "surpreso", "pensativo",
    "confuso", "serio", "triste", "irritado", "rindo", "apontando",
]

SYSTEM = (
    "Você controla um avatar reativo num vídeo. Recebe a transcrição dividida em "
    "linhas numeradas. Para CADA linha, escolha a emoção do avatar que melhor reage "
    "ao que está sendo dito, usando SOMENTE estes valores:\n"
    + ", ".join(EMOTIONS) + ".\n"
    "Use 'neutro' quando não houver emoção marcante. Considere o tom e o contexto "
    "(empolgação, dúvida, surpresa, crítica, piada). Retorne uma escolha por linha."
)


class Pick(BaseModel):
    line_index: int = Field(description="índice da linha")
    emotion: str = Field(description="uma das emoções permitidas")


class EmotionPlan(BaseModel):
    picks: list[Pick]


def classify(lines: list, provider: str = "openai", api_key: str | None = None,
             min_hold: float = 1.5) -> list[list]:
    """Retorna segmentos [start, end, emotion] em tempo da comp."""
    if not lines:
        return []
    numbered = "\n".join(f"[{i}] ({l.start:.1f}s) {l.text}" for i, l in enumerate(lines))
    user = f"Transcrição ({len(lines)} linhas):\n\n{numbered}"

    plan = structured(provider, SYSTEM, user, EmotionPlan, api_key=api_key)
    per_line = {}
    for p in plan.picks:
        emo = p.emotion.strip().lower()
        per_line[p.line_index] = emo if emo in EMOTIONS else "neutro"

    return _build_segments(lines, per_line, min_hold)


def neutral_timeline(lines: list) -> list[list]:
    """Fallback: tudo 'neutro' (usado se a IA falhar)."""
    return _build_segments(lines, {}, min_hold=0.0)


def _build_segments(lines: list, per_line: dict, min_hold: float) -> list[list]:
    raw = [[l.start, l.end, per_line.get(i, "neutro")] for i, l in enumerate(lines)]

    # une linhas consecutivas com a mesma emoção
    merged: list[list] = []
    for s in raw:
        if merged and merged[-1][2] == s[2]:
            merged[-1][1] = s[1]
        else:
            merged.append(list(s))

    # intervalo mínimo: emoção curta demais é absorvida pela anterior (anti-flicker)
    out: list[list] = []
    for s in merged:
        if out and (s[1] - s[0]) < min_hold:
            out[-1][1] = s[1]
        else:
            out.append(s)
    return out
