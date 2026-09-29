// Renders every Shootbook frame to a 1080x1920 PNG and writes the shot list CSV.
// Run from this src/ folder:  node Giniroisenkou_Shootbook_render.js
// Needs Node and Playwright (npm i playwright) with a Chromium browser installed.
// Output: ../frames/Giniroisenkou_Shootbook_<CODE>_<Name>.png and ../Giniroisenkou_Shootbook_shot_list.csv
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const PAGE = path.join(__dirname, 'Giniroisenkou_Shootbook_render_page.html');
const OUT = path.join(__dirname, '..', 'frames');
const CSV = path.join(__dirname, '..', 'Giniroisenkou_Shootbook_shot_list.csv');
const CATS = { SZ: 'Shot size', AN: 'Camera angle', CP: 'Composition', SB: 'People in frame', MV: 'Camera movement',
  DA: 'Dance', HK: 'Hiking', EV: 'Events', SW: 'Swing and live band', TR: 'Transitions' };

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  // Frames are drawn at 180 x 320 CSS px; a device scale of 6 gives 1080 x 1920 with line weights kept in proportion.
  const page = await browser.newPage({ viewport: { width: 400, height: 600 }, deviceScaleFactor: 6 });
  await page.goto('file://' + PAGE);
  await page.evaluate(() => {
    document.documentElement.setAttribute('data-theme', 'light');
    document.body.style.padding = '0';
    document.body.innerHTML = '<div id="stage" style="position:fixed;left:0;top:0;background:#fff;line-height:0"></div>';
  });
  const rows = await page.evaluate(() => {
    const c = {};
    return window.__shots.map((r, i) => { c[r[0]] = (c[r[0]] || 0) + 1;
      return { i, cat: r[0], ctx: r[1], name: r[2], note: r[3], code: r[0] + '-' + String(c[r[0]]).padStart(2, '0') }; });
  });
  for (const r of rows) {
    r.file = `Giniroisenkou_Shootbook_${r.code}_${r.name.replace(/[^A-Za-z0-9]+/g, '-').replace(/-+$/, '')}.png`;
    const label = `${r.code}  ${r.name}`, fsz = 4, lw = label.length * fsz * 0.62 + fsz * 1.6;
    await page.evaluate(({ i, label, lw, fsz }) => {
      document.getElementById('stage').innerHTML =
        `<svg class="fr" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 90 160" style="width:180px;height:320px;aspect-ratio:auto;display:block">` +
        `<rect class="bgr" x="0" y="0" width="90" height="160"/>${window.__svg(i, false)}` +
        `<rect x="3" y="3" width="${lw}" height="${fsz * 1.7}" rx="${fsz * .4}" fill="#17191B"/>` +
        `<text x="${3 + fsz * .8}" y="${3 + fsz * 1.22}" font-family="IBM Plex Mono, DejaVu Sans Mono, Consolas, monospace" font-size="${fsz}" fill="#ffffff">${label}</text></svg>`;
    }, { i: r.i, label, lw, fsz });
    await page.screenshot({ path: path.join(OUT, r.file), clip: { x: 0, y: 0, width: 180, height: 320 } });
  }
  const esc = v => `"${String(v).replace(/"/g, '""')}"`;
  const ctxName = x => x === 'dhes' ? 'any' : x.split('').map(k => ({ d: 'dance', h: 'hiking', e: 'events', s: 'swing' })[k]).join(' / ');
  fs.writeFileSync(CSV, 'code,category,name,note,context,file\n' +
    rows.map(r => [r.code, CATS[r.cat], r.name, r.note, ctxName(r.ctx), r.file].map(esc).join(',')).join('\n') + '\n');
  console.log(`${rows.length} frames written to ${OUT}`);
  await browser.close();
})();
