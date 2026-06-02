"""Gera legendas em tempo DA COMP CORTADA.

Como o corte remove silêncios, o tempo da comp não bate com o tempo do vídeo
original. Aqui mapeamos cada palavra para o tempo da comp e agrupamos em linhas.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Caption:
    start: float   # tempo na comp
    end: float
    text: str


def _word_in_segment(w, seg) -> bool:
    mid = (w.start + w.end) / 2
    return seg.start <= mid <= seg.end


def _timed_words(words: list, segments: list) -> list[tuple[float, float, str]]:
    """Converte cada palavra para o tempo da comp cortada."""
    offsets = []
    t = 0.0
    for s in segments:
        offsets.append(t)
        t += (s.end - s.start)

    timed: list[tuple[float, float, str]] = []
    for w in words:
        for seg, off in zip(segments, offsets):
            if _word_in_segment(w, seg):
                cs = off + (w.start - seg.start)
                ce = off + (w.end - seg.start)
                timed.append((cs, ce, w.text))
                break
    return timed


def build_word_captions(words: list, segments: list, max_hold: float = 1.2) -> list[Caption]:
    """Uma legenda por palavra (estilo Reels). Cada palavra fica na tela até
    a próxima começar (limitado a max_hold para não 'segurar' em pausas)."""
    timed = _timed_words(words, segments)
    caps: list[Caption] = []
    for i, (cs, ce, text) in enumerate(timed):
        word = text.strip()
        if not word:
            continue
        if i + 1 < len(timed):
            end = min(timed[i + 1][0], cs + max_hold)
        else:
            end = ce
        end = max(end, cs + 0.12)  # tempo mínimo na tela
        caps.append(Caption(cs, end, word))
    return caps


def build_captions(
    words: list,
    segments: list,
    max_chars: int = 42,
    max_words: int = 8,
    max_duration: float = 4.0,
) -> list[Caption]:
    """Mapeia palavras -> tempo da comp e agrupa em linhas de legenda.

    Quebra de linha quando: passa de max_chars/max_words, a palavra termina
    em pontuação forte (. ? !), ou a linha já dura mais que max_duration.
    """
    timed = _timed_words(words, segments)

    captions: list[Caption] = []
    buf: list[tuple[float, float, str]] = []

    def flush():
        if not buf:
            return
        text = "".join(p[2] for p in buf).strip()
        captions.append(Caption(buf[0][0], buf[-1][1], text))
        buf.clear()

    for cs, ce, text in timed:
        buf.append((cs, ce, text))
        cur_text = "".join(p[2] for p in buf).strip()
        dur = buf[-1][1] - buf[0][0]
        ends_sentence = text.rstrip().endswith((".", "?", "!"))
        if (
            ends_sentence
            or len(cur_text) >= max_chars
            or len(buf) >= max_words
            or dur >= max_duration
        ):
            flush()
    flush()
    return captions
