// Plausibilitätstests über alle Anreisetage bis 31.05.2027 mit den echten Preisen.
// Gewollte Ausnahmen (Entscheidung 17.10.2026): Preissprung bei 7 Nächten (Wochenrabatt) und 28 Nächten (Monatspreis).
const assert = require('assert');
const a = require('../site/assets/app.js');
const P = require('../content/prices.json');
const U = require('../content/units.json');
const units = U.units || U;
const ALLOWED_DROP_AT = [P.rules.weekly_from_nights, 28];
let n = 0, bad = [];
for (const name of ['studio', 'apartment']) {
  const unit = { rules: P.rules, nightly: P.units[name].nightly, monthly: P.units[name].monthly, weekly: P.units[name].weekly };
  const max = units[name].max_guests;
  for (let d = '2026-10-17'; d <= '2027-05-30'; d = a.addDays(d, 1)) {
    let prevTotal = null;
    for (let nights = 1; nights <= 40; nights++) {
      const out = a.addDays(d, nights);
      if (out > '2027-06-01') break;
      let prevG = null;
      for (let g = 1; g <= max; g++) {
        const q = a.quote(unit, d, out, g); n++;
        if (typeof q.total !== 'number' || !isFinite(q.total) || q.total < 0) bad.push(`${name} ${d} ${nights}N ${g}G: Betrag ${q.total}`);
        if (prevG !== null && q.total < prevG) bad.push(`${name} ${d} ${nights}N: ${g} Gäste billiger als ${g - 1}`);
        prevG = q.total;
      }
      const t2 = a.quote(unit, d, out, 2).total;
      if (prevTotal !== null && t2 < prevTotal && ALLOWED_DROP_AT.indexOf(nights) < 0) bad.push(`${name} ${d}: ${nights} Nächte (${t2}) billiger als ${nights - 1} (${prevTotal})`);
      prevTotal = t2;
    }
  }
}
assert.deepStrictEqual(bad.slice(0, 10), [], bad.length + ' Auffälligkeiten');
console.log(`plausibility ok (${n} Preisberechnungen)`);
