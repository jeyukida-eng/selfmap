// ── 블록 마을 렌더링 엔진 ───────────────────────────────────────
// 기존 '우리 마을 조달청'의 아이소메트릭 좌표계(p 함수)와 블록 표현을 그대로 이어받고,
// 균일 배율 카메라·설치 조립 순서·깊이 보정·클릭 판정을 더했습니다.
const canvas = $('scene'), ctx = canvas.getContext('2d');
const IMG = {};
for (const k in ASSETS) { IMG[k] = new Image(); IMG[k].src = ASSETS[k]; }

// 원본 아틀라스 좌표(px) 기준. s는 임베드 이미지 축소 비율.
const SPR = {
  buoy: { img: 'res', s: .5, rect: [0, 15, 554, 554], mask: [[0, 15], [490, 15], [490, 265], [554, 265], [554, 415], [490, 415], [490, 569], [0, 569]], name: '부이', h: 74 },
  deer: { img: 'res', s: .5, rect: [500, 22, 450, 545], mask: [[500, 22], [950, 22], [950, 567], [550, 567], [550, 278], [500, 278]], name: '다랑이', h: 72 },
  chief: { img: 'res', s: .5, rect: [1020, 18, 396, 553], name: '마을이장', h: 80 },
  mongdol: { img: 'res', s: .5, rect: [30, 580, 495, 485], name: '몽돌이', h: 70 },
  sorang: { img: 'res', s: .5, rect: [540, 566, 405, 494], name: '소랑이', h: 80, float: true },
  chiefLying: { img: 'res', s: .5, rect: [946, 660, 502, 356], name: '마을이장', h: 62 },
  sora: { img: 'elder', s: .5, rect: [45, 5, 704, 970], name: '소라대감', h: 88 },
  emperor: { img: 'elder', s: .5, rect: [853, 25, 680, 985], name: '제육황제', h: 88 },
  bandit: { img: 'bandit', s: 1, rect: [0, 0, 432, 465], name: '반딧대왕', h: 72 },
  jacheong: { img: 'jacheong', s: 1, rect: [0, 0, 226, 533], name: '자청비', h: 88 }
};
function sprReady(key) { const im = IMG[SPR[key].img]; return im && im.complete && im.naturalWidth > 0 }
function paintSprite(target, key, x, y, height, flip = false) {
  const def = SPR[key], img = IMG[def.img]; if (!sprReady(key)) return;
  const [sx, sy, sw, sh] = def.rect, width = height * sw / sh, k = def.s;
  target.save(); target.translate(x - width / 2, y - height);
  if (flip) { target.translate(width, 0); target.scale(-1, 1) }
  target.scale(width / sw, height / sh);
  if (def.mask) { target.beginPath(); def.mask.forEach(([px, py], i) => i ? target.lineTo(px - sx, py - sy) : target.moveTo(px - sx, py - sy)); target.closePath(); target.clip() }
  target.imageSmoothingEnabled = true; target.imageSmoothingQuality = 'high';
  target.drawImage(img, sx * k, sy * k, sw * k, sh * k, 0, 0, sw, sh); target.restore();
}
// 패널용 원형 초상화 (얼굴 위주로 잘라냄)
const portraitCache = {};
function portrait(key) {
  if (key === 'yeongdeung') return ASSETS.yeongdeung;
  if (portraitCache[key]) return portraitCache[key];
  if (!sprReady(key)) return ASSETS.yeongdeung;
  const c = document.createElement('canvas'); c.width = c.height = 120; const g = c.getContext('2d');
  g.fillStyle = '#f4efdf'; g.fillRect(0, 0, 120, 120);
  const def = SPR[key], [, , sw, sh] = def.rect, focus = { chiefLying: [190, 120, 1.0], mongdol: [120, 190, 1.25], bandit: [110, 170, 1.15], deer: [125, 185, 1.25], sorang: [130, 200, 1.2], jacheong: [118, 300, 1.6] }[key] || [125, 210, 1.25];
  const h = 120 * sh / Math.max(sw, sh) * focus[2] * (sh > sw ? 1.6 : 1.2);
  paintSprite(g, key, 60, h + 6 - (h * .02), h);
  return portraitCache[key] = c.toDataURL('image/png');
}

