# Teaching method and transcript format

## Who it is for

A1 beginners whose first language is Arabic. Short sentences (8 words or fewer), about 95% known
words, 3–5 target words per video. Essam made his website lessons only as illustrations — do not
plan around them.

## The shape of every video (about 4½–5½ minutes, horizontal 16:9)

| Part | Length | What it is |
|---|---|---|
| 1 — The story | ~1–1½ min | 20–25 short lines told by the Narrator, with one or two lines spoken by the characters. Essam usually brings the story idea himself (the ice-cream story was his own day). |
| 2 — Questions | ~3 min | One round per target word, in story order. A Guide voice opens it: "Now, answer the questions!" |
| 3 — The story again | ~30 s | 7 lines retelling the story. The Guide says "Listen to the story again." first. |
| End | ~8 s | The word card (each word in English + Arabic), then the Etqan end screen. |

The story comes first and the questions are its revision — that order is Essam's.

## Grammar

One focus structure per video, repeated until it is automatic. The first video used
**be + feelings** (is / is not / Is …? / Yes, he is / No, he isn't / … or …? / Why …? Because …).
Actions in the story may use present simple ("He opens the drawer."). Later videos can circle
present simple, present continuous or past simple the same way.

## A question round (the repetition ladder)

```
Narrator  recap:        Abu Bedr looks at the book. Abu Bedr is confused.
Question  yes:          Is Abu Bedr confused? ⏸        Answer: Yes. Abu Bedr is confused.
Question  no:           Is Abu Bedr ready? ⏸           Answer: No. Abu Bedr is not ready. He is confused.
Question  either/or:    Is he confused or hot? ⏸       Answer: He is confused.
Question  why:          Why is the book on the table? ⏸ Answer: Because Abu Bedr wants to study English!
Narrator  close:        Oh, Abu Bedr!
```

- **The answer must match the picture.** A "No" question asks about a *different* word — and its
  answer repeats the target word anyway ("No. He is not happy. He is confused."). Essam's first
  example ("Is this person angry? No, not angry") had this backwards; the picture decides.
- The "No" question reuses a word from earlier in the story, so older words keep coming back.
- Mix in "Who …? A or B?", "What does … want?", "Does … ?" for variety.
- Count: every target word should be heard 10–15 times across the whole video. Count after
  writing (a few lines of Python over the transcript) and report the counts.

## Arabic lines

- Simple Modern Standard Arabic, natural rather than literal: «لأن عنده آيس كريم» (he rejected
  «لأنه يحمل آيس كريم»).
- **Every English line with "he" gets «هو», every "she" line «هي»** in the Arabic
  («هو يفتح الدرج», «هو ينسى درس الإنجليزية»). Where Arabic joins the pronoun to a word
  («لأنه», «لأنها») that already carries it — «لأن هو» would be wrong Arabic.
- Masculine/feminine agreement must follow the character (Bedr: «بدر يشعر بالحر», «هو سعيد»).
- "Is X hot?" for a person is «هل يشعر X بالحر؟», not «حار».

## Transcript file format (voice.py parses it — keep it exact)

```markdown
# Title — transcript

**Target words:** ready (مستعد) · hot (حار / يشعر بالحر) · …
**Voices (all male):** Narrator · Question · Answer · Guide · <characters>

## Part 1 — The story (about 1 minute)

| # | Voice | English | Arabic | Visual |
|---|---|---|---|---|
| 1 | Narrator | This is Abu Bedr. | هذا أبو بدر. | Abu Bedr in his office |
| 7 | Narrator | Abu Bedr is **ready**. | أبو بدر **مستعد**. | sits up straight |
| 11 | Bedr | Baba, I am **hot**. I want ice cream, please! | بابا، أنا أشعر بالحر. … | Bedr tugs his sleeve |

## Part 2 — Questions and answers (about 3 minutes)

| 26 | Question | Is Abu Bedr **ready**? ⏸ | هل أبو بدر مستعد؟ | |
| 27 | Answer | Yes. Abu Bedr is **ready**. | نعم. أبو بدر مستعد. | ✓ |

## Part 3 — The story again (about 30 seconds)

| 71 | Narrator | At six o'clock, Abu Bedr is **ready** to study English. | … |
```

- Lines are numbered 1…N straight through all three parts; the id is what the story file uses
  for timing (`ls(13)` = start of line 13).
- `## Part N` headings must start with `## Part 1`, `## Part 2`, `## Part 3` — voice.py adds the
  Guide's title lines (ids `T2`, `T3`) when it meets Parts 2 and 3.
- `⏸` on a question = a 2-second answer pause with the "Your turn · دورك" bar.
- `**word**` marks a target word (gold on screen). Roles: Narrator, Question, Answer, Guide, or a
  character name. The full worked example is `examples/abu-bedr-ice-cream/transcript.md`.

## Planning with Essam

He likes to go step by step at the start of a new idea: level and grammar → the story (1 minute)
→ the question rounds → voices → a look at style frames → the video. Show the story as a table
(English | Arabic) and ask the few questions that matter (names, which words). Once he has
approved the plan he wants the video made without more questions — at that point decide small
things yourself and tell him what you chose.
