"""Seleção de B-roll com Claude (Anthropic API).

Manda as linhas da transcrição (com timestamps na comp) e recebe, em JSON
estruturado, quais momentos ilustrar — cada um com uma query de busca em inglês
e um prompt de Stable Diffusion. Muito superior às regras locais para contexto.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from pydantic import BaseModel, Field

MODEL = "claude-opus-4-7"

SYSTEM = (
    "Você é um diretor de arte de vídeo. Recebe a transcrição de um vídeo dividida "
    "em linhas numeradas (com o tempo de cada linha). Sua tarefa é escolher os "
    "momentos que merecem uma imagem de B-roll ilustrativa (estilo documentário), "
    "evitando momentos abstratos ou genéricos. Para cada momento escolhido, forneça:\n"
    "- line_index: o índice da linha que o B-roll deve acompanhar.\n"
    "- query_en: uma busca de imagem CURTA e CONCRETA em INGLÊS (ex: 'basketball "
    "court at night', 'person working on laptop'). Substantivos visuais, não abstrações.\n"
    "- sd_prompt: um prompt em inglês para gerar a imagem por IA, com estilo "
    "fotográfico/cinemático de documentário.\n"
    "Escolha apenas momentos que rendam boas imagens. Espace os momentos ao longo do vídeo."
)


class Moment(BaseModel):
    line_index: int = Field(description="índice da linha da transcrição")
    query_en: str = Field(description="busca de imagem curta e concreta em inglês")
    sd_prompt: str = Field(description="prompt de Stable Diffusion em inglês")


class BrollPlan(BaseModel):
    moments: list[Moment]


@dataclass
class Topic:
    time: float
    query: str    # usado na busca web
    prompt: str   # usado na geração por IA
    score: float = 1.0


def plan_broll(lines: list, max_topics: int = 8, api_key: str | None = None,
               context: str = "") -> list[Topic]:
    """lines: lista de captions (objs com .start e .text) em ordem cronológica."""
    import anthropic

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "Chave da API Anthropic não encontrada. Defina ANTHROPIC_API_KEY "
            "ou 'anthropic_api_key' no config.json."
        )

    numbered = "\n".join(f"[{i}] ({l.start:.1f}s) {l.text}" for i, l in enumerate(lines))
    ctx = f"\nCONTEXTO DO VÍDEO:\n{context.strip()}\n" if context.strip() else ""
    user = (
        f"Transcrição ({len(lines)} linhas). Escolha no máximo {max_topics} momentos "
        f"para B-roll.{ctx}\n\n{numbered}"
    )

    client = anthropic.Anthropic(api_key=key)
    response = client.messages.parse(
        model=MODEL,
        max_tokens=4096,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_format=BrollPlan,
    )

    plan = response.parsed_output
    topics: list[Topic] = []
    for m in plan.moments[:max_topics]:
        if 0 <= m.line_index < len(lines):
            topics.append(Topic(
                time=lines[m.line_index].start,
                query=m.query_en.strip(),
                prompt=m.sd_prompt.strip(),
            ))
    topics.sort(key=lambda t: t.time)
    return topics
