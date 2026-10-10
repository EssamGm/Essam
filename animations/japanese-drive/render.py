"""Faceless 2D animation: "Otsukaresama deshita" — a late drive home.

Renders 1080x1920 (9:16) frames with skia-python and pipes them to ffmpeg.

    python3 render.py out.mp4            # full render (video only)
    python3 render.py --still 21.5 a.png # single frame preview
"""
import math
import os
import random
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
import skia

W, H = 1080, 1920
FPS = 30
DUR = 48.5

# ---------------------------------------------------------------- helpers

def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def lerp(a, b, t):
    return a + (b - a) * t


def prog(t, a, b):
    return clamp((t - a) / (b - a))


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in(x):
    x = clamp(x)
    return x ** 3


def ease_back(x):
    x = clamp(x)
    c = 1.9
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def rgb(h):
    if isinstance(h, tuple):
        return h
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mixc(a, b, t):
    a, b = rgb(a), rgb(b)
    return tuple(int(lerp(a[i], b[i], clamp(t))) for i in range(3))


def shade(h, k):
    r, g, b = rgb(h)
    return (int(clamp(r * k, 0, 255)), int(clamp(g * k, 0, 255)), int(clamp(b * k, 0, 255)))


def col(h, a=1.0):
    r, g, b = rgb(h)
    return skia.ColorSetARGB(int(clamp(a) * 255), r, g, b)


def P(c='#000000', a=1.0, stroke=None, cap=True, blur=0, shader=None, blend=None):
    p = skia.Paint(AntiAlias=True)
    p.setColor(col(c, a))
    if stroke:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(stroke)
        p.setStrokeCap(skia.Paint.kRound_Cap if cap else skia.Paint.kButt_Cap)
        p.setStrokeJoin(skia.Paint.kRound_Join)
    if blur:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if shader is not None:
        p.setShader(shader)
    if blend is not None:
        p.setBlendMode(blend)
    return p


def lin(p0, p1, colors, pos=None):
    return skia.GradientShader.MakeLinear([skia.Point(*p0), skia.Point(*p1)],
                                          [col(*c) if isinstance(c, (list,)) else c for c in colors], pos)


def rad(c, r, colors, pos=None):
    return skia.GradientShader.MakeRadial(skia.Point(*c), max(r, 1), colors, pos)


def glow(cv, x, y, r, c, a, blend=skia.BlendMode.kPlus):
    cv.drawCircle(x, y, r, P(shader=rad((x, y), r, [col(c, a), col(c, a * 0.35), col(c, 0)], [0, 0.35, 1]),
                              blend=blend))


def rrect(cv, x, y, w, h, r, paint):
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), r, r), paint)


def poly(pts, close=True):
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    if close:
        p.close()
    return p


# ---------------------------------------------------------------- fonts

FONT_DIR = '/usr/share/fonts/opentype'
TF = {
    'reg': skia.Typeface.MakeFromFile(f'{FONT_DIR}/inter/Inter-Regular.otf'),
    'med': skia.Typeface.MakeFromFile(f'{FONT_DIR}/inter/Inter-Medium.otf'),
    'semi': skia.Typeface.MakeFromFile(f'{FONT_DIR}/inter/Inter-SemiBold.otf'),
    'bold': skia.Typeface.MakeFromFile(f'{FONT_DIR}/inter/Inter-Bold.otf'),
    'ital': skia.Typeface.MakeFromFile(f'{FONT_DIR}/inter/Inter-MediumItalic.otf'),
    'jp': skia.Typeface.MakeFromFile(f'{FONT_DIR}/noto/NotoSansCJK-Regular.ttc', 0),
    'jpb': skia.Typeface.MakeFromFile(f'{FONT_DIR}/noto/NotoSansCJK-Bold.ttc', 0),
}
_fonts = {}


def font(name, size):
    k = (name, round(size, 1))
    if k not in _fonts:
        f = skia.Font(TF[name], size)
        f.setSubpixel(True)
        f.setEdging(skia.Font.Edging.kAntiAlias)
        _fonts[k] = f
    return _fonts[k]


def text_w(s, name, size):
    return font(name, size).measureText(s)


def text(cv, s, x, y, size, c='#FFFFFF', a=1.0, name='semi', align='c', blur=0, blend=None):
    f = font(name, size)
    w = f.measureText(s)
    if align == 'c':
        x -= w / 2
    elif align == 'r':
        x -= w
    blob = skia.TextBlob.MakeFromString(s, f)
    if blob is not None:
        cv.drawTextBlob(blob, x, y, P(c, a, blur=blur, blend=blend))
    return w


def wrap(s, name, size, maxw):
    words, lines, cur = s.split(' '), [], ''
    for wd in words:
        t = (cur + ' ' + wd).strip()
        if text_w(t, name, size) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- palette

NIGHT_TOP = '#070A1E'
NIGHT_MID = '#151A42'
NIGHT_LOW = '#3A2A5E'
WARM = '#FFB86B'
GOLD = '#FFD98A'
SKIN = '#C98E6A'
HAIR = '#251C33'
SHIRT = '#E6EAF4'
JACKET = '#33407C'
PANTS = '#20243F'
SHOE = '#121428'
CAR = '#D5554A'

rng = random.Random(7)
STARS = [(rng.uniform(0, W), rng.uniform(0, 1150), rng.uniform(1.2, 3.2), rng.uniform(0, 6.28), rng.uniform(0.6, 2.0))
         for _ in range(150)]


def sky(cv, t, top=NIGHT_TOP, mid=NIGHT_MID, low=NIGHT_LOW, horizon=1400, stars=1.0, ox=0.0):
    cv.drawRect(skia.Rect.MakeWH(W, H), P(shader=lin((0, 0), (0, horizon),
                                                       [col(top), col(mid), col(low)], [0, 0.55, 1])))
    if stars > 0:
        for (x, y, r, ph, sp) in STARS:
            if y > horizon - 120:
                continue
            a = (0.45 + 0.55 * math.sin(t * sp + ph) ** 2) * stars
            xx = (x - ox) % W
            cv.drawCircle(xx, y, r * 0.55, P('#FFFFFF', a * 0.85))


def moon(cv, x, y, r=56, a=1.0):
    glow(cv, x, y, r * 4.2, '#9FB4FF', 0.22 * a)
    cv.drawCircle(x, y, r, P('#F4EBD3', a))
    cv.drawCircle(x - r * 0.3, y - r * 0.25, r * 0.16, P('#E2D6B8', a * 0.8))
    cv.drawCircle(x + r * 0.28, y + r * 0.3, r * 0.11, P('#E2D6B8', a * 0.8))
    cv.drawCircle(x + r * 0.35, y - r * 0.32, r * 0.07, P('#E2D6B8', a * 0.8))


# ---------------------------------------------------------------- character rig

DEFAULT_POSE = dict(lean=0.0, head=0.0, arm_f=(8.0, 14.0), arm_b=(-6.0, -2.0),
                    leg_f=(3.0, 1.0), leg_b=(-3.0, -1.0), bob=0.0)


def pose_mix(a, b, t):
    out = {}
    for k in DEFAULT_POSE:
        va, vb = a.get(k, DEFAULT_POSE[k]), b.get(k, DEFAULT_POSE[k])
        if isinstance(va, tuple):
            out[k] = tuple(lerp(va[i], vb[i], t) for i in range(len(va)))
        else:
            out[k] = lerp(va, vb, t)
    return out


def pose_track(t, keys):
    """keys: list of (time, pose). Smoothly interpolates."""
    if t <= keys[0][0]:
        return pose_mix(keys[0][1], keys[0][1], 0)
    for (t0, p0), (t1, p1) in zip(keys, keys[1:]):
        if t <= t1:
            return pose_mix(p0, p1, smooth((t - t0) / (t1 - t0)))
    return pose_mix(keys[-1][1], keys[-1][1], 0)


def _limb(cv, start, a1, l1, a2, l2, w, c):
    x0, y0 = start
    x1 = x0 + l1 * math.sin(math.radians(a1))
    y1 = y0 + l1 * math.cos(math.radians(a1))
    x2 = x1 + l2 * math.sin(math.radians(a2))
    y2 = y1 + l2 * math.cos(math.radians(a2))
    path = skia.Path()
    path.moveTo(x0, y0)
    path.lineTo(x1, y1)
    path.lineTo(x2, y2)
    cv.drawPath(path, P(c, stroke=w))
    return (x2, y2)


