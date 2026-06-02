"""Obtém imagens de B-roll: busca na web (Openverse, sem chave) ou geração por IA
local (Stable Diffusion na GPU). Salva arquivos prontos pra importar no AE."""
from __future__ import annotations

import io
import os

_HEADERS = {"User-Agent": "AssistenteEdicao/0.1 (local tool)"}
_OPENVERSE = "https://api.openverse.org/v1/images/"

_sd_pipe = None  # cache do pipeline de IA


def _save_image_bytes(data: bytes, out_path: str, max_side: int = 1920) -> str | None:
    from PIL import Image
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return None
    w, h = img.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    img.save(out_path, "JPEG", quality=90)
    return out_path


def fetch_web_image(query: str, out_path: str) -> str | None:
    """Busca uma imagem de licença livre no Openverse e baixa a primeira válida."""
    import requests
    try:
        r = requests.get(
            _OPENVERSE,
            params={"q": query, "page_size": 5, "mature": "false"},
            headers=_HEADERS, timeout=20,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
    except Exception:
        return None

    for item in results:
        url = item.get("url") or item.get("thumbnail")
        if not url:
            continue
        try:
            img = requests.get(url, headers=_HEADERS, timeout=20)
            img.raise_for_status()
            saved = _save_image_bytes(img.content, out_path)
            if saved:
                return saved
        except Exception:
            continue
    return None


def _load_sd():
    global _sd_pipe
    if _sd_pipe is not None:
        return _sd_pipe
    import torch
    from diffusers import AutoPipelineForText2Image
    model = os.environ.get("SD_MODEL", "stabilityai/sd-turbo")
    pipe = AutoPipelineForText2Image.from_pretrained(model, torch_dtype=torch.float16)
    pipe = pipe.to("cuda")
    pipe.set_progress_bar_config(disable=True)
    _sd_pipe = pipe
    return pipe


def generate_ai_image(query: str, out_path: str, style: str = "documentary photo, cinematic, natural light, high detail") -> str | None:
    """Gera uma imagem por IA local (Stable Diffusion) na GPU."""
    try:
        pipe = _load_sd()
        prompt = f"{query}, {style}"
        image = pipe(prompt=prompt, num_inference_steps=3, guidance_scale=0.0).images[0]
        image.save(out_path, "JPEG", quality=90)
        return out_path
    except Exception:
        return None


def get_asset(web_query: str, ai_prompt: str, mode: str, out_dir: str, idx: int) -> str | None:
    """mode: 'web' | 'ia' | 'both' (tenta web, cai pra IA).

    web_query é o termo de busca; ai_prompt é o prompt de geração por IA.
    """
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"asset_{idx:02d}.jpg")
    if mode == "web":
        return fetch_web_image(web_query, out_path)
    if mode == "ia":
        return generate_ai_image(ai_prompt, out_path)
    # both
    return fetch_web_image(web_query, out_path) or generate_ai_image(ai_prompt, out_path)
