const assert = require('assert');
const a = require('../site/assets/app.js');
assert.strictEqual(a.nightsBetween('2026-10-01', '2026-10-05'), 4);
assert.strictEqual(a.addDays('2026-12-31', 1), '2027-01-01');
const b = a.blockedSet([['2026-10-14', '2026-10-18']]);
assert.ok(b['2026-10-14'] && b['2026-10-17'] && !b['2026-10-18']);
assert.ok(a.rangeFree(b, '2026-10-10', '2026-10-14'));   // Abreise am Anreisetag eines anderen ok
assert.ok(!a.rangeFree(b, '2026-10-13', '2026-10-15'));
assert.ok(a.rangeFree(b, '2026-10-18', '2026-10-20'));   // Anreise am Abreisetag ok
const u = { nightly: { '10': 100, '11': null }, monthly: { price: 600, valid_until: '2027-05-31' } };
assert.deepStrictEqual(a.quote(u, '2026-10-10', '2026-10-13'), { nights: 3, total: 300, mode: 'nightly', base: 300, discount: 0, cleaning: 0, extra: 0 });
assert.strictEqual(a.quote(u, '2026-10-30', '2026-11-02').mode, 'request');
assert.deepStrictEqual(a.quote(u, '2026-10-01', '2026-10-31'), { nights: 30, total: 600, mode: 'monthly', base: 600, discount: 0, cleaning: 0, extra: 0 });
assert.strictEqual(a.quote(u, '2027-05-20', '2027-06-20').mode, 'request');
assert.strictEqual(a.plural({ one: '{n} Nacht', other: '{n} Nächte' }, 'de', 1), '1 Nacht');
console.log('app.js tests ok');
const u2 = { nightly: { '8': 100 }, daily: { '2027-08-14': 150 }, monthly: null };
assert.deepStrictEqual(a.quote(u2, '2027-08-13', '2027-08-16'), { nights: 3, total: 350, mode: 'nightly', base: 350, discount: 0, cleaning: 0, extra: 0 });
console.log('daily price test ok');

const rules = { cleaning_fee: 30, extra_guest_fee: 12, extra_guest_from: 3, weekly_from_nights: 7, weekly_discount_winter: 30, weekly_discount_season: 10, winter_months: [11,12,1,2,3,4], winter_min_nights: 7 };
const u3 = { min_stay: 2, rules, nightly: { '1': 59, '7': 118 }, monthly: null };
// Winter, 7 Nächte: 413 - 30 % = 124 Rabatt, +30 Reinigung
let q = a.quote(u3, '2027-01-10', '2027-01-17', 2);
assert.deepStrictEqual([q.base, q.discount, q.cleaning, q.extra, q.total], [413, 124, 30, 0, 319]);
// Saison, 7 Nächte, 4 Gäste: 826 - 10 % = 83; Zusatzgäste (4-3+1)*12*7 = 168
q = a.quote(u3, '2027-07-05', '2027-07-12', 4);
assert.deepStrictEqual([q.base, q.discount, q.extra, q.total], [826, 83, 168, 826 - 83 + 30 + 168]);
// unter 7 Nächten kein Rabatt, 2 Gäste keine Zusatzgebühr
q = a.quote(u3, '2027-07-05', '2027-07-08', 2);
assert.deepStrictEqual([q.discount, q.extra, q.total], [0, 0, 354 + 30]);
assert.strictEqual(a.minStay(u3, '2027-01-10'), 7);
assert.strictEqual(a.minStay(u3, '2027-07-10'), 2);
console.log('fees tests ok');
