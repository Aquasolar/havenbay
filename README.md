# Haven Bay – Website

Statische, mehrsprachige Website (EN, DE, HR, CS, HU, PL, IT, SL) für Haven Bay Apartments, Rogotin. Gehostet über GitHub Pages, erzeugt von `build.py` (nur Python-Standardbibliothek).

## Aufbau

| Pfad | Inhalt |
|---|---|
| `config.json` | Domain, Sprachen, Kontaktdaten, Betreiberangaben, Formular-Endpunkt |
| `content/units.json` | Studio (Haven Bay 1) und Apartment (Haven Bay 2): Gäste, Ausstattung, Fotos |
| `content/prices.json` | Nächtepreise pro Monat, Monatspreis, Gültigkeit bis 31.05.2027 |
| `content/ui.json` | Alle Oberflächentexte in 8 Sprachen |
| `content/things-to-do.json` | Ausflugsziele, Events, eigene Beiträge |
| `content/legal.json` | Impressum und Datenschutz (Entwurf, rechtlich prüfen lassen) |
| `site/assets/` | CSS, JavaScript, Bilder (`img/`, `img/todo/`) |
| `scripts/sync_availability.py` | Holt die iCal-Kalender von Booking/Airbnb |
| `apps-script/inquiry.gs` | Empfängt Anfragen (Google Sheet + E-Mail) |
| `.github/workflows/deploy.yml` | Tests, Kalenderabgleich, Build, Veröffentlichung (stündlich) |

## Lokal erzeugen

```
python build.py --draft --availability content/availability.sample.json --out dist
python tests/test_sync.py && node tests/test_app.js
```

Die Produktionsversion (ohne `--draft`) bricht ab, solange `prices.json` nicht `"confirmed": true` hat.

## Preise und Kontaktdaten ändern

- Nächtepreise: `content/prices.json`, Schlüssel 1–12 = Monat, `null` = „auf Anfrage“.
- Monatspreis: `monthly.price` (pro 30 Nächte, gilt ab 28 Nächten bis `valid_until`).
- Kontakt: `contact_email`, `contact_phone` in `config.json`.

## Ausflugstipps erweitern

In `content/things-to-do.json`:

- Neuer Ort: Eintrag in `places` mit `cat`, `name`, Texten `t.en`/`t.de`/`t.hr`, optional `map`, `url`, `phone`.
- Karussell „Aktuell“: `featured: true` setzen, optional `season` (Monate) oder `ends` (Datum) bzw. `annual` (jährliches Event).
- Eigener Beitrag (Ausflug, Event): Eintrag in `posts`. Fehlende Sprachen fallen auf Englisch zurück.
- Fotos nach `site/assets/img/todo/<id>.jpg`.

## Kalender-Synchronisation

1. Booking: Extranet > Kalender > Kalender synchronisieren > Exportlink kopieren (Einstellung „Gebuchte und geschlossene Daten“).
2. Airbnb: Kalender > Verfügbarkeit > Kalender verbinden > Kalender exportieren.
3. Im Repository unter Settings > Secrets and variables > Actions anlegen:
   - `ICAL_STUDIO` (Haven Bay 1), `ICAL_APARTMENT` (Haven Bay 2). Mehrere Links (Booking + Airbnb) durch Leerzeichen trennen.
4. Direktbuchungen in einen Google-Kalender eintragen und dessen iCal-Link bei Airbnb und Booking importieren; den Link zusätzlich zum jeweiligen Secret hinzufügen. Die Synchronisation hat Verzögerung (stündlich), Doppelbuchungen sind daher bei Buchungen am selben Tag möglich.

Die Links gehören nur in Secrets, nie in das Repository. Auf der Website erscheinen nur belegte Zeiträume, keine Gästedaten.

## Anfrageformular

1. Neues Google-Sheet, Erweiterungen > Apps Script, Inhalt von `apps-script/inquiry.gs` einfügen, `OWNER_EMAIL` setzen.
2. Bereitstellen > Web-App (Ausführen als: Ich, Zugriff: Jeder).
3. URL in `config.json` bei `form_endpoint` eintragen. Ohne Endpunkt öffnet das Formular das E-Mail-Programm.

## Fotos

Bilder nach `site/assets/img/` legen (Dateinamen siehe `content/units.json`, zusätzlich `hero-bay.jpg`, `bay-2.jpg`). Fehlende Bilder zeigen einen Farbverlauf. Nur Fotos verwenden, an denen du die Rechte hast.

## Veröffentlichen mit havenbay.eu

1. Repository > Settings > Pages > Source: GitHub Actions.
2. Actions > „Website veröffentlichen“ > Run workflow.
3. Pages > Custom domain: `www.havenbay.eu`, HTTPS erzwingen.
4. Bei Porkbun: `www` als CNAME auf `aquasolar.github.io`; für die Hauptdomain vier A-Records auf `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`. Alte Google-Sites-Einträge entfernen.

Hinweis: GitHub pausiert geplante Workflows nach 60 Tagen ohne Repository-Aktivität. Dann einmal manuell starten oder einen Commit machen.
