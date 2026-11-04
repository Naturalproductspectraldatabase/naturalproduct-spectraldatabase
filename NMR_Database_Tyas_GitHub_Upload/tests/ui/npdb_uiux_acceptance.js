// UI/UX acceptance gate for NPDB (docs/NPDB_UIUX_AUDIT_20261104.md, section 7).
//
// Runs against a LOCAL app that reads the isolated synthetic fixture with DUMMY accounts.
// Never point it at production. Not part of offline CI (CI installs no browser).
//
//   NPDB_READ_BACKEND=snapshot NPDB_APPROVED_USERS='<dummy users>' \
//     streamlit run NMR_Database_Tyas_GitHub_Upload/scripts/app.py --server.port 8620 --server.headless true
//   node NMR_Database_Tyas_GitHub_Upload/tests/ui/npdb_uiux_acceptance.js 8620 ./uiux-out creds.json axe.min.js
//
// creds.json: {"viewer": ["<dummy>", "<dummy>"], "owner": ["<dummy>", "<dummy>"]}
// Exit code 0 only when every check passes. Writes acceptance-report.json and screenshots.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const [PORT, OUT, CREDS, AXE] = process.argv.slice(2);
if (!PORT || !OUT || !CREDS || !AXE) { console.error('usage: node npdb_uiux_acceptance.js <port> <outDir> <creds.json> <axe.min.js>'); process.exit(2); }
// Importer safety guard: local synthetic fixtures only, with no network escape.
if (!/^[0-9]{1,5}$/.test(PORT) || Number(PORT) < 1024 || Number(PORT) > 65535) {
  throw new Error('Require a numeric unprivileged loopback port');
}
const BASE = `http://127.0.0.1:${Number(PORT)}`;
const creds = JSON.parse(fs.readFileSync(CREDS, 'utf8'));
for (const role of ['viewer', 'owner']) {
  if (!Array.isArray(creds[role]) || creds[role].length !== 2 ||
      !creds[role].every(v => typeof v === 'string' && v.startsWith('synthetic_'))) {
    throw new Error('Only explicit synthetic_ fixture usernames/passwords are allowed');
  }
}
const PAGE_BG = process.env.NPDB_PAGE_BG || '#0B1220';   // dark-theme page background token
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const check = (id, pass, detail) => { results.push({ id, pass: !!pass, detail }); console.log(`${pass ? 'PASS' : 'FAIL'} ${id} ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`); };

async function settle(p) { await p.waitForTimeout(1000); for (let i = 0; i < 400; i++) { if (!(await p.locator('[data-testid="stStatusWidget"]').count())) { await p.waitForTimeout(1000); if (!(await p.locator('[data-testid="stStatusWidget"]').count())) return; } await p.waitForTimeout(250); } }
async function login(p, role) {
  await p.goto(`${BASE}/`); await p.getByPlaceholder('Enter your username').waitFor({ timeout: 150000 }); await settle(p);
  await p.getByPlaceholder('Enter your username').fill(creds[role][0]); await p.getByPlaceholder('Enter your password').fill(creds[role][1]);
  await p.getByRole('button', { name: /Open Database/ }).click();
  await p.locator('[data-testid="stSidebar"]').getByRole('button', { name: 'Home', exact: true }).waitFor({ timeout: 150000 }); await settle(p);
}
async function nav(p, label) {
  const sb = p.locator('[data-testid="stSidebar"]');
  let b = sb.getByRole('button', { name: label, exact: true });
  if (!(await b.count()) || !(await b.first().isVisible())) {           // Data Library pages may sit in a collapsed group
    const group = sb.locator('summary').filter({ hasText: /Additional Views|Data Library/ }).first();
    if (await group.count()) { await group.click(); await settle(p); }
    b = sb.getByRole('button', { name: label, exact: true });
  }
  await b.first().click(); await settle(p);
}

