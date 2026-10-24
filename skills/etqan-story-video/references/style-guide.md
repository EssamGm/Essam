# Look, characters and sound

Everything visual comes from the **Etqan brand guidelines v1.0** (`assets/Etqan-brand-guidelines.html`,
13 pages, Arabic). Essam's instruction: use his guideline and nothing else — not his website pages,
not memory of other Etqan material. The extracted pieces are in `assets/brand/` and coded in
`scripts/etqan.py`.

## Brand

| Token | Hex | Use |
|---|---|---|
| Navy | #14365C | the logo (light version), headings; the room's wall |
| Gold | #C9A227 | the square, target-word highlights, badges — the only gold |
| Surface | #0B1A2A | dark background, subtitle panel, end screen |
| Elevated / Border | #122943 / #24374C | cards and panel edges |
| Navy soft / light | #1F4E79 / #3E6C99 | fills, name chips |
| Text / Text 2 | #F2F5F8 / #9AA6B5 | English line / Arabic line on dark |
| Positive / Alert | #1D7A6B / #B83227 | ✓ and ✗ only (state colours, not identity) |

- **Fonts:** Cairo (900 logo, 800 headings, 700 buttons/numbers) and IBM Plex Sans Arabic
  (400/500/600 body). Taken from the subsets embedded in the guideline; `etqan.py` merges each
  weight's Arabic + Latin subsets (the Arabic subset has no `. ! :`).
- **Logo:** vector wordmark + a 7×7 gold square at (0, 12.84) in an 86.36 × 31.80 box — the
  square, never a dot. Reversed version (#F2F5F8 word) on dark. Clear space = the square's height.
- **Motion (guideline §11):** light and quiet — fades and small slides with ease-out. No rotation,
  elastic bounce, glitter or flying particles. Logo animation: the square first (0.4 s), then the
  word settles (0.5 s).

## Frame layout (1920×1080)

- Artwork lives above y≈820; the subtitle panel sits at (140, 846), 1640×196, Surface with a
  Border outline. English on top (IBM Plex 600, 56 px, Text), Arabic below (IBM Plex 500, 48 px,
  Text 2). Target words in gold in both languages.
- A question shows a small gold square at the panel's left; an answer shows a green ✓ or red ✗.
- After a question: "Your turn · دورك" and a thin gold bar that empties over the 2-second pause,
  with a soft tick as it starts.
- When a character speaks, a navy chip above the panel: "Bedr ▪ بدر".
- Top-left section chip in Parts 2 and 3 ("Questions · الأسئلة", "The story again · القصة مرة أخرى").
  Part 1 has no chip.
- Top-right: the reversed logo, 170 px wide, the whole video.
- Title cards (Guide lines): a dark scrim over the picture, gold square, big English + Arabic.
- **No intro** — the video opens straight on the story (Essam: "no need for the Etqan intro").
- **End screen = the logo only**, centred on Surface. No "WWW.ETQAN.SA": he said the site isn't real.

## Characters (faceless)

- A head with hair, and nothing else on it: no eyes, nose, mouth — and **no ear** and **no
  beard**. The ear made the head look "weird"; a jaw-line beard read as a smile from the side.
- Hair covers the top and the whole back of the head down to the neck with a soft hairline in
  front, so it is always clear which way someone faces (`render_lib.person`).
- Abu Bedr: casual home clothes (light t-shirt, navy trousers). Bedr: a boy — `BEDR` outfit with
  shorter legs/body and a slightly bigger head. New characters: copy an outfit dict and change
  colours/proportions; keep them male unless Essam says otherwise.
- Feelings are shown with the body and symbols because there is no face: ready = sits up straight,
  book open, "ABC" thought; hot = heat waves, fanning; happy = gentle hops, warm glow; confused =
  hand scratching head, gold "?". Gentle character acting is fine; sparkles and bouncy brand-style
  effects are not.

## Sound

- **No music, and nothing musical.** Essam heard "music" in chimes, pings and a rising "pop" in an
  earlier video and asked for none at all. Only noise-based sounds: room tone, street, footsteps,
  drawer, book, door, clicks, a soft whoosh.
- **All voices male — no woman's voice whatsoever**, including pitch-shifted female voices.
  - Narrator + answers: `bm_george` (UK) · Questions: `bm_lewis` (UK) · Guide/instructions:
    `am_fenrir` (deeper US — a different voice "to break the rhythm") · Abu Bedr: `am_michael` ·
    a boy: `am_echo` raised tape-style ×1.25.
  - The boy voice is generated slowly and played back faster (resample). Pitch-shifting with
    time-stretch (`atempo`) sounded robotic and was rejected.
- Speech is slowed (speed 0.80); a held pause after "But wait!"; extra silence after action lines
  so the animation can play. Names are fixed in phonemes: Abu = a-BOO, Bedr keeps its r.
- ElevenLabs would sound more natural, but Essam chose to stay with these voices for now ("if
  people didn't like the voice, I'll add the API key"). If he adds it later, the key comes from the
  environment (`ELEVENLABS_API_KEY`), never pasted in chat, and the voices must still be male.
- Loudness: −16 LUFS, true peak −1.5 dB (ffmpeg loudnorm at the end).

## Text rendering

Arabic must be shaped (HarfBuzz) — skia's plain text drawing and ffmpeg `drawtext` break the
letter joins. `etqan.draw_text` handles shaping, right-to-left punctuation and gold highlights; it
caches shaped runs, so text is cheap per frame.
