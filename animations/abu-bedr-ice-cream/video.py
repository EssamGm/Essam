"""Render "Abu Bedr and the Ice Cream" (1920x1080, Etqan identity) from the narration timeline.

    python3 video.py NARRATION_DIR OUT.mp4            # full video with sound
    python3 video.py NARRATION_DIR --still T OUT.png   # one frame, for checking

NARRATION_DIR is what voice.py wrote (timeline.json, narration.wav).
"""
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
from multiprocessing import Pool

import numpy as np
import skia

import etqan as E
import scenes as S
from render_lib import (ABU_BEDR, BEDR, FPS, H, P, W, clamp, col, ease_out, glow, lerp, pose_mix, prog, rrect,
                        shade, smooth, person, walk_pose)

ND = None
LINES = []
L = {}


def load(nd):
    global ND, LINES, L, T_WORDS, T_END, DUR
    ND = nd
    LINES = json.load(open(os.path.join(nd, 'timeline.json'), encoding='utf-8'))
    L = {l['id']: l for l in LINES}
    T_WORDS = LINES[-1]['end'] + 1.2
    T_END = T_WORDS + 5.0
    DUR = T_END + 3.4


def ls(i):
    return L[str(i)]['start']


def le(i):
    return L[str(i)]['end']


def lg(i):
    l = L[str(i)]
    return l['end'] + l['gap']


T_WORDS = T_END = DUR = 0.0
FADE = 0.45

# ------------------------------------------------------------------ geometry and kinematics

S_ABU, S_BEDR = 1.12, 1.0
SIT = (680, 642)
STAND_Y = 565
BEDR_Y = 640
DESK_BOOK = (1025, 583)

SHOPKEEPER = dict(skin='#B97E58', hair='#2A2026', top='#E9ECF1', pants='#2A3F5C', shoe='#2A2A2A',
                  beard=False, sleeve=0.55, leg=1.0, torso=1.0, head=1.0)

POSE_SIT = dict(lean=4, head=2, arm_f=(30, 96), arm_b=(36, 100), leg_f=(86, 2), leg_b=(82, -2))
POSE_SIT_RELAX = dict(lean=-2, head=6, arm_f=(16, 70), arm_b=(12, 60), leg_f=(86, 2), leg_b=(82, -2))
POSE_STAND = dict(lean=0, head=0, arm_f=(8, 14), arm_b=(-6, -2), leg_f=(3, 1), leg_b=(-3, -1))


def _rot(x, y, deg):
    a = math.radians(deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def shoulder_world(hip, s, pose, facing, outfit):
    rx, ry = _rot(2, -148 * outfit['torso'], pose.get('lean', 0))
    return hip[0] + facing * s * rx, hip[1] + pose.get('bob', 0) + s * ry


def arm_ik(hip, s, pose, facing, outfit, target, bend=1):
    """Angles (relative to the torso) that put the hand on `target` (world)."""
    sx, sy = shoulder_world(hip, s, pose, facing, outfit)
    dx, dy = (target[0] - sx) / (s * facing), (target[1] - sy) / s
    a = math.radians(pose.get('lean', 0))
    ux, uy = dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)
    l1, l2 = 86, 80
    D = clamp(math.hypot(ux, uy), abs(l1 - l2) + 0.5, l1 + l2 - 0.5)
    base = math.degrees(math.atan2(ux, uy))
    alpha = math.degrees(math.acos(clamp((l1 * l1 + D * D - l2 * l2) / (2 * l1 * D), -1, 1)))
    a1 = base - alpha * bend
    ex, ey = l1 * math.sin(math.radians(a1)), l1 * math.cos(math.radians(a1))
    a2 = math.degrees(math.atan2(ux - ex, uy - ey))
    return a1, a2


def hand_world(hip, s, pose, facing, outfit, arm='arm_f'):
    a1, a2 = pose[arm]
    T = outfit['torso']
    x, y = 2.0, -148 * T
    x += 86 * math.sin(math.radians(a1))
    y += 86 * math.cos(math.radians(a1))
    x += 80 * math.sin(math.radians(a2))
    y += 80 * math.cos(math.radians(a2))
    rx, ry = _rot(x, y, pose.get('lean', 0))
    return hip[0] + facing * s * rx, hip[1] + pose.get('bob', 0) + s * ry


def head_world(hip, s, pose, facing, outfit):
    T, hd = outfit['torso'], outfit['head']
    rx, ry = _rot(8 + 6 * hd, -172 * T - 66 * hd, pose.get('lean', 0))
    return hip[0] + facing * s * rx, hip[1] + pose.get('bob', 0) + s * ry


def walk_x(t, t0, t1, x0, x1):
    u = smooth(prog(t, t0, t1))
    return lerp(x0, x1, u)


def gait(x, s=S_ABU):
    return x * 2 * math.pi / (210 * s)


# ------------------------------------------------------------------ props

def draw_book(cv, x, y, ang=0.0, open_=0.0, w=270):
    cv.save()
    cv.translate(x, y)
    cv.rotate(ang)
    if open_ <= 0.01:
        h = w * 0.126
        rrect(cv, -w / 2, -h / 2, w, h, 5, P(E.NAVY_SOFT))
        cv.drawRect(skia.Rect.MakeXYWH(-w / 2 + 6, -h / 2, w - 12, h * 0.24), P(E.TEXT))
        if w > 150:
            E.draw_text(cv, 'ENGLISH', 0, h * 0.36, w * 0.074, E.GOLD, kind='btn')
    else:
        lift = 44 * open_
        hw = w * 0.56
        cv.drawPath(_page(-hw, lift), P(E.TEXT))
        cv.drawPath(_page(hw, lift), P(shade(E.TEXT, 0.9)))
        for k in range(3):
            cv.drawLine(-hw * 0.8, 10 - k * 8, -hw * 0.15, 10 - lift * 0.8 - k * 4 + k * 3, P(E.TEXT_2, open_, stroke=2))
        cv.drawLine(0, 17 - lift, 0, 17, P(E.NAVY_SOFT, stroke=4))
    cv.restore()


