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
  if (OWNER_EMAIL) {
    MailApp.sendEmail({
      to: OWNER_EMAIL, replyTo: p.email,
      subject: 'Haven Bay Anfrage: ' + clean(p.unit_name || p.unit) + ' ' + clean(p.check_in) + '–' + clean(p.check_out),
      body: row.slice(1).join('\n')
    });
  }
  return out_({ok: true});
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