def person(cv, x, y, s, pose, facing=1, light=None, alpha=1.0, phone=None, silhouette=None):
    """Faceless person. (x, y) = hip position. Angles: 0 = straight down, + = forward.

    light: optional skia shader drawn on top of the figure only (rim / tint light).
    phone: optional glow strength for a phone held in the front hand.
    silhouette: draw all parts in a single flat colour.
    """
    pz = dict(DEFAULT_POSE)
    pz.update(pose)
    cv.saveLayerAlpha(None, int(clamp(alpha) * 255))
    cv.save()
    cv.translate(x, y + pz['bob'])
    cv.scale(s * facing, s)

    def cc(c, k=1.0):
        if silhouette:
            return silhouette
        return shade(c, k)

    # legs (world angles)
    for side, k in (('leg_b', 0.72), ('leg_f', 1.0)):
        a1, a2 = pz[side]
        hx = -6 if side == 'leg_b' else 8
        end = _limb(cv, (hx, 0), a1, 98, a2, 96, 38, cc(PANTS, k))
        rrect(cv, end[0] - 16, end[1] - 4, 50, 22, 11, P(cc(SHOE, k)))

    cv.save()
    cv.rotate(pz['lean'])
    sh = (2, -148)
    # back arm (relative to torso)
    a1, a2 = pz['arm_b']
    hb = _limb(cv, sh, a1, 86, a2, 80, 30, cc(JACKET, 0.7))
    cv.drawCircle(hb[0], hb[1], 15, P(cc(SKIN, 0.75)))
    # hips + torso
    cv.drawOval(skia.Rect.MakeXYWH(-50, -26, 100, 50), P(cc(PANTS)))
    rrect(cv, -47, -178, 94, 186, 44, P(cc(JACKET)))
    if not silhouette:
        cv.drawPath(poly([(4, -176), (34, -170), (16, -128)]), P(SHIRT))
        cv.drawPath(poly([(4, -176), (16, -128), (12, -176)]), P(shade(JACKET, 0.8)))
    # neck + head
    cv.save()
    cv.translate(8, -172)
    cv.rotate(pz['head'])
    rrect(cv, -10, -20, 22, 28, 8, P(cc(SKIN, 0.85)))
    hx, hy, r = 6, -66, 50
    cv.drawCircle(hx, hy, r, P(cc(SKIN)))
    if not silhouette:
        cv.save()
        clip = skia.Path()
        clip.addCircle(hx, hy, r + 6)
        cv.clipPath(clip, doAntiAlias=True)
        hair = skia.Path()
        hair.addCircle(hx - 16, hy - 17, r + 2)
        cv.drawPath(hair, P(HAIR))
        cv.restore()
        # ear + soft cheek shading (no facial features)
        cv.drawOval(skia.Rect.MakeXYWH(hx - 10, hy - 6, 17, 24), P(shade(SKIN, 0.9)))
        cv.drawCircle(hx + 22, hy + 14, 26, P(shade(SKIN, 1.08), 0.25, blur=8))
    cv.restore()
    # front arm
    a1, a2 = pz['arm_f']
    hf = _limb(cv, sh, a1, 86, a2, 80, 30, cc(JACKET, 0.95))
    if phone is not None:
        cv.save()
        cv.translate(hf[0] + 4, hf[1] - 6)
        cv.rotate(-(a2) + 180)
        rrect(cv, -12, -40, 24, 50, 6, P('#0E0F1C'))
        if phone > 0:
            rrect(cv, -9, -37, 18, 44, 4, P('#CFE3FF', phone))
        cv.restore()
    cv.drawCircle(hf[0], hf[1], 15, P(cc(SKIN)))
    cv.restore()  # torso rotation
    cv.restore()
    if light is not None:
        cv.drawRect(skia.Rect.MakeWH(W, H), P(shader=light, blend=skia.BlendMode.kSrcATop))
    cv.restore()


def walk_pose(phase, stride=1.0):
    s = math.sin(phase)
    leg_f = (28 * s * stride, 28 * s * stride - 38 * max(0.0, math.sin(phase + 1.3)) * stride)
    s2 = math.sin(phase + math.pi)
    leg_b = (28 * s2 * stride, 28 * s2 * stride - 38 * max(0.0, math.sin(phase + math.pi + 1.3)) * stride)
    return dict(lean=6, head=2, leg_f=leg_f, leg_b=leg_b,
                arm_f=(-26 * s * stride, -26 * s * stride + 30), arm_b=(26 * s * stride, 26 * s * stride + 30),
                bob=-8 * abs(math.cos(phase)))


# ---------------------------------------------------------------- car

def car(cv, x, y, s, wheel_ang, lights=1.0, body=CAR, brake=0.0, sweep=0.0):
    cv.save()
    cv.translate(x, y)
    cv.scale(s, s)
    cv.drawOval(skia.Rect.MakeXYWH(-300, -26, 600, 40), P('#000000', 0.45, blur=10))
    if lights > 0:
        beam = poly([(285, -112), (1100, -230), (1100, 60)])
        cv.drawPath(beam, P(shader=lin((285, 0), (1000, 0), [col('#FFF1C2', 0.32 * lights), col('#FFF1C2', 0)]),
                            blend=skia.BlendMode.kPlus))
    b = skia.Path()
    b.moveTo(-275, -38)
    b.lineTo(-282, -95)
    b.quadTo(-284, -128, -250, -135)
    b.lineTo(-185, -142)
    b.quadTo(-150, -150, -122, -200)
    b.quadTo(-100, -230, -60, -232)
    b.lineTo(40, -232)
    b.quadTo(82, -230, 112, -200)
    b.lineTo(160, -152)
    b.quadTo(250, -142, 278, -122)
    b.quadTo(298, -110, 295, -80)
    b.lineTo(291, -42)
    b.quadTo(288, -28, 270, -28)
    b.lineTo(-260, -28)
    b.quadTo(-275, -28, -275, -38)
    b.close()
    cv.drawPath(b, P(shader=lin((0, -232), (0, -28), [col(shade(body, 1.12)), col(body), col(shade(body, 0.62))],
                               [0, 0.45, 1])))
    # shoulder highlight
    hl = skia.Path()
    hl.moveTo(-250, -128)
    hl.lineTo(-185, -134)
    hl.moveTo(165, -144)
    hl.quadTo(240, -136, 268, -120)
    cv.drawPath(hl, P('#FFFFFF', 0.28, stroke=4))
    # windows
    w = skia.Path()
    w.moveTo(-138, -150)
    w.quadTo(-116, -196, -90, -212)
    w.quadTo(-78, -219, -58, -219)
    w.lineTo(36, -219)
    w.quadTo(62, -217, 86, -196)
    w.lineTo(132, -153)
    w.close()
    cv.drawPath(w, P(shader=lin((0, -219), (0, -150), [col('#2A3160'), col('#151935')])))
    # driver silhouette inside
    cv.save()
    cv.clipPath(w, doAntiAlias=True)
    cv.drawCircle(46, -178, 24, P('#2E2B44'))
    cv.drawCircle(40, -184, 24, P('#1A1526'))
    rrect(cv, 18, -160, 56, 60, 22, P('#232A50'))
    # reflection streak
    cv.drawPath(poly([(-60, -219), (-30, -219), (-90, -150), (-120, -150)]), P('#FFFFFF', 0.08))
    cv.drawPath(poly([(60, -219), (72, -219), (20, -150), (8, -150)]), P('#FFFFFF', 0.06))
    cv.restore()
    rrect(cv, -32, -220, 12, 70, 4, P(shade(body, 0.85)))
    # door line + handle
    d = skia.Path()
    d.moveTo(-26, -150)
    d.lineTo(-30, -44)
    d.moveTo(138, -150)
    d.quadTo(146, -96, 140, -44)
    cv.drawPath(d, P(shade(body, 0.55), stroke=3))
    rrect(cv, 70, -128, 34, 8, 4, P(shade(body, 0.55)))
    rrect(cv, -90, -128, 34, 8, 4, P(shade(body, 0.55)))
    # lights
    rrect(cv, 266, -122, 26, 16, 7, P('#FFF6D6'))
    if lights > 0:
        glow(cv, 282, -114, 70, '#FFE7A8', 0.5 * lights)
    rrect(cv, -287, -118, 12, 26, 5, P('#FF3B3B'))
    glow(cv, -284, -105, 50 + 30 * brake, '#FF3030', 0.35 + 0.5 * brake)
    # wheels
    for wx in (-168, 176):
        cv.drawCircle(wx, -40, 56, P('#0B0C18'))
        cv.drawCircle(wx, -40, 46, P('#16161C'))
        cv.drawCircle(wx, -40, 27, P('#8E95B0'))
        cv.save()
        cv.translate(wx, -40)
        cv.rotate(math.degrees(wheel_ang))
        for k in range(5):
            cv.rotate(72)
            cv.drawLine(0, 0, 0, -24, P('#4B5070', stroke=6))
        cv.restore()
        cv.drawCircle(wx, -40, 7, P('#C5CAE0'))
    if sweep > 0:
        cv.drawPath(b, P(shader=lin((-280, -232), (300, -28), [col('#FFD89A', 0), col('#FFD89A', 0.35 * sweep),
                                                                 col('#FFD89A', 0)]),
                         blend=skia.BlendMode.kPlus))
    cv.restore()


# ---------------------------------------------------------------- scene: office exterior (0 - 3)

BLD_RNG = random.Random(11)
SKYLINE = [(BLD_RNG.uniform(-40, W), BLD_RNG.uniform(160, 520), BLD_RNG.uniform(90, 200)) for _ in range(14)]
WIN_X, WIN_Y = 3, 7  # lit window column / row
TOWER_X, TOWER_Y, TOWER_W = 300, 560, 480


def tower_window(col_i, row_i):
    cw = TOWER_W / 6
    return TOWER_X + col_i * cw + 14, TOWER_Y + 70 + row_i * 92, cw - 28, 58


