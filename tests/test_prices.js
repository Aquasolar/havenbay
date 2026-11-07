// Prüft content/prices.json auf grobe Fehler (Tippfehler, falsche Struktur). Gewollte Preislogik prüft test_plausibility.js.
const assert = require('assert');
const P = require('../content/prices.json');
const bad = [];
const isNum = v => typeof v === 'number' && isFinite(v);
const isDate = s => typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s) && !isNaN(Date.parse(s));
if (P.currency !== 'EUR') bad.push('currency muss EUR sein');
if (P.confirmed !== true) bad.push('confirmed muss true sein');
const R = P.rules || {};
if (!Number.isInteger(R.winter_min_nights) || R.winter_min_nights < 1 || R.winter_min_nights > 7) bad.push('rules.winter_min_nights muss 1 bis 7 sein');
if (!Array.isArray(R.min_nights_months) || R.min_nights_months.some(m => !Number.isInteger(m) || m < 1 || m > 12)) bad.push('rules.min_nights_months: nur Monate 1 bis 12');
if (R.weekly_from_nights !== 7) bad.push('weekly_from_nights muss 7 sein');
for (const name of ['studio', 'apartment']) {
  const u = (P.units || {})[name];
  if (!u) { bad.push(name + ' fehlt'); continue; }
  for (let m = 1; m <= 12; m++) {
    const v = u.nightly[String(m)];
    if (v !== null && (!isNum(v) || v < 20 || v > 400)) bad.push(`${name} nightly ${m}: ${v} außerhalb 20 bis 400`);
  }
  for (const [m, w] of Object.entries(u.weekly || {})) {
    const n = u.nightly[m];
    if (!isNum(w) || w <= 0) bad.push(`${name} weekly ${m}: ungültig`);
    else if (isNum(n) && w > 7 * n * 1.05) bad.push(`${name} weekly ${m}: ${w} teurer als 7 Nächte (${7 * n})`);
  }
  const mo = u.monthly || {};
  if (!isNum(mo.price) || mo.price < 100) bad.push(`${name} monthly.price ungültig`);
  if (!isDate(mo.valid_until)) bad.push(`${name} monthly.valid_until ist kein Datum`);
  if (isNum(mo.price) && isNum(u.weekly && u.weekly['11']) && mo.price > u.weekly['11'] * 4.5) bad.push(`${name}: Monatspreis höher als 4,5 Wochen`);
}
assert.deepStrictEqual(bad, [], bad.join('; '));
console.log('prices.json ok');
