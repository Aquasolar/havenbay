// Ebene 2: Browser-Test der fertig gebauten Seite (Playwright, Chromium).
// Aufruf: node tests/e2e.js <dist-Ordner>   (gebaut mit tests/fixtures/availability.json)
// Prüft: Anzeige = gesendete Anfrage = Sollbetrag, Mindestaufenthalt, belegte Tage, Spam-Feld, Handy-Breite, Sprachen.
const http = require('http'), fs = require('fs'), path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { ({ chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')); }

const DIST = path.resolve(process.argv[2] || 'build/e2e-dist');
const NOW = new Date('2026-10-17T10:00:00+02:00');   // feste "Heute"-Zeit: Tests bleiben über die Zeit gültig
const ENDPOINT = 'https://form.test.invalid/inquiry';
const LANGS = ['en', 'de', 'hr', 'cs', 'hu', 'pl', 'it', 'sl'];

// Sollbeträge: siehe Testplan (Abschnitt Preis). Bei Preisänderungen hier anpassen.
const PRICE_CASES = [
  ['P1', 'studio', '2027-01-10', '2027-01-13', 2, 207],
  ['P2', 'studio', '2027-01-10', '2027-01-13', 3, 243],
  ['P3', 'apartment', '2027-02-01', '2027-02-08', 2, 334],
  ['P4', 'apartment', '2027-02-01', '2027-02-08', 4, 502],
  ['P5', 'studio', '2026-10-30', '2026-11-02', 2, 267],
  ['P6', 'apartment', '2027-01-01', '2027-01-31', 2, 720],
  ['P7', 'apartment', '2027-01-01', '2027-01-31', 4, 750],
  ['P8', 'studio', '2027-02-01', '2027-03-01', 3, 637],
];

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.jpg': 'image/jpeg', '.png': 'image/png', '.svg': 'image/svg+xml', '.webp': 'image/webp', '.ico': 'image/x-icon', '.ics': 'text/calendar' };
function serve() {
  const srv = http.createServer((req, res) => {
    let p = decodeURIComponent(req.url.split('?')[0]);
    let f = path.join(DIST, p);
    if (!f.startsWith(DIST)) { res.writeHead(403); return res.end(); }
    if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
    if (!fs.existsSync(f)) { res.writeHead(404); return res.end('not found'); }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream' });
    fs.createReadStream(f).pipe(res);
  });
  return new Promise(r => srv.listen(0, '127.0.0.1', () => r(srv)));
}

let failures = 0, passed = 0;
function check(id, ok, msg) {
  if (ok) { passed++; console.log(`  ok   ${id}`); }
  else { failures++; console.log(`  FEHLER ${id}: ${msg}`); }
}
const euros = t => { const d = String(t).replace(/[^\d]/g, ''); return d ? Number(d) : null; };

async function openBooking(browser, base, lang, viewport) {
  const ctx = await browser.newContext({ viewport: viewport || { width: 1280, height: 900 }, locale: lang, timezoneId: 'Europe/Vienna' });
  const page = await ctx.newPage();
  await page.clock.setFixedTime(NOW);
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  // Formular an einen Test-Endpunkt umleiten und gesendete Daten mitschneiden
  const sent = [];
  await page.route(`**/${lang}/`, async route => {
    const r = await route.fetch(); let body = await r.text();
    body = body.replace('"endpoint":""', `"endpoint":"${ENDPOINT}"`);
    await route.fulfill({ response: r, body });
  });
  await page.route(ENDPOINT, async route => { sent.push(Object.fromEntries(new URLSearchParams(route.request().postData() || ''))); await route.fulfill({ status: 200, body: 'ok' }); });
  await page.goto(`${base}/${lang}/`);
  await page.waitForSelector('#cal .cal-day');
  await page.waitForFunction(() => document.querySelector('#cal-status') && document.querySelector('#cal-status').textContent.length > 0);
  return { ctx, page, sent, errors };
}
async function clickDate(page, d) {
  for (let i = 0; i < 24; i++) {
    const b = page.locator(`#cal button.cal-day[data-date="${d}"]:visible`);
    if (await b.count()) { await b.click(); return; }
    const navs = page.locator('#cal .cal-nav');
    const first = await page.locator('#cal button.cal-day:visible').first().getAttribute('data-date');
    await navs.nth(d < first ? 0 : 1).click();
  }
  throw new Error('Datum nicht im Kalender: ' + d);
}
async function pick(page, unit, a, b, guests) {
  await page.selectOption('#unit', unit);
  await page.selectOption('#guests', String(guests));
  await clickDate(page, a); await clickDate(page, b);
}

(async () => {
  const srv = await serve();
  const base = `http://127.0.0.1:${srv.address().port}`;
  const opts = process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {};
  const browser = await chromium.launch(opts);
  try {
    console.log('Preise: Anzeige = Anfrage = Soll');
    for (const [id, unit, a, b, g, soll] of PRICE_CASES) {
      const { ctx, page, sent } = await openBooking(browser, base, 'de');
      await pick(page, unit, a, b, g);
      const shown = euros(await page.textContent('#sum-total'));
      await page.fill('#f-name', 'Test Gast'); await page.fill('#request-form [name=email]', 'test@example.com');
      const consent = page.locator('#request-form input[type=checkbox]');
      if (await consent.count()) await consent.first().check();
      await page.click('#btn-send');
      await page.waitForFunction(() => document.querySelector('#form-msg').textContent.length > 0);
      const est = sent.length ? Number(sent[0].estimate) : null;
      check(id, shown === soll && est === soll && sent[0].guests === String(g) && sent[0].check_in === a && sent[0].check_out === b,
        `Soll ${soll}, Anzeige ${shown}, Anfrage ${est}, Daten ${sent[0] && [sent[0].check_in, sent[0].check_out, sent[0].guests]}`);
      await ctx.close();
    }

    console.log('Mindestaufenthalt und belegte Tage');
    let s = await openBooking(browser, base, 'de');
    await pick(s.page, 'studio', '2027-01-10', '2027-01-12', 2);
    check('M1', await s.page.locator('#sum-hint.is-error').count() === 1 && await s.page.isDisabled('#btn-send'), 'zu kurzer Aufenthalt im Winter wurde angenommen');
    await s.page.click('#btn-clear');
    await pick(s.page, 'studio', '2027-05-30', '2027-06-02', 2);
    check('M2', await s.page.isDisabled('#btn-send'), 'Aufenthalt über die Sperre ab 01.06.2027 wurde angenommen');
    await s.page.click('#btn-clear');
    await pick(s.page, 'studio', '2026-10-20', '2026-10-22', 2);
    check('M3', !(await s.page.isDisabled('#btn-send')), '2 Nächte im Oktober wurden abgelehnt');
    await s.page.click('#btn-clear');
    await pick(s.page, 'apartment', '2027-02-25', '2027-03-01', 2);
    check('M4', !(await s.page.isDisabled('#btn-send')), 'Abreise am Anreisetag eines anderen Gastes wurde abgelehnt');
    await s.page.click('#btn-clear');
    await s.page.selectOption('#unit', 'apartment');
    await clickDate(s.page, '2027-03-05');
    const booked = await s.page.locator('#cal button.cal-day[data-date="2027-03-05"]').getAttribute('class');
    await pick(s.page, 'apartment', '2027-02-25', '2027-03-03', 2);
    check('K8', /is-booked/.test(booked) && await s.page.isDisabled('#btn-send'), 'belegter Tag frei oder Zeitraum über belegte Tage wählbar');
    await s.ctx.close();

    console.log('Spam-Feld');
    s = await openBooking(browser, base, 'de');
    await pick(s.page, 'studio', '2027-01-10', '2027-01-13', 2);
    await s.page.fill('#f-name', 'Bot'); await s.page.fill('#request-form [name=email]', 'bot@example.com');
    await s.page.evaluate(() => { const f = document.querySelector('#request-form [name=website]'); if (f) f.value = 'spam'; });
    await s.page.click('#btn-send'); await s.page.waitForTimeout(300);
    check('A3', s.sent.length === 0, 'Anfrage mit ausgefülltem Spam-Feld wurde gesendet');
    await s.ctx.close();

    console.log('Sprachen und Handy (390 px)');
    for (const lang of LANGS) {
      const m = await openBooking(browser, base, lang, { width: 390, height: 844 });
      const r = await m.page.evaluate(() => ({ sw: document.documentElement.scrollWidth, text: document.body.innerText }));
      check(`I1-${lang}`, !/\{[a-z_]+\}/.test(r.text) && !/undefined|NaN/.test(r.text), 'offener Platzhalter, undefined oder NaN im Text');
      check(`I7-${lang}`, r.sw <= 392, `seitliches Scrollen: Breite ${r.sw}px`);
      await pick(m.page, 'apartment', '2027-01-01', '2027-01-31', 4);
      check(`P7-${lang}`, euros(await m.page.textContent('#sum-total')) === 750, 'Preis in dieser Sprache abweichend');
      check(`JS-${lang}`, m.errors.length === 0, m.errors.join(' | '));
      await m.ctx.close();
    }
  } finally {
    await browser.close(); srv.close();
  }
  console.log(`\n${passed} bestanden, ${failures} fehlgeschlagen`);
  process.exit(failures ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
