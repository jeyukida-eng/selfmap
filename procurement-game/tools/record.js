// ?demo 모드를 1920×1080으로 녹화 → ffmpeg로 MP4 변환 (node tools/record.js 출력폴더)
const { chromium } = require('playwright'); const path = require('path'); const fs = require('fs');
const OUT = path.resolve(process.argv[2] || 'video');
(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1, recordVideo: { dir: OUT, size: { width: 1920, height: 1080 } } });
  const page = await ctx.newPage(); const errs = [];
  page.on('pageerror', e => errs.push(e.message));
  await page.goto('file://' + path.resolve(__dirname, '../dist/woorimaeul-jodal.html') + '?demo');
  await page.waitForTimeout(63000);
  await page.screenshot({ path: OUT + '/demo_end.png' });
  const v = page.video(); await ctx.close(); await browser.close();
  console.log(await v.path(), 'errors', errs);
})();