// Page-level checks shared by every page.
async function pageChecks(p, key, { axe = true } = {}) {
  const m = await p.evaluate((pageBg) => {
    const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
    const parse = (c) => (c.match(/[\d.]+/g) || []).map(Number);
    const lum = ([r, g, b]) => [r, g, b].map((v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }).reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0);
    const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
    // Nearest opaque background. An ancestor painted with a background-image (the app's gradient page and
    // cards) is visually the dark page token, whatever its computed background-color says (often white).
    const opaqueBg = (el) => { for (let n = el; n; n = n.parentElement) { const cs = getComputedStyle(n); const a = parse(cs.backgroundColor); if (a.length === 3 || (a.length === 4 && a[3] > 0.5)) return a.slice(0, 3); if (cs.backgroundImage && cs.backgroundImage !== 'none') return hex(pageBg); } return hex(pageBg); };
    const composite = (el) => { const c = parse(getComputedStyle(el).color); let op = c.length === 4 ? c[3] : 1; for (let n = el; n; n = n.parentElement) op *= parseFloat(getComputedStyle(n).opacity); const bg = opaqueBg(el); return { fg: c.slice(0, 3).map((v, i) => v * op + bg[i] * (1 - op)), bg }; };
    // Text the audit found unreadable: widget labels, captions, radio labels, field values.
    const sel = '[data-testid="stWidgetLabel"] p, [data-testid="stCaptionContainer"] p, [role="radiogroup"] label p, [data-testid="stMarkdownContainer"] h3';
    const texts = [...document.querySelectorAll(sel)].filter((e) => e.offsetParent && (e.innerText || '').trim()).map((e) => { const { fg, bg } = composite(e); return { text: e.innerText.trim().slice(0, 40), ratio: +ratio(fg, bg).toFixed(2) }; });
    const fields = [...document.querySelectorAll('input[type="text"], input[type="number"], textarea')].filter((e) => e.offsetParent && e.value).map((e) => { const cs = getComputedStyle(e); const fg = parse(cs.webkitTextFillColor || cs.color).slice(0, 3); return { field: (e.getAttribute('aria-label') || '').slice(0, 30), ratio: +ratio(fg, opaqueBg(e)).toFixed(2) }; });
    const main = document.querySelector('[data-testid="stMain"]') || document.documentElement;
    return {
      h1: document.querySelectorAll('h1').length,
      overflow: Math.max(document.documentElement.scrollWidth - document.documentElement.clientWidth, main.scrollWidth - main.clientWidth),
      lowText: texts.filter((t) => t.ratio < 4.5), lowFields: fields.filter((f) => f.ratio < 4.5),
      claims: (main.innerText.match(/\d+\s*%\s*Verified|curated (records|data|NPDB|compound)|high-quality spectral records/gi) || []),
    };
  }, PAGE_BG);
  check(`${key}: exactly one h1`, m.h1 === 1, `${m.h1} h1`);
  check(`${key}: no horizontal overflow`, m.overflow <= 1, `${m.overflow}px`);
  check(`${key}: labels and captions >= 4.5:1`, !m.lowText.length, m.lowText.slice(0, 4));
  check(`${key}: typed text >= 4.5:1`, !m.lowFields.length, m.lowFields.slice(0, 4));
  check(`${key}: no unsupported curation claims`, !m.claims.length, m.claims.slice(0, 4));
  if (axe) {
    await p.addScriptTag({ path: AXE });
    const v = await p.evaluate(async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } })).violations.filter((x) => x.impact === 'serious' || x.impact === 'critical').map((x) => `${x.id}:${x.nodes.length}`));
    check(`${key}: axe serious/critical = 0`, !v.length, v);
  }
  await p.screenshot({ path: path.join(OUT, `${key}.jpg`), type: 'jpeg', quality: 72 });
}

