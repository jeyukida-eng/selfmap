// 처음부터 17개 지역 끝까지 실제 클릭으로 플레이하며 오류·화면을 점검
const { chromium } = require('playwright');
const path = require('path');
const OUT = process.argv[2] || 'shots', W = +(process.argv[3] || 1440), H = +(process.argv[4] || 900), ONLY = process.argv[5];
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errors.push(m.text()) });
  page.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
  await page.goto('file://' + path.resolve(__dirname, '../dist/woorimaeul-jodal.html'));
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/00_title.png` });
  await page.click('#tStart'); await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/01_map.png` });
  const ids = await page.evaluate(() => ROUTE);
  let n = 0;
  for (const id of ids) {
    if (ONLY && !ONLY.split(',').includes(id)) continue;
    n++;
    await page.evaluate(id => { mapSel = id; renderMap() }, id);
    await page.click('#btnGo'); await page.waitForTimeout(1000);
    if (n <= 2 || ONLY) await page.screenshot({ path: `${OUT}/${id}_1survey.png` });
    for (let i = 0; i < 3; i++) await page.click(`[data-hear="${i}"]`);
    await page.click('#go');
    const best = await page.evaluate(id => { const r = byId[id]; let b = null; for (const pri of Object.keys(PRI)) for (let prod = 0; prod < 3; prod++) for (const ex of [false, true]) { if (r.products[prod][1] > capOf(r, pri)) continue; if (ex && (r.products[prod][4] <= r.event.d || r.products[prod][1] + expressOf(r).cost > r.budget)) continue; const s = scoreRegion(r, { heard: 3, pri, prod, express: ex }); if (!b || s.total > b.s.total) b = { pri, prod, ex, s } } return { pri: b.pri, prod: b.prod, ex: b.ex, total: b.s.total } }, id);
    // 일부 지역은 일부러 '최저가 A형'을 골라 결과 차이를 확인
    const cheap = ['busan', 'incheon'].includes(id);
    await page.click(`[data-pri="${best.pri}"]`); await page.click('#go');
    await page.click(`[data-prod="${cheap ? 0 : best.prod}"]`);
    if (n <= 2 || ONLY) await page.screenshot({ path: `${OUT}/${id}_2product.png` });
    await page.click('#go');
    if (best.ex && !cheap) await page.click('[data-ex="1"]');
    if (n <= 2 || ONLY) await page.screenshot({ path: `${OUT}/${id}_3event.png` });
    await page.click('#go');
    await page.waitForTimeout(ONLY ? 3600 : 400);
    if (ONLY) await page.screenshot({ path: `${OUT}/${id}_4install.png` });
    await page.click('#btnSkip');
    await page.waitForTimeout(1300);
    await page.screenshot({ path: `${OUT}/${id}_5result.png` });
    const res = await page.evaluate(() => ({ total: R.res.total, stars: R.res.stars, phase: R.phase }));
    console.log(id, cheap ? 'A형' : 'best', JSON.stringify(res));
    await page.click('#go'); await page.waitForTimeout(300);
  }
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/99_final.png` });
  if (await page.$('#mClose')) { await page.click('#mClose'); await page.waitForTimeout(300); await page.screenshot({ path: `${OUT}/99_map_done.png` }) }
  const saved = await page.evaluate(() => localStorage.getItem('umjc-nationwide-v1'));
  console.log('saved regions', saved ? Object.keys(JSON.parse(saved).best).length : 0);
  console.log('ERRORS', errors.length, errors.slice(0, 10));
  await browser.close();
})();
