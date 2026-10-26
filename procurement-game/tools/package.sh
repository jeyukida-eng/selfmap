#!/bin/sh
# 공모전 파일명 규칙에 맞춰 제출물 생성: sh tools/package.sh 성명 [작품명]
NAME="${1:?성명을 입력하세요}"; TITLE="${2:-우리마을조달청전국조달원정대}"
OUT="$(dirname "$0")/../submit"; mkdir -p "$OUT"; cd "$(dirname "$0")/.."
python3 tools/build.py >/dev/null
TMP=$(mktemp -d); cp dist/woorimaeul-jodal.html "$TMP/${TITLE}.html"
printf '실행 방법: %s.html 파일을 더블클릭하면 브라우저(Chrome/Edge 권장)에서 실행됩니다.\n인터넷 연결이 필요 없습니다.\n' "$TITLE" > "$TMP/실행방법.txt"
rm -f "$OUT/AI게임_실행파일_${TITLE}_${NAME}.zip"
(cd "$TMP" && zip -q -r "$OLDPWD/$OUT/AI게임_실행파일_${TITLE}_${NAME}.zip" .)
cp video/demo_60s.mp4 "$OUT/AI게임_시연영상_${TITLE}_${NAME}.mp4"
ls -la "$OUT"
