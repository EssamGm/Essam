# Bedtime 4コマ

Three short 4-panel strips per night, each punchline hinging on one Japanese word
being reviewed. Published page: https://claude.ai/artifact/SX4vtXd3bVVsTiCm1CGCUL

- `page.src.html` holds the strips (art + lines) and the player. Edit strips here.
- `build.py` voices every line with VOICEVOX and writes `index.html` (the page that
  gets published) with the MP3 clips embedded, at ふつう (1.0×) and ゆっくり (0.8×).
- `setup_voicevox.sh` installs VOICEVOX CORE 0.17.0 and the voice models.

## Cast

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