def _page(edge_x, lift):
    p = skia.Path()
    p.moveTo(edge_x, 11)
    p.lineTo(0, 17 - lift)
    p.lineTo(0, 17)
    p.lineTo(edge_x, 17)
    p.close()
    return p


def draw_cone(cv, x, y, s=1.0, ang=0.0, a=1.0):
    cv.save()
    cv.translate(x, y)
    cv.rotate(ang)
    cv.scale(s, s)
    cone = S.poly([(-17, -22), (17, -22), (0, 40)])
    cv.drawPath(cone, P('#D9A35B', a))
    for k in range(-1, 2):
        cv.drawLine(-13 + k * 8, -18, 4 + k * 8, 26, P('#B9853F', a, stroke=2))
    cv.drawCircle(0, -34, 21, P('#F3E6CF', a))
    cv.drawCircle(-6, -52, 15, P('#E99AAE', a))
    cv.restore()


def name_tag(cv, x, y, en, ar, a=1.0, focus=False):
    w = E.text_width('semi', en, 28) + E.text_width('semi', ar, 28) + 70
    rrect(cv, x - w / 2, y - 26, w, 50, 25, P(E.GOLD if focus else E.SURFACE, 0.92 * a))
    ink = E.SURFACE if focus else E.TEXT
    wn = E.draw_text(cv, en, x - w / 2 + 22, y + 9, 28, ink, kind='semi', align='l', alpha=a)
    E.draw_text(cv, ar, x - w / 2 + 22 + wn + 26, y + 9, 28, ink, kind='semi', align='l', alpha=a)


def thought_icon(cv, x, y, a=1.0, s=1.0, kind='ABC', tail=1):
    """Thought bubble centred at (x, y); tail=1 points the little circles down-right, -1 down-left."""
    cv.save()
    cv.translate(x, y)
    cv.scale(s, s)
    for (dx, dy, r) in ((70, 90, 9), (48, 62, 14)):
        cv.drawCircle(dx * tail, dy, r, P(E.TEXT, a))
    rrect(cv, -90, -42, 180, 86, 43, P(E.TEXT, a))
    if kind == 'ABC':
        E.draw_text(cv, 'ABC', 0, 16, 40, E.NAVY, kind='h', alpha=a)
    else:
        draw_cone(cv, 0, 12, 0.75, 0, a)
    cv.restore()


# ------------------------------------------------------------------ the study, driven by a state dict

def base_state():
    return dict(abu=dict(x=SIT[0], y=SIT[1], pose=dict(POSE_SIT_RELAX), facing=1, a=1.0),
                bedr=None, book='drawer', book_xy=None, book_ang=0.0, book_open=0.0, drawer=0.0, door=0.0,
                bubble=0.0, bubble_s=1.0, bubble_dy=0.0, qmark=0.0, heat=0.0, glow_bedr=0.0, glow_abu=0.0,
                cone=None, cone_xy=None, tags=0.0, tag_focus=None, wants=0.0, cam=(1.0, W / 2, H / 2), clock=0.0)


def draw_study(cv, t, st):
    z, cx, cy = st['cam']
    cv.save()
    cv.translate(W / 2, H / 2)
    cv.scale(z, z)
    cv.translate(-cx, -cy)
    S.room(cv, t, book=None, drawer_open=st['drawer'], door_open=st['door'])
    if st['clock'] > 0:
        cv.drawCircle(1015, 230, 96, P(E.GOLD, 0.9 * st['clock'], stroke=6))
    if st['book'] in ('table', 'open'):
        draw_book(cv, *DESK_BOOK, open_=st['book_open'] if st['book'] == 'open' else 0.0, w=270)
    light = S.lamp_light()
    b = st['bedr']
    if b and b['a'] > 0:
        if st['glow_bedr'] > 0:
            glow(cv, b['x'], b['y'] - 120, 260, '#FFD58A', 0.35 * st['glow_bedr'])
        person(cv, b['x'], b['y'], S_BEDR, b['pose'], BEDR, facing=b['facing'], light=light, alpha=b['a'])
    a = st['abu']
    if st['glow_abu'] > 0:
        glow(cv, a['x'], a['y'] - 150, 300, '#FFD58A', 0.3 * st['glow_abu'])
    person(cv, a['x'], a['y'], S_ABU, a['pose'], ABU_BEDR, facing=a['facing'], light=light, alpha=a['a'])
    # held props
    if st['book'] == 'hand':
        hx, hy = hand_world((a['x'], a['y']), S_ABU, a['pose'], a['facing'], ABU_BEDR)
        draw_book(cv, hx, hy - 6, st['book_ang'], 0.0, w=200)
    if st['cone'] == 'abu':
        hx, hy = hand_world((a['x'], a['y']), S_ABU, a['pose'], a['facing'], ABU_BEDR)
        draw_cone(cv, hx, hy - 10)
    elif st['cone'] == 'bedr' and b:
        hx, hy = hand_world((b['x'], b['y']), S_BEDR, b['pose'], b['facing'], BEDR)
        draw_cone(cv, hx, hy - 10)
    # thought, question mark, heat
    ah = head_world((a['x'], a['y']), S_ABU, a['pose'], a['facing'], ABU_BEDR)
    if st['bubble'] > 0:
        thought_icon(cv, ah[0] - 120, ah[1] - 150 + st['bubble_dy'], st['bubble'], st['bubble_s'])
    if st['qmark'] > 0:
        S.question_mark(cv, ah[0] + 70, ah[1] - 90 - 10 * math.sin(t * 2.2), 150, a=st['qmark'])
    if b and b['a'] > 0:
        bh = head_world((b['x'], b['y']), S_BEDR, b['pose'], b['facing'], BEDR)
        if st['heat'] > 0:
            S.heat_waves(cv, bh[0], bh[1] - 70, t, a=st['heat'])
        if st['wants'] > 0:
            thought_icon(cv, bh[0] - 200, bh[1] - 120, st['wants'], 1.1, kind='cone')
        if st['tags'] > 0:
            name_tag(cv, bh[0], bh[1] - 130, 'Bedr', 'بدر', st['tags'], focus=st['tag_focus'] == 'bedr')
    if st['tags'] > 0:
        dim = 0.45 if st['tag_focus'] == 'bedr' else 1.0
        name_tag(cv, ah[0], ah[1] - 130, 'Abu Bedr', 'أبو بدر', st['tags'] * dim)
    cv.restore()


