"""Gera um script ExtendScript (.jsx) que monta uma comp no After Effects
com apenas os trechos mantidos, em sequência."""
from __future__ import annotations

import json
import os


def build_jsx(
    media_path: str,
    segments: list,
    comp_name: str = "Corte Automatico",
    captions: list | None = None,
    caption_font: str = "SofiaPro-Bold",
    caption_style: str = "word",
    caption_color: list | None = None,
    caption_pos: str = "default",
    caption_scale: float = 1.0,
    broll: list | None = None,
    avatar: list | None = None,
    avatar_corner: str = "bottom-right",
    avatar_size: float = 0.35,
) -> str:
    seg_pairs = [[round(s.start, 4), round(s.end, 4)] for s in segments]
    segs_js = json.dumps(seg_pairs)
    media_js = json.dumps(os.path.abspath(media_path))
    name_js = json.dumps(comp_name)
    font_js = json.dumps(caption_font)
    style_js = json.dumps(caption_style)
    color_js = json.dumps(caption_color or [1, 1, 1])
    pos_js = json.dumps(caption_pos)
    scale_js = json.dumps(float(caption_scale))

    caps = captions or []
    caps_data = [[round(c.start, 4), round(c.end, 4), c.text] for c in caps]
    caps_js = json.dumps(caps_data, ensure_ascii=False)

    broll_data = [[os.path.abspath(b["path"]), round(b["time"], 4), round(b["duration"], 4)]
                  for b in (broll or [])]
    broll_js = json.dumps(broll_data, ensure_ascii=False)

    avatar_data = [[os.path.abspath(a["path"]), round(a["start"], 4), round(a["end"], 4)]
                   for a in (avatar or [])]
    avatar_js = json.dumps(avatar_data, ensure_ascii=False)
    avatar_corner_js = json.dumps(avatar_corner)
    avatar_size_js = json.dumps(float(avatar_size))

    return f"""// Gerado pelo Assistente de Edição — corte + legendas por transcrição
(function() {{
    var mediaPath = {media_js};
    var segs = {segs_js};
    var compName = {name_js};
    var caps = {caps_js};
    var broll = {broll_js};
    var avatar = {avatar_js};
    var avatarCorner = {avatar_corner_js};
    var avatarSize = {avatar_size_js};
    var fontName = {font_js};
    var capStyle = {style_js};
    var capColor = {color_js};
    var capPos = {pos_js};
    var capScale = {scale_js};

    app.beginUndoGroup("Assistente: corte automatico");

    var io = new ImportOptions(File(mediaPath));
    var footage = app.project.importFile(io);

    var w = footage.width, h = footage.height;
    var fps = footage.frameRate || 30;

    var total = 0;
    for (var i = 0; i < segs.length; i++) total += (segs[i][1] - segs[i][0]);
    if (total <= 0) total = footage.duration;

    var comp = app.project.items.addComp(compName, w, h, footage.pixelAspect || 1, total, fps);

    var t = 0;
    for (var j = 0; j < segs.length; j++) {{
        var s = segs[j][0], e = segs[j][1];
        var dur = e - s;
        var layer = comp.layers.add(footage);
        layer.startTime = t - s;   // alinha o tempo de origem ao tempo da comp
        layer.inPoint = t;
        layer.outPoint = t + dur;
        t += dur;
    }}

    // suaviza as keyframes de uma propriedade (easy ease)
    function easeKeys(prop) {{
        var ease = new KeyframeEase(0, 75);
        for (var i = 1; i <= prop.numKeys; i++) {{
            var dim = (prop.value.length) ? prop.value.length : 1;
            var ein = [], eout = [];
            for (var d = 0; d < dim; d++) {{ ein.push(ease); eout.push(ease); }}
            try {{ prop.setTemporalEaseAtKey(i, ein, eout); }} catch (eEz) {{}}
        }}
    }}

    // B-roll — imagens ilustrativas (acima da footage, abaixo das legendas)
    // Elemento contido (não cobre a tela toda), pop in + pop out (escala a zero).
    var inDur = 0.22, outDur = 0.18;
    for (var b = 0; b < broll.length; b++) {{
        var bPath = broll[b][0], bTime = broll[b][1], bDur = broll[b][2];
        var bf;
        try {{ bf = app.project.importFile(new ImportOptions(File(bPath))); }}
        catch (eImp) {{ continue; }}
        var bl = comp.layers.add(bf);
        var iw = bf.width, ih = bf.height;
        // "fit" dentro de uma caixa (mantém a imagem inteira, sem cobrir a tela)
        var boxW = w * 0.82, boxH = h * 0.50;
        var fit = Math.min(boxW / iw, boxH / ih) * 100;
        bl.property("Transform").property("Anchor Point").setValue([iw / 2, ih / 2]);
        bl.property("Transform").property("Position").setValue([w / 2, h * 0.42]);
        bl.startTime = bTime;
        bl.inPoint = bTime;
        bl.outPoint = bTime + bDur;

        var t0 = bTime, t1 = bTime + bDur;
        var bsc = bl.property("Transform").property("Scale");
        bsc.setValueAtTime(t0, [0, 0]);                                  // pop in: começa em 0
        bsc.setValueAtTime(t0 + inDur * 0.7, [fit * 1.12, fit * 1.12]);  // overshoot
        bsc.setValueAtTime(t0 + inDur, [fit, fit]);                      // assenta
        bsc.setValueAtTime(t1 - outDur, [fit, fit]);                     // segura
        bsc.setValueAtTime(t1, [0, 0]);                                  // pop out: some em 0
        easeKeys(bsc);
    }}

    // Legendas — point text centralizado em w/2, com quebra de linha manual
    var isVertical = h > w;          // 9:16, Reels/Shorts
    var isWord = (capStyle === "word");   // estilo Reels palavra-a-palavra
    var divV = isWord ? 11 : 16, divH = isWord ? 13 : 20;
    var fontSize = Math.round((isVertical ? (w / divV) : (h / divH)) * capScale);
    var capYFrac;
    if (capPos === "top") capYFrac = 0.12;
    else if (capPos === "middle") capYFrac = 0.50;
    else if (capPos === "bottom") capYFrac = 0.86;
    else capYFrac = isVertical ? 0.74 : 0.82;
    var capY = Math.round(h * capYFrac);
    var strokeW = Math.max(2, Math.round(fontSize / 12));
    var usableW = isVertical ? (w * 0.90) : (w * 0.80);
    var maxChars = Math.max(8, Math.floor(usableW / (fontSize * 0.55)));

    // Resolve o nome PostScript real da fonte (ex: Sofia Pro Bold via Adobe Fonts)
    function resolveFont(want) {{
        try {{
            if (app.fonts && app.fonts.allFonts) {{
                var fonts = app.fonts.allFonts;
                for (var i = 0; i < fonts.length; i++) {{
                    if (fonts[i].postScriptName === want) return want;
                }}
                var wantFam = "sofia", wantStyle = "bold";
                for (var j = 0; j < fonts.length; j++) {{
                    var fam = (fonts[j].familyName || "").toLowerCase();
                    var st = (fonts[j].styleName || "").toLowerCase();
                    if (fam.indexOf(wantFam) >= 0 && st.indexOf(wantStyle) >= 0) {{
                        return fonts[j].postScriptName;
                    }}
                }}
            }}
        }} catch (e) {{}}
        return want;
    }}
    var resolvedFont = resolveFont(fontName);

    function wrapText(s, maxc) {{
        var parts = s.split(" ");
        var lines = [], line = "";
        for (var i = 0; i < parts.length; i++) {{
            var test = line.length ? (line + " " + parts[i]) : parts[i];
            if (test.length > maxc && line.length) {{
                lines.push(line); line = parts[i];
            }} else {{
                line = test;
            }}
        }}
        if (line.length) lines.push(line);
        return lines.join("\\r");
    }}

    for (var k = 0; k < caps.length; k++) {{
        var cStart = caps[k][0], cEnd = caps[k][1];
        var cText = wrapText(caps[k][2], maxChars);
        var tl = comp.layers.addText(cText);
        var doc = tl.property("Source Text").value;
        doc.fontSize = fontSize;
        try {{ doc.font = resolvedFont; }} catch (e) {{}}
        doc.fillColor = capColor;
        doc.applyStroke = true;
        doc.strokeColor = [0, 0, 0];
        doc.strokeWidth = strokeW;
        doc.strokeOverFill = false;
        doc.justification = ParagraphJustification.CENTER_JUSTIFY;
        tl.property("Source Text").setValue(doc);
        // point text com center justify -> ancora no centro horizontal
        tl.property("Transform").property("Position").setValue([w / 2, capY]);
        if (isWord) {{
            // "pop" de escala em cada palavra
            var sc = tl.property("Transform").property("Scale");
            sc.setValueAtTime(cStart, [80, 80]);
            sc.setValueAtTime(cStart + 0.07, [108, 108]);
            sc.setValueAtTime(cStart + 0.13, [100, 100]);
        }}
        tl.inPoint = cStart;
        tl.outPoint = cEnd;
    }}

    // Avatar reativo — canto fixo, troca de PNG conforme a emoção (camada por cima)
    var margin = h * 0.03;
    for (var a = 0; a < avatar.length; a++) {{
        var aPath = avatar[a][0], aStart = avatar[a][1], aEnd = avatar[a][2];
        var af;
        try {{ af = app.project.importFile(new ImportOptions(File(aPath))); }}
        catch (eAv) {{ continue; }}
        var al = comp.layers.add(af);
        var aw = af.width, ah = af.height;
        var target = h * avatarSize;            // altura desejada do avatar
        var asc = (target / ah) * 100;
        var dw = aw * asc / 100, dh = target;   // tamanho exibido
        al.property("Transform").property("Anchor Point").setValue([aw / 2, ah / 2]);
        al.property("Transform").property("Scale").setValue([asc, asc]);
        var cx, cy;
        if (avatarCorner === "bottom-left") {{ cx = margin + dw / 2; cy = h - margin - dh / 2; }}
        else if (avatarCorner === "top-right") {{ cx = w - margin - dw / 2; cy = margin + dh / 2; }}
        else if (avatarCorner === "top-left") {{ cx = margin + dw / 2; cy = margin + dh / 2; }}
        else {{ cx = w - margin - dw / 2; cy = h - margin - dh / 2; }}  // bottom-right
        al.property("Transform").property("Position").setValue([cx, cy]);
        al.inPoint = aStart;
        al.outPoint = aEnd;
    }}

    comp.openInViewer();
    app.endUndoGroup();
    var orient = (h > w) ? "vertical" : "horizontal";
    alert("Comp '" + compName + "' (" + w + "x" + h + ", " + orient + "): "
          + segs.length + " trechos, " + caps.length + " legendas, "
          + broll.length + " B-roll, " + avatar.length + " avatares.");
}})();
"""