def office_ext(cv, t):
    wx, wy, ww, wh = tower_window(WIN_X, WIN_Y)
    cxw, cyw = wx + ww / 2, wy + wh / 2
    k = smooth(prog(t, 0.8, 3.0))
    z = lerp(1.0, 9.0, ease_in(prog(t, 0.9, 3.0)))
    z *= lerp(1.0, 1.04, prog(t, 0, 1))
    cx, cy = lerp(W / 2, cxw, k), lerp(H / 2, cyw, k)
    sky(cv, t, horizon=1500)
    cv.save()
    cv.translate(W / 2, H / 2)
    cv.scale(z, z)
    cv.translate(-cx, -cy)
    moon(cv, 840, 330)
    for (x, h, w) in SKYLINE:
        top = 1500 - h - 260
        cv.drawRect(skia.Rect.MakeXYWH(x, top, w, H), P('#161A3C'))
        for yy in range(int(top) + 30, 1700, 46):
            for xx in range(int(x) + 16, int(x + w) - 20, 34):
                if (xx * 7 + yy * 3) % 11 == 0:
                    cv.drawRect(skia.Rect.MakeXYWH(xx, yy, 14, 18), P('#FFC870', 0.35))
    # tower
    cv.drawRect(skia.Rect.MakeXYWH(TOWER_X, TOWER_Y, TOWER_W, H), P(shader=lin((TOWER_X, 0), (TOWER_X + TOWER_W, 0),
                                                                                    [col('#262B57'), col('#1C2048')])))
    cv.drawRect(skia.Rect.MakeXYWH(TOWER_X - 14, TOWER_Y - 24, TOWER_W + 28, 30), P('#2E3466'))
    cv.drawLine(TOWER_X + 360, TOWER_Y - 24, TOWER_X + 360, TOWER_Y - 150, P('#2E3466', stroke=8))
    blink = 1.0 if (t % 1.2) < 0.5 else 0.15
    glow(cv, TOWER_X + 360, TOWER_Y - 152, 40, '#FF4040', 0.6 * blink)
    cv.drawCircle(TOWER_X + 360, TOWER_Y - 152, 7, P('#FF5050', 0.4 + 0.6 * blink))
    for r_i in range(14):
        for c_i in range(6):
            x, y, w_, h_ = tower_window(c_i, r_i)
            if (c_i, r_i) == (WIN_X, WIN_Y):
                continue
            cv.drawRect(skia.Rect.MakeXYWH(x, y, w_, h_), P('#2F3566'))
            cv.drawRect(skia.Rect.MakeXYWH(x, y, w_, 6), P('#3A4178'))
    # the one lit window
    glow(cv, cxw, cyw, 150, '#FFB65C', 0.55)
    cv.drawRect(skia.Rect.MakeXYWH(wx, wy, ww, wh), P(shader=lin((0, wy), (0, wy + wh), [col('#FFE2A6'), col('#FFB45A')])))
    cv.save()
    cv.clipRect(skia.Rect.MakeXYWH(wx, wy, ww, wh))
    # tiny figure at a desk
    cv.drawCircle(wx + ww * 0.36, wy + wh * 0.42, 7.5, P('#3A2A3A'))
    rrect(cv, wx + ww * 0.36 - 8, wy + wh * 0.55, 16, 30, 6, P('#3A2A3A'))
    cv.drawRect(skia.Rect.MakeXYWH(wx + ww * 0.52, wy + wh * 0.72, ww * 0.5, 4), P('#5A3E3A'))
    cv.drawRect(skia.Rect.MakeXYWH(wx + ww * 0.62, wy + wh * 0.52, 3, 12), P('#B9D7FF'))
    cv.restore()
    # street level
    cv.drawRect(skia.Rect.MakeXYWH(0, 1700, W, 300), P('#0C0E22'))
    for lx in (120, 960):
        cv.drawLine(lx, 1700, lx, 1540, P('#1F2245', stroke=8))
        glow(cv, lx, 1540, 110, WARM, 0.45)
        cv.drawCircle(lx, 1540, 9, P('#FFE2B0'))
    cv.restore()


# ---------------------------------------------------------------- scene: office interior (2.4 - 7)

def clock(cv, x, y, r, t, hour=11, minute=47):
    cv.drawCircle(x, y, r + 10, P('#2A2F57'))
    cv.drawCircle(x, y, r, P('#C9CDE0'))
    for i in range(12):
        a = math.radians(i * 30)
        l = 14 if i % 3 == 0 else 7
        cv.drawLine(x + math.sin(a) * (r - 8), y - math.cos(a) * (r - 8),
                    x + math.sin(a) * (r - 8 - l), y - math.cos(a) * (r - 8 - l), P('#3A3F66', stroke=4))
    sec = (12 + int(t)) % 60
    ha = math.radians((hour + minute / 60) * 30)
    ma = math.radians(minute * 6 + sec * 0.1)
    sa = math.radians(sec * 6)
    cv.drawLine(x, y, x + math.sin(ha) * r * 0.5, y - math.cos(ha) * r * 0.5, P('#22264A', stroke=9))
    cv.drawLine(x, y, x + math.sin(ma) * r * 0.75, y - math.cos(ma) * r * 0.75, P('#22264A', stroke=6))
    cv.drawLine(x, y, x + math.sin(sa) * r * 0.82, y - math.cos(sa) * r * 0.82, P('#E0574A', stroke=3))
    cv.drawCircle(x, y, 6, P('#E0574A'))


def city_window(cv, x, y, w, h, t, ox=0.0):
    cv.save()
    cv.clipRect(skia.Rect.MakeXYWH(x, y, w, h))
    cv.drawRect(skia.Rect.MakeXYWH(x, y, w, h), P(shader=lin((0, y), (0, y + h), [col('#0A0E2A'), col('#2B2459')])))
    for (sx, sy, r, ph, sp) in STARS[:40]:
        cv.drawCircle(x + (sx * 0.45 - ox * 0.2) % w, y + sy * 0.25, r * 0.45, P('#FFFFFF', 0.6))
    rr = random.Random(3)
    bx = x - (ox % 900)
    while bx < x + w + 900:
        bw, bh = rr.uniform(50, 120), rr.uniform(h * 0.25, h * 0.7)
        cv.drawRect(skia.Rect.MakeXYWH(bx, y + h - bh, bw, bh), P('#141638'))
        for yy in range(int(y + h - bh + 14), int(y + h), 26):
            for xx in range(int(bx + 8), int(bx + bw - 10), 20):
                if rr.random() < 0.25:
                    cv.drawRect(skia.Rect.MakeXYWH(xx, yy, 8, 10), P('#FFC870', 0.55))
        bx += bw + rr.uniform(4, 30)
    cv.restore()


def office_int(cv, t):
    z = lerp(1.08, 1.0, ease_out(prog(t, 2.4, 4.0)))
    cv.save()
    cv.translate(W / 2, H / 2)
    cv.scale(z, z)
    cv.translate(-W / 2, -H / 2)
    cv.drawRect(skia.Rect.MakeWH(W, H), P(shader=lin((0, 0), (0, 1360), [col('#151A3D'), col('#1E2350')])))
    cv.drawRect(skia.Rect.MakeXYWH(0, 1360, W, 600), P('#0F1228'))
    cv.drawRect(skia.Rect.MakeXYWH(0, 1352, W, 10), P('#262B57'))
    # window
    city_window(cv, 70, 420, 470, 560, t)
    rrect(cv, 60, 410, 490, 580, 10, P('#2C3263', stroke=20, cap=False))
    cv.drawLine(305, 420, 305, 980, P('#2C3263', stroke=12))
    cv.drawLine(70, 700, 540, 700, P('#2C3263', stroke=12))
    clock(cv, 810, 560, 92, t)
    # desk
    cv.drawRect(skia.Rect.MakeXYWH(520, 1104, 540, 26), P('#4A3A5C'))
    cv.drawRect(skia.Rect.MakeXYWH(540, 1130, 22, 230), P('#33284A'))
    cv.drawRect(skia.Rect.MakeXYWH(1010, 1130, 22, 230), P('#33284A'))
    # papers + mug
    for i in range(5):
        cv.drawRect(skia.Rect.MakeXYWH(930 + i * 2, 1092 - i * 8, 110, 7), P(shade('#B9BDD4', 0.75 + i * 0.05)))
    rrect(cv, 560, 1046, 44, 58, 8, P('#C4553F'))
    cv.drawArc(skia.Rect.MakeXYWH(594, 1058, 26, 30), -90, 180, False, P('#C4553F', stroke=6))
    for i in range(2):
        sp = skia.Path()
        x0 = 574 + i * 16
        sp.moveTo(x0, 1036)
        for k in range(1, 8):
            yy = 1036 - k * 12
            sp.lineTo(x0 + 7 * math.sin(k * 0.9 + t * 3 + i), yy)
        cv.drawPath(sp, P('#FFFFFF', 0.14, stroke=4))
    # chair
    cv.drawLine(330, 1230, 330, 1320, P('#1A1D38', stroke=14))
    cv.drawLine(260, 1330, 400, 1330, P('#1A1D38', stroke=10))
    rrect(cv, 240, 1200, 220, 34, 16, P('#262A4D'))
    rrect(cv, 222, 900, 46, 330, 22, P('#262A4D'))
    # person
    keys = [
        (2.4, dict(lean=10, head=8, arm_f=(28, 88), arm_b=(34, 92), leg_f=(86, 2), leg_b=(82, -2))),
        (5.0, dict(lean=10, head=10, arm_f=(28, 88), arm_b=(34, 92), leg_f=(86, 2), leg_b=(82, -2))),
        (5.6, dict(lean=-6, head=-14, arm_f=(168, 176), arm_b=(160, 170), leg_f=(86, 2), leg_b=(82, -2))),
        (6.2, dict(lean=-6, head=-12, arm_f=(170, 178), arm_b=(162, 172), leg_f=(86, 2), leg_b=(82, -2))),
        (6.8, dict(lean=4, head=22, arm_f=(14, 20), arm_b=(8, 14), leg_f=(86, 2), leg_b=(82, -2))),
    ]
    pz = pose_track(t, keys)
    if t < 5.0:
        typ = 4 * math.sin(t * 22)
        pz['arm_f'] = (pz['arm_f'][0] + typ * 0.4, pz['arm_f'][1] + typ)
        pz['arm_b'] = (pz['arm_b'][0] - typ * 0.4, pz['arm_b'][1] - typ)
    screen_light = rad((800, 1000), 700, [col('#9CC8FF', 0.45), col('#9CC8FF', 0)])
    person(cv, 380, 1196, 1.38, pz, light=screen_light)
    # laptop (screen faces the person)
    cv.drawRect(skia.Rect.MakeXYWH(640, 1094, 240, 10), P('#9AA0BF'))
    cv.save()
    cv.translate(878, 1098)
    cv.rotate(-12)
    rrect(cv, -12, -190, 14, 196, 5, P('#B4B9D2'))
    cv.drawRect(skia.Rect.MakeXYWH(-14, -184, 4, 180), P('#DDEBFF'))
    cv.restore()
    cv.drawPath(poly([(866, 910), (866, 1100), (300, 1260), (240, 760)]),
                P(shader=lin((866, 0), (300, 0), [col('#A8CEFF', 0.18), col('#A8CEFF', 0)]), blend=skia.BlendMode.kPlus))
    glow(cv, 860, 1000, 380, '#8DB8FF', 0.18)
    cv.restore()