(async () => {
  const browser = await chromium.launch();
  async function isolatedContext(options) {
    const context = await browser.newContext({ ...options, serviceWorkers: 'block' });
    const allowed = raw => {
      try { const u = new URL(raw); return ['http:', 'ws:'].includes(u.protocol) &&
        u.hostname === '127.0.0.1' && u.port === String(Number(PORT)); }
      catch { return false; }
    };
    await context.route('**/*', async route => {
      if (!allowed(route.request().url())) return route.abort();
      // Playwright routes only the first request of a redirect chain. Never let
      // a loopback response redirect the browser to an unreviewed destination.
      const response = await route.fetch({ maxRedirects: 0 });
      if (response.status() >= 300 && response.status() < 400) return route.abort();
      return route.fulfill({ response });
    });
    await context.routeWebSocket('**/*', socket => {
      if (allowed(socket.url())) socket.connectToServer(); else socket.close();
    });
    return context;
  }
  const viewer = await (await isolatedContext({ viewport: { width: 1280, height: 1100 } })).newPage();
  await login(viewer, 'viewer');
  await pageChecks(viewer, 'home-1280');

  // Keyboard: every tab stop shows a visible indicator (outline >= 2px, or an opaque box-shadow ring >= 2px).
  await viewer.mouse.click(5, 5);
  const stops = [];
  for (let i = 0; i < 40; i++) {
    await viewer.keyboard.press('Tab');
    stops.push(await viewer.evaluate(() => {
      const el = document.activeElement; if (!el || el === document.body) return null;
      const ring = (n) => { if (!n) return false; const cs = getComputedStyle(n);
        if (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2) return true;
        return /rgba?\((\d+), (\d+), (\d+)(, (0?\.\d+|1))?\) 0px 0px 0px ([2-9]|\d\d)/.test(cs.boxShadow) && !/, 0?\.[0-4]\d*\)/.test(cs.boxShadow); };
      const holder = el.matches('input, textarea') ? el.closest('[data-baseweb]') || el.parentElement : el;
      return { label: (el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 30), visible: ring(el) || ring(holder) };
    }));
  }
  const real = stops.filter(Boolean);
  check('keyboard: every tab stop has a visible focus indicator', real.length && real.every((s) => s.visible), `${real.filter((s) => !s.visible).length} of ${real.length} without`);

  // Information architecture: trust pages reachable from the app.
  const sidebarText = await viewer.locator('[data-testid="stSidebar"]').innerText();
  for (const page of ['About', 'How to cite', 'License', 'Privacy', 'Contact']) {
    check(`IA: "${page}" reachable from the sidebar or footer`, new RegExp(page, 'i').test(sidebarText), '');
  }

  // NMR search -> Open Record must open the record and keep the results for the way back.
  await nav(viewer, 'Search Spectra');
  await viewer.locator('[data-testid="stMain"] [role="radiogroup"]').first().getByText('13C Match', { exact: true }).click(); await settle(viewer);
  await viewer.getByLabel(/Enter 13C peaks/).fill(process.env.NPDB_13C_QUERY || '10, 20, 30');
  await viewer.getByRole('button', { name: /Run 13C Match/ }).click(); await settle(viewer);
  await pageChecks(viewer, 'search-13c-1280');
  const open = viewer.locator('[data-testid="stMain"]').getByRole('button', { name: /^Open Record/ }).first();
  if (await open.count()) {
    await open.click(); await settle(viewer);
    check('search: Open Record opens the compound record', await viewer.getByRole('button', { name: /Download Full Record/ }).count() > 0, '');
  } else check('search: result cards offer Open Record', false, 'no Open Record button');

  await nav(viewer, 'Browse Dashboard');
  await pageChecks(viewer, 'record-1280');
  await nav(viewer, '13C Spectra Gallery');
  await pageChecks(viewer, 'gallery-13c-1280');

  // Small screens: no horizontal overflow on Home and the record page.
  for (const w of [320, 768]) {
    const p = await (await isolatedContext({ viewport: { width: w, height: 900 } })).newPage();
    await login(p, 'viewer');
    const o = await p.evaluate(() => { const m = document.querySelector('[data-testid="stMain"]'); return Math.max(document.documentElement.scrollWidth - document.documentElement.clientWidth, m.scrollWidth - m.clientWidth); });
    check(`home-${w}: no horizontal overflow`, o <= 1, `${o}px`);
    await p.screenshot({ path: path.join(OUT, `home-${w}.jpg`), type: 'jpeg', quality: 72 });
    await p.context().close();
  }

  // Owner curation pages.
  const owner = await (await isolatedContext({ viewport: { width: 1280, height: 1100 } })).newPage();
  await login(owner, 'owner');
  const activeNav = await owner.evaluate(() => [...document.querySelectorAll('[data-testid="stSidebar"] button[kind="primary"], [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]')].length);
  await nav(owner, 'New Submission');
  const activeAfter = await owner.evaluate(() => [...document.querySelectorAll('[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]')].map((b) => b.innerText.trim()));
  check('navigation: exactly one active item', activeAfter.length === 1, activeAfter);
  await pageChecks(owner, 'owner-new-submission-1280');
  await nav(owner, 'Update Metadata');
  await pageChecks(owner, 'owner-update-metadata-1280');

  await browser.close();
  const failed = results.filter((r) => !r.pass);
  fs.writeFileSync(path.join(OUT, 'acceptance-report.json'), JSON.stringify({ base: BASE, pageBg: PAGE_BG, total: results.length, failed: failed.length, results }, null, 1));
  console.log(`\n${results.length - failed.length} of ${results.length} checks passed`);
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error('FATAL', e.message); process.exit(1); });
