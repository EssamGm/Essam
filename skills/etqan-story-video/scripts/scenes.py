"""Scenes and on-screen components for "Abu Bedr and the Ice Cream", in the Etqan identity.

    python3 scenes.py --stills OUT_DIR    render the style frames for review
"""
import math
import os
import random
import sys

import skia

import etqan as E
from render_lib import (ABU_BEDR, BEDR, H, P, W, col, ease_out, glow, lerp, lin, mixc, person, poly, prog,
                        rad, rrect, shade, smooth)

ART_BOTTOM = 820          # artwork lives above this; the subtitle panel sits below
FLOOR_Y = 790
WOOD = '#7A5536'

# ------------------------------------------------------------------ the study at 6 pm

_rng = random.Random(4)
SKYLINE = []
_x = 220
while _x < 640:
    w = _rng.uniform(40, 90)
    SKYLINE.append((_x, w, _rng.uniform(40, 150)))
    _x += w + _rng.uniform(0, 8)


def clock(cv, x, y, r, hour=6, minute=0):
    cv.drawCircle(x, y, r + 8, P(E.BORDER))
    cv.drawCircle(x, y, r, P(E.TEXT))
    for i in range(12):
        a = math.radians(i * 30)
        l = 12 if i % 3 == 0 else 6
        cv.drawLine(x + math.sin(a) * (r - 8), y - math.cos(a) * (r - 8),
                    x + math.sin(a) * (r - 8 - l), y - math.cos(a) * (r - 8 - l), P(E.NAVY, stroke=4))
    ha = math.radians((hour % 12 + minute / 60) * 30)
    ma = math.radians(minute * 6)
    cv.drawLine(x, y, x + math.sin(ha) * r * 0.5, y - math.cos(ha) * r * 0.5, P(E.NAVY, stroke=8))
    cv.drawLine(x, y, x + math.sin(ma) * r * 0.75, y - math.cos(ma) * r * 0.75, P(E.NAVY, stroke=5))
    cv.drawCircle(x, y, 6, P(E.GOLD))


def window(cv, x, y, w, h):
    cv.save()
    cv.clipRect(skia.Rect.MakeXYWH(x, y, w, h))
    # 6 pm: dusk sky
    cv.drawRect(skia.Rect.MakeXYWH(x, y, w, h), P(shader=lin((0, y), (0, y + h), [
        col(E.NAVY_LIGHT), col('#C98A5A'), col('#F1C27D')], [0, 0.72, 1])))
    glow(cv, x + w * 0.7, y + h * 0.86, 120, '#FFE0A0', 0.6)
    for (bx, bw, bh) in SKYLINE:
        cv.drawRect(skia.Rect.MakeXYWH(x + (bx - 220) * w / 420, y + h - bh, bw * w / 420, bh), P(E.SURFACE, 0.92))
    cv.restore()
    rrect(cv, x - 14, y - 14, w + 28, h + 28, 10, P(E.BORDER, stroke=16, cap=False))
    cv.drawLine(x + w / 2, y, x + w / 2, y + h, P(E.BORDER, stroke=10))
    cv.drawRect(skia.Rect.MakeXYWH(x - 30, y + h + 10, w + 60, 16), P(E.BORDER))