# ------------------------------------------------------------------ part 1 choreography

def bedr_entry(t, st):
    """Bedr comes in through the door at line 9 (after 'But wait!')."""
    t_in = ls(9) + L['9'].get('split', 1.2)
    st['door'] = smooth(prog(t, t_in - 0.2, t_in + 0.4))
    if t < t_in:
        return
    x = walk_x(t, t_in + 0.2, t_in + 1.7, 1760, 1480)
    walking = t_in + 0.2 < t < t_in + 1.7
    pose = walk_pose(gait(x, S_BEDR), 0.9) if walking else dict(POSE_STAND, head=4)
    st['bedr'] = dict(x=x, y=BEDR_Y, pose=pose, facing=-1, a=smooth(prog(t, t_in, t_in + 0.35)))


def part1_state(t):
    st = base_state()
    a = st['abu']
    st['cam'] = (lerp(1.06, 1.0, smooth(prog(t, 0, ls(3)))), W / 2, H / 2)
    # line 2: the clock
    st['clock'] = smooth(prog(t, ls(2), ls(2) + 0.4)) * (1 - smooth(prog(t, lg(2) - 0.3, lg(2) + 0.2)))
    # line 3: wants to study English
    st['bubble'] = smooth(prog(t, ls(3) + 0.3, ls(3) + 0.8)) * (1 - smooth(prog(t, ls(9) - 0.2, ls(9) + 0.3)))
    pose = dict(POSE_SIT_RELAX)
    # line 4: opens the drawer
    drawer_hand = (835, 652)
    u_reach = smooth(prog(t, ls(4), ls(4) + 0.8))
    if u_reach > 0:
        p = pose_mix(POSE_SIT_RELAX, dict(POSE_SIT, lean=30, head=24), u_reach)
        p['arm_f'] = arm_ik(SIT, S_ABU, p, 1, ABU_BEDR, drawer_hand)
        p['arm_f'] = tuple(lerp(POSE_SIT_RELAX['arm_f'][i], p['arm_f'][i], u_reach) for i in range(2))
        pose = p
    st['drawer'] = smooth(prog(t, ls(4) + 0.6, ls(4) + 1.1)) * (1 - smooth(prog(t, ls(6) + 0.9, ls(6) + 1.4)))
    # line 5: takes the book (it rises from the drawer with his hand)
    if t >= ls(5) + 0.2:
        st['book'] = 'hand'
        u = smooth(prog(t, ls(5) + 0.2, ls(5) + 1.3))
        tgt = (lerp(drawer_hand[0], 880, u), lerp(drawer_hand[1], 520, u))
        p = dict(POSE_SIT, lean=lerp(30, 10, u), head=lerp(24, 6, u))
        p['arm_f'] = arm_ik(SIT, S_ABU, p, 1, ABU_BEDR, tgt)
        pose = p
        st['book_ang'] = lerp(-10, 0, u)
    # line 6: puts the book on the table
    if t >= ls(6):
        u = smooth(prog(t, ls(6), ls(6) + 0.8))
        tgt = (lerp(880, DESK_BOOK[0] - 40, u), lerp(520, DESK_BOOK[1] - 4, u))
        p = dict(POSE_SIT, lean=lerp(10, 12, u), head=8)
        p['arm_f'] = arm_ik(SIT, S_ABU, p, 1, ABU_BEDR, tgt)
        pose = p
        if t >= ls(6) + 0.8:
            st['book'] = 'table'
            r = smooth(prog(t, ls(6) + 0.8, ls(6) + 1.4))
            pose = pose_mix(p, POSE_SIT, r)
    # line 7: ready — the book opens, he sits up straight
    if t >= ls(7):
        st['book'] = 'open'
        st['book_open'] = smooth(prog(t, ls(7) + 0.1, ls(7) + 0.6))
        pose = pose_mix(POSE_SIT, dict(POSE_SIT, lean=0, head=10), smooth(prog(t, ls(7), ls(7) + 0.6)))
    # line 9: But wait! — he turns his head toward the door
    if t >= ls(9):
        pose = pose_mix(pose, dict(pose, head=-4, lean=-2), smooth(prog(t, ls(9), ls(9) + 0.5)))
    a['pose'] = pose
    bedr_entry(t, st)
    if st['bedr']:
        b = st['bedr']
        # line 10/11: hot — heat waves, fanning with his hand
        st['heat'] = smooth(prog(t, ls(10) + 0.3, ls(10) + 0.9))
        if t > ls(10) + 0.3:
            bp = dict(b['pose'])
            hh = head_world((b['x'], b['y']), S_BEDR, bp, -1, BEDR)
            fan = (hh[0] - 40 + 14 * math.sin(t * 12), hh[1] + 10)
            u = smooth(prog(t, ls(10) + 0.3, ls(10) + 0.8))
            ik = arm_ik((b['x'], b['y']), S_BEDR, bp, -1, BEDR, fan, bend=-1)
            bp['arm_f'] = tuple(lerp(bp['arm_f'][i], ik[i], u) for i in range(2))
            if t > ls(11):
                bp['lean'] = 6 + 3 * math.sin(t * 3)
            b['pose'] = bp
    # line 12: a good father — stands up, walks toward Bedr
    if t >= ls(12):
        u = smooth(prog(t, ls(12), ls(12) + 0.8))
        x = walk_x(t, ls(12) + 0.9, lg(12) - 0.1, SIT[0] + 30, 1240)
        a['x'] = lerp(SIT[0], SIT[0] + 30, u) if t < ls(12) + 0.9 else x
        a['y'] = lerp(SIT[1], STAND_Y, u)
        p = pose_mix(a['pose'], POSE_STAND, u)
        if ls(12) + 0.9 < t < lg(12) - 0.1:
            p = walk_pose(gait(x))
        a['pose'] = p
        st['bubble'] = 0
    return st


