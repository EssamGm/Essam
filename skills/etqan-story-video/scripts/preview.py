"""Narration review video: each line's bilingual subtitle on a plain Etqan background.

    python3 preview.py NARRATION_DIR OUT.mp4
"""
import json
import os
import subprocess
import sys
import tempfile

import skia

import etqan as E
import scenes as S
from render_lib import H, P, W, col

PART_NAME = {1: ('The story', 'القصة'), 2: ('Questions', 'الأسئلة'), 3: ('The story again', 'القصة مرة أخرى')}
SPEAKER = {'Bedr': ('Bedr', 'بدر'), 'Abu Bedr': ('Abu Bedr', 'أبو بدر')}


def card(line, wait=None):
    s = skia.Surface(W, H)
    cv = s.getCanvas()
    cv.clear(col(E.SURFACE))
    S.section_chip(cv, *PART_NAME[line['part']])
    S.watermark(cv)
    E.draw_text(cv, f"line {line['id']}" if not line.get('title') else '', W / 2, 420, 34, E.TEXT_2, kind='med')
    if line.get('title'):
        E.draw_text(cv, line['en'], W / 2, 520, 72, E.TEXT, kind='h')
        E.draw_text(cv, line['ar'], W / 2, 620, 60, E.TEXT_2, kind='h')
        return s
    kind = {'Question': 'q'}.get(line['role'])
    if line['role'] == 'Answer':
        kind = 'no' if line['en'].startswith('No') else 'yes' if line['en'].startswith('Yes') else None
    hl_en = line['bold_en'][0] if line['bold_en'] else None
    hl_ar = line['bold_ar'][0] if line['bold_ar'] else None
    S.subtitle(cv, line['en'], line['ar'], hl_en, hl_ar, kind=kind, speaker=SPEAKER.get(line['role']), wait=wait)
    return s


def main():
    nd, out = sys.argv[1], sys.argv[2]
    lines = json.load(open(os.path.join(nd, 'timeline.json'), encoding='utf-8'))
    tmp = tempfile.mkdtemp()
    entries = []
    t = 0.0
    for i, line in enumerate(lines):
        nxt = lines[i + 1]['start'] if i + 1 < len(lines) else line['end'] + line['gap']
        if line['wait']:
            spans = [(line['end'], None), (nxt, 0.5)]   # while asking, then the learner's turn
        else:
            spans = [(nxt, None)]
        start = t
        for j, (until, wait) in enumerate(spans):
            p = os.path.join(tmp, f'{i:03d}_{j}.png')
            card(line, wait).makeImageSnapshot().save(p, skia.kPNG)
            dur = until - (line['start'] if j == 0 and i == 0 else start)
            if i == 0 and j == 0:
                dur = until  # first card also covers the lead-in silence
            entries.append((p, dur))
            start = until
        t = nxt
    with open(os.path.join(tmp, 'list.txt'), 'w') as f:
        for p, d in entries:
            f.write(f"file '{p}'\nduration {d:.3f}\n")
        f.write(f"file '{entries[-1][0]}'\n")
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', os.path.join(tmp, 'list.txt'),
                    '-i', os.path.join(nd, 'narration.wav'), '-vf', 'fps=10,format=yuv420p', '-c:v', 'libx264',
                    '-preset', 'veryfast', '-crf', '24', '-af', 'loudnorm=I=-16:TP=-1.5', '-ar', '48000',
                    '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', out], check=True)
    print('wrote', out)


if __name__ == '__main__':
    main()
