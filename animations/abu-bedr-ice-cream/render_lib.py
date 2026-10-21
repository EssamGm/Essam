"""Drawing helpers and the faceless character rig for the Abu Bedr video (1920x1080)."""
import math

import skia

W, H = 1920, 1080
FPS = 30


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
    return skia.GradientShader.MakeLinear([skia.Point(*p0), skia.Point(*p1)], colors, pos)


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


# ------------------------------------------------------------------ character rig

DEFAULT_POSE = dict(lean=0.0, head=0.0, arm_f=(8.0, 14.0), arm_b=(-6.0, -2.0),
                    leg_f=(3.0, 1.0), leg_b=(-3.0, -1.0), bob=0.0)

# casual home clothes
ABU_BEDR = dict(skin='#C68A62', hair='#1E1A22', top='#DCE2EA', pants='#2A3F5C', shoe='#3A2E2A',
                beard=True, sleeve=0.55, leg=1.0, torso=1.0, head=1.0)
# a boy: shorter legs and body, slightly larger head
BEDR = dict(skin='#CF966C', hair='#231C24', top='#3E6C99', pants='#1C2F47', shoe='#E9ECF1',
            beard=False, sleeve=0.5, leg=0.72, torso=0.78, head=1.12)


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
    """keys: list of (time, pose). Smoothly interpolates (no overshoot, per the motion guideline)."""
    if t <= keys[0][0]:
        return pose_mix(keys[0][1], keys[0][1], 0)
    for (t0, p0), (t1, p1) in zip(keys, keys[1:]):
        if t <= t1:
            return pose_mix(p0, p1, smooth((t - t0) / (t1 - t0)))
    return pose_mix(keys[-1][1], keys[-1][1], 0)


def _pt(x0, y0, a, l):
    return x0 + l * math.sin(math.radians(a)), y0 + l * math.cos(math.radians(a))


def _arm(cv, sh, a1, a2, skin, sleeve_col, sleeve, w):
    e = _pt(*sh, a1, 86)
    h = _pt(*e, a2, 80)
    path = skia.Path()
    path.moveTo(*sh)
    path.lineTo(*e)
    path.lineTo(*h)
    cv.drawPath(path, P(skin, stroke=w))
    s_end = _pt(*sh, a1, 86 * sleeve)
    cv.drawLine(sh[0], sh[1], s_end[0], s_end[1], P(sleeve_col, stroke=w + 6))
    cv.drawCircle(h[0], h[1], w * 0.5, P(skin))
    return h


def person(cv, x, y, s, pose, outfit=ABU_BEDR, facing=1, light=None, alpha=1.0, hold=None):
    """Faceless person: head with hair, no eyes, nose or mouth. (x, y) = hip position.
    Angles: 0 = straight down, + = forward. hold: callback(cv, hand_xy) to draw a held object."""
    o = outfit
    pz = dict(DEFAULT_POSE)
    pz.update(pose)
    cv.saveLayerAlpha(None, int(clamp(alpha) * 255))
    cv.save()
    cv.translate(x, y + pz['bob'])
    cv.scale(s * facing, s)
    # legs (world angles)
    for side, k in (('leg_b', 0.75), ('leg_f', 1.0)):
        a1, a2 = pz[side]
        hx = -6 if side == 'leg_b' else 8
        kn = _pt(hx, 0, a1, 98 * o['leg'])
        an = _pt(*kn, a2, 96 * o['leg'])
        path = skia.Path()
        path.moveTo(hx, 0)
        path.lineTo(*kn)
        path.lineTo(*an)
        cv.drawPath(path, P(shade(o['pants'], k), stroke=40))
        rrect(cv, an[0] - 16, an[1] - 4, 50, 22, 11, P(shade(o['shoe'], k)))
    cv.save()
    cv.rotate(pz['lean'])
    T = o['torso']
    sh = (2, -148 * T)
    a1, a2 = pz['arm_b']
    _arm(cv, sh, a1, a2, shade(o['skin'], 0.78), shade(o['top'], 0.72), o['sleeve'], 30)
    cv.drawOval(skia.Rect.MakeXYWH(-50, -26, 100, 50), P(o['pants']))
    # t-shirt torso with a soft collar
    rrect(cv, -47, -178 * T, 94, 176 * T, 40, P(o['top']))
    rrect(cv, -47, -40, 94, 22, 10, P(shade(o['top'], 0.9)))
    cv.drawArc(skia.Rect.MakeXYWH(-6, -178 * T - 8, 28, 22), 20, 140, False, P(shade(o['top'], 0.8), stroke=4))
    # neck + head
    cv.save()
    cv.translate(8, -172 * T)
    cv.scale(o['head'], o['head'])
    cv.rotate(pz['head'])
    rrect(cv, -10, -20, 22, 28, 8, P(shade(o['skin'], 0.86)))
    hx, hy, r = 6, -66, 50
    cv.drawCircle(hx, hy, r, P(o['skin']))
    cv.save()
    clip = skia.Path()
    clip.addCircle(hx, hy, r + 6)
    cv.clipPath(clip, doAntiAlias=True)
    hair = skia.Path()
    hair.addCircle(hx - 16, hy - 19, r + 1)
    cv.drawPath(hair, P(o['hair']))
    if o['beard']:
        # short, neat beard along the jawline, from the ear to the chin (no facial features)
        cv.drawArc(skia.Rect.MakeXYWH(hx - r + 9, hy - r + 9, 2 * r - 18, 2 * r - 18), 18, 104, False,
                   P(o['hair'], 0.9, stroke=18, cap=True))
    cv.restore()
    cv.drawOval(skia.Rect.MakeXYWH(hx - 10, hy - 6, 17, 24), P(shade(o['skin'], 0.9)))
    cv.restore()
    a1, a2 = pz['arm_f']
    hand = _arm(cv, sh, a1, a2, o['skin'], shade(o['top'], 0.95), o['sleeve'], 30)
    if hold:
        hold(cv, hand)
    cv.restore()
    cv.restore()
    if light is not None:
        cv.drawRect(skia.Rect.MakeWH(W, H), P(shader=light, blend=skia.BlendMode.kSrcATop))
    cv.restore()


def walk_pose(phase, stride=1.0):
    s = math.sin(phase)
    s2 = math.sin(phase + math.pi)
    return dict(lean=4, head=0,
                leg_f=(26 * s * stride, 26 * s * stride - 34 * max(0.0, math.sin(phase + 1.3)) * stride),
                leg_b=(26 * s2 * stride, 26 * s2 * stride - 34 * max(0.0, math.sin(phase + math.pi + 1.3)) * stride),
                arm_f=(-22 * s * stride, -22 * s * stride + 26), arm_b=(22 * s * stride, 22 * s * stride + 26),
                bob=-6 * abs(math.cos(phase)))
