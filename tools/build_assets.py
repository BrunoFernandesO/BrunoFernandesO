#!/usr/bin/env python3
"""Generate the profile README graphics (header, facts strip, project cards).

Every SVG is self-contained: Latin Modern (the LaTeX typeface) is subset and
embedded as WOFF2, so GitHub renders it without external requests.
Outputs assets/<lang>/<name>-<theme>.svg for lang in en, pt, es and theme in light, dark.

Requires: fonttools, brotli, and Latin Modern OTFs (TeX Live: fonts/opentype/public/lm).
Usage: python3 tools/build_assets.py [--fonts /usr/share/texmf/fonts/opentype/public/lm]
"""
import argparse
import base64
import io
import math
import os
from xml.sax.saxutils import escape

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- tokens
# Brass: cipher disks were brass instruments. Ink: iron-gall blue-black of
# manuscript ciphers. Steel: the colour of ciphertext before it is broken.
THEMES = {
    "light": {"ink": "#1A1F2B", "muted": "#566070", "brass": "#8C5B12",
              "steel": "#7D8899", "rule": "#D3D9E1", "faint": "#E7EBF0"},
    "dark":  {"ink": "#E9E4D8", "muted": "#9AA3B0", "brass": "#D4A04A",
              "steel": "#6E7C90", "rule": "#2E3644", "faint": "#252D3A"},
}

FONT_FILES = {
    "display": "lmroman17-regular.otf",
    "text": "lmroman12-regular.otf",
    "italic": "lmroman12-italic.otf",
    "mono": "lmmono10-regular.otf",
}
FAMILY = {"display": "LMDisplay", "text": "LMText", "italic": "LMItalic", "mono": "LMMono"}

# ---------------------------------------------------------------- copy
NAME = "Bruno Fernandes Ortega"
PLAIN = "BRUNO FERNANDES ORTEGA"
KEY = 3

