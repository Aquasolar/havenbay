/* Haven Bay – Buchungskalender, Preisberechnung, Menü, Karussell, Filter.
   Daten kommen aus <script id="hb-data" type="application/json"> und ../availability.json */
(function (root) {
  'use strict';

  /* ---------- Reine Funktionen (auch im Test genutzt) ---------- */
  var DAY = 86400000;
  function pad(n) { return String(n).padStart(2, '0'); }
  function toUTC(s) { var p = s.split('-').map(Number); return Date.UTC(p[0], p[1] - 1, p[2]); }
  function fromUTC(t) { var d = new Date(t); return d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate()); }
  function addDays(s, n) { return fromUTC(toUTC(s) + n * DAY); }
  function nightsBetween(a, b) { return Math.round((toUTC(b) - toUTC(a)) / DAY); }

  // Belegte Nächte: Bereiche [start, ende) -> Set aus 'JJJJ-MM-TT'
  function blockedSet(ranges) {
    var set = {};
    (ranges || []).forEach(function (r) {
      for (var t = toUTC(r[0]); t < toUTC(r[1]); t += DAY) set[fromUTC(t)] = true;
    });
    return set;
  }
  // Alle Nächte von in bis out (ohne out) frei?
  function rangeFree(blocked, inD, outD) {
    for (var t = toUTC(inD); t < toUTC(outD); t += DAY) if (blocked[fromUTC(t)]) return false;
    return true;
  }
  // Winter laut Regeln? (nach Anreisemonat)
  function isWinter(rules, inD) {
    return !!(rules && rules.winter_months && rules.winter_months.indexOf(Number(inD.slice(5, 7))) >= 0);
  }
  // Mindestaufenthalt: im Winter ggf. länger (eigene Monatsliste min_nights_months, sonst winter_months)
  function minStay(unit, inD) {
    var r = unit.rules;
    var months = r && (r.min_nights_months || r.winter_months);
    var hit = !!(months && months.indexOf(Number(inD.slice(5, 7))) >= 0);
    if (r && r.winter_min_nights && hit) return Math.max(unit.min_stay || 1, r.winter_min_nights);
    return unit.min_stay || 1;
  }
  // Preis: pro Nacht nach Monat oder Tagespreis; ab 28 Nächten Monatspreis (pro 30 Nächte), wenn gültig;
  // Wochenrabatt ab 7 Nächten; dazu Reinigung und Zusatzgäste (ab dem 3. Gast pro Nacht).
  function quote(unit, inD, outD, guests) {
    var nights = nightsBetween(inD, outD);
    var r = unit.rules || {};
    var cleaning = r.cleaning_fee || 0;
    var extra = 0;
    if (r.extra_guest_fee && guests >= (r.extra_guest_from || 3)) extra = (guests - (r.extra_guest_from || 3) + 1) * r.extra_guest_fee * nights;
    var m = unit.monthly, base, discount = 0, mode;
    if (nights >= 28 && m && typeof m.price === 'number' && outD <= addDays(m.valid_until, 1)) {
      base = Math.round(m.price * nights / 30); mode = 'monthly';
    } else {
      base = 0; mode = 'nightly';
      for (var t = toUTC(inD); t < toUTC(outD); t += DAY) {
        var month = String(new Date(t).getUTCMonth() + 1);
        var p = unit.nightly ? unit.nightly[month] : null;
        if (unit.daily && typeof unit.daily[fromUTC(t)] === 'number') p = unit.daily[fromUTC(t)];
        if (typeof p !== 'number') return { nights: nights, total: null, mode: 'request' };
        base += p;
      }
      if (r.weekly_from_nights && nights >= r.weekly_from_nights) {
        var pct = isWinter(r, inD) ? r.weekly_discount_winter : r.weekly_discount_season;
        discount = Math.round(base * (pct || 0) / 100);
      }
    }
    return { nights: nights, total: base - discount + cleaning + extra, mode: mode, base: base, discount: discount, cleaning: cleaning, extra: extra };
  }
  function plural(forms, lang, n) {
    var cat = 'other';
    try { cat = new Intl.PluralRules(lang).select(n); } catch (e) { /* ignore */ }
    var s = forms[cat] || forms.other;
    return s.replace('{n}', n);
  }

  var api = { toUTC: toUTC, fromUTC: fromUTC, addDays: addDays, nightsBetween: nightsBetween, blockedSet: blockedSet, rangeFree: rangeFree, quote: quote, minStay: minStay, isWinter: isWinter, plural: plural };
  if (typeof module !== 'undefined' && module.exports) { module.exports = api; return; }

  /* ---------- Browser ---------- */
  var doc = root.document;
  var dataEl = doc.getElementById('hb-data');
  var D = dataEl ? JSON.parse(dataEl.textContent) : null;

  function $(sel, ctx) { return (ctx || doc).querySelector(sel); }
  function $all(sel, ctx) { return Array.prototype.slice.call((ctx || doc).querySelectorAll(sel)); }
  function fmt(str, vars) { return str.replace(/\{(\w+)\}/g, function (_, k) { return vars[k] != null ? vars[k] : ''; }); }

  /* Menü */
  var menuBtn = $('.menu-btn'), nav = $('#nav');
  if (menuBtn && nav) {
    menuBtn.addEventListener('click', function () {
      var open = nav.classList.toggle('is-open');
      menuBtn.setAttribute('aria-expanded', String(open));
    });
  }

  /* Sprachumschalter: bei Klick außerhalb schließen */
  doc.addEventListener('click', function (e) {
    $all('.lang[open]').forEach(function (d) { if (!d.contains(e.target)) d.removeAttribute('open'); });
  });

  /* Verfügbarkeit & Buchung */
  var bookingEl = $('#booking');
  if (D && bookingEl) initBooking(bookingEl);

  function initBooking(el) {
    var ui = D.ui, lang = D.lang;
    var unitSel = $('#unit'), guestsSel = $('#guests');
    var calHost = $('#cal'), statusEl = $('#cal-status');
    var inEl = $('#sum-in'), outEl = $('#sum-out'), nightsEl = $('#sum-nights'), totalEl = $('#sum-total'), hintEl = $('#sum-hint');
    var form = $('#request-form'), msgEl = $('#form-msg'), sendBtn = $('#btn-send');
    var clearBtn = $('#btn-clear');

    var state = { unit: unitSel.value, start: null, end: null, blocked: {}, avail: null, view: null };
    var today = (function () { var n = new Date(); return n.getFullYear() + '-' + pad(n.getMonth() + 1) + '-' + pad(n.getDate()); })();
    var lastDay = addDays(today, 540);
    state.view = today.slice(0, 7);

    var dateFmt = new Intl.DateTimeFormat(lang, { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
    var monthFmt = new Intl.DateTimeFormat(lang, { month: 'long', year: 'numeric', timeZone: 'UTC' });
    var dowFmt = new Intl.DateTimeFormat(lang, { weekday: 'short', timeZone: 'UTC' });
    var fullFmt = new Intl.DateTimeFormat(lang, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });

    function unitCfg() { return D.units[state.unit]; }

    function setGuests() {
      var max = unitCfg().max_guests, cur = Number(guestsSel.value) || 1;
      guestsSel.innerHTML = '';
      for (var i = 1; i <= max; i++) {
        var o = doc.createElement('option'); o.value = i; o.textContent = i; guestsSel.appendChild(o);
      }
      guestsSel.value = Math.min(cur, max);
    }

    function loadAvailability() {
      return fetch(D.availability_url, { cache: 'no-cache' }).then(function (r) {
        if (!r.ok) throw new Error('http ' + r.status);
        return r.json();
      }).then(function (j) {
        state.avail = j; statusEl.classList.remove('is-error');
        var t = new Date(j.updated);
        var when = isNaN(t) ? '' : new Intl.DateTimeFormat(lang, { dateStyle: 'medium', timeStyle: 'short' }).format(t);
        statusEl.textContent = when ? fmt(ui.cal_updated, { t: when }) : '';
      }).catch(function () {
        state.avail = { units: {} };
        statusEl.classList.add('is-error');
        statusEl.textContent = ui.avail_error;
      });
    }

    function loadDaily() {
      if (!D.daily_url) return Promise.resolve();
      return fetch(D.daily_url, { cache: 'no-cache' }).then(function (r) {
        if (!r.ok) throw new Error('http ' + r.status);
        return r.json();
      }).then(function (j) {
        Object.keys(D.units).forEach(function (k) { D.units[k].daily = (j.units && j.units[k]) || {}; });
        D.events = j.events || [];
      }).catch(function () { /* ohne Tagespreise: Monatspreise gelten */ });
    }

    function recomputeBlocked() {
      var r = state.avail && state.avail.units ? state.avail.units[state.unit] : [];
      state.blocked = blockedSet(r || []);
    }

    function monthGrid(ym) {
      var y = Number(ym.slice(0, 4)), m = Number(ym.slice(5, 7)) - 1;
      var first = new Date(Date.UTC(y, m, 1));
      var lead = (first.getUTCDay() + 6) % 7; // Montag zuerst
      var dim = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
      var wrap = doc.createElement('div'); wrap.className = 'cal-month';
      var h = doc.createElement('h4'); h.textContent = monthFmt.format(first); wrap.appendChild(h);
      var grid = doc.createElement('div'); grid.className = 'cal-grid'; grid.setAttribute('role', 'grid');
      // Wochentage (2024-01-01 war ein Montag)
      for (var i = 0; i < 7; i++) {
        var d = doc.createElement('div'); d.className = 'cal-dow'; d.textContent = dowFmt.format(new Date(Date.UTC(2024, 0, 1 + i))); grid.appendChild(d);
      }
      for (var b = 0; b < lead; b++) { var bl = doc.createElement('div'); bl.className = 'cal-blank'; grid.appendChild(bl); }
      for (var day = 1; day <= dim; day++) {
        var s = ym + '-' + pad(day);
        var btn = doc.createElement('button');
        btn.type = 'button'; btn.className = 'cal-day'; btn.textContent = day; btn.dataset.date = s;
        var past = s < today || s > lastDay;
        var booked = !!state.blocked[s];
        if (past) btn.disabled = true;
        if (booked) btn.classList.add('is-booked');
        if (s === today) btn.classList.add('is-today');
        if (state.start && s === state.start) btn.classList.add('is-start');
        if (state.end && s === state.end) btn.classList.add('is-end');
        if (state.start && state.end && s > state.start && s < state.end) btn.classList.add('in-range');
        btn.setAttribute('aria-label', fullFmt.format(new Date(toUTC(s))) + (booked ? ', ' + ui.legend_booked : ''));
        btn.setAttribute('aria-pressed', String(s === state.start || s === state.end));
        grid.appendChild(btn);
      }
      wrap.appendChild(grid);
      return wrap;
    }

    function renderCal() {
      calHost.innerHTML = '';
      var tool = doc.createElement('div'); tool.className = 'cal-toolbar';
      var prev = doc.createElement('button'); prev.type = 'button'; prev.className = 'cal-nav'; prev.textContent = '‹'; prev.setAttribute('aria-label', ui.cal_prev);
      var next = doc.createElement('button'); next.type = 'button'; next.className = 'cal-nav'; next.textContent = '›'; next.setAttribute('aria-label', ui.cal_next);
      prev.disabled = state.view <= today.slice(0, 7);
      next.disabled = state.view >= lastDay.slice(0, 7);
      prev.addEventListener('click', function () { shiftView(-1); });
      next.addEventListener('click', function () { shiftView(1); });
      tool.appendChild(prev); tool.appendChild(next);
      var months = doc.createElement('div'); months.className = 'cal-months';
      months.appendChild(monthGrid(state.view));
      months.appendChild(monthGrid(shiftYM(state.view, 1)));
      calHost.appendChild(tool); calHost.appendChild(months);
      // Pfeile links/rechts neben die Monatsüberschriften verteilen
      tool.style.justifyContent = 'space-between';
    }

    function shiftYM(ym, n) {
      var y = Number(ym.slice(0, 4)), m = Number(ym.slice(5, 7)) - 1 + n;
      return new Date(Date.UTC(y, m, 1)).toISOString().slice(0, 7);
    }
    function shiftView(n) { state.view = shiftYM(state.view, n); renderCal(); }

    function setHint(text, isError) { hintEl.textContent = text || ''; hintEl.classList.toggle('is-error', !!isError); }

    function onDay(s) {
      var u = unitCfg();
      setHint('');
      if (!state.start || state.end) {
        if (state.blocked[s]) return; // belegte Nacht kann kein Anreisetag sein
        state.start = s; state.end = null;
      } else if (s <= state.start) {
        if (state.blocked[s]) return;
        state.start = s;
      } else {
        if (!rangeFree(state.blocked, state.start, s)) {
          setHint(ui.range_blocked, true);
          state.start = state.blocked[s] ? null : s; state.end = null;
        } else if (nightsBetween(state.start, s) < minStay(u, state.start)) {
          var ms = minStay(u, state.start);
          setHint(fmt(ui.min_stay, { nights: plural(ui.nights, lang, ms) }), true);
        } else {
          state.end = s;
        }
      }
      renderCal(); renderSummary();
    }

    function renderSummary() {
      var u = unitCfg();
      inEl.textContent = state.start ? dateFmt.format(new Date(toUTC(state.start))) : '–';
      outEl.textContent = state.end ? dateFmt.format(new Date(toUTC(state.end))) : '–';
      var ok = !!(state.start && state.end);
      nightsEl.textContent = ok ? String(nightsBetween(state.start, state.end)) : '–';
      var priceNote = '';
      if (ok) {
        var q = quote(u, state.start, state.end, Number(guestsSel.value) || 1);
        if (q.total == null) { totalEl.textContent = ui.on_request; priceNote = ui.est_none; }
        else { totalEl.textContent = D.currency_symbol + ' ' + q.total; priceNote = ui.est_note; }
        if (!hintEl.classList.contains('is-error')) setHint(priceNote);
      } else {
        totalEl.textContent = '–';
        if (!hintEl.classList.contains('is-error')) setHint(ui.pick_dates);
      }
      sendBtn.disabled = !ok;
      clearBtn.hidden = !(state.start || state.end);
    }

    function clear() { state.start = null; state.end = null; setHint(''); renderCal(); renderSummary(); }

    function changeUnit(u) {
      state.unit = u; unitSel.value = u;
      var strip = $('#strip-unit'); if (strip) strip.value = u;
      state.start = null; state.end = null; setHint('');
      setGuests(); recomputeBlocked(); renderCal(); renderSummary();
    }

    calHost.addEventListener('click', function (e) {
      var b = e.target.closest('.cal-day'); if (!b || b.disabled) return;
      onDay(b.dataset.date);
    });
    unitSel.addEventListener('change', function () { changeUnit(unitSel.value); });
    guestsSel.addEventListener('change', renderSummary);
    clearBtn.addEventListener('click', clear);

    // Leiste im Hero (Startseite)
    var stripUnit = $('#strip-unit'), stripGuests = $('#strip-guests'), stripGo = $('#strip-go');
    if (stripUnit) {
      stripUnit.addEventListener('change', function () { changeUnit(stripUnit.value); });
      stripGuests.addEventListener('change', function () { guestsSel.value = stripGuests.value; renderSummary(); });
      stripGo.addEventListener('click', function (e) {
        e.preventDefault();
        bookingEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        var first = $('.cal-day:not([disabled])', calHost); if (first) setTimeout(function () { first.focus({ preventScroll: true }); }, 400);
      });
    }

    // Anfrage senden
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!state.start || !state.end) { setHint(ui.pick_dates, true); return; }
      if (form.elements.website && form.elements.website.value) return; // Honeypot
      var payload = {
        unit: state.unit, unit_name: ui['' + state.unit + '_name'], check_in: state.start, check_out: state.end,
        nights: nightsBetween(state.start, state.end), guests: guestsSel.value,
        name: form.elements.name.value, email: form.elements.email.value, phone: form.elements.phone.value,
        message: form.elements.message.value, lang: lang, page: root.location.href
      };
      var q = quote(unitCfg(), state.start, state.end, Number(guestsSel.value) || 1);
      payload.estimate = q.total == null ? '' : String(q.total);
      sendBtn.disabled = true; msgEl.className = 'form-msg'; msgEl.textContent = '';

      function ok(text) { msgEl.textContent = text; msgEl.className = 'form-msg'; form.reset(); clear(); sendBtn.disabled = true; }
      function fail() {
        msgEl.className = 'form-msg is-error';
        msgEl.textContent = ui.sent_err + (D.contact_email ? ' ' + D.contact_email : '');
        sendBtn.disabled = false;
      }

      if (D.demo) { ok(D.demo_message); return; }
      if (D.endpoint) {
        var body = new URLSearchParams(payload);
        fetch(D.endpoint, { method: 'POST', mode: 'no-cors', body: body }).then(function () { ok(ui.sent_ok); }).catch(fail);
      } else if (D.contact_email) {
        var subject = encodeURIComponent('Booking request ' + payload.unit_name + ' ' + payload.check_in + ' - ' + payload.check_out);
        var text = encodeURIComponent(Object.keys(payload).map(function (k) { return k + ': ' + payload[k]; }).join('\n'));
        root.location.href = 'mailto:' + D.contact_email + '?subject=' + subject + '&body=' + text;
        sendBtn.disabled = false;
      } else { fail(); }
    });

    // Preistabelle (Unterseiten)
    var priceHost = $('#price-table');
    if (priceHost) renderPrices(priceHost);

    function renderEvents(host) {
      var today = fromUTC(Date.now());
      var list = (D.events || []).filter(function (e) { return e.to >= today; }).slice(0, 12);
      if (!list.length) return;
      var h = doc.createElement('h3'); h.textContent = ui.special_h; host.appendChild(h);
      var fmtDay = new Intl.DateTimeFormat(lang, { day: 'numeric', month: 'short', timeZone: 'UTC' });
      var table = doc.createElement('table'); table.className = 'price-table';
      list.forEach(function (e) {
        var u = unitCfg(); var p = u.daily && u.daily[e.from];
        if (typeof p !== 'number') return;
        var tr = doc.createElement('tr');
        var th = doc.createElement('th'); th.scope = 'row';
        th.textContent = e.label + ' (' + fmtDay.format(new Date(toUTC(e.from))) + (e.to !== e.from ? '–' + fmtDay.format(new Date(toUTC(e.to))) : '') + ')';
        var td = doc.createElement('td'); td.textContent = D.currency_symbol + ' ' + p + ' ' + ui.per_night;
        tr.appendChild(th); tr.appendChild(td); table.appendChild(tr);
      });
      if (table.children.length) host.appendChild(table);
    }

    function renderPrices(host) {
      var u = unitCfg();
      var table = doc.createElement('table'); table.className = 'price-table';
      var monthName = new Intl.DateTimeFormat(lang, { month: 'long', timeZone: 'UTC' });
      for (var m = 1; m <= 12; m++) {
        var tr = doc.createElement('tr');
        var th = doc.createElement('th'); th.scope = 'row'; th.textContent = monthName.format(new Date(Date.UTC(2026, m - 1, 1)));
        th.style.textTransform = 'capitalize';
        var td = doc.createElement('td'); var p = u.nightly[String(m)];
        td.textContent = typeof p === 'number' ? D.currency_symbol + ' ' + p + ' ' + ui.per_night : ui.on_request;
        tr.appendChild(th); tr.appendChild(td); table.appendChild(tr);
      }
      host.appendChild(table);
    }

    setGuests();
    renderCal(); renderSummary();
    Promise.all([loadAvailability(), loadDaily()]).then(function () {
      recomputeBlocked(); renderCal(); renderSummary();
      if (priceHost) renderEvents(priceHost);
    });
  }

  /* Karussell */
  $all('.carousel').forEach(function (c) {
    var track = $('.carousel-track', c), prev = $('[data-dir="-1"]', c), next = $('[data-dir="1"]', c);
    if (!track) return;
    function update() {
      var overflow = track.scrollWidth > track.clientWidth + 4;
      var ctl = $('.carousel-ctl', c); if (ctl) ctl.hidden = !overflow;
    }
    [prev, next].forEach(function (b) {
      if (!b) return;
      b.addEventListener('click', function () { track.scrollBy({ left: Number(b.dataset.dir) * track.clientWidth * 0.8, behavior: 'smooth' }); });
    });
    root.addEventListener('resize', update); update();
  });

  /* Filter der Ausflugsziele */
  var chips = $all('.chip');
  if (chips.length) {
    chips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        var cat = chip.dataset.cat;
        chips.forEach(function (c) { c.setAttribute('aria-pressed', String(c === chip)); });
        $all('.cat-section').forEach(function (s) { s.hidden = !(cat === 'all' || s.dataset.cat === cat); });
      });
    });
  }
})(typeof window !== 'undefined' ? window : globalThis);
