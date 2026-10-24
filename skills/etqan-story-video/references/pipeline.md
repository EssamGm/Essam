# Pipeline and story-file reference

## Contents
1. Files
2. Commands
3. Writing a story file (the API)
4. Checking before the full render
5. Pitfalls that already cost time
6. Delivering

## 1. Files (copied into the work folder by `scripts/setup.sh`)

| File | Role |
|---|---|
| `etqan.py` | Brand tokens, fonts (HarfBuzz-shaped text, highlights), the logo |
| `render_lib.py` | Easing/colour helpers and the faceless character rig `person()`, outfits `ABU_BEDR`, `BEDR`, poses, `walk_pose` |
| `scenes.py` | The study room, subtitle panel, chips, watermark, title card parts, word card, end screen |
| `voice.py` | transcript.md → one WAV per line → `narration.wav` + `timeline.json` |
| `engine.py` | Kinematics, props, the study state machine, text layers, compositor, sound mix, render |
| `preview.py` | Narration-only review video (subtitles on a plain background) |
| `story.py` | **The only file you write per video** (copy `examples/abu-bedr-ice-cream/story.py`) |
| `brand/` | Logo SVGs and fonts from the guideline |

## 2. Commands

```bash
bash <skill>/scripts/setup.sh WORK            # once per video folder (installs, copies, downloads the voice model ~350 MB)
cd WORK                                        # put transcript.md and story.py here
python3 voice.py kokoro-model narr --story story.py         # ~30 s; prints part lengths and total
python3 preview.py narr narration-preview.mp4               # optional: listen with subtitles, no animation
python3 engine.py narr story.py --still 12.5 a.png 40 b.png # any number of frames
python3 engine.py narr story.py --test test.mp4             # first 20 s with sound (~40 s to render)
python3 engine.py narr story.py final.mp4                   # full video (~12 min for 5½ min on 4 cores)
```

`timeline.json` holds, per line: `id, part, role, en, ar, start, end, gap, wait, title`, and
`split` for a line with a held pause (the time the second half starts, relative to `start`).

## 3. Writing a story file

A story file is plain Python that the engine imports. It must define:

| Name | What |
|---|---|
| `TARGETS` | `{'ready': ['مستعدًا', 'مستعدة', 'مستعد'], …}` — English word → Arabic forms to highlight (longest form first) |
| `SPEAKER` | `{'Bedr': ('Bedr', 'بدر'), …}` — roles that get a name chip when they speak |
| `WORDS` | `[('ready', 'مستعد'), …]` — the word card (2–5 words) |
| `QA_MAP`, `qa_state(name, t, t0, t1)` | Parts 2–3: which named picture each line id shows, and how to build it |
| `segments()` | `[(t0, t1, draw_fn), …]` — the running order; neighbours cross-dissolve over 0.45 s |
| `sound(A)` | sound cues (see below) |
| voice settings | `VOICE_ROLES`, `PAUSE_AFTER`, `SPOKEN_REPLACE`, `EXTRA_GAP`, optional `PHONEME_FIXES` — plain literals, read by `voice.py --story` |

