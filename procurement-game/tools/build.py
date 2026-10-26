"""src/ 와 assets/ 를 하나의 오프라인 HTML 파일로 묶습니다."""
import base64, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
src = ROOT / 'src'
html = (src / 'index.html').read_text(encoding='utf-8')
css = (src / 'style.css').read_text(encoding='utf-8')
names = {'res': 'atlas_res', 'elder': 'atlas_elder', 'bandit': 'bandit', 'jacheong': 'jacheong', 'yeongdeung': 'yeongdeung', 'narmi': 'narmi3d', 'dari': 'dari3d', 'ppsLogo': 'pps_logo'}
assets = ',\n'.join(f"{k}:'data:image/webp;base64,{base64.b64encode((ROOT / 'assets' / (v + '.webp')).read_bytes()).decode()}'" for k, v in names.items())
js = '\n'.join((src / f).read_text(encoding='utf-8') for f in ['data.js', 'engine.js', 'scenes.js', 'game.js', 'demo.js'])
out = html.replace('/*STYLE*/', css).replace('/*ASSETS*/', 'const ASSETS={\n' + assets + '\n};').replace('/*SCRIPTS*/', js)
dist = ROOT / 'dist'; dist.mkdir(exist_ok=True)
target = dist / 'woorimaeul-jodal.html'
target.write_text(out, encoding='utf-8')
print(target, round(len(out.encode()) / 1024), 'KB')
