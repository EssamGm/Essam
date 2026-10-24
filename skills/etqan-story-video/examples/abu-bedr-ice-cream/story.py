"""Story module: "Abu Bedr and the Ice Cream" — the worked example for the Etqan story-video engine.

Copy this file for a new story and rewrite the choreography. Everything here reads the narration
timeline through G.ls(id) / G.le(id) / G.lg(id) (start, end, end + gap of a transcript line), so the
animation always follows the voices.
"""
import math
import random

import skia

import engine as G
import etqan as E
import scenes as S
from engine import (DESK_BOOK, POSE_SIT, POSE_SIT_RELAX, POSE_STAND, S_ABU, S_BEDR, SIT, STAND_Y, BEDR_Y,
                    arm_ik, base_state, draw_cone, draw_study, gait, hand_world, head_world, walk_x)
from render_lib import ABU_BEDR, BEDR, P, W, H, col, glow, lerp, pose_mix, prog, rrect, shade, smooth, person, walk_pose

ls, le, lg = G.ls, G.le, G.lg

# words highlighted in gold, with the Arabic forms to look for
TARGETS = {'ready': ['مستعدًا', 'مستعدة', 'مستعد'], 'hot': ['بالحر', 'حار'], 'happy': ['سعيدًا', 'سعيدة', 'سعيد'],
           'confused': ['حائرًا', 'حائرة', 'حائر']}
# the word card at the end: (English, Arabic)
WORDS = [('ready', 'مستعد'), ('hot', 'يشعر بالحر'), ('happy', 'سعيد'), ('confused', 'حائر')]
# roles that get a name tag over the subtitle when they speak
SPEAKER = {'Bedr': ('Bedr', 'بدر'), 'Abu Bedr': ('Abu Bedr', 'أبو بدر')}

# ---- voice settings, read by voice.py --story (plain literals only)
VOICE_ROLES = {'Bedr': 'BOY'}          # Abu Bedr, Narrator, Question, Answer, Guide are built in
PAUSE_AFTER = {'But wait!': 0.9}
SPOKEN_REPLACE = [('Oh, Abu Bedr', 'Oh... Abu Bedr')]   # a sigh, not a quick "oh"
# extra seconds after story lines so each action has time to play
EXTRA_GAP = {'3': 0.3, '4': 0.6, '5': 0.6, '6': 0.7, '9': 0.9, '11': 0.3, '12': 1.2, '13': 1.6, '14': 1.2,
             '15': 1.4, '16': 0.9, '17': 0.4, '19': 1.8, '20': 0.7, '21': 0.7, '22': 0.4, '23': 0.7, '24': 0.9}

SHOPKEEPER = dict(skin='#B97E58', hair='#2A2026', top='#E9ECF1', pants='#2A3F5C', shoe='#2A2A2A',
                  beard=False, sleeve=0.55, leg=1.0, torso=1.0, head=1.0)

# ------------------------------------------------------------------ part 1 choreography

def bedr_entry(t, st):
    """Bedr comes in through the door at line 9 (after 'But wait!')."""
    t_in = ls(9) + G.L['9'].get('split', 1.2)
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




# ------------------------------------------------------------------ the running order

def segments():
    """(start, end, draw) pieces; neighbours cross-dissolve over engine.FADE seconds."""
    return [
        (0.0, ls(13), lambda cv, t: draw_study(cv, t, part1_state(t))),
        (ls(13), ls(16), street_frame),
        (ls(16), ls('T2'), lambda cv, t: draw_study(cv, t, part1b_state(t))),
        (ls('T2'), G.T_WORDS, G.qa_frame),
        (G.T_WORDS, G.T_END, lambda cv, t: S.word_card(cv, smooth(prog(t, G.T_WORDS, G.T_WORDS + 0.6)), WORDS)),
        (G.T_END, G.DUR + 1, lambda cv, t: S.end_screen(cv, t, G.T_END + 0.3)),
    ]


# ------------------------------------------------------------------ sound cues (noise-based, no music)

def sound(A):

    A.bed(A.room, 0, ls(13) + 0.3, 0.025)
    A.bed(A.street, ls(13), ls(16) + 0.3, 0.035)
    A.bed(A.room, ls(16), G.T_WORDS, 0.025)
    # study actions
    A.add(A.slide(0.5), ls(4) + 0.6, 0.05)
    A.add(A.click(0.03, 600, 3000, 90), ls(4) + 1.1, 0.06)
    A.add(A.slide(0.3, 1500, 6000), ls(5) + 0.2, 0.03)
    A.add(A.thud(130, 0.25), ls(6) + 0.8, 0.10)
    A.add(A.slide(0.4), ls(6) + 0.9, 0.04)
    A.add(A.slide(0.25, 2000, 8000), ls(7) + 0.1, 0.03)
    t_in = ls(9) + G.L['9'].get('split', 1.2)
    A.add(A.click(0.04, 800, 4000, 60), t_in - 0.15, 0.07)
    for k in range(5):
        A.add(A.step(), t_in + 0.25 + k * 0.3, 0.05)
    A.add(A.slide(0.4, 100, 600), ls(12), 0.04)
    for k in range(6):
        A.add(A.step(), ls(12) + 0.95 + k * 0.32, 0.06)
    for k in range(int((ls(14) - ls(13)) / 0.34)):
        A.add(A.step(), ls(13) + 0.15 + k * 0.34, 0.06)
    A.add(A.click(0.02, 1500, 7000, 200), ls(14) + 0.9, 0.05)
    for k in range(int((ls(16) - ls(15) - 0.3) / 0.34)):
        A.add(A.step(), ls(15) + 0.25 + k * 0.34, 0.06)
    for k in range(5):
        A.add(A.step(), ls(19) + 0.1 + k * 0.32, 0.04)
        A.add(A.step(), ls(19) + 0.4 + k * 0.36, 0.05)
    A.add(A.click(0.04, 800, 4000, 60), ls(19) + 1.9, 0.06)
    A.add(A.slide(0.4, 100, 600), ls(19) + 2.2, 0.04)
    A.add(A.slide(0.3, 1500, 6000), ls(21) + 0.5, 0.03)
    A.add(A.slide(0.6, 2000, 8000) * 0.6, ls(23) + 1.0, 0.03)
