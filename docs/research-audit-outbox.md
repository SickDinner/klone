# KLONE 4A.9: auditoinnin pysyvä outbox

Tutkimusversion ja `completed`-tapahtuman kanssa **samassa
SQLite-transaktiossa** tallennetaan myös auditoinnin toimituspyyntö.

`ResearchAuditOutbox(database_path).pending()` palauttaa odottavat
tapahtumat. `deliver(sink=...)` lähettää ne luotetulle auditointipalvelulle
ja merkitsee toimitetut tapahtumat. Jos vastaanottaja on poissa käytöstä,
tapahtuma jää odottamaan uutta yritystä.

Tapahtuman tunniste on vakaa `research-run:<run_id>`.

## Tärkeät rajat

- Toimitustakuu on **vähintään kerran**, ei täsmälleen kerran.
  Vastaanottajan on poistettava kaksoiskappaleet `event_id`-tunnuksella.
- Vastaanottajan onnistumisen ja paikallisen toimituskuittauksen välissä
  tapahtuva kaatuminen voi johtaa saman tapahtuman uuteen lähetykseen.
- Isäntäpalvelun tulee valvoa lähettäjän identiteettiä ja pääsyä
  tietokantaan. Outbox ei itsessään toteuta tunnistusta.
- Tämä ei vielä käynnistä automaattista taustatyöntekijää eikä korvaa
  vanhaa ulkoista auditointicallbackia.
- `started`-tilaan jääneiden ajojen palautus tehdään erikseen.
