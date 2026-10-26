// ── 게임 흐름 ──────────────────────────────────────────────────
const DEMO = /[?&]demo/.test(location.search);
const SAVE_KEY = 'umjc-nationwide-v1';
const STEPS = [['survey', '현장 조사', '주민 이야기 듣기'], ['budget', '예산 배분', '우선순위 정하기'], ['product', '제품 비교', '가격·성능·납기'], ['event', '긴급 상황', '납기 확인'], ['install', '지역 회복', '공급·설치·작동']];
const TL = { strike: 2000, truck: 1500, unload: 2300, built: 4600, active: 5400, end: 6800 };
const LEAD = [['narmi', '나르미', '조달 원정대장 · 현장 조사와 원정 지휘'], ['dari', '달이', '조달·계약 담당 · 예산과 제품 비교']];
const TEAM = [['emperor', '제육황제', '현장 조사 도우미'], ['buoy', '부이', '예산 도우미'], ['bandit', '반딧대왕', '시설 설치 담당'], ['deer', '다랑이', '길 안내 담당']];
const byId = Object.fromEntries(REGIONS.map(r => [r.id, r]));

let save = loadSave(), view = 'title', reg = byId.seoul, R = null, mapSel = null, sound = false, audioCtx, lastStepIdx = -1;

function loadSave() { try { const s = JSON.parse(localStorage.getItem(SAVE_KEY)); if (s && s.best) return s } catch (e) { } return { best: {}, seenFinal: false } }
function persist() { if (DEMO) return; try { localStorage.setItem(SAVE_KEY, JSON.stringify(save)) } catch (e) { } }
function doneCount() { return Object.keys(save.best).length }
function totalStars() { return Object.values(save.best).reduce((a, b) => a + b.stars, 0) }
function nextRecommended() { return ROUTE.find(id => !save.best[id]) || null }
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])) }
function starStr(n) { return '★'.repeat(n) + '☆'.repeat(3 - n) }

function tone2(freqs, dur = .12, type = 'sine', vol = .07) {
  if (!sound) return;
  try { audioCtx ??= new (window.AudioContext || window.webkitAudioContext)(); const t0 = audioCtx.currentTime; freqs.forEach((f, i) => { const o = audioCtx.createOscillator(), g = audioCtx.createGain(); o.type = type; o.connect(g); g.connect(audioCtx.destination); o.frequency.setValueAtTime(f, t0 + i * dur); g.gain.setValueAtTime(vol, t0 + i * dur); g.gain.exponentialRampToValueAtTime(.001, t0 + i * dur + dur * 1.6); o.start(t0 + i * dur); o.stop(t0 + i * dur + dur * 1.7) }) } catch (e) { }
}
const sfx = { tap: () => tone2([660], .07), ok: () => tone2([523, 784], .1), warn: () => tone2([330, 247], .14, 'triangle'), done: () => tone2([523, 659, 784, 1046], .11), truck: () => tone2([196, 220], .12, 'square', .03) };

// ── 화면 전환 ──
function show(v) {
  view = v;
  $('viewRegion').classList.toggle('hidden', v === 'map');
  $('viewMap').classList.toggle('hidden', v !== 'map');
  sceneOn = v !== 'map';
  if (v === 'map') renderMap();
}
function openModal(html, wide = false) { $('modal').className = 'modal' + (wide ? ' wide' : ''); $('modal').innerHTML = html; $('overlay').classList.remove('hidden'); const b = $('modal').querySelector('button'); b && b.focus() }
function closeModal() { $('overlay').classList.add('hidden') }

// ── 지역 임무 ──
function startRegion(id) {
  reg = byId[id]; R = { heard: [], pri: null, prod: null, express: false, phase: 'survey', t0: 0, say: null, sayUntil: 0, res: null, showBefore: false, arriveAt: performance.now(), doneAt: 0 };
  lastStepIdx = -1; closeModal(); show('region'); renderRegion();
  R.say = { id: 'r0', text: '원정대님! 우리 동네 이야기 좀 들어주세요.' }; R.sayUntil = performance.now() + 4200;
}
function phaseIdx() { return { survey: 0, budget: 1, product: 2, event: 3, install: 4, finishing: 4, result: 4 }[R.phase] }
function curProduct() { return R.prod == null ? null : reg.products[R.prod] }
function spentNow() { const p = curProduct(); return p ? p[1] + (R.express ? expressOf(reg).cost : 0) : 0 }