def part1b_state(t):
    """Lines 16-24: back in the study with the ice cream, then the confusion."""
    st = base_state()
    a, s16 = st['abu'], ls(16)
    st['book'] = 'open'
    st['book_open'] = 1.0
    st['door'] = 1.0 - smooth(prog(t, ls(19) + 1.6, ls(19) + 2.1))
    a.update(x=1240, y=STAND_Y, pose=dict(POSE_STAND))
    b = dict(x=1480, y=BEDR_Y, pose=dict(POSE_STAND, head=4), facing=-1, a=1.0)
    st['bedr'] = b
    st['heat'] = 1 - smooth(prog(t, s16 + 1.2, s16 + 2.0))
    meet = (1360, 548)
    # line 16: gives the ice cream to Bedr
    u = smooth(prog(t, s16, s16 + 0.9))
    held = (lerp(1300, meet[0], u), lerp(560, meet[1], u))
    pa = dict(POSE_STAND)
    pa['arm_f'] = arm_ik((a['x'], a['y']), S_ABU, pa, 1, ABU_BEDR, held)
    give = s16 + 1.0
    if t < give:
        st['cone'] = 'abu'
        ub = smooth(prog(t, s16 + 0.4, give))
        pb = dict(b['pose'])
        ik = arm_ik((b['x'], b['y']), S_BEDR, pb, -1, BEDR, meet)
        pb['arm_f'] = tuple(lerp(pb['arm_f'][i], ik[i], ub) for i in range(2))
        b['pose'] = pb
    else:
        st['cone'] = 'bedr'
        r = smooth(prog(t, give, give + 0.8))
        pa = pose_mix(pa, POSE_STAND, r)
        pb = dict(b['pose'])
        up = (lerp(meet[0], 1450, r), lerp(meet[1], 470, r))
        pb['arm_f'] = arm_ik((b['x'], b['y']), S_BEDR, pb, -1, BEDR, up)
        b['pose'] = pb
    a['pose'] = pa
    # line 17-18: happy — gentle hops and a warm glow
    st['glow_bedr'] = smooth(prog(t, ls(17), ls(17) + 0.5)) * (1 - smooth(prog(t, ls(19), ls(19) + 0.6)))
    if ls(17) <= t < ls(19):
        hop = abs(math.sin((t - ls(17)) * math.pi * 1.6)) * 22 * (1 - smooth(prog(t, lg(18) - 0.6, lg(18))))
        b['y'] = BEDR_Y - hop
        b['pose']['arm_b'] = (-30, -10)
    # line 19: Bedr leaves, Abu Bedr goes back to his chair and sits
    if t >= ls(19):
        bx = walk_x(t, ls(19), ls(19) + 1.6, 1480, 1780)
        b.update(x=bx, facing=1, a=1 - smooth(prog(t, ls(19) + 1.2, ls(19) + 1.6)),
                 pose=walk_pose(gait(bx, S_BEDR), 0.9) if t < ls(19) + 1.6 else dict(POSE_STAND))
        st['cone'] = 'bedr'
        ax = walk_x(t, ls(19) + 0.3, ls(19) + 2.2, 1240, SIT[0] + 30)
        if t < ls(19) + 2.2:
            a.update(x=ax, facing=-1, pose=walk_pose(gait(ax)))
        else:
            u = smooth(prog(t, ls(19) + 2.2, ls(19) + 2.9))
            a.update(x=lerp(SIT[0] + 30, SIT[0], u), y=lerp(STAND_Y, SIT[1], u), facing=1,
                     pose=pose_mix(POSE_STAND, POSE_SIT, u))
    if t >= ls(19) + 2.0:
        st['bedr'] = None if t > ls(19) + 1.7 else b
    # line 20: he looks at the table
    if t >= ls(20):
        z = lerp(1.0, 1.22, smooth(prog(t, ls(20), ls(20) + 1.2)))
        z = lerp(z, 1.0, smooth(prog(t, ls(24), lg(24) - 0.4)))
        st['cam'] = (z, lerp(W / 2, 900, smooth(prog(t, ls(20), ls(20) + 1.2))),
                     lerp(H / 2, 520, smooth(prog(t, ls(20), ls(20) + 1.2))))
        if t < ls(24):
            st['cam'] = (z, 900, 520)
        else:
            k = smooth(prog(t, ls(24), lg(24) - 0.4))
            st['cam'] = (z, lerp(900, W / 2, k), lerp(520, H / 2, k))
        a['pose'] = dict(POSE_SIT, head=lerp(2, 14, smooth(prog(t, ls(20), ls(20) + 0.6))))
        st['book'] = 'table'
        st['book_open'] = 0.0
    # line 21: "A book? Why is this book on the table?" — he picks it up and looks at it
    if ls(21) <= t < ls(22) + 0.5:
        p = dict(POSE_SIT, head=6)
        u = smooth(prog(t, ls(21), ls(21) + 0.5))
        lift = smooth(prog(t, ls(21) + 0.5, ls(21) + 1.2))
        back = smooth(prog(t, ls(22), ls(22) + 0.5))
        tgt = (lerp(DESK_BOOK[0] - 40, 900, lift - back * lift + back * 0), lerp(DESK_BOOK[1] - 4, 470, lift))
        if back > 0:
            tgt = (lerp(900, DESK_BOOK[0] - 40, back), lerp(470, DESK_BOOK[1] - 4, back))
        ik = arm_ik(SIT, S_ABU, p, 1, ABU_BEDR, tgt)
        p['arm_f'] = tuple(lerp(POSE_SIT['arm_f'][i], ik[i], u) for i in range(2))
        a['pose'] = p
        if u >= 0.99 and back < 0.99:
            st['book'] = 'hand'
            st['book_ang'] = 12 * math.sin((t - ls(21)) * 3.0) * lift
    # line 22-24: confused — scratches his head, a question mark
    if t >= ls(22) + 0.5:
        p = dict(POSE_SIT, lean=-2, head=-12)
        hh = head_world(SIT, S_ABU, p, 1, ABU_BEDR)
        scratch = (hh[0] + 4 + 8 * math.sin(t * 9), hh[1] - 52)
        u = smooth(prog(t, ls(22) + 0.5, ls(22) + 1.0))
        ik = arm_ik(SIT, S_ABU, p, 1, ABU_BEDR, scratch, bend=-1)
        p['arm_f'] = tuple(lerp(POSE_SIT['arm_f'][i], ik[i], u) for i in range(2))
        if t >= ls(24):
            k = smooth(prog(t, ls(24), ls(24) + 0.6))
            p = pose_mix(p, dict(POSE_SIT, lean=-4, head=-6, arm_f=(40, 150), arm_b=(30, 140)), k)
        a['pose'] = p
    st['qmark'] = smooth(prog(t, ls(22) + 0.3, ls(22) + 0.8))
    # line 23: he forgets — the "ABC" thought appears, then fades away
    if t >= ls(23):
        appear = smooth(prog(t, ls(23), ls(23) + 0.4))
        gone = smooth(prog(t, ls(23) + 1.0, ls(23) + 1.9))
        st['bubble'] = appear * (1 - gone)
        st['bubble_s'] = lerp(1.0, 0.7, gone)
        st['bubble_dy'] = -40 * gone
    return st


