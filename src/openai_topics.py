"""Seleção de B-roll com a API da OpenAI (alternativa ao Claude).

Mesma ideia do llm_topics, mas usando o SDK da OpenAI com saída estruturada
(structured outputs via Pydantic).
"""
from __future__ import annotations

import os

from .llm_topics import BrollPlan, Topic, SYSTEM

MODEL = "gpt-4o-mini"


def plan_broll(lines: list, max_topics: int = 8, api_key: str | None = None) -> list[Topic]:
    from openai import OpenAI

    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "Chave da API OpenAI não encontrada. Defina OPENAI_API_KEY "
            "ou 'openai_api_key' no config.json."
        )

    numbered = "\n".join(f"[{i}] ({l.start:.1f}s) {l.text}" for i, l in enumerate(lines))
    user = (
        f"Transcrição ({len(lines)} linhas). Escolha no máximo {max_topics} momentos "
        f"para B-roll.\n\n{numbered}"
    )

    client = OpenAI(api_key=key)
    completion = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        response_format=BrollPlan,
    )

    plan = completion.choices[0].message.parsed
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
