---
name: etqan-story-video
description: Make Essam's faceless animated English-lesson story videos in the إتقان (Etqan) brand — a short A1 story, question-and-answer revision with answer pauses, a retelling, English + Arabic subtitles, all-male offline voices and no music, rendered to MP4 (16:9). Use whenever Essam wants an English story video, a new Abu Bedr / Bedr episode, an animation that teaches English words through a story, repetition or "circling" questions, or "another video like the ice cream one" — even when he only describes a story idea or a word list. Not for the إتقان Q&A podcast videos (itqan-video), shorts (itqan-shorts) or Japanese practice.
---

# Etqan story videos (English for beginners)

Essam teaches English to Arabic-speaking adults. These videos tell one short story about Abu Bedr
(and his son Bedr, or new characters), then ask simple questions about it so a few target words
are heard 10–15 times, then tell the story again. The first one, "Abu Bedr and the Ice Cream",
is in `examples/abu-bedr-ice-cream/` (transcript + story file) and is the reference for quality.

## What every video keeps (Essam's decisions — the reasons are in the references)

- **Faceless people:** a head with hair, no eyes, nose, mouth, ear or beard. Casual home clothes.
- **Etqan identity only from his guideline** (`assets/Etqan-brand-guidelines.html`): navy/surface
  palette, one gold, Cairo + IBM Plex Sans Arabic, the square logo top-right. No intro; the end
  screen is the logo alone (no website).
- **English + Arabic subtitles on every line**, target words in gold in both. Simple Modern Standard
  Arabic, with «هو» / «هي» for every he/she line.
- **All voices male, no music.** UK narrator, a second UK voice for questions, a different deeper
  voice for instructions, slowed speech, 2-second answer pauses. Only noise-based sounds.
- **Calm motion:** fades and gentle moves; no sparkles, spins or bouncy effects.

## Workflow

1. **Plan with Essam** (when the idea is new): level and grammar focus, the 1-minute story, the
   target words, then the question rounds. Read `references/teaching-method.md` first — it has the
   repetition ladder, the Arabic rules and the exact transcript format. Write `transcript.md`, count
   how often each target word is heard, and show him the story as an English | Arabic table.
   Once he approves the plan, build the video without more questions; decide small things yourself
   and say what you chose.

2. **Set up a work folder** (the skill folder may be read-only):
   ```bash
   bash <this-skill>/scripts/setup.sh ~/work/<video-name>
   cp <this-skill>/examples/abu-bedr-ice-cream/story.py ~/work/<video-name>/story.py   # starting point
   ```
   Put the new `transcript.md` in the same folder.

3. **Voices first, animation second.** Everything is timed from the narration:
   `python3 voice.py kokoro-model narr --story story.py`. Add extra seconds after action lines
   (`EXTRA_GAP` in story.py) so each action has time to play, and re-run. A narration-only preview
   (`preview.py`) is a good thing to send Essam when the voices or the script are new.

4. **Write the story file.** Rewrite `story.py`'s choreography for the new story: the Part 1 scene
   functions, the pictures for the question rounds (`QA_MAP`, `qa_state`), `segments()`,
   `sound(A)`, `TARGETS`, `WORDS`, `SPEAKER` and the voice settings. The engine API, the room
   geometry and the state keys are in `references/pipeline.md`. Reuse the study room and the
   characters; add a new place (like the example's street and shop) only when the story needs it.

5. **Check with stills before rendering.** Render 30–40 frames across the timeline into contact
   sheets and look at every one (overlaps, reach, facing, subtitle fit, faceless heads). Then a
   20-second `--test` render with sound. Fix, re-check.

6. **Render and deliver.** Full render in the background (~12 min for a 5½-minute video on 4 cores),
   verify duration, loudness (≈ −16 LUFS) and a few frames of the final file, then send it. Delivery
   details (30 MiB chat limit, the GitHub raw link) are at the end of `references/pipeline.md`.

## References

- `references/teaching-method.md` — A1 method, video structure, question ladder, Arabic rules,
  transcript format, how Essam likes to plan.
- `references/style-guide.md` — brand tokens, frame layout, characters, sound and voices, and why
  each rule exists.
- `references/pipeline.md` — commands, the story-file API, checking steps, known pitfalls,
  delivery.
- `examples/abu-bedr-ice-cream/` — the complete first video: `transcript.md` and `story.py`.