function renderRegion() {
  const r = reg, idx = R ? phaseIdx() : 0;
  $('rEyebrow').textContent = `${r.full} · ${r.town}`.toUpperCase();
  $('rTitle').textContent = r.mission;
  $('rSub').textContent = `조달 품목: ${r.item} · 지역 예산 ${r.budget}코인`;
  $('rDay').textContent = `원정 ${String(doneCount()).padStart(2, '0')} / 17 회복`;
  $('townName').textContent = `${r.name} · ${r.town}`; $('townType').textContent = r.full;
  $('weather').textContent = r.weather;
  $('steps').innerHTML = STEPS.map(([k, n, d], i) => `<div class="step ${i === idx ? 'active' : ''} ${i < idx || (R && R.phase === 'result') ? 'done' : ''}"><small>${i < idx || (R && R.phase === 'result') ? '✓' : i + 1}</small><b>${n}</b><span>${d}</span></div>`).join('');
  $('sBudget').textContent = r.budget - spentNow(); $('sBudgetTot').textContent = `/ ${r.budget} 코인`;
  if (R && R.phase === 'result') { $('sMidLabel').textContent = '이번 조달 점수'; $('sMid').textContent = R.res.total; $('sMidTot').textContent = '/ 100' }
  else { $('sMidLabel').textContent = '조사한 주민'; $('sMid').textContent = R ? R.heard.length : 0; $('sMidTot').textContent = '/ 3' }
  $('sDone').textContent = doneCount();
  $('dots').innerHTML = ROUTE.map(id => `<i class="dot ${save.best[id] ? 'done' : ''} ${id === r.id ? 'cur' : ''}" title="${byId[id].name}"></i>`).join('');
  updateMapState(performance.now());
  renderPanel();
}
function updateMapState(t) {
  const r = reg, ms = $('mapstate'); let cls = 'mapstate', text = '! ' + r.problem, msg = r.before;
  if (R) {
    if (R.phase === 'survey') msg = R.heard.length < 3 ? '주민을 눌러 이야기를 들어보세요. (? 표시가 있는 주민)' : '조사를 마쳤어요. 예산을 정하러 가볼까요?';
    if (R.phase === 'budget') msg = '모든 요청을 한 번에 해결할 순 없어요. 무엇을 먼저 할까요?';
    if (R.phase === 'product') msg = '가격만 보지 말고 성능·유지비·납기를 함께 비교하세요.';
    if (R.phase === 'event') { cls = 'mapstate alert'; text = `${r.event.icon} ${r.event.name} D-${r.event.d}`; msg = '기상·안전 이벤트가 다가오고 있어요!' }
    if (R.phase === 'install') { const base = t - R.t0 - (R.res.late ? TL.strike : 0); if (base < 0) { cls = 'mapstate alert'; text = `${r.event.icon} ${r.event.name}!`; msg = r.event.hit + ' 공급이 늦어지고 있어요…' } else if (base < TL.built) { text = '🚚 공급·설치 진행 중'; msg = base < TL.truck ? '공급 차량이 도착하고 있어요.' : base < TL.unload ? '장비와 물품을 내리고 있어요.' : '반딧대왕이 시설을 조립하고 있어요.' } else { cls = 'mapstate solved'; text = '✓ ' + r.fixed; msg = r.after } }
    if (R.phase === 'result') { if (R.showBefore) { text = '! ' + r.problem + ' (조달 전)'; msg = r.before } else { cls = 'mapstate solved'; text = '✓ ' + r.fixed; msg = r.after + (R.res.late ? ' (다만 납기가 늦어 피해가 일부 남았어요.)' : '') } }
  }
  ms.className = cls; ms.textContent = text; $('mapmsg').textContent = msg;
  $('btnSkip').classList.toggle('hidden', !(R && R.phase === 'install'));
  $('btnCompare').classList.toggle('hidden', !(R && R.phase === 'result'));
  $('btnCompare').textContent = R && R.showBefore ? '조달 후 보기 ↷' : '조달 전 보기 ↶';
}

