# KLONE Atlas E6: tutkimusäly, ristiriitasignaalit ja päämuisti

## Tietotilanne

Käyttäjän viimeisin Android-ajon tosite vahvisti:
- 63/63 kohdistettua E1–E5-testiä läpi, portti 8031 vastasi HTTP 200.
- Julkisia E3-julkaisuviitteitä oli **148**.
- **148** uutta, julkiseksi luokiteltua \`research-room\`-Memory Core
  -tapahtumaa lisättiin portin **8031** todelliseen tietokantaan,
  \`~/klone-var/arxiv-e1.db\`.
- E5:n \`--commit\` kirjoitti tapahtumat, alkuperäislähteiden
  provenienssin ja audit-tapahtuman samassa transaktiossa.
- Pääpalvelimen portti **8000** käyttää omaa tietokantaansa;
  sen muistia ei ole vielä päivitetty tällä E6-työpuulla.

## Mitä E6 rakentaa tähän päälle?

\`src/klone/limbo_intelligence.py\` on todellinen KLONEn julkisen
Memory Coren lukija ja **deterministinen tutkimusehdotusten suunnittelija**:

1. Se lukee **vain** \`research-room\`-muistihuoneen aktiiviset,
   julkisiksi luokitellut \`unverified_public_research_observation\`
   -tapahtumat. Privaatteja, suljettuja tai genomisandboksin
   tietueita se ei edes kysy.
2. Kunkin artikkelin viimeisin muistiversio valitaan artikkeli-ID:n ja
   versionumeron mukaan. Vanhojen versioiden lukumäärä näkyy raportissa.
3. Tutkimuskysymystä verrataan lähdeotsikoihin, tieteenaloihin
   ja alkuperäisiin lyhyisiin lähdekuvauksiin. Yleiset suomenkieliset
   hakutermit laajennetaan eksplisiittisellä, tarkastettavalla
   englanninkielisten termien sanastolla (esim. genetiikka,
   psykiatria, filosofia, talous ja tekoäly).
4. Aiheeltaan lähellä olevia lähteitä verrataan keskenään.
   \`topic_overlap\` tarkoittaa yhteistä sanastoa, ei samaa tulosta.
   \`potential_claim_tension\` tarkoittaa vain kahta mahdollisesti
   vastakkaissuuntaista *sanallista vihjettä*; ristiriita
   **ei ole todennettu**, sillä kokeen tulokset ja väitteiden
   kohteet voivat olla aivan eri asioita.
5. Lähteiden kustantajaryhmät erotellaan; eri kustantaja ei vielä
   todista aidosti riippumatonta tutkimusnäyttöä.
6. Limbon kahdeksan olemassa olevan viestinviejän vastuualueista
   muodostetaan jatkotutkimuskysymykset, vaihtoehtomallien
   testausesitykset ja asiantuntijarinkien tehtäväehdotukset.
7. Valitut Memory Core -tietueet syötetään myös
   **olemassa olevaan Council72-istuntoon**. Lähteiden kuitit
   tarkistetaan ennen istuntoa uudelleen ja kaikki havainnot
   pysyvät \`stance=unknown\`. Agenttien neuromodulaattorit,
   äänet ja kahdeksan erikoisagentin ringit pysyvät
   **simuloituna päätöksen esikatseluna**.
8. Ei ulkoisia verkkohakuja, ei automaattista julkaisua,
   ei muutoksia mihinkään Memory Core -tietokantaan.

E6 on nykyisellään **lähteitä yhdistelevä kysymysten suunnittelija**.
Se ei ole koulutettu omaksi tieteelliseksi päättelymalliksi eikä
kykene varmistamaan tutkimusten koko sisältöä pelkän RSS-tiivistelmän
perusteella. \`question\`, \`source_url\`, \`receipt_sha256\` sekä
epävarmuusraja säilyvät.

## Asenna E6 nykyisen 8031-portin KLONEen

\`\`\`bash
cd ~/klone-arxiv-e1 || exit 1

git fetch origin feat/limbo-external-intelligence-20261115 || exit 1
git switch --detach FETCH_HEAD || exit 1

bash scripts/klone-atlas-e3-phone.sh || exit 1
\`\`\`

Skripti suorittaa E1–E6-testit ja käynnistää uudelleen **vain
paikallisen 8031-palvelun** tästä samasta työpuusta.

Avaa \`http://127.0.0.1:8031/limbo-atlas\`. Sivun
**Atlas E6 · Neuvoston tutkimusäly** -kohdassa:
- kirjoita esim. \`genetiikka\`, \`muisti\`, \`filosofia\`,
  \`psykiatria\`, \`talous\` tai \`ancestry\`;
- valitse 12, 24 tai 48 julkista tutkimusviitettä;
- valitse automaattinen tai yksi ringeistä 2–8;
- avaa lähdevertailut, varovaiset ristiriitasignaalit,
  tehtäväehdotukset ja Council72-agenttien esikatselu;
- halutessasi tallenna JSON-analyysi.

E6:ta voi käyttää myös suoraan Termuxissa:

\`\`\`bash
cd ~/klone-arxiv-e1 || exit 1
STAMP="$(date +%Y%m%d-%H%M%S)"
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_intelligence \
  --klone-db "$HOME/klone-var/arxiv-e1.db" \
  --question "genetiikka" \
  --limit 24 \
  --output "$HOME/klone-var/e6-research-$STAMP.json"
\`\`\`

## Pää-KLONEn muistin (portti 8000) turvallinen integraatio

### Suunnitelma A: nykyinen 8000-palvelin tuntee research-roomin

\`scripts/klone-atlas-main-memory.sh\` tarkistaa:
- portin 8000 **todellisen** \`/api/health.database_path\`-arvon;
- \`/api/rooms\`-vastauksesta \`research-room\`-huoneen;
- E3:n 148 julkisen lähdehavainnon esikatselun;
- SQLite-online-varmuuskopion ja sen \`PRAGMA integrity_check\` -tuloksen;
- kirjoittamiseen tarvittavan käyttäjän oman vahvistuksen \`PAAMUISTI\`.

Jos \`research-room\` on tuettu ja hyväksyt, E5:n sama auditoitu
tuontimoottori siirtää lähdehavainnot myös **8000:n oikeaan tietokantaan**.
Jokainen kaksoiskappale jätetään kirjaamatta uudelleen.
Mitään ei kirjoiteta automaattisesti.

### Suunnitelma B: portti 8000 käyttää edelleen vanhaa ohjelmistoversiota

**Älä vaihda pääpalvelimen lähdekoodia kesken käynnissä olevan työn.**
Käynnistä ensin erillinen **vain luku** -E6-lukija. Se käyttää
portin 8000 todellista tietokantaa, mutta ei käynnistä uudelleen
vanhaa pääpalvelinta:

\`\`\`bash
cd ~/klone-arxiv-e1 || exit 1
bash scripts/klone-main-research-canary.sh
\`\`\`

Portissa 8041 on vain rajatut luku-API:t:
- \`http://127.0.0.1:8041/health\`
- \`http://127.0.0.1:8041/api/limbo-atlas/intelligence?q=genetiikka\`
- \`http://127.0.0.1:8041/api/limbo-atlas/memory/recall?q=genetics\`

Tämä lukija **ei** avaa mitään Memory Coren kirjoitus-API:a.

Kun vain luku -katselun tietokantapolku on varmistettu, suoritettavissa
on erikseen omistajan hyväksyntää odottava tuonti:

\`\`\`bash
cd ~/klone-arxiv-e1 || exit 1
bash scripts/klone-atlas-main-memory.sh
\`\`\`

Skripti tekee aina esikatselun, SQLite-varmuuskopion ja
omistajan \`PAAMUISTI\`-vahvistuksen. Jos 8000 on vielä vanha,
se hyväksyy tuonnin vasta kun **8041:n read-only-tutkimuslukija
osoittaa täsmälleen samaan pääpalvelimen tietokantaan**.
Aineisto tulee tällöin oikeaan päämuistiin, mutta 8000:n
vanha käyttöliittymä ei vielä osaa näyttää \`research-room\`-huonetta.
Uusia tutkimuksia voidaan lukea portin 8041 kautta.

**Pää-KLONEn ohjelmiston myöhempi päivitys vaatii erillisen hallitun
julkaisu- ja palautussuunnitelman.** Näitä kahta palvelua ei
automaattisesti korvata toisillaan.

## Turvallisuus ja rajat

- Avoin lähdehavainto ei ole sama asia kuin todennettu tieteellinen fakta.
- Kertomukset, negatiot, tilastolliset erot ja kausaalisuus arvioidaan
  vasta lukemalla alkuperäiset tutkimukset ja niiden menetelmät.
- Päämuistiin viedään vain E3:n **julkiset** ja uudelleen validoidut
  tietueet; yksityistä muisti-, lääke- tai DNA-dataa ei kopioida.
- Pääpalvelimen 8000 lähdekoodia, prosessia, tietyssä
  \`~/klone\`-työpuussa olevia muutoksia tai sen muita portteja
  ei muuteta näillä skripteillä.
- \`E6\` ei kirjoita muistiin. \`E5\`-päämuistituonti
  kirjoittaa **vain manuaalisen hyväksynnän jälkeen**.
