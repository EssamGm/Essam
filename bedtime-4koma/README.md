# Bedtime 4コマ

Three short 4-panel strips per night, each punchline hinging on one Japanese word
being reviewed. Published page: https://claude.ai/artifact/SX4vtXd3bVVsTiCm1CGCUL

- `LEVEL.md` records Essam's level and what makes a strip land for him. Read it before writing
  new strips and update it after reading new answers.
- `page.src.html` holds the strips (art + lines) and the player. Edit strips here.
- `build.py` voices every line with VOICEVOX at ふつう (1.0×) and ゆっくり (0.8×). It writes
  `index.html` (the page, ~60 KB) and one `audio/<strip id>.json` per strip, which the page
  loads when that strip is opened. Unchanged strips are skipped.
- Publishing: publish `index.html` to the page's URL with `root: "bedtime-4koma"` and
  `files` = the audio files build.py lists as new or changed. Files already on the page are
  kept, so never re-send all of them. Do not pass `capabilities` (the page declares `db`).
- `setup_voicevox.sh` installs VOICEVOX CORE 0.17.0 and the voice models.

## Cast (STORY.md is the source of truth; it supersedes the skill's old cast limit)

Voices now: 父 青山龍星, 息子 白上虎太郎, じいちゃん 麒ヶ島宗麟 (53), タマ 黒沢冴白 (100), 山田さん 玄野武宏 (11), ミカ 春歌ナナ (54), narration 雀松朱司. Speaker prefixes: `父「`, `息子「`, `じいちゃん「`, `タマ「`, `山田さん「`, `ミカ「`. A little girl (ミカ) is allowed; no women.

Old table (kept for reference):

| Role | Voice | Style ID |
|---|---|---|
| Narration | 雀松朱司 ノーマル | 52 |
| 父 | 青山龍星 ノーマル (喜び 83 for the ハハハ line) | 13 |
| 息子 | 白上虎太郎 ふつう | 12 |
| タマ / grandpa-type lines (`じいちゃん「…」`) | ちび式じい ノーマル | 42 |

A line is spoken by a character when it is written `父「…」`, `息子「…」`,
`タマ「…」` or `じいちゃん「…」`; anything else is narration. Misread words go in
`READINGS` in `build.py`.

Credit shown on the page (required by the voice terms): `VOICEVOX:<voice name>` for
every voice used.

## Before publishing (lessons from 2026-10-12)

- A syntax error in the inline script blanks the whole page, and publishing does not catch it.
  After `build.py`, load `index.html` in headless Chromium and check: no page error, `#dots`
  reads "1 / N", `#jump` has N+1 options, and each new strip opens with 4 panels.
- Every strip in `page.src.html` must end with `  ]},` (panels array closed, then the strip).
- Publishing is refused until the live version has been fully viewed: `Artifact read`, then Read
  every line of the saved HTML it names, merge, publish once.
- Merge live-only strips into `page.src.html` first and fetch their `audio/*.json` from the live
  page so `build.py` only re-voices the new strips.
