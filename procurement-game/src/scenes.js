// ── 17개 지역 장면 ──────────────────────────────────────────────
// S.built: 설치 시작 이후 / S.b: 조립 진행도(0~1) / S.active: 시설 작동 / S.late: 납기 지연
// S.q: 'low'(성능 미달) 또는 'ok' / S.storm: 기상 강도(0~1) / S.pri: 선택한 예산 우선순위
const LAYOUT_DEFAULT = { lane: 8.5, stop: 5, res: [[2.3, 10.9], [5.1, 11.1], [7.9, 10.9]], team: [[10.9, 3.4], [10.9, 6.4]], crew: [7.4, 7.2], cars: true };
const LAYOUT = {
  seoul: { stop: 5.2 },
  busan: { stop: 4.2, crew: [6.3, 5.0] },
  daegu: { stop: 4.6 },
  incheon: { stop: 5.6, crew: [9.6, 7.3] },
  gwangju: { stop: 5.6, crew: [9.8, 7.0] },
  daejeon: { stop: 4.8, crew: [9.2, 6.9] },
  ulsan: { stop: 5.2, crew: [8.4, 6.6] },
  sejong: { stop: 2.0, crew: [9.6, 7.0], cars: false },
  gyeonggi: { stop: 1.6, crew: [9.4, 6.8], cars: false },
  gangwon: { stop: 6.8, crew: [5.6, 7.0], cars: false },
  chungbuk: { stop: 6.4, crew: [8.7, 6.0] },
  chungnam: { stop: 6.6, crew: [9.0, 6.5] },
  jeonbuk: { stop: 5.6, crew: [8.6, 6.9] },
  jeonnam: { stop: 6.0, lane: 8.2, res: [[2.4, 10.2], [5.0, 10.3], [7.6, 10.2]], crew: [8.8, 6.6], team: [[10.2, 3.4], [10.2, 6.4]], cars: false },
  gyeongbuk: { stop: 6.4, crew: [8.4, 6.6], res: [[4.6, 6.6], [5.6, 11.0], [8.2, 10.9]] },
  gyeongnam: { stop: 6.4, crew: [9.8, 6.4] },
  jeju: { stop: 6.2, crew: [8.8, 6.4] }
};
function L(id) { return { ...LAYOUT_DEFAULT, ...(LAYOUT[id] || {}) } }

// 공통: 예산을 '편의시설 우선'으로 쓴 경우 작은 편의시설이 함께 생김
function comfortExtra(S, x, y) { if (S.active && S.pri === 'comfort') { S.bench(x, y, '#c49c74'); S.flowers(x + .1, y + .7) } }
function upkeepExtra(S, x, y) { if (S.active && S.pri === 'upkeep') { S.box(x, y, .1, .5, .4, .6, '#e9e2c8', true); S.box(x + .08, y + .41, .3, .34, .02, .3, '#6e9473') } }
const people = ['#5f8fb7', '#e07a5f', '#7fb069', '#c98bb9', '#e8aa49', '#6c8ea3'];