**Timing** always comes from the narration: `G.ls(id)` start, `G.le(id)` end, `G.lg(id)` end + gap
(= next line's start). `G.T_WORDS`, `G.T_END`, `G.DUR` are the word card, end screen and total.
Animate with `prog(t, a, b)` + `smooth()`; nothing should depend on frame numbers.

**The study** is drawn from a state dict: `st = base_state()` then `draw_study(cv, t, st)`.

| Key | Meaning |
|---|---|
| `abu` | `dict(x, y, pose, facing, a)` — hip position; sitting hip `SIT=(680,642)`, standing `y=STAND_Y=565`, scale `S_ABU=1.12` |
| `bedr` | same dict or `None`; standing `y=BEDR_Y=640`, scale `S_BEDR=1.0`, facing −1 (toward the desk) |
| `book` | `'drawer'` (hidden) · `'hand'` (drawn at Abu Bedr's front hand, angle `book_ang`) · `'table'` · `'open'` (`book_open` 0–1) |
| `cone` | `None` · `'abu'` · `'bedr'` — an ice cream in that person's front hand |
| `drawer`, `door` | 0–1 open |
| `bubble`, `bubble_s`, `bubble_dy` | the "ABC" thought over Abu Bedr (alpha, scale, drift) |
| `qmark`, `heat`, `wants` | gold "?" · heat waves over Bedr · Bedr's ice-cream thought |
| `glow_bedr`, `glow_abu` | soft warm glow behind a character |
| `tags`, `tag_focus` | name tags over both heads; `'bedr'` highlights Bedr's |
| `clock` | gold ring around the clock |
| `cam` | `(zoom, cx, cy)` |

Room geometry (scenes.room): window x240–640 y150–480 · clock (1015, 230) · shelf x1120–1450 at
y330 · desk top y600, x760–1360, left drawer handle ≈ (835, 652), book spot `DESK_BOOK=(1025, 583)`
· lamp x≈1200 · door x1610–1840 · floor y790. For another place, write a draw function like
`draw_street` + `street_frame` in the example (the street with the ice-cream shop).

**Poses and hands.** Poses are dicts (`lean, head, arm_f, arm_b, leg_f, leg_b, bob`; angles in
degrees, 0 = straight down, + = forward). Ready-made: `POSE_SIT`, `POSE_SIT_RELAX`, `POSE_STAND`,
`walk_pose(gait(x))`. Blend with `pose_mix(a, b, u)`. To put a hand on a point use
`arm_ik(hip, scale, pose, facing, outfit, target, bend=1)` (`bend=-1` for reaching up to the head);
`hand_world(...)` / `head_world(...)` give world positions for props, bubbles, tags. Walking:
`x = walk_x(t, t0, t1, x0, x1)`, pose `walk_pose(gait(x))`.

**Reach:** an arm is 166 px × scale (≈186 px for Abu Bedr). Put hand-off points within reach of
both people (the shop counter needed moving twice).

**Parts 2–3.** Map every question-part line id to a picture name in `QA_MAP` (the Guide titles are
`'T2'`, `'T3'`), and build each picture in `qa_state` — a still pose plus small idle motion
(breathing, heat waves, a gentle bob). The engine cross-dissolves when the picture changes and adds
a slow camera drift.

**Sound** (`sound(A)`): `A.bed(A.room or A.street, t0, t1, gain)`, `A.add(sound, t0, gain)` with
`A.click(dur, lo, hi, decay)`, `A.thud(freq, dur)`, `A.slide(dur, lo, hi)`, `A.step()`. Typical gains
0.03–0.10 so the voices stay on top. The engine adds the answer-pause tick itself. Keep everything
noise-based (no tones).

## 4. Checking before the full render

1. `python3 -m pyflakes story.py`.
2. Render 30–40 stills across the timeline (every story line, one per question picture, the title
   cards, word card, end screen) and tile them into contact sheets (PIL, 480×270 tiles, time in the
   corner). Look at them: overlaps (a bubble over the clock or the "?"), a hand that doesn't reach,
   someone facing the wrong way, text running out of the panel.
3. Zoom into a character at full size once per new pose — heads must stay faceless.
4. `--test` render and listen to the first 20 s (voice level vs. sounds).
5. Full render in the background; then check duration, `ebur128` loudness (≈ −16 LUFS) and a few
   frames from the finished file.

## 5. Pitfalls that already cost time

- **Unbalanced `cv.save()` / `cv.restore()`** in a drawing function leaks a layer: the whole frame
  got a grey haze. Count saves and restores after editing the rig.
- **Empty strings** go through `etqan.shape` safely now; keep it that way.
- **Running engine.py directly**: the story's `import engine` must get the running module — the
  engine registers itself (`load_story`). Don't "fix" this by importing engine twice.
- **`pgrep -f` / `pkill -f` match their own shell** — waiting on a render with
  `while pgrep -f video.py` never ends, and `pkill -f "while pgrep"` killed the waiting shell.
  Wait on a PID (`while kill -0 PID`) instead.
- **Fonts:** the guideline's Arabic font subsets lack ASCII punctuation; `etqan.py` merges subsets
  per weight into `brand/.cache/` on first use (needs `fonttools` + `brotli`).
- **Kokoro on a new machine**: the model comes from GitHub release assets; if github.com is blocked,
  say so plainly — don't substitute a female or robotic voice.

## 6. Delivering

- Send the video with the file tool. The chat file limit is 30 MiB; a 5½-minute video at crf 19 is
  ≈ 30 MB — if it is over, send a crf 23 copy (≈ 14 MB) and keep the full one elsewhere.
- In Claude Code with Essam's repo: save under `animations/<name>/` with the transcript and story
  file, commit, push, and give the raw GitHub link
  (`https://github.com/EssamGm/Essam/raw/<branch>/animations/<name>/<file>.mp4`) for download.
- A cloud session cannot save into his PC; say so and give him the file card or the link.
