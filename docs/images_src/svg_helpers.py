"""Primitives SVG partagees pour regenerer les diagrammes de conception_uml_v4,
dans le meme style que les diagrammes originaux de v3 (fond blanc, ellipses/boites
bleu tres clair #F2F4F9, titres navy #111111, accents bleu #1565C0, texte gris
#555555 pour les sous-titres/notes)."""
import html

NAVY = "#111111"
BLUE = "#1565C0"
GREY = "#555555"
FILL = "#F2F4F9"
FILL2 = "#E3E8F5"
BORDER = "#333333"
WHITE = "#FFFFFF"

FONT = "Helvetica, Arial, sans-serif"


def esc(s):
    return html.escape(str(s))


class SVG:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">',
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="{WHITE}"/>',
        ]

    def raw(self, s):
        self.parts.append(s)

    def title(self, text, x=None, cx=None, y=40, size=30, color=NAVY, anchor="middle"):
        cx = cx if cx is not None else (x if x is not None else self.width / 2)
        self.parts.append(
            f'<text x="{cx}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="bold" fill="{color}" text-anchor="{anchor}">{esc(text)}</text>'
        )

    def text(self, x, y, text, size=17, color=NAVY, anchor="middle", weight="normal",
              style="normal", family=None):
        fam = family or FONT
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" '
            f'font-weight="{weight}" font-style="{style}" fill="{color}" '
            f'text-anchor="{anchor}">{esc(text)}</text>'
        )

    def multiline(self, x, y, lines, size=17, color=NAVY, anchor="middle",
                   weight="normal", lh=None, family=None, style="normal"):
        lh = lh or (size + 6)
        for i, line in enumerate(lines):
            self.text(x, y + i * lh, line, size=size, color=color, anchor=anchor,
                       weight=weight, family=family, style=style)

    def rect(self, x, y, w, h, fill=FILL, stroke=BORDER, rx=8, sw=1.5, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}/>'
        )

    def ellipse(self, cx, cy, rx, ry, fill=FILL, stroke=NAVY, sw=1.8):
        self.parts.append(
            f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def diamond(self, cx, cy, w, h, fill=FILL2, stroke=NAVY, sw=1.8):
        pts = f"{cx},{cy-h/2} {cx+w/2},{cy} {cx},{cy+h/2} {cx-w/2},{cy}"
        self.parts.append(
            f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def line(self, x1, y1, x2, y2, stroke=NAVY, sw=1.6, dash=None, marker=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        m = f' marker-end="url(#{marker})"' if marker else ""
        self.parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
            f'stroke-width="{sw}"{d}{m}/>'
        )

    def path(self, d, stroke=NAVY, sw=1.6, fill="none", dash=None, marker=None):
        dd = f' stroke-dasharray="{dash}"' if dash else ""
        m = f' marker-end="url(#{marker})"' if marker else ""
        self.parts.append(f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" fill="{fill}"{dd}{m}/>')

    def defs_arrow(self):
        self.parts.append(
            '<defs>'
            '<marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" '
            'orient="auto" markerUnits="strokeWidth">'
            f'<path d="M0,0 L0,6 L9,3 z" fill="{NAVY}"/></marker>'
            '<marker id="arrowblue" markerWidth="10" markerHeight="10" refX="8" refY="3" '
            'orient="auto" markerUnits="strokeWidth">'
            f'<path d="M0,0 L0,6 L9,3 z" fill="{BLUE}"/></marker>'
            '<marker id="arrowopen" markerWidth="12" markerHeight="12" refX="9" refY="4" '
            'orient="auto" markerUnits="strokeWidth">'
            f'<path d="M1,1 L9,4 L1,7" fill="none" stroke="{NAVY}" stroke-width="1.4"/></marker>'
            '</defs>'
        )

    def actor(self, cx, top_y, label, sub=None, scale=1.0, color=NAVY):
        r = 18 * scale
        head_cy = top_y + r
        self.parts.append(f'<circle cx="{cx}" cy="{head_cy}" r="{r}" fill="{WHITE}" stroke="{color}" stroke-width="2.2"/>')
        body_top = head_cy + r
        body_bot = body_top + 55 * scale
        self.line(cx, body_top, cx, body_bot, stroke=color, sw=2.2)
        arm_y = body_top + 16 * scale
        self.line(cx - 26 * scale, arm_y, cx + 26 * scale, arm_y, stroke=color, sw=2.2)
        self.line(cx, body_bot, cx - 22 * scale, body_bot + 32 * scale, stroke=color, sw=2.2)
        self.line(cx, body_bot, cx + 22 * scale, body_bot + 32 * scale, stroke=color, sw=2.2)
        self.text(cx, body_bot + 32 * scale + 24, label, size=17, weight="bold", color=color)
        if sub:
            self.text(cx, body_bot + 32 * scale + 44, sub, size=13, color=GREY)

    def note(self, x, y, text_lines, size=13, color=GREY, anchor="middle", lh=None):
        self.multiline(x, y, text_lines, size=size, color=color, anchor=anchor, style="italic", lh=lh)

    def save(self, path):
        self.parts.append("</svg>")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.parts))


def render(path_svg, path_png, scale=2.0):
    import cairosvg
    cairosvg.svg2png(url=path_svg, write_to=path_png, scale=scale)


class SeqDiagram:
    """Diagramme de sequence generique (memes conventions visuelles que
    conception_uml_v3 : lifelines a bandeau noir, traits pleins = appels,
    traits pointilles bleus = retours, messages numerotes)."""

    def __init__(self, actors, width=None, height=1300, lane_w=300, left_pad=170, top_y=150, header_h=70):
        self.actors = actors
        self.n = len(actors)
        self.lane_w = lane_w
        self.left_pad = left_pad
        self.top_y = top_y
        self.header_h = header_h
        self.width = width or (left_pad * 2 + lane_w * (self.n - 1))
        self.height = height
        self.s = SVG(self.width, self.height)
        self.y = top_y + header_h + 60

    def x(self, i):
        return self.left_pad + i * self.lane_w

    def title(self, text, subtitle=None):
        self.s.title(text, y=42, size=27)
        if subtitle:
            self.s.text(self.width / 2, 74, subtitle, size=16, color=GREY, style="italic")

    def draw_headers(self):
        s = self.s
        s.defs_arrow()
        for i, name in enumerate(self.actors):
            cx = self.x(i)
            s.rect(cx - 130, self.top_y, 260, self.header_h, fill=NAVY, stroke=NAVY, rx=3, sw=1)
            s.text(cx, self.top_y + self.header_h / 2 + 6, name, size=16.5, weight="bold", color=WHITE)
            s.line(cx, self.top_y + self.header_h, cx, self.height - 60, stroke="#AAAAAA", sw=1.3, dash="4,4")

    def call(self, i_from, i_to, label, num=None, gap=52, color=NAVY, self_call=False):
        s = self.s
        x1, x2 = self.x(i_from), self.x(i_to)
        y = self.y
        text = f"{num}. {label}" if num is not None else label
        if self_call:
            s.text(x1 + 14, y - 6, text, size=14, anchor="start", color=color)
            s.path(f"M {x1} {y} L {x1+70} {y} L {x1+70} {y+22} L {x1} {y+22}", stroke=color, sw=1.6)
            s.raw(f'<path d="M {x1+12} {y+22} L {x1} {y+22} L {x1+7} {y+16}" stroke="{color}" stroke-width="1.6" fill="none"/>')
        else:
            mid = (x1 + x2) / 2
            s.text(mid, y - 6, text, size=14.5, anchor="middle", color=color)
            s.line(x1, y, x2, y, stroke=color, sw=1.8, marker="arrow")
        self.y += gap

    def ret(self, i_from, i_to, label, num=None, gap=60, color=BLUE):
        s = self.s
        x1, x2 = self.x(i_from), self.x(i_to)
        y = self.y
        mid = (x1 + x2) / 2
        text = f"{num}. {label}" if num is not None else label
        s.text(mid, y - 6, text, size=14.5, anchor="middle", color=color)
        s.line(x1, y, x2, y, stroke=color, sw=1.8, dash="7,4", marker="arrowblue")
        self.y += gap

    def note_band(self, label, color="#F5F0E0", gap=54):
        s = self.s
        y = self.y
        s.rect(self.left_pad - 140, y - 26, self.width - 2 * (self.left_pad - 140), 34, fill=color, stroke="#B08D2B", sw=1.2, rx=3)
        s.text(self.width / 2, y - 4, label, size=14, weight="bold", color="#6B4E00")
        self.y += gap

    def gap(self, amount):
        self.y += amount

    def footer_note(self, text):
        self.s.text(self.width / 2, self.height - 24, text, size=14, color="#333333")

    def finish(self, i):
        return self.s


def activity_pill(s, cx, top_y, w, text_lines, fill=FILL, stroke=NAVY, h=None, size=16.5):
    lh = 24
    h = h or (len(text_lines) * lh + 26)
    s.rect(cx - w/2, top_y, w, h, fill=fill, stroke=stroke, rx=h/2 if h < w else 22, sw=1.8)
    s.multiline(cx, top_y + h/2 - (len(text_lines)-1)*lh/2 + 6, text_lines, size=size, lh=lh)
    return h


def start_node(s, cx, cy, r=14, fill=NAVY):
    s.parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>')


def end_node(s, cx, cy, r=16, fill=NAVY):
    s.parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{fill}" stroke-width="2.2"/>')
    s.parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r-5}" fill="{fill}"/>')