COPY = {
    "en": {
        "tagline": "Software engineering student heading into research in cryptography, security and AI for hard problems.",
        "key": "key k = 3",
        "facts": [("5", "languages"), ("3", "TED-Ed talks"), ("2", "hackathon podiums"), ("8", "olympiad medals")],
        "cards": {
            "course": ("Criptografia na Prática", "Math and Python from zero to RSA",
                       "An 8-hour course I designed and taught at WorkInTech 2026. Every student broke Caesar and Vigenère with code they wrote.",
                       "public repository"),
            "foodbank": ("Food bank inventory", "Java, MySQL, JDBC",
                         "Console system that hands out the food closest to expiry first and keeps every delivery traceable.",
                         "in progress"),
            "academy": ("Seleta Academy", "Onboarding platform, DB1 Group",
                        "I proposed it, specified and architected it, and shipped it by directing AI coding agents. In production since November 2026.",
                        "private, internal"),
            "homelab": ("Security homelab", "Three machines, one decision record each",
                        "An attacker, a workstation and a deliberately vulnerable target. Built by hand first, automated later.",
                        "private for now"),
        },
        "gates": ["types", "lint", "tests"],
        "nodes": ["attacker", "workstation", "target"],
        "days": "days to expiry",
    },
    "pt": {
        "tagline": "Estudante de engenharia de software a caminho da pesquisa em criptografia, segurança e IA para problemas difíceis.",
        "key": "chave k = 3",
        "facts": [("5", "idiomas"), ("3", "palestras TED-Ed"), ("2", "pódios em hackathons"), ("8", "medalhas em olimpíadas")],
        "cards": {
            "course": ("Criptografia na Prática", "Matemática e Python do zero ao RSA",
                       "Curso de 8 horas que criei e ministrei na WorkInTech 2026. Todos os alunos quebraram César e Vigenère com código próprio.",
                       "repositório público"),
            "foodbank": ("Banco de alimentos", "Java, MySQL, JDBC",
                         "Sistema de console que distribui primeiro o que está mais perto de vencer e rastreia cada entrega.",
                         "em andamento"),
            "academy": ("Seleta Academy", "Plataforma de onboarding, DB1 Group",
                        "Propus, especifiquei, arquitetei e entreguei a plataforma conduzindo agentes de IA. Em produção desde novembro de 2026.",
                        "privado, interno"),
            "homelab": ("Homelab de segurança", "Três máquinas, um registro de decisão para cada",
                        "Um atacante, uma estação de trabalho e um alvo vulnerável de propósito. Primeiro à mão, depois automatizado.",
                        "privado por enquanto"),
        },
        "gates": ["tipos", "lint", "testes"],
        "nodes": ["atacante", "estação", "alvo"],
        "days": "dias até vencer",
    },
    "es": {
        "tagline": "Estudiante de ingeniería de software en camino a la investigación en criptografía, seguridad e IA para problemas difíciles.",
        "key": "clave k = 3",
        "facts": [("5", "idiomas"), ("3", "charlas TED-Ed"), ("2", "podios en hackathons"), ("8", "medallas en olimpiadas")],
        "cards": {
            "course": ("Criptografia na Prática", "Matemática y Python desde cero hasta RSA",
                       "Curso de 8 horas que diseñé e impartí en WorkInTech 2026. Todos los estudiantes rompieron César y Vigenère con su propio código.",
                       "repositorio público"),
            "foodbank": ("Banco de alimentos", "Java, MySQL, JDBC",
                         "Sistema de consola que entrega primero lo más cercano a vencer y deja cada entrega trazable.",
                         "en desarrollo"),
            "academy": ("Seleta Academy", "Plataforma de onboarding, DB1 Group",
                        "La propuse, la especifiqué, la arquitecté y la entregué dirigiendo agentes de IA. En producción desde noviembre de 2026.",
                        "privado, interno"),
            "homelab": ("Homelab de seguridad", "Tres máquinas, un registro de decisión para cada una",
                        "Un atacante, una estación de trabajo y un objetivo vulnerable a propósito. Primero a mano, después automatizado.",
                        "privado por ahora"),
        },
        "gates": ["tipos", "lint", "pruebas"],
        "nodes": ["atacante", "estación", "objetivo"],
        "days": "días para vencer",
    },
}

ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


# ---------------------------------------------------------------- fonts
class Fonts:
    def __init__(self, font_dir):
        self.tt = {role: TTFont(os.path.join(font_dir, f)) for role, f in FONT_FILES.items()}
        self.paths = {role: os.path.join(font_dir, f) for role, f in FONT_FILES.items()}

    def width(self, role, text, size):
        f = self.tt[role]
        cmap = f.getBestCmap()
        hmtx = f["hmtx"]
        upm = f["head"].unitsPerEm
        total = 0
        for ch in text:
            g = cmap.get(ord(ch))
            if g is None:
                g = cmap.get(ord("?"))
            total += hmtx[g][0]
        return total * size / upm

    def wrap(self, role, text, size, max_w):
        lines, cur = [], ""
        for word in text.split(" "):
            trial = (cur + " " + word).strip()
            if self.width(role, trial, size) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def face_css(self, used):
        """used: {role: set_of_chars} -> @font-face CSS with subset WOFF2 data URIs."""
        css = []
        for role, chars in used.items():
            if not chars:
                continue
            font = TTFont(self.paths[role])
            opts = Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga"]
            opts.name_IDs = []
            opts.notdef_outline = True
            sub = Subsetter(opts)
            sub.populate(text="".join(sorted(chars)))
            sub.subset(font)
            font.flavor = "woff2"
            buf = io.BytesIO()
            font.save(buf)
            b64 = base64.b64encode(buf.getvalue()).decode()
            css.append(f"@font-face{{font-family:{FAMILY[role]};src:url(data:font/woff2;base64,{b64}) format('woff2');}}")
        return "".join(css)