# ------------------------------------------------------------------ the street and the shop (lines 13-15)

_srng = random.Random(8)
STREET_BLD = []
_x = -40
while _x < W + 40:
    w = _srng.uniform(140, 260)
    STREET_BLD.append((_x, w, _srng.uniform(150, 330), [(_srng.random(), _srng.random()) for _ in range(6)]))
    _x += w + _srng.uniform(10, 40)


def draw_street(cv, t):
    cv.drawRect(skia.Rect.MakeWH(W, H), P(shader=S.lin((0, 0), (0, 700), [col(E.NAVY_LIGHT), col('#C98A5A'),
                                                                          col('#F1C27D')], [0, 0.7, 1])))
    glow(cv, 420, 600, 260, '#FFE0A0', 0.7)
    cv.drawCircle(420, 600, 70, P('#FFE3A3'))
    for (x, w, h, lights) in STREET_BLD:
        if 1100 < x < 1720:
            continue
        cv.drawRect(skia.Rect.MakeXYWH(x, 790 - h, w, h), P(E.ELEVATED))
        for (u, v) in lights:
            if v < 0.55:
                cv.drawRect(skia.Rect.MakeXYWH(x + 16 + u * (w - 46), 790 - h + 24 + v * (h - 60), 18, 22),
                            P('#FFC870', 0.7))
    # heat shimmer over the road — it is a hot day
    for i in range(5):
        y = 760 - i * 9
        p = skia.Path()
        p.moveTo(0, y)
        for k in range(1, 25):
            p.lineTo(k * 80, y + 3 * math.sin(k * 1.7 + t * 4 + i))
        cv.drawPath(p, P('#FFE6B0', 0.08, stroke=2))
    # the shop
    sx, sw = 1150, 560
    cv.drawRect(skia.Rect.MakeXYWH(sx, 390, sw, 400), P(E.NAVY_SOFT))
    for i in range(8):
        c = E.TEXT if i % 2 == 0 else E.NAVY_LIGHT
        cv.drawPath(S.poly([(sx - 20 + i * (sw + 40) / 8, 390), (sx - 20 + (i + 1) * (sw + 40) / 8, 390),
                            (sx - 20 + (i + 1) * (sw + 40) / 8, 440), (sx - 20 + i * (sw + 40) / 8, 440)]), P(c))
    rrect(cv, sx + 80, 300, sw - 160, 74, 14, P(E.SURFACE))
    E.draw_text(cv, 'ICE CREAM', sx + sw / 2 + 24, 352, 40, E.TEXT, kind='h')
    draw_cone(cv, sx + 135, 340, 0.62)
    # counter window, lit
    cv.drawRect(skia.Rect.MakeXYWH(sx + 30, 470, 300, 230), P('#FFD9A0'))
    for i in range(5):
        rrect(cv, sx + 50 + i * 54, 650, 44, 34, 6, P(['#E99AAE', '#F3E6CF', '#8FC9A8', '#C9946B', '#F3E6CF'][i]))
    cv.drawRect(skia.Rect.MakeXYWH(sx + 30, 470, 300, 230), P(E.BORDER, stroke=10, cap=False))
    # door
    cv.drawRect(skia.Rect.MakeXYWH(sx + 390, 520, 120, 270), P(shade('#7A5536', 0.95)))
    cv.drawCircle(sx + 490, 660, 7, P(E.GOLD))
    # ground
    cv.drawRect(skia.Rect.MakeXYWH(0, 790, W, H - 790), P(E.SURFACE))
    cv.drawRect(skia.Rect.MakeXYWH(0, 790, W, 4), P(E.BORDER))


def street_frame(cv, t):
    draw_street(cv, t)
    s13, s14, s15 = ls(13), ls(14), ls(15)
    sx = 1150
    counter = (sx + 40, 520)
    # the shopkeeper behind the counter window
    keeper_hip = (sx + 190, 700)
    kp = dict(POSE_STAND, head=6)
    hand_out = s14 + 0.1 < t < s14 + 1.2
    if hand_out:
        u = smooth(prog(t, s14 + 0.1, s14 + 0.6))
        tgt = (lerp(sx + 130, counter[0], u), lerp(600, counter[1], u))
        kp['arm_f'] = arm_ik(keeper_hip, 1.0, kp, -1, SHOPKEEPER, tgt)
    cv.save()
    cv.clipRect(skia.Rect.MakeXYWH(sx + 35, 475, 290, 170))
    person(cv, keeper_hip[0], keeper_hip[1], 1.0, kp, SHOPKEEPER, facing=-1)
    cv.restore()
    if hand_out:
        # the arm and the cone come out past the window frame
        hx, hy = hand_world(keeper_hip, 1.0, kp, -1, SHOPKEEPER)
        cv.drawLine(sx + 40, hy + 6, hx, hy, P(SHOPKEEPER['skin'], stroke=30))
        cv.drawCircle(hx, hy, 15, P(SHOPKEEPER['skin']))
    # Abu Bedr
    stop_x = sx - 100
    if t < s14:
        x = walk_x(t, s13 + 0.1, s14 - 0.1, -120, stop_x)
        pose = walk_pose(gait(x)) if t < s14 - 0.1 else dict(POSE_STAND)
        facing, cone = 1, None
    elif t < s15:
        x, facing = stop_x, 1
        pose = dict(POSE_STAND)
        u = smooth(prog(t, s14 + 0.4, s14 + 0.9))
        back = smooth(prog(t, s14 + 1.2, s14 + 1.8))
        tgt = (lerp(x + 40, counter[0] - 6, u * (1 - back)), lerp(560, counter[1], u * (1 - back)))
        if back > 0:
            tgt = (lerp(counter[0] - 6, x + 80, back), lerp(counter[1], 520, back))
        if u > 0:
            ik = arm_ik((x, STAND_Y), S_ABU, pose, 1, ABU_BEDR, tgt)
            pose['arm_f'] = tuple(lerp(POSE_STAND['arm_f'][i], ik[i], max(u, back)) for i in range(2))
        cone = 'abu' if t > s14 + 1.15 else ('keeper' if hand_out else None)
    else:
        x = walk_x(t, s15 + 0.2, ls(16) - 0.1, stop_x, -260)
        facing = -1
        pose = walk_pose(gait(x)) if t > s15 + 0.2 else dict(POSE_STAND)
        pose['arm_f'] = (55, 120)
        cone = 'abu'
    person(cv, x, STAND_Y, S_ABU, pose, ABU_BEDR, facing=facing)
    if cone == 'abu':
        hx, hy = hand_world((x, STAND_Y), S_ABU, pose, facing, ABU_BEDR)
        draw_cone(cv, hx, hy - 10)
    elif cone == 'keeper':
        hx, hy = hand_world(keeper_hip, 1.0, kp, -1, SHOPKEEPER)
        draw_cone(cv, hx, hy - 10)


