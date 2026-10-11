#!/usr/bin/env bash
# Install VOICEVOX CORE (Python) + ONNX Runtime + Open JTalk dictionary + voice models
# for build.py, without the official downloader.
#
# The official `download` tool looks releases up through api.github.com, which this
# cloud environment blocks (anonymous calls are also rate-limited). Release files
# on github.com/*/releases/download/* do work, and the voice models are plain files
# in the voicevox_vvm git repo, so we fetch the same assets directly.
#
# Needs network access to: github.com, objects.githubusercontent.com,
# release-assets.githubusercontent.com, pypi.org, files.pythonhosted.org.
#
# By running this you accept the VOICEVOX 音声モデル 利用規約 and each voice's terms
# (see voicevox_vvm/README.md). Generated audio must credit "VOICEVOX:<voice name>".
set -euo pipefail

VV_HOME=${VV_HOME:-/home/user/vv}
VVM_DIR=${VVM_DIR:-/home/user/voicevox/voicevox_vvm}
CORE_VER=0.17.0
ORT_VER=1.23.2
GH=https://github.com

mkdir -p "$VV_HOME/assets" "$VV_HOME/ort" "$VV_HOME/dict"
cd "$VV_HOME/assets"
curl -sSfLO "$GH/VOICEVOX/onnxruntime-builder/releases/download/voicevox_onnxruntime-$ORT_VER/voicevox_onnxruntime-linux-x64-$ORT_VER.tgz"
curl -sSfLO "$GH/r9y9/open_jtalk/releases/download/v1.11.1/open_jtalk_dic_utf_8-1.11.tar.gz"
curl -sSfLO "$GH/VOICEVOX/voicevox_core/releases/download/$CORE_VER/voicevox_core-$CORE_VER-cp310-abi3-manylinux_2_34_x86_64.whl"
tar xzf "voicevox_onnxruntime-linux-x64-$ORT_VER.tgz" -C "$VV_HOME/ort"
tar xzf open_jtalk_dic_utf_8-1.11.tar.gz -C "$VV_HOME/dict"

python3 -m venv "$VV_HOME/venv"
"$VV_HOME/venv/bin/pip" install -q "voicevox_core-$CORE_VER-cp310-abi3-manylinux_2_34_x86_64.whl"

# Voice models (~1.7 GB). Only 9, 10, 12 and 15.vvm are used by build.py today.
if [ ! -d "$VVM_DIR/.git" ]; then
  mkdir -p "$(dirname "$VVM_DIR")"
  GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 "$GH/VOICEVOX/voicevox_vvm" "$VVM_DIR"
fi

command -v ffmpeg >/dev/null || { echo "ffmpeg is required for build.py" >&2; exit 1; }
echo "Ready. Build with: $VV_HOME/venv/bin/python -I build.py"
