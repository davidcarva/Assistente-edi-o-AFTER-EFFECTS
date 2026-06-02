"""Analisa um vídeo de referência e deriva parâmetros de corte (ritmo).

Mede a frequência/duração média dos cortes (detecção de cena) e mapeia para a
agressividade do corte por silêncio. É uma heurística: 'corte rápido' -> remover
mais pausas; 'corte lento' -> deixar mais respiro.
"""
from __future__ import annotations


def analyze_cut_rhythm(video_path: str) -> dict:
    """Retorna estatísticas de ritmo de corte do vídeo de referência."""
    from scenedetect import detect, ContentDetector

    scene_list = detect(video_path, ContentDetector())
    if not scene_list:
        return {"n_scenes": 0, "avg_shot": None, "cuts_per_min": 0.0, "total": 0.0}

    durations = [(end - start).get_seconds() for start, end in scene_list]
    total = sum(durations)
    avg_shot = total / len(durations)
    cuts_per_min = (len(scene_list) / total) * 60.0 if total > 0 else 0.0
    return {
        "n_scenes": len(scene_list),
        "avg_shot": round(avg_shot, 2),
        "cuts_per_min": round(cuts_per_min, 1),
        "total": round(total, 1),
    }


def derive_cut_params(stats: dict) -> dict:
    """Mapeia o ritmo medido para silence_threshold/padding.

    Quanto mais curto o shot médio (corte rápido), mais agressivo o corte de pausa.
    avg_shot ~1.5s -> bem apertado; ~6s+ -> mais solto.
    """
    avg = stats.get("avg_shot")
    if not avg:
        return {}
    # interpola avg_shot [1.5 .. 6.0] -> silence_threshold [0.20 .. 0.70]
    lo_shot, hi_shot = 1.5, 6.0
    lo_thr, hi_thr = 0.20, 0.70
    a = max(lo_shot, min(hi_shot, avg))
    frac = (a - lo_shot) / (hi_shot - lo_shot)
    thr = round(lo_thr + frac * (hi_thr - lo_thr), 2)
    pad = round(0.02 + frac * 0.08, 3)   # 0.02 .. 0.10
    return {"silence_threshold": thr, "padding": pad}
