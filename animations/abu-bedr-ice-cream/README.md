# Abu Bedr and the Ice Cream — English for beginners (A1)

A faceless 2D animated story (16:9, 1920×1080, about 5½ minutes) in the Etqan
(إتقان) visual identity. It teaches four feelings — **ready, hot, happy, confused** —
through a short story, question-and-answer revision with pauses for the learner,
and a quick retelling. Every line is shown in English with an Arabic translation.

**Video:** `abu-bedr-ice-cream.mp4` · **Script:** `transcript.md`

## Structure

| Part | What happens |
|---|---|
| 1 — The story | Abu Bedr gets ready to study English at 6 pm. His son Bedr is hot and wants ice cream. Abu Bedr buys it, comes home, and forgets why his book is on the table. |
| 2 — Questions | Four rounds of questions (one per word). After each question a 2-second "Your turn · دورك" pause lets the learner answer out loud. |
| 3 — The story again | A 7-line retelling. |
| End | The four words with Arabic, then the Etqan end screen. |

## Voices (all male, offline Kokoro voices)

Narrator and answers: UK male · Questions: a second UK male · Instructions ("Now, answer
the questions!"): a deeper US male · Abu Bedr: US male · Bedr: a US male voice raised
to sound like a boy. No music — only quiet room/street sound and small action sounds.

## Brand

Colours, fonts (Cairo, IBM Plex Sans Arabic) and the logo come only from the Etqan brand
guidelines v1.0 (`brand/`). Arabic is shaped with HarfBuzz. Motion is calm (fades and
slides, no rotation, bounce or particles), as the guideline asks.

## Rebuild

Requires `skia-python`, `uharfbuzz`, `fonttools`, `brotli`, `kokoro-onnx`, `soundfile`,
`scipy`, `ffmpeg`, and the Kokoro model files (`kokoro-v1.0.onnx`, `voices-v1.0.bin`).

```bash
python3 voice.py MODEL_DIR NARRATION_DIR           # all spoken lines + timeline.json
python3 video.py NARRATION_DIR abu-bedr-ice-cream.mp4
python3 video.py NARRATION_DIR --still 37 frame.png   # check one moment
python3 preview.py NARRATION_DIR preview.mp4        # narration with subtitles only
python3 scenes.py --stills DIR                      # style frames
```