function quoteBox(key, who, text) { return `<div class="quote"><img src="${portrait(key)}" alt=""><div><b>${esc(who)}</b>${text}</div></div>` }
function tipCard(k) { const [t, d] = TIPS[k]; return `<div class="tip"><b>🏛 실제 조달에서는? · ${t}</b>${d}</div>` }
function renderPanel() {
  const r = reg, P = $('panel'); if (!R) return;
  const back = (to, label) => `<button class="ghost" data-back="${to}">← ${label}</button>`;
  if (R.phase === 'survey') {
    P.innerHTML = `<div class="tag"><span>STEP 1 · 현장 조사</span><span>${R.heard.length}/3 명</span></div><h2>${esc(r.mission)}</h2>
      ${quoteBox('narmi', '나르미 · 조달 원정대장', `${esc(r.town)}에 도착! 주민들에게 무엇이 필요한지 먼저 들어보자. 장면 속 주민이나 아래 이름을 눌러봐.`)}
      <div class="label">주민 이야기<span>3명 모두 들으면 만족도 보너스</span></div>
      <div class="list">${r.residents.map((x, i) => `<button class="card who ${R.heard.includes(i) ? 'sel' : ''}" data-hear="${i}"><img src="${portrait(x.k)}" alt=""><span><span class="t">${esc(x.n)}</span><span class="d" style="display:block">${R.heard.includes(i) ? '“' + esc(x.line) + '”' : '눌러서 이야기 듣기'}</span></span><span class="pill ${R.heard.includes(i) ? 'ok' : ''}">${R.heard.includes(i) ? '✓' : '?'}</span></button>`).join('')}</div>
      ${R.heard.length ? `<div class="notes">${R.heard.map(i => `<div class="note">📝 ${esc(r.residents[i].clue)}</div>`).join('')}</div>` : ''}
      ${tipCard('survey')}
      <button class="primary" id="go" ${R.heard.length ? '' : 'disabled'}><span>예산 정하러 가기</span><span>→</span></button>`;
  }
  if (R.phase === 'budget') {
    P.innerHTML = `<div class="tag"><span>STEP 2 · 예산 배분</span><span>예산 ${r.budget}코인</span></div><h2>무엇을 먼저 할까요?</h2>
      ${quoteBox('dari', '달이 · 조달·계약 담당', `예산은 ${r.budget}코인이야. 모든 요청을 다 들어줄 순 없으니, 주민에게 가장 중요한 것부터 정하자!`)}
      ${notes()}
      <div class="list">${Object.entries(PRI).map(([k, v]) => `<button class="card ${R.pri === k ? 'sel' : ''}" data-pri="${k}"><span class="row"><span class="t">${v.icon} ${v.n}</span><span class="pill">구매 한도 ${capOf(r, k)}</span></span><span class="d">${esc(r.pt[k])}</span><span class="d">예비비 ${r.budget - capOf(r, k)}코인 ${k === 'upkeep' ? '· 유지관리 점수 +3' : k === 'comfort' ? '· 벤치·꽃밭 추가' : ''}</span></button>`).join('')}</div>
      ${tipCard('budget')}<div class="btnrow">${back('survey', '조사로')}</div>
      <button class="primary" id="go" ${R.pri ? '' : 'disabled'}><span>제품 비교하러 가기</span><span>→</span></button>`;
  }
  if (R.phase === 'product') {
    const cap = capOf(r, R.pri), minM = Math.min(...r.products.map(p => p[3]));
    P.innerHTML = `<div class="tag"><span>STEP 3 · 제품 비교</span><span>구매 한도 ${cap}코인</span></div><h2>🛒 나라장터에서 제품 비교</h2>
      <div class="chips"><span class="chip">필요 ${esc(r.perf)} ${r.min} 이상</span><span class="chip warn">${r.event.icon} ${esc(r.event.name)} D-${r.event.d}</span></div>
      <div class="list">${r.products.map((p, i) => { const over = p[1] > cap, low = p[2] < r.min, late = p[4] > r.event.d; return `<button class="card ${R.prod === i ? 'sel' : ''}" data-prod="${i}" ${over ? 'disabled' : ''}>
        <span class="row"><span class="t">${esc(p[0])}${INNOVATIVE[r.id] === i ? ' <span class="pill inno">✦ 혁신제품</span>' : ''}</span><span class="pill ${'abc'[i]}">${TYPES[i]}</span></span><span class="d">${esc(p[5])}${over ? ' · <b style="color:#b4553f">구매 한도 초과</b>' : ''}</span>
        <span class="metrics"><span class="metric">가격<b>${p[1]}</b></span><span class="metric ${low ? 'bad' : 'good'}">성능<b>${p[2]}</b></span><span class="metric ${p[3] > minM * 2 ? 'bad' : p[3] === minM ? 'good' : ''}">유지비/년<b>${p[3]}</b></span><span class="metric ${late ? 'bad' : 'good'}">납기<b>${p[4]}일</b></span></span>
        <span class="d">생애주기비용(5년) ${p[1] + p[3] * 5}코인 = ${p[1]} + ${p[3]}×5</span></button>` }).join('')}</div>
      ${tipCard('product')}
      <div class="btnrow">${back('budget', '예산으로')}</div>
      <button class="primary" id="go" ${R.prod == null ? 'disabled' : ''}><span>이 제품으로 계약하기</span><span>→</span></button>`;
  }
  if (R.phase === 'event') {
    const p = curProduct(), ex = expressOf(r), eff = p[4] - (R.express ? ex.days : 0), late = eff > r.event.d, canEx = p[4] > r.event.d && r.budget - p[1] >= ex.cost;
    const maxD = Math.max(p[4], r.event.d) + 1, pos = d => 12 + (d / maxD) * 76;
    P.innerHTML = `<div class="tag"><span>STEP 4 · 긴급 상황</span><span>${r.event.icon} D-${r.event.d}</span></div><h2>${esc(r.event.name)}이(가) 다가와요!</h2>
      ${quoteBox('yeongdeung', '영등할망 · 기상 특보', `${r.event.d}일 뒤 ${esc(r.event.name)}! 계약한 「${esc(p[0])}」은(는) ${p[4]}일 뒤 도착한단다.`)}
      <div class="timeline"><div class="bar"></div><div class="mark" style="left:${pos(0)}%">오늘<i style="background:#6e9473"></i></div><div class="mark" style="left:${pos(r.event.d)}%;color:#b4553f">${r.event.icon} D-${r.event.d}<i style="background:#d0533f"></i></div><div class="mark" style="left:${pos(eff)}%;top:${Math.abs(eff - r.event.d) < 1.5 ? 27 : 6}px;color:#2f5c86">🚚 ${eff}일<i style="background:#2f5c86"></i></div></div>
      <div class="lesson ${late ? 'bad' : 'good'}">${late ? `⚠ 이대로면 ${eff - r.event.d}일 늦어요. ${esc(r.event.name)} 피해를 막지 못할 수 있어요.` : '✓ 위기 전에 공급할 수 있어요!'}</div>
      <div class="label" style="margin-top:10px">배송 방법</div>
      <div class="list"><button class="card ${!R.express ? 'sel' : ''}" data-ex="0"><span class="row"><span class="t">📦 계약 납기대로 공급</span><span class="pill">추가 0</span></span><span class="d">납기 ${p[4]}일</span></button>
      <button class="card ${R.express ? 'sel' : ''}" data-ex="1" ${canEx ? '' : 'disabled'}><span class="row"><span class="t">🚨 긴급 조달 요청</span><span class="pill bad">+${ex.cost}코인</span></span><span class="d">${p[4] <= r.event.d ? '이미 제때 도착해서 필요 없어요.' : canEx ? `예비비로 납기 ${ex.days}일 단축 → ${Math.max(1, p[4] - ex.days)}일` : '예비비가 부족해요.'}</span></button></div>
      ${tipCard('event')}<div class="btnrow">${back('product', '제품 다시 고르기')}</div>
      <button class="primary" id="go"><span>🚚 공급 시작</span><span>→</span></button>`;
  }
  if (R.phase === 'install') {
    const base = performance.now() - R.t0 - (R.res.late ? TL.strike : 0), idx = installIdx(base);
    const items = [...(R.res.late ? [`${r.event.icon} ${r.event.name} 먼저 도착`] : []), '🚚 공급 차량 도착', '📦 장비·물품 하역', '🔧 시설 조립·설치', '⚡ 시설 작동 시작', '😊 주민 생활 변화'];
    const off = R.res.late ? 1 : 0, cur = idx + off;
    P.innerHTML = `<div class="tag"><span>STEP 5 · 지역 회복</span><span>공급 중</span></div><h2>${esc(r.item)} 공급·설치</h2>
      ${quoteBox('bandit', '반딧대왕 · 시설 설치 담당', '자로 재고, 블록을 맞추고! 정확한 위치에 단단히 설치하겠다.')}
      <ul class="log">${items.map((s, i) => `<li class="${i < cur ? 'on' : i === cur ? 'now' : ''}">${i < cur ? '✓' : i === cur ? '▶' : '·'} ${s}</li>`).join('')}</ul>
      ${tipCard('install')}<button class="primary" id="skip2"><span>⏭ 결과 바로 보기</span><span>→</span></button>`;
  }
  if (R.phase === 'result') {
    const s = R.res, best = save.best[r.id];
    P.innerHTML = `<div class="tag"><span>지역 회복 결과</span><span>최고 ${best ? best.score : s.total}점</span></div><h2>${esc(r.name)} ${s.stars === 3 ? '완벽 회복!' : s.stars === 2 ? '회복 성공!' : '절반의 회복'}</h2>
      <div class="stars">${'★'.repeat(s.stars)}<span class="off">${'★'.repeat(3 - s.stars)}</span></div>
      <div class="total"><b>${s.total}</b> / 100점 ${R.newBest ? '· 🏅 최고 기록!' : ''}</div>
      <div class="bars">${SCORE_PARTS.map(([k, n, m]) => `<div class="barrow"><span>${n}</span><span class="track"><span class="fill" style="display:block;width:${s.parts[k] / m * 100}%"></span></span><b>${s.parts[k]}/${m}</b></div>`).join('')}</div>
      <div class="lessons">${lessons(r, s).map(([c, t]) => `<div class="lesson ${c}">${t}</div>`).join('')}</div>
      ${tipCard('result')}<button class="primary" id="go"><span>${doneCount() === 17 && !save.seenFinal ? '전국 회복 결과 보기' : '전국 지도로 돌아가기'}</span><span>→</span></button>
      <div class="btnrow"><button class="sec" id="retry">↻ 다시 도전</button>${nextRecommended() ? `<button class="sec" id="nextReg">다음 추천: ${byId[nextRecommended()].name} →</button>` : ''}</div>`;
  }
  bindPanel();
}
function notes() { return R.heard.length ? `<div class="notes">${R.heard.map(i => `<div class="note">📝 ${esc(reg.residents[i].clue)}</div>`).join('')}</div>` : `<div class="notes"><div class="note">📝 조사한 내용이 없어요. 주민 이야기를 들으면 힌트가 생겨요.</div></div>` }
function lessons(r, s) {
  const out = [], p = r.products[R.prod];
  if (!s.meets) out.push(['bad', `가격은 낮았지만 필요한 ${r.perf} ${r.min}을(를) 채우지 못했어요 (성능 ${p[2]}).`]);
  if (s.late) out.push(['bad', `납기가 ${s.eff - r.event.d}일 늦어 ${r.event.name}에 대비하지 못했어요. 위기 상황에선 납기가 핵심!`]);
  else if (R.express) out.push(['good', `예비비로 긴급 조달을 요청해 ${r.event.name} 전에 공급했어요.`]);
  else out.push(['good', `${r.event.name} 전에 제때 공급했어요.`]);
  if (s.parts.care <= 4) out.push(['bad', `연 유지비 ${p[3]}코인 · 생애주기비용(5년) ${p[1] + p[3] * 5}코인. 구입가만 보면 장기 지출을 놓쳐요.`]);
  if (R.pri === r.focus) out.push(['good', `주민이 가장 원한 「${PRI[r.focus].n}」을 먼저 챙겼어요.`]);
  else out.push(['', `주민들의 이야기를 다시 보면 「${PRI[r.focus].n}」이 더 필요했어요.`]);
  if (R.heard.length < 3) out.push(['', `주민 ${3 - R.heard.length}명의 이야기를 더 들었다면 숨은 조건을 알 수 있었어요.`]);
  if (INNOVATIVE[r.id] === R.prod) out.push(['good', '새 기술이 담긴 혁신제품을 공공이 먼저 구매해 현장에서 써봤어요. 좋은 기술이 자랄 기회가 돼요.']);
  if (s.stars === 3) out.push(['good', '필요한 곳에, 필요한 것을, 제때! 좋은 조달이에요.']);
  return out;
}
function bindPanel() {
  const P = $('panel');
  P.querySelectorAll('[data-hear]').forEach(b => b.onclick = () => hear(+b.dataset.hear));
  P.querySelectorAll('[data-pri]').forEach(b => b.onclick = () => { R.pri = b.dataset.pri; if (R.prod != null && reg.products[R.prod][1] > capOf(reg, R.pri)) R.prod = null; sfx.tap(); renderRegion() });
  P.querySelectorAll('[data-prod]').forEach(b => b.onclick = () => { R.prod = +b.dataset.prod; R.express = false; sfx.tap(); renderRegion() });
  P.querySelectorAll('[data-ex]').forEach(b => b.onclick = () => { R.express = b.dataset.ex === '1'; sfx.tap(); renderRegion() });
  P.querySelectorAll('[data-back]').forEach(b => b.onclick = () => { R.phase = b.dataset.back; renderRegion() });
  const go = $('go'); if (go) go.onclick = advance;
  const sk = $('skip2'); if (sk) sk.onclick = skipInstall;
  const rt = $('retry'); if (rt) rt.onclick = () => startRegion(reg.id);
  const nx = $('nextReg'); if (nx) nx.onclick = () => travelTo(nextRecommended());
}
function hear(i) {
  if (!R || R.phase !== 'survey') return;
  if (!R.heard.includes(i)) R.heard.push(i);
  R.say = { id: 'r' + i, text: reg.residents[i].line }; R.sayUntil = performance.now() + 7000; sfx.tap(); renderRegion();
}
function advance() {
  const r = reg;
  if (R.phase === 'survey') { R.phase = 'budget'; R.say = null }
  else if (R.phase === 'budget') R.phase = 'product';
  else if (R.phase === 'product') { R.phase = 'event'; R.express = false; sfx.warn() }
  else if (R.phase === 'event') {
    R.res = scoreRegion(r, { heard: R.heard.length, pri: R.pri, prod: R.prod, express: R.express });
    R.phase = 'install'; R.t0 = performance.now(); R.say = null; sfx.truck();
  }
  else if (R.phase === 'result') {
    if (doneCount() === 17 && !save.seenFinal) { show('map'); showFinal(); }
    else { show('map'); mapSel = nextRecommended() || r.id; renderMap() }
    return;
  }
  renderRegion();
}
function installIdx(base) { return base < 0 ? -1 : base < TL.truck ? 0 : base < TL.unload ? 1 : base < TL.built ? 2 : base < TL.active ? 3 : 4 }
function skipInstall() { if (R && R.phase === 'install') R.t0 = performance.now() - TL.end - (R.res.late ? TL.strike : 0) - 1 }
function finishInstall() {
  const r = reg, s = R.res, prev = save.best[r.id];
  R.newBest = !prev || s.total > prev.score;
  if (R.newBest) save.best[r.id] = { score: s.total, stars: s.stars, parts: s.parts, prod: R.prod, pri: R.pri, express: R.express };
  persist(); R.phase = 'result'; R.doneAt = performance.now(); confettiAt = s.stars >= 2 ? performance.now() : -1e9; sfx.done();
  R.say = { id: 'r0', text: s.late ? '조금 늦었지만… ' + r.thanks : !s.meets ? '고마워요. 그런데 성능이 조금 아쉬워요.' : r.thanks, good: true }; R.sayUntil = performance.now() + 9000;
  renderRegion();
}

