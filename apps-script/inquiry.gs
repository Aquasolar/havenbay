/**
 * Haven Bay – Buchungsanfragen empfangen.
 * Einrichtung: siehe README (Abschnitt "Anfrageformular").
 * 1. Neues Google-Sheet anlegen, Erweiterungen > Apps Script, diesen Code einfügen.
 * 2. OWNER_EMAIL eintragen.
 * 3. Bereitstellen > Neue Bereitstellung > Web-App (Ausführen als: Ich, Zugriff: Jeder).
 * 4. Die Web-App-URL in config.json unter "form_endpoint" eintragen.
 */
var OWNER_EMAIL = '';          // z. B. info@havenbay.eu
var SHEET_NAME = 'Anfragen';
var GUEST_REPLY = true;        // Eingangsbestätigung an den Gast senden
var BANK = {
  holder: 'MEDITERRANEAN RESIDENCE d.o.o., Ulica prvog svibnja 20, Podaca',
  iban: 'HR96 2407 0001 1007 5093 0',
  bic: 'OTPVHR2X',
  bank: 'OTP banka d.d.'
};
var DEPOSIT_PCT = 30;          // Anzahlung in Prozent
var BALANCE_DAYS = 14;         // Restzahlung so viele Tage vor Anreise

// Eingangsbestätigung an den Gast (ohne Bankdaten – die kommen erst mit Ihrer persönlichen Bestätigung)
var REPLY = {
  de: {s: 'Ihre Anfrage bei Haven Bay', b: 'Guten Tag {name},\n\nvielen Dank für Ihre Anfrage für {unit} vom {in} bis {out}. Wir prüfen die Verfügbarkeit und melden uns in der Regel innerhalb von 24 Stunden mit einer Bestätigung.\n\nZahlung: {pct} % Anzahlung nach unserer Bestätigung, der Rest {days} Tage vor Anreise (bei kurzfristigen Buchungen der volle Betrag sofort). Per Überweisung (SEPA) oder mit Karte über einen sicheren Zahlungslink. Bankverbindung und Link erhalten Sie mit unserer Bestätigung.\n\nDies ist noch keine verbindliche Buchung.\n\nHerzliche Grüße\nHaven Bay Apartments, Rogotin'},
  en: {s: 'Your request at Haven Bay', b: 'Hello {name},\n\nthank you for your request for {unit} from {in} to {out}. We will check availability and usually reply within 24 hours with a confirmation.\n\nPayment: {pct}% deposit after our confirmation, the balance {days} days before arrival (for short-notice bookings the full amount at once). By bank transfer (SEPA) or by card via a secure payment link. You receive the bank details and the link with our confirmation.\n\nThis is not yet a binding booking.\n\nKind regards\nHaven Bay Apartments, Rogotin'},
  hr: {s: 'Vaš upit – Haven Bay', b: 'Poštovani/a {name},\n\nhvala na upitu za {unit} od {in} do {out}. Provjerit ćemo dostupnost i u pravilu se javiti u roku od 24 sata s potvrdom.\n\nPlaćanje: predujam od {pct} % nakon naše potvrde, ostatak {days} dana prije dolaska (kod kratkoročnih rezervacija cijeli iznos odmah). Bankovnom doznakom (SEPA) ili karticom putem sigurne poveznice. Bankovne podatke i poveznicu dobivate uz našu potvrdu.\n\nOvo još nije obvezujuća rezervacija.\n\nSrdačan pozdrav\nHaven Bay Apartments, Rogotin'}
};

function doPost(e) {
  var p = (e && e.parameter) || {};
  if (p.website) return out_({ok: true});          // Honeypot: Bots still ignorieren
  if (!p.email || !p.name || !p.check_in || !p.check_out) return out_({ok: false, error: 'missing'});
  var clean = function (v) { return String(v || '').replace(/^[=+\-@]/, "'$&").slice(0, 2000); };
  var row = [new Date(), clean(p.unit_name || p.unit), clean(p.check_in), clean(p.check_out), clean(p.guests),
             clean(p.name), clean(p.email), clean(p.phone), clean(p.message), clean(p.lang), clean(p.estimate)];
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
  if (sh.getLastRow() === 0) {
    sh.appendRow(['Eingang', 'Objekt', 'Anreise', 'Abreise', 'Gäste', 'Name', 'E-Mail', 'Telefon', 'Nachricht', 'Sprache', 'Schätzpreis']);
  }
  sh.appendRow(row);
  var unit = clean(p.unit_name || p.unit), inD = clean(p.check_in), outD = clean(p.check_out);
  if (OWNER_EMAIL) {
    MailApp.sendEmail({
      to: OWNER_EMAIL, replyTo: p.email,
      subject: 'Haven Bay Anfrage: ' + unit + ' ' + inD + '–' + outD,
      body: row.slice(1).join('\n') + '\n\n----- Vorlage für Ihre Bestätigung an den Gast -----\n\n' + confirmText_(p, unit, inD, outD)
    });
  }
  if (GUEST_REPLY) {
    var t = REPLY[p.lang] || REPLY.en;
    var f = function (x) {
      return x.replace('{name}', clean(p.name)).replace('{unit}', unit).replace('{in}', inD).replace('{out}', outD)
              .replace('{pct}', DEPOSIT_PCT).replace('{days}', BALANCE_DAYS);
    };
    var m = {to: p.email, subject: t.s, body: f(t.b), name: 'Haven Bay Apartments'};
    if (OWNER_EMAIL) m.replyTo = OWNER_EMAIL;
    MailApp.sendEmail(m);
  }
  return out_({ok: true});
}

// Bestätigungstext mit Bankdaten und Beträgen – Sie prüfen ihn und senden ihn selbst an den Gast.
function confirmText_(p, unit, inD, outD) {
  var total = parseFloat(p.estimate);
  var amounts = isNaN(total) ? 'Gesamtpreis: [BETRAG] €\nAnzahlung ' + DEPOSIT_PCT + ' %: [BETRAG] €\n'
    : 'Gesamtpreis: ' + total.toFixed(2) + ' €\nAnzahlung ' + DEPOSIT_PCT + ' %: ' + (total * DEPOSIT_PCT / 100).toFixed(2) +
      ' € – bitte innerhalb von 3 Tagen\nRestbetrag: ' + (total * (100 - DEPOSIT_PCT) / 100).toFixed(2) + ' € – bis ' + BALANCE_DAYS + ' Tage vor Anreise\n';
  return 'Guten Tag ' + String(p.name || '') + ',\n\nwir bestätigen gerne Ihren Aufenthalt in ' + unit + ' vom ' + inD + ' bis ' + outD + '.\n\n' +
    amounts + '\nÜberweisung (SEPA):\nEmpfänger: ' + BANK.holder + '\nIBAN: ' + BANK.iban + '\nBIC: ' + BANK.bic + ' (' + BANK.bank + ')\n' +
    'Verwendungszweck: Haven Bay ' + inD + ' ' + String(p.name || '') + '\n\nOder mit Karte: [ZAHLUNGSLINK]\n\nHerzliche Grüße\nHaven Bay Apartments';
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
