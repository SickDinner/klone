# KLONE Limbo Atlas E3 – pysyvä julkinen tutkimusmuisti

E3 täydentää E2-tutkimustyöpöytää **erillisellä,
käyttäjän nimenomaisesti valitsemalla SQLite-arkistolla**.

- E1: 8 Limbo-viestinviejää ja perusarXiv-lukija.
- E2: 8 monialaista vastuuta, 26 julkista lähdeasetusta, 72-neuvoston
  rajattavat tutkimusluonnokset.
- E3: alkuperäiset julkisten lähteiden havaintotietueet säilyvät ja
  seuraavat hakukierrokset voivat vertailla, **onko sama viite uusi,
  sisältääkö se muuttunutta metadataa vai onko se ennestään tuttu**.

**Julkaisun metadatan muuttuminen ei todista sen tutkimustuloksen muuttuneen**.
Tietojen oikeellisuus, kokeiden toistettavuus ja toisistaan riippumattomat
lähteet vaativat yhä varsinaisen tutkimisen.

## E3:n turva- ja tietomalli

- **Oma tietokanta:** \`~/klone-var/atlas-memory.sqlite3\`, erillään
  KLONEn SQLite Mission Controlista, yksityisestä Memory Coresta ja
  henkilökohtaisista tai lääketieteellisistä tiedoista.
- **Vain julkiset lähdemetatiedot:** \`source_id\`, \`courier_id\`,
  artikkelin HTTPS-URL, otsikko, lähteen kuvausteksti ja julkaisuhetki.
  Ne validoidaan uudelleen E2:n 26 lähteen rekisteriä ja 8 nykyistä
  Limbo-agenttia vasten.
- **Sovellustason append-only:** tallennuskoodi ei muuta tai poista
  vanhoja versioita. Vanha versio sisältää sormenjäljen, jota
  seuraava versio osoittaa \`previous_sha256\`-kentällä. Käyttäjän
  omistamaa SQLite-tiedostoa ei kuitenkaan ole kryptografisesti
  sinetöity; tätä ei pidä kutsua muuttumattomaksi, turvatuksi lokiksi.
- **Erän idempotenssi:** saman raporttisisällön tuonti toiseen kertaan
  ei tee uutta ajoa eikä muutosta vanhaan tietokantaan.
- **Tunnistetut muutokset:** \`new\`, \`metadata_changed\`, \`unchanged\`.
  Uusi \`run_id\` ja artikkelin \`version\` ovat paikallisen
  arkistoinnin tietoja, eivät tutkimuksen vertaisarviointitilaa.
- **Yksi tietokantatransaktio** uusia havaintoja, versioita ja
  tuontierää varten. Puutteelliset tai luvattomiksi tulkitut
  havaintosyötteet hylätään ennen arkistointia.
- **Ei automaattisia muutoksia:** verkkohaku, arkiston tallennus,
  ulkoiset viestit ja somejulkaisut eivät ole toistensa sivuvaikutuksia.
  HTTP API:ssa ei ole uusia arkistointitoimintoja.

### Rajat

- Korkeintaan **512 hyväksyttyä havaintoa per arkistointierä**.
- E2-neuvoston käsittelyerä säilyy **48 havainnossa**.
- Koko 26 lähteen hakua ajettaessa valinnainen \`--memory-db\`
  tallettaa **kaikki palautuneet hyväksytyt havainnot**, myös ne,
  jotka eivät mahdu 48 havainnon neuvostoraporttiin.
- Muistiarkiston luku- ja kirjoituspolun tulee osoittaa suoraan
  \`~/klone-var\`-hakemistoon, eikä symbolisia linkkejä hyväksytä.
- Koko raporttitiedoston lukemiselle on 24 MiB katto.

## Käyttö Android/Termuxissa

Seuraavat komennot käyttävät **jo asennettua**
\`~/klone-arxiv-e1\`-työpuuta. Ne eivät vaadi uuden portin avaamista
tai nykyisen palvelimen pysäyttämistä.

### 1. Päivitä E3 ja testaa

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
git fetch origin feat/limbo-external-intelligence-20261115 || exit 1
git switch --detach FETCH_HEAD || exit 1

PY="$HOME/klone-next/.venv/bin/python"
PYTHONPATH="$PWD/src" "$PY" -m unittest discover \
  -s tests -p 'test_limbo_memory.py' || exit 1
PYTHONPATH="$PWD/src" "$PY" -m unittest discover \
  -s tests -p 'test_limbo_atlas.py' || exit 1
\`\`\`

### 2. Arkistoi aikaisempi 48 havainnon raportti

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
PY="$HOME/klone-next/.venv/bin/python"
mkdir -p "$HOME/klone-var" "$HOME/storage/downloads"

PYTHONPATH="$PWD/src" "$PY" -m klone.limbo_memory \
  --ingest "$HOME/klone-var/atlas-all-20261116-014113.json" \
  --db "$HOME/klone-var/atlas-memory.sqlite3" \
  --output "$HOME/klone-var/atlas-e3-first-delta.json"

cp "$HOME/klone-var/atlas-e3-first-delta.json" \
  "$HOME/storage/downloads/KLONE-E3-ensimmainen-muutos.json"
\`\`\`

Tämä arkistoi vain alkuperäiseen E2-raporttiin tallentuneet 48 havaintoa.
**Aiemmassa haussa raportin ulkopuolelle jääneitä 99 tietuetta ei voi
palauttaa tästä 48 havaintoa sisältävästä JSONista**; ne edellyttävät
uutta julkisten lähteiden hakua.

### 3. Uusi täysi 26 lähteen haku sekä muistitoiminto

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
PY="$HOME/klone-next/.venv/bin/python"
STAMP="$(date +%Y%m%d-%H%M%S)"

PYTHONPATH="$PWD/src" "$PY" -m klone.limbo_atlas \
  --fetch --all \
  --memory-db "$HOME/klone-var/atlas-memory.sqlite3" \
  --memory-delta-output "$HOME/klone-var/atlas-e3-delta-$STAMP.json" \
  --output "$HOME/klone-var/atlas-e3-briefing-$STAMP.json" || exit 1

cp "$HOME/klone-var/atlas-e3-delta-$STAMP.json" \
  "$HOME/storage/downloads/KLONE-E3-muutokset.json"
cp "$HOME/klone-var/atlas-e3-briefing-$STAMP.json" \
  "$HOME/storage/downloads/KLONE-E3-tutkimusraportti.json"
\`\`\`

Aiemmin käsitellyt julkaisut merkitään \`unchanged\`, jos lähteen
tallennettu otsikko, tiivistelmä ja julkaisuhetki ovat yhtenevät.
Muuttunut lähdemetadata saa uuden version. Tiedostonimestä syntyy
uusi jokaisella ajokerralla; SQLite-arkiston polku pysyy samana.

### 4. Tarkista muistissa olevat julkaisut

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
STAMP="$(date +%Y%m%d-%H%M%S)"
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_memory \
  --status \
  --db "$HOME/klone-var/atlas-memory.sqlite3" \
  --output "$HOME/klone-var/atlas-e3-status-$STAMP.json"

cp "$HOME/klone-var/atlas-e3-status-$STAMP.json" \
  "$HOME/storage/downloads/KLONE-E3-tila-$STAMP.json"
\`\`\`

Tämä lukee arkistoa ilman muutoksia. Tiedostot luodaan ensin suoraan `~/klone-var`-hakemistoon ja kopioidaan vasta sitten Lataukset-kansioon, koska KLONEn turvallinen vientikirjoitin hylkää Termuxin symbolisen `~/storage/downloads`-linkin.

Tämä lukee arkistoa ilman muutoksia. Tuotu E3-muutos- tai tilaraportti
voidaan näyttää \`/limbo-atlas\`-työpöydän **Atlas E3** -osiossa.
Palvelimen pitää olla käynnissä E3:n käyttöliittymätiedostoilla
päivitetystä työpuusta. Jos portissa 8031 on vanha Uvicorn-prosessi,
se pitää käynnistää uudelleen; pelkkä \`git fetch\` ei lataa uusia
FastAPI-reittejä vanhaan prosessiin.

## Myöhemmät E4-tutkimustehtävät

- Vahvistettujen alkuperäislähteiden vertailu ennen johtopäätöstä.
- Erottelu oikeisiin kokeellisiin tuloksiin, puhtaasti uutisoituihin
  väitteisiin, esijulkaisuihin ja toimituksellisiin arvioihin.
- Aihekohtaiset tutkimuskysymysten jatkoversiot, joissa sama vanha
  idea, sen arviointi, epävarmuus ja uusi lähde jäävät ketjuun.
- Valinnainen ajastus ja lähteiden palvelukohtainen käyttöehto- sekä
  pyyntötahtikäytäntö ennen käyttöönottoa.