// ── 엔진에 넘기는 장면 상태 ──
function sceneState(t) {
  const st = { reg, built: false, b: 0, active: false, late: false, q: 'ok', storm: .3, pri: null, say: null, travel: 0, activeAt: 0, dark: 0, windowsLit: false };
  if (view === 'title' || !R) { Object.assign(st, { built: true, b: 1, active: true, activeAt: -1e6, pri: 'comfort' }); return st }
  st.pri = R.pri; st.travel = Math.max(0, 1 - (t - R.arriveAt) / 900); st.travelText = `다랑이가 ${reg.name}(으)로 안내 중…`;
  if (R.phase === 'event') st.storm = .6;
  if (R.phase === 'install') {
    const s = R.res, base = t - R.t0 - (s.late ? TL.strike : 0);
    Object.assign(st, { late: s.late, q: s.meets ? 'ok' : 'low', storm: base < 0 ? 1 : base >= TL.built ? .9 : .55, built: base >= TL.unload, b: Math.max(0, Math.min(1, (base - TL.unload) / (TL.built - TL.unload))), active: base >= TL.built, activeAt: R.t0 + (s.late ? TL.strike : 0) + TL.built, base });
    if (installIdx(base) !== lastStepIdx) { lastStepIdx = installIdx(base); if (lastStepIdx === 3) { confettiAt = t; sfx.ok() } renderPanel(); updateMapState(t) }
    if (base >= TL.end) setTimeout(finishInstall, 0), R.phase = 'finishing';
  }
  if (R.phase === 'finishing' || R.phase === 'result') {
    const s = R.res; Object.assign(st, { late: s.late, q: s.meets ? 'ok' : 'low', storm: .7, built: !R.showBefore, b: 1, active: !R.showBefore, activeAt: R.doneAt - 2000 });
  }
  if (R.say && t < R.sayUntil) st.say = R.say;
  return st;
}
function lerp(a, b, k) { return a + (b - a) * k }
function ease(k) { k = Math.max(0, Math.min(1, k)); return k * k * (3 - 2 * k) }
function drawActors(S) {
  const r = S.reg, Lr = L(r.id), t = S.t;
  const phase = view === 'title' || !R ? 'title' : R.phase;
  r.residents.forEach((res, i) => {
    let [x, y] = Lr.res[i]; let key = res.k;
    if (res.lying && S.active) key = 'chief';
    const heard = R && R.heard.includes(i), surv = phase === 'survey';
    S.actor('r' + i, x, y, key, { name: res.n, mark: surv ? (heard ? '✓' : '?') : null, ring: surv && !heard ? '#e8aa49' : null, hop: phase === 'result' && !S.late && i === 0 && S.active });
  });
  const T = Lr.team;
  // 주연 나르미·달이는 모든 단계에 등장, 조연은 패널과 설치 장면에 등장
  S.actor('narmi', T[0][0], T[0][1], 'narmi', { hop: phase === 'result' && S.active });
  S.actor('dari', T[1][0], T[1][1], 'dari', { hop: phase === 'result' && S.active });
  // 공급 차량 → 하역 → 설치 담당
  if (phase === 'install' || phase === 'finishing') {
    const base = S.base ?? 1e9, lane = Lr.lane, stop = Lr.stop;
    if (base >= 0 && base < TL.end) {
      let x, a = 1;
      if (base < TL.truck) x = lerp(13.5, stop, ease(base / TL.truck)); else if (base < TL.active) x = stop; else x = lerp(stop, -3.5, ease((base - TL.active) / (TL.end - TL.active)));
      if (x > 11.4) a = Math.max(0, (13.5 - x) / 2.1); if (x < -.6) a = Math.max(0, (x + 3.5) / 2.9);
      S.truck(x, lane, { a, cargo: base < TL.truck + 200 ? 3 : base < TL.unload ? 3 - Math.floor((base - TL.truck) / ((TL.unload - TL.truck) / 3)) : 0 });
      if (base >= TL.truck && base < TL.built) { for (let i = 0; i < 3; i++) { const k = Math.max(0, Math.min(1, (base - TL.truck - i * 230) / 450)); if (k <= 0 || base > TL.unload + 300) continue; const [cx, cy] = Lr.crew; S.crate(lerp(stop + 1.2, cx - .9 + i * .45, k), lerp(lane + .2, cy - .5, k), Math.sin(k * Math.PI) * 1.2 + (1 - k) * 1.2) } }
    }
    if (base >= TL.truck - 200) { const [cx, cy] = Lr.crew; S.actor('bandit', cx, cy, 'bandit', { hop: base > TL.unload && base < TL.built }); if (base > TL.unload && base < TL.built) S.say = { id: 'bandit', text: '뚝딱뚝딱! 정확한 자리에 조립 중!' }; if (base >= TL.built && base < TL.built + 1400) S.say = { id: 'bandit', text: '설치 완료! 작동 시작!', good: true } }
  }
  if (phase === 'result' && S.active) { const [cx, cy] = Lr.crew; S.actor('bandit', cx, cy, 'bandit') }
  if (S.active && Lr.cars && phase !== 'install') { S.car(((t * .0016) % 16) - 2.5, 9.2, '#5f8fb7', { lights: S.dark > 0 }); S.car(((t * .0016 + 7) % 16) - 2.5, 9.2, '#e8aa49', { lights: S.dark > 0 }) }
}
function onActorClick(id) { if (id.startsWith('r') && R && R.phase === 'survey') hear(+id.slice(1)) }
function clickable(id) { return id.startsWith('r') && R && R.phase === 'survey' }
function travelTo(id) { startRegion(id); sfx.tap() }