# ---------------------------------------------------------------- scene: driving exterior (6.5 - 11.6)

def skyline_layer(cv, ox, seed, base, hmin, hmax, color, lit_a, tile=2200):
    rr = random.Random(seed)
    blds = []
    x = 0
    while x < tile:
        w = rr.uniform(90, 200)
        h = rr.uniform(hmin, hmax)
        blds.append((x, w, h, [(rr.random(), rr.random()) for _ in range(10)]))
        x += w + rr.uniform(0, 26)
    off = ox % tile
    for rep in (-1, 0, 1):
        for (bx, bw, bh, lights) in blds:
            xx = bx - off + rep * tile
            if xx > W or xx + bw < 0:
                continue
            cv.drawRect(skia.Rect.MakeXYWH(xx, base - bh, bw, bh + 4), P(color))
            for (u, v) in lights:
                if v < 0.6:
                    cv.drawRect(skia.Rect.MakeXYWH(xx + 12 + u * (bw - 34), base - bh + 20 + v * (bh - 40), 10, 14),
                                P('#FFC870', lit_a))


def streetlight(cv, x, base, hgt=520, a=1.0, pool_y=None):
    top = base - hgt
    cv.drawLine(x, base, x, top + 20, P('#272B52', stroke=12))
    arm = skia.Path()
    arm.moveTo(x, top + 30)
    arm.quadTo(x, top, x + 60, top)
    arm.lineTo(x + 92, top)
    cv.drawPath(arm, P('#272B52', stroke=10))
    rrect(cv, x + 70, top - 6, 56, 18, 8, P('#2E3360'))
    cone = poly([(x + 76, top + 10), (x + 120, top + 10), (x + 320, base + 160), (x - 120, base + 160)])
    cv.drawPath(cone, P(shader=lin((0, top), (0, base + 160), [col('#FFC77A', 0.22 * a), col('#FFC77A', 0.03 * a)]),
                        blend=skia.BlendMode.kPlus))
    glow(cv, x + 98, top + 10, 120, '#FFC77A', 0.6 * a)
    cv.drawOval(skia.Rect.MakeXYWH(x + 76, top + 4, 44, 12), P('#FFF0CF', a))


def drive_ext(cv, t):
    v = 980.0
    ox = v * (t - 6.5)
    sky(cv, t, horizon=1380, ox=ox * 0.02)
    moon(cv, 800, 380, 58)
    cv.save()
    cv.translate(0, -300)
    skyline_layer(cv, ox * 0.08, 21, 1360, 220, 520, '#1D1F48', 0.35)
    skyline_layer(cv, ox * 0.3, 22, 1370, 120, 380, '#14163A', 0.5)
    cv.drawRect(skia.Rect.MakeXYWH(0, 1350, W, 40), P('#22264A'))
    cv.drawRect(skia.Rect.MakeXYWH(0, 1390, W, 340), P('#12142A'))
    cv.drawRect(skia.Rect.MakeXYWH(0, 1730, W, 700), P('#0B0D1E'))
    cv.drawRect(skia.Rect.MakeXYWH(0, 1726, W, 8), P('#2A2E58'))
    off = ox % 200
    for i in range(-1, 8):
        x = i * 200 - off
        rrect(cv, x, 1556, 100, 10, 5, P('#E9E3C8', 0.55))
    sp = 640
    car_x = 470
    near = 1e9
    for i in range(-1, 4):
        lx = i * sp - (ox * 0.95 % sp) + 120
        streetlight(cv, lx, 1372)
        cv.drawOval(skia.Rect.MakeXYWH(lx - 120, 1460, 460, 120), P('#FFC77A', 0.07, blur=20, blend=skia.BlendMode.kPlus))
        near = min(near, abs(lx + 98 - car_x))
    sweep = clamp(1 - near / 260)
    bob = 2 * math.sin(t * 13) + 1.2 * math.sin(t * 7.3)
    car(cv, car_x, 1640 + bob, 1.15, ox / 46, lights=1.0, sweep=sweep)
    # speed streaks
    for i in range(6):
        y = 1420 + i * 46
        x = (W - ((ox * 1.6 + i * 337) % (W + 400)))
        cv.drawLine(x, y, x + 160, y, P('#FFFFFF', 0.05, stroke=3))
    cv.restore()


# ---------------------------------------------------------------- scene: car interior (11 - 27.6)

PHRASE_KANA = 'おつかれさまでした'
PHRASE = 'お疲れ様でした'
ROMAJI = 'otsukaresama deshita'
KANA_POOL = 'のはがをにでもねよなあいうえおかきくけこさしすせそたちつてとなにぬねまみむめもやゆよらりるれろわん'
PHONE_POS = (905, 935)


def _make_particles():
    rr = random.Random(5)
    parts = []
    ts = 12.0
    while ts < 20.4:
        parts.append(dict(ch=rr.choice(KANA_POOL), t0=ts, ang=rr.uniform(160, 215), dist=rr.uniform(260, 720),
                          size=rr.uniform(46, 76), wob=rr.uniform(8, 22), ph=rr.uniform(0, 6.28),
                          rot=rr.uniform(-18, 18), life=rr.uniform(3.2, 4.2), special=None))
        ts += rr.uniform(0.22, 0.42)
    for i, ch in enumerate(PHRASE_KANA):
        parts.append(dict(ch=ch, t0=15.6 + i * 0.5, ang=rr.uniform(165, 205), dist=rr.uniform(220, 560),
                          size=rr.uniform(52, 70), wob=rr.uniform(8, 18), ph=rr.uniform(0, 6.28),
                          rot=rr.uniform(-14, 14), life=99, special=i))
    return parts


PARTICLES = _make_particles()
GATHER_T = 21.0


def slot_pos(i, n=9, size=100):
    return 540 + (i - (n - 1) / 2) * size * 1.02, 440


def particle_state(p, t):
    age = t - p['t0']
    if age < 0:
        return None
    k = 1 - math.exp(-age / 1.6)
    a = math.radians(p['ang'])
    x = PHONE_POS[0] + math.cos(a) * p['dist'] * k
    y = PHONE_POS[1] - 30 + math.sin(a) * p['dist'] * k * 0.5 - 220 * k + p['wob'] * math.sin(age * 2.2 + p['ph'])
    alpha = smooth(age / 0.4)
    scale = lerp(0.4, 1.0, ease_out(age / 0.6))
    if p['special'] is None:
        alpha *= 1 - smooth((age - (p['life'] - 0.8)) / 0.8)
        if t > GATHER_T:
            alpha *= 1 - smooth((t - GATHER_T) / 0.4)
    return x, y, alpha, scale


def kana_glyph(cv, ch, x, y, size, a, rot=0.0, color='#E8ECFF', blur=0.0, glow_a=0.0):
    if a <= 0.003:
        return
    cv.save()
    cv.translate(x, y)
    cv.rotate(rot)
    if glow_a > 0:
        text(cv, ch, 0, size * 0.35, size, GOLD, glow_a * a, name='jpb', blur=size * 0.18, blend=skia.BlendMode.kPlus)
    text(cv, ch, 0, size * 0.35, size, color, a, name='jpb', blur=blur)
    cv.restore()