# ------------------------------------------------------------------ parts 2 and 3: one picture per line

def qa_state(name, t, t0, t1):
    st = base_state()
    a = st['abu']
    if name in ('READY', 'BOOK_TABLE', 'CONFUSED', 'CONFUSED_ABC', 'FORGETS'):
        a['pose'] = dict(POSE_SIT, lean=0, head=10)
        st['book'] = 'open' if name == 'READY' else 'table'
        st['book_open'] = 1.0
        if name == 'READY':
            st['bubble'] = 1.0
        if name == 'BOOK_TABLE':
            p = dict(POSE_SIT)
            p['arm_f'] = arm_ik(SIT, S_ABU, p, 1, ABU_BEDR, (DESK_BOOK[0] - 40, DESK_BOOK[1] - 4))
            a['pose'] = p
        if name.startswith('CONFUSED') or name == 'FORGETS':
            p = dict(POSE_SIT, lean=-2, head=-12)
            hh = head_world(SIT, S_ABU, p, 1, ABU_BEDR)
            p['arm_f'] = arm_ik(SIT, S_ABU, p, 1, ABU_BEDR, (hh[0] + 4 + 8 * math.sin(t * 9), hh[1] - 52), bend=-1)
            a['pose'] = p
            st['qmark'] = 1.0
            if name == 'CONFUSED_ABC':
                st['bubble'] = 1.0
            if name == 'FORGETS':
                k = smooth(prog(t, t0 + 0.3, max(t0 + 1.0, t1 - 0.3)))
                st['bubble'] = 1 - k
                st['bubble_s'] = lerp(1.0, 0.7, k)
                st['bubble_dy'] = -40 * k
    elif name in ('HOT', 'HOT_WHO', 'HOT_BEDR', 'WANTS'):
        a['pose'] = dict(POSE_SIT, head=-4, lean=-2)
        st['book'] = 'open'
        st['book_open'] = 1.0
        st['door'] = 1.0
        b = dict(x=1480, y=BEDR_Y, pose=dict(POSE_STAND, head=4), facing=-1, a=1.0)
        hh = head_world((b['x'], b['y']), S_BEDR, b['pose'], -1, BEDR)
        b['pose']['arm_f'] = arm_ik((b['x'], b['y']), S_BEDR, b['pose'], -1, BEDR,
                                    (hh[0] - 40 + 14 * math.sin(t * 12), hh[1] + 10), bend=-1)
        st['bedr'] = b
        st['heat'] = 1.0
        if name in ('HOT_WHO', 'HOT_BEDR'):
            st['tags'] = 1.0
            st['tag_focus'] = 'bedr' if name == 'HOT_BEDR' else None
        if name == 'WANTS':
            st['wants'] = 1.0
    elif name in ('HAPPY', 'FATHER'):
        a.update(x=1240, y=STAND_Y, pose=dict(POSE_STAND))
        b = dict(x=1480, y=BEDR_Y - abs(math.sin(t * math.pi * 1.2)) * 14, pose=dict(POSE_STAND, head=4,
                                                                                   arm_b=(-30, -10)), facing=-1, a=1.0)
        b['pose']['arm_f'] = arm_ik((b['x'], b['y']), S_BEDR, b['pose'], -1, BEDR, (1450, b['y'] - 170))
        st['bedr'] = b
        st['cone'] = 'bedr'
        st['glow_bedr'] = 1.0
        st['door'] = 1.0
        st['book'] = 'open'
        st['book_open'] = 1.0
        if name == 'FATHER':
            st['glow_abu'] = 1.0
    # a slow drift keeps still pictures alive
    st['cam'] = (lerp(1.0, 1.035, smooth(prog(t, t0, t1 + 2))), W / 2, H / 2)
    return st


QA_MAP = {'T2': 'READY', 'T3': 'READY'}
for i in range(25, 35):
    QA_MAP[str(i)] = 'READY'
for i in range(35, 46):
    QA_MAP[str(i)] = 'HOT'
QA_MAP.update({'40': 'HOT_WHO', '41': 'HOT_BEDR', '44': 'WANTS', '45': 'WANTS'})
for i in range(46, 57):
    QA_MAP[str(i)] = 'HAPPY'
QA_MAP.update({'55': 'FATHER', '56': 'FATHER'})
for i in range(57, 71):
    QA_MAP[str(i)] = 'CONFUSED'
QA_MAP.update({'66': 'CONFUSED_ABC', '67': 'CONFUSED_ABC', '68': 'FORGETS', '69': 'FORGETS', '70': 'FORGETS'})
QA_MAP.update({'71': 'READY', '72': 'BOOK_TABLE', '73': 'HOT', '74': 'WANTS', '75': 'HAPPY', '76': 'CONFUSED',
               '77': 'FORGETS'})


