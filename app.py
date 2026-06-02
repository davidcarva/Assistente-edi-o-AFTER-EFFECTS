"""Assistente de Edição — interface gráfica (Tkinter, tema escuro).

Rodar:  python app.py     (a partir da pasta do projeto)
"""
from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from src import cli, voice, styles as ST

# Paleta (escuro, estilo moderno)
BG = "#0d0d0d"
SIDEBAR = "#171717"
PANEL = "#202020"
BORDER = "#2f2f2f"
TEXT = "#ececec"
MUTED = "#8e8e8e"
ACCENT = "#10a37f"
ACCENT_HOVER = "#1abd92"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.cfg = cli.load_config("config.json")
        self.recorder: voice.Recorder | None = None
        self.log_q: queue.Queue[str] = queue.Queue()
        self.busy = False
        self.ref_params: dict = {}
        self._provider_labels = {"OpenAI": ("openai", "openai_api_key"),
                                 "Claude": ("anthropic", "anthropic_api_key")}

        root.title("Assistente de Edição")
        root.geometry("980x680")
        root.configure(bg=BG)
        root.minsize(880, 560)
        self._setup_style()

        # ---- layout: sidebar (controles) + conteúdo (log) ----
        sidebar = tk.Frame(root, bg=SIDEBAR, width=380)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        content = tk.Frame(root, bg=BG)
        content.pack(side="left", fill="both", expand=True)

        self._build_sidebar(sidebar)
        self._build_content(content)

        self.root.after(100, self._drain_log)

    # ---------- estilo ----------
    def _setup_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=SIDEBAR, foreground=TEXT, font=("Segoe UI", 10))
        s.configure("Side.TLabel", background=SIDEBAR, foreground=TEXT)
        s.configure("Head.TLabel", background=SIDEBAR, foreground=MUTED,
                    font=("Segoe UI", 8, "bold"))
        s.configure("Title.TLabel", background=SIDEBAR, foreground=TEXT,
                    font=("Segoe UI Semibold", 16))
        s.configure("Hint.TLabel", background=SIDEBAR, foreground=MUTED, font=("Segoe UI", 8))
        s.configure("Status.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))

        s.configure("TButton", background=PANEL, foreground=TEXT, bordercolor=BORDER,
                    relief="flat", padding=7, focuscolor=SIDEBAR)
        s.map("TButton", background=[("active", BORDER), ("disabled", "#1a1a1a")],
              foreground=[("disabled", MUTED)])
        s.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                    font=("Segoe UI Semibold", 12), padding=11, relief="flat")
        s.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", BORDER)],
              foreground=[("disabled", MUTED)])

        s.configure("TEntry", fieldbackground=PANEL, foreground=TEXT, insertcolor=TEXT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=6)
        s.configure("TCheckbutton", background=SIDEBAR, foreground=TEXT, focuscolor=SIDEBAR)
        s.map("TCheckbutton", background=[("active", SIDEBAR)])
        s.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=TEXT,
                    arrowcolor=TEXT, bordercolor=BORDER, padding=5)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TEXT)],
              selectbackground=[("readonly", PANEL)], selectforeground=[("readonly", TEXT)])
        # dropdown das comboboxes
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    def _section(self, parent, title):
        ttk.Label(parent, text=title.upper(), style="Head.TLabel").pack(
            anchor="w", padx=18, pady=(16, 4))
        frame = tk.Frame(parent, bg=SIDEBAR)
        frame.pack(fill="x", padx=18)
        return frame

    # ---------- construção da UI ----------
    def _build_sidebar(self, sb):
        ttk.Label(sb, text="Assistente de Edição", style="Title.TLabel").pack(
            anchor="w", padx=18, pady=(18, 0))

        f = self._section(sb, "Projeto")
        self.media_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.media_var).pack(fill="x", pady=(0, 6))
        ttk.Button(f, text="Procurar vídeo...", command=self.pick_file).pack(fill="x")

        f = self._section(sb, "Comando")
        self.cmd_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.cmd_var).pack(fill="x", pady=(0, 6))
        self.rec_btn = ttk.Button(f, text="Gravar voz", command=self.toggle_record)
        self.rec_btn.pack(fill="x")
        ttk.Label(f, text='ex: "corte seco, legenda amarela no topo"',
                  style="Hint.TLabel", wraplength=320).pack(anchor="w", pady=(4, 0))

        f = self._section(sb, "Estilo")
        self.style_var = tk.StringVar()
        self.style_box = ttk.Combobox(f, textvariable=self.style_var, state="readonly")
        self.style_box.pack(fill="x", pady=(0, 6))
        brow = tk.Frame(f, bg=SIDEBAR); brow.pack(fill="x")
        ttk.Button(brow, text="Salvar estilo", command=self.save_style_dialog).pack(
            side="left", expand=True, fill="x", padx=(0, 3))
        ttk.Button(brow, text="Aprender de vídeo", command=self.learn_ref).pack(
            side="left", expand=True, fill="x", padx=(3, 0))
        self._refresh_styles()

        f = self._section(sb, "Gerador (audio+vídeo casados)")
        self.mode_var = tk.StringVar(value=self.cfg.get("mode", "editor"))
        mrow = tk.Frame(f, bg=SIDEBAR); mrow.pack(fill="x")
        ttk.Label(mrow, text="Modo:", style="Side.TLabel").pack(side="left")
        ttk.Combobox(mrow, textvariable=self.mode_var, state="readonly", width=10,
                     values=["editor", "gerador"]).pack(side="left", padx=6)
        drow = tk.Frame(f, bg=SIDEBAR); drow.pack(fill="x", pady=(6, 0))
        ttk.Label(drow, text="Duração alvo (s):", style="Side.TLabel").pack(side="left")
        self.target_dur_var = tk.IntVar(value=int(self.cfg.get("target_duration", 45)))
        ttk.Spinbox(drow, from_=15, to=120, increment=5,
                    textvariable=self.target_dur_var, width=6).pack(side="left", padx=6)
        ttk.Label(f, text="No modo 'gerador' a IA detecta beats e casa visual a visual com a fala.",
                  style="Hint.TLabel", wraplength=320).pack(anchor="w", pady=(4, 0))

        f = self._section(sb, "B-roll (imagens)")
        self.broll_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Gerar B-roll", variable=self.broll_var).pack(anchor="w")
        mrow = tk.Frame(f, bg=SIDEBAR); mrow.pack(fill="x", pady=(4, 0))
        ttk.Label(mrow, text="Fonte:", style="Side.TLabel").pack(side="left")
        self.broll_mode_var = tk.StringVar(value="both")
        ttk.Combobox(mrow, textvariable=self.broll_mode_var, state="readonly", width=8,
                     values=["both", "web", "ia"]).pack(side="left", padx=6)
        self.topic_ia_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(mrow, text="Tópicos com IA", variable=self.topic_ia_var).pack(side="left")

        f = self._section(sb, "Avatar reativo")
        self.avatar_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Usar avatar (emoções)", variable=self.avatar_var).pack(anchor="w")
        self.avatar_root_var = tk.StringVar(value=self.cfg.get("avatar_root", ""))
        arow = tk.Frame(f, bg=SIDEBAR); arow.pack(fill="x", pady=(4, 0))
        ttk.Entry(arow, textvariable=self.avatar_root_var).pack(side="left", fill="x", expand=True)
        ttk.Button(arow, text="Raiz...", command=self.pick_avatar_root).pack(side="left", padx=(6, 0))
        crow = tk.Frame(f, bg=SIDEBAR); crow.pack(fill="x", pady=(6, 0))
        ttk.Label(crow, text="Canal:", style="Side.TLabel").pack(side="left")
        self.avatar_channel_var = tk.StringVar(value=self.cfg.get("avatar_channel", ""))
        self.channel_box = ttk.Combobox(crow, textvariable=self.avatar_channel_var,
                                        state="readonly", width=16)
        self.channel_box.pack(side="left", padx=6)
        crow2 = tk.Frame(f, bg=SIDEBAR); crow2.pack(fill="x", pady=(6, 0))
        ttk.Label(crow2, text="Canto:", style="Side.TLabel").pack(side="left")
        self.avatar_corner_var = tk.StringVar(value=self.cfg.get("avatar_corner", "bottom-right"))
        ttk.Combobox(crow2, textvariable=self.avatar_corner_var, state="readonly", width=14,
                     values=["bottom-right", "bottom-left", "top-right", "top-left"]).pack(side="left", padx=6)
        self._refresh_channels()

        f = self._section(sb, "Inteligência Artificial")
        prow = tk.Frame(f, bg=SIDEBAR); prow.pack(fill="x", pady=(0, 6))
        cur = "Claude" if self.cfg.get("ai_provider") == "anthropic" else "OpenAI"
        self.provider_var = tk.StringVar(value=cur)
        prov = ttk.Combobox(prow, textvariable=self.provider_var, state="readonly", width=9,
                            values=["OpenAI", "Claude"])
        prov.pack(side="left")
        prov.bind("<<ComboboxSelected>>", lambda e: self._load_key_field())
        self.key_var = tk.StringVar()
        ttk.Entry(prow, textvariable=self.key_var, show="•").pack(
            side="left", fill="x", expand=True, padx=6)
        ttk.Button(f, text="Salvar chave", command=self.save_key).pack(fill="x")
        self._load_key_field()

        # botão principal
        self.gen_btn = ttk.Button(sb, text="Gerar", style="Accent.TButton", command=self.generate)
        self.gen_btn.pack(side="bottom", fill="x", padx=18, pady=18)

    def _build_content(self, ct):
        top = tk.Frame(ct, bg=BG); top.pack(fill="x", padx=16, pady=(16, 4))
        ttk.Label(top, text="Saída", background=BG, foreground=MUTED,
                  font=("Segoe UI", 8, "bold")).pack(side="left")
        ttk.Button(top, text="Abrir pasta de saída", command=self.open_out).pack(side="right")

        self.log = tk.Text(ct, wrap="word", state="disabled", bg=PANEL, fg=TEXT,
                           insertbackground=TEXT, relief="flat", highlightthickness=0,
                           font=("Consolas", 9), padx=12, pady=10)
        self.log.pack(fill="both", expand=True, padx=16, pady=8)

        self.status = ttk.Label(ct, text="pronto", style="Status.TLabel")
        self.status.pack(anchor="w", padx=16, pady=(0, 10))

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

    def pick_avatar_root(self):
        path = filedialog.askdirectory(title="Pasta raiz dos avatares (subpasta por canal)")
        if path:
            self.avatar_root_var.set(path)
            self._refresh_channels()

    def _refresh_channels(self):
        chans = cli.list_avatar_channels(self.avatar_root_var.get().strip())
        self.channel_box.configure(values=chans)
        if chans and self.avatar_channel_var.get() not in chans:
            self.avatar_channel_var.set(chans[0])

    def _load_key_field(self):
        _, key_field = self._provider_labels[self.provider_var.get()]
        self.key_var.set(self.cfg.get(key_field, ""))

    def save_key(self):
        provider, key_field = self._provider_labels[self.provider_var.get()]
        self.cfg["ai_provider"] = provider
        self.cfg[key_field] = self.key_var.get().strip()
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(self.cfg, f, ensure_ascii=False, indent=2)
        self._log(f"Chave de {self.provider_var.get()} salva no config.json.")

    def _refresh_styles(self):
        names = ["(nenhum)"] + list(ST.load_styles().keys())
        self.style_box.configure(values=names)
        if not self.style_var.get():
            self.style_var.set("(nenhum)")

    def save_style_dialog(self):
        if self.busy:
            return
        name = simpledialog.askstring("Salvar estilo", "Nome do estilo:", parent=self.root)
        if not name:
            return
        cfg = dict(self.cfg)
        cfg.update(self.ref_params)
        estilo = None if self.style_var.get() == "(nenhum)" else self.style_var.get()
        cfg = cli.resolve_cfg(cfg, comando=self.cmd_var.get().strip(), estilo=estilo, log=self._log)
        ST.save_style(name, cfg)
        self._refresh_styles()
        self.style_var.set(name)
        self._log(f"Estilo salvo: {name}")

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
            self._log("Selecione um arquivo de vídeo válido.")
            return
        self._set_busy(True, "processando...")
        threading.Thread(target=self._run, args=(media, self.cmd_var.get().strip()), daemon=True).start()

    def _run(self, media: str, comando: str):
        try:
            cfg = dict(self.cfg)
            cfg.update(self.ref_params)
            estilo = None if self.style_var.get() == "(nenhum)" else self.style_var.get()
            cfg = cli.resolve_cfg(cfg, comando=comando or None, estilo=estilo, log=self._log)
            cfg["mode"] = self.mode_var.get()
            cfg["target_duration"] = float(self.target_dur_var.get())
            if self.broll_var.get():
                cfg["broll_enabled"] = True
                cfg["broll_mode"] = self.broll_mode_var.get()
                cfg["topic_engine"] = "llm" if self.topic_ia_var.get() else "rules"
                provider, key_field = self._provider_labels[self.provider_var.get()]
                cfg["ai_provider"] = provider
                cfg[key_field] = self.key_var.get().strip() or cfg.get(key_field, "")
            if self.avatar_var.get():
                cfg["avatar_enabled"] = True
                cfg["avatar_root"] = self.avatar_root_var.get().strip()
                cfg["avatar_channel"] = self.avatar_channel_var.get().strip()
                cfg["avatar_corner"] = self.avatar_corner_var.get()
                # avatar usa IA -> garante provedor/chave atualizados
                provider, key_field = self._provider_labels[self.provider_var.get()]
                cfg["ai_provider"] = provider
                cfg[key_field] = self.key_var.get().strip() or cfg.get(key_field, "")
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
    root = tk.Tk()
    App(root)
    root.mainloop()
