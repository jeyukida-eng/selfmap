#!/usr/bin/env bash
# 마무리 일괄: Cycles 스틸 4장 → EEVEE 플라이스루 576프레임 → 환경음 → MP4. 중단 후 재실행하면 이미 있는 프레임은 건너뜀.
# 실행: bash final/run_final.sh  (로그: out/logs/)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; PY=/opt/bvenv/bin/python
mkdir -p "$ROOT/out/logs"
$PY "$ROOT/final/render_still.py" --long 1600 --samples 96 2>&1 | grep --line-buffered -E "^\[still\]|Error|Traceback" | tee "$ROOT/out/logs/still.log"
EGL_PLATFORM=surfaceless $PY "$ROOT/final/flythrough.py" --res 960x540 --samples 12 2>&1 | grep --line-buffered -E "^\[fly\]|Error|Traceback" | tee "$ROOT/out/logs/fly.log"
$PY "$ROOT/final/audio_synth.py"
bash "$ROOT/final/make_mp4.sh" | tee "$ROOT/out/logs/mp4.log"
echo DONE