def line_at(t):
    cur = LINES[0]
    for l in LINES:
        if l['start'] - 0.05 <= t:
            cur = l
        else:
            break
    return cur


def qa_frame(cv, t):
    idx = [i for i, l in enumerate(LINES) if l['start'] - 0.05 <= t]
    i = idx[-1] if idx else 0
    cur = LINES[i]
    name = QA_MAP.get(cur['id'], 'READY')
    span = state_span(i)
    draw_study(cv, t, qa_state(name, t, *span))
    if i > 0 and LINES[i - 1]['id'] in QA_MAP:
        prev = QA_MAP[LINES[i - 1]['id']]
        k = prog(t, cur['start'] - 0.05, cur['start'] + 0.4)
        if prev != name and k < 1:
            # cross-dissolve from the previous picture
            cv.saveLayerAlpha(None, int(255 * (1 - smooth(k))))
            draw_study(cv, t, qa_state(prev, t, *state_span(i - 1)))
            cv.restore()


def state_span(i):
    """Start and end time of the run of lines that share line i's picture."""
    name = QA_MAP.get(LINES[i]['id'])
    a = b = i
    while a > 0 and QA_MAP.get(LINES[a - 1]['id']) == name:
        a -= 1
    while b + 1 < len(LINES) and QA_MAP.get(LINES[b + 1]['id']) == name:
        b += 1
    return LINES[a]['start'], LINES[b]['end']


# ------------------------------------------------------------------ text layers

TARGETS = {'ready': ['مستعدًا', 'مستعدة', 'مستعد'], 'hot': ['بالحر', 'حار'], 'happy': ['سعيدًا', 'سعيدة', 'سعيد'],
           'confused': ['حائرًا', 'حائرة', 'حائر']}
SPEAKER = {'Bedr': ('Bedr', 'بدر'), 'Abu Bedr': ('Abu Bedr', 'أبو بدر')}


def highlights(line):
    en = [w for w in TARGETS if re.search(r'\b%s\b' % w, line['en'], re.I)]
    ar = []
    for w in en:
        for form in TARGETS[w]:
            if form in line['ar']:
                ar.append(form)
                break
    return en, ar


def text_layer(cv, t):
    cur = line_at(t)
    i = LINES.index(cur)
    nxt = LINES[i + 1]['start'] if i + 1 < len(LINES) else cur['end'] + cur['gap']
    if t > nxt - 0.02 or t < cur['start'] - 0.15:
        return
    a = smooth(prog(t, cur['start'] - 0.15, cur['start'] + 0.1)) * (1 - smooth(prog(t, nxt - 0.12, nxt - 0.02)))
    if cur.get('title'):
        cv.drawRect(skia.Rect.MakeWH(W, H), P(E.SURFACE, 0.72 * a))
        cv.drawRect(skia.Rect.MakeXYWH(W / 2 - 16, 370, 32, 32), P(E.GOLD, a))
        E.draw_text(cv, cur['en'], W / 2, 520, 84, E.TEXT, kind='h', alpha=a)
        E.draw_text(cv, cur['ar'], W / 2, 630, 68, E.TEXT_2, kind='h', alpha=a)
        return
    kind = 'q' if cur['role'] == 'Question' else None
    if cur['role'] == 'Answer':
        kind = 'no' if cur['en'].startswith('No') else 'yes' if cur['en'].startswith('Yes') else None
    wait = prog(t, cur['end'], cur['end'] + cur['gap']) if cur['wait'] and t > cur['end'] else None
    hl_en, hl_ar = highlights(cur)
    S.subtitle(cv, cur['en'], cur['ar'], hl_en, hl_ar, a=a, speaker=SPEAKER.get(cur['role']), kind=kind, wait=wait)


def chip_layer(cv, t):
    if t < ls('T2') - 0.3:
        return
    if t < ls('T3') - 0.3:
        S.section_chip(cv, 'Questions', 'الأسئلة', a=smooth(prog(t, ls('T2') - 0.3, ls('T2') + 0.3)))
    elif t < T_WORDS:
        S.section_chip(cv, 'The story again', 'القصة مرة أخرى', a=smooth(prog(t, ls('T3') - 0.3, ls('T3') + 0.3)))


# ------------------------------------------------------------------ compositor

def segments():
    return [
        (0.0, ls(13), lambda cv, t: draw_study(cv, t, part1_state(t))),
        (ls(13), ls(16), street_frame),
        (ls(16), ls('T2'), lambda cv, t: draw_study(cv, t, part1b_state(t))),
        (ls('T2'), T_WORDS, qa_frame),
        (T_WORDS, T_END, lambda cv, t: S.word_card(cv, smooth(prog(t, T_WORDS, T_WORDS + 0.6)))),
        (T_END, DUR + 1, lambda cv, t: S.end_screen(cv, t, T_END + 0.3)),
    ]


def draw_frame(cv, t):
    cv.clear(col(E.SURFACE))
    segs = segments()
    for k, (t0, t1, fn) in enumerate(segs):
        if t0 <= t < t1:
            fn(cv, t)
            if k > 0 and t < t0 + FADE:
                cv.saveLayerAlpha(None, int(255 * (1 - smooth((t - t0) / FADE))))
                segs[k - 1][2](cv, t)
                cv.restore()
            break
    if t < T_WORDS:
        S.watermark(cv)
        chip_layer(cv, t)
        text_layer(cv, t)
    fade = max(1 - prog(t, 0, 0.4), prog(t, DUR - 0.8, DUR))
    if fade > 0:
        cv.drawRect(skia.Rect.MakeWH(W, H), P('#000000', fade))


_surface = None


def render(i):
    global _surface
    if _surface is None:
        _surface = skia.Surface(W, H)
    draw_frame(_surface.getCanvas(), i / FPS)
    return _surface.makeImageSnapshot().toarray().tobytes()


# ------------------------------------------------------------------ sound: narration + light ambience (no music)

