# KLONE 4A.7: atominen tutkimusajon valmistuminen

`finalize_verified_run_atomically(...)` käyttää yhtä SQLite-yhteyttä ja
`BEGIN IMMEDIATE`-transaktiota tallentaakseen **sekä dossier-version
että tutkimusajon completed-tapahtuman**. Jos kumpi tahansa kirjoitus
epäonnistuu, kumpikaan ei jää tietokantaan.

Ennen transaktiota tarkistetaan kuratoidun julkisen tutkimuksen JSON,
lähteiden tavueheys, hypoteesit ja raportti. Transaktiossa tarkistetaan
että run_id kuuluu samaan trace_id/dossier_id-yhdistelmään ja on edelleen
tilassa `started`. Samalla estetään saman ajon kaksoisvalmistuminen.

## Rajat

- Tämä on luotetun palvelun sisäinen transaktioprimitiivi, ei julkinen API.
- `started`-merkintä syntyy erikseen ennen tutkimuksen suorittamista.
- Ulkoiset auditointicallbackit eivät kuulu SQLite-transaktioon.
- Lähteiden SHA-256 ei todista lähteen aitoutta eikä väitteen totuutta.
- Ei automaattista toipumista keskeneräisistä ajoista tai julkaisuvaltuutta.
- Integrointi Mission Controlin `run`-polkuun tehdään seuraavassa vaiheessa;
  tämä PR ei vielä muuta olemassa olevan 4A.6-palvelun kirjoituspolkua.
