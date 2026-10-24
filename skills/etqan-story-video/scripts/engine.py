"""Etqan story-video engine: characters, the study room, props, subtitles, compositing, sound, rendering.

A story module (see examples/abu-bedr-ice-cream/story.py) supplies the choreography:
    TARGETS, SPEAKER, QA_MAP, qa_state(name, t, t0, t1), segments(), sound(A)

    python3 engine.py NARRATION_DIR STORY.py OUT.mp4              # full video with sound
    python3 engine.py NARRATION_DIR STORY.py --still T OUT.png ... # single frames, for checking
    python3 engine.py NARRATION_DIR STORY.py --test OUT.mp4        # first 20 seconds only

NARRATION_DIR is what voice.py wrote (timeline.json, narration.wav).
"""
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from multiprocessing import Pool

import numpy as np
import skia

import etqan as E
import scenes as S
from render_lib import (ABU_BEDR, BEDR, FPS, H, P, W, clamp, col, glow, lerp, prog, rrect,  # noqa: F401
                        shade, smooth, person)

STORY = None   # the loaded story module
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



# ------------------------------------------------------------------ parts 2 and 3: one picture per line

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
    name = STORY.QA_MAP.get(cur['id'], 'READY')
    span = state_span(i)
    draw_study(cv, t, STORY.qa_state(name, t, *span))
    if i > 0 and LINES[i - 1]['id'] in STORY.QA_MAP:
        prev = STORY.QA_MAP[LINES[i - 1]['id']]
        k = prog(t, cur['start'] - 0.05, cur['start'] + 0.4)
        if prev != name and k < 1:
            # cross-dissolve from the previous picture
            cv.saveLayerAlpha(None, int(255 * (1 - smooth(k))))
            draw_study(cv, t, STORY.qa_state(prev, t, *state_span(i - 1)))
            cv.restore()


def state_span(i):
    """Start and end time of the run of lines that share line i's picture."""
    name = STORY.QA_MAP.get(LINES[i]['id'])
    a = b = i
    while a > 0 and STORY.QA_MAP.get(LINES[a - 1]['id']) == name:
        a -= 1
    while b + 1 < len(LINES) and STORY.QA_MAP.get(LINES[b + 1]['id']) == name:
        b += 1
    return LINES[a]['start'], LINES[b]['end']



# ------------------------------------------------------------------ text layers

def highlights(line):
    en = [w for w in STORY.TARGETS if re.search(r'\b%s\b' % w, line['en'], re.I)]
    ar = []
    for w in en:
        for form in STORY.TARGETS[w]:
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
    S.subtitle(cv, cur['en'], cur['ar'], hl_en, hl_ar, a=a, speaker=STORY.SPEAKER.get(cur['role']), kind=kind, wait=wait)


def chip_layer(cv, t):
    if t < ls('T2') - 0.3:
        return
    if t < ls('T3') - 0.3:
        S.section_chip(cv, 'Questions', 'الأسئلة', a=smooth(prog(t, ls('T2') - 0.3, ls('T2') + 0.3)))
    elif t < T_WORDS:
        S.section_chip(cv, 'The story again', 'القصة مرة أخرى', a=smooth(prog(t, ls('T3') - 0.3, ls('T3') + 0.3)))



# ------------------------------------------------------------------ compositor

def draw_frame(cv, t):
    cv.clear(col(E.SURFACE))
    segs = STORY.segments()
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

class _Audio:
    """Helpers handed to STORY.sound(A): A.add(sound, t0, gain), A.bed(loop, t0, t1, gain), and the
    sound makers A.click/A.thud/A.slide/A.step plus two loops A.room and A.street. Noise-based only:
    no tones, chimes or music (Essam treats any melody as music)."""

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
    A = _Audio()
    A.add, A.bed, A.click, A.thud, A.slide, A.step, A.room, A.street = add, bed, click, thud, slide, step, room, street
    STORY.sound(A)
    # a soft tick when it is the learner's turn
    for l in LINES:
        if l['wait']:
            add(click(0.015, 2500, 8000, 300), l['end'] + 0.05, 0.035)
    fade = np.minimum(np.clip(np.arange(n) / sr / 0.4, 0, 1), np.clip((DUR - np.arange(n) / sr) / 0.8, 0, 1))
    mix *= fade
    mix /= np.abs(mix).max() + 1e-9
    sf.write(out_wav, (mix * 0.9).astype(np.float32), sr)


def load_story(path):
    global STORY
    # the story does `import engine`; make that the module already running, not a fresh copy
    sys.modules.setdefault('engine', sys.modules[__name__])
    spec = importlib.util.spec_from_file_location('story', os.path.abspath(path))
    STORY = importlib.util.module_from_spec(spec)
    sys.modules['story'] = STORY
    spec.loader.exec_module(STORY)


def main():
    load(sys.argv[1])
    load_story(sys.argv[2])
    if sys.argv[3] == '--still':
        for k in range(4, len(sys.argv) - 1, 2):
            s = skia.Surface(W, H)
            draw_frame(s.getCanvas(), float(sys.argv[k]))
            s.makeImageSnapshot().save(sys.argv[k + 1], skia.kPNG)
        return
    test = sys.argv[3] == '--test'
    out = sys.argv[4] if test else sys.argv[3]
    tmp = tempfile.mkdtemp()
    video_only = os.path.join(tmp, 'video.mp4')
    wav = os.path.join(tmp, 'sound.wav')
    build_audio(wav)
    nframes = int((min(DUR, 20.0) if test else DUR) * FPS)
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