def car_int(cv, t):
    v = 1150.0
    ox = v * (t - 11.0)
    aha = prog(t, GATHER_T, GATHER_T + 0.6)
    warm = smooth(prog(t, GATHER_T, GATHER_T + 1.2))
    cam = lerp(1.0, 1.06, smooth(prog(t, 11.0, 20.8)))
    cam = lerp(cam, 1.0, ease_out(prog(t, GATHER_T, GATHER_T + 0.8)))
    shake = (1 - prog(t, GATHER_T, GATHER_T + 0.5)) * (t > GATHER_T) * 6
    road = 1.5 * math.sin(t * 11) + 1.0 * math.sin(t * 5.7)
    cv.drawRect(skia.Rect.MakeWH(W, H), P('#0E1128'))
    cv.save()
    cv.translate(W / 2 + shake * math.sin(t * 70), H / 2 + road * 0.5)
    cv.scale(cam, cam)
    cv.translate(-W / 2, -H / 2 - 40)
    # cabin shell
    cv.drawRect(skia.Rect.MakeWH(W, H), P(shader=lin((0, 0), (0, H), [col('#0B0D22'), col('#171A3A'), col('#0C0E22')],
                                                       [0, 0.5, 1])))
    # side window with passing city
    win = skia.Path()
    win.moveTo(40, 1090)
    win.lineTo(40, 760)
    win.quadTo(46, 640, 190, 620)
    win.lineTo(690, 610)
    win.lineTo(790, 1090)
    win.close()
    cv.save()
    cv.clipPath(win, doAntiAlias=True)
    cv.drawRect(skia.Rect.MakeXYWH(0, 600, W, 520), P(shader=lin((0, 600), (0, 1100), [col('#0B0F2E'), col('#33275C')])))
    for (sx, sy, r, ph, sp) in STARS[:50]:
        cv.drawCircle((sx - ox * 0.01) % W, 620 + sy * 0.18, r * 0.5, P('#FFFFFF', 0.55))
    cv.save()
    cv.translate(0, -300)
    skyline_layer(cv, ox * 0.12, 31, 1400, 160, 420, '#1D1F48', 0.35)
    skyline_layer(cv, ox * 0.45, 32, 1400, 60, 260, '#121433', 0.55)
    cv.restore()
    sp = 760
    lamp_hits = []
    for i in range(-1, 4):
        lx = i * sp - (ox % sp) + 200
        cv.drawLine(lx, 1100, lx, 700, P('#0A0B1C', stroke=16))
        glow(cv, lx + 40, 690, 150, '#FFC77A', 0.7)
        cv.drawOval(skia.Rect.MakeXYWH(lx + 10, 682, 60, 16), P('#FFF0CF'))
        lamp_hits.append(lx)
    cv.restore()
    cv.drawPath(win, P('#05060F', stroke=26))
    # windshield + A pillar
    ws = poly([(800, 1090), (700, 610), (1080, 560), (1080, 1090)])
    cv.drawPath(ws, P(shader=lin((800, 600), (1080, 1000), [col('#121638'), col('#1A1C40')])))
    for i in range(3):
        sx = 1080 - ((ox * 0.7 + i * 400) % 1200)
        cv.drawLine(sx, 640 + i * 40, sx + 120, 610 + i * 40, P('#FFFFFF', 0.05, stroke=8))
    cv.drawPath(poly([(690, 600), (735, 600), (840, 1100), (790, 1100)]), P('#05060F'))
    # roof liner
    cv.drawRect(skia.Rect.MakeXYWH(0, 0, W, 612), P(shader=lin((0, 0), (0, 612), [col('#0B0D22'), col('#141738')])))
    # seat
    rrect(cv, 248, 860, 170, 600, 70, P('#1C1F40'))
    rrect(cv, 290, 760, 110, 120, 40, P('#1C1F40'))
    rrect(cv, 300, 880, 26, 520, 13, P('#24284D'))
    # dashboard
    dash = skia.Path()
    dash.moveTo(760, 1080)
    dash.quadTo(900, 1040, 1080, 1050)
    dash.lineTo(1080, 1500)
    dash.lineTo(840, 1500)
    dash.quadTo(800, 1300, 760, 1080)
    dash.close()
    cv.drawPath(dash, P(shader=lin((0, 1040), (0, 1500), [col('#232650'), col('#111328')])))
    rrect(cv, 900, 1110, 120, 40, 18, P('#0B0D1E'))
    glow(cv, 960, 1130, 90, '#4FD1E5', 0.35)
    cv.drawArc(skia.Rect.MakeXYWH(920, 1104, 40, 40), 180, 180, False, P('#6FE3F5', 0.8, stroke=3))
    cv.drawArc(skia.Rect.MakeXYWH(966, 1104, 40, 40), 180, 180, False, P('#6FE3F5', 0.8, stroke=3))
    # driver
    head_t = lerp(10, -10, ease_back(aha)) if t >= GATHER_T else 10 + 3 * math.sin(t * 1.3)
    lean = lerp(8, 2, ease_back(aha)) if t >= GATHER_T else 8
    pz = dict(lean=lean, head=head_t, arm_f=(48, 104), arm_b=(54, 108), leg_f=(80, 30), leg_b=(76, 26), bob=road)
    # light from passing lamps + phone + aha
    lamp_level = 0.0
    for lx in lamp_hits:
        d = abs(lx - 420)
        lamp_level = max(lamp_level, clamp(1 - d / 300))
    light = rad((880, 900), 760, [col(mixc('#86A8FF', '#FFC27A', warm), 0.30 + 0.25 * warm),
                                  col('#86A8FF', 0)])
    person(cv, 450, 1270, 1.55, pz, light=light)
    # lamp sweep light over interior
    if lamp_level > 0:
        cv.drawRect(skia.Rect.MakeWH(W, H), P(shader=lin((0, 600), (900, 1400), [col('#FFC77A', 0.0),
                                                                                  col('#FFC77A', 0.12 * lamp_level),
                                                                                  col('#FFC77A', 0)]),
                                                 blend=skia.BlendMode.kPlus))
    # steering wheel
    cv.save()
    cv.translate(738, 1060)
    cv.rotate(-16)
    cv.drawOval(skia.Rect.MakeXYWH(-36, -150, 72, 300), P('#090A18', stroke=26))
    cv.restore()
    cv.drawLine(738, 1060, 880, 1150, P('#090A18', stroke=34))
    # phone on mount
    cv.drawLine(PHONE_POS[0], PHONE_POS[1] + 90, PHONE_POS[0] + 10, 1060, P('#0A0B18', stroke=12))
    cv.save()
    cv.translate(*PHONE_POS)
    cv.rotate(-8)
    rrect(cv, -62, -105, 124, 210, 18, P('#06070F'))
    rrect(cv, -55, -97, 110, 194, 13, P(shader=lin((0, -97), (0, 97), [col('#2B2F6B'), col('#141634')])))
    text(cv, '日本語', 0, -60, 22, '#FFFFFF', 0.9, name='jpb')
    text(cv, 'Japanese Audio', 0, -36, 11, '#B7BEF0', 0.9, name='med')
    for i in range(9):
        hgt = 8 + 34 * abs(math.sin(t * 7 + i * 1.7)) * (0.6 + 0.4 * math.sin(t * 3 + i))
        if t > GATHER_T:
            hgt *= 1 - 0.6 * smooth(prog(t, GATHER_T, GATHER_T + 0.5))
        rrect(cv, -44 + i * 10.5, 10 - hgt / 2, 6, hgt, 3, P('#8FA6FF'))
    cv.drawLine(-40, 62, 40, 62, P('#FFFFFF', 0.25, stroke=4))
    cv.drawLine(-40, 62, -40 + 80 * ((t - 11) / 18 % 1), 62, P('#FFFFFF', 0.9, stroke=4))
    cv.restore()
    glow(cv, PHONE_POS[0], PHONE_POS[1], 220, '#7E95FF', 0.22)
    cv.restore()

    # --- kana particles (screen space)
    for p in PARTICLES:
        st = particle_state(p, t)
        if st is None:
            continue
        x, y, a, sc = st
        rot = p['rot'] + 6 * math.sin(t * 1.4 + p['ph'])
        size = p['size'] * sc
        blur = 1.6
        color = '#C9D2FF'
        a *= 0.7
        glow_a = 0.0
        if p['special'] is not None and t > GATHER_T - 0.6:
            u = ease_out(prog(t, GATHER_T + p['special'] * 0.05, GATHER_T + 0.75 + p['special'] * 0.05))
            sx, sy = slot_pos(p['special'])
            x, y = lerp(x, sx, u), lerp(y, sy, u)
            rot = lerp(rot, 0, u)
            size = lerp(size, 100, u)
            blur = lerp(1.6, 0, u)
            a = lerp(a, 1.0, u)
            color = mixc('#C9D2FF', '#FFF4D6', u)
            glow_a = 0.6 * u
            a *= 1 - smooth(prog(t, 22.6, 23.1))
        kana_glyph(cv, p['ch'], x, y, size, a, rot, color, blur, glow_a)

    # --- aha effects
    if t >= GATHER_T:
        hx, hy = 470, 870
        flash = math.exp(-(t - GATHER_T) * 4.5)
        cv.drawRect(skia.Rect.MakeWH(W, H), P('#FFF2D0', 0.32 * flash, blend=skia.BlendMode.kPlus))
        for k in range(2):
            u = prog(t, GATHER_T + k * 0.18, GATHER_T + 1.1 + k * 0.18)
            if 0 < u < 1:
                cv.drawCircle(hx, hy, lerp(60, 520, ease_out(u)), P(GOLD, 0.55 * (1 - u), stroke=lerp(10, 2, u)))
        u = prog(t, GATHER_T + 0.05, GATHER_T + 0.6)
        su = 1 - prog(t, GATHER_T + 1.4, GATHER_T + 2.0)
        if u > 0 and su > 0:
            for i in range(9):
                a = math.radians(-160 + i * 17.5)
                r0, r1 = 120 + 30 * ease_out(u), 170 + 80 * ease_out(u)
                cv.drawLine(hx + math.cos(a) * r0, hy + math.sin(a) * r0, hx + math.cos(a) * r1, hy + math.sin(a) * r1,
                            P(GOLD, 0.9 * su, stroke=8))
        warm_a = 0.16 * warm
        cv.drawRect(skia.Rect.MakeWH(W, H), P(shader=rad((540, 500), 1100, [col('#FFB86B', warm_a), col('#FFB86B', 0)]),
                                                 blend=skia.BlendMode.kPlus))
        # kanji phrase + romaji
        m = prog(t, 22.6, 23.2)
        if m > 0:
            sc = lerp(0.8, 1.0, ease_back(m))
            cv.save()
            cv.translate(540, 450)
            cv.scale(sc, sc)
            text(cv, PHRASE, 0, 40, 118, GOLD, 0.8 * m, name='jpb', blur=26, blend=skia.BlendMode.kPlus)
            text(cv, PHRASE, 0, 40, 118, '#FFF6E0', m, name='jpb')
            cv.restore()
        r = prog(t, 23.2, 23.8)
        if r > 0:
            text(cv, ROMAJI, 540, 570 + 20 * (1 - ease_out(r)), 46, '#FFE3B0', r, name='ital')


