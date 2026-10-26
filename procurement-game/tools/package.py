"""공모전 파일명 규칙에 맞춘 제출물 생성: python3 tools/package.py 성명 [작품명]
ZIP 내부 파일명은 영문(어떤 압축 프로그램·OS에서도 풀리도록), 바깥 ZIP 이름만 규칙대로 한글."""
import sys, zipfile, shutil, subprocess, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
name = sys.argv[1]; title = sys.argv[2] if len(sys.argv) > 2 else '우리마을조달청전국조달원정대'
subprocess.run([sys.executable, str(ROOT / 'tools/build.py')], check=True, stdout=subprocess.DEVNULL)
out = ROOT / 'submit'; out.mkdir(exist_ok=True)
for f in out.glob('*'): f.unlink()
z = out / f'AI게임_실행파일_{title}_{name}.zip'
howto = ('우리 마을 조달청 · 전국 조달 원정대\r\n\r\n'
         '실행 방법: play.html 파일을 더블클릭하세요.\r\n'
         '크롬(Chrome) 또는 엣지(Edge) 브라우저에서 실행됩니다. 인터넷 연결이 필요 없습니다.\r\n'
         '진행 기록은 브라우저에 자동 저장되며, 지도 화면의 "처음부터 다시 시작"으로 초기화할 수 있습니다.\r\n')
with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    zf.write(ROOT / 'dist/woorimaeul-jodal.html', 'play.html')
    zf.writestr('HOW_TO_PLAY.txt', '﻿' + howto)  # 메모장에서 한글이 깨지지 않도록 BOM 포함
shutil.copy(ROOT / 'video/demo_60s.mp4', out / f'AI게임_시연영상_{title}_{name}.mp4')
for f in sorted(out.iterdir()): print(f.name, round(f.stat().st_size / 1024), 'KB')