const SCENES = {
seoul(S) {
  S.road(0, 8, 12, 2, '#b9b3a6'); S.road(3, 5, 7, 3, '#e6dfcf');
  for (let i = 0; i < 5; i++) S.box(4.7 + i * .5, 8.1, .1, .28, 1.8, .03, '#f6f3ea');
  S.tower(.2, .2, 2.4, 2.2, 4.4, '#9fb4c4'); S.tower(3.1, .3, 2.2, 1.8, 3.2, '#d6c2a5'); S.tower(8.4, .3, 2.8, 2.2, 3.8, '#b9a5c4'); S.tower(.2, 3.3, 1.9, 2.4, 2.6, '#c9b7a0'); S.tower(5.8, .4, 2.1, 1.6, 2.4, '#a7c4b0');
  S.tree(10.4, 4.6, .8); S.tree(1.2, 10.6, .7);
  const pos = S.q === 'low' ? [[3.6, 5.3], [7.4, 5.3]] : [[3.4, 5.2], [5.6, 5.2], [7.8, 5.2]];
  for (const [x, y] of pos) {
    S.fb(x + .7, y + .7, .1, .16, .16, 2.35, '#7d8a8f');
    if (S.q !== 'low') S.fb(x + .62, y + .62, 1.4, .32, .32, .28, '#e8aa49');
    S.fb(x, y, 2.45, 1.55, 1.55, .16, S.q === 'low' ? '#d9c08a' : '#4fb3a0', true); S.fb(x + .5, y + .5, 2.61, .55, .55, .14, S.q === 'low' ? '#c4a76c' : '#3d8f80');
  }
  comfortExtra(S, 4.8, 6.6); upkeepExtra(S, 9.4, 6.4);
  const shaded = S.active;
  [[3.9, 6.3], [6.0, 6.5], [8.1, 6.3], [4.8, 7.4]].forEach(([x, y], i) => S.minifig(x, y, { shirt: people[i], sad: !shaded || (S.late && i === 3), k: i }));
},
busan(S) {
  S.water(0, 0, 12, 2); S.road(0, 8, 12, 2, '#cdbf9e');
  for (let x = 0; x < 12; x++) S.box(x, 2, 0, 1, 1.1, .16, x % 2 ? '#b98d5f' : '#c49a6c');
  const bob = Math.sin(S.t * .002) * .08 * (1 + S.storm * 2);
  S.box(2.2, .3, -.05 + bob, 2, .9, .35, '#f4f1e6', true); S.box(2.8, .45, .3 + bob, .8, .6, .45, '#5b8fb0'); S.box(7.5, .5, -.05 - bob, 2.4, .8, .3, '#e07a5f', true);
  S.house(9.2, 4.3, 2.2, 2, '#5b8fb0', '#f4e6c8'); S.tree(1, 5.5, .8); S.box(.6, 4.2, .1, 1.4, .9, .9, '#d8a868', true);
  if (S.storm > .5 && !S.active) for (let i = 0; i < 6; i++) { const ph = (S.t * .0015 + i * .3) % 1; S.box(i * 2 + ph, 1.6, .1, .7, .3, .2 + Math.sin(ph * 3.1) * .6, '#ffffff', false, { a: .6 }) }
  // 시설: 난간 + 구명장비함
  const n = S.q === 'low' ? 0 : 9;
  for (let i = 0; i < n; i++) S.fb(.8 + i * 1.2, 2.1, .16, .14, .14, .9, '#e9e4d6');
  if (n) { S.fb(.8, 2.1, .95, 9.8, .1, .1, '#f2b84b'); S.fb(.8, 2.1, .62, 9.8, .08, .08, '#f2b84b') }
  for (const x of [3.2, 6.8]) { S.fb(x, 2.6, .16, .7, .5, 1.1, '#e05a3f', true); S.fb(x + .1, 3.11, .45, .5, .03, .55, '#fff4e4'); S.fb(x + .18, 3.15, .55, .34, .03, .34, '#ff8a3d') }
  comfortExtra(S, 4.6, 4.6); upkeepExtra(S, 8.2, 4.8);
  [[3, 4.5], [5.6, 3.6], [8, 4.2]].forEach(([x, y], i) => S.minifig(x, y, { shirt: people[i + 1], sad: !S.active, walk: S.active, k: i }));
},
daegu(S) {
  S.road(0, 8, 12, 2, '#d3c4a8'); S.road(3, 3.6, 6, 4, '#e3d6bd');
  S.house(.4, 3.2, 2.2, 2.2, '#c86f55', '#f4dcb8'); S.house(.4, .4, 2.4, 2, '#d9a35f', '#f1dfb4'); S.house(9.3, 3.3, 2.2, 2.2, '#8fa7c2', '#f3e2c0'); S.house(9.4, .4, 2.2, 2, '#c99a7a', '#f2e0c2');
  S.box(3.4, .6, .1, 4.8, 1.6, 1.5, '#e4cfae', true); S.sign(5.8, 1.4, '달구벌 시장');
  const x = 4.4, y = 4.0;
  S.fb(x, y, .1, 3.4, 2.4, .16, '#d9d4c7');
  for (const [a, b] of [[0, 0], [3.2, 0], [0, 2.2], [3.2, 2.2]]) S.fb(x + a, y + b, .26, .2, .2, 2, '#8a9ea8');
  S.fb(x + .2, y + .05, .26, 3, .06, 2, '#bfe6f0', false, { a: .38 }); S.fb(x + .05, y + .2, .26, .06, 2, 2, '#bfe6f0', false, { a: .38 });
  S.fb(x + .5, y + .8, .26, 2.2, .5, .4, '#7fb8d6', true);
  S.fb(x + 3.35, y + .2, .26, .06, 2, 2, '#bfe6f0', false, { a: .3 });
  S.fb(x - .15, y - .15, 2.26, 3.7, 2.7, .26, S.q === 'low' ? '#d8b47c' : '#79b8d8', true);
  if (S.q !== 'low') S.fb(x + 1.3, y + .8, 2.52, 1, .8, .45, '#eef3f5', true, { d: x + y + 3.2 });
  if (S.active) { S.glow(x + 1.7, y + 1.2, 1, S.q === 'low' ? 30 : 60, '#bfe9ff'); for (let i = 0; i < 4; i++) S.minifig(x + .8 + i * .7, y + 1.6 + (i % 2) * .3, { shirt: people[i], k: i }) }
  else[[4.2, 7.6], [6.4, 7.4], [8.6, 7.7]].forEach(([a, b], i) => S.minifig(a, b, { shirt: people[i + 2], sad: true, k: i }));
  comfortExtra(S, 8.2, 6.6); upkeepExtra(S, 3.3, 6.8);
},
incheon(S) {
  S.water(0, 0, 12, 1.5, '#6fa8bd'); S.road(0, 8, 12, 2, '#a9a79d');
  S.house(.5, 2.2, 2.3, 2.2, '#5b8f9e', '#efe2c9'); S.house(3.6, 2.0, 2.4, 2.4, '#d48670', '#f4dfb6'); S.house(6.9, 2.2, 2.2, 2.2, '#8ba06e', '#f1dfb4'); S.house(9.6, 2.0, 2, 2.3, '#c99a7a', '#efe0c4');
  for (let x = 0; x < 12; x++) for (let y = 6; y < 8; y++) S.tile(x, y, '#c9cdd0');
  if (!S.active || S.late) for (let i = 0; i < 7; i++) { if (S.active && i % 2) continue; const q = [1 + i * 1.6, 6.5 + (i % 2) * .8]; S.deco(q[0] + q[1], () => { const c = p(q[0], q[1], .11); oval(c[0], c[1], 22, 8, '#8fc1d6aa'); oval(c[0] - 5, c[1] - 2, 8, 2, '#ffffff88') }) }
  for (let i = 0; i < 12; i++) { S.fb(i, 6.05, .1, 1, 1.9, .08, i % 2 ? '#c46f4f' : '#b8654a', true); if (i % 3 === 1) S.fb(i, 6.9, .18, 1, .25, .02, '#f2c94c') }
  if (S.q !== 'low') { for (let i = 0; i < 6; i++) S.fb(.6 + i * 2, 5.85, .1, .12, .12, .8, '#8a9ea8'); S.fb(.6, 5.85, .9, 10.2, .1, .08, '#e8aa49') }
  comfortExtra(S, 4.6, 4.8); upkeepExtra(S, 8.4, 4.9);
  [[2.6, 6.8], [6.4, 7.2], [9.4, 6.7]].forEach(([x, y], i) => S.minifig(x, y, { shirt: people[i], umbrella: ['#e07a5f', '#5f8fb7', '#e8aa49'][i], walk: S.active, sad: !S.active, k: i }));
},
gwangju(S) {
  S.dark = S.active ? (S.q === 'low' ? .38 : .26) : .52; S.windowsLit = true;
  S.road(0, 8, 12, 2, '#cbbfa7'); S.road(4, 3, 2, 5, '#cbbfa7');
  S.house(.4, 3.4, 2.6, 2.4, '#ce8066', '#f5d9ab'); S.house(.5, .4, 2.2, 2, '#b0b495', '#f1dfb4'); S.house(7, 3.2, 3, 2.6, '#7c8fb3', '#f1e3c3'); S.house(7.4, .3, 2.4, 2, '#c99a7a', '#efe0c4');
  S.sign(8.5, 4.2, '빛고을초'); S.tree(11, 7, .7); S.tree(1.4, 10.8, .7);
  for (let i = 0; i < 8; i++) S.box(i * .25 + 10, .6 + (i % 3), 6 + (i % 4) * .4, .05, .05, .05, '#fff7d6');
  const xs = [1.6, 4.4, 7.2, 10.0];
  for (const x of xs) {
    S.fb(x, 7.55, .1, .18, .18, 2.8, '#566f78'); S.fb(x - .3, 7.5, 2.75, .7, .28, .1, '#566f78');
    S.fb(x - .38, 7.45, 2.58, .42, .38, .17, '#fff1c0', true);
    if (S.q !== 'low') S.fb(x - .3, 7.3, 3.0, .75, .65, .07, '#2f5c86');
    if (S.active) { S.glow(x - .2, 8.3, .1, S.q === 'low' ? 34 : 62, '#ffe9a2'); S.glow(x - .2, 7.6, 2.6, 22, '#fff6d0') }
  }
  comfortExtra(S, 4.4, 1.2); upkeepExtra(S, 6.2, 5.4);
  [[4.6, 9.2], [5.6, 9.4]].forEach(([x, y], i) => S.minifig(x + (S.active ? Math.sin(S.t * .0008) * 1.5 : 0), y, { shirt: ['#f2b84b', '#7fb069'][i], hat: '#f2d24c', walk: S.active, sad: !S.active, k: i, scale: .85 }));
},
daejeon(S) {
  S.road(0, 8, 12, 2, '#d8cfbd'); S.road(2.5, 4.4, 7, 3.4, '#e9e1cf');
  S.house(2.6, .6, 5, 3, '#7c74c4', '#f3e7cf', { door: '#5a5296' }); S.sign(5.1, 2.1, '한밭 작은도서관'); S.tree(.9, 1.2, .9); S.tree(9.8, 1.4, .85, '#7fb069'); S.tree(10.6, 5.6, .7);
  if (!S.active) { S.box(3.2, 4.6, .1, .7, .5, 1.1, '#9aa0a3'); S.box(3.25, 5.11, .6, .6, .02, .4, '#4a4f52'); S.sign(3.5, 4.9, '고장'); }
  // 시설: 정보검색 키오스크 + 독서 부스
  S.fb(3.4, 4.7, .1, .6, .5, 1.3, '#f4f1e6', true); S.fb(3.46, 5.21, .7, .48, .02, .5, '#5aa0c8');
  if (S.q !== 'low') { S.fb(4.6, 4.7, .1, .6, .5, 1.3, '#f4f1e6', true); S.fb(4.66, 5.21, .7, .48, .02, .5, '#5aa0c8') }
  const bx = 6.0, by = 4.6; S.fb(bx, by, .1, 2.8, 2, .12, '#d9c7a5');
  for (const [a, b] of [[0, 0], [2.6, 0], [0, 1.8], [2.6, 1.8]]) S.fb(bx + a, by + b, .22, .18, .18, 1.9, '#9c7f5e');
  S.fb(bx + .2, by + .1, .22, 2.4, .35, 1.3, '#b58a5c', true);
  for (let i = 0; i < 5; i++) S.fb(bx + .3 + i * .45, by + .46, .5 + (i % 2) * .4, .3, .02, .3, ['#e07a5f', '#5f8fb7', '#e8aa49', '#7fb069', '#c98bb9'][i]);
  S.fb(bx - .15, by - .15, 2.12, 3.1, 2.3, .22, '#7c74c4', true);
  comfortExtra(S, 6.3, 6.8); upkeepExtra(S, 9.3, 6.8);
  if (S.active) [[6.6, 5.9], [7.4, 6.1], [3.7, 5.6], [8.2, 5.8]].forEach(([x, y], i) => S.minifig(x, y, { shirt: people[i], k: i }));
},
ulsan(S) {
  S.road(0, 8, 12, 2, '#a9a99f'); S.road(0, 5.4, 12, 2.6, '#c4c4bb');
  const fac = (x, y, dx, dy, c) => { S.box(x, y, .1, dx, dy, 2.1, c, false); for (let i = 0; i < dx; i += 1) S.box(x + i, y, 2.2, .9, dy, .35 + (i % 2) * .15, tone(c, -.12), true) };
  fac(.4, .6, 4, 2.6, '#c9ccc5'); fac(5.6, .4, 3.4, 2.2, '#d2c6b3');
  S.box(9.8, .5, .1, .6, .6, 4.2, '#b1b5ad', true); S.box(9.75, .45, 3.6, .7, .7, .25, '#d0533f'); S.box(10.8, 2.4, .1, 1, 1, 1.6, '#9aa6ae', true);
  for (let i = 0; i < 9; i++) S.box(.4 + i * 1.2, 3.6, 1.2, 1.1, .25, .25, '#8a9ea8');
  if (!S.active || S.late) { S.smoke(2.6, 1.6, 2.6, S.late && S.active ? .5 : 1); if (!S.active) S.smoke(7.1, 1.4, 2.6, .8) }
  else S.smoke(10.1, .8, 4.3, .4);
  // 시설: 지붕 위 감지기(지붕보다 나중에 그림) + 경보 기둥
  const roofD = 7;
  for (const [x, y] of [[1.2, 1.6], [3.2, 1.6], [6.4, 1.2], [8.0, 1.2]]) S.fb(x, y, 2.75, .3, .3, .16, '#f4f1e6', true, { d: roofD + x * .01 });
  if (S.q !== 'low') for (const x of [2.2, 6.2, 9.0]) { S.fb(x, 5.0, .1, .16, .16, 2.2, '#566f78'); S.fb(x - .1, 4.9, 2.3, .36, .36, .36, '#e0533f', true); if (S.active && S.storm > .5 && Math.sin(S.t * .012) > 0) S.glow(x, 5, 2.5, 34, '#ff5a3c') }
  S.fb(4.6, 5.6, .1, .45, .45, .8, '#d0533f', true);
  comfortExtra(S, 6.8, 6.2); upkeepExtra(S, 3.0, 6.3);
  [[1.8, 6.2], [4.0, 6.6], [8.2, 6.3]].forEach(([x, y], i) => S.minifig(x, y, { shirt: '#f2b84b', hat: '#f4f1e6', pants: '#4f6278', walk: S.active, k: i, sad: !S.active }));
},
sejong(S) {
  S.road(0, 8, 12, 2, '#9fa0a0'); S.road(0, 6.8, 12, 1.2, '#e3dccb'); S.road(0, 10, 12, 1, '#e3dccb');
  S.house(2.4, 1.2, 6.2, 3.2, '#e8b04a', '#f6ecd6', { door: '#6e9473' }); S.sign(5.5, 2.6, '새롬초등학교');
  S.box(8.9, 1.5, .1, .8, .8, 3.6, '#f6ecd6', true); S.box(8.95, 2.31, 2.6, .7, .02, .7, '#fffdf3');
  S.fence(.3, 5.6, 4, '#f3e8ce'); S.fence(8.6, 5.6, 5, '#f3e8ce'); S.tree(.9, 1.2, .8); S.tree(10.6, 4.4, .7);
  for (let i = 0; i < 6; i++) S.box(4.6 + i * .5, 8.1, .1, .3, 1.8, .025, '#e9e7df', false, { a: S.active ? 0 : .7 });
  for (let i = 0; i < 6; i++) S.fb(4.6 + i * .5, 8.1, .1, .3, 1.8, .035, '#ffffff');
  if (S.q !== 'low') { S.fb(4.2, 7.88, .1, 3.4, .12, .04, '#f7d35c'); S.fb(4.2, 9.98, .1, 3.4, .12, .04, '#f7d35c'); if (S.active) { const on = Math.sin(S.t * .004) > -.2; for (let i = 0; i < 4; i++) { S.glow(4.5 + i * .9, 7.9, .1, 16, on ? '#ffd84a' : '#7cff9a'); S.glow(4.5 + i * .9, 10.0, .1, 16, on ? '#ffd84a' : '#7cff9a') } } }
  for (const [x, y] of [[4.0, 7.3], [7.9, 10.3]]) { S.fb(x, y, .1, .16, .16, 2.2, '#566f78'); S.fb(x - .12, y - .05, 2.0, .42, .3, .55, '#2d3b40', true); if (S.active) S.glow(x, y, 2.2, 14, '#7cff9a') }
  comfortExtra(S, 9.6, 6.6); upkeepExtra(S, 2.2, 6.9);
  const carX = S.active ? 9.4 : ((S.t * .002) % 15) - 2; S.car(carX, 8.25, '#e07a5f');
  const kidsX = S.active ? 4.8 + ((S.t * .0006) % 1) * 2.2 : 3.6;
  [[0, 0], [.6, .4]].forEach(([a, b], i) => S.minifig(kidsX + a, 7.2 + b + (S.active ? ((S.t * .0006) % 1) * 2.4 : 0), { shirt: ['#f2b84b', '#e07a5f'][i], hat: '#f2d24c', walk: S.active, sad: !S.active, k: i, scale: .8 }));
},
gyeonggi(S) {
  S.road(0, 8, 12, 2, '#a9a99f'); S.road(3, 6.2, 6, 1.8, '#e3dccb');
  S.tower(.3, .3, 2.6, 2.3, 4.6, '#c9d3dc'); S.tower(3.6, .3, 2.2, 2, 3.6, '#e2d6c0'); S.tower(6.6, .3, 2.4, 2.2, 4.0, '#b7c9b8'); S.tower(9.6, .5, 2, 2.4, 3.0, '#d3c3d8');
  S.tree(1.4, 5.4, .8, '#7fa98f'); S.tree(10.4, 5.2, .8, '#7fa98f');
  const x = 4.0, y = 6.3, low = S.q === 'low';
  S.fb(x, y, .1, 3.8, 1.3, .1, '#d7dbd8');
  S.fb(x, y, .2, .14, .14, 2.2, '#566f78'); S.fb(x + 3.6, y, .2, .14, .14, 2.2, '#566f78');
  if (!low) { S.fb(x + .14, y, .2, 3.46, .08, 2, '#bfe6f0', false, { a: .4 }); S.fb(x, y + .14, .2, .08, 1.0, 2, '#bfe6f0', false, { a: .4 }) }
  S.fb(x + .4, y + .3, .2, 2.4, .45, .45, low ? '#c49c74' : '#e8915a', true);
  S.fb(x - .1, y - .1, 2.4, 4, 1.5, .18, '#4c9a7a', true);
  if (!low) { S.fb(x + .3, y + .1, 2.58, 3.3, 1.1, .05, '#2f5c86', false, { d: x + y + 3.5 }); S.fb(x + 3.0, y + .9, .2, .55, .1, 1.9, '#2d3b40'); S.fb(x + 3.05, y + 1.0, 1.1, .45, .03, .7, '#7cd6a8') }
  if (S.active && !low) S.glow(x + 1.6, y + .5, .6, 30, '#ffb27a');
  comfortExtra(S, 8.4, 6.6); upkeepExtra(S, 2.4, 6.6);
  const busX = S.active ? Math.max(4.2, 12.5 - (S.t - S.activeAt) * .003) : -9; if (S.active) S.bus(busX, 8.2, '#4c9a7a');
  if (!S.active) [[4.6, 7.3], [6.0, 7.4], [7.2, 7.2]].forEach(([a, b], i) => S.minifig(a, b, { shirt: people[i], hat: '#7a8fb0', sad: true, k: i }));
},
gangwon(S) {
  S.road(0, 8, 12, 2, S.active ? '#b8b4ab' : '#f4f7f9');
  for (const [x, y, s] of [[.2, .2, 3.6], [3.8, .1, 2.8], [.1, 3.8, 2.4], [8.6, .2, 3]]) { S.box(x, y, .1, s, s, .8, '#8a9a94', true); S.box(x + .4, y + .4, .9, s - .8, s - .8, .8, '#a3b2aa', true); S.box(x + .8, y + .8, 1.7, Math.max(.4, s - 1.6), Math.max(.4, s - 1.6), .6, '#f4f7f9', true) }
  S.house(4.4, 4.0, 2.4, 2.2, '#c86f55', '#f1e3c3'); S.house(8.8, 4.2, 2.2, 2, '#7c8fb3', '#f1e3c3');
  for (const [x, y] of [[1.2, 6.4], [10.6, 3.4], [7.6, 1.6]]) S.tree(x, y, .8, '#4f8a72');
  // 쌓인 눈 / 제설 후 길가 눈더미
  const blocked = !S.active || S.late;
  if (blocked) for (let i = 0; i < 9; i++) { if (S.active && i % 3) continue; S.box(.4 + i * 1.3, 8.1 + (i % 2) * .7, .1, 1.1, .9, .4 + (i % 3) * .15 + S.storm * .3, '#ffffff', true) }
  if (S.active) for (let i = 0; i < 6; i++) S.box(.5 + i * 2, 7.25, .1, 1.2, .55, .45, '#f4f7f9', true);
  // 시설: 제설 차량(+삽날·살포기) + 염화칼슘 보관함
  const v = S.active ? (S.late ? 7.4 : 9 - ((S.t * .0012) % 1) * 0) : 7.4, vy = S.active ? 8.3 : 6.2;
  if (S.q !== 'low') {
    S.fb(v, vy, .2, 2.4, 1, .7, '#f08a3c', true); S.fb(v - .05, vy + .1, .9, .9, .8, .6, '#f08a3c'); S.fb(v - .07, vy + .2, .95, .04, .6, .35, '#bfe6f0');
    S.fb(v - .55, vy - .1, .1, .25, 1.2, .55, '#f2c94c'); S.fb(v + 1.4, vy + .1, .9, .9, .8, .5, '#c9ccc5', true);
    for (const wx of [v + .2, v + 1.8]) { S.fb(wx, vy - .06, .02, .4, .12, .4, '#3e4a4c'); S.fb(wx, vy + .94, .02, .4, .12, .4, '#3e4a4c') }
  } else { S.fb(v, vy, .2, 1, .7, .5, '#f08a3c', true); S.fb(v - .3, vy - .05, .1, .2, .8, .35, '#f2c94c') }
  S.fb(2.2, 6.2, .1, 1.2, 1, .9, '#7c8fb3', true); S.fb(2.15, 6.15, 1.0, 1.3, 1.1, .2, '#5b6f96');
  comfortExtra(S, 9.2, 6.8); upkeepExtra(S, 1.0, 7.0);
  if (S.active && !S.late) S.car(((S.t * .0018) % 15) - 2, 9.1, '#5f8fb7'); else S.car(3.0, 8.9, '#5f8fb7');
},
chungbuk(S) {
  S.water(0, 0, 12, 2.2, '#7a9fae'); S.road(0, 8, 12, 2, '#cfc6b0');
  S.house(1.0, 3.6, 2.2, 2.0, '#c86f55', '#f1dfb4'); S.house(4.2, 3.4, 2.4, 2.2, '#8ba06e', '#f4e2c0'); S.house(7.2, 3.6, 2.0, 2.0, '#c99a7a', '#efe0c4');
  S.tree(10.8, 6.2, .7); S.tree(.6, 7.2, .6);
  // 침수 물: 시설이 작동하면 빠짐(지연 시 일부 남음)
  const lvl = S.active ? (S.late ? .45 : 0) : (.4 + S.storm * .6);
  if (lvl > 0) for (let x = 0; x < 10; x++) for (let y = 2; y < 10; y++) { if (S.active && (x + y) % 3) continue; S.deco(x + y + .05, () => { ctx.save(); ctx.globalAlpha = .55; boxRaw(x, y, .1, 1, 1, .12 + lvl * .25, '#8fc6d0'); ctx.restore() }) }
  // 시설: 배수펌프 + 배수관
  const big = S.q !== 'low';
  S.fb(9.6, 2.6, .1, 1.8, 1.4, big ? 1.4 : .7, '#3f86b0', true);
  if (big) { S.fb(9.75, 4.01, .4, 1.2, .03, .7, '#2d5c7a'); S.fb(10.0, 2.0, 1.0, .35, .7, .35, '#9aa6ae'); S.fb(10.0, 1.2, .9, .35, .9, .3, '#9aa6ae'); }
  S.fb(8.4, 4.2, .1, 1.3, .3, .3, '#9aa6ae'); S.fb(6.0, 6.6, .1, 3.4, .3, .3, '#9aa6ae');
  if (S.active) { const ph = (S.t * .002) % 1; S.box(10.1, .6 + ph * .4, .0, .3, .3, .2, '#d8f2f5', false, { a: 1 - ph }); }
  comfortExtra(S, 2.2, 6.7); upkeepExtra(S, 8.2, 6.8);
  [[2.4, 6.2], [5.6, 6.4], [8.0, 6.6]].forEach(([x, y], i) => S.minifig(x, y, { shirt: people[i], umbrella: S.active ? null : '#5f8fb7', sad: !S.active, walk: S.active && !S.late, k: i }));
},
chungnam(S) {
  S.road(0, 8, 12, 2, '#d8c9a5');
  const green = S.active ? (S.late ? .55 : 1) : 0;
  for (let x = 0; x < 8; x++) for (let y = 1; y < 6; y++) { S.tile(x, y, mix('#b99a63', '#8db06a', green)); if (green && (x + y) % 2 === 0) S.box(x + .3, y + .3, .1, .2, .2, .2 + green * .35, '#6fa85a') }
  if (!S.active) for (let i = 0; i < 6; i++) S.deco(i, () => { const q = p(1 + i * 1.2, 2 + (i % 3) * 1.2, .11); ctx.strokeStyle = '#8a6a3c'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(q[0] - 10, q[1]); ctx.lineTo(q[0], q[1] + 3); ctx.lineTo(q[0] + 8, q[1] - 2); ctx.stroke() });
  S.house(8.8, 4.6, 2.2, 2, '#c86f55', '#f1dfb4'); S.tree(11, 1.4, .8); S.fence(.2, 6.3, 7, '#d8c9a5');
  // 시설: 급수탑 + 펌프 + 급수관
  S.fb(9.2, 1.2, .1, .16, .16, 2.2, '#8a7c6a'); S.fb(10.4, 1.2, .1, .16, .16, 2.2, '#8a7c6a'); S.fb(9.2, 2.4, .1, .16, .16, 2.2, '#8a7c6a'); S.fb(10.4, 2.4, .1, .16, .16, 2.2, '#8a7c6a');
  S.fb(9.0, 1.0, 2.3, 1.8, 1.8, 1.0, S.q === 'low' ? '#9fb3b9' : '#4e9bb5', true);
  S.fb(8.2, 3.3, .1, .9, .7, .7, '#e9e2c8', true);
  S.fb(0, 6.0, .1, 8.6, .22, .22, S.q === 'low' ? '#cfd6d8' : '#3a6f8f'); S.fb(4.0, 1.0, .1, .22, 5, .22, S.q === 'low' ? '#cfd6d8' : '#3a6f8f');
  if (S.active) { const ph = (S.t * .0015) % 1; for (let i = 0; i < 4; i++) S.box(8.2 - ((ph + i * .25) % 1) * 8, 6.02, .32, .2, .18, .05, '#bfe9ff') }
  comfortExtra(S, 6.0, 6.9); upkeepExtra(S, 7.6, 7.0);
  [[2, 7], [5.4, 7.2]].forEach(([x, y], i) => S.minifig(x, y, { shirt: ['#7fb069', '#e8aa49'][i], hat: '#e9d8a6', sad: !S.active, k: i }));
},
jeonbuk(S) {
  S.road(0, 8, 12, 2, '#d8c9a5');
  for (let x = 0; x < 4; x++) for (let y = 1; y < 6; y++) { S.tile(x, y, '#a3864f'); if ((x + y) % 2) S.box(x + .25, y + .25, .1, .5, .5, .3, '#7fb069', true) }
  S.house(9.4, 1.2, 2.2, 2.0, '#6aa84f', '#f4e2c0'); S.tree(11, 5.6, .7);
  // 수확물 상자: 시들거나(전) 저장고로 들어감(후)
  const outside = S.active ? (S.late ? 3 : 0) : 6;
  for (let i = 0; i < outside; i++) S.crate(4.4 + (i % 3) * .55, 6.6 + Math.floor(i / 3) * .5, .1, S.active ? '#d8a868' : '#b89a5a');
  if (!S.active) for (let i = 0; i < 6; i++) S.box(4.45 + (i % 3) * .55, 6.65 + Math.floor(i / 3) * .5, .46, .3, .3, .1, '#b8a656');
  // 시설: 저온저장고
  const x = 4.2, y = 2.6;
  S.fb(x, y, .1, 3.8, 2.8, .14, '#c9ccc5');
  S.fb(x, y, .24, 3.8, 2.8, 2.0, '#f4f7f9', true);
  S.fb(x + .05, y + 2.81, .5, 3.7, .02, .25, '#6d9fd0'); S.fb(x + 1.4, y + 2.82, .24, 1, .04, 1.5, '#9aa6ae');
  if (S.q !== 'low') S.fb(x + 2.4, y + .6, 2.24, 1.1, .9, .5, '#9aa6ae', true, { d: x + y + 4.2 });
  if (S.active) S.glow(x + 1.9, y + 2.9, .8, 40, '#cdefff');
  comfortExtra(S, 9.2, 6.6); upkeepExtra(S, 3.0, 6.8);
  [[1.6, 6.8], [3.0, 7.1]].forEach(([a, b], i) => S.minifig(a, b, { shirt: ['#7fb069', '#c98bb9'][i], hat: '#e9d8a6', sad: !S.active, k: i }));
},
jeonnam(S) {
  for (let i = 0; i < 12; i++) { S.water(i, 0, 1, 1, '#5fb3c4'); S.water(i, 11, 1, 1, '#5fb3c4'); if (i > 0 && i < 11) { S.water(0, i, 1, 1, '#5fb3c4'); S.water(11, i, 1, 1, '#5fb3c4') } }
  S.road(1, 8, 10, 1.4, '#e3d6b0');
  S.house(1.6, 1.6, 2.2, 2, '#3aa0a8', '#f4ecd6'); S.house(4.8, 1.4, 2.2, 2, '#e07a5f', '#f4ecd6'); S.tree(8.6, 1.6, .7, '#5f9a6a'); S.tree(1.6, 5.4, .6, '#5f9a6a');
  const bob = Math.sin(S.t * .002) * .06; S.box(11.1, 6.6, -.05 + bob, .8, 2.6, .35, '#f4f1e6', true); S.box(11.2, 7.4, .3 + bob, .6, .9, .45, '#3aa0a8');
  if (!S.active) { for (let i = 0; i < 5; i++) { S.minifig(3 + i * .6, 6.4, { shirt: people[i], sad: true, k: i }); S.box(3.1 + i * .6, 6.0, .1, .22, .22, .3, '#5f8fb7') } }
  // 시설: 정수설비(컨테이너 + 탱크) + 급수대
  const big = S.q !== 'low';
  if (big) { S.fb(7.4, 3.4, .1, 2.6, 1.3, 1.2, '#3aa0a8', true); S.fb(7.5, 4.71, .4, 2.3, .02, .6, '#e9f4f5'); }
  S.fb(7.6, 5.0, .1, .9, .9, 1.4, '#e9eef0', true); S.fb(8.7, 5.0, .1, .9, .9, 1.4, '#e9eef0', true);
  S.fb(5.4, 6.4, .1, .6, .4, 1.0, '#9aa6ae', true); S.fb(5.5, 6.82, .7, .2, .2, .12, '#6d9fd0'); S.fb(6.0, 6.5, .1, 1.6, .16, .16, '#9aa6ae');
  if (S.active) { const ph = (S.t * .003) % 1; S.box(5.55, 6.86, .65 - ph * .5, .08, .08, .1, '#8fd6ff', false, { a: 1 - ph }); }
  comfortExtra(S, 2.6, 6.4); upkeepExtra(S, 9.6, 6.8);
},
gyeongbuk(S) {
  S.road(0, 8, 12, 2, '#d8cfb4'); S.road(3, 5, 6, 3, '#e6dfca');
  // 마을회관(한옥 지붕)
  S.box(2.6, 1.4, .1, 5.2, 2.6, .35, '#b9a98a', true); S.box(2.9, 1.7, .45, 4.6, 2.0, 1.6, '#f3e7cf');
  S.box(2.4, 1.2, 2.05, 5.6, 3.0, .25, '#4f5d63'); S.box(2.8, 1.5, 2.3, 4.8, 2.4, .25, '#5d6b70', true); S.box(4.0, 2.2, 2.55, 2.4, 1, .2, '#4f5d63');
  S.box(4.6, 3.71, .45, .8, .04, 1.2, '#8a6a4a'); S.sign(5.1, 2.8, '하회 마을회관');
  S.tree(.9, 1.4, 1.0, '#5f9a6a'); S.tree(10.2, 2.0, .9, '#7fb069'); S.tree(10.8, 6.0, .7);
  // 시설: AED 보관함 + 길 안내 표지
  S.fb(6.2, 3.72, .45, .7, .25, .9, '#f4f7f9', true); S.fb(6.25, 3.98, .6, .6, .02, .25, '#3f9f5a'); S.fb(6.36, 3.99, .95, .38, .02, .3, '#d8545e');
  if (S.q !== 'low') for (const [x, y] of [[9.0, 7.6], [2.4, 7.6], [9.6, 5.0]]) { S.fb(x, y, .1, .14, .14, 1.9, '#8a6a4a'); S.fb(x - .3, y - .05, 1.6, .9, .1, .38, '#3f9f5a'); S.fb(x - .22, y + .06, 1.68, .3, .02, .22, '#ffffff') }
  if (S.active) S.glow(6.5, 4, 1.2, 22, '#7cff9a');
  comfortExtra(S, 7.6, 5.6); upkeepExtra(S, 3.4, 5.4);
  if (S.active) [[3.6, 6.2], [4.4, 6.4], [7.0, 6.1]].forEach(([x, y], i) => S.minifig(x, y, { shirt: people[i + 2], hair: '#d9d9d9', k: i, wave: i === 1 }));
  else[[6.2, 6.0], [7.0, 6.5]].forEach(([x, y], i) => S.minifig(x, y, { shirt: people[i], hair: '#d9d9d9', sad: true, k: i }));
},
gyeongnam(S) {
  S.road(0, 8, 12, 2, '#d8cfbd'); S.road(2, 5, 8, 3, '#ece2d6');
  // 높은 단 위의 회관 + 계단
  S.box(3.0, 1.0, .1, 5.0, 3.0, .9, '#c9b9a2', true); S.box(3.3, 1.2, 1.0, 4.4, 2.4, 1.6, '#f6ecd6', true);
  for (let i = 0; i < 3; i++) S.box(3.4 + i * .5, 2.4, 2.6 + i * .25, 4.2 - i, 1.4 - i * .3, .25, '#d983a6', i === 2);
  S.box(5.0, 3.61, 1.0, .8, .04, 1.1, '#8a6a4a'); S.sign(5.5, 2.2, '벚꽃 마을회관');
  for (let i = 0; i < 4; i++) S.box(4.9, 4.0 + i * .35, .1, 1.0, .35, .9 - i * .22, '#d9cbb3', true);
  for (const [x, y] of [[1.0, 1.2], [10.2, 1.6], [10.6, 5.6], [1.2, 6.0]]) S.tree(x, y, .85, '#f2a7c3');
  // 시설: 완만한 경사로 + 손잡이 + 점자블록
  const steps = S.q === 'low' ? 3 : 8, len = S.q === 'low' ? 1.2 : 3.2;
  for (let i = 0; i < steps; i++) S.fb(6.1 + .02, 4.0 + i * (len / steps), .1, .9, len / steps + .02, .9 * (1 - (i + .5) / steps) + .05, '#cfd3c9', false);
  if (S.q !== 'low') { for (const side of [6.05, 7.0]) { for (let i = 0; i <= 3; i++) S.fb(side, 4.0 + i * 1.05, .1 + .85 * (1 - i / 3), .08, .08, .7, '#e8aa49') } S.fb(6.1, 7.2, .1, .9, .5, .04, '#f2c94c', true); }
  comfortExtra(S, 8.2, 5.4); upkeepExtra(S, 2.4, 5.6);
  if (S.active) S.minifig(6.5, 5.6, { shirt: '#c98bb9', walk: true, k: 1 }); else S.minifig(5.4, 5.8, { shirt: '#c98bb9', sad: true });
},
jeju(S) {
  S.road(0, 8, 12, 2, '#cfc6b0');
  S.dark = S.storm > .5 && (!S.active || S.late) ? .42 : (S.storm > .5 ? .16 : 0); S.windowsLit = S.active && S.q !== 'low';
  // 현무암 돌담 + 귤나무
  for (let i = 0; i < 11; i++) { S.box(.3 + i, 6.6, .1, .9, .4, .5 + (i % 2) * .12, '#4a4f52', true) }
  for (let i = 0; i < 5; i++) S.box(.3, 1 + i, .1, .4, .9, .5, '#4a4f52', true);
  for (const [x, y] of [[1.4, 1.4], [1.4, 3.8], [10.4, 1.4], [10.6, 3.8]]) { S.tree(x, y, .75, '#4f8a4a', S.storm); for (let k = 0; k < 4; k++) S.box(x - .1 + (k % 2) * .5, y + .7 - (k > 1) * .5, 1.75 + (k % 2) * .3, .14, .14, .14, '#f08a3c') }
  const h = S.house(4.2, 2.4, 3.6, 2.6, '#f08a3c', '#f4ecd6', { noChimney: true });
  // 시설: 지붕 태양광 — 지붕 최상단(3.05) 위에 받침을 두고, 지붕 전체보다 나중에 그려 묻히지 않게 함
  const roofD = h.depth + 1.2, mods = S.q === 'low' ? 0 : 3;
  for (let i = 0; i < mods; i++) { const x = 4.68 + i * .92; S.fb(x + .1, 3.3, h.roofTop + .04, .66, .58, .23, '#a9bdba', false, { d: roofD }); S.fb(x, 3.14, h.roofTop + .27, .86, .95, .19, '#3e6684', false, { d: roofD + .01 }); for (let a = 0; a < 2; a++) for (let b = 0; b < 2; b++) S.fb(x + .06 + a * .39, 3.21 + b * .4, h.roofTop + .47, .35, .33, .025, '#8fc4d2', false, { d: roofD + .02 }) }
  // 비상배터리(ESS) 캐비닛 + 연결선
  S.fb(8.3, 3.2, .1, .9, .9, 1.4, '#c9ccc5', true); S.fb(8.35, 4.11, .6, .8, .02, .5, '#2d3b40'); S.fb(8.45, 4.12, 1.0, .15, .02, .12, '#7cff9a');
  if (S.q === 'low') { S.fb(8.3, 5.0, .1, .8, .6, .6, '#d0533f', true) }
  S.fb(7.8, 3.6, .1, .5, .12, .12, '#3e4a4c');
  if (S.active && S.windowsLit) S.glow(8.7, 4.2, 1.2, 16, '#7cff9a');
  comfortExtra(S, 2.2, 5.4); upkeepExtra(S, 9.6, 5.6);
  if (!S.active) [[5, 5.8], [6, 6.0]].forEach(([x, y], i) => S.minifig(x, y, { shirt: people[i + 3], sad: true, umbrella: S.storm > .5 ? '#f08a3c' : null, k: i }));
}
};
