"""Ambient sound design for the animation (no music). Writes a 48 kHz stereo WAV.

    python3 audio.py out.wav
"""
import math
import random
import sys
import wave

import numpy as np
from scipy import signal

import render as R

SR = 48000
N = int(R.DUR * SR)
rng = np.random.default_rng(3)
L = np.zeros(N)
Rt = np.zeros(N)


def tt(n):
    return np.arange(n) / SR


def bandpass(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype='band', fs=SR, output='sos')
    return signal.sosfilt(sos, x)


def lowpass(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, btype='low', fs=SR, output='sos'), x)


def highpass(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, btype='high', fs=SR, output='sos'), x)


def pink(n):
    w = rng.standard_normal(n)
    f = np.fft.rfft(w)
    k = np.arange(len(f))
    k[0] = 1
    f /= np.sqrt(k)
    x = np.fft.irfft(f, n)
    return x / (np.abs(x).max() + 1e-9)


def brown(n):
    x = np.cumsum(rng.standard_normal(n))
    x = highpass(x, 20)
    return x / (np.abs(x).max() + 1e-9)


def add(sig, t0, gain=1.0, pan=0.0):
    """pan: -1 left .. +1 right (equal power)."""
    i0 = int(t0 * SR)
    if i0 >= N:
        return
    if i0 < 0:
        sig = sig[-i0:]
        i0 = 0
    sig = sig[:N - i0]
    a = (pan + 1) * math.pi / 4
    L[i0:i0 + len(sig)] += sig * gain * math.cos(a)
    Rt[i0:i0 + len(sig)] += sig * gain * math.sin(a)


def env_track(t0, t1, fade_in=0.4, fade_out=0.4):
    """Full-length gain curve that is 1 between t0 and t1 with smooth fades."""
    t = tt(N)
    up = np.clip((t - t0) / fade_in, 0, 1)
    dn = np.clip((t1 - t) / fade_out, 0, 1)
    e = np.minimum(up, dn)
    return e * e * (3 - 2 * e)


def bed(sig, t0, t1, gain, fade_in=0.4, fade_out=0.4, pan=0.0):
    e = env_track(t0, t1, fade_in, fade_out)
    s = np.resize(sig, N) * e
    add(s, 0, gain, pan)


# ------------------------------------------------------------ sound atoms

def click(dur=0.012, lo=1800, hi=6000, decay=200):
    n = int(dur * SR)
    x = bandpass(rng.standard_normal(n), lo, hi) * np.exp(-tt(n) * decay)
    return x / (np.abs(x).max() + 1e-9)


def thud(f=80, dur=0.35, decay=12, noise=0.4):
    n = int(dur * SR)
    t = tt(n)
    x = np.sin(2 * np.pi * f * t * (1 - 0.3 * t)) * np.exp(-t * decay)
    x += noise * lowpass(rng.standard_normal(n), 600) * np.exp(-t * decay * 2)
    return x / (np.abs(x).max() + 1e-9)


def whoosh(dur=0.7, lo=300, hi=3000, peak=0.5):
    n = int(dur * SR)
    t = tt(n) / dur
    e = np.exp(-((t - peak) ** 2) / 0.04)
    x = bandpass(rng.standard_normal(n), lo, hi) * e
    return x / (np.abs(x).max() + 1e-9)


def chime(freqs, dur=2.5, decay=2.2, bright=1.0):
    n = int(dur * SR)
    t = tt(n)
    x = np.zeros(n)
    for i, f in enumerate(freqs):
        for h, ha in ((1, 1.0), (2.76, 0.35 * bright), (5.4, 0.12 * bright)):
            x += ha / (i + 1) ** 0.3 * np.sin(2 * np.pi * f * h * t + i) * np.exp(-t * decay * (1 + 0.6 * (h - 1)))
    x *= np.minimum(1, t / 0.006)
    return x / (np.abs(x).max() + 1e-9)


def ping(f, dur=0.35, decay=14):
    n = int(dur * SR)
    t = tt(n)
    x = np.sin(2 * np.pi * f * t) * np.exp(-t * decay) * np.minimum(1, t / 0.003)
    return x