// ── 카메라 ──
const VIEW = { x0: 70, x1: 730, y0: 36, y1: 482 };
const cam = { s: 1, ox: 0, oy: 0, W: 1, H: 1, dpr: 1, lx0: 0, lx1: 800, ly0: 0, ly1: 600 };
function fitCanvas() {
  const r = canvas.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2);
  const W = Math.max(1, Math.round(r.width * dpr)), H = Math.max(1, Math.round(r.height * dpr));
  if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H }
  const small = r.width < 700, top = (small ? 40 : 52) * dpr, bot = (small ? 54 : 66) * dpr, avH = Math.max(50, H - top - bot);
  const s = Math.min(W / (VIEW.x1 - VIEW.x0), avH / (VIEW.y1 - VIEW.y0));
  Object.assign(cam, { s, dpr, W, H, ox: W / 2 - (VIEW.x0 + VIEW.x1) / 2 * s, oy: top + avH / 2 - (VIEW.y0 + VIEW.y1) / 2 * s });
  cam.lx0 = -cam.ox / s; cam.lx1 = (W - cam.ox) / s; cam.ly0 = -cam.oy / s; cam.ly1 = (H - cam.oy) / s;
  cam.topPad = top / s; cam.botPad = bot / s;
}
function toLogical(ev) {
  const r = canvas.getBoundingClientRect();
  return [((ev.clientX - r.left) * cam.dpr - cam.ox) / cam.s, ((ev.clientY - r.top) * cam.dpr - cam.oy) / cam.s];
}

// ── 기본 도형 ──
function p(x, y, z = 0) { return [400 + (x - y) * 26, 153 + (x + y) * 12.6 - z * 25] }
function tone(c, n) { const a = c.replace('#', ''); const rgb = [0, 2, 4].map(i => parseInt(a.slice(i, i + 2), 16)); return '#' + rgb.map(v => Math.max(0, Math.min(255, Math.round(n > 0 ? v + (255 - v) * n : v * (1 + n)))).toString(16).padStart(2, '0')).join('') }
function mix(c1, c2, k) { const f = c => [0, 2, 4].map(i => parseInt(c.replace('#', '').slice(i, i + 2), 16)); const a = f(c1), b = f(c2); return '#' + a.map((v, i) => Math.round(v + (b[i] - v) * k).toString(16).padStart(2, '0')).join('') }
function poly(pts, c, stroke) { ctx.fillStyle = c; ctx.beginPath(); pts.forEach((v, i) => i ? ctx.lineTo(...v) : ctx.moveTo(...v)); ctx.closePath(); ctx.fill(); if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = .7; ctx.stroke() } }
function oval(x, y, rx, ry, c) { ctx.fillStyle = c; ctx.beginPath(); ctx.ellipse(x, y, Math.max(.1, rx), Math.max(.1, ry), 0, 0, 7); ctx.fill() }
function rr(x, y, w, h, r, c) { ctx.fillStyle = c; ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(x, y, w, h, r); else ctx.rect(x, y, w, h); ctx.fill() }
function txt(s, x, y, size = 12, color = '#3f5b52', weight = 'bold') { ctx.fillStyle = color; ctx.font = `${weight} ${size}px Arial,"Malgun Gothic","Apple SD Gothic Neo",sans-serif`; ctx.textAlign = 'center'; ctx.fillText(s, x, y) }
function stud(x, y, z, c, r = .19) { const q = p(x, y, z); oval(q[0], q[1] + 1, r * 26, r * 12.6 + 2, tone(c, -.2)); oval(q[0], q[1] - 1, r * 26, r * 12.6, tone(c, .17)); ctx.strokeStyle = tone(c, .33); ctx.lineWidth = .8; ctx.beginPath(); ctx.ellipse(q[0], q[1] - 2, r * 21, r * 9, 0, Math.PI, Math.PI * 2); ctx.stroke() }
function boxRaw(x, y, z, dx, dy, dz, c, studs = false) {
  const a = p(x, y, z + dz), b = p(x + dx, y, z + dz), d = p(x, y + dy, z + dz), e = p(x + dx, y + dy, z + dz), bt = p(x + dx, y, z), dt = p(x, y + dy, z), et = p(x + dx, y + dy, z);
  poly([b, bt, et, e], tone(c, -.20), tone(c, -.27)); poly([d, e, et, dt], tone(c, -.07), tone(c, -.17));
  const g = ctx.createLinearGradient(a[0], a[1], e[0], e[1]); g.addColorStop(0, tone(c, .22)); g.addColorStop(1, tone(c, .04)); poly([a, b, e, d], g, tone(c, .16));
  if (studs) { for (let i = .5; i < dx; i++) for (let j = .5; j < dy; j++) stud(x + i, y + j, z + dz, c) }
}
// 보이는 두 벽면(남쪽 y+dy, 동쪽 x+dx)에 창문·간판을 붙이는 면 사각형
function faceRect(face, plane, u0, u1, z0, z1, c) {
  if (face === 'S') poly([p(u0, plane, z0), p(u1, plane, z0), p(u1, plane, z1), p(u0, plane, z1)], c);
  else poly([p(plane, u0, z0), p(plane, u1, z0), p(plane, u1, z1), p(plane, u0, z1)], c);
}

