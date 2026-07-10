"""Interpretador de comandos em linguagem natural (regras locais, offline, PT-BR).

Recebe um texto livre ('corta as pausas e legenda palavra-a-palavra em amarelo')
e devolve uma config atualizada + a lista de mudanças aplicadas (pra dar feedback).
"""
from __future__ import annotations

import re
import unicodedata


def _norm(s: str) -> str:
    s = s.lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s


COLORS = {
    "amarel": [1.0, 0.85, 0.1],
    "branc": [1.0, 1.0, 1.0],
    "verde": [0.3, 1.0, 0.4],
    "vermelh": [1.0, 0.2, 0.2],
    "azul": [0.3, 0.6, 1.0],
    "pret": [0.0, 0.0, 0.0],
    "laranj": [1.0, 0.6, 0.1],
    "rosa": [1.0, 0.4, 0.7],
    "rox": [0.6, 0.3, 1.0],
}


def parse_command(text: str, cfg: dict) -> tuple[dict, list[str]]:
    t = _norm(text)
    cfg = dict(cfg)
    notes: list[str] = []

    # ligar/desligar legendas
    if re.search(r"sem legenda|tira(r)? (a |as )?legenda|nao legenda", t):
        cfg["captions_enabled"] = False
        notes.append("legendas desativadas")
    elif "legenda" in t:
        cfg["captions_enabled"] = True

    # estilo da legenda
    if re.search(r"palavra a palavra|palavra-a-palavra|reels|tiktok|karaok|uma palavra", t):
        cfg["caption_style"] = "word"
        notes.append("legenda palavra-a-palavra")
    elif re.search(r"em linha|linha (cheia|inteira)|legenda normal|frase inteira", t):
        cfg["caption_style"] = "line"
        notes.append("legenda em linha")

    # cor (só muda se o comando fala de legenda/cor/texto)
    if re.search(r"legenda|cor|texto|amarel|verde|vermelh|azul|laranj|rosa|rox", t):
        for key, rgb in COLORS.items():
            if key in t:
                cfg["caption_color"] = rgb
                notes.append("cor da legenda alterada")
                break

    # posição
    if re.search(r"em cima|no topo|parte de cima|acima", t):
        cfg["caption_pos"] = "top"; notes.append("legenda no topo")
    elif re.search(r"no meio|centro vertical|meio da tela", t):
        cfg["caption_pos"] = "middle"; notes.append("legenda no meio")
    elif re.search(r"embaixo|em baixo|parte de baixo|rodape", t):
        cfg["caption_pos"] = "bottom"; notes.append("legenda embaixo")

    # tamanho
    if re.search(r"fonte maior|legenda maior|texto maior|aumenta(r)? (a )?legenda|maior", t):
        cfg["caption_scale"] = round(float(cfg.get("caption_scale", 1.0)) * 1.25, 3)
        notes.append("legenda maior")
    elif re.search(r"fonte menor|legenda menor|texto menor|diminui(r)? (a )?legenda|menor", t):
        cfg["caption_scale"] = round(float(cfg.get("caption_scale", 1.0)) * 0.8, 3)
        notes.append("legenda menor")

    # agressividade do corte
    if re.search(r"corte seco|bem apertad|mais apertad|sem pausa|tira(r)? (as )?pausas|"
                 r"corta(r)? (os )?silencio|remov(er|e) (os )?silencio|corta(r)? (as )?pausas", t):
        cfg["silence_threshold"] = min(float(cfg.get("silence_threshold", 0.35)), 0.25)
        cfg["padding"] = 0.02
        notes.append("cortes mais apertados")
    elif re.search(r"mais respir|menos apertad|mais folga|deixa as pausas|nao corta tanto", t):
        cfg["silence_threshold"] = 0.8
        cfg["padding"] = 0.1
        notes.append("cortes mais suaves")

    # contorno (stroke) da legenda
    if re.search(r"sem (contorno|stroke|borda)", t):
        cfg["caption_stroke"] = False
        notes.append("legenda sem contorno")
    elif re.search(r"com (contorno|stroke|borda)", t):
        cfg["caption_stroke"] = True
        notes.append("legenda com contorno")

    # B-roll (imagens ilustrativas)
    if re.search(r"sem (b-?roll|imagens|imagem|ilustra)", t):
        cfg["broll_enabled"] = False
        notes.append("b-roll desativado")
    elif re.search(r"b-?roll|com imagens|gera(r)? imagens|ilustra(r|cao|ç)|imagens ilustrativ", t):
        cfg["broll_enabled"] = True
        notes.append("b-roll ativado")
    if re.search(r"imagens da web|busca(r)? (na )?web|imagens reais", t):
        cfg["broll_mode"] = "web"; notes.append("b-roll via web")
    elif re.search(r"gera(r)? por ia|inteligencia artificial|imagens por ia|stable diffusion", t):
        cfg["broll_mode"] = "ia"; notes.append("b-roll por IA")

    return cfg, notes