def desk(cv, book='closed', drawer_open=0.0):
    # desk front-on, the person sits at its left end facing right
    top_y, x0, x1 = 600, 760, 1360
    cv.drawRect(skia.Rect.MakeXYWH(x0, top_y, x1 - x0, 24), P(shade(WOOD, 1.1)))
    cv.drawRect(skia.Rect.MakeXYWH(x0 + 20, top_y + 24, x1 - x0 - 40, 150), P(WOOD))
    # drawer
    u = drawer_open
    if u > 0:
        cv.drawRect(skia.Rect.MakeXYWH(x0 + 40, top_y + 30, 260, 24 * u), P('#2A1C12'))
    g = 1 + 0.06 * u
    cv.save()
    cv.translate(x0 + 170, top_y + 94 + 16 * u)
    cv.scale(g, g)
    cv.drawRect(skia.Rect.MakeXYWH(-130, -50, 260, 100), P(shade(WOOD, 0.88 + 0.1 * u)))
    rrect(cv, -30, -6, 60, 12, 6, P(E.GOLD))
    cv.restore()
    cv.drawRect(skia.Rect.MakeXYWH(x0 + 340, top_y + 44, 240, 100), P(shade(WOOD, 0.88)))
    rrect(cv, x0 + 430, top_y + 88, 60, 12, 6, P(shade(WOOD, 0.6)))
    for lx in (x0 + 30, x1 - 52):
        cv.drawRect(skia.Rect.MakeXYWH(lx, top_y + 174, 22, FLOOR_Y - top_y - 174), P(shade(WOOD, 0.75)))
    # lamp
    cv.drawLine(1290, top_y, 1290, top_y - 150, P(E.BORDER, stroke=8))
    cv.drawLine(1290, top_y - 150, 1230, top_y - 190, P(E.BORDER, stroke=8))
    shade_p = poly([(1176, top_y - 214), (1262, top_y - 172), (1236, top_y - 132), (1160, top_y - 168)])
    cv.drawPath(shade_p, P(E.NAVY_SOFT))
    cv.drawLine(1160, top_y - 168, 1236, top_y - 132, P('#FFE2A8', stroke=6))
    glow(cv, 1200, top_y - 140, 260, '#FFD58A', 0.35)
    # the English book
    if book == 'closed':
        rrect(cv, 890, top_y - 34, 270, 34, 5, P(E.NAVY_SOFT))
        cv.drawRect(skia.Rect.MakeXYWH(896, top_y - 34, 258, 8), P(E.TEXT))
        E.draw_text(cv, 'ENGLISH', 1025, top_y - 6, 20, E.GOLD, kind='btn')
    elif book == 'open':
        cv.drawPath(poly([(860, top_y - 6), (1010, top_y - 44), (1010, top_y), (860, top_y)]), P(E.TEXT))
        cv.drawPath(poly([(1010, top_y - 44), (1160, top_y - 6), (1160, top_y), (1010, top_y)]), P(shade(E.TEXT, 0.9)))
        for k in range(3):
            cv.drawLine(890, top_y - 12 - k * 8, 990, top_y - 36 - k * 4 + k * 3, P(E.TEXT_2, stroke=2))
        cv.drawLine(1010, top_y - 44, 1010, top_y, P(E.NAVY_SOFT, stroke=4))


def room(cv, t, book='closed', drawer_open=0.0, door_open=0.0):
    cv.drawRect(skia.Rect.MakeWH(W, H), P(shader=lin((0, 0), (0, FLOOR_Y), [col(E.NAVY), col(E.ELEVATED)])))
    glow(cv, 1205, 460, 900, '#FFC56B', 0.10)
    window(cv, 240, 150, 400, 330)
    clock(cv, 1015, 230, 74)
    # shelf with books and a plant, above the desk
    cv.drawRect(skia.Rect.MakeXYWH(1120, 330, 330, 14), P(E.BORDER))
    for i, c in enumerate((E.NAVY_LIGHT, E.GOLD, E.TEXT_2, E.NAVY_SOFT)):
        rrect(cv, 1140 + i * 34, 330 - (90 + 12 * (i % 2)), 26, 90 + 12 * (i % 2), 4, P(c, 0.9))
    rrect(cv, 1360, 270, 56, 60, 10, P(E.BORDER))
    for ang in (-35, -10, 15, 38):
        a = math.radians(ang)
        cv.drawLine(1388, 275, 1388 + math.sin(a) * 60, 275 - math.cos(a) * 70, P(E.POSITIVE, stroke=12))
    door(cv, door_open)
    # floor
    cv.drawRect(skia.Rect.MakeXYWH(0, FLOOR_Y, W, H - FLOOR_Y), P(E.SURFACE))
    cv.drawRect(skia.Rect.MakeXYWH(0, FLOOR_Y, W, 4), P(E.BORDER))
    # chair (left end of the desk)
    rrect(cv, 520, 640, 230, 30, 14, P(E.BORDER))
    rrect(cv, 500, 380, 40, 290, 18, P(E.BORDER))
    cv.drawLine(630, 670, 630, 760, P(shade(E.BORDER, 0.8), stroke=14))
    cv.drawLine(560, 775, 700, 775, P(shade(E.BORDER, 0.8), stroke=10))
    desk(cv, book, drawer_open)