// ── 장면 상태 S: 매 프레임 새로 구성 ──
let queue = [], shadows = [], glows = [], smokes = [], hits = [], heads = {};
const S = {};
const fnCache = {};
function push(depth, fn) { queue.push({ depth, fn }) }
S.box = (x, y, z, dx, dy, dz, c, studs = false, o = {}) => {
  push(o.d ?? x + y + (dx + dy) / 2 + z * .01, () => { if (o.a != null && o.a < 1) { ctx.save(); ctx.globalAlpha = o.a; boxRaw(x, y, z, dx, dy, dz, c, studs); ctx.restore() } else boxRaw(x, y, z, dx, dy, dz, c, studs) })
};
// 시설 부품: 설치 진행도(S.b)에 따라 순서대로 위에서 내려와 '정확한 높이'에 고정됨
S.fb = (x, y, z, dx, dy, dz, c, studs = false, o = {}) => {
  const i = S._fi++; if (!S.built) return;
  if (S.b >= 1) return S.box(x, y, z, dx, dy, dz, c, studs, o);
  const n = fnCache[S.reg.id] || 30, k = S.b * n; if (i > k) return;
  const fr = Math.min(1, k - i), drop = (1 - fr) * 1.4;
  S.box(x, y, z + drop, dx, dy, dz, c, studs, { ...o, d: o.d ?? x + y + (dx + dy) / 2 + z * .01, a: (o.a ?? 1) * (.35 + .65 * fr) });
};
S.deco = (depth, fn) => push(depth, fn);
S.shadow = (x, y, rx = 1, ry = .6) => { const q = p(x, y, 0); shadows.push(() => oval(q[0] + 9, q[1] + 9, rx * 27, ry * 15, '#26473b20')) };
S.glow = (x, y, z, r, c = '#ffe9a2') => glows.push({ x, y, z, r, c });
S.smoke = (x, y, z, k = 1) => smokes.push({ x, y, z, k });
S.tile = (x, y, c) => boxRaw(x, y, 0, 1, 1, .1, c, false);
S.road = (x, y, dx, dy, c = '#e5dbc4') => { for (let i = x; i < x + dx; i++) for (let j = y; j < y + dy; j++) S.tile(i, j, (i + j) % 2 ? c : tone(c, -.03)) };
S.water = (x, y, dx, dy, c = '#78b9cb') => {
  for (let i = x; i < x + dx; i++) for (let j = y; j < y + dy; j++) {
    boxRaw(i, j, -.12, 1, 1, .12, (i + j) % 2 ? c : tone(c, .05));
    const ph = (S.t * .0012 + i * .7 + j * 1.3) % 1; boxRaw(i + .15 + ph * .4, j + .35, -.01, .4, .1, .01, tone(c, .45));
  }
};
S.tree = (x, y, s = 1, c = '#5fa888', sway = 0) => {
  S.shadow(x + .3, y + .3, s, s * .5); const w = sway * Math.sin(S.t * .006 + x) * .12;
  S.box(x + .23, y + .23, .1, .35, .35, 1.5 * s, '#ad805a'); S.box(x - .32 * s + w, y - .32 * s, 1.2 * s, 1.35 * s, 1.35 * s, .7 * s, c, true);
  S.box(x - .15 * s + w * 1.5, y - .15 * s, 1.9 * s, 1 * s, 1 * s, .6 * s, tone(c, .12), true); S.box(x + .06 * s + w * 2, y + .06 * s, 2.5 * s, .58 * s, .58 * s, .35 * s, tone(c, .26), false);
};
S.flowers = (x, y) => { for (let i = 0; i < 3; i++) { S.box(x + i * .26, y, .1, .16, .16, .25, '#84a977'); S.box(x + i * .26 - .04, y - .04, .35, .25, .25, .1, ['#f6c16c', '#f4a29f', '#f4ead0'][i]) } };
S.fence = (x, y, n = 3, c = '#f3e8ce') => { for (let i = 0; i < n; i++) S.box(x + i * .55, y, .1, .17, .17, .65, c, true); S.box(x, y, .46, n * .55, .12, .13, tone(c, -.03)) };
S.bench = (x, y, c = '#c49c74') => { S.box(x, y, .3, 1.2, .45, .12, c, true); S.box(x + .1, y + .1, .1, .15, .25, .2, tone(c, -.2)); S.box(x + .95, y + .1, .1, .15, .25, .2, tone(c, -.2)) };
S.house = (x, y, dx = 2.4, dy = 2, roof = '#d48670', wall = '#f4dfb6', o = {}) => {
  S.shadow(x + dx / 2, y + dy / 2, dx * .8, dy * .8); S.box(x - .1, y - .1, .1, dx + .2, dy + .2, .22, '#c5b28d'); S.box(x, y, .32, dx, dy, 1.9, wall, true);
  for (let i = 0; i < 3; i++) S.box(x - .17 + i * .29, y - .18 + i * .24, 2.22 + i * .27, dx + .34 - i * .58, dy + .36 - i * .48, .29, roof, i === 2);
  if (!o.noChimney) S.box(x + dx - .58, y + .13, 2.4, .35, .4, .75, '#e4d0b2', true);
  const lit = S.windowsLit ? '#ffe3a0' : '#7ebdce';
  S.box(x + .9, y + dy + .015, .34, .55, .08, 1.2, o.door || '#749990'); S.box(x + .2, y + dy + .025, 1.12, .48, .08, .67, '#fdf4d9'); S.box(x + .26, y + dy + .11, 1.2, .35, .05, .5, lit);
  S.box(x + dx + .025, y + .55, 1.12, .08, .65, .67, '#fdf4d9'); S.box(x + dx + .11, y + .62, 1.2, .04, .5, .5, S.windowsLit ? '#ffe9b0' : '#8bc5d2');
  if (S.windowsLit) { S.glow(x + .5, y + dy + .3, 1.4, 26, '#ffe2a0'); }
  return { roofTop: 3.05, depth: x + y + (dx + dy) / 2 }; // 지붕 최상단 높이 (태양광·감지기 설치 기준)
};
S.tower = (x, y, dx, dy, h, c, o = {}) => {
  S.shadow(x + dx / 2, y + dy / 2, dx * .8, dy * .8);
  push(x + y + (dx + dy) / 2, () => {
    boxRaw(x, y, .1, dx, dy, h, c, false); boxRaw(x - .05, y - .05, .1 + h, dx + .1, dy + .1, .18, tone(c, -.12), true);
    const lit = S.windowsLit, wc = lit ? '#ffe2a0' : (o.win || '#a9d3df');
    for (let z = .6; z < h - .3; z += .75) {
      for (let u = x + .25; u < x + dx - .3; u += .55) faceRect('S', y + dy + .01, u, u + .32, z, z + .42, (lit && ((u * 7 + z * 3) | 0) % 3 === 0) ? '#6b7d8f' : wc);
      for (let u = y + .25; u < y + dy - .3; u += .55) faceRect('E', x + dx + .01, u, u + .32, z, z + .42, tone(wc, -.12));
    }
  });
};
S.sign = (x, y, text, c = '#fffdf3') => S.deco(x + y + 2, () => { const q = p(x, y, 2.4); ctx.font = 'bold 9px Arial,"Malgun Gothic",sans-serif'; const w = ctx.measureText(text).width + 14; rr(q[0] - w / 2, q[1] - 9, w, 16, 6, c); txt(text, q[0], q[1] + 3, 9, '#3f5b52') });