class Doc:
    """Collects SVG elements and the characters each font role needs."""

    def __init__(self, fonts, w, h, title):
        self.fonts, self.w, self.h, self.title = fonts, w, h, title
        self.els, self.css = [], []
        self.used = {r: set() for r in FONT_FILES}

    def text(self, role, x, y, s, size, fill, anchor="start", extra=""):
        self.used[role].update(s)
        self.els.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FAMILY[role]}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" {extra}>{escape(s)}</text>')

    def raw(self, s):
        self.els.append(s)

    def render(self):
        style = self.fonts.face_css(self.used) + "".join(self.css)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
                f'width="{self.w}" height="{self.h}" role="img" aria-label="{escape(self.title)}">'
                f'<title>{escape(self.title)}</title><style>{style}</style>'
                + "".join(self.els) + "</svg>")


# ---------------------------------------------------------------- header
def header(fonts, lang, t):
    c = COPY[lang]
    W, H = 1200, 380
    d = Doc(fonts, W, H, f"{NAME}. {c['tagline']}")
    x0 = 40

    # 1. the cipher line: each column rolls back KEY letters, ciphertext -> plaintext
    size, slot = 30, 40
    adv = fonts.width("mono", "M", size)
    base_y = 74
    d.raw(f'<clipPath id="win"><rect x="{x0 - 4}" y="{base_y - 27}" width="{adv * len(PLAIN) + 8:.1f}" height="36"/></clipPath>')
    cols = []
    for i, p in enumerate(PLAIN):
        if p == " ":
            continue
        pi = ALPHA.index(p)
        strip = [ALPHA[(pi + KEY - k) % 26] for k in range(KEY + 1)]  # cipher ... plain
        x = x0 + i * adv
        parts = []
        for k, ch in enumerate(strip):
            fill = t["brass"] if k == KEY else t["steel"]
            d.used["mono"].add(ch)
            parts.append(f'<text x="{x:.1f}" y="{base_y + k * slot}" font-family="{FAMILY["mono"]}" '
                         f'font-size="{size}" fill="{fill}">{ch}</text>')
        delay = 0.7 + i * 0.055
        cols.append(f'<g class="roll" style="animation-delay:{delay:.3f}s">{"".join(parts)}</g>')
    d.raw(f'<g clip-path="url(#win)">{"".join(cols)}</g>')

    # 2. the name, revealed by a left-to-right wipe once the line has decrypted
    name_size = 84
    while fonts.width("display", NAME, name_size) > 790:
        name_size -= 2
    name_y = 178
    d.raw(f'<mask id="wipe"><rect class="wipe" x="0" y="0" width="{W}" height="{H}" fill="#fff"/></mask>')
    d.used["display"].update(NAME)
    d.raw(f'<text x="{x0}" y="{name_y}" font-family="{FAMILY["display"]}" font-size="{name_size}" '
          f'fill="{t["ink"]}" mask="url(#wipe)">{escape(NAME)}</text>')
    d.raw(f'<line x1="{x0}" y1="{name_y + 26}" x2="{x0 + 120}" y2="{name_y + 26}" stroke="{t["brass"]}" stroke-width="2"/>')

    # 3. tagline
    tag_size = 29
    lines = fonts.wrap("italic", c["tagline"], tag_size, 790)
    while len(lines) > 2:
        tag_size -= 1
        lines = fonts.wrap("italic", c["tagline"], tag_size, 790)
    for j, ln in enumerate(lines):
        d.text("italic", x0, name_y + 76 + j * 40, ln, tag_size, t["muted"])

    # 4. the formula that the animation performs
    d.text("mono", x0, H - 34, "D(c) = (c − 3) mod 26", 20, t["steel"])

    # 5. the cipher disk: outer ring plaintext (fixed), inner ring ciphertext (turns 3 steps)
    cx, cy = 1022, 190
    r_out, r_mid, r_in = 152, 110, 68
    step = 360 / 26
    ring = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{t["rule"]}" stroke-width="1.5"/>'
            for r in (r_out, r_mid, r_in)]
    outer, inner = [], []
    for i, ch in enumerate(ALPHA):
        a = math.radians(i * step - 90)
        for r, bucket, fill, sz in ((131, outer, t["ink"], 19), (89, inner, t["steel"], 17)):
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            d.used["text"].add(ch)
            bucket.append(f'<text x="{x:.1f}" y="{y + sz * 0.34:.1f}" font-family="{FAMILY["text"]}" '
                          f'font-size="{sz}" fill="{fill}" text-anchor="middle" '
                          f'transform="rotate({i * step:.2f} {x:.1f} {y:.1f})">{ch}</text>')
        ta = math.radians((i + 0.5) * step - 90)
        for r1, r2, bucket in ((r_mid, r_out, outer), (r_in, r_mid, inner)):
            bucket.append(f'<line x1="{cx + r1 * math.cos(ta):.1f}" y1="{cy + r1 * math.sin(ta):.1f}" '
                          f'x2="{cx + r2 * math.cos(ta):.1f}" y2="{cy + r2 * math.sin(ta):.1f}" '
                          f'stroke="{t["rule"]}" stroke-width="1"/>')
    d.raw("".join(ring) + "".join(outer))
    d.raw(f'<g class="disk">{"".join(inner)}</g>')
    # index pointer and hub
    d.raw(f'<path d="M{cx - 9} {cy - r_out - 16} L{cx + 9} {cy - r_out - 16} L{cx} {cy - r_out - 3} Z" fill="{t["brass"]}"/>')
    d.raw(f'<rect x="{cx - 15}" y="{cy - r_out + 4}" width="30" height="{r_out - r_in - 8}" rx="5" fill="none" stroke="{t["brass"]}" stroke-width="1.8" class="idx"/>')
    d.raw(f'<circle cx="{cx}" cy="{cy}" r="4" fill="{t["brass"]}"/>')
    d.text("italic", cx, cy + r_out + 32, c["key"], 22, t["muted"], anchor="middle")

    roll_dist = KEY * slot
    d.css.append(
        ".roll{transform:translateY(-%dpx);animation:roll .9s cubic-bezier(.65,0,.35,1) both}"
        "@keyframes roll{from{transform:translateY(0)}to{transform:translateY(-%dpx)}}"
        ".disk{transform-origin:%dpx %dpx;transform:rotate(-%.3fdeg);animation:turn 1.9s cubic-bezier(.65,0,.35,1) .7s both}"
        "@keyframes turn{from{transform:rotate(0)}to{transform:rotate(-%.3fdeg)}}"
        ".wipe{transform-box:fill-box;transform-origin:0 0;animation:wipe 1.1s cubic-bezier(.65,0,.35,1) 2.2s both}"
        "@keyframes wipe{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
        ".idx{animation:idx .6s ease 2.6s both}@keyframes idx{from{opacity:0}to{opacity:1}}"
        "@media (prefers-reduced-motion:reduce){.roll,.disk,.wipe,.idx{animation:none}}"
        % (roll_dist, roll_dist, cx, cy, KEY * step, KEY * step))
    return d.render()


