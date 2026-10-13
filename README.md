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

## Gästeseite (/guest)

Die Gästeinfos liegen unter `https://www.havenbay.eu/guest` (Englisch) und sind per Sprachmenü in alle 8 Sprachen umschaltbar (`/de/guest.html` usw.). Die Seite ist nicht von der Website verlinkt, steht auf `noindex` und ist in `robots.txt` ausgeschlossen. Die URL bleibt gleich, die QR-Codes in den Apartments können also hängen bleiben.

Inhalt ändern: `content/guest.json` (WLAN, Telefonnummern, Zeiten oben; Texte je Sprache unter `t`). Achtung: Das Repository und die Seite sind öffentlich lesbar. Keine Türcodes oder Safe-Codes eintragen. Das WLAN-Passwort ist wie bisher für jeden mit dem Link sichtbar.

## Tagespreise

Preise pro Nacht lassen sich für einzelne Tage oder Zeiträume festlegen (z. B. Lada-Marathon). Sie gehen vor den Monatspreisen aus `content/prices.json`.

1. Google-Tabelle „Haven Bay Tagespreise“ (Blatt `Tagespreise`, Blatt `Regeln` mit Mindestpreisen) mit den Spalten `von`, `bis`, `studio`, `apartment`, `bezeichnung`, `status` (Zeilen mit `vorschlag` erscheinen nicht auf der Website, erst nach Freigabe) (Datum als `13.08.2027` oder `2027-08-13`; `bis` leer = ein Tag; Preis leer = Monatspreis gilt; `bis` und Preise gelten je Nacht, `bis` inklusive).
2. Datei > Im Web veröffentlichen > Blatt als CSV. Den Link als Secret `PRICES_CSV_URL` eintragen.
3. Die Seite liest die Tabelle stündlich. Zeiträume mit Bezeichnung erscheinen auf den Unterseiten unter „Special dates“. Monatspreise ab 28 Nächten bleiben unverändert.

## Reinigungstag

`content/operations.json`: Endet ein Aufenthalt an einem Werktag (Mo–Fr), ist die Nacht des Abreisetags ebenfalls gesperrt, damit die Wohnung gerichtet werden kann. Am Wochenende gibt es keinen Puffer. Zeiträume ohne Puffer (Urlaub, Lenka vor Ort) unter `free_dates` eintragen, z. B. `[["2027-08-01", "2027-08-31"]]`.

Die Sperre gilt für die Website. Damit auch Booking sie berücksichtigt, erzeugt die Synchronisation pro Unterkunft eine iCal-Datei mit Direktbuchungen und Reinigungstagen (keine Buchungen der Plattformen): `https://www.havenbay.eu/ical/<ICAL_EXPORT_TOKEN>/studio.ics` und `.../apartment.ics`. Diese Links bei Booking und Airbnb als zusätzlichen Kalender importieren (sofern die Plattform den Import anbietet). Airbnb kann Vorbereitungszeiten auch selbst einstellen.

Optionale Secrets: `ICAL_ADMIN` (geheime iCal-Adresse des Admin-Kalenders; Termine "Studio · Direkt · Name", "Apartment · Blockiert · Grund" oder "Studio + Apartment · Direkt · Name" sperren die Einheit), `ICAL_DIRECT_STUDIO`, `ICAL_DIRECT_APARTMENT` (iCal-Links der Google-Kalender mit Direktbuchungen), `ICAL_EXPORT_TOKEN` (zufällige Zeichenfolge, mindestens 20 Zeichen).

## Fotos

Quelle: Google Drive, `Immobilien/Rogotin Primorska 14A/HavenBay/Fotos/WebSite` und `Things to do`. Für das Web verkleinert (max. 1600 px) in `site/assets/img/`:

| Datei | Inhalt |
|---|---|
| `hero-bay.jpg` | Drohnenfoto der Bucht (Titelbild) |
| `bay-2.jpg` | Sonnenuntergang (Abschnitt „Location“) |
| `studio-01..10.jpg` | Studio (Haven Bay 1), Reihenfolge = Galerie, Nr. 1 = Vorschaubild |
| `apartment-01..12.jpg` | Apartment (Haven Bay 2) |
| `todo/<id>.jpg` | Bild zum Eintrag mit gleicher `id` in `things-to-do.json` |

Austauschen: Datei mit gleichem Namen überschreiben. Neue Fotos: in `content/units.json` unter `photos` eintragen. Fehlende Bilder zeigen einen Farbverlauf.

Hinweise:
- Die Zuordnung zu Studio/Apartment stammt aus den Dateinamen (A1 = Studio, A2 = Apartment) und dem Raumeindruck. Bitte prüfen. Zwei Dateien tragen „A2“, zeigen aber den Raum des Studios (`Apartment A2.jpg`, `orange Couch aufgebettet A2.jpg`) und wurden nicht verwendet.
- Nicht verwendet: Fotos mit erkennbaren Personen sowie Bilder mit KI-artigen Dateinamen (z. B. „Helles Wohnzimmer mit Meerblick und Sonnenuntergang“), die Dubletten echter Fotos zu sein scheinen. Gästen sollten nur echte Fotos der Unterkunft gezeigt werden.
- Bilder von Restaurants/Webseiten Dritter (WhatsApp, .webp) sind nicht übernommen, solange die Rechte nicht geklärt sind.

## Veröffentlichen mit havenbay.eu

1. Repository > Settings > Pages > Source: GitHub Actions.
2. Actions > „Website veröffentlichen“ > Run workflow.
3. Pages > Custom domain: `www.havenbay.eu`, HTTPS erzwingen.
4. Bei Porkbun: `www` als CNAME auf `aquasolar.github.io`; für die Hauptdomain vier A-Records auf `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`. Alte Google-Sites-Einträge entfernen.

Hinweis: GitHub pausiert geplante Workflows nach 60 Tagen ohne Repository-Aktivität. Dann einmal manuell starten oder einen Commit machen.
