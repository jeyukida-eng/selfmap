#!/usr/bin/env bash
# 프레임 + 환경음 → out/geobukseon_flythrough.mp4 (H.264 yuv420p + AAC)
# 실행: bash final/make_mp4.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$ROOT/out/ambience.wav" ] || /opt/bvenv/bin/python "$ROOT/final/audio_synth.py"
ffmpeg -y -hide_banner -loglevel error \
  -framerate 24 -i "$ROOT/out/frames/fly_%04d.png" \
  -i "$ROOT/out/ambience.wav" \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart \
  -c:a aac -b:a 192k -shortest \
  "$ROOT/out/geobukseon_flythrough.mp4"
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate \
  -of compact "$ROOT/out/geobukseon_flythrough.mp4"
