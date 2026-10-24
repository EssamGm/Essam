#!/usr/bin/env bash
# Prepare a working folder for one video:  bash setup.sh WORK_DIR
# Copies the toolkit and the Etqan brand kit into WORK_DIR (the skill folder itself may be
# read-only), installs the Python packages, and downloads the offline voice model once.
set -e
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${1:?usage: bash setup.sh WORK_DIR}"
mkdir -p "$WORK"
cp "$SKILL"/scripts/*.py "$WORK"/
rm -rf "$WORK/brand" && cp -r "$SKILL/assets/brand" "$WORK/brand"

pip install -q skia-python uharfbuzz fonttools brotli kokoro-onnx soundfile scipy numpy pillow 2>&1 | grep -v -i warning || true
# skia needs libEGL on minimal Linux images
python3 -c "import skia" 2>/dev/null || { apt-get install -y -q libegl1 >/dev/null 2>&1 || { apt-get update -q >/dev/null && apt-get install -y -q libegl1 >/dev/null; }; }
python3 -c "import skia, uharfbuzz, kokoro_onnx" || { echo "python packages failed to install"; exit 1; }

MODEL="$WORK/kokoro-model"
mkdir -p "$MODEL"
for f in kokoro-v1.0.onnx voices-v1.0.bin; do
  [ -s "$MODEL/$f" ] || curl -sSLo "$MODEL/$f" "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/$f"
done
[ "$(stat -c %s "$MODEL/kokoro-v1.0.onnx")" -gt 100000000 ] || { echo "voice model download failed (is github.com reachable?)"; exit 1; }
command -v ffmpeg >/dev/null || { apt-get install -y -q ffmpeg >/dev/null 2>&1 || echo "ffmpeg is missing: install it"; }
echo "ready: $WORK  (voice model in $MODEL)"