# ---------------------------------------------------------------- scene: home exterior (27 - 32.8)

def house_scene_bg(cv, t, door_open=0.0, win_light=0.0):
    sky(cv, t, horizon=1440)
    moon(cv, 230, 380, 52)
    # distant hills + tree
    hill = skia.Path()
    hill.moveTo(0, 1300)
    hill.quadTo(300, 1180, 620, 1290)
    hill.quadTo(860, 1220, 1080, 1270)
    hill.lineTo(1080, 1500)
    hill.lineTo(0, 1500)
    hill.close()
    cv.drawPath(hill, P('#141A3A'))
    cv.drawLine(150, 1440, 150, 1180, P('#18122A', stroke=22))
    for (dx, dy, r) in ((0, -90, 110), (-70, -30, 80), (70, -40, 85), (0, 10, 70)):
        cv.drawCircle(150 + dx, 1180 + dy, r, P('#18233F'))
    # house
    cv.drawRect(skia.Rect.MakeXYWH(520, 1040, 500, 400), P(shader=lin((520, 0), (1020, 0), [col('#3A3566'), col('#2C2852')])))
    cv.drawPath(poly([(490, 1060), (770, 800), (1050, 1060)]), P('#4A2F45'))
    cv.drawPath(poly([(490, 1060), (770, 800), (1050, 1060)]), P('#2A1C2E', stroke=10))
    cv.drawRect(skia.Rect.MakeXYWH(900, 840, 50, 120), P('#3A2638'))
    # window (lights up when he gets in)
    wl = win_light
    cv.drawRect(skia.Rect.MakeXYWH(590, 1110, 170, 130), P(mixc('#1A1C3A', '#FFC57A', wl)))
    if wl > 0:
        glow(cv, 675, 1175, 200, '#FFB65C', 0.45 * wl)
    cv.drawRect(skia.Rect.MakeXYWH(590, 1110, 170, 130), P('#22203F', stroke=10, cap=False))
    cv.drawLine(675, 1110, 675, 1240, P('#22203F', stroke=8))
    # door
    dx, dy, dw, dh = 820, 1196, 96, 244
    cv.drawRect(skia.Rect.MakeXYWH(dx - 10, dy - 10, dw + 20, dh + 10), P('#22203F'))
    if door_open > 0:
        cv.drawRect(skia.Rect.MakeXYWH(dx, dy, dw, dh), P('#FFD08A'))
        glow(cv, dx + dw / 2, dy + dh * 0.6, 260, '#FFB65C', 0.55 * door_open)
        cv.drawPath(poly([(dx, dy + dh), (dx + dw, dy + dh), (dx + dw + 160, dy + dh + 120), (dx - 160, dy + dh + 120)]),
                    P('#FFC27A', 0.25 * door_open, blend=skia.BlendMode.kPlus))
    cv.drawRect(skia.Rect.MakeXYWH(dx, dy, dw * (1 - 0.85 * door_open), dh), P('#7A3E3A'))
    cv.drawCircle(dx + dw * (1 - 0.85 * door_open) - 14, dy + 130, 5, P('#E8C27A'))
    # porch light
    glow(cv, dx + dw + 34, dy + 20, 90, '#FFC77A', 0.55)
    cv.drawCircle(dx + dw + 34, dy + 20, 8, P('#FFE9C0'))
    # ground
    cv.drawRect(skia.Rect.MakeXYWH(0, 1440, W, 500), P(shader=lin((0, 1440), (0, 1920), [col('#121A30'), col('#080B18')])))
    cv.drawPath(poly([(330, 1440), (1030, 1440), (1080, 1560), (180, 1560)]), P('#1A1E36'))
    cv.drawRect(skia.Rect.MakeXYWH(0, 1436, W, 6), P('#232A48'))


def home_ext(cv, t):
    z = lerp(1.0, 1.05, smooth(prog(t, 27.0, 32.8)))
    cv.save()
    cv.translate(W / 2, H / 2)
    cv.scale(z, z)
    cv.translate(-W / 2, -H / 2)
    door = smooth(prog(t, 30.75, 31.05)) * (1 - smooth(prog(t, 31.55, 31.85)))
    winl = smooth(prog(t, 31.85, 32.15))
    house_scene_bg(cv, t, door, winl)
    # car arrives
    u = ease_out(prog(t, 27.0, 29.0))
    cx = lerp(-420, 330, u)
    dist = cx + 420
    lights = 1.0 - smooth(prog(t, 29.3, 29.6))
    brake = clamp(1 - abs(t - 28.7) / 0.6)
    car(cv, cx, 1500, 0.62, dist / (46 * 0.62), lights=lights, brake=brake)
    # driver walks to the door
    if t > 29.55:
        a = smooth(prog(t, 29.55, 29.8)) * (1 - smooth(prog(t, 31.25, 31.5)))
        w = prog(t, 29.8, 30.95)
        px = lerp(410, 866, w)
        phase = (t - 29.8) * 13
        pz = walk_pose(phase, 1.15) if 0 < w < 1 else dict(lean=2)
        if t > 31.0:
            pz = pose_mix(walk_pose(phase, 1.15), dict(lean=4), smooth(prog(t, 30.95, 31.15)))
            pz['arm_f'] = (lerp(10, 80, smooth(prog(t, 30.7, 30.9))), 70)
        person(cv, px, 1352, 0.42, pz, alpha=a)
    cv.restore()


# ---------------------------------------------------------------- scene: living room (32.2 - 34.6, 40.6 - 45.6)

def living_bg(cv, t):
    cv.drawRect(skia.Rect.MakeWH(W, H), P(shader=lin((0, 0), (0, 1380), [col('#241B3A'), col('#33264A')])))
    cv.drawRect(skia.Rect.MakeXYWH(0, 1380, W, 600), P(shader=lin((0, 1380), (0, 1920), [col('#2A1E33'), col('#140E1E')])))
    cv.drawRect(skia.Rect.MakeXYWH(0, 1372, W, 12), P('#3A2C4E'))
    # window with moon
    cv.drawRect(skia.Rect.MakeXYWH(640, 470, 320, 400), P(shader=lin((0, 470), (0, 870), [col('#0B0F2E'), col('#2B2459')])))
    for (sx, sy, r, ph, sp) in STARS[:18]:
        cv.drawCircle(640 + sx * 0.29, 470 + sy * 0.3, r * 0.45, P('#FFFFFF', 0.6))
    moon(cv, 870, 560, 34)
    cv.drawRect(skia.Rect.MakeXYWH(640, 470, 320, 400), P('#4A3A5E', stroke=18, cap=False))
    cv.drawLine(800, 470, 800, 870, P('#4A3A5E', stroke=10))
    # picture frame + plant
    cv.drawRect(skia.Rect.MakeXYWH(200, 560, 200, 150), P('#3F3158'))
    cv.drawRect(skia.Rect.MakeXYWH(214, 574, 172, 122), P('#E7B47A', 0.55))
    cv.drawPath(poly([(214, 696), (280, 620), (330, 670), (360, 640), (386, 696)]), P('#7A4C5E', 0.9))
    rrect(cv, 960, 1250, 80, 120, 14, P('#6A3E3A'))
    for ang in (-40, -15, 10, 35):
        a = math.radians(ang)
        cv.drawLine(1000, 1260, 1000 + math.sin(a) * 150, 1260 - math.cos(a) * 170, P('#2E5A4A', stroke=22))
    # floor lamp
    cv.drawLine(110, 1380, 110, 860, P('#1A1426', stroke=10))
    cv.drawPath(poly([(40, 860), (180, 860), (150, 760), (70, 760)]), P('#F2C98A'))
    glow(cv, 110, 860, 620, '#FFB765', 0.42)
    # couch (side view, facing right)
    rrect(cv, 240, 1060, 110, 300, 40, P('#7B4A55'))
    rrect(cv, 240, 1210, 470, 120, 34, P('#8D5560'))
    rrect(cv, 640, 1150, 90, 180, 34, P('#7B4A55'))
    rrect(cv, 250, 1310, 470, 40, 14, P('#5A3640'))
    cv.drawLine(290, 1350, 290, 1376, P('#2A1A26', stroke=12))
    cv.drawLine(690, 1350, 690, 1376, P('#2A1A26', stroke=12))


