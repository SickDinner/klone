# KLONE 4A.10: atominen Mission Control + auditointi-outbox

`MissionControlTrackedResearch.run` käyttää nyt atomista
`finalize_verified_run_atomically`-polkua. Samassa SQLite-transaktiossa
tallennetaan dossier-versio, completed-ajotapahtuma ja odottava
auditoinnin outbox-tapahtuma.

## Vikatilanteet

- Lähde-eheystarkistus epäonnistuu: dossieria ei tallenneta;
  ajolle kirjataan failed, mikäli journal on käytettävissä.
- SQLite-commit epäonnistuu: dossier, completed ja outbox peruuntuvat
  yhdessä.
- Ulkoinen completion-auditointi epäonnistuu commitin jälkeen:
  tutkimus pysyy completed-tilassa ja outbox-tapahtuma odottaa
  toimitusta.
- `ResearchAuditOutbox(...).deliver(sink=...)` toimittaa odottavat
  tapahtumat erikseen. Sinkin on deduplikoitava `event_id`.

## Tuotantorajat

Tunnistus, käyttöoikeuksien tarkistus, luotettu auditointivastaanottaja
ja toimitustyön ajastus ovat isäntäpalvelun vastuulla. Automaattinen
palautus ei saa suorittaa samaa run_id:tä uudelleen. Ulkoisen auditoinnin
vähintään-kerran-toimitus ei ole täsmälleen-kerran-takuu.