def door(cv, open_=0.0):
    x, y, w, h = 1610, 250, 230, FLOOR_Y - 250
    cv.drawRect(skia.Rect.MakeXYWH(x - 16, y - 16, w + 32, h + 16), P(E.BORDER))
    cv.drawRect(skia.Rect.MakeXYWH(x, y, w, h), P(shade('#FFD9A0', 0.9)))   # warm hallway light
    dw = w * (1 - 0.82 * open_)
    cv.drawRect(skia.Rect.MakeXYWH(x, y, dw, h), P(shade(WOOD, 0.95)))
    cv.drawRect(skia.Rect.MakeXYWH(x + dw * 0.12, y + 40, dw * 0.76, h * 0.36), P(shade(WOOD, 0.85)))
    cv.drawRect(skia.Rect.MakeXYWH(x + dw * 0.12, y + 80 + h * 0.36, dw * 0.76, h * 0.4), P(shade(WOOD, 0.85)))
    cv.drawCircle(x + dw - 26, y + h * 0.55, 9, P(E.GOLD))


def lamp_light():
    return rad((1205, 460), 900, [col('#FFC56B', 0.28), col('#FFC56B', 0)])


# ------------------------------------------------------------------ props

def thought(cv, x, y, text, a=1.0):
    for i, (dx, dy, r) in enumerate(((-70, 90, 9), (-48, 62, 14))):
        cv.drawCircle(x + dx, y + dy, r, P(E.TEXT, a))
    rrect(cv, x - 90, y - 40, 180, 84, 42, P(E.TEXT, a))
    E.draw_text(cv, text, x, y + 16, 40, E.NAVY, kind='h', alpha=a)


def heat_waves(cv, x, y, t, a=1.0):
    for i in range(3):
        p = skia.Path()
        x0 = x + (i - 1) * 34
        p.moveTo(x0, y)
        for k in range(1, 7):
            p.lineTo(x0 + 7 * math.sin(k * 1.3 + t * 5 + i), y - k * 14)
        cv.drawPath(p, P('#FF9C5A', 0.8 * a, stroke=5))


def question_mark(cv, x, y, size, a=1.0):
    E.draw_text(cv, '?', x, y, size, E.GOLD, kind='logo', alpha=a)


def check_mark(cv, x, y, r, ok=True, a=1.0):
    cv.drawCircle(x, y, r, P(E.POSITIVE if ok else E.ALERT, a))
    p = skia.Path()
    if ok:
        p.moveTo(x - r * 0.42, y + r * 0.02)
        p.lineTo(x - r * 0.1, y + r * 0.34)
        p.lineTo(x + r * 0.45, y - r * 0.3)
    else:
        p.moveTo(x - r * 0.35, y - r * 0.35)
        p.lineTo(x + r * 0.35, y + r * 0.35)
        p.moveTo(x + r * 0.35, y - r * 0.35)
        p.lineTo(x - r * 0.35, y + r * 0.35)
    cv.drawPath(p, P(E.TEXT, a, stroke=r * 0.2))


# ------------------------------------------------------------------ on-screen text

PANEL = (140, 846, 1640, 196)   # x, y, w, h