def living(cv, t):
    z = lerp(1.0, 2.6, ease_in(prog(t, 33.4, 34.6)))
    cx, cy = lerp(W / 2, 640, smooth(prog(t, 33.2, 34.4))), lerp(H / 2, 930, smooth(prog(t, 33.2, 34.4)))
    cv.save()
    cv.translate(W / 2, H / 2)
    cv.scale(z, z)
    cv.translate(-cx, -cy)
    living_bg(cv, t)
    lift = smooth(prog(t, 32.4, 33.3))
    pz = dict(lean=lerp(-4, 6, lift), head=lerp(4, 14, lift), leg_f=(84, 4), leg_b=(80, 0),
              arm_f=(lerp(10, 20, lift), lerp(20, 150, lift)), arm_b=(lerp(4, 24, lift), lerp(10, 120, lift)))
    lamp = rad((110, 860), 900, [col('#FFB765', 0.35), col('#FFB765', 0)])
    person(cv, 440, 1206, 1.3, pz, light=lamp, phone=lift)
    glow(cv, 600, 1000, 160, '#BFD8FF', 0.35 * lift)
    cv.restore()


def celebrate(cv, t):
    z = lerp(1.06, 1.0, ease_out(prog(t, 40.6, 42.0)))
    cv.save()
    cv.translate(W / 2, H / 2)
    cv.scale(z, z)
    cv.translate(-W / 2, -H / 2)
    living_bg(cv, t)
    up = ease_back(prog(t, 41.0, 41.5))
    j1 = math.sin(math.pi * prog(t, 41.5, 41.95))
    j2 = math.sin(math.pi * prog(t, 42.15, 42.6))
    jump = -90 * (j1 + 0.7 * j2)
    pz = pose_mix(dict(lean=6, head=12, leg_f=(84, 4), leg_b=(80, 0), arm_f=(20, 150), arm_b=(24, 120)),
                  dict(lean=-4, head=-10, leg_f=(6, -4), leg_b=(-8, -14), arm_f=(150, 168), arm_b=(140, 160)), up)
    hip_y = lerp(1206, 1180, up) + jump
    hip_x = lerp(440, 560, up)
    if j1 > 0 or j2 > 0:
        pz['leg_f'] = (20, -10)
        pz['leg_b'] = (-6, -30)
    cv.drawOval(skia.Rect.MakeXYWH(hip_x - 90 - jump * 0.1, 1366, 180 + jump * 0.2, 22), P('#000000', 0.3, blur=6))
    lamp = rad((110, 860), 900, [col('#FFB765', 0.35), col('#FFB765', 0)])
    person(cv, hip_x, hip_y, 1.3, pz, light=lamp, phone=0.8)
    # sparkles
    rr = random.Random(9)
    for i in range(34):
        t0 = 41.2 + rr.uniform(0, 1.6)
        u = prog(t, t0, t0 + 1.4)
        if u <= 0 or u >= 1:
            continue
        a = rr.uniform(0, 6.28)
        d = rr.uniform(160, 520) * ease_out(u)
        x = hip_x + math.cos(a) * d
        y = hip_y - 380 + math.sin(a) * d * 0.8 + 120 * u * u
        s = rr.uniform(8, 18) * (1 - u)
        c = rr.choice([GOLD, '#FF9E7A', '#9FD8FF', '#FFFFFF'])
        star = skia.Path()
        for k in range(8):
            rr_ = s if k % 2 == 0 else s * 0.35
            ang = k * math.pi / 4 + t * 2
            pt = (x + math.cos(ang) * rr_, y + math.sin(ang) * rr_)
            star.moveTo(*pt) if k == 0 else star.lineTo(*pt)
        star.close()
        cv.drawPath(star, P(c, 1 - u * 0.5))
    cv.restore()
    # glowing phrase above
    m = prog(t, 41.3, 41.9)
    if m > 0:
        y = 330 + 10 * math.sin(t * 2)
        sc = lerp(0.85, 1.0, ease_back(m))
        cv.save()
        cv.translate(540, y)
        cv.scale(sc, sc)
        text(cv, PHRASE, 0, 0, 120, GOLD, 0.8 * m, name='jpb', blur=26, blend=skia.BlendMode.kPlus)
        text(cv, PHRASE, 0, 0, 120, '#FFF6E0', m, name='jpb')
        text(cv, '“Thank you for your hard work.”', 0, 90, 44, '#FFE3B0', m, name='ital')
        cv.restore()


# ---------------------------------------------------------------- scene: phone UI (34 - 41.2)

PX, PY, PWD, PHT = 220, 400, 640, 1290


def phone_ui(cv, t):
    # warm blurred room behind
    cv.drawRect(skia.Rect.MakeWH(W, H), P(shader=lin((0, 0), (0, H), [col('#2A1E3C'), col('#160F22')])))
    rr = random.Random(4)
    for i in range(14):
        x, y, r = rr.uniform(0, W), rr.uniform(0, H), rr.uniform(40, 140)
        glow(cv, x + 10 * math.sin(t * 0.5 + i), y, r, rr.choice(['#FFB765', '#FF8A6A', '#8FA6FF']), 0.12)
    z = lerp(1.0, 1.05, smooth(prog(t, 37.4, 41.2)))
    rise = 1 - ease_out(prog(t, 34.0, 34.7))
    cv.save()
    cv.translate(W / 2, H / 2 + rise * 140)
    cv.scale(z, z)
    cv.translate(-W / 2, -H / 2)
    # hand behind: palm below the phone, fingertips peeking past the right edge
    hand = shade(SKIN, 0.82)
    rrect(cv, PX + 40, PY + PHT - 120, PWD - 60, 420, 150, P(hand))
    for i in range(3):
        rrect(cv, PX + PWD - 60, PY + 690 + i * 110, 96, 92, 44, P(shade(SKIN, 0.78 - i * 0.03)))
    # phone body
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(PX - 8, PY + 20, PWD + 16, PHT), 86, 86),
                 P('#000000', 0.5, blur=30))
    rrect(cv, PX, PY, PWD, PHT, 82, P('#0C0D18'))
    sx, sy, sw, shh = PX + 20, PY + 20, PWD - 40, PHT - 40
    rrect(cv, sx, sy, sw, shh, 64, P('#F6F3EE'))
    cv.save()
    cv.clipRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(sx, sy, sw, shh), 64, 64), doAntiAlias=True)
    rrect(cv, 540 - 70, sy + 18, 140, 36, 18, P('#0C0D18'))
    text(cv, '12:31', sx + 70, sy + 50, 28, '#1B1D33', 1, name='semi', align='l')
    rrect(cv, sx + sw - 110, sy + 30, 46, 22, 6, P('#1B1D33', stroke=3))
    rrect(cv, sx + sw - 106, sy + 34, 26, 14, 3, P('#1B1D33'))
    text(cv, 'Dictionary', sx + 44, sy + 150, 52, '#1B1D33', 1, name='bold', align='l')
    text(cv, 'Japanese → English', sx + 46, sy + 196, 26, '#8A8798', 1, name='med', align='l')
    # search field
    fx, fy, fw, fh = sx + 36, sy + 230, sw - 72, 96
    tap = math.exp(-max(0, t - 36.6) * 8) if t > 36.6 else 0
    rrect(cv, fx, fy, fw, fh, 48, P(mixc('#ECE8F0', '#FFE2CC', tap)))
    cv.drawCircle(fx + 50, fy + 44, 15, P('#8A8798', stroke=4))
    cv.drawLine(fx + 61, fy + 55, fx + 72, fy + 66, P('#8A8798', stroke=5))
    n = int(clamp((t - 34.7) / 0.17, 0, 9))
    convert = t > 36.25
    s = PHRASE if convert else PHRASE_KANA[:n]
    tx = fx + 96
    if not s:
        text(cv, 'Search a word or phrase', tx, fy + 60, 30, '#A6A2B3', 1, name='reg', align='l')
    else:
        w = text(cv, s, tx, fy + 62, 40, '#1B1D33', 1, name='jp', align='l')
        if not convert:
            cv.drawLine(tx, fy + 74, tx + w, fy + 74, P('#E8724C', stroke=3))
        if (t * 2) % 1 < 0.55 and t < 36.6:
            cv.drawLine(tx + w + 6, fy + 26, tx + w + 6, fy + 72, P('#E8724C', stroke=3))
    # loading dots
    if 36.7 < t < 37.4:
        for i in range(3):
            a = 0.3 + 0.7 * abs(math.sin((t - 36.7) * 7 - i * 0.6))
            cv.drawCircle(540 + (i - 1) * 36, fy + 230, 11, P('#E8724C', a))
    # result card
    rc = ease_out(prog(t, 37.35, 37.9))
    if rc > 0:
        cy = fy + 150 + (1 - rc) * 300
        cx, cw, chh = fx, fw, 640
        cv.saveLayerAlpha(None, int(255 * rc))
        rrect(cv, cx, cy + 10, cw, chh, 40, P('#000000', 0.08, blur=16))
        rrect(cv, cx, cy, cw, chh, 40, P('#FFFFFF'))
        text(cv, PHRASE, cx + 40, cy + 110, 72, '#1B1D33', 1, name='jpb', align='l')
        text(cv, ROMAJI, cx + 42, cy + 166, 32, '#8A8798', 1, name='ital', align='l')
        cv.drawLine(cx + 40, cy + 206, cx + cw - 40, cy + 206, P('#ECE8F0', stroke=3))
        text(cv, 'MEANING', cx + 42, cy + 258, 24, '#E8724C', 1, name='bold', align='l')
        yy = cy + 312
        for line in wrap('“Thank you for your hard work.”', 'bold', 40, cw - 80):
            text(cv, line, cx + 40, yy, 40, '#1B1D33', 1, name='bold', align='l')
            yy += 52
        yy += 14
        for line in wrap('A warm, polite phrase said to someone at the end of a long day of work.', 'reg', 30,
                         cw - 80):
            text(cv, line, cx + 40, yy, 30, '#5E5A6E', 1, name='reg', align='l')
            yy += 42
        cv.restore()
        # badge
        b = prog(t, 38.9, 39.35)
        if b > 0:
            bs = ease_back(b)
            bx, by = 540, cy + chh + 90
            cv.save()
            cv.translate(bx, by)
            cv.scale(bs, bs)
            label = 'Kind  ·  Positive  ·  Polite'
            lw = text_w(label, 'bold', 30) + 110
            glow(cv, 0, 0, lw * 0.7, '#2BA36B', 0.25 * b, blend=skia.BlendMode.kSrcOver)
            rrect(cv, -lw / 2, -42, lw, 84, 42, P('#2BA36B'))
            cv.drawCircle(-lw / 2 + 44, 0, 22, P('#FFFFFF'))
            chk = skia.Path()
            chk.moveTo(-lw / 2 + 33, 0)
            chk.lineTo(-lw / 2 + 41, 9)
            chk.lineTo(-lw / 2 + 56, -8)
            cv.drawPath(chk, P('#2BA36B', stroke=5))
            text(cv, label, 30, 11, 30, '#FFFFFF', 1, name='bold')
            cv.restore()
            # little hearts
            rr = random.Random(2)
            for i in range(10):
                t0 = 39.0 + rr.uniform(0, 1.2)
                u = prog(t, t0, t0 + 1.6)
                if 0 < u < 1:
                    hx = bx + rr.choice([-1, 1]) * rr.uniform(220, 320)
                    hy = by - 20 - 200 * u
                    hs = rr.uniform(10, 18)
                    heart(cv, hx + 14 * math.sin(u * 6 + i), hy, hs, rr.choice(['#FF7A8A', '#FFB86B', '#E8724C']),
                          (1 - u))
    cv.restore()
    # thumb over the left edge
    cv.save()
    cv.translate(PX + 6, PY + 930)
    cv.rotate(14)
    rrect(cv, -46, -90, 84, 230, 42, P(shade(SKIN, 0.9)))
    rrect(cv, -30, -78, 52, 50, 22, P(shade(SKIN, 1.02), 0.6))
    cv.restore()
    cv.restore()


