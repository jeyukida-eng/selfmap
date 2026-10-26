// ── 시연영상 자동 재생 모드 (?demo) ─────────────────────────────
// 실제 게임 함수를 그대로 호출해 약 60초 동안 한 지역(제주)을 플레이하고 전국 회복 화면으로 마무리합니다.
// 저장 기록은 건드리지 않습니다(DEMO일 때 persist 비활성).
async function runDemo() {
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const click = async (sel, ms = 900) => { const el = typeof sel === 'string' ? document.querySelector(sel) : sel; if (el) { el.style.outline = '4px solid #e8aa49'; await wait(450); el.click() } await wait(ms) };
  save = { best: {}, seenFinal: false };
  showTitle(); await wait(3200);                                   // 0~3초: 타이틀
  await click('#tStart', 600);                                      // 3~7초: 전국 지도
  mapSel = 'jeju'; renderMap(); await wait(2200);
  await click('#btnGo', 1600);                                      // 7~17초: 현장 조사
  for (let i = 0; i < 3; i++) await click(`[data-hear="${i}"]`, 2300);
  await click('#go', 1500);                                         // 17~28초: 예산·제품 비교
  await click('[data-pri="safety"]', 1300); await click('#go', 1600);
  await click('[data-prod="1"]', 1700); await click('[data-prod="2"]', 1800);
  await click('#go', 2600);                                         // 28~39초: 긴급 상황 → 공급
  await click('#go', 0);
  await wait(TL.end + 800);                                         // 39~50초: 설치·회복
  await wait(6400);                                                 // 결과·점수 확인
  show('map'); await wait(900);                                     // 50~60초: 전국 지도가 차례로 밝아짐(시연용 가상 완료)
  for (const [i, id] of ROUTE.entries()) { if (!save.best[id]) save.best[id] = { score: 84 + (i * 7) % 12, stars: i % 4 ? 3 : 2 }; mapSel = id; renderMap(); await wait(190) }
  await wait(1300);
  showFinal();
}