// ── 사람·캐릭터 ──
// 배경 주민: 머리·몸통·팔·다리가 구분되는 블록 인형
S.minifig = (x, y, o = {}) => {
  const q = p(x, y, .12), ph = o.walk ? S.t * .012 + (o.k || 0) : 0, sw = o.walk ? Math.sin(ph) * 2.2 : 0, sc = o.scale || 1;
  S.shadow(x, y, .3, .18);
  push(x + y + .9, () => {
    ctx.save(); ctx.translate(q[0], q[1]); ctx.scale(o.flip ? -sc : sc, sc);
    const skin = o.skin || '#f3c9a0', shirt = o.shirt || '#5f8fb7', pants = o.pants || '#3f4f63';
    rr(-4.5 + sw * .3, -11, 3.6, 11, 1.2, pants); rr(.9 - sw * .3, -11, 3.6, 11, 1.2, tone(pants, -.15));
    rr(-5 + sw * .3, -1.5, 4.5, 2, 1, '#3a3a3a'); rr(.6 - sw * .3, -1.5, 4.5, 2, 1, '#3a3a3a');
    poly([[-6.5, -21], [6.5, -21], [5.5, -10.5], [-5.5, -10.5]], shirt); rr(-6, -12, 12, 2, 1, tone(pants, .1));
    ctx.save(); ctx.translate(-7, -20); ctx.rotate((o.wave ? -2.2 + Math.sin(S.t * .01) * .4 : -sw * .08)); rr(-1.6, 0, 3.2, 9, 1.5, tone(shirt, -.1)); oval(0, 9.5, 1.8, 1.8, skin); ctx.restore();
    ctx.save(); ctx.translate(7, -20); ctx.rotate(sw * .08); rr(-1.6, 0, 3.2, 9, 1.5, tone(shirt, -.1)); oval(0, 9.5, 1.8, 1.8, skin); ctx.restore();
    rr(-2, -23.5, 4, 3, 1, skin); oval(0, -28.5, 6, 6, skin);
    ctx.fillStyle = o.hair || '#4a3a2c'; ctx.beginPath(); ctx.ellipse(0, -30.5, 6.4, 4.5, 0, Math.PI, 0); ctx.fill();
    if (o.hat) { rr(-7, -33.5, 14, 2.2, 1, o.hat); rr(-4.5, -37.5, 9, 4.5, 2, o.hat) }
    oval(-2.1, -28.3, .8, 1, '#2d2a26'); oval(2.1, -28.3, .8, 1, '#2d2a26');
    ctx.strokeStyle = '#a0533f'; ctx.lineWidth = .8; ctx.beginPath(); if (o.sad) ctx.arc(0, -24.4, 1.8, Math.PI * 1.15, Math.PI * 1.85); else ctx.arc(0, -26.4, 1.8, .2, Math.PI - .2); ctx.stroke();
    if (o.cheek !== false) { oval(-3.6, -26.5, 1.1, .7, '#f2a08f88'); oval(3.6, -26.5, 1.1, .7, '#f2a08f88') }
    if (o.umbrella) { ctx.fillStyle = o.umbrella; ctx.beginPath(); ctx.ellipse(0, -40, 11, 6, 0, Math.PI, 0); ctx.fill(); ctx.strokeStyle = '#555'; ctx.beginPath(); ctx.moveTo(0, -40); ctx.lineTo(0, -22); ctx.stroke() }
    ctx.restore();
  });
};
// 사용자 제공 캐릭터: id로 말풍선·클릭 판정에 등록
S.actor = (id, x, y, key, o = {}) => {
  if (!sprReady(key)) return; const def = SPR[key], h = (o.h || def.h) * (o.scale || 1);
  S.shadow(x, y, key === 'chiefLying' ? 1.4 : .6, .34);
  const q = p(x, y, .12), bob = def.float ? Math.sin(S.t * .0025 + x) * 3 : (o.hop ? -Math.abs(Math.sin(S.t * .012)) * 5 : Math.sin(S.t * .002 + x) * .5);
  const width = h * def.rect[2] / def.rect[3], top = q[1] + bob - h;
  heads[id] = { x: q[0] + (key === 'chiefLying' ? -width * .25 : 0), y: key === 'chiefLying' ? top + h * .25 : top + 4, width, bottom: q[1] + bob, name: o.name || def.name };
  hits.push({ id, x0: q[0] - width / 2, x1: q[0] + width / 2, y0: top, y1: q[1] + 4, d: x + y });
  push(x + y + 1.05, () => {
    if (o.ring) { ctx.save(); ctx.strokeStyle = o.ring; ctx.lineWidth = 2.5; ctx.setLineDash([5, 4]); ctx.lineDashOffset = -S.t * .02; ctx.beginPath(); ctx.ellipse(q[0], q[1] + 2, width * .42, 9, 0, 0, 7); ctx.stroke(); ctx.restore() }
    paintSprite(ctx, key, q[0], q[1] + bob, h, o.flip);
    if (o.mark) { const my = top - 6 + Math.sin(S.t * .006) * 2; rr(q[0] - 8, my - 15, 16, 16, 8, o.mark === '✓' ? '#6e9473' : '#e8aa49'); txt(o.mark, q[0], my - 3, 11, '#fff') }
  });
};

