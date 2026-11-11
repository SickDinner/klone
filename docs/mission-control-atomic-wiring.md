# KLONE 4A.8: Mission Controlin atominen tallennuspolku

`MissionControlTrackedResearch.run` käyttää nyt 4A.7:n
`finalize_verified_run_atomically`-funktiota. Tutkimusversion tallennus
ja `completed`-tapahtuma tapahtuvat samassa SQLite-transaktiossa.

Käyttöoikeudet tarkistetaan ennen `started`-kirjausta ja uudelleen
ennen lopullista tallennusta. Samaa run_id:tä ei voi käyttää uudelleen.

**Ulkoisen auditoinnin raja:** completion-auditointi tapahtuu vasta
SQLite-commitin jälkeen. Jos ulkoinen auditointi epäonnistuu, ajon tila
pysyy oikein `completed` eikä muutu virheellisesti `failed`-tilaan.
Tämä on erillinen palautettava toimitusvirhe, joka vaatii myöhemmin
outbox- tai reconciliation-mekanismin.

`started`-tilaan kaatuneen ajon automaattinen jatkaminen ei ole
turvallista ilman erillistä palautusprotokollaa.