# ---------------------------------------------------------------- facts strip
def facts(fonts, lang, t):
    c = COPY[lang]
    W, H = 1200, 150
    d = Doc(fonts, W, H, ", ".join(f"{n} {label}" for n, label in c["facts"]))
    cell = W / len(c["facts"])
    for i, (n, label) in enumerate(c["facts"]):
        x = i * cell + 28
        d.text("display", x, 92, n, 76, t["brass"])
        lx = x + fonts.width("display", n, 76) + 14
        lab_lines = fonts.wrap("italic", label, 23, cell - (lx - i * cell) - 18)
        for j, ln in enumerate(lab_lines):
            d.text("italic", lx, 92 - (len(lab_lines) - 1 - j) * 27, ln, 23, t["ink"])
        if i:
            d.raw(f'<line x1="{i * cell:.1f}" y1="34" x2="{i * cell:.1f}" y2="112" stroke="{t["rule"]}" stroke-width="1.5"/>')
    d.raw(f'<line x1="0" y1="1" x2="{W}" y2="1" stroke="{t["rule"]}" stroke-width="2"/>'
          f'<line x1="0" y1="{H - 1}" x2="{W}" y2="{H - 1}" stroke="{t["rule"]}" stroke-width="2"/>')
    return d.render()


# ---------------------------------------------------------------- cards
def card(fonts, lang, t, key):
    title, sub, body, status = COPY[lang]["cards"][key]
    W, H = 600, 320
    d = Doc(fonts, W, H, f"{title}. {sub}. {body}")
    d.raw(f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="8" fill="none" stroke="{t["rule"]}" stroke-width="2"/>')
    px, text_w = 34, 330
    tsize = 34
    while fonts.width("display", title, tsize) > text_w + 40:
        tsize -= 1
    d.text("display", px, 70, title, tsize, t["ink"])
    sub_lines = fonts.wrap("italic", sub, 20, text_w + 20)
    for j, ln in enumerate(sub_lines):
        d.text("italic", px, 102 + j * 26, ln, 20, t["brass"])
    y = 102 + len(sub_lines) * 26 + 22
    for j, ln in enumerate(fonts.wrap("text", body, 19, text_w)):
        d.text("text", px, y + j * 27, ln, 19, t["muted"])
    d.text("mono", px, H - 30, status, 16, t["steel"])
    motif = {"course": motif_tabula, "foodbank": motif_expiry,
             "academy": motif_gates, "homelab": motif_lab}[key]
    motif(d, fonts, lang, t, 400, 40, 170, 240)
    return d.render()


def motif_tabula(d, fonts, lang, t, x, y, w, h):
    """A corner of the Vigenère square; the k = 3 row (Caesar) is set in brass."""
    n = 6
    cs = w / n
    for r in range(n):
        for col in range(n):
            ch = ALPHA[(r + col) % 26]
            hl = r == KEY
            fill = t["brass"] if hl else (t["ink"] if col == 0 or r == 0 else t["steel"])
            d.text("mono", x + col * cs + cs / 2, y + 20 + r * cs + cs / 2, ch, 19, fill, anchor="middle")
    d.raw(f'<rect x="{x}" y="{y + 20 + KEY * cs + 3:.1f}" width="{w}" height="{cs - 2:.1f}" rx="3" '
          f'fill="none" stroke="{t["brass"]}" stroke-width="1.5"/>')
    d.raw(f'<line x1="{x}" y1="{y + 20 + cs:.1f}" x2="{x + w}" y2="{y + 20 + cs:.1f}" stroke="{t["rule"]}" stroke-width="1"/>'
          f'<line x1="{x + cs:.1f}" y1="{y + 20}" x2="{x + cs:.1f}" y2="{y + 20 + n * cs:.1f}" stroke="{t["rule"]}" stroke-width="1"/>')


def motif_expiry(d, fonts, lang, t, x, y, w, h):
    """Stock sorted by days to expiry; the item that leaves first is in brass."""
    days = [2, 5, 9, 16, 30]
    bar_h, gap = 22, 18
    top = y + 34
    for i, n in enumerate(days):
        by = top + i * (bar_h + gap)
        bw = (w - 40) * n / max(days)
        d.raw(f'<rect x="{x + 40}" y="{by}" width="{bw:.1f}" height="{bar_h}" rx="2" '
              f'fill="{t["brass"] if i == 0 else t["faint"]}" stroke="{t["brass"] if i == 0 else t["rule"]}" stroke-width="1.5"/>')
        d.text("mono", x + 30, by + 16, f"{n}", 16, t["brass"] if i == 0 else t["steel"], anchor="end")
    d.text("italic", x + 40, top + len(days) * (bar_h + gap) + 8, COPY[lang]["days"], 17, t["muted"])


def motif_gates(d, fonts, lang, t, x, y, w, h):
    """Agent output only ships after passing three gates."""
    labels = COPY[lang]["gates"]
    gx = x + w / 2
    for i, lab in enumerate(labels):
        gy = y + 40 + i * 62
        d.raw(f'<rect x="{x + 20}" y="{gy}" width="{w - 40}" height="40" rx="4" fill="none" stroke="{t["rule"]}" stroke-width="1.5"/>')
        d.text("mono", gx - 8, gy + 26, lab, 17, t["ink"], anchor="middle")
        d.raw(f'<path d="M{x + w - 44} {gy + 20} l6 7 l12 -14" fill="none" stroke="{t["brass"]}" stroke-width="2.2"/>')
        if i < len(labels) - 1:
            d.raw(f'<line x1="{gx}" y1="{gy + 40}" x2="{gx}" y2="{gy + 62}" stroke="{t["steel"]}" stroke-width="1.5"/>')
    end = y + 40 + len(labels) * 62 - 22
    d.raw(f'<line x1="{gx}" y1="{end}" x2="{gx}" y2="{end + 22}" stroke="{t["brass"]}" stroke-width="1.5"/>'
          f'<circle cx="{gx}" cy="{end + 28}" r="6" fill="{t["brass"]}"/>')


def motif_lab(d, fonts, lang, t, x, y, w, h):
    """Attacker and workstation on the admin side; the target sits alone, in brass."""
    a, ws, tg = COPY[lang]["nodes"]
    pts = {"a": (x + 30, y + 60), "w": (x + w - 30, y + 60), "t": (x + w / 2, y + 190)}
    d.raw(f'<line x1="{pts["a"][0]}" y1="{pts["a"][1]}" x2="{pts["w"][0]}" y2="{pts["w"][1]}" stroke="{t["steel"]}" stroke-width="1.5"/>')
    d.raw(f'<line x1="{pts["a"][0]}" y1="{pts["a"][1]}" x2="{pts["t"][0]}" y2="{pts["t"][1]}" stroke="{t["brass"]}" stroke-width="1.5" stroke-dasharray="5 5"/>')
    for k, lab in (("a", a), ("w", ws)):
        px, py = pts[k]
        d.raw(f'<rect x="{px - 16}" y="{py - 12}" width="32" height="24" rx="3" fill="{t["faint"]}" stroke="{t["ink"]}" stroke-width="1.5"/>')
        d.text("italic", px, py - 22, lab, 17, t["muted"], anchor="middle")
    px, py = pts["t"]
    d.raw(f'<rect x="{px - 16}" y="{py - 12}" width="32" height="24" rx="3" fill="{t["brass"]}" stroke="{t["brass"]}" stroke-width="1.5"/>')
    d.text("italic", px, py + 38, tg, 17, t["muted"], anchor="middle")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", default="/usr/share/texmf/fonts/opentype/public/lm")
    args = ap.parse_args()
    fonts = Fonts(args.fonts)
    for lang in COPY:
        out = os.path.join(ROOT, "assets", lang)
        os.makedirs(out, exist_ok=True)
        for theme, t in THEMES.items():
            files = {"header": header(fonts, lang, t), "facts": facts(fonts, lang, t)}
            for key in COPY[lang]["cards"]:
                files[f"card-{key}"] = card(fonts, lang, t, key)
            for name, svg in files.items():
                with open(os.path.join(out, f"{name}-{theme}.svg"), "w", encoding="utf-8") as fh:
                    fh.write(svg)
    print("ok")


if __name__ == "__main__":
    main()