def footstep():
    n = int(0.09 * SR)
    t = tt(n)
    x = bandpass(rng.standard_normal(n), 120, 1400) * np.exp(-t * 55)
    x += 0.6 * np.sin(2 * np.pi * 90 * t) * np.exp(-t * 40)
    return x / (np.abs(x).max() + 1e-9)


def keys_jingle(dur=0.5):
    n = int(dur * SR)
    x = np.zeros(n)
    for _ in range(9):
        i0 = int(rng.uniform(0, dur * 0.7) * SR)
        m = n - i0
        t = tt(m)
        hit = np.zeros(m)
        for f in rng.uniform(3200, 8500, 4):
            hit += np.sin(2 * np.pi * f * t) * np.exp(-t * rng.uniform(25, 60))
        x[i0:] += hit * rng.uniform(0.4, 1.0)
    return x / (np.abs(x).max() + 1e-9)


def engine(n, f0, rough=0.25):
    """f0 may be an array (Hz) of length n."""
    f0 = np.broadcast_to(f0, (n,)).astype(float)
    jitter = 1 + 0.015 * lowpass(rng.standard_normal(n), 3)
    ph = 2 * np.pi * np.cumsum(f0 * jitter) / SR
    x = np.sin(ph) + 0.5 * np.sin(2 * ph + 0.3) + 0.3 * np.sin(3 * ph + 1.1) + 0.15 * np.sin(4 * ph)
    x *= 1 + rough * lowpass(rng.standard_normal(n), 40)
    x = lowpass(x, 260)
    return x / (np.abs(x).max() + 1e-9)


def crickets(n):
    t = tt(n)
    x = np.zeros(n)
    for f, rate, ph in ((4300, 2.1, 0.0), (4700, 2.6, 1.3), (3900, 1.7, 2.1)):
        chirp = (np.sin(2 * np.pi * rate * t + ph) > 0.55).astype(float)
        chirp = lowpass(chirp, 30)
        trill = 0.5 + 0.5 * np.sin(2 * np.pi * 38 * t)
        x += np.sin(2 * np.pi * f * t) * chirp * trill
    return x / (np.abs(x).max() + 1e-9)


def babble(dur, seed=1):
    """Muffled, wordless speech-like murmur coming out of a small phone speaker."""
    r = random.Random(seed)
    n = int(dur * SR)
    t = tt(n)
    pitch = 165 + 25 * np.sin(2 * np.pi * 0.35 * t) + 12 * np.sin(2 * np.pi * 1.3 * t)
    ph = 2 * np.pi * np.cumsum(pitch) / SR
    src = signal.sawtooth(ph) + 0.05 * rng.standard_normal(n)
    vowels = [(730, 1090), (270, 2290), (300, 870), (530, 1840), (570, 840)]
    out = np.zeros(n)
    pos = 0.0
    while pos < dur:
        syl = r.uniform(0.11, 0.2)
        gap = r.uniform(0.02, 0.06) if r.random() > 0.15 else r.uniform(0.25, 0.45)
        i0, i1 = int(pos * SR), min(n, int((pos + syl) * SR))
        if i1 > i0 + 64:
            f1, f2 = r.choice(vowels)
            seg = src[i0:i1]
            v = bandpass(seg, f1 * 0.8, f1 * 1.25) + 0.6 * bandpass(seg, f2 * 0.85, f2 * 1.18)
            e = np.sin(np.linspace(0, np.pi, i1 - i0)) ** 0.8
            out[i0:i1] += v * e * r.uniform(0.6, 1.0)
        pos += syl + gap
    out = bandpass(out, 350, 3200)
    return out / (np.abs(out).max() + 1e-9)


# ------------------------------------------------------------ scene beds

