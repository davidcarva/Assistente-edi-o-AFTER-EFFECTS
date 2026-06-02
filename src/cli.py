"""CLI do Assistente de Edição (MVP): vídeo -> transcrição -> cortes -> .jsx para o AE.

Uso:
    python -m src.cli "C:\\caminho\\footage.mp4"
    python -m src.cli footage.mp4 --config config.json --out saida/
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import transcribe as T
from . import segments as S
from . import ae_script as A
from . import captions as C
from . import commands as CMD
from . import styles as ST
from . import topics as TP
from . import assets as AS
from . import emotions as EMO
from . import beats as BT


DEFAULTS = {
    "model": "large-v3",
    "device": "cuda",
    "compute_type": "float16",
    "language": "pt",
    "silence_threshold": 0.6,
    "min_segment": 0.4,
    "padding": 0.08,
    "caption_font": "SofiaPro-Bold",
    "caption_style": "word",
    "caption_color": [1, 1, 1],
    "caption_pos": "default",
    "caption_scale": 1.0,
    "captions_enabled": True,
    "broll_enabled": False,
    "broll_mode": "both",     # web | ia | both
    "broll_max": 8,
    "broll_duration": 3.0,
    "mode": "editor",          # editor | gerador (gerador usa beats com IA)
    "target_duration": 45.0,   # duração alvo (s) no modo gerador
    "topic_engine": "rules",   # rules | llm
    "ai_provider": "openai",   # openai | anthropic (quando topic_engine == llm)
    "anthropic_api_key": "",
    "openai_api_key": "",
    "avatar_enabled": False,
    "avatar_root": "",         # pasta raiz com uma subpasta por canal
    "avatar_channel": "",      # canal escolhido (subpasta)
    "avatar_dir": "",          # alternativa: pasta única direta (sem canais)
    "avatar_corner": "bottom-right",
    "avatar_size": 0.35,
}


def load_config(path: str | None) -> dict:
    cfg = dict(DEFAULTS)
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


def resolve_cfg(cfg: dict, comando: str | None = None, estilo: str | None = None, log=print) -> dict:
    """Aplica um estilo nomeado (se houver) e interpreta o comando em linguagem natural."""
    if estilo:
        cfg, applied = ST.apply_style(estilo, cfg)
        log(f"Estilo aplicado: {applied}" if applied else f"Estilo '{estilo}' nao encontrado.")
    if comando:
        sname = ST.extract_style_name(comando)
        if sname:
            cfg, applied = ST.apply_style(sname, cfg)
            if applied:
                log(f"Estilo aplicado: {applied}")
        cfg, notes = CMD.parse_command(comando, cfg)
        log("Ajustes: " + ("; ".join(notes) if notes else "nenhum (config padrao)"))
    return cfg


def learn_from_reference(ref_path: str, cfg: dict, log=print) -> dict:
    """Mede o ritmo de corte de um vídeo de referência e ajusta a agressividade do corte."""
    from . import reference as R
    log(f"Analisando ritmo de corte da referência: {os.path.basename(ref_path)}...")
    stats = R.analyze_cut_rhythm(ref_path)
    log(f"  {stats['n_scenes']} cenas, shot médio {stats['avg_shot']}s, {stats['cuts_per_min']} cortes/min")
    derived = R.derive_cut_params(stats)
    if derived:
        cfg = dict(cfg)
        cfg.update(derived)
        log(f"  Parâmetros derivados: silence_threshold={derived['silence_threshold']}, padding={derived['padding']}")
    return cfg


def list_avatar_channels(root: str) -> list[str]:
    """Lista as subpastas (canais) da raiz que tenham pelo menos um 'neutro.*'."""
    if not root or not os.path.isdir(root):
        return []
    chans = []
    for name in sorted(os.listdir(root)):
        sub = os.path.join(root, name)
        if os.path.isdir(sub) and _resolve_avatar(sub, "neutro"):
            chans.append(name)
    return chans


def _resolve_avatar(avatar_dir: str, emotion: str) -> str | None:
    """Acha o arquivo do avatar para uma emoção (tenta png/webp/jpg; cai pra 'neutro')."""
    for emo in (emotion, "neutro"):
        for ext in (".png", ".webp", ".jpg", ".jpeg"):
            p = os.path.join(avatar_dir, emo + ext)
            if os.path.exists(p):
                return p
    return None


def process(media: str, cfg: dict, out: str = "saida", log=print) -> dict:
    """Roda o pipeline completo (transcrição -> cortes -> legendas -> .jsx).

    `log` é um callback (str) -> None para reportar progresso (print ou GUI).
    Retorna dict com os caminhos gerados e estatísticas.
    """
    os.makedirs(out, exist_ok=True)
    base = os.path.splitext(os.path.basename(media))[0]

    log(f"[1/3] Transcrevendo (modelo {cfg['model']}, {cfg['device']})...")
    words = T.transcribe(
        media, model_name=cfg["model"], device=cfg["device"],
        compute_type=cfg["compute_type"], language=cfg["language"],
    )
    log(f"      {len(words)} palavras transcritas.")

    transcript_path = os.path.join(out, f"{base}.transcript.json")
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(T.words_to_dicts(words), f, ensure_ascii=False, indent=2)

    log("[2/3] Detectando trechos a manter...")
    segs = S.detect_keep_segments(
        words, silence_threshold=cfg["silence_threshold"],
        min_segment=cfg["min_segment"], padding=cfg["padding"],
    )
    kept = sum(s.duration for s in segs)
    log(f"      {len(segs)} trechos, {kept:.1f}s de fala mantidos.")

    cuts_path = os.path.join(out, f"{base}.cuts.json")
    with open(cuts_path, "w", encoding="utf-8") as f:
        json.dump([{"start": s.start, "end": s.end} for s in segs], f, indent=2)

    if not cfg["captions_enabled"]:
        caps = []
        log("      legendas desativadas.")
    elif cfg["caption_style"] == "word":
        caps = C.build_word_captions(words, segs)
        log(f"      {len(caps)} legendas geradas (estilo word).")
    else:
        caps = C.build_captions(words, segs)
        log(f"      {len(caps)} legendas geradas (estilo line).")

    broll = []
    ai_warning = None
    if cfg.get("broll_enabled"):
        is_gerador = cfg.get("mode") == "gerador"
        items: list[dict] = []   # cada item: {time, duration, query, prompt}

        # --- modo Gerador: beats com IA (duração por beat) ---
        if is_gerador:
            lines = C.build_captions(words, segs)
            try:
                log("[Gerador] Detectando beats com IA...")
                api_key = (cfg.get("anthropic_api_key") if cfg.get("ai_provider") == "anthropic"
                           else cfg.get("openai_api_key")) or None
                bts = BT.plan_beats(
                    lines, provider=cfg.get("ai_provider", "openai"),
                    api_key=api_key, target_duration=cfg.get("target_duration", 45.0),
                )
                items = [{"time": b.start, "duration": b.duration,
                          "query": b.query, "prompt": b.prompt} for b in bts]
                log(f"      {len(bts)} beats: " + ", ".join(b.intent for b in bts))
            except Exception as e:
                msg = str(e)
                if "insufficient_quota" in msg or "exceeded your current quota" in msg:
                    ai_warning = "Gerador: IA sem crédito. Caí pras regras locais."
                else:
                    ai_warning = f"Gerador: a IA falhou ({type(e).__name__}). Caí pras regras locais."
                log("      " + ai_warning)

        # --- modo Editor com IA: tópicos por LLM ---
        if not items and not is_gerador and cfg.get("topic_engine") == "llm":
            lines = C.build_captions(words, segs)
            try:
                if cfg.get("ai_provider") == "anthropic":
                    log("[B-roll] Escolhendo tópicos com Claude (IA)...")
                    from . import llm_topics as LLM
                    tops = LLM.plan_broll(lines, max_topics=cfg["broll_max"],
                                          api_key=cfg.get("anthropic_api_key") or None)
                else:
                    log("[B-roll] Escolhendo tópicos com OpenAI (IA)...")
                    from . import openai_topics as OAI
                    tops = OAI.plan_broll(lines, max_topics=cfg["broll_max"],
                                          api_key=cfg.get("openai_api_key") or None)
                items = [{"time": t.time, "duration": cfg["broll_duration"],
                          "query": t.query, "prompt": t.prompt} for t in tops]
            except Exception as e:
                msg = str(e)
                if "insufficient_quota" in msg or "exceeded your current quota" in msg:
                    ai_warning = ("A IA não rodou: a conta de IA está sem crédito. "
                                  "Usei as regras locais.")
                else:
                    ai_warning = f"A IA não rodou ({type(e).__name__}). Usei as regras locais."
                log("      " + ai_warning)

        # --- fallback final: regras offline ---
        if not items:
            log("[B-roll] Detectando tópicos da fala (regras)...")
            tops = TP.extract_topics(words, segs, max_topics=cfg["broll_max"])
            items = [{"time": t.time, "duration": cfg["broll_duration"],
                      "query": t.query, "prompt": t.prompt} for t in tops]

        log("      queries: " + ", ".join(it["query"] for it in items))
        assets_dir = os.path.join(out, f"{base}_assets")
        for i, it in enumerate(items):
            path = AS.get_asset(it["query"], it["prompt"], cfg["broll_mode"], assets_dir, i)
            if path:
                broll.append({"path": path, "time": it["time"], "duration": it["duration"]})
                log(f"      [{i+1}/{len(items)}] '{it['query']}' -> {os.path.basename(path)}")
            else:
                log(f"      [{i+1}/{len(items)}] '{it['query']}' -> sem asset")
        log(f"      {len(broll)} imagens de B-roll prontas.")

    avatar = []
    if cfg.get("avatar_enabled"):
        root = cfg.get("avatar_root") or ""
        chan = cfg.get("avatar_channel") or ""
        if root and chan:
            adir = os.path.join(root, chan)
        else:
            adir = cfg.get("avatar_dir") or ""
        if not os.path.isdir(adir):
            log(f"[Avatar] pasta não encontrada: {adir!r} — avatar ignorado.")
        else:
            if chan:
                log(f"[Avatar] canal: {chan}")
            lines = C.build_captions(words, segs)
            try:
                log("[Avatar] Classificando emoções com IA...")
                emo_segs = EMO.classify(
                    lines, provider=cfg.get("ai_provider", "openai"),
                    api_key=(cfg.get("openai_api_key") if cfg.get("ai_provider") != "anthropic"
                             else cfg.get("anthropic_api_key")) or None,
                )
            except Exception as e:
                msg = str(e)
                if "insufficient_quota" in msg or "exceeded your current quota" in msg:
                    ai_warning = ("Avatar: a IA está sem crédito; usei só 'neutro'.")
                else:
                    ai_warning = f"Avatar: a IA não rodou ({type(e).__name__}); usei só 'neutro'."
                log("      " + ai_warning)
                emo_segs = EMO.neutral_timeline(lines)

            used = []
            for s, e, emo in emo_segs:
                p = _resolve_avatar(adir, emo)
                if p:
                    avatar.append({"path": p, "start": s, "end": e})
                    used.append(emo)
            log(f"      {len(avatar)} trocas de avatar. Emoções: {', '.join(dict.fromkeys(used))}")

    log("[3/3] Gerando script para o After Effects...")
    jsx = A.build_jsx(
        media, segs, comp_name=f"{base} - corte",
        captions=caps, caption_font=cfg["caption_font"],
        caption_style=cfg["caption_style"], caption_color=cfg["caption_color"],
        caption_pos=cfg["caption_pos"], caption_scale=cfg["caption_scale"],
        broll=broll, avatar=avatar, avatar_corner=cfg["avatar_corner"],
        avatar_size=cfg["avatar_size"],
    )
    jsx_path = os.path.join(out, f"{base}.build.jsx")
    with open(jsx_path, "w", encoding="utf-8") as f:
        f.write(jsx)

    log("Pronto! Script AE: " + jsx_path)
    return {
        "transcript": transcript_path, "cuts": cuts_path, "jsx": jsx_path,
        "n_words": len(words), "n_segments": len(segs), "n_captions": len(caps),
        "ai_warning": ai_warning,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Assistente de Edição — corte por transcrição")
    p.add_argument("media", help="arquivo de vídeo ou áudio")
    p.add_argument("--config", default="config.json", help="JSON de configuração")
    p.add_argument("--out", default="saida", help="pasta de saída")
    p.add_argument("--comando", default=None, help="comando em linguagem natural (texto)")
    p.add_argument("--voz", action="store_true", help="grava o comando pelo microfone")
    p.add_argument("--estilo", default=None, help="aplica um estilo nomeado (ver styles.json)")
    p.add_argument("--aprender-de", dest="aprender_de", default=None,
                   help="vídeo de referência: aprende o ritmo de corte dele")
    p.add_argument("--salvar-estilo", dest="salvar_estilo", default=None,
                   help="salva a config resultante como um estilo nomeado")
    p.add_argument("--broll", action="store_true", help="gera B-roll (imagens ilustrativas)")
    p.add_argument("--broll-mode", dest="broll_mode", default=None,
                   choices=["web", "ia", "both"], help="fonte do B-roll")
    p.add_argument("--topicos-ia", dest="topicos_ia", action="store_true",
                   help="escolhe os tópicos do B-roll com Claude (IA)")
    p.add_argument("--avatar", dest="avatar_dir", default=None,
                   help="pasta única com PNGs do avatar (neutro.png, ...); ativa o avatar")
    p.add_argument("--avatar-root", dest="avatar_root", default=None,
                   help="pasta raiz com uma subpasta por canal")
    p.add_argument("--canal", dest="avatar_channel", default=None,
                   help="nome do canal (subpasta) a usar")
    args = p.parse_args(argv)

    if not os.path.exists(args.media):
        print(f"Arquivo não encontrado: {args.media}", file=sys.stderr)
        return 1

    cfg = load_config(args.config)

    comando = args.comando
    if args.voz:
        from . import voice
        comando = voice.record_command(
            model_name=cfg["model"], device=cfg["device"],
            compute_type=cfg["compute_type"], language=cfg["language"],
        )
        print(f"Comando entendido: \"{comando}\"")

    if args.aprender_de:
        cfg = learn_from_reference(args.aprender_de, cfg)

    cfg = resolve_cfg(cfg, comando=comando, estilo=args.estilo)

    if args.broll:
        cfg["broll_enabled"] = True
    if args.broll_mode:
        cfg["broll_mode"] = args.broll_mode
    if args.topicos_ia:
        cfg["topic_engine"] = "llm"
    if args.avatar_dir:
        cfg["avatar_enabled"] = True
        cfg["avatar_dir"] = args.avatar_dir
    if args.avatar_root:
        cfg["avatar_enabled"] = True
        cfg["avatar_root"] = args.avatar_root
    if args.avatar_channel:
        cfg["avatar_channel"] = args.avatar_channel

    if args.salvar_estilo:
        ST.save_style(args.salvar_estilo, cfg)
        print(f"Estilo salvo: {args.salvar_estilo}")

    process(args.media, cfg, out=args.out)
    print("\nNo After Effects: File > Scripts > Run Script File... e selecione o .jsx")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
