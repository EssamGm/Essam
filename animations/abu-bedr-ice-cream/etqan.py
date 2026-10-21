"""Etqan (إتقان) brand layer for the animation, built only from the Etqan brand guidelines v1.0.

Colours, fonts, the logo and the motion rules all live here, so every scene uses
the same identity. Fonts are the Cairo and IBM Plex Sans Arabic files embedded
in the guideline (brand/fonts/); Arabic is shaped with HarfBuzz.
"""
import os
import re

import skia
import uharfbuzz as hb
from fontTools.merge import Merger
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, 'brand', 'fonts')
CACHE_DIR = os.path.join(HERE, 'brand', '.cache')

# ------------------------------------------------------------------ colours (guideline §05–07)
NAVY = '#14365C'        # primary: mark, headings, buttons
GOLD = '#C9A227'        # the square, badges, borders (one gold only)
INK = '#1A1A2E'
GRAY = '#5A5A6E'
LINE = '#E6E7EC'
BG_SOFT = '#F6F7F9'
WHITE = '#FFFFFF'
# dark mode
SURFACE = '#0B1A2A'
ELEVATED = '#122943'
BORDER = '#24374C'
NAVY_SOFT = '#1F4E79'
NAVY_LIGHT = '#3E6C99'
TEXT = '#F2F5F8'
TEXT_2 = '#9AA6B5'
# supporting (states only, not identity)
ALERT = '#B83227'
POSITIVE = '#1D7A6B'
TINTS = ('#F4F8FC', '#FBF4E2', '#E6F4F1', '#FDECEA')
SITE = 'WWW.ETQAN.SA'

# ------------------------------------------------------------------ fonts

def _woff2_to_tt(path):
    f = TTFont(path)
    f.flavor = None
    return f