def build():
    T = tt(N)

    # city night (exterior office) + office room tone
    bed(lowpass(pink(N), 700), 0.0, 2.9, 0.10, fade_in=0.6, fade_out=0.5)
    bed(lowpass(brown(N), 250), 2.4, 7.0, 0.10, fade_in=0.5, fade_out=0.5)
    hum = np.sin(2 * np.pi * 60 * T) * 0.5 + np.sin(2 * np.pi * 120 * T) * 0.2
    bed(hum, 2.4, 7.0, 0.012)
    for s in range(3, 7):
        add(click(0.01, 2500, 7000, 400), s + 0.0, 0.06, pan=0.45)
    t = 2.6
    kr = random.Random(4)
    while t < 5.0:
        add(click(0.02, 1200, 5000, 180), t, kr.uniform(0.05, 0.09), pan=0.25)
        t += kr.uniform(0.07, 0.17) if kr.random() > 0.12 else kr.uniform(0.3, 0.45)
    add(whoosh(0.6, 200, 900, 0.5), 5.05, 0.05)  # stretch / chair creak-ish rustle
    add(thud(140, 0.25, 22, 0.6), 6.35, 0.06)  # arms drop

    # driving exterior: engine + road + lamp whooshes
    n = N
    eng = engine(n, 42 + 3 * np.sin(2 * np.pi * 0.2 * T))
    road = bandpass(pink(n), 80, 1400)
    bed(eng, 6.5, 11.4, 0.045, fade_in=0.7)
    bed(road, 6.5, 11.4, 0.05, fade_in=0.7)
    # lamp passes (same maths as drive_ext)
    sp, last = 640, None
    for k in range(int(6.5 * 200), int(11.6 * 200)):
        tk = k / 200
        ox = 980 * (tk - 6.5)
        near = min(abs(i * sp - (ox * 0.95 % sp) + 120 + 98 - 470) for i in range(-1, 4))
        if near < 6 and (last is None or tk - last > 0.3):
            add(whoosh(0.8, 400, 2600, 0.5), tk - 0.4, 0.07, pan=0.0)
            last = tk

    # car interior: muffled engine + road, lamp sweeps, phone audio murmur
    eng_in = engine(n, 40 + 2 * np.sin(2 * np.pi * 0.13 * T), rough=0.15)
    road_in = lowpass(pink(n), 420)
    bed(eng_in, 11.0, 27.6, 0.035, fade_in=0.6, fade_out=0.6)
    bed(road_in, 11.0, 27.6, 0.035, fade_in=0.6, fade_out=0.6)
    last = None
    for k in range(int(11.0 * 200), int(27.6 * 200)):
        tk = k / 200
        ox = 1150 * (tk - 11.0)
        near = min(abs(i * 760 - (ox % 760) + 200 - 420) for i in range(-1, 4))
        if near < 7 and (last is None or tk - last > 0.3):
            add(lowpass(whoosh(0.9, 300, 1800, 0.5), 1200), tk - 0.45, 0.05, pan=-0.4)
            last = tk
    bab = babble(10.2, seed=2)
    e = np.ones(len(bab))
    e[:int(0.5 * SR)] = np.linspace(0, 1, int(0.5 * SR))
    e[-int(0.5 * SR):] = np.linspace(1, 0, int(0.5 * SR))
    add(bab * e, 11.2, 0.035, pan=0.5)
    # aha moment
    add(whoosh(0.9, 500, 6000, 0.95), R.GATHER_T - 0.85, 0.08)
    add(thud(55, 1.2, 3.5, 0.2), R.GATHER_T, 0.22)
    add(chime([659.3, 830.6, 987.8, 1318.5], 3.5, 1.3), R.GATHER_T, 0.10, pan=-0.1)
    add(chime([493.9, 659.3, 987.8], 3.0, 1.5, 0.6), 22.6, 0.07, pan=0.1)
    for i in range(9):
        add(ping(1600 + i * 110, 0.25, 22), R.GATHER_T + 0.15 + i * 0.05, 0.015, pan=-0.8 + i * 0.2)

    # home exterior: crickets, car slows + stops, door, steps, keys, house door
    cr = crickets(N)
    bed(cr, 27.0, 33.0, 0.035, fade_in=1.0, fade_out=0.8)
    bed(lowpass(pink(N), 500), 27.0, 33.0, 0.06, fade_in=0.8, fade_out=0.6)
    seg = int(2.6 * SR)
    f = np.interp(tt(seg), [0, 2.0, 2.6], [44, 30, 26])
    stop_eng = engine(seg, f) * np.interp(tt(seg), [0, 0.3, 2.2, 2.6], [0, 1, 0.8, 0])
    add(stop_eng, 27.0, 0.05, pan=-0.3)
    add(lowpass(pink(int(2.0 * SR)), 300) * np.interp(tt(int(2.0 * SR)), [0, 0.3, 2.0], [0, 1, 0]), 27.0, 0.035)
    add(click(0.03, 600, 3000, 90), 29.35, 0.10, pan=-0.3)   # engine off / key
    add(click(0.04, 800, 4000, 70), 29.55, 0.12, pan=-0.2)   # door handle
    add(thud(95, 0.4, 14, 0.7), 29.82, 0.22, pan=-0.2)       # car door shut
    for k in range(5):
        add(footstep(), 29.85 + k * (math.pi / 13), 0.10, pan=-0.2 + k * 0.12)
    add(keys_jingle(0.45), 30.55, 0.06, pan=0.4)
    add(click(0.03, 900, 5000, 120), 30.78, 0.10, pan=0.45)  # lock / latch
    add(whoosh(0.5, 200, 1200, 0.4), 30.8, 0.04, pan=0.45)
    add(thud(85, 0.45, 12, 0.6), 31.6, 0.22, pan=0.45)       # house door shut

    # living room + phone
    bed(lowpass(brown(N), 200), 31.8, 41.2, 0.06, fade_in=0.6)
    bed(lowpass(brown(N), 200), 40.6, 45.8, 0.06, fade_in=0.4, fade_out=0.6)
    add(whoosh(0.5, 300, 1500, 0.5), 32.45, 0.04)  # pulling out the phone
    for k in range(9):
        add(click(0.008, 2500, 9000, 600), 34.7 + k * 0.17, 0.08, pan=0.05)
    add(click(0.008, 2500, 9000, 600), 36.25, 0.08)
    add(click(0.012, 1500, 6000, 350), 36.6, 0.11)
    add(whoosh(0.45, 600, 4000, 0.6), 37.2, 0.05)
    up = np.sin(2 * np.pi * np.cumsum(np.linspace(700, 1250, int(0.12 * SR))) / SR) * np.exp(-tt(int(0.12 * SR)) * 22)
    add(up, 38.9, 0.10)
    add(chime([1046.5, 1318.5, 1568.0], 1.6, 3.0, 0.5), 39.0, 0.05)

    # celebrate
    add(whoosh(0.5, 200, 1200, 0.5), 40.95, 0.06)
    add(thud(70, 0.4, 14, 0.5), 41.95, 0.16)
    add(thud(70, 0.4, 14, 0.5), 42.6, 0.12)
    sr_ = random.Random(9)
    for i in range(16):
        add(ping(sr_.uniform(2200, 4200), 0.4, 10), 41.2 + sr_.uniform(0, 1.6), 0.018, pan=sr_.uniform(-0.7, 0.7))
    add(chime([523.3, 659.3, 784.0, 1046.5], 3.5, 1.2, 0.7), 41.3, 0.06)

    # end card
    bed(cr, 44.8, R.DUR, 0.025, fade_in=1.0, fade_out=1.2)
    add(chime([440.0, 554.4, 659.3, 880.0], 3.2, 1.1, 0.6), 45.3, 0.05)
    seg = int(3.1 * SR)
    pas = lowpass(pink(seg), 900) * np.interp(tt(seg), [0, 1.5, 3.1], [0, 1, 0])
    add(pas, 45.4, 0.05, pan=0.0)

    # master: gentle fades
    fade = np.minimum(np.clip(T / 0.6, 0, 1), np.clip((R.DUR - T) / 0.9, 0, 1))
    return np.stack([L * fade, Rt * fade], axis=1)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'ambience.wav'
    x = build()
    x = x / (np.abs(x).max() + 1e-9) * 0.89
    pcm = (x * 32767).astype(np.int16)
    with wave.open(out, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == '__main__':
    main()
