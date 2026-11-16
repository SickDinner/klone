# KLONE Atlas E5 – ulkomaailman julkiset tutkimukset Memory Coreen

**Tämä vaihe toteuttaa käyttäjän pyytämän yhteyden oikeaan KLONE-älymuistiin.**
E3:n erillinen SQLite-arkisto säilyy lähteenä. E5 ei luo uutta korvaavaa
muistimoottoria, vaan kirjoittaa E3:n uusimmat, tarkistettujen lähdeviitteiden
metatiedot KLONEn **olemassa oleviin \`memory_events\`- ja
\`memory_provenance\`-tauluihin**, omistajan käskystä.

## Muistien tietosisältö

Jokainen julkaisu kirjataan näin:
- \`room_id = research-room\`, \`classification_level = public\`
- \`event_type = unverified_public_research_observation\`
- \`source_table = atlas_revisions\`, lähde-ID \`article:<id>:revision:<id>\`
- otsikko, julkaisijan kuvaus, alkuperäisen julkaisun HTTPS-URL
- aihealue (genetiikka, farmakologia/psykologia, talous, geopolitiikka,
  filosofia, yhteiskunta, teknologia tai luonnontieteet)
- alkuperäinen Limbo-agentti / välittäjä, E3-metadata-versio ja SHA-256-kuitti
- **\`epistemic_status = unverified_publisher_claim\`**, \`truth_verified = false\`

Tämä tuottaa autenttisen merkinnän **siitä, että KLONE vastaanotti
lähteen julkaisumetatiedon**. Se **ei** autentikoi julkaisun tieteellistä
sisältöä, aitoutta, vertaisarviointia tai väitteen todenperäisyyttä.

## Valta-, huone- ja audit-rajat

- Vanhaa \`public-room\`-huonetta **ei muuteta**. Sen kirjoituslupa
  pysyy rajoitettuna.
- Lisätään \`research-room\` (tuettu \`public_room\`-tyyppi,
  \`public\`-luokitus). Sinne saa kirjoittaa vain omistajan manuaalisella
  työkalukomennolla; automaattista syöte- tai HTTP-kirjoittajaa ei ole.
- Ennen kirjoittamista tarkistetaan AccessGuard ja ClassificationGuard.
  Jos ne eivät salli muutosta nimenomaisesti, tuonti pysähtyy.
- Luodut muistitapahtumat, niiden lähdeprovenienssit ja omistajan
  tuontia koskeva audit-tapahtuma kirjoitetaan **samassa
  SQLite-transaktiossa**. Audit-virhe peruuttaa koko erän.
- Vanhan version muistimerkintää ei ylikirjoiteta. Uusi E3-artikkeliversio
  luo oman identifioitavan Memory Core -tapahtuman.
- Jo tuodun artikkeliversion uusintatuonti on idempotentti.
- Älymuistin salattuja/yksityisiä huoneita, raaka-DNA:ta tai henkilökohtaisia
  muistioita ei lueta eikä muuteta. Myöskään mitään ei julkaista ulkoverkkoon.
- Tarkoitettu Termux-ympäristöön ja olemassa olevaan 8031-kehityspalvelimeen.
  Työkalussa **kohde-Memory Core -tietokantapolku annetaan aina erikseen**;
  se ei arvaa kohdetta eikä luo uutta puuttuvaa KLONE-tietokantaa.

## Päivitä E5 nykyiseen Termux-työpuuhun

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
git fetch origin feat/limbo-external-intelligence-20261115 || exit 1
git switch --detach FETCH_HEAD || exit 1

PY="$HOME/klone-next/.venv/bin/python"
PYTHONPATH="$PWD/src" "$PY" -m unittest discover \
  -s tests -p 'test_limbo_memory_bridge.py' || exit 1

# Muutkin Limbo-testit ja yksinomaan oman portin 8031 uudelleenkäynnistys
bash scripts/klone-atlas-e3-phone.sh || exit 1
\`\`\`

## Esikatsele 147 tutkimusviitteen tuonti

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_memory_bridge \
  --atlas-db "$HOME/klone-var/atlas-memory.sqlite3" \
  --klone-db "$HOME/klone-var/arxiv-e1.db"
\`\`\`

Varmista, että raportti kertoo:
\`mode=preview\`, \`room_id=research-room\`,
\`archive_articles=147\`, \`selected=147\`,
\`memory_events_were_written=false\`.
Jos 8031-palvelimen tietokanta ei ole \`arxiv-e1.db\`,
tarkista \`http://127.0.0.1:8031/api/health\`-vastauksen
\`database_path\` ennen minkään \`--commit\`-komennon käyttöä.
Jos haluat tutkimusmuistit myös erilliseen pää-KLONE-palvelimeen,
tuo ne sinne omalla, oikeaksi tunnistetulla DB-polulla vasta erikseen.

## Kirjoita vasta tarkistetun esikatselun jälkeen

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_memory_bridge \
  --atlas-db "$HOME/klone-var/atlas-memory.sqlite3" \
  --klone-db "$HOME/klone-var/arxiv-e1.db" \
  --commit \
  --output "$HOME/klone-var/atlas-e5-$(date +%Y%m%d-%H%M%S).json"
\`\`\`

Tämä ei vahvista yhtään tutkimusväitettä oikeaksi. Se luo ne
lähdekriittiseen Memory Core -tietoon.

## Hae tutkimus muistista, pyydä kontekstia

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_memory_bridge \
  --klone-db "$HOME/klone-var/arxiv-e1.db" \
  --recall "genetics"
\`\`\`

Myös nykyinen KLONEn MemoryService toimii:
- \`GET /api/memory/events?room_id=research-room&limit=100\`
- \`GET /api/memory/context/package?room_id=research-room&event_id=<id>\`
- \`GET /api/memory/context/payload?room_id=research-room&event_id=<id>\`
- \`GET /api/limbo-atlas/memory/recall?q=genetics&limit=20\`

Selaimen Atlas-työpöydällä \`/limbo-atlas\` näkyy oma
**E5 Älymuisti** -haku. Jokainen tulos sisältää lähdesivun ja
linkin Memory Coren omaan lähteelliseen kontekstipakettiin.

## E5.1 – seuraavat kehityskohdat

1. Rikkaampi semanttinen muistihaku (upotukset ja mallit, kun ne ovat
   oikeasti paikallisesti käytössä; ei tekaistua 'ymmärtämistä').
2. Julkaisujen riippumattoman lähdekritiikin selitetty tila:
   menetelmä, aineisto, vertaisarviointi, virhelähteet ja vastaevidenssi.
3. Rinkkien työhypoteesit omiksi versioiduiksi muistisolmuiksi,
   lähde- ja hypoteesikytkennät sekä ihmisen erillinen tarkistuspäätös.
4. Pysyvän E4-jonon hyväksyntä- ja etenemisloki,
   joka ei sekoitu tutkimusväitteen totuusarvioon.