// ── 차량 ──
S.truck = (x, y, o = {}) => {
  const c = o.color || '#f4f1e6', a = o.a ?? 1, o2 = { a };
  S.shadow(x + 1.1, y + .45, 1.4, .5);
  S.box(x, y, .2, .75, .9, .8, '#4f9a83', false, o2); S.box(x - .03, y + .1, .55, .05, .7, .35, '#a9d8e3', false, o2);
  S.box(x + .78, y - .02, .2, 1.55, .94, 1.1, c, true, o2);
  S.deco(x + y + 1.6, () => { if (a < .05) return; ctx.save(); ctx.globalAlpha = a; faceRect('S', y + .93, x + 1, x + 2.2, .55, .95, '#e8aa49'); const q = p(x + 1.6, y + .93, .62); txt('조달', q[0], q[1] - 1, 8, '#fff'); ctx.restore() });
  for (const wx of [x + .2, x + 1.75]) { S.box(wx, y - .06, .02, .38, .12, .36, '#4a5558', false, o2); S.box(wx, y + .86, .02, .38, .12, .36, '#4a5558', false, o2) }
  if (o.cargo) for (let i = 0; i < o.cargo; i++) S.box(x + 1 + i * .45, y + .2, 1.32, .38, .5, .32, '#d8a868', true, o2);
};
S.car = (x, y, c = '#e07a5f', o = {}) => {
  S.shadow(x + .55, y + .3, .7, .35);
  S.box(x, y, .15, 1.15, .62, .35, c, false); S.box(x + .25, y + .06, .5, .6, .5, .28, tone(c, .25), false); S.box(x + .22, y + .05, .58, .02, .52, .18, '#b8e0ea');
  for (const wx of [x + .15, x + .8]) { S.box(wx, y - .04, .02, .24, .08, .24, '#3e4a4c'); S.box(wx, y + .6, .02, .24, .08, .24, '#3e4a4c') }
  if (o.lights) S.glow(x - .1, y + .3, .4, 18, '#fff4c4');
};
S.bus = (x, y, c = '#4c9a7a') => {
  S.shadow(x + 1.4, y + .45, 1.7, .5); S.box(x, y, .2, 2.9, .9, 1.05, c, true);
  for (let i = 0; i < 4; i++) S.box(x + .25 + i * .65, y + .91, .7, .45, .03, .35, '#bfe4ec');
  S.box(x - .02, y + .12, .65, .04, .66, .4, '#bfe4ec');
  for (const wx of [x + .3, x + 2.2]) { S.box(wx, y - .05, .02, .38, .12, .36, '#3e4a4c'); S.box(wx, y + .85, .02, .38, .12, .36, '#3e4a4c') }
};
S.crate = (x, y, z, c = '#d8a868') => { S.box(x, y, z, .42, .42, .36, c, true); S.box(x + .19, y - .01, z, .05, .44, .37, tone(c, -.15)) };

