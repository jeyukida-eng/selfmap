// 지역별 모든 선택 조합의 점수를 계산해 밸런스를 점검
const { REGIONS, PRI, scoreRegion, capOf, expressOf } = require('../src/data.js');
let issues = 0;
for (const r of REGIONS) {
  const rows = [];
  for (const pri of Object.keys(PRI)) for (let prod = 0; prod < 3; prod++) for (const express of [false, true]) {
    const price = r.products[prod][1];
    if (price > capOf(r, pri)) continue;
    const ex = expressOf(r);
    if (express && (price + ex.cost > r.budget)) continue;
    const s = scoreRegion(r, { heard: 3, pri, prod, express });
    if (express && !(r.products[prod][4] > r.event.d)) continue;
    rows.push({ pri, prod: 'ABC'[prod], express, total: s.total, stars: s.stars, ...s.parts });
  }
  rows.sort((a, b) => b.total - a.total);
  const best = rows[0], cheap = rows.filter(x => x.prod === 'A' && x.pri === r.focus)[0];
  console.log(`${r.name.padEnd(3)} best ${best.pri}/${best.prod}${best.express ? '+EX' : ''} ${best.total}  | A형+focus ${cheap ? cheap.total : '-'} | top3: ${rows.slice(0, 3).map(x => x.pri[0] + x.prod + (x.express ? '+' : '') + ':' + x.total).join(' ')}`);
  if (best.prod === 'A') { issues++; console.log('  !! cheapest is best'); }
  if (best.total < 85) { issues++; console.log('  !! no 3-star path'); }
}
console.log('issues', issues);
