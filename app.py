"""Assistente de Edição — interface gráfica (CustomTkinter, tema escuro moderno).

Rodar:  python app.py     (a partir da pasta do projeto)
"""
from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, simpledialog

# --- diagnóstico de crash (inclusive nativo, ex: áudio/CUDA) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_DIR = os.path.join(BASE_DIR, "saida")
os.makedirs(_LOG_DIR, exist_ok=True)
CRASH_LOG = os.path.join(_LOG_DIR, "_crash.log")
try:
    import faulthandler
    faulthandler.enable(open(os.path.join(_LOG_DIR, "_faulthandler.log"), "w"))
except Exception:
    pass


def _log_crash(text: str) -> None:
    try:
        with open(CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass


def _sys_excepthook(exc, val, tb):
    import traceback
    _log_crash("[sys] " + "".join(traceback.format_exception(exc, val, tb)))


def _thread_excepthook(args):
    import traceback
    _log_crash("[thread] " + "".join(
        traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))


import sys as _sys
_sys.excepthook = _sys_excepthook
threading.excepthook = _thread_excepthook

import customtkinter as ctk

from src import cli, voice, styles as ST

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# Paleta
BG = "#0e0f11"
NAV = "#15171a"
CARD = "#1b1e22"
CARD2 = "#22262b"
TEXT = "#ececec"
MUTED = "#8a9099"
ACCENT = "#10a37f"
ACCENT_HOVER = "#13b88f"

# Textos de ajuda (botões "?")
HELP = {
    "perfil": "Perfil do canal: um preset que guarda TUDO de um canal (corte, legenda, "
              "tema, linguagem, fonte de imagens, avatar e voz). Escolha um e os controles "
              "se preenchem. 'Salvar perfil' grava o estado atual com um nome.",
    "instrucoes": "Diretrizes que vão direto para a IA: tom, linguagem, o que priorizar ou "
                  "evitar. Ex: 'tom dark e misterioso, frases curtas, foco em curiosidades'. "
                  "Isso molda como a IA escolhe beats, B-roll e emoções.",
    "aprender": "Mede o RITMO DE CORTE de um vídeo de referência (detecção de cena) e ajusta "
                "a agressividade do seu corte para combinar.",
    "modo": "Editor: você ajusta um vídeo existente. Gerador: a IA detecta 'beats' (momentos "
            "com intenção) e casa um visual sob medida com cada trecho da fala — melhor para "
            "shorts de 30-60s.",
    "duracao": "Duração-alvo do vídeo (s). No modo Gerador a IA usa isso para decidir quantos "
               "beats/visuais criar.",
    "contexto": "Diga do que o vídeo trata (ex: 'anime Naruto, cenas de batalha'). Sem isso a "
                "IA traduz palavras ao pé da letra e erra os visuais.",
    "broll": "B-roll = imagens ilustrativas entrando ao longo da fala, com pop-in/out.",
    "fonte": "De onde vêm as imagens. web: busca grátis (Openverse, ruim para anime/IP). "
             "ia: gera com Stable Diffusion local (bom para temas específicos). "
             "both: tenta web e cai para IA.",
    "topicos_ia": "Liga a IA para ESCOLHER o que ilustrar (em vez de palavras-chave por regra). "
                  "Entende contexto e gera buscas em inglês. Precisa de chave + crédito.",
    "avatar": "Mostra um avatar (PNG) que troca de emoção conforme a fala (a IA classifica). "
              "Organize por canal: pasta raiz com uma subpasta por canal, cada uma com "
              "neutro.png, feliz.png, etc.",
    "provider": "Qual IA de texto usar para beats/tópicos/emoção. OpenAI (gpt-4o-mini por "
                "padrão; gpt-4o entende mais contexto) ou Claude. Só o TEXTO vai para a nuvem.",
    "gemini": "O Gemini assiste o vídeo de referência (não só o texto) e cria um perfil de "
              "estilo automático: ritmo, legenda, tema e tom. Camada gratuita generosa.",
    "faceless": "Canal sem rosto: usa avatar + voz gerada por IA. Liga o avatar junto.",
    "voz": "Vozes da sua conta ElevenLabs. Clique 'Carregar vozes' depois de salvar a chave.",
    "roteiro": "Você dá um roteiro (.txt); a ElevenLabs gera a voz e o app monta o vídeo "
               "inteiro em cima dela (corte, legenda, avatar, B-roll).",
    "leg_estilo": "Palavra a palavra: cada palavra aparece no tempo exato da fala, com 'pop' "
                  "(estilo Reels/TikTok). Frase inteira: legenda estática tradicional, linha "
                  "completa na tela (estilo documentário/YouTube).",
    "leg_cor": "Cor do texto da legenda. Clique numa bolinha para escolher — a selecionada "
               "ganha um anel branco.",
    "leg_stroke": "Contorno preto ao redor das letras. Com contorno: lê bem sobre qualquer "
                  "fundo. Sem contorno: visual mais limpo, melhor sobre fundos escuros/lisos.",
    "leg_fonte": "Fonte da legenda. A lista mostra as fontes instaladas no seu Windows e o "
                 "preview abaixo mostra como ela fica. No After Effects, o app acha a versão "
                 "Bold da família automaticamente (funciona com Adobe Fonts também).",
    "leg_pos": "Onde a legenda fica na tela. Automática: o app decide pela orientação do "
               "vídeo (~74% da altura no vertical, ~82% no horizontal).",
}

# Cores de legenda disponíveis no seletor: (nome, hex do botão, RGB 0-1 para o AE)
CAP_COLORS = [
    ("Branco",   "#FFFFFF", (1.0, 1.0, 1.0)),
    ("Amarelo",  "#FFD918", (1.0, 0.85, 0.1)),
    ("Verde",    "#4DFF66", (0.3, 1.0, 0.4)),
    ("Vermelho", "#FF4040", (1.0, 0.2, 0.2)),
    ("Azul",     "#4D9AFF", (0.3, 0.6, 1.0)),
    ("Rosa",     "#FF66B3", (1.0, 0.4, 0.7)),
]
CAP_POS_LABELS = {"Automática": "default", "Topo": "top", "Meio": "middle", "Base": "bottom"}
CAP_POS_REVERSE = {v: k for k, v in CAP_POS_LABELS.items()}


class Tooltip:
    """Tooltip simples para qualquer widget (mostra texto no hover)."""
    def __init__(self, widget, text):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 26
        y = self.widget.winfo_rooty() + 24
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, justify="left", bg="#2b2f34", fg=TEXT,
                 relief="solid", borderwidth=1, wraplength=340,
                 font=("Segoe UI", 9), padx=10, pady=7).pack()

    def _hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class App:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.config_path = os.path.join(BASE_DIR, "config.json")
        self.cfg = cli.load_config(self.config_path)
        self.recorder: voice.Recorder | None = None
        self.log_q: queue.Queue[str] = queue.Queue()
        self.busy = False
        self.ref_params: dict = {}
        self._voice_map: dict = {}
        self._provider_labels = {"OpenAI": ("openai", "openai_api_key"),
                                 "Claude": ("anthropic", "anthropic_api_key")}
        self.pages: dict = {}
        self.nav_buttons: dict = {}

        root.title("Assistente de Edição")
        root.geometry("1120x740")
        root.minsize(1000, 660)
        root.configure(fg_color=BG)

        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        self._install_error_logging()
        self._build_nav()
        self._build_main()

        self._show_page("Projeto")
        self.root.after(100, self._drain_log)

    def _install_error_logging(self):
        """Captura QUALQUER exceção de callback: grava em saida/_crash.log e mostra
        popup — evita o crash silencioso quando rodando via pythonw (sem console)."""
        import traceback

        def handler(exc, val, tb):
            msg = "".join(traceback.format_exception(exc, val, tb))
            try:
                with open(CRASH_LOG, "a", encoding="utf-8") as f:
                    f.write(msg + "\n")
            except Exception:
                pass
            try:
                self._log("ERRO: " + str(val))
            except Exception:
                pass
            try:
                messagebox.showerror("Ocorreu um erro", f"{type(val).__name__}: {val}\n\n"
                                     "Detalhes salvos em saida/_crash.log")
            except Exception:
                pass

        self.root.report_callback_exception = handler

    # ---------- helpers de layout ----------
    def _help(self, parent, key):
        b = ctk.CTkButton(parent, text="?", width=22, height=22, corner_radius=11,
                          fg_color=CARD2, hover_color="#33383e", text_color=MUTED,
                          font=ctk.CTkFont(size=12, weight="bold"))
        Tooltip(b, HELP.get(key, ""))
        return b

    def _card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14)
        card.pack(fill="x", padx=4, pady=8)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(12, 2))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=(2, 14))
        return inner

    def _row(self, parent):
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x", pady=4)
        return r

    def _hint(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=11), text_color=MUTED,
                     wraplength=560, justify="left").pack(anchor="w", pady=(2, 0))

    # ---------- navegação ----------
    def _build_nav(self):
        nav = ctk.CTkFrame(self.root, fg_color=NAV, corner_radius=0, width=210)
        nav.grid(row=0, column=0, sticky="nsw")
        nav.grid_propagate(False)

        ctk.CTkLabel(nav, text="🎬  Assistente", font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=TEXT).pack(anchor="w", padx=20, pady=(20, 4))
        ctk.CTkLabel(nav, text="de Edição", font=ctk.CTkFont(size=13),
                     text_color=MUTED).pack(anchor="w", padx=20, pady=(0, 18))

        for name, icon in [("Projeto", "📁"), ("Conteúdo", "✨"), ("IA & Voz", "🤖")]:
            b = ctk.CTkButton(nav, text=f"  {icon}   {name}", anchor="w",
                              font=ctk.CTkFont(size=13), height=42, corner_radius=10,
                              fg_color="transparent", hover_color=CARD,
                              text_color=TEXT, command=lambda n=name: self._show_page(n))
            b.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[name] = b

    def _show_page(self, name):
        for n, p in self.pages.items():
            p.grid_remove()
        self.pages[name].grid(row=0, column=0, sticky="nsew")
        for n, b in self.nav_buttons.items():
            b.configure(fg_color=ACCENT if n == name else "transparent",
                        text_color="#ffffff" if n == name else TEXT)
        self.header.configure(text=name)

    # ---------- área principal ----------
    def _build_main(self):
        main = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self.header = ctk.CTkLabel(main, text="", font=ctk.CTkFont(size=22, weight="bold"),
                                   text_color=TEXT)
        self.header.grid(row=0, column=0, sticky="w", padx=24, pady=(18, 6))

        container = ctk.CTkFrame(main, fg_color="transparent")
        container.grid(row=1, column=0, sticky="nsew", padx=18)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)
        for name in ("Projeto", "Conteúdo", "IA & Voz"):
            page = ctk.CTkScrollableFrame(container, fg_color="transparent")
            page.grid(row=0, column=0, sticky="nsew")
            page.grid_remove()
            self.pages[name] = page

        self._build_page_projeto(self.pages["Projeto"])
        self._build_page_conteudo(self.pages["Conteúdo"])
        self._build_page_ia(self.pages["IA & Voz"])

        # log + barra inferior
        logwrap = ctk.CTkFrame(main, fg_color=CARD, corner_radius=14)
        logwrap.grid(row=2, column=0, sticky="ew", padx=24, pady=(6, 6))
        head = ctk.CTkFrame(logwrap, fg_color="transparent"); head.pack(fill="x", padx=14, pady=(8, 0))
        ctk.CTkLabel(head, text="Saída", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=MUTED).pack(side="left")
        ctk.CTkButton(head, text="Abrir pasta de saída", width=150, height=26,
                      fg_color=CARD2, hover_color="#33383e", command=self.open_out).pack(side="right")
        self.log = tk.Text(logwrap, height=8, wrap="word", state="disabled", bg=CARD,
                           fg=TEXT, insertbackground=TEXT, relief="flat", highlightthickness=0,
                           font=("Consolas", 9), padx=10, pady=8)
        self.log.pack(fill="both", expand=False, padx=12, pady=(4, 10))

        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 14))
        bar.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(bar, text="pronto", text_color=MUTED,
                                   font=ctk.CTkFont(size=12))
        self.status.grid(row=0, column=0, sticky="w")
        self.gen_btn = ctk.CTkButton(bar, text="Gerar", width=200, height=46,
                                     font=ctk.CTkFont(size=15, weight="bold"),
                                     fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                     command=self.generate)
        self.gen_btn.grid(row=0, column=1, sticky="e")

    # ---------- páginas ----------
    def _build_page_projeto(self, pg):
        c = self._card(pg, "Vídeo")
        self.media_var = tk.StringVar()
        r = self._row(c)
        ctk.CTkEntry(r, textvariable=self.media_var, placeholder_text="caminho do vídeo...").pack(
            side="left", fill="x", expand=True)
        ctk.CTkButton(r, text="Procurar...", width=110, command=self.pick_file).pack(side="left", padx=(8, 0))

        c = self._card(pg, "Comando (texto ou voz)")
        self.cmd_var = tk.StringVar()
        r = self._row(c)
        ctk.CTkEntry(r, textvariable=self.cmd_var,
                     placeholder_text='ex: "corte seco, legenda amarela no topo"').pack(
            side="left", fill="x", expand=True)
        self.rec_btn = ctk.CTkButton(r, text="Gravar voz", width=110, fg_color=CARD2,
                                     hover_color="#33383e", command=self.toggle_record)
        self.rec_btn.pack(side="left", padx=(8, 0))

        c = self._card(pg, "Perfil do canal")
        r = self._row(c)
        self.style_var = tk.StringVar(value="(nenhum)")
        self.style_box = ctk.CTkOptionMenu(r, variable=self.style_var, values=["(nenhum)"],
                                           command=lambda _: self._on_profile_selected(),
                                           fg_color=CARD2, button_color=CARD2,
                                           button_hover_color="#33383e", width=220)
        self.style_box.pack(side="left")
        self._help(r, "perfil").pack(side="left", padx=8)
        self._refresh_styles()

        r = self._row(c)
        ctk.CTkLabel(r, text="Instruções do canal (linguagem, tom, regras)",
                     text_color=MUTED, font=ctk.CTkFont(size=11)).pack(side="left")
        self._help(r, "instrucoes").pack(side="left", padx=8)
        self.instr_txt = ctk.CTkTextbox(c, height=70, fg_color=CARD2, corner_radius=8,
                                        font=ctk.CTkFont(size=12))
        self.instr_txt.pack(fill="x", pady=(2, 4))
        self.instr_txt.insert("0.0", self.cfg.get("instructions", ""))
        self._hint(c, 'ex: "tom dark e misterioso; frases curtas; evite gírias; foco em curiosidades".')

        r = self._row(c)
        ctk.CTkButton(r, text="Salvar perfil", command=self.save_style_dialog).pack(
            side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(r, text="Aprender de vídeo", fg_color=CARD2, hover_color="#33383e",
                      command=self.learn_ref).pack(side="left", expand=True, fill="x", padx=(4, 0))
        self._help(r, "aprender").pack(side="left", padx=8)

    def _build_page_conteudo(self, pg):
        # ---- Legendas: tudo clicável, sem digitar comando ----
        c = self._card(pg, "Legendas")
        r = self._row(c)
        self.caps_on_var = tk.BooleanVar(value=self.cfg.get("captions_enabled", True))
        ctk.CTkCheckBox(r, text="Legendas ativas", variable=self.caps_on_var).pack(side="left")

        r = self._row(c)
        ctk.CTkLabel(r, text="Estilo:", text_color=TEXT, width=70, anchor="w").pack(side="left")
        self.cap_style_var = tk.StringVar(
            value="Palavra a palavra" if self.cfg.get("caption_style", "word") == "word"
            else "Frase inteira")
        ctk.CTkSegmentedButton(r, values=["Palavra a palavra", "Frase inteira"],
                               variable=self.cap_style_var, fg_color=CARD2,
                               selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
                               unselected_color=CARD2, unselected_hover_color="#33383e").pack(side="left")
        self._help(r, "leg_estilo").pack(side="left", padx=8)

        r = self._row(c)
        ctk.CTkLabel(r, text="Cor:", text_color=TEXT, width=70, anchor="w").pack(side="left")
        self._cap_color_btns = {}
        self._cap_rgb = tuple(self.cfg.get("caption_color", [1, 1, 1]))
        for name, hexc, rgb in CAP_COLORS:
            b = ctk.CTkButton(r, text="", width=26, height=26, corner_radius=13,
                              fg_color=hexc, hover_color=hexc,
                              border_color="#ffffff", border_width=0,
                              command=lambda n=name: self._pick_cap_color(n))
            b.pack(side="left", padx=3)
            Tooltip(b, name)
            self._cap_color_btns[name] = b
        self._help(r, "leg_cor").pack(side="left", padx=8)
        self._select_color_by_rgb(self._cap_rgb)

        r = self._row(c)
        self.cap_stroke_var = tk.BooleanVar(value=self.cfg.get("caption_stroke", True))
        ctk.CTkCheckBox(r, text="Contorno preto (stroke)", variable=self.cap_stroke_var).pack(side="left")
        self._help(r, "leg_stroke").pack(side="left", padx=8)

        r = self._row(c)
        ctk.CTkLabel(r, text="Posição:", text_color=TEXT, width=70, anchor="w").pack(side="left")
        self.cap_pos_var = tk.StringVar(
            value=CAP_POS_REVERSE.get(self.cfg.get("caption_pos", "default"), "Automática"))
        ctk.CTkSegmentedButton(r, values=["Automática", "Topo", "Meio", "Base"],
                               variable=self.cap_pos_var, fg_color=CARD2,
                               selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
                               unselected_color=CARD2, unselected_hover_color="#33383e").pack(side="left")
        self._help(r, "leg_pos").pack(side="left", padx=8)

        r = self._row(c)
        ctk.CTkLabel(r, text="Tamanho:", text_color=TEXT, width=70, anchor="w").pack(side="left")
        self.cap_size_slider = ctk.CTkSlider(r, from_=0.6, to=2.0, number_of_steps=14,
                                             command=self._upd_capsize, width=200)
        self.cap_size_slider.set(float(self.cfg.get("caption_scale", 1.0)))
        self.cap_size_slider.pack(side="left")
        self.cap_size_lbl = ctk.CTkLabel(r, text=f"{float(self.cfg.get('caption_scale', 1.0)):.1f}x",
                                         text_color=ACCENT, width=44)
        self.cap_size_lbl.pack(side="left", padx=6)

        r = self._row(c)
        ctk.CTkLabel(r, text="Fonte:", text_color=TEXT, width=70, anchor="w").pack(side="left")
        stored_font = self.cfg.get("caption_font", "Sofia Pro")
        if stored_font.replace("-", "").lower().startswith("sofiapro"):
            stored_font = "Sofia Pro"
        self.font_var = tk.StringVar(value=stored_font)
        families = sorted({f for f in tkfont.families() if not f.startswith("@")})
        self.font_box = ctk.CTkComboBox(r, variable=self.font_var, values=families,
                                        command=lambda _=None: self._update_font_preview(),
                                        fg_color=CARD2, button_color=CARD2,
                                        button_hover_color="#33383e", width=260)
        self.font_box.pack(side="left")
        self._help(r, "leg_fonte").pack(side="left", padx=8)
        self.font_preview = ctk.CTkLabel(c, text="Legenda de Exemplo 123",
                                         text_color=TEXT, fg_color=CARD2, corner_radius=8,
                                         height=44)
        self.font_preview.pack(fill="x", pady=(6, 0))
        self._update_font_preview()

        c = self._card(pg, "Gerador (áudio + vídeo casados)")
        r = self._row(c)
        ctk.CTkLabel(r, text="Modo:", text_color=TEXT, width=70, anchor="w").pack(side="left")
        self.mode_var = tk.StringVar(value=self.cfg.get("mode", "editor"))
        ctk.CTkOptionMenu(r, variable=self.mode_var, values=["editor", "gerador"],
                          fg_color=CARD2, button_color=CARD2, button_hover_color="#33383e",
                          width=140).pack(side="left")
        self._help(r, "modo").pack(side="left", padx=8)

        r = self._row(c)
        ctk.CTkLabel(r, text="Duração:", text_color=TEXT, width=70, anchor="w").pack(side="left")
        self.dur_slider = ctk.CTkSlider(r, from_=15, to=120, number_of_steps=21,
                                        command=self._upd_dur, width=200)
        self.dur_slider.set(int(self.cfg.get("target_duration", 45)))
        self.dur_slider.pack(side="left")
        self.dur_lbl = ctk.CTkLabel(r, text=f"{int(self.cfg.get('target_duration', 45))}s",
                                    text_color=ACCENT, width=44)
        self.dur_lbl.pack(side="left", padx=6)
        self._help(r, "duracao").pack(side="left", padx=4)

        r = self._row(c)
        ctk.CTkLabel(r, text="Contexto do vídeo:", text_color=MUTED,
                     font=ctk.CTkFont(size=11)).pack(side="left")
        self._help(r, "contexto").pack(side="left", padx=8)
        self.ctx_var = tk.StringVar(value=self.cfg.get("video_context", ""))
        ctk.CTkEntry(c, textvariable=self.ctx_var,
                     placeholder_text='ex: "anime Naruto, cenas de batalha"').pack(fill="x", pady=(2, 0))

        c = self._card(pg, "B-roll (imagens)")
        r = self._row(c)
        self.broll_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(r, text="Gerar B-roll", variable=self.broll_var).pack(side="left")
        self._help(r, "broll").pack(side="left", padx=8)
        r = self._row(c)
        ctk.CTkLabel(r, text="Fonte:", text_color=TEXT, width=70, anchor="w").pack(side="left")
        self.broll_mode_var = tk.StringVar(value="both")
        ctk.CTkOptionMenu(r, variable=self.broll_mode_var, values=["both", "web", "ia"],
                          fg_color=CARD2, button_color=CARD2, button_hover_color="#33383e",
                          width=120).pack(side="left")
        self._help(r, "fonte").pack(side="left", padx=8)
        r = self._row(c)
        self.topic_ia_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(r, text="Tópicos com IA", variable=self.topic_ia_var).pack(side="left")
        self._help(r, "topicos_ia").pack(side="left", padx=8)

        c = self._card(pg, "Avatar reativo")
        r = self._row(c)
        self.avatar_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(r, text="Usar avatar (emoções)", variable=self.avatar_var).pack(side="left")
        self._help(r, "avatar").pack(side="left", padx=8)
        r = self._row(c)
        self.avatar_root_var = tk.StringVar(value=self.cfg.get("avatar_root", ""))
        ctk.CTkEntry(r, textvariable=self.avatar_root_var,
                     placeholder_text="pasta raiz dos avatares").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(r, text="Raiz...", width=90, fg_color=CARD2, hover_color="#33383e",
                      command=self.pick_avatar_root).pack(side="left", padx=(8, 0))
        r = self._row(c)
        ctk.CTkLabel(r, text="Canal:", text_color=TEXT, width=70, anchor="w").pack(side="left")
        self.avatar_channel_var = tk.StringVar(value=self.cfg.get("avatar_channel", ""))
        self.channel_box = ctk.CTkOptionMenu(r, variable=self.avatar_channel_var, values=[""],
                                             fg_color=CARD2, button_color=CARD2,
                                             button_hover_color="#33383e", width=180)
        self.channel_box.pack(side="left")
        r = self._row(c)
        ctk.CTkLabel(r, text="Canto:", text_color=TEXT, width=70, anchor="w").pack(side="left")
        self.avatar_corner_var = tk.StringVar(value=self.cfg.get("avatar_corner", "bottom-right"))
        ctk.CTkOptionMenu(r, variable=self.avatar_corner_var,
                          values=["bottom-right", "bottom-left", "top-right", "top-left"],
                          fg_color=CARD2, button_color=CARD2, button_hover_color="#33383e",
                          width=160).pack(side="left")
        self._refresh_channels()

    def _build_page_ia(self, pg):
        c = self._card(pg, "Provedor de texto (beats, tópicos, emoção)")
        r = self._row(c)
        cur = "Claude" if self.cfg.get("ai_provider") == "anthropic" else "OpenAI"
        self.provider_var = tk.StringVar(value=cur)
        ctk.CTkOptionMenu(r, variable=self.provider_var, values=["OpenAI", "Claude"],
                          command=lambda _: self._load_key_field(),
                          fg_color=CARD2, button_color=CARD2, button_hover_color="#33383e",
                          width=110).pack(side="left")
        self.key_var = tk.StringVar()
        ctk.CTkEntry(r, textvariable=self.key_var, show="•",
                     placeholder_text="API key").pack(side="left", fill="x", expand=True, padx=8)
        self._help(r, "provider").pack(side="left")
        ctk.CTkButton(c, text="Salvar chave", command=self.save_key).pack(fill="x", pady=(6, 0))
        self._load_key_field()

        c = self._card(pg, "Análise de vídeo (Gemini)")
        r = self._row(c)
        self.gemini_key_var = tk.StringVar(value=self.cfg.get("gemini_api_key", ""))
        ctk.CTkEntry(r, textvariable=self.gemini_key_var, show="•",
                     placeholder_text="Gemini API key").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(r, text="Salvar", width=80, fg_color=CARD2, hover_color="#33383e",
                      command=self.save_gemini_key).pack(side="left", padx=(8, 0))
        self._help(r, "gemini").pack(side="left", padx=4)
        ctk.CTkButton(c, text="Analisar vídeo e criar perfil...",
                      command=self.analyze_with_gemini).pack(fill="x", pady=(6, 0))

        c = self._card(pg, "Faceless + Voz (ElevenLabs)")
        r = self._row(c)
        self.faceless_var = tk.BooleanVar(value=self.cfg.get("faceless", False))
        ctk.CTkCheckBox(r, text="Canal faceless (avatar + voz)",
                        variable=self.faceless_var).pack(side="left")
        self._help(r, "faceless").pack(side="left", padx=8)
        r = self._row(c)
        self.eleven_key_var = tk.StringVar(value=self.cfg.get("elevenlabs_api_key", ""))
        ctk.CTkEntry(r, textvariable=self.eleven_key_var, show="•",
                     placeholder_text="ElevenLabs API key").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(r, text="Salvar", width=80, fg_color=CARD2, hover_color="#33383e",
                      command=self.save_eleven_key).pack(side="left", padx=(8, 0))
        r = self._row(c)
        ctk.CTkLabel(r, text="Voz:", text_color=TEXT, width=50, anchor="w").pack(side="left")
        self.voice_var = tk.StringVar(value=self.cfg.get("tts_voice", ""))
        self.voice_box = ctk.CTkOptionMenu(r, variable=self.voice_var, values=[""],
                                           fg_color=CARD2, button_color=CARD2,
                                           button_hover_color="#33383e", width=180)
        self.voice_box.pack(side="left")
        ctk.CTkButton(r, text="Carregar vozes", width=120, fg_color=CARD2,
                      hover_color="#33383e", command=self.load_voices).pack(side="left", padx=8)
        self._help(r, "voz").pack(side="left")
        r = self._row(c)
        ctk.CTkButton(r, text="Gerar vídeo a partir de roteiro...",
                      command=self.generate_from_script).pack(side="left", expand=True, fill="x")
        self._help(r, "roteiro").pack(side="left", padx=8)

    def _upd_dur(self, v):
        self.dur_lbl.configure(text=f"{int(float(v))}s")

    def _upd_capsize(self, v):
        self.cap_size_lbl.configure(text=f"{float(v):.1f}x")

    def _pick_cap_color(self, name):
        for n, hexc, rgb in CAP_COLORS:
            self._cap_color_btns[n].configure(border_width=3 if n == name else 0)
            if n == name:
                self._cap_rgb = rgb

    def _select_color_by_rgb(self, rgb):
        """Marca a bolinha correspondente a um RGB salvo (tolerância pequena)."""
        try:
            rgb = tuple(float(x) for x in rgb)
        except Exception:
            rgb = (1.0, 1.0, 1.0)
        best = "Branco"
        for n, hexc, ref in CAP_COLORS:
            if max(abs(a - b) for a, b in zip(rgb, ref)) < 0.08:
                best = n
                break
        self._pick_cap_color(best)

    def _update_font_preview(self):
        fam = self.font_var.get().strip()
        try:
            self.font_preview.configure(text=f"Legenda de Exemplo 123  —  {fam}",
                                        font=(fam, 18, "bold"))
        except Exception:
            self.font_preview.configure(text=f"(fonte '{fam}' não pôde ser exibida)")

    # ---------- helpers ----------
    def _log(self, msg: str):
        self.log_q.put(msg)

    def _drain_log(self):
        while not self.log_q.empty():
            msg = self.log_q.get_nowait()
            self.log.configure(state="normal")
            self.log.insert("end", msg + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        self.root.after(100, self._drain_log)

    def _set_busy(self, busy: bool, status: str):
        self.busy = busy
        self.status.configure(text=status)
        self.gen_btn.configure(state="disabled" if busy else "normal")

    # ---------- ações ----------
    def pick_file(self):
        path = filedialog.askopenfilename(
            title="Escolha o vídeo",
            filetypes=[("Vídeo", "*.mp4 *.mov *.mkv *.avi *.m4v"), ("Todos", "*.*")],
        )
        if path:
            self.media_var.set(path)

    def save_gemini_key(self):
        self.cfg["gemini_api_key"] = self.gemini_key_var.get().strip()
        self._save_config()
        self._log("Chave Gemini salva no config.json.")

    def _save_config(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.cfg, f, ensure_ascii=False, indent=2)

    def analyze_with_gemini(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(
            title="Vídeo de referência para analisar com Gemini",
            filetypes=[("Vídeo", "*.mp4 *.mov *.mkv *.avi *.m4v"), ("Todos", "*.*")],
        )
        if not path:
            return
        key = self.gemini_key_var.get().strip() or self.cfg.get("gemini_api_key") or None
        self._set_busy(True, "analisando com Gemini...")
        threading.Thread(target=self._do_analyze_with_gemini, args=(path, key), daemon=True).start()

    def _do_analyze_with_gemini(self, path: str, key):
        try:
            from src import video_analyzer as VA
            result = VA.analyze_video(path, api_key=key, log=self._log)
            name = result["name"] or "Estilo Gemini"
            existing = ST.load_styles()
            base, i = name, 2
            while name in existing:
                name = f"{base} {i}"; i += 1
            ST.save_style(name, result["style"])
            self.root.after(0, self._refresh_styles)
            self.root.after(0, lambda: self.style_var.set(name))
            self._log(f"Perfil salvo: '{name}' — {result.get('summary','')}")
            self.root.after(0, lambda: messagebox.showinfo(
                "Perfil criado", f"Perfil '{name}' criado a partir do vídeo.\n\n{result.get('summary','')}"))
        except Exception as e:
            self._log(f"Erro na análise Gemini: {e}")
            self.root.after(0, lambda m=str(e): messagebox.showerror("Falhou", f"Análise com Gemini falhou:\n{m}"))
        finally:
            self.root.after(0, lambda: self._set_busy(False, "pronto"))

    def save_eleven_key(self):
        self.cfg["elevenlabs_api_key"] = self.eleven_key_var.get().strip()
        self._save_config()
        self._log("Chave ElevenLabs salva no config.json.")

    def load_voices(self):
        if self.busy:
            return
        key = self.eleven_key_var.get().strip() or self.cfg.get("elevenlabs_api_key") or None
        self._set_busy(True, "carregando vozes...")
        threading.Thread(target=self._do_load_voices, args=(key,), daemon=True).start()

    def _do_load_voices(self, key):
        try:
            from src import tts
            voices = tts.list_voices(key)
            self._voice_map = {name: vid for vid, name in voices}
            names = list(self._voice_map.keys())
            self.root.after(0, lambda: self.voice_box.configure(values=names or [""]))
            if names:
                self.root.after(0, lambda: self.voice_var.set(names[0]))
            self._log(f"{len(names)} vozes carregadas da ElevenLabs.")
        except Exception as e:
            self._log(f"Erro ao carregar vozes: {e}")
        finally:
            self.root.after(0, lambda: self._set_busy(False, "pronto"))

    def generate_from_script(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(
            title="Roteiro (.txt) para gerar a voz",
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
        )
        if not path:
            return
        cfg = self._collect_cfg()                  # lê os widgets na thread principal
        cfg["faceless"] = True
        cfg["tts_enabled"] = True
        comando = self.cmd_var.get().strip()
        self._set_busy(True, "gerando voz + vídeo...")
        threading.Thread(target=self._do_generate_from_script,
                         args=(path, cfg, comando), daemon=True).start()

    def _do_generate_from_script(self, txt_path: str, cfg: dict, comando: str):
        try:
            with open(txt_path, "r", encoding="utf-8") as fh:
                script = fh.read().strip()
            if not script:
                self._log("Roteiro vazio.")
                self.root.after(0, lambda: self._set_busy(False, "pronto"))
                return
            mp3 = cli.voice_from_script(script, cfg, out="saida", log=self._log)
        except Exception as e:
            self._log(f"Erro ao gerar voz: {e}")
            self.root.after(0, lambda m=str(e): messagebox.showerror("ElevenLabs falhou", m))
            self.root.after(0, lambda: self._set_busy(False, "pronto"))
            return
        self._run(mp3, comando, cfg)

    def _refresh_styles(self):
        names = ["(nenhum)"] + list(ST.load_styles().keys())
        self.style_box.configure(values=names)
        if self.style_var.get() not in names:
            self.style_var.set("(nenhum)")

    def _on_profile_selected(self):
        name = self.style_var.get()
        if not name or name == "(nenhum)":
            return
        prof = ST.load_styles().get(name, {})
        if "instructions" in prof:
            self.instr_txt.delete("0.0", "end")
            self.instr_txt.insert("0.0", prof.get("instructions", ""))
        if "video_context" in prof:
            self.ctx_var.set(prof.get("video_context", ""))
        if "captions_enabled" in prof:
            self.caps_on_var.set(bool(prof["captions_enabled"]))
        if "caption_style" in prof:
            self.cap_style_var.set("Palavra a palavra" if prof["caption_style"] == "word"
                                   else "Frase inteira")
        if "caption_color" in prof:
            self._select_color_by_rgb(prof["caption_color"])
        if "caption_stroke" in prof:
            self.cap_stroke_var.set(bool(prof["caption_stroke"]))
        if "caption_pos" in prof:
            self.cap_pos_var.set(CAP_POS_REVERSE.get(prof["caption_pos"], "Automática"))
        if "caption_scale" in prof:
            self.cap_size_slider.set(float(prof["caption_scale"]))
            self._upd_capsize(prof["caption_scale"])
        if "caption_font" in prof:
            fname = prof["caption_font"]
            if fname.replace("-", "").lower().startswith("sofiapro"):
                fname = "Sofia Pro"
            self.font_var.set(fname)
            self._update_font_preview()
        if "broll_enabled" in prof:
            self.broll_var.set(bool(prof["broll_enabled"]))
        if "broll_mode" in prof:
            self.broll_mode_var.set(prof["broll_mode"])
        if "topic_engine" in prof:
            self.topic_ia_var.set(prof["topic_engine"] == "llm")
        if "mode" in prof:
            self.mode_var.set(prof["mode"])
        if "faceless" in prof:
            self.faceless_var.set(bool(prof["faceless"]))
        if "avatar_enabled" in prof:
            self.avatar_var.set(bool(prof["avatar_enabled"]))
        if "avatar_channel" in prof:
            self.avatar_channel_var.set(prof.get("avatar_channel", ""))
        if "tts_voice" in prof:
            self.voice_var.set(prof.get("tts_voice", ""))
        self._log(f"Perfil '{name}' carregado nos controles.")

    def save_style_dialog(self):
        if self.busy:
            return
        name = simpledialog.askstring("Salvar perfil do canal", "Nome do canal/perfil:", parent=self.root)
        if not name:
            return
        cfg = self._collect_cfg()
        cmd = self.cmd_var.get().strip()
        if cmd:
            cfg = cli.resolve_cfg(cfg, comando=cmd, estilo=None, log=self._log)
        ST.save_style(name, cfg)
        self._refresh_styles()
        self.style_var.set(name)
        self._log(f"Perfil salvo: {name}")

    def learn_ref(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(
            title="Vídeo de referência",
            filetypes=[("Vídeo", "*.mp4 *.mov *.mkv *.avi *.m4v"), ("Todos", "*.*")],
        )
        if not path:
            return
        self._set_busy(True, "analisando referência...")
        threading.Thread(target=self._do_learn_ref, args=(path,), daemon=True).start()

    def _do_learn_ref(self, path: str):
        try:
            cfg = cli.learn_from_reference(path, self.cfg, log=self._log)
            self.ref_params = {k: cfg[k] for k in ("silence_threshold", "padding") if k in cfg}
            self._log("Ritmo de corte da referência será aplicado no próximo 'Gerar'.")
        except Exception as e:
            self._log(f"Erro ao analisar referência: {e}")
        finally:
            self.root.after(0, lambda: self._set_busy(False, "pronto"))

    def pick_avatar_root(self):
        path = filedialog.askdirectory(title="Pasta raiz dos avatares (subpasta por canal)")
        if path:
            self.avatar_root_var.set(path)
            self._refresh_channels()

    def _refresh_channels(self):
        chans = cli.list_avatar_channels(self.avatar_root_var.get().strip())
        self.channel_box.configure(values=chans or [""])
        if chans and self.avatar_channel_var.get() not in chans:
            self.avatar_channel_var.set(chans[0])

    def save_key(self):
        provider, key_field = self._provider_labels[self.provider_var.get()]
        self.cfg["ai_provider"] = provider
        self.cfg[key_field] = self.key_var.get().strip()
        self._save_config()
        self._log(f"Chave de {self.provider_var.get()} salva no config.json.")

    def _load_key_field(self):
        _, key_field = self._provider_labels[self.provider_var.get()]
        self.key_var.set(self.cfg.get(key_field, ""))

    def open_out(self):
        out = os.path.abspath("saida")
        os.makedirs(out, exist_ok=True)
        os.startfile(out)

    def toggle_record(self):
        if self.busy:
            return
        if self.recorder is None:
            self.recorder = voice.Recorder()
            self.recorder.start()
            self.rec_btn.configure(text="Parar e usar")
            self.status.configure(text="gravando...")
        else:
            self.rec_btn.configure(text="Gravar voz", state="disabled")
            self._set_busy(True, "transcrevendo voz...")
            threading.Thread(target=self._finish_record, daemon=True).start()

    def _finish_record(self):
        rec, self.recorder = self.recorder, None
        try:
            text = rec.stop_and_transcribe(
                model_name=self.cfg["model"], device=self.cfg["device"],
                compute_type=self.cfg["compute_type"], language=self.cfg["language"],
            )
            self.root.after(0, lambda: self.cmd_var.set(text))
            self._log(f'Comando entendido: "{text}"')
        except Exception as e:
            self._log(f"Erro na gravação: {e}")
        finally:
            self.root.after(0, lambda: self.rec_btn.configure(state="normal"))
            self.root.after(0, lambda: self._set_busy(False, "pronto"))

    def generate(self):
        if self.busy:
            return
        media = self.media_var.get().strip()
        if not media or not os.path.exists(media):
            self._log("Selecione um arquivo de vídeo válido (aba Projeto).")
            return
        cfg = self._collect_cfg()                  # lê os widgets na thread principal
        comando = self.cmd_var.get().strip()
        self._set_busy(True, "processando...")
        threading.Thread(target=self._run, args=(media, comando, cfg), daemon=True).start()

    def _collect_cfg(self) -> dict:
        cfg = dict(self.cfg)
        cfg.update(self.ref_params)
        cfg["mode"] = self.mode_var.get()
        cfg["target_duration"] = float(self.dur_slider.get())
        cfg["video_context"] = self.ctx_var.get().strip()
        cfg["instructions"] = self.instr_txt.get("0.0", "end").strip()
        # legendas (seletores visuais)
        cfg["captions_enabled"] = bool(self.caps_on_var.get())
        cfg["caption_style"] = "word" if self.cap_style_var.get() == "Palavra a palavra" else "line"
        cfg["caption_color"] = list(self._cap_rgb)
        cfg["caption_stroke"] = bool(self.cap_stroke_var.get())
        cfg["caption_pos"] = CAP_POS_LABELS.get(self.cap_pos_var.get(), "default")
        cfg["caption_scale"] = round(float(self.cap_size_slider.get()), 2)
        cfg["caption_font"] = self.font_var.get().strip() or cfg.get("caption_font", "SofiaPro-Bold")
        cfg["broll_enabled"] = bool(self.broll_var.get())
        cfg["broll_mode"] = self.broll_mode_var.get()
        cfg["topic_engine"] = "llm" if self.topic_ia_var.get() else "rules"
        provider, key_field = self._provider_labels[self.provider_var.get()]
        cfg["ai_provider"] = provider
        cfg[key_field] = self.key_var.get().strip() or cfg.get(key_field, "")
        cfg["gemini_api_key"] = self.gemini_key_var.get().strip() or cfg.get("gemini_api_key", "")
        cfg["faceless"] = bool(self.faceless_var.get())
        cfg["avatar_enabled"] = bool(self.avatar_var.get()) or bool(self.faceless_var.get())
        cfg["avatar_root"] = self.avatar_root_var.get().strip()
        cfg["avatar_channel"] = self.avatar_channel_var.get().strip()
        cfg["avatar_corner"] = self.avatar_corner_var.get()
        cfg["elevenlabs_api_key"] = self.eleven_key_var.get().strip() or cfg.get("elevenlabs_api_key", "")
        cfg["tts_voice"] = self._voice_map.get(self.voice_var.get(), self.voice_var.get()) or cfg.get("tts_voice", "")
        return cfg

    def _run(self, media: str, comando: str, cfg: dict):
        try:
            if comando:
                cfg = cli.resolve_cfg(cfg, comando=comando, estilo=None, log=self._log)
            result = cli.process(media, cfg, out="saida", log=self._log)
            if result.get("ai_warning"):
                self.root.after(0, lambda m=result["ai_warning"]: messagebox.showwarning("IA não rodou", m))
            self._log("\nNo After Effects: File > Scripts > Run Script File... e selecione:")
            self._log(os.path.abspath(result["jsx"]))
        except Exception as e:
            self._log(f"ERRO: {e}")
        finally:
            self.root.after(0, lambda: self._set_busy(False, "pronto"))


if __name__ == "__main__":
    try:
        root = ctk.CTk()
        App(root)
        root.mainloop()
    except Exception:
        import traceback
        with open(CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(traceback.format_exc() + "\n")
        try:
            from tkinter import messagebox
            messagebox.showerror("Falha ao iniciar", traceback.format_exc())
        except Exception:
            pass
        raise
