"""Build every spoken line from transcript.md with the offline Kokoro voices, plus a timeline.

    python3 voice.py MODEL_DIR OUT_DIR

Writes OUT_DIR/lines/NN.wav, OUT_DIR/narration.wav and OUT_DIR/timeline.json.
All voices are male (Essam's request): narrator/answers UK male, questions a second UK
male, Abu Bedr US male, Bedr a US male voice raised tape-style to sound like a boy.
"""
import json
import os
import re
import sys

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 24000

VOICES = {  # role -> (kokoro voice, language, speed, boy pitch factor)
    'Narrator': ('bm_george', 'en-gb', 0.88, None),
    'Answer': ('bm_george', 'en-gb', 0.88, None),
    'Question': ('bm_lewis', 'en-gb', 0.88, None),
    'Abu Bedr': ('am_michael', 'en-us', 0.85, None),
    'Bedr': ('am_echo', 'en-us', 0.95, 1.25),
}

# silence after each line, by what comes next
GAP_LINE = 0.75        # between story lines
GAP_ANSWER_WAIT = 2.0  # the learner answers out loud
GAP_AFTER_ANSWER = 1.0
GAP_SECTION = 1.6

# spoken cues that are not table rows in the transcript
TITLE_QA = ('Narrator', 'Now, answer the questions!', 'الآن، أجب عن الأسئلة!')
TITLE_RETELL = ('Narrator', 'Listen to the story again.', 'استمع إلى القصة مرة أخرى.')


def load_lines():
    rows = []
    part = 0
    for raw in open(os.path.join(HERE, 'transcript.md'), encoding='utf-8'):
        if raw.startswith('## Part'):
            part = int(raw.split()[2])
            if part == 2:
                rows.append(dict(id='T2', part=2, role=TITLE_QA[0], en=TITLE_QA[1], ar=TITLE_QA[2], title=True,
                                 wait=False, visual='', bold_en=[], bold_ar=[]))
            if part == 3:
                rows.append(dict(id='T3', part=3, role=TITLE_RETELL[0], en=TITLE_RETELL[1], ar=TITLE_RETELL[2],
                                 title=True, wait=False, visual='', bold_en=[], bold_ar=[]))
        m = re.match(r'\| (\d+) \|', raw)
        if not m:
            continue
        c = [x.strip() for x in raw.strip().strip('|').split('|')]
        en = c[2].replace('**', '')
        rows.append(dict(id=c[0], part=part, role=c[1], en=en.replace('⏸', '').strip(), ar=c[3].replace('**', ''),
                         visual=c[4] if len(c) > 4 else '', bold_en=re.findall(r'\*\*(.+?)\*\*', c[2]),
                         bold_ar=re.findall(r'\*\*(.+?)\*\*', c[3]), wait='⏸' in en, title=False))
    return rows


def spoken_text(line):
    t = line['en']
    if t.startswith('Oh, Abu Bedr'):
        t = t.replace('Oh, Abu Bedr', 'Oh... Abu Bedr')  # a sigh, not a quick "oh"
    return t


def fix_phonemes(ph):
    ph = re.sub(r'ˈ(?:a|æ)buː', 'ɐbˈuː', ph)            # a-BOO, not AB-oo
    ph = re.sub(r'bˈɛd(?:ɚɹ?|əɹ?)(?![a-zɪʊ])', 'bˈɛdəɹ', ph)  # keep the r in Bedr
    return ph


def synth(k, line):
    voice, lang, speed, boy = VOICES[line['role']]
    ph = fix_phonemes(k.tokenizer.phonemize(spoken_text(line), lang))
    if boy:
        x, sr = k.create(ph, voice=voice, speed=speed / boy, is_phonemes=True)
        x = resample_poly(x, int(round(100 / boy)), 100)   # tape-style: pitch + formants up together
    else:
        x, sr = k.create(ph, voice=voice, speed=speed, is_phonemes=True)
    assert sr == SR
    x = np.asarray(x, dtype=float)
    idx = np.where(np.abs(x) > 0.01)[0]
    x = x[max(0, idx[0] - 240): idx[-1] + 1200]
    return x / (np.abs(x).max() + 1e-9) * 0.9


def gap_after(lines, i):
    cur = lines[i]
    nxt = lines[i + 1] if i + 1 < len(lines) else None
    if cur['wait']:
        return GAP_ANSWER_WAIT
    if nxt is None:
        return 1.0
    if nxt['part'] != cur['part'] or nxt.get('title') or cur.get('title'):
        return GAP_SECTION
    if cur['role'] == 'Answer':
        return GAP_AFTER_ANSWER
    return GAP_LINE


def main():
    model_dir, out = sys.argv[1], sys.argv[2]
    from kokoro_onnx import Kokoro
    k = Kokoro(os.path.join(model_dir, 'kokoro-v1.0.onnx'), os.path.join(model_dir, 'voices-v1.0.bin'))
    os.makedirs(os.path.join(out, 'lines'), exist_ok=True)
    lines = load_lines()
    t = 0.6
    chunks = [np.zeros(int(SR * t))]
    for i, line in enumerate(lines):
        x = synth(k, line)
        sf.write(os.path.join(out, 'lines', f"{line['id']}.wav"), x, SR)
        line['start'] = round(t, 3)
        line['end'] = round(t + len(x) / SR, 3)
        g = gap_after(lines, i)
        line['gap'] = g
        chunks += [x, np.zeros(int(SR * g))]
        t = line['end'] + g
    audio = np.concatenate(chunks)
    sf.write(os.path.join(out, 'narration.wav'), audio, SR)
    json.dump(lines, open(os.path.join(out, 'timeline.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    parts = {p: (min(l['start'] for l in lines if l['part'] == p), max(l['end'] + l['gap'] for l in lines if l['part'] == p))
             for p in (1, 2, 3)}
    for p, (a, b) in parts.items():
        print(f'part {p}: {a:6.1f}s -> {b:6.1f}s  ({b - a:5.1f}s)')
    print(f'total {len(audio) / SR:.1f}s, {len(lines)} lines')


if __name__ == '__main__':
    main()