def subtitle(cv, en, ar, hl_en=None, hl_ar=None, a=1.0, speaker=None, kind=None, wait=None):
    """Bilingual subtitle panel. kind: None | 'q' (question) | 'yes' | 'no'.
    wait: 0..1 progress of the learner's answer pause (questions only)."""
    x, y, w, h = PANEL
    cv.saveLayerAlpha(None, int(255 * a))
    rrect(cv, x, y, w, h, 26, P(E.SURFACE, 0.94))
    rrect(cv, x, y, w, h, 26, P(E.BORDER, stroke=2))
    cx = x + w / 2
    if kind == 'q':
        # the brand square marks a question
        cv.drawRect(skia.Rect.MakeXYWH(x + 44, y + 50, 26, 26), P(E.GOLD))
    elif kind in ('yes', 'no'):
        check_mark(cv, x + 58, y + 64, 22, ok=(kind == 'yes'))
    E.draw_text(cv, en, cx, y + 82, 56, E.TEXT, kind='semi', highlight=hl_en)
    E.draw_text(cv, ar, cx, y + 160, 48, E.TEXT_2, kind='med', highlight=hl_ar)
    if wait is not None:
        # learner's turn: a thin gold bar that empties during the pause
        bw = 300
        bx, by = x + w - bw - 50, y + h - 26
        rrect(cv, bx, by, bw, 8, 4, P(E.BORDER))
        rrect(cv, bx, by, bw * (1 - wait), 8, 4, P(E.GOLD))
        E.draw_text(cv, 'Your turn', bx, by - 16, 26, E.GOLD, kind='semi', align='l')
        E.draw_text(cv, 'دورك', bx + bw, by - 16, 26, E.GOLD, kind='semi', align='r')
    if speaker:
        en_name, ar_name = speaker
        label_w = E.text_width('semi', en_name, 30) + E.text_width('semi', ar_name, 30) + 90
        rrect(cv, x + 30, y - 30, label_w, 54, 27, P(E.NAVY_SOFT))
        wn = E.draw_text(cv, en_name, x + 58, y + 7, 30, E.TEXT, kind='semi', align='l')
        cv.drawRect(skia.Rect.MakeXYWH(x + 58 + wn + 16, y - 8, 10, 10), P(E.GOLD))
        E.draw_text(cv, ar_name, x + 58 + wn + 42, y + 7, 30, E.TEXT, kind='semi', align='l')
    cv.restore()


def section_chip(cv, en, ar, a=1.0):
    cv.saveLayerAlpha(None, int(255 * a))
    w = E.text_width('btn', en, 34) + E.text_width('btn', ar, 34) + 110
    rrect(cv, 60, 46, w, 70, 35, P(E.SURFACE, 0.9))
    cv.drawRect(skia.Rect.MakeXYWH(92, 72, 18, 18), P(E.GOLD))
    wn = E.draw_text(cv, en, 128, 93, 34, E.TEXT, kind='btn', align='l')
    E.draw_text(cv, ar, 128 + wn + 24, 93, 34, E.TEXT_2, kind='btn', align='l')
    cv.restore()


def watermark(cv, a=0.9):
    # reversed logo, top right; clear space = the square's height on every side
    E.draw_logo(cv, W - 60 - 170, 52, 170, dark=True, word_alpha=a, square_alpha=a)


def end_screen(cv, t=99.0, t0=0.0):
    cv.drawRect(skia.Rect.MakeWH(W, H), P(E.SURFACE))
    sq = ease_out(prog(t, t0, t0 + 0.4))
    wd = ease_out(prog(t, t0 + 0.4, t0 + 0.9))
    lw = 560
    E.draw_logo(cv, (W - lw) / 2, (H - lw * E.LOGO_H / E.LOGO_W) / 2, lw, dark=True, word_alpha=wd, square_alpha=sq, word_dx=(1 - wd) * 30)


DEFAULT_WORDS = [('ready', 'مستعد'), ('hot', 'يشعر بالحر'), ('happy', 'سعيد'), ('confused', 'حائر')]


