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
assert.deepStrictEqual(a.quote(u, '2026-10-10', '2026-10-13'), { nights: 3, total: 300, mode: 'nightly' });
assert.strictEqual(a.quote(u, '2026-10-30', '2026-11-02').mode, 'request');
assert.deepStrictEqual(a.quote(u, '2026-10-01', '2026-10-31'), { nights: 30, total: 600, mode: 'monthly' });
assert.strictEqual(a.quote(u, '2027-05-20', '2027-06-20').mode, 'request');
assert.strictEqual(a.plural({ one: '{n} Nacht', other: '{n} Nächte' }, 'de', 1), '1 Nacht');
console.log('app.js tests ok');