// ── 전국 지도 (SVG) ──
const COAST = [[37.73, 126.55], [37.95, 126.85], [38.25, 127.15], [38.3, 127.55], [38.32, 128.0], [38.62, 128.36], [38.35, 128.55], [38.05, 128.75], [37.8, 128.92], [37.55, 129.12], [37.25, 129.32], [36.95, 129.42], [36.55, 129.43], [36.05, 129.57], [35.95, 129.48], [35.6, 129.45], [35.35, 129.36], [35.15, 129.2], [35.07, 129.05], [35.05, 128.85], [34.9, 128.7], [34.78, 128.45], [34.85, 128.1], [34.75, 127.8], [34.62, 127.6], [34.5, 127.3], [34.55, 127.05], [34.4, 126.85], [34.3, 126.55], [34.5, 126.3], [34.8, 126.38], [35.05, 126.3], [35.35, 126.45], [35.6, 126.5], [35.85, 126.65], [36.1, 126.55], [36.4, 126.5], [36.7, 126.15], [36.95, 126.35], [36.95, 126.8], [37.1, 126.7], [37.3, 126.6], [37.45, 126.58], [37.62, 126.52]];
const MAPPOS = { sejong: [36.72, 127.02], daejeon: [36.3, 127.42] };
function proj(lat, lon) { return [(lon - 125.55) * 100, (38.78 - lat) * 122] }
function regPos(r) { const [la, lo] = MAPPOS[r.id] || [r.lat, r.lon]; return proj(la, lo) }
function buildMapSVG() {
  const pts = COAST.map(([a, b]) => proj(a, b).map(v => v.toFixed(1)).join(',')).join(' '), [jx, jy] = proj(33.38, 126.55);
  const isl = [[34.62, 126.05, 7], [34.4, 126.25, 5], [34.45, 127.75, 5], [37.5, 126.4, 5]].map(([a, b, r]) => { const [x, y] = proj(a, b); return `<circle cx="${x}" cy="${y}" r="${r}"/>` }).join('');
  const land = `<polygon points="${pts}"/><ellipse cx="${jx}" cy="${jy}" rx="40" ry="19"/>${isl}`;
  const route = ROUTE.map(id => regPos(byId[id]).join(',')).join(' ');
  return `<svg viewBox="0 0 430 700" preserveAspectRatio="xMidYMid meet" role="img" aria-label="대한민국 17개 시·도 캠페인 지도">
  <defs><pattern id="studs" width="14" height="14" patternUnits="userSpaceOnUse"><circle cx="7" cy="7" r="3.2" fill="#00000012"/><circle cx="6.3" cy="6.2" r="2.2" fill="#ffffff40"/></pattern>
  <clipPath id="landClip">${land}</clipPath><filter id="soft"><feGaussianBlur stdDeviation="14"/></filter></defs>
  <g fill="#a9c7b0" transform="translate(4,8)">${land}</g>
  <g fill="#f4efd9" stroke="#ffffff" stroke-width="3" stroke-linejoin="round">${land}</g>
  <g clip-path="url(#landClip)"><g id="mapGlow" filter="url(#soft)"></g><rect width="430" height="700" fill="url(#studs)"/></g>
  <polyline points="${route}" fill="none" stroke="#8aa596" stroke-width="2" stroke-dasharray="4 5" stroke-linecap="round"/>
  <g id="mapRoute"></g><g id="mapMarks"></g>
  <text x="300" y="640" font-size="13" fill="#5f8a9f" font-weight="bold" font-family="Arial,'Malgun Gothic',sans-serif">🌊 바다 건너 제주로</text></svg>`;
}
function renderMap() {
  const K = $('korea'); if (!K.firstChild) K.innerHTML = buildMapSVG() + `<div class="legend"><span><i style="background:#6e9473"></i>회복 완료</span><span><i style="background:#fff;border:1px solid #bbb"></i>도전 전</span><span><i style="background:#e8aa49"></i>추천 다음 지역</span></div>`;
  const rec = nextRecommended(); if (!mapSel) mapSel = rec || 'seoul';
  $('mapGlow').innerHTML = REGIONS.filter(r => save.best[r.id]).map(r => { const [x, y] = regPos(r); return `<circle cx="${x}" cy="${y}" r="46" fill="${r.color}" opacity=".55"/>` }).join('');
  let done = ROUTE.filter(id => save.best[id]);
  $('mapRoute').innerHTML = '';
  $('mapMarks').innerHTML = REGIONS.map(r => {
    const [x, y] = regPos(r), b = save.best[r.id], sel = r.id === mapSel, isRec = r.id === rec;
    return `<g class="mk" data-reg="${r.id}" tabindex="0" role="button" aria-label="${r.full} ${r.mission} ${b ? '완료 별 ' + b.stars + '개' : '미완료'}" transform="translate(${x.toFixed(1)},${y.toFixed(1)})">
      ${isRec ? `<circle r="24" fill="none" stroke="#e8aa49" stroke-width="3"><animate attributeName="r" values="20;27;20" dur="1.6s" repeatCount="indefinite"/><animate attributeName="opacity" values="1;.3;1" dur="1.6s" repeatCount="indefinite"/></circle>` : ''}
      <ellipse cx="2" cy="5" rx="17" ry="13" fill="#2a4a3a22"/>
      <circle class="pin" r="17" fill="${b ? r.color : '#ffffff'}" stroke="${sel ? '#254e40' : b ? '#ffffff' : '#c9d3c4'}" stroke-width="${sel ? 3.5 : 2}"/>
      <text y="5.5" text-anchor="middle" font-size="15">${b ? r.icon : '?'}</text>
      <g transform="translate(0,30)"><rect x="-21" y="-10" width="42" height="15" rx="7" fill="${b ? '#254e40' : '#ffffffdd'}"/><text y="1.5" text-anchor="middle" font-size="10" font-weight="bold" fill="${b ? '#fff' : '#3f5b52'}">${r.name}</text></g>
      ${b ? `<text y="49" text-anchor="middle" font-size="10" fill="#e0a43c" stroke="#fff" stroke-width="2.4" paint-order="stroke">${'★'.repeat(b.stars)}</text>` : ''}</g>`
  }).join('');
  K.querySelectorAll('.mk').forEach(g => { g.onclick = () => { mapSel = g.dataset.reg; sfx.tap(); renderMap() }; g.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); mapSel = g.dataset.reg; renderMap(); $('btnGo') && $('btnGo').focus() } } });
  $('mDay').textContent = `회복 ${doneCount()} / 17 · ★ ${totalStars()} / 51`;
  const r = byId[mapSel], b = save.best[r.id], dc = doneCount();
  $('mapPanel').innerHTML = `<div class="tag"><span>선택한 지역</span><span>${b ? '최고 ' + b.score + '점' : '도전 전'}</span></div>
    <h2>${r.icon} ${esc(r.full)}</h2>
    ${quoteBox('narmi', '나르미 · 조달 원정대장', `${esc(r.town)}에서 「${esc(r.mission)}」 임무가 기다려요. 조달 품목은 ${esc(r.item)}!`)}
    <div class="chips"><span class="chip">예산 ${r.budget}코인</span><span class="chip warn">${r.event.icon} ${esc(r.event.name)}</span>${b ? `<span class="chip" style="color:#e0a43c">${starStr(b.stars)}</span>` : ''}</div>
    <button class="primary" id="btnGo" style="margin:4px 0 12px"><span>${b ? '↻ 최고 점수 재도전' : '🚐 이 지역으로 출발'}</span><span>→</span></button>
    <div class="label">17개 시·도 <span>추천 순서 · ${dc}곳 회복</span></div>
    <div class="regionlist">${ROUTE.map(id => { const x = byId[id], bb = save.best[id]; return `<button class="rbtn ${bb ? 'done' : ''} ${id === mapSel ? 'sel' : ''} ${id === rec ? 'rec' : ''}" data-pick="${id}">${x.name}<small>${bb ? '★'.repeat(bb.stars) : id === rec ? '추천' : ''}</small></button>` }).join('')}</div>
    <div class="btnrow">${dc === 17 ? '<button class="sec" id="btnFinal">🏆 전국 회복 결과</button>' : ''}<button class="ghost" id="btnReset">처음부터 다시 시작</button></div>`;
  $('btnGo').onclick = () => travelTo(r.id);
  $('mapPanel').querySelectorAll('[data-pick]').forEach(b => b.onclick = () => { mapSel = b.dataset.pick; sfx.tap(); renderMap() });
  $('btnReset').onclick = confirmReset;
  const bf = $('btnFinal'); if (bf) bf.onclick = showFinal;
}
function confirmReset() {
  openModal(`<div class="eyebrow">RESET</div><h2>처음부터 다시 시작할까요?</h2><p>17개 지역의 기록과 별이 모두 지워져요. 이 작업은 되돌릴 수 없어요.</p><button class="primary" id="mReset"><span>기록 지우고 처음부터</span><span>→</span></button><button class="ghost" id="mCancel">취소</button>`);
  $('mReset').onclick = () => { save = { best: {}, seenFinal: false }; persist(); mapSel = 'seoul'; closeModal(); renderMap() };
  $('mCancel').onclick = closeModal;
}
function showFinal() {
  save.seenFinal = true; persist(); renderMap();
  const sc = Object.values(save.best), avg = Math.round(sc.reduce((a, b) => a + b.score, 0) / Math.max(1, sc.length)), stars = totalStars();
  openModal(`<div class="eyebrow">NATIONWIDE RECOVERY COMPLETE</div><h2>🇰🇷 전국 17개 시·도가 회복되었어요!</h2>
    <p>원정대가 조사하고, 비교하고, 제때 공급한 덕분에 대한민국 곳곳의 일상이 달라졌어요.</p>
    <div class="summary" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px"><div class="stat"><small>평균 점수</small><strong>${avg}</strong><em>/100</em></div><div class="stat"><small>모은 별</small><strong>${stars}</strong><em>/51</em></div><div class="stat"><small>완벽 회복</small><strong>${sc.filter(x => x.stars === 3).length}</strong><em>/17</em></div></div>
    <div class="finalgrid">${ROUTE.map(id => `<div>${byId[id].icon} ${byId[id].name}<small>${'★'.repeat(save.best[id] ? save.best[id].stars : 0)}</small></div>`).join('')}</div>
    <img class="ppslogo" src="${ASSETS.ppsLogo}" alt="조달청" style="display:block;margin:0 auto 10px">
    <p class="message">우리의 선택이 지역을 살립니다.<br>필요한 곳에, 필요한 것을.<br>조달로 연결되는 대한민국.</p>
    <button class="primary" id="mClose"><span>완성된 전국 지도 보기</span><span>→</span></button><div class="btnrow"><button class="sec" id="mRestart">처음부터 다시 도전</button></div>`, true);
  $('mClose').onclick = closeModal; $('mRestart').onclick = confirmReset;
}

