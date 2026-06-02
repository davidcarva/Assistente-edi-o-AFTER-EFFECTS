"""Extrai 'o que ilustrar' (tópicos/palavras-chave) da transcrição, com timestamp
na comp cortada. Offline, por regras (sem POS tagger): remove stopwords e prioriza
substantivos prováveis (palavras longas, nomes próprios, números)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .captions import _timed_words


@dataclass
class Topic:
    time: float       # tempo na comp (s) onde a palavra é dita
    query: str        # termo de busca (web)
    score: float
    prompt: str = ""  # prompt de geração por IA (default: a própria query)

    def __post_init__(self):
        if not self.prompt:
            self.prompt = self.query


STOPWORDS = set("""
a o e é de da do das dos em no na nos nas um uma uns umas que se com por para porque
mas mais menos muito muita pouco como quando onde qual quais quem cujo cuja eu tu ele
ela nos vos eles elas meu minha seu sua nosso nossa este esta isso isto esse essa aquele
aquela aqui ali la lá então tá ta to tô né ne entao ja já ainda agora sempre nunca tudo
nada algo alguem alguém ser estar ter fazer ir vir ver dizer falar sobre entre sem ate até
também tambem assim cada todo toda todos todas qualquer vai vou foi era são sao tem têm
""".split())


def _norm(s: str) -> str:
    s = s.lower().strip()
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _clean_word(w: str) -> str:
    return re.sub(r"[^\wÀ-ÿ-]", "", w.strip())


def extract_topics(words: list, segments: list, max_topics: int = 8,
                   min_gap: float = 2.5) -> list[Topic]:
    """Retorna até `max_topics` tópicos espaçados por pelo menos `min_gap` segundos."""
    timed = _timed_words(words, segments)

    candidates: list[Topic] = []
    for cs, ce, raw in timed:
        word = _clean_word(raw)
        if len(word) < 4:
            continue
        if _norm(word) in STOPWORDS:
            continue
        nw = _norm(word)
        if nw.endswith("mente") and len(word) > 6:            # advérbios (-mente)
            continue
        if nw.endswith(("ando", "endo", "indo")):             # gerúndios (verbos)
            continue
        if not word[0].isupper() and len(word) > 5 and nw.endswith(("ar", "er", "ir")):
            continue                                          # infinitivos (verbos)
        score = 0.0
        score += min(len(word), 12) / 12.0          # palavras mais longas pontuam mais
        if word[0].isupper():                        # provável nome próprio
            score += 0.6
        if any(ch.isdigit() for ch in word):         # números (datas, quantidades)
            score += 0.4
        candidates.append(Topic(time=cs, query=word, score=round(score, 2)))

    # ordena por relevância, evita repetir o mesmo termo e respeita o espaçamento
    candidates.sort(key=lambda t: t.score, reverse=True)
    chosen: list[Topic] = []
    used_terms: set[str] = set()
    for c in candidates:
        key = _norm(c.query)
        if key in used_terms:
            continue
        if any(abs(c.time - x.time) < min_gap for x in chosen):
            continue
        chosen.append(c)
        used_terms.add(key)
        if len(chosen) >= max_topics:
            break

    chosen.sort(key=lambda t: t.time)   # ordem cronológica para a timeline
    return chosen
