# 捨てたもんじゃない — the drive home

A short faceless 2D animation (9:16, 1080×1920, 30 fps, ~48 s) of a true story:
working late, driving home tired while listening to Japanese, suddenly
understanding a sentence, and rushing home to check whether it was a good one.

**Final video:** `suteta-mon-ja-nai-drive-home.mp4`

## Scenes

| Time | Scene |
|---|---|
| 0–7 s | Late night at the office, clock at 11:47 |
| 7–11 s | Driving home through the city |
| 11–21 s | Japanese audio in the car — kana drift by, not understood yet |
| 21–27 s | The "aha": the sounds assemble into 捨てたもんじゃない |
| 27–32 s | Arriving home, rushing to the door |
| 32–41 s | Looking it up: "Not so bad after all." (lit. "not something to throw away") — sounds negative, but it's a compliment |
| 41–48 s | Celebration and end card |

## Rebuild

Requires `skia-python`, `numpy`, `scipy`, `ffmpeg`, plus the Inter and Noto Sans CJK fonts.

```bash
python3 render.py video_only.mp4          # frames -> H.264 (video only)
python3 audio.py ambience.wav             # ambient sound design (no music)
ffmpeg -i video_only.mp4 -i ambience.wav -map 0:v -map 1:a -c:v copy \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11" -c:a aac -b:a 192k -shortest \
  -movflags +faststart suteta-mon-ja-nai-drive-home.mp4

python3 render.py --still 21.5 frame.png  # preview a single frame
```
