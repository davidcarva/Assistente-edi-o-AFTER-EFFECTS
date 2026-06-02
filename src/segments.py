"""Detecta os trechos a manter (fala) removendo silêncios entre palavras."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Segment:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def detect_keep_segments(
    words: list,
    silence_threshold: float = 0.6,
    min_segment: float = 0.4,
    padding: float = 0.08,
) -> list[Segment]:
    """Agrupa palavras em trechos de fala, cortando silêncios longos.

    - silence_threshold: gap (s) entre palavras que conta como corte.
    - min_segment: descarta trechos mais curtos que isso.
    - padding: folga (s) adicionada antes/depois de cada trecho.
    """
    if not words:
        return []

    segments: list[Segment] = []
    cur_start = words[0].start
    cur_end = words[0].end

    for w in words[1:]:
        gap = w.start - cur_end
        if gap > silence_threshold:
            segments.append(Segment(cur_start, cur_end))
            cur_start = w.start
        cur_end = w.end
    segments.append(Segment(cur_start, cur_end))

    out: list[Segment] = []
    for s in segments:
        if s.duration < min_segment:
            continue
        out.append(Segment(max(0.0, s.start - padding), s.end + padding))
    return _merge_overlaps(out)


def _merge_overlaps(segs: list[Segment]) -> list[Segment]:
    if not segs:
        return []
    merged = [segs[0]]
    for s in segs[1:]:
        last = merged[-1]
        if s.start <= last.end:
            last.end = max(last.end, s.end)
        else:
            merged.append(s)
    return merged