// ── 타이틀·도움말 ──
function showTitle() {
  view = 'title'; reg = byId.seoul; R = null; show('title'); renderTitleRegion();
  const has = doneCount() > 0;
  openModal(`<div class="titlecard"><img class="ppslogo" src="${ASSETS.ppsLogo}" alt="조달청"><div class="sub">우리 마을 조달청 · 확장 캠페인</div><h2>전국 조달 원정대</h2>
    <p>전국 17개 시·도를 여행하며 주민의 이야기를 듣고, 제한된 예산으로 꼭 맞는 제품을 제때 공급해 지역을 회복시켜요.</p>
    <div class="lead">${LEAD.map(([k, n, d]) => `<div><img src="${portrait(k)}" alt=""><span><small>주연 · 조달청 마스코트</small><b>${n}</b>${d}</span></div>`).join('')}</div>
    <div class="label">함께하는 원정대 <span>조연</span></div>
    <div class="team">${TEAM.map(([k, n, d]) => `<div><img src="${portrait(k)}" alt=""><b>${n}</b>${d}</div>`).join('')}</div>
    <button class="primary" id="tStart"><span>${has ? `이어하기 (${doneCount()}/17 회복)` : '원정 시작하기'}</span><span>→</span></button>
    <div class="btnrow"><button class="sec" id="tHelp">게임 방법</button>${has ? '<button class="ghost" id="tReset">처음부터 다시 시작</button>' : ''}</div></div>`);
  $('tStart').onclick = () => { closeModal(); mapSel = nextRecommended() || 'seoul'; show('map') };
  $('tHelp').onclick = showHelp;
  const tr = $('tReset'); if (tr) tr.onclick = () => { save = { best: {}, seenFinal: false }; persist(); showTitle() };
}
function renderTitleRegion() {
  $('rEyebrow').textContent = 'BLOCK VILLAGE JOURNEY'; $('rTitle').textContent = '오늘도, 전국을 부탁해요.'; $('rSub').textContent = '필요를 듣고, 꼼꼼히 고르고, 제때 공급하면 일상이 달라집니다.';
  $('rDay').textContent = `원정 ${String(doneCount()).padStart(2, '0')} / 17 회복`; $('townName').textContent = '서울 · 한빛동'; $('townType').textContent = '원정 출발지'; $('weather').textContent = '☀ 맑음';
  $('steps').innerHTML = STEPS.map(([k, n, d], i) => `<div class="step"><small>${i + 1}</small><b>${n}</b><span>${d}</span></div>`).join('');
  $('mapstate').className = 'mapstate solved'; $('mapstate').textContent = '✓ 조달로 달라진 마을'; $('mapmsg').textContent = '좋은 조달은 가장 싼 것이 아니라, 필요한 것을 알맞은 값에 제때 공급하는 것이에요.';
  $('btnSkip').classList.add('hidden'); $('btnCompare').classList.add('hidden');
  $('sBudget').textContent = '-'; $('sBudgetTot').textContent = ''; $('sMid').textContent = '-'; $('sMidTot').textContent = ''; $('sDone').textContent = doneCount();
  $('panel').innerHTML = `<div class="tag"><span>HOW TO PLAY</span></div><h2>지역마다 5단계</h2><ul class="log">${STEPS.map(([k, n, d]) => `<li class="on">${n} · ${d}</li>`).join('')}</ul><p class="hint">점수: 주민 만족도 30 · 예산 운영 20 · 제품 적합성 25 · 납기·위기 대응 15 · 유지관리 효율 10</p>`;
}
function showHelp() {
  openModal(`<div class="eyebrow">HOW TO PLAY</div><h2>좋은 조달의 5단계</h2>
    <p>① <b>현장 조사</b> — 장면 속 주민을 눌러 이야기를 들어요. 숨은 조건(성능 기준·마감일·유지비 걱정)이 나와요.<br>
    ② <b>예산 배분</b> — 안전시설·편의시설·유지관리 중 무엇을 먼저 할지 정해요. 우선순위에 따라 구매 한도와 예비비가 달라져요.<br>
    ③ <b>제품 비교</b> — 나라장터처럼 A형 경제형·B형 균형형·C형 고급형의 가격·성능·연 유지비·납기를 비교해요.<br>
    ④ <b>긴급 상황</b> — 기상·안전 이벤트 전에 도착하는지 확인하고, 필요하면 예비비로 긴급 조달을 요청해요.<br>
    ⑤ <b>지역 회복</b> — 공급 차량 도착 → 하역 → 조립 → 작동 → 주민 생활 변화를 확인해요.</p>
    <p>✦ 표시는 새로운 기술이 담긴 <b>혁신제품</b>이에요. 5년 총비용은 <b>생애주기비용</b>, 즉 사는 값 + 쓰는 동안의 관리비예요.</p>
    <p><b>점수(100점)</b> 주민 만족도 30 · 예산 운영 20 · 제품 적합성 25 · 납기·위기 대응 15 · 유지관리 효율 10 → 85점 이상 ★★★, 65점 이상 ★★</p>
    <p style="font-size:11px">진행 기록은 이 브라우저에 자동 저장돼요. 게임 코인과 제품·지역 상황은 모두 가상입니다.</p>
    <button class="primary" id="hClose"><span>알겠어요</span><span>→</span></button>`);
  $('hClose').onclick = () => { closeModal(); if (view === 'title') showTitle() };
}