// ── 렌더 루프 ──
let sceneOn = true, confettiAt = -1e9;
function drawBoard(land, t) {
  // 받침판(두꺼운 블록 디스플레이) + 바닥 타일
  oval(400, 466, 300, 44, '#35574814');
  boxRaw(0, 0, -.85, 12, 12, .8, tone(land, -.14), false);
  for (let x = 0; x < 12; x++) for (let y = 0; y < 12; y++) { const c = (x + y) % 2 ? tone(land, .025) : land; boxRaw(x, y, 0, 1, 1, .1, c, false); if ((x * 7 + y * 3) % 2 === 0) stud(x + .5, y + .5, .11, c, .16) }
}
function weather(kind, k, t) {
  const L = cam.lx0, R = cam.lx1, T = cam.ly0, B = cam.ly1, w = R - L, h = B - T;
  if (kind === 'rain' || kind === 'storm') {
    const n = 25 + k * 90; ctx.strokeStyle = '#5f8a9f66'; ctx.lineWidth = 1.1;
    for (let i = 0; i < n; i++) { const x = L + ((i * 103.7 + t * .03 * (1 + k)) % w), y = T + ((i * 67.3 + t * .5) % h); ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 3 - k * 3, y + 11); ctx.stroke() }
    if (k > .6) { ctx.fillStyle = `rgba(40,60,80,${.12 * k})`; ctx.fillRect(L, T, w, h) }
  }
  if (kind === 'snow' || kind === 'cold') {
    const n = (kind === 'cold' ? 15 : 35) + k * 90;
    for (let i = 0; i < n; i++) { const x = L + ((i * 97.3 + Math.sin(t * .001 + i) * 18 + t * .01 * k) % w), y = T + ((i * 53.1 + t * (.04 + k * .04)) % h); oval(x, y, 1.8 + (i % 3) * .5, 1.8 + (i % 3) * .5, '#ffffffdd') }
    if (kind === 'cold') { ctx.fillStyle = `rgba(150,190,230,${.08 + .1 * k})`; ctx.fillRect(L, T, w, h) }
    if (kind === 'snow' && k > .6) { ctx.fillStyle = `rgba(235,242,250,${.18 * k})`; ctx.fillRect(L, T, w, h) }
  }
  if (kind === 'wind') {
    ctx.strokeStyle = '#ffffffaa'; ctx.lineWidth = 1.4; const n = 10 + k * 30;
    for (let i = 0; i < n; i++) { const x = L + ((i * 131 + t * (.25 + k * .4)) % (w + 120)) - 60, y = T + 60 + (i * 47) % (h - 120); ctx.beginPath(); ctx.moveTo(x, y); ctx.quadraticCurveTo(x + 18, y - 5, x + 40 + k * 30, y + 2); ctx.stroke() }
    if (k > .5) { ctx.strokeStyle = '#5f8a9f55'; ctx.lineWidth = 1; for (let i = 0; i < 70 * k; i++) { const x = L + ((i * 103.7 + t * .4) % w), y = T + ((i * 67.3 + t * .45) % h); ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 10, y + 8); ctx.stroke() } ctx.fillStyle = `rgba(50,70,90,${.15 * k})`; ctx.fillRect(L, T, w, h) }
  }
  if (kind === 'heat' || kind === 'dry') {
    const g = ctx.createRadialGradient(R - 70, T + 60, 5, R - 70, T + 60, 160); g.addColorStop(0, `rgba(255,214,120,${.55 + .3 * k})`); g.addColorStop(1, 'rgba(255,214,120,0)'); ctx.fillStyle = g; ctx.fillRect(L, T, w, h);
    ctx.fillStyle = `rgba(255,170,90,${.05 + .1 * k})`; ctx.fillRect(L, T, w, h);
  }
}
function heatShimmer(k, t) { for (let i = 0; i < 4 + k * 4; i++) { const q = p(2 + i * 1.3, 9.5 - (i % 3), 1.5); ctx.strokeStyle = '#d99a5a66'; ctx.lineWidth = 1.6; ctx.beginPath(); const o = Math.sin(t * .003 + i) * 4; ctx.moveTo(q[0], q[1]); ctx.bezierCurveTo(q[0] - 8 + o, q[1] - 12, q[0] + 8 - o, q[1] - 24, q[0], q[1] - 36); ctx.stroke() } }
function drawBubble(id, msg, fill) {
  const head = heads[id]; if (!head) return;
  ctx.font = 'bold 11px Arial,"Malgun Gothic",sans-serif';
  // 긴 대사는 두 줄로 나눔
  let lines = [msg]; if (ctx.measureText(msg).width > 230) { const words = msg.split(' '); let a = '', b = ''; for (const wd of words) { if (ctx.measureText(a + wd).width < ctx.measureText(msg).width / 2 + 10 || !a) a += (a ? ' ' : '') + wd; else b += (b ? ' ' : '') + wd } lines = [a, b] }
  const bw = Math.max(110, ...lines.map(l => ctx.measureText(l).width)) + 26, bh = 22 + lines.length * 15, gap = 12;
  const minX = cam.lx0 + 8 + bw / 2, maxX = cam.lx1 - 8 - bw / 2;
  let cx = Math.max(minX, Math.min(maxX, head.x)), top = head.y - gap - bh;
  // 이웃 캐릭터의 얼굴을 가리지 않도록 옆으로 비킴
  for (const [key, o] of Object.entries(heads)) { if (key === id) continue; const ov = top + bh > o.y - 4 && top < o.bottom - 10 && cx + bw / 2 > o.x - o.width * .4 && cx - bw / 2 < o.x + o.width * .4; if (ov) { const right = o.x + o.width * .4 + bw / 2 + 8, left = o.x - o.width * .4 - bw / 2 - 8; if (right < maxX && Math.abs(right - head.x) < bw) cx = right; else if (left > minX && Math.abs(left - head.x) < bw) cx = left; else top = Math.min(top, o.y - bh - 14) } }
  top = Math.max(cam.ly0 + cam.topPad - 4, top);
  ctx.shadowColor = '#26483c30'; ctx.shadowBlur = 10; rr(cx - bw / 2, top, bw, bh, 12, fill); ctx.shadowBlur = 0;
  const tb = Math.max(cx - bw / 2 + 16, Math.min(cx + bw / 2 - 16, head.x)); poly([[tb - 6, top + bh - 1], [tb + 6, top + bh - 1], [head.x, Math.max(top + bh + 4, head.y - 3)]], fill);
  ctx.font = 'bold 9px Arial,"Malgun Gothic",sans-serif'; ctx.textAlign = 'center'; ctx.fillStyle = '#84957a'; ctx.fillText(head.name, cx, top + 13);
  lines.forEach((l, i) => txt(l, cx, top + 29 + i * 15, 11, '#395b49'));
}
function frame() {
  requestAnimationFrame(frame);
  if (!sceneOn) return;
  fitCanvas();
  const t = performance.now(), st = sceneState(t); // game.js가 현재 진행 상태를 제공
  const reg = st.reg;
  queue = []; shadows = []; glows = []; smokes = []; hits = []; heads = {};
  Object.assign(S, st, { t, _fi: 0 });
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const g = ctx.createLinearGradient(0, 0, 0, cam.H); g.addColorStop(0, reg.sky[0]); g.addColorStop(1, reg.sky[1]); ctx.fillStyle = g; ctx.fillRect(0, 0, cam.W, cam.H);
  ctx.setTransform(cam.s, 0, 0, cam.s, cam.ox, cam.oy);
  drawBoard(S.landColor || reg.land, t);
  SCENES[reg.id](S);
  fnCache[reg.id] = Math.max(1, S._fi);
  drawActors(S);
  shadows.forEach(f => f()); queue.sort((a, b) => a.depth - b.depth).forEach(o => o.fn());
  // 연기
  for (const s of smokes) for (let i = 0; i < 5; i++) { const k = ((t * .0005 + i * .2) % 1), q = p(s.x, s.y, s.z + k * 3 * s.k); oval(q[0] + k * 20, q[1], 6 + k * 14, 5 + k * 10, `rgba(120,120,120,${(1 - k) * .35 * s.k})`) }
  // 밤 장면: 어둡게 덮은 뒤 불빛을 더함
  if (S.dark > 0) { ctx.fillStyle = `rgba(18,30,58,${S.dark})`; ctx.fillRect(cam.lx0, cam.ly0, cam.lx1 - cam.lx0, cam.ly1 - cam.ly0) }
  if (glows.length) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; for (const gl of glows) { const q = p(gl.x, gl.y, gl.z), gg = ctx.createRadialGradient(q[0], q[1], 0, q[0], q[1], gl.r); gg.addColorStop(0, gl.c + 'aa'); gg.addColorStop(1, gl.c + '00'); ctx.fillStyle = gg; ctx.beginPath(); ctx.ellipse(q[0], q[1], gl.r, gl.r * (gl.flat ? .5 : 1), 0, 0, 7); ctx.fill() } ctx.restore() }
  weather(reg.wx === 'night' ? '' : reg.wx, S.storm, t);
  if ((reg.wx === 'heat' || reg.wx === 'dry') && !S.active) heatShimmer(S.storm, t);
  // 말풍선
  if (S.say && heads[S.say.id]) drawBubble(S.say.id, S.say.text, S.say.good ? '#f2fbeaff' : '#fffdf4ff');
  // 축하 색종이
  const age = t - confettiAt; if (age < 1500) { const k = age / 1500; for (let i = 0; i < 36; i++) { ctx.save(); ctx.globalAlpha = 1 - k; ctx.translate(400 + Math.sin(i * 2.4) * (50 + k * 270), 250 - Math.cos(i * 1.7) * (50 + k * 150) + k * 80); ctx.rotate(i + k * 4); rr(-3, -3, 6, 9, 1, ['#ebbd74', '#8ebbaa', '#d5a2b4', '#7fa6d6'][i % 4]); ctx.restore() } }
  if (S.travel) { const k = S.travel; ctx.fillStyle = `rgba(239,244,237,${Math.min(1, k * 1.4)})`; ctx.fillRect(cam.lx0, cam.ly0, cam.lx1 - cam.lx0, cam.ly1 - cam.ly0); ctx.globalAlpha = Math.min(1, k * 1.4); paintSprite(ctx, 'deer', 400 + Math.sin(t * .01) * 4, 268, 90); txt(S.travelText, 400, 300, 20); txt('필요한 곳마다, 조달이 찾아갑니다.', 400, 326, 12, '#81958a'); ctx.globalAlpha = 1 }
}
canvas.addEventListener('click', ev => { const [x, y] = toLogical(ev); const h = hits.filter(o => x >= o.x0 && x <= o.x1 && y >= o.y0 && y <= o.y1).sort((a, b) => b.d - a.d)[0]; if (h) onActorClick(h.id) });
canvas.addEventListener('mousemove', ev => { const [x, y] = toLogical(ev); const h = hits.some(o => x >= o.x0 && x <= o.x1 && y >= o.y0 && y <= o.y1 && clickable(o.id)); canvas.style.cursor = h ? 'pointer' : 'default' });