def heart(cv, x, y, s, c, a):
    p = skia.Path()
    p.moveTo(x, y + s * 0.9)
    p.cubicTo(x - s * 1.6, y - s * 0.2, x - s * 0.6, y - s * 1.3, x, y - s * 0.4)
    p.cubicTo(x + s * 0.6, y - s * 1.3, x + s * 1.6, y - s * 0.2, x, y + s * 0.9)
    p.close()
    cv.drawPath(p, P(c, a))


# ---------------------------------------------------------------- scene: end card (45 - 48.5)

def end_card(cv, t):
    cv.drawRect(skia.Rect.MakeWH(W, H), P(shader=lin((0, 0), (0, H), [col('#0A0C22'), col('#1E1838'), col('#0A0C1E')],
                                                       [0, 0.5, 1])))
    rr = random.Random(12)
    for i in range(18):
        x, y, r = rr.uniform(0, W), rr.uniform(0, H), rr.uniform(30, 120)
        glow(cv, x + 14 * math.sin(t * 0.4 + i), y - (t - 45) * rr.uniform(6, 20), r,
             rr.choice(['#FFB765', '#FF8A6A', '#8FA6FF']), 0.10)
    a1 = smooth(prog(t, 45.3, 46.0))
    a2 = smooth(prog(t, 45.9, 46.5))
    a3 = smooth(prog(t, 46.4, 47.0))
    cv.save()
    cv.translate(540, 880)
    s = lerp(0.94, 1.0, ease_out(prog(t, 45.3, 46.4)))
    cv.scale(s, s)
    text(cv, PHRASE, 0, 0, 132, GOLD, 0.8 * a1, name='jpb', blur=30, blend=skia.BlendMode.kPlus)
    text(cv, PHRASE, 0, 0, 132, '#FFF6E0', a1, name='jpb')
    cv.restore()
    text(cv, ROMAJI, 540, 1000, 46, '#FFE3B0', a2, name='ital')
    cv.drawLine(440, 1060, 640, 1060, P(GOLD, 0.5 * a3, stroke=2))
    text(cv, 'Thank you for your hard work.', 540, 1140, 46, '#FFFFFF', a3, name='med')
    # tiny faceless car driving across bottom
    u = prog(t, 45.4, 48.5)
    car(cv, lerp(-200, 1300, u), 1560, 0.32, u * 120, lights=1.0)


# ---------------------------------------------------------------- captions

CAPTIONS = [
    ('Working late… again.', 0.8, 6.2, 1580),
    ('Finally driving home,\nexhausted.', 7.0, 11.0, 1580),
    ('Japanese audio playing,\nlike every drive…', 11.7, 15.9, 1580),
    ('…just sounds I could\nnever quite catch.', 16.2, 20.6, 1580),
    ('Wait…\nI UNDERSTOOD that!', 21.5, 26.7, 1580),
    ('I couldn’t wait to get home\nand look it up.', 27.6, 32.0, 1600),
    ('But was it a good phrase…\nor a bad one?', 32.7, 37.3, 250),
    ('Exactly what I needed\nto hear tonight.', 41.6, 45.2, 1580),
]


def captions(cv, t):
    for (s, t0, t1, y) in CAPTIONS:
        if t < t0 or t > t1:
            continue
        a = ease_out(prog(t, t0, t0 + 0.45)) * (1 - smooth(prog(t, t1 - 0.4, t1)))
        dy = (1 - ease_out(prog(t, t0, t0 + 0.5))) * 26
        lines = s.split('\n')
        size = 52
        lh = 66
        w = max(text_w(l, 'semi', size) for l in lines)
        hh = lh * len(lines) + 44
        top = y - hh / 2 + dy
        rrect(cv, 540 - w / 2 - 46, top, w + 92, hh, 40, P('#070914', 0.62 * a))
        for i, l in enumerate(lines):
            text(cv, l, 540, top + 22 + lh * i + size * 0.95, size, '#FFFFFF', a, name='semi')


# ---------------------------------------------------------------- compositor

SCENES = [
    (office_ext, 0.0, 3.0),
    (office_int, 2.5, 7.0),
    (drive_ext, 6.5, 11.6),
    (car_int, 11.0, 27.6),
    (home_ext, 27.0, 32.8),
    (living, 32.2, 34.6),
    (phone_ui, 34.0, 41.2),
    (celebrate, 40.6, 45.6),
    (end_card, 45.0, DUR + 1),
]

_grain = None


def grain_image(i):
    global _grain
    if _grain is None:
        g = np.random.default_rng(1)
        _grain = []
        for _ in range(4):
            n = g.integers(0, 255, size=(480, 270), dtype=np.uint8)
            arr = np.stack([n, n, n, np.full_like(n, 255)], axis=-1)
            _grain.append(skia.Image.fromarray(arr, colorType=skia.kRGBA_8888_ColorType))
    return _grain[i % 4]


def draw_frame(cv, t):
    cv.clear(col('#000000'))
    active = [(f, a, b) for (f, a, b) in SCENES if a <= t < b]
    for idx, (f, a, b) in enumerate(active):
        if idx == 0:
            cv.save()
            f(cv, t)
            cv.restore()
        else:
            prev_end = active[idx - 1][2]
            alpha = smooth(prog(t, a, prev_end))
            cv.saveLayerAlpha(None, int(alpha * 255))
            f(cv, t)
            cv.restore()
    captions(cv, t)
    # vignette + grain + fade in/out
    cv.drawRect(skia.Rect.MakeWH(W, H), P(shader=rad((W / 2, H / 2), 1150, [col('#000000', 0), col('#000000', 0),
                                                                          col('#000000', 0.5)], [0, 0.55, 1])))
    gp = skia.Paint(Alphaf=0.05)
    gp.setBlendMode(skia.BlendMode.kOverlay)
    cv.drawImageRect(grain_image(int(t * FPS)), skia.Rect.MakeWH(W, H),
                     skia.SamplingOptions(skia.FilterMode.kLinear), gp)
    fade = max(1 - prog(t, 0, 0.6), prog(t, DUR - 0.9, DUR))
    if fade > 0:
        cv.drawRect(skia.Rect.MakeWH(W, H), P('#000000', fade))


_surface = None


def render(i):
    global _surface
    if _surface is None:
        _surface = skia.Surface(W, H)
    cv = _surface.getCanvas()
    draw_frame(cv, i / FPS)
    return _surface.makeImageSnapshot().toarray().tobytes()


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == '--still':
        for k in range(2, len(sys.argv) - 1, 2):
            t, path = float(sys.argv[k]), sys.argv[k + 1]
            s = skia.Surface(W, H)
            draw_frame(s.getCanvas(), t)
            s.makeImageSnapshot().save(path, skia.kPNG)
        return
    out = sys.argv[1] if len(sys.argv) > 1 else 'video.mp4'
    n = int(DUR * FPS)
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra',
                           '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'slow',
                           '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out],
                          stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for k, buf in enumerate(pool.imap(render, range(n), chunksize=4)):
            ff.stdin.write(buf)
            if k % 150 == 0:
                print(f'frame {k}/{n}', flush=True)
    ff.stdin.close()
    ff.wait()


if __name__ == '__main__':
    main()