def build_audio(out_wav):
    import soundfile as sf
    from scipy import signal
    sr = 48000
    n = int(DUR * sr)
    mix = np.zeros(n)
    rng = np.random.default_rng(2)
    narr, nsr = sf.read(os.path.join(ND, 'narration.wav'))
    narr = signal.resample_poly(narr, sr, nsr)
    mix[:min(n, len(narr))] += narr[:n] * 0.9

    def bp(x, lo, hi):
        return signal.sosfilt(signal.butter(2, [lo, hi], btype='band', fs=sr, output='sos'), x)

    def lp(x, f):
        return signal.sosfilt(signal.butter(2, f, btype='low', fs=sr, output='sos'), x)

    def add(x, t0, g):
        i0 = int(t0 * sr)
        if 0 <= i0 < n:
            x = x[:n - i0]
            mix[i0:i0 + len(x)] += x * g

    def env(dur, a=0.005, d=None):
        m = int(dur * sr)
        e = np.exp(-np.arange(m) / sr * (d or 30))
        e[:int(a * sr)] *= np.linspace(0, 1, int(a * sr))
        return e

    def click(dur=0.03, lo=1200, hi=6000, d=120):
        return bp(rng.standard_normal(int(dur * sr)), lo, hi) * env(dur, 0.001, d)

    def thud(f=110, dur=0.25):
        tt = np.arange(int(dur * sr)) / sr
        return np.sin(2 * np.pi * f * tt) * np.exp(-tt * 18) + 0.4 * lp(rng.standard_normal(len(tt)), 700) * np.exp(-tt * 30)

    def slide(dur=0.5, lo=200, hi=1600):
        m = int(dur * sr)
        return bp(rng.standard_normal(m), lo, hi) * np.sin(np.linspace(0, np.pi, m)) ** 2

    def step():
        return bp(rng.standard_normal(int(0.08 * sr)), 150, 1500) * env(0.08, 0.002, 45)

    def bed(x, t0, t1, g, fade=0.5):
        i0, i1 = int(t0 * sr), min(n, int(t1 * sr))
        seg = np.resize(x, i1 - i0)
        m = min(int(fade * sr), (i1 - i0) // 2)
        seg[:m] *= np.linspace(0, 1, m)
        seg[-m:] *= np.linspace(1, 0, m)
        mix[i0:i1] += seg * g

    room = lp(np.cumsum(rng.standard_normal(sr * 4)) * 0.02, 180)
    room /= np.abs(room).max()
    street = lp(rng.standard_normal(sr * 6), 900)
    street /= np.abs(street).max()
    bed(room, 0, ls(13) + 0.3, 0.025)
    bed(street, ls(13), ls(16) + 0.3, 0.035)
    bed(room, ls(16), T_WORDS, 0.025)
    # study actions
    add(slide(0.5), ls(4) + 0.6, 0.05)
    add(click(0.03, 600, 3000, 90), ls(4) + 1.1, 0.06)
    add(slide(0.3, 1500, 6000), ls(5) + 0.2, 0.03)
    add(thud(130, 0.25), ls(6) + 0.8, 0.10)
    add(slide(0.4), ls(6) + 0.9, 0.04)
    add(slide(0.25, 2000, 8000), ls(7) + 0.1, 0.03)
    t_in = ls(9) + L['9'].get('split', 1.2)
    add(click(0.04, 800, 4000, 60), t_in - 0.15, 0.07)
    for k in range(5):
        add(step(), t_in + 0.25 + k * 0.3, 0.05)
    add(slide(0.4, 100, 600), ls(12), 0.04)
    for k in range(6):
        add(step(), ls(12) + 0.95 + k * 0.32, 0.06)
    for k in range(int((ls(14) - ls(13)) / 0.34)):
        add(step(), ls(13) + 0.15 + k * 0.34, 0.06)
    add(click(0.02, 1500, 7000, 200), ls(14) + 0.9, 0.05)
    for k in range(int((ls(16) - ls(15) - 0.3) / 0.34)):
        add(step(), ls(15) + 0.25 + k * 0.34, 0.06)
    for k in range(5):
        add(step(), ls(19) + 0.1 + k * 0.32, 0.04)
        add(step(), ls(19) + 0.4 + k * 0.36, 0.05)
    add(click(0.04, 800, 4000, 60), ls(19) + 1.9, 0.06)
    add(slide(0.4, 100, 600), ls(19) + 2.2, 0.04)
    add(slide(0.3, 1500, 6000), ls(21) + 0.5, 0.03)
    add(slide(0.6, 2000, 8000) * 0.6, ls(23) + 1.0, 0.03)
    # a soft tick when it is the learner's turn
    for l in LINES:
        if l['wait']:
            add(click(0.015, 2500, 8000, 300), l['end'] + 0.05, 0.035)
    fade = np.minimum(np.clip(np.arange(n) / sr / 0.4, 0, 1), np.clip((DUR - np.arange(n) / sr) / 0.8, 0, 1))
    mix *= fade
    mix /= np.abs(mix).max() + 1e-9
    sf.write(out_wav, (mix * 0.9).astype(np.float32), sr)


def main():
    load(sys.argv[1])
    if sys.argv[2] == '--still':
        for k in range(3, len(sys.argv) - 1, 2):
            s = skia.Surface(W, H)
            draw_frame(s.getCanvas(), float(sys.argv[k]))
            s.makeImageSnapshot().save(sys.argv[k + 1], skia.kPNG)
        return
    out = sys.argv[2]
    tmp = tempfile.mkdtemp()
    video_only = os.path.join(tmp, 'video.mp4')
    wav = os.path.join(tmp, 'sound.wav')
    build_audio(wav)
    nframes = int(DUR * FPS)
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra',
                           '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium',
                           '-crf', '19', '-pix_fmt', 'yuv420p', video_only], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for k, buf in enumerate(pool.imap(render, range(nframes), chunksize=8)):
            ff.stdin.write(buf)
            if k % 600 == 0:
                print(f'frame {k}/{nframes}', flush=True)
    ff.stdin.close()
    ff.wait()
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', video_only, '-i', wav, '-map', '0:v', '-map', '1:a',
                    '-c:v', 'copy', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '48000', '-c:a', 'aac',
                    '-b:a', '192k', '-shortest', '-movflags', '+faststart', out], check=True)
    print('wrote', out)


if __name__ == '__main__':
    main()
