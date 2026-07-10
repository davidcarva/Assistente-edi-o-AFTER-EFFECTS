"""Chamada de IA com saída estruturada (Pydantic), unificando OpenAI e Claude."""
from __future__ import annotations

import os

ANTHROPIC_MODEL = "claude-opus-4-7"
OPENAI_MODEL = "gpt-4o-mini"


def structured(provider: str, system: str, user: str, schema, api_key: str | None = None,
               max_tokens: int = 4096):
    """Manda system+user e devolve uma instância do `schema` (Pydantic BaseModel)."""
    if provider == "anthropic":
        import anthropic
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("Chave Anthropic não encontrada (ANTHROPIC_API_KEY / anthropic_api_key).")
        client = anthropic.Anthropic(api_key=key)
        r = client.messages.parse(
            model=ANTHROPIC_MODEL, max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        return r.parsed_output

    # openai (default)
    from openai import OpenAI
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Chave OpenAI não encontrada (OPENAI_API_KEY / openai_api_key).")
    client = OpenAI(api_key=key)
    c = client.beta.chat.completions.parse(
        model=os.environ.get("AI_OPENAI_MODEL", OPENAI_MODEL),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format=schema,
    )
    return c.choices[0].message.parsed
