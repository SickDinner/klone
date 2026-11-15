# KLONE Limbo Atlas E2 – 8 alaa, 26 lähdettä, 7 asiantuntijarinkiä

## Mitä tämä tekee?

Atlas E2 **ei luo uusia neuvoston jäseniä**. Se käyttää suoraan
\`council72-catalog.json\`-tiedoston kahdeksaa ensimmäisen (Limbo) ringin
viestinviejää, heidän nykyisiä tehtäviään, perustajayhteyksiään ja
kuutta rajattua laskennallista neuromodulaattoria.

| Limbo-agentti | Jäsen | E2-vastuualue | Työluonnoksen oletusrinki |
|---|---:|---|---|
| Naberius | 24 | Geopolitiikka, diplomatia, turvallisuus, kansainvälinen oikeus | 8, Vilppi (evidenssi ja auditointi) |
| Ronove | 27 | Talous, työmarkkinat, rahoitus, eriarvoisuus | 4, Ahneus (resurssit ja toteutusjärjestys) |
| Forneus | 30 | Tekoäly, teknologia, tietoturva ja insinööritieteet | 7, Väkivalta (arkkitehtuuri ja rajatut toimet) |
| Caim | 53 | Yhteiskunta, koulutus, kansanterveys ja viestintä | 5, Viha (kuormitus ja säätely) |
| Orobas | 55 | **Genetiikka**, muinais-DNA, genomiikka, evoluutio ja populaatiot | 3, Ylensyönti (muisti ja kokemukset) |
| Seere | 70 | Luonnontieteet, fysiikka, ilmasto, energia ja avaruus | 6, Harhaoppi (tutkimus ja vaihtoehtomallit) |
| Gusion | 11 | **Psykiatria, psykologia, farmakologia**, neurotiede ja lääkkeiden turvallisuus | 5, Viha (kognitio ja riskit) |
| Dantalion | 71 | **Filosofia**, historia, uskonnot, etiikka, taide | 2, Himo (merkitys ja luovuus) |

**Rinkien nimet ovat KLONEn fiktiivistä rakennetta.**
Ne eivät luokittele tieteenaloja moraalisesti eikä mikään ääri- tai
väkivaltaisen toiminnan simulaatio saa toteutusvaltaa.

Tutkimus lähtee Limbon courier-ID:stä → sisäinen 72-jäseninen
neuvosto käsittelee epävarmana väitteenä → E2 ehdottaa aiheesta
työluonnoksen ringeille 2–8 (asiantuntija, perustaja, kysymykset,
lähdeviitteet, vaihtoehtoiset selitykset, falsifiointi).
Käyttäjä voi vaihtaa vastaanottavan ringin ja muotoilla itse kysymyksen.

## Julkiset lähteet

E2 sisältää **26 kuratoitua lähdeasetusta**; ne eivät ole 26 toisistaan
riippumatonta julkaisijaa.

- **arXiv**: AI, koneoppiminen, taloustiede, rahoitustiede,
  genomiikka, populaatio/evoluutio, neurotiede, geofysiikka,
  kvanttifysiikka, tieteenhistoria ja -filosofia.
- **Europe PMC**: genomiikka, muinais-DNA, psykiatria,
  psykologia, farmakologia ja lääketurvallisuus.
- **RSS-uutiset**: BBC:n maailma, talous, teknologia, terveys,
  koulutus, tiede ja ympäristö; Guardian World, Smithsonianin
  innovaatiot, Nasan uutisvirta.
- **Stanford Encyclopedia of Philosophy**: virallinen
  \`https://plato.stanford.edu/rss/sep.xml\` uudet ja päivitetyt artikkelit.

Suoraan virallisiin API-ohjeisiin:
- https://info.arxiv.org/help/api/index.html
- https://dev.europepmc.org/RestfulWebService
- https://plato.stanford.edu/new.html

Aineistot voivat sisältää vertaisarvioimattomia esijulkaisuja,
organisaatioiden tiedotteita sekä journalistista raportointia.
**Otsikko tai referaatti ei todista väitettä oikeaksi.**
Sama kustantaja lasketaan yhdeksi julkaisijaryhmäksi.

## Päivitä olemassa oleva Termux-työpuu

Ei uutta KLONE-kopiota; käytetään jo toimivaa
\`~/klone-arxiv-e1\`-hakemistoa ja virtuaaliympäristöä.

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
git fetch origin feat/limbo-external-intelligence-20261115 || exit 1
git switch --detach FETCH_HEAD || exit 1

PY="$HOME/klone-next/.venv/bin/python"
PYTHONPATH="$PWD/src" "$PY" -m unittest discover \
  -s tests -p 'test_limbo_atlas.py' || exit 1
PYTHONPATH="$PWD/src" "$PY" -m unittest discover \
  -s tests -p 'test_limbo_external.py' || exit 1
\`\`\`

### Hae 2 aihetta (genetiikka ja psykiatria/farmakologia)

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
mkdir -p "$HOME/klone-var"
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_atlas \
  --fetch \
  --domain genetics \
  --domain mind_medicine \
  --output "$HOME/klone-var/atlas-genetics-mind-$(date +%Y%m%d-%H%M%S).json"
\`\`\`

### Hae jokaiselta alalta (voi kestää useita minuutteja)

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_atlas \
  --fetch --all \
  --output "$HOME/klone-var/atlas-all-$(date +%Y%m%d-%H%M%S).json"
\`\`\`

Kaikki lähteet eivät välttämättä vastaa; yhden epäonnistuminen
ei muuta muiden havaintojen laatua eikä estä niiden raportointia.
Haku on aina **käyttäjän manuaalisesti käynnistämä**, ei ajastettu.
\`--all\` tasapainottaa enintään 48 havaintoa kaikkien kahdeksan
osa-alueen kesken niin, etteivät ensimmäisenä haetut lähteet vie kaikkea tilaa.

### Avaa päivitetty UI portissa 8031

Nykyisen portin 8031 Uvicorn-prosessi on käynnistetty ilman automaattista
lähdekoodin latausta. **Uusi FastAPI-reitti vaatii prosessin uudelleenkäynnistyksen.**
Portin 8000 ja 8001 prosesseihin ei kosketa.

Tarkista ensin prosessi:

\`\`\`sh
ps -A -o PID,ARGS | grep 'uvicorn' | grep '8031'
\`\`\`

Jos kyseessä on KLONEn aiemmin tähän porttiin käynnistetty prosessi,
pysäytä sen **oikea PID** \`kill -TERM <PID>\` ja käynnistä uusi:

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
PY="$HOME/klone-next/.venv/bin/python"
mkdir -p "$HOME/klone-var"

KLONE_DB_PATH="$HOME/klone-var/arxiv-e1.db" \
KLONE_DATA_DIR="$HOME/klone-var" \
PYTHONPATH="$PWD/src" \
nohup "$PY" -m uvicorn klone.main:app \
  --host 127.0.0.1 --port 8031 \
  > "$HOME/klone-var/arxiv-server.log" 2>&1 < /dev/null &

sleep 3
curl -fsS http://127.0.0.1:8031/api/limbo-atlas/catalog
\`\`\`

Uusi käyttöliittymä: **http://127.0.0.1:8031/limbo-atlas**

### Aiemman 12 artikkelin raportin tuonti

Työpöydällä on oma **Tuo tutkimus-JSON** -painike.
Vanhan E1-raportin \`arxiv-ai\` ja \`arxiv-neuro\` muunnetaan E2:n
lähde-ID:ihin ja oikeisiin vastuuagentteihin. Otsikot, linkit ja
referaatit säilyvät; muunnos ei ole todisteiden laadun parantumista.
Raportti on selaimen välilehden muistissa, ei pysyvässä tietokannassa.

## Käyttörajoitukset

- Ei salaa ihmistä esittävää bottiverkkoa, itsenäistä somejulkaisua,
  yksityisiä tilejä, kirjautumisia tai autonomisia ulkoisia viestejä.
- Ei mielenterveysdiagnooseja tai lääkehoitosuosituksia aineiston
  otsikoiden perusteella.
- Ei yksityisen Memory Coren luku- tai kirjoitusoikeuksia.
- Syötedata pysyy epäluotettavana, ja jokainen suunnitelma on
  **tarkistettava tutkimusluonnos**, ei toimeksianto.
- E2:n suunnitelman istunto voidaan toistaa samasta syötteestä,
  mutta lähteiden tietosisältöä ei siinä autentikoida.