// ── 이벤트 연결 ──
$('btnMap').onclick = () => {
  closeModal();
  if (view === 'region' && R && R.phase !== 'result' && R.phase !== 'survey') {
    openModal(`<div class="eyebrow">LEAVE MISSION</div><h2>임무를 중단할까요?</h2><p>${esc(reg.name)} 임무의 이번 진행 내용은 저장되지 않아요. (이전 최고 기록은 유지돼요)</p><button class="primary" id="mLeave"><span>전국 지도로 가기</span><span>→</span></button><button class="ghost" id="mStay">계속하기</button>`);
    $('mLeave').onclick = () => { closeModal(); R = null; show('map') }; $('mStay').onclick = closeModal; return;
  }
  R = null; show('map');
};
$('btnHelp').onclick = showHelp;
$('btnSound').onclick = () => { sound = !sound; $('btnSound').textContent = sound ? '🔊 소리 끄기' : '🔈 소리 켜기'; $('btnSound').setAttribute('aria-pressed', sound); sfx.ok() };
$('btnSkip').onclick = skipInstall;
$('btnCompare').onclick = () => { R.showBefore = !R.showBefore; updateMapState(performance.now()) };
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('overlay').classList.contains('hidden') && view !== 'title') closeModal() });

// 이미지가 준비되면 초상화가 들어간 화면을 다시 그림
let pending = Object.values(IMG).filter(im => !im.complete).length;
Object.values(IMG).forEach(im => { if (!im.complete) im.onload = () => { if (--pending === 0) refreshUI() } });
function refreshUI() { if (view === 'title') { if (!$('overlay').classList.contains('hidden') && $('tStart')) showTitle(); renderTitleRegion() } else if (view === 'map') renderMap(); else renderRegion() }

frame();
if (DEMO) runDemo(); else showTitle();
