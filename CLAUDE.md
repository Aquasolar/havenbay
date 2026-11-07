# Haven Bay Website: Regeln für Änderungen

- Direktpreise (`content/prices.json`: nightly, weekly, monthly) ändert nur Ortwin oder nur auf seinen ausdrücklichen Wunsch. Claude schlägt vor, ändert nicht von sich aus.
- Änderungen immer in einem eigenen Zweig und als Pull Request. Nicht direkt auf `main`.
- Vor dem Hochladen lokal laufen lassen: `python tests/test_sync.py && node tests/test_app.js && node tests/test_plausibility.js && node tests/test_prices.js`
- Preislogik: Direktpreise sind Endpreise inklusive Reinigung. Wochenpreis ab 7 Nächten, Monatspreis ab 28 Nächten (gilt bis `valid_until`).
- Mindestaufenthalt für alle Kanäle: 2 Nächte bis 31.05.2027.
- Keine Links aus Kalender-Exporten (iCal) oder Zugangsdaten in das Repository. Nur als Secrets.
