"""Biblioteca de estilos nomeados (presets de 'look' completo).

Um estilo guarda os parâmetros de corte + legenda. O usuário cria/reusa por nome
('edita no estilo Reels'). Persistido em styles.json na pasta do projeto.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata

STYLES_PATH = "styles.json"

# Quais chaves da config fazem parte de um "estilo"
STYLE_KEYS = [
    "silence_threshold", "min_segment", "padding",
    "caption_font", "caption_style", "caption_color",
    "caption_pos", "caption_scale", "captions_enabled",
]


def _norm(s: str) -> str:
    s = s.lower().strip()
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def load_styles(path: str = STYLES_PATH) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_style(name: str, cfg: dict, path: str = STYLES_PATH) -> dict:
    styles = load_styles(path)
    styles[name] = {k: cfg[k] for k in STYLE_KEYS if k in cfg}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(styles, f, ensure_ascii=False, indent=2)
    return styles[name]


def match_style(name: str, path: str = STYLES_PATH) -> str | None:
    """Acha o nome real do estilo (case/acento-insensível, com match parcial)."""
    styles = load_styles(path)
    n = _norm(name)
    for k in styles:
        if _norm(k) == n:
            return k
    for k in styles:
        nk = _norm(k)
        if n and (n in nk or nk in n):
            return k
    return None


def apply_style(name: str, cfg: dict, path: str = STYLES_PATH) -> tuple[dict, str | None]:
    key = match_style(name, path)
    if key is None:
        return cfg, None
    cfg = dict(cfg)
    cfg.update(load_styles(path)[key])
    return cfg, key


def extract_style_name(text: str) -> str | None:
    """Extrai o nome após 'estilo' num comando ('no estilo Reels' -> 'Reels')."""
    m = re.search(r"estilo\s+(?:do |da |de |o |a )?([\wçãáéíóúâêôõ-]+)", text, re.IGNORECASE)
    return m.group(1) if m else None