def _build_font(name, weight):
    """Merge the guideline's Arabic + Latin subsets of one weight into one TTF; cached."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    out = os.path.join(CACHE_DIR, f'{name}-{weight}.ttf')
    if os.path.exists(out):
        return out
    parts = []
    for script in ('arabic', 'latin'):
        if name == 'Cairo':
            f = _woff2_to_tt(os.path.join(FONT_DIR, f'Cairo-{script}-variable.woff2'))
            f = instantiateVariableFont(f, {'wght': weight})
        else:
            f = _woff2_to_tt(os.path.join(FONT_DIR, f'IBMPlexSansArabic-{weight}-{script}.woff2'))
        p = os.path.join(CACHE_DIR, f'_{name}-{weight}-{script}.ttf')
        f.save(p)
        parts.append(p)
    Merger().merge(parts).save(out)
    return out


class Face:
    def __init__(self, name, weight):
        path = _build_font(name, weight)
        data = open(path, 'rb').read()
        self.tf = skia.Typeface.MakeFromData(skia.Data.MakeWithCopy(data))
        self.hb_face = hb.Face(data)
        self.hb_font = hb.Font(self.hb_face)
        self.upem = self.hb_face.upem
        self._fonts = {}

    def skfont(self, size):
        if size not in self._fonts:
            f = skia.Font(self.tf, size)
            f.setSubpixel(True)
            f.setEdging(skia.Font.Edging.kAntiAlias)
            self._fonts[size] = f
        return self._fonts[size]


_faces = {}


def face(kind):
    """kind: 'logo' (Cairo 900), 'h' (Cairo 800), 'btn' (Cairo 700), 'body' (Plex 400),
    'med' (Plex 500), 'semi' (Plex 600)."""
    spec = {'logo': ('Cairo', 900), 'h': ('Cairo', 800), 'btn': ('Cairo', 700),
            'body': ('IBMPlexSansArabic', 400), 'med': ('IBMPlexSansArabic', 500),
            'semi': ('IBMPlexSansArabic', 600)}[kind]
    if spec not in _faces:
        _faces[spec] = Face(*spec)
    return _faces[spec]


def is_arabic(s):
    return bool(re.search(r'[؀-ۿ]', s))


_shape_cache = {}


def shape(fc, text, size):
    """Shape text; returns (glyph ids, x positions, total advance, clusters) in visual order."""
    if not text:
        return [], [], 0.0, [], []
    key = (id(fc), text, size)
    if key not in _shape_cache:
        _shape_cache[key] = _shape(fc, text, size)
    return _shape_cache[key]


def _shape(fc, text, size):
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(fc.hb_font, buf, {'kern': True, 'liga': True})
    k = size / fc.upem
    gids, xs, cl = [], [], []
    x = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        gids.append(info.codepoint)
        xs.append(x + pos.x_offset * k)
        cl.append(info.cluster)
        x += pos.x_advance * k
    return gids, xs, x, cl, [p.y_offset * k for p in buf.glyph_positions]


def text_width(kind, text, size):
    return shape(face(kind), text, size)[2]


def draw_text(cv, text, x, y, size, color=TEXT, kind='med', align='c', alpha=1.0, highlight=None,
              hl_color=GOLD, hl_kind=None):
    """Draw shaped text with baseline at y. align: 'c', 'l', 'r'.
    highlight: substring drawn in hl_color (and hl_kind font, if given) — e.g. the target word."""
    from render_lib import P  # local import keeps this module free of scene code
    fc = face(kind)
    gids, xs, w, cl, ys = shape(fc, text, size)
    x0 = x - w / 2 if align == 'c' else (x - w if align == 'r' else x)
    hl = set()
    for h in ([highlight] if isinstance(highlight, str) else (highlight or [])):
        pat = r'\b%s\b' % re.escape(h) if re.match(r'[A-Za-z]', h) else re.escape(h)
        for m in re.finditer(pat, text):
            hl.update(range(m.start(), m.end()))
    groups = {}
    for g, gx, c, gy in zip(gids, xs, cl, ys):
        groups.setdefault(c in hl, []).append((g, gx, gy))
    for is_hl, items in groups.items():
        b = skia.TextBlobBuilder()
        b.allocRunPos(fc.skfont(size), [g for g, _, _ in items], [skia.Point(x0 + gx, -gy) for _, gx, gy in items])
        blob = b.make()
        cv.drawTextBlob(blob, 0, y, P(hl_color if is_hl else color, alpha))
    return w


# ------------------------------------------------------------------ logo (guideline §01–03)

def _svg_path(d):
    """Minimal SVG path parser for the wordmark (M L H V Q C Z, absolute)."""
    p = skia.Path()
    toks = re.findall(r'[MLHVQCZmlhvqcz]|-?\d*\.?\d+(?:e-?\d+)?', d)
    i, cmd, cx, cy = 0, None, 0.0, 0.0
    def num():
        nonlocal i
        v = float(toks[i]); i += 1
        return v
    while i < len(toks):
        if re.match(r'[A-Za-z]', toks[i]):
            cmd = toks[i]; i += 1
            if cmd in 'Zz':
                p.close()
                continue
        if cmd == 'M':
            cx, cy = num(), num(); p.moveTo(cx, cy); cmd = 'L'
        elif cmd == 'L':
            cx, cy = num(), num(); p.lineTo(cx, cy)
        elif cmd == 'H':
            cx = num(); p.lineTo(cx, cy)
        elif cmd == 'V':
            cy = num(); p.lineTo(cx, cy)
        elif cmd == 'Q':
            x1, y1, cx, cy = num(), num(), num(), num(); p.quadTo(x1, y1, cx, cy)
        elif cmd == 'C':
            x1, y1, x2, y2, cx, cy = num(), num(), num(), num(), num(), num(); p.cubicTo(x1, y1, x2, y2, cx, cy)
        else:
            raise ValueError('unsupported path command ' + cmd)
    return p


_WORDMARK = None
LOGO_W, LOGO_H = 86.36, 31.80
SQUARE = (0.0, 12.84, 7.0)  # x, y, size inside the logo box


def wordmark_path():
    global _WORDMARK
    if _WORDMARK is None:
        svg = open(os.path.join(HERE, 'brand', 'etqan-logo.svg')).read()
        path = skia.Path()
        for d in re.findall(r'<path d="([^"]+)"', svg):
            path.addPath(_svg_path(d))
        _WORDMARK = path
    return _WORDMARK


def draw_logo(cv, x, y, width, dark=True, word_alpha=1.0, square_alpha=1.0, word_dx=0.0):
    """Full logo with its top-left at (x, y), `width` px wide. dark=True: reversed version."""
    from render_lib import P
    s = width / LOGO_W
    cv.save()
    cv.translate(x, y)
    cv.scale(s, s)
    if word_alpha > 0:
        cv.save()
        cv.translate(word_dx / s, 0)
        cv.drawPath(wordmark_path(), P(TEXT if dark else NAVY, word_alpha))
        cv.restore()
    if square_alpha > 0:
        sx, sy, sz = SQUARE
        cv.drawRect(skia.Rect.MakeXYWH(sx, sy, sz, sz), P(GOLD, square_alpha))
    cv.restore()
    return width, LOGO_H * s
