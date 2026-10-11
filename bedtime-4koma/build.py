#!/usr/bin/env python3
"""Voice the bedtime 4コマ strips with VOICEVOX and embed the clips in the page.

Reads the strip lines from page.src.html, picks a voice per speaker, synthesizes
every line at two speeds with voicevox_core, levels loudness with ffmpeg, and
writes index.html with the MP3s embedded as data: URIs.

    VV_HOME=/home/user/vv VV_MODELS=/home/user/voicevox/voicevox_vvm/vvms \
        /home/user/vv/venv/bin/python build.py

Run setup_voicevox.sh first.
"""

import base64
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile

HERE = Path(__file__).resolve().parent
VV_HOME = Path(os.environ.get("VV_HOME", "/home/user/vv"))
VV_MODELS = Path(os.environ.get("VV_MODELS", "/home/user/voicevox/voicevox_vvm/vvms"))
ORT_LIB = VV_HOME / "ort/voicevox_onnxruntime-linux-x64-1.23.2/lib/libvoicevox_onnxruntime.so.1.23.2"
DICT_DIR = VV_HOME / "dict/open_jtalk_dic_utf_8-1.11"
CACHE = VV_HOME / "clip-cache"

# Style IDs and the .vvm file each lives in (from the voicevox_vvm README table).
VOICES = {
    "narrator": {"style": 52, "vvm": "12.vvm", "name": "雀松朱司"},
    "父": {"style": 13, "vvm": "15.vvm", "name": "青山龍星"},
    "息子": {"style": 12, "vvm": "9.vvm", "name": "白上虎太郎"},
    "タマ": {"style": 42, "vvm": "10.vvm", "name": "ちび式じい"},
    "じいちゃん": {"style": 42, "vvm": "10.vvm", "name": "ちび式じい"},
}
# A line containing the key uses this style instead (same character, other mood).
STYLE_OVERRIDES = {
    "ハハハ": 83,  # 青山龍星 喜び
}
STYLE_VVM = {v["style"]: v["vvm"] for v in VOICES.values()} | {83: "15.vvm"}
# Spoken text fixes where Open JTalk misreads the written form.
READINGS = {
    "ザーザー降り": "ザーザーぶり",
    "八十？": "はちじゅう？",
    "二十歳": "はたち",
    "開いている": "あいている",
}
SPEEDS = {"n": 1.0, "s": 0.8}  # ふつう / ゆっくり
VVM_VERSION_TAG = (VV_MODELS.parent / "env.json").read_text()

SPEAKER_RE = re.compile(r"^(.*?)(" + "|".join(k for k in VOICES if k != "narrator") + r")「(.*)」$")


def parse_strips(src: str):
    """Return strips -> panels -> list of raw HTML line strings, as written in the page."""
    block = src.split("/* STRIPS-START */", 1)[1].split("/* STRIPS-END */", 1)[0]
    strips = []
    for chunk in re.split(r"\btitle:\s*\"", block)[1:]:
        panels = []
        for m in re.finditer(r"lines:\[(.*?)\]\s*\}", chunk, re.S):
            panels.append([s.replace("\\'", "'") for s in re.findall(r"'((?:[^'\\]|\\.)*)'", m.group(1))])
        strips.append(panels)
    return strips


def segments(line_html: str):
    """Split one displayed line into (speaker, text) pieces in speaking order."""
    text = re.sub(r"<[^>]+>", "", line_html).strip()
    m = SPEAKER_RE.match(text)
    if not m:
        return [("narrator", text)]
    out = []
    if m.group(1).strip():
        out.append(("narrator", m.group(1).strip()))
    out.append((m.group(2), m.group(3)))
    return out


def spoken(text: str) -> str:
    for a, b in READINGS.items():
        text = text.replace(a, b)
    return text


def style_for(speaker: str, text: str) -> int:
    for key, sid in STYLE_OVERRIDES.items():
        if key in text and speaker != "narrator":
            return sid
    return VOICES[speaker]["style"]


def to_mp3(wav: bytes) -> bytes:
    """Level to about -19 LUFS (two-pass loudnorm) and encode mono 24 kHz MP3."""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td, "in.wav")
        dst = Path(td, "out.mp3")
        src.write_bytes(wav)
        target = "I=-19:TP=-2:LRA=11"
        probe = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-af", f"loudnorm={target}:print_format=json", "-f", "null", "-"],
            capture_output=True, text=True, check=True,
        ).stderr
        meas = json.loads(probe[probe.rindex("{"):probe.rindex("}") + 1])
        af = f"loudnorm={target}:linear=true"
        if meas["input_i"] not in ("-inf", "inf"):
            af += (f":measured_I={meas['input_i']}:measured_TP={meas['input_tp']}"
                   f":measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}"
                   f":offset={meas['target_offset']}")
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-af", af,
             "-ac", "1", "-ar", "24000", "-c:a", "libmp3lame", "-b:a", "48k", str(dst)],
            check=True,
        )
        return dst.read_bytes()


def main():
    src = (HERE / "page.src.html").read_text(encoding="utf-8")
    strips = parse_strips(src)
    CACHE.mkdir(parents=True, exist_ok=True)

    syn = None
    loaded = set()

    def synth(text: str, style: int, speed: float) -> bytes:
        nonlocal syn
        key = hashlib.sha256(f"{VVM_VERSION_TAG}|{style}|{speed}|{text}".encode()).hexdigest()[:24]
        cached = CACHE / f"{key}.mp3"
        if cached.exists():
            return cached.read_bytes()
        if syn is None:
            ort = Onnxruntime.load_once(filename=str(ORT_LIB))
            syn = Synthesizer(ort, OpenJtalk(str(DICT_DIR)), cpu_num_threads=max(os.cpu_count() or 2, 2))
        vvm = STYLE_VVM[style]
        if vvm not in loaded:
            with VoiceModelFile.open(VV_MODELS / vvm) as m:
                syn.load_voice_model(m)
            loaded.add(vvm)
        q = syn.create_audio_query(text, style)
        q.speed_scale = speed
        mp3 = to_mp3(syn.synthesis(q, style))
        cached.write_bytes(mp3)
        return mp3

    used = []
    clips = []
    report = []
    for si, panels in enumerate(strips):
        sc = []
        for pi, lines in enumerate(panels):
            pc = []
            for li, line in enumerate(lines):
                segs = segments(line)
                if len(segs) != 1:
                    raise SystemExit(f"strip {si+1} panel {pi+1}: split lines into separate entries: {line}")
                speaker, text = segs[0]
                style = style_for(speaker, text)
                name = VOICES[speaker]["name"]
                if name not in used:
                    used.append(name)
                entry = {}
                for sp, scale in SPEEDS.items():
                    entry[sp] = "data:audio/mpeg;base64," + base64.b64encode(synth(spoken(text), style, scale)).decode()
                pc.append(entry)
                report.append(f"{si+1}-{pi+1}-{li+1}  {speaker:<8} {name}({style})  {spoken(text)}")
            sc.append(pc)
        clips.append(sc)

    voice = {"credit": [f"VOICEVOX:{n}" for n in used], "clips": clips}
    out = re.sub(r"/\*VOICE-START\*/.*?/\*VOICE-END\*/",
                 lambda _: "/*VOICE-START*/" + json.dumps(voice, ensure_ascii=False, separators=(",", ":")) + "/*VOICE-END*/",
                 src, count=1, flags=re.S)
    (HERE / "index.html").write_text(out, encoding="utf-8")
    print("\n".join(report))
    print(f"\ncredit: {'、'.join(voice['credit'])}")
    print(f"index.html: {len(out.encode()) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