def word_card(cv, a=1.0, words=None):
    """The story's target words (English, Arabic), shown before the end screen. Fits 2-5 cards."""
    cv.drawRect(skia.Rect.MakeWH(W, H), P(E.SURFACE))
    E.draw_text(cv, 'Words in this story', W / 2, 190, 60, E.TEXT, kind='h', alpha=a)
    E.draw_text(cv, 'كلمات القصة', W / 2, 270, 48, E.TEXT_2, kind='h', alpha=a)
    words = words or DEFAULT_WORDS
    n = len(words)
    gap = 40
    cw, chh = min(380, (W - 160 - (n - 1) * gap) / n), 380
    x0 = (W - (n * cw + (n - 1) * gap)) / 2
    for i, (en, ar) in enumerate(words):
        x = x0 + i * (cw + gap)
        rrect(cv, x, 360, cw, chh, 28, P(E.ELEVATED, a))
        rrect(cv, x, 360, cw, chh, 28, P(E.BORDER, a, stroke=2))
        cv.drawRect(skia.Rect.MakeXYWH(x + cw / 2 - 11, 400, 22, 22), P(E.GOLD, a))
        E.draw_text(cv, en, x + cw / 2, 560, 64, E.GOLD, kind='h', alpha=a)
        E.draw_text(cv, ar, x + cw / 2, 660, 52, E.TEXT, kind='h', alpha=a)


# ------------------------------------------------------------------ style frames

def frame_ready(cv):
    room(cv, 0, book='open')
    pz = dict(lean=4, head=-2, arm_f=(30, 96), arm_b=(36, 100), leg_f=(86, 2), leg_b=(82, -2))
    person(cv, 640, 642, 1.12, pz, ABU_BEDR, light=lamp_light())
    thought(cv, 790, 230, 'ABC')
    watermark(cv)
    subtitle(cv, 'Abu Bedr is ready.', 'أبو بدر مستعد.', 'ready', 'مستعد')


def frame_bedr(cv):
    room(cv, 0, book='closed', door_open=1.0)
    pz = dict(lean=0, head=10, arm_f=(30, 96), arm_b=(36, 100), leg_f=(86, 2), leg_b=(82, -2))
    person(cv, 640, 642, 1.12, pz, ABU_BEDR, light=lamp_light())
    bz = dict(lean=2, head=6, arm_f=(130, 175), arm_b=(40, 75), leg_f=(4, 2), leg_b=(-6, -4))
    person(cv, 1500, 640, 1.0, bz, BEDR, facing=-1, light=lamp_light())
    heat_waves(cv, 1505, 340, 0.3)
    watermark(cv)
    subtitle(cv, 'Baba, I am hot. I want ice cream, please!', 'بابا، أنا أشعر بالحر. أريد آيس كريم، من فضلك!',
             'hot', 'بالحر', speaker=('Bedr', 'بدر'))


def frame_question(cv):
    room(cv, 0, book='closed')
    pz = dict(lean=-4, head=-16, arm_f=(150, 170), arm_b=(36, 100), leg_f=(86, 2), leg_b=(82, -2))
    person(cv, 640, 642, 1.12, pz, ABU_BEDR, light=lamp_light())
    question_mark(cv, 760, 250, 160)
    section_chip(cv, 'Questions', 'الأسئلة')
    watermark(cv)
    subtitle(cv, 'Is Abu Bedr confused?', 'هل أبو بدر حائر؟', 'confused', 'حائر', kind='q', wait=0.35)


def frame_answer(cv):
    room(cv, 0, book='closed')
    pz = dict(lean=-4, head=-16, arm_f=(150, 170), arm_b=(36, 100), leg_f=(86, 2), leg_b=(82, -2))
    person(cv, 640, 642, 1.12, pz, ABU_BEDR, light=lamp_light())
    question_mark(cv, 760, 250, 160)
    section_chip(cv, 'Questions', 'الأسئلة')
    watermark(cv)
    subtitle(cv, 'No. He is not happy. He is confused.', 'لا. هو ليس سعيدًا. هو حائر.', 'confused', 'حائر',
             kind='no')


STILLS = [('1_story_ready', frame_ready), ('2_story_bedr', frame_bedr), ('3_question', frame_question),
          ('4_answer', frame_answer), ('5_words', word_card), ('6_end', end_screen)]


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--stills':
        out = sys.argv[2]
        os.makedirs(out, exist_ok=True)
        for name, fn in STILLS:
            s = skia.Surface(W, H)
            cv = s.getCanvas()
            cv.clear(col(E.SURFACE))
            fn(cv)
            s.makeImageSnapshot().save(os.path.join(out, name + '.png'), skia.kPNG)
            print('wrote', name)
