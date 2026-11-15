# KLONE External Intelligence Network E1 – Limbon julkinen tutkimus

**Tila: kokeellinen, lähteisiin sidottu tutkimuskomponentti.**
Ei autonomista somejulkaisua, tilien luontia, ihmiseksi tekeytymistä,
luvattomia kirjautumisia, piilotettua sidosverkostoa eikä oikeuksia
KLONEn yksityiseen muistiin. Ulkoista viestintää varten on vain
**lähettämättömiä, tekoälyluonteensa ilmoittavia kysymysluonnoksia**.

## Mikä on oikeasti toteutettu?

- 8 Limbon nykyistä agenttia **suoraan Council72-katalogista**, ei korvaavia hahmoja.
- Jokaisen agentin perustajakytkentä (9. ringin kuninkaan ID), työtehtävä,
  kuusi baseline-neuromodulaattoria ja johdettu laskennallinen huomiopolitiikka.
- 8 kiinteää, julkista HTTPS RSS/Atom-syötettä: BBC, NASA, arXiv, Smithsonian.
  Osalla eri syötteistä on sama julkaisija. Sama kustantaja lasketaan
  **yhdeksi lähderyhmäksi**, eikä sitä saa vääristää riippumattomaksi vahvistukseksi.
- **Vain erillisellä CLI-komennolla käynnistettävä verkkoluku.**
  Ei tausta-ajastimia, automaattista kirjautumista, indeksointia tai someposteja.
- Joka lähteestä vain enintään 6 havaintoa; rajattu XML-koko (1 MiB),
  lukuviive, suljetut uudelleenohjaukset, kiinteät nimet ja isäntäjoukot.
  URL:t tarkistetaan. Näiden rajojen vuoksi osa RSS-syötteistä voi epäonnistua,
  ja epäonnistumisen syy raportoidaan eikä sitä korvata keksityllä aineistolla.
- 48 havainnon rajoitetut vientiaineistot, SHA-256-sormenjäljet,
  public-luokitus ja **stance=unknown**, kunnes lähdeväite on erikseen tarkistettu.
- Raportti menee **olemassa olevan** neuvoston deterministiseen istuntomoottoriin.
  Havainto kulkee courier → steward → council, mutta mikään teksti
  ei itsessään saa hyväksyntää tai suoritusvaltaa.
- \`GET /api/limbo-external/agents\`, \`GET /sources\`, \`POST /preview\`,
  \`POST /question-draft\`. Nämä API-pyynnöt **eivät fetchaa ulkoverkkoa**.
- Selainpohjainen työpöytä osoitteessa \`/limbo-external\`, jossa voi lisätä
  havaintoja, tuoda CLI-raportin, tehdä neuvoston esikatselun sekä luoda
  tekoälyksi tunnistettavan kysymysluonnoksen.

**Toteuttamatta:** itsenäinen jatkuva seuranta, sosiaalisen median kanavaliittimet,
lähetyslupajono, pitkäaikainen agenttikohtainen tietokantamuisti,
luokiteltujen tietojen ulosmenevän siirron hyväksyntä sekä oikea dialogia ylläpitävä
ulkoinen kielimalliyhteys. E1 on näiden turvallinen edeltävä vaihe.

## Kahdeksan reittiä

| Limbo-agentti | Jäsen-ID | Alkutehtävä |
| --- | ---: | --- |
| Naberius | 24 | Kielten ja yleisöjen tulkkaus |
| Ronove | 27 | Yhteisökeskustelun tiivistys |
| Forneus | 30 | Dokumentaation ja ohjeiden selkeys |
| Caim | 53 | Palautteen ja erimielisyyksien vastaanotto |
| Orobas | 55 | Väitteiden ja lähdeviitteiden tarkistus |
| Seere | 70 | Ajankohtaisten havaintojen välitys |
| Gusion | 11 | Kysymysten reititys oikeaan rinkiin |
| Dantalion | 71 | Viestin sävyn ja ymmärrettävyyden arviointi |

Agenttien varsinaiset perustajakytkennät ja laskennalliset kuuden modulaattorin
arvot luetaan aina samasta \`council72-catalog.json\`-tietokannasta.

## Käyttöönotto puhelimella ilman portin 8000 asennuksen sotkemista

Oletus: nykyinen KLONE on \`~/klone-next\` ja sen venv
\`~/klone-next/.venv\`.

\`\`\`sh
cd ~/klone-next || exit 1
git fetch origin feat/limbo-external-intelligence-20261115 || exit 1
ROOT="$HOME/klone-limbo-e1"

if [ ! -e "$ROOT" ]; then
  git worktree add --detach "$ROOT" FETCH_HEAD || exit 1
fi

cd "$ROOT" || exit 1
PY="$HOME/klone-next/.venv/bin/python"
PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
  -s tests -p 'test_limbo_external.py'
\`\`\`

Käynnistä toinen, erillinen kehityspalvelin porttiin **8001**.
Se käyttää **omaa, erillistä tietokantaa**, eikä muuta jo käynnissä
olevan portin 8000 KLONEn dataa:

\`\`\`sh
cd ~/klone-limbo-e1 || exit 1
mkdir -p "$HOME/klone-var"
KLONE_DB_PATH="$HOME/klone-var/limbo-e1.db" \
KLONE_DATA_DIR="$HOME/klone-var" \
PYTHONPATH="$PWD/src" \
nohup "$HOME/klone-next/.venv/bin/python" -m uvicorn klone.main:app \
  --host 127.0.0.1 --port 8001 \
  > "$HOME/klone-var/limbo-e1-server.log" 2>&1 < /dev/null &
sleep 4
curl -sS http://127.0.0.1:8001/api/health
\`\`\`

Selainosoite: **http://127.0.0.1:8001/limbo-external**.

Jos olet käynnistänyt koodin aiemmin toisesta työhakemistosta,
tarkista uudelleenkäynnistys ja git-version SHA ennen testaamista.

## arXivin viikonloppuhaku: --recent

ArXivin virallinen RSS-syöte on **tyhjä lauantaisin, sunnuntaisin ja
arXivin lomapäivinä**. Se on normaalia eikä tarkoita, että KLONE tai
verkkoyhteys olisi rikki. Vanha komentorivityökalu ilmoitti tällöin
"no public feed observations", mikä näytti tekniseltä virheeltä.

Nyt **vain käyttäjän käynnistämä** \`--fetch --recent\` hakee kuusi
viimeisintä julkaistua artikkelia aihealuetta kohti arXivin virallisesta
Atom-haku-API:sta \`https://export.arxiv.org/api/query\`.

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
git fetch origin feat/limbo-external-intelligence-20261115 || exit 1
git switch --detach FETCH_HEAD || exit 1

PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m unittest discover -s tests -p 'test_limbo_external.py' || exit 1

PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_external \
  --fetch --recent \
  --source arxiv-ai \
  --source arxiv-neuro \
  --output "$HOME/klone-var/arxiv-recent-$(date +%Y%m%d-%H%M%S).json"
\`\`\`

Kun haet molemmat kategoriat, ohjelma odottaa vähintään 3 sekuntia
hakujen välissä arXivin API-ohjeen mukaisesti.
Tämä ei ole jatkuva, ajastettu tai automaattinen haku.

Jos arXiv-API ei vastaa, KLONE ilmoittaa syötteen virheen. Virhetilanteesta
ei kirjoiteta onnistunutta raporttia, eikä tutkimuksia keksitä.
JSON-raportin voi tuoda avattuun työpöytään
\`http://127.0.0.1:8031/limbo-external\`.
CLI käyttää uusinta Python-koodia ilman palvelimen uudelleenkäynnistystä.


## Yhden julkisen lähteen nouto (vain omalla komennolla)

\`\`\`sh
cd ~/klone-limbo-e1 || exit 1
PYTHONPATH="$PWD/src" \
"$HOME/klone-next/.venv/bin/python" -m klone.limbo_external \
  --fetch \
  --source arxiv-ai \
  --output "$HOME/klone-var/limbo-ai-20261115.json"
\`\`\`

Huomaa: \`--fetch\` on tietoinen lupa ohjelmalle hakea
**vain ennalta hyväksytystä** syötteestä. Osa virallisista syötteistä saattaa
estää koneellista noutoa tai ohjata uuteen URL-osoitteeseen, jolloin luku
hylätään. Verkko-API:t ja käyttösäännöt tulee tarkistaa ennen säännöllistämistä.
Vienti ei korvaa aiemmin samannimistä tiedostoa.

Avaa luotu JSON työpöydän ”Tuo havainto-JSON” -toiminnolla.
Raportin vastaanottaminen ei kirjoita KLONEn Memory Coreen.

## Käytettävät ulkoiset lähteet

Lähteet tarkistetaan julkaisutavan ja toistettavuuden mukaan. Esimerkiksi
arXivin virallinen RSS-ohje kertoo kiinteistä kategoriaosoitteista,
Nasan RSS-sivu luettelee uutis- ja teknologiavirtoja, Smithsonian
julkaisee aihekohtaisia syötteitä ja BBC:llä on julkiset uutisvirrat.
Tätä listaa on laajennettava lähde kerrallaan ja kunkin lähteen käyttöehtoja noudattaen.

## Tärkeät rajat

- Feed/artikkelin teksti on **epäluotettavaa dataa**.
  Sitä ei suoriteta eikä tulkita käyttöoikeus- tai työohjeeksi.
- Kaikki artikkelit ovat **raportoituja väitteitä**, ei automaattisesti
  vahvistettuja tosiasioita. Samalta kustantajalta saadut kaksi RSS-artikkelia
  eivät muutu kahdeksi riippumattomaksi todisteeksi.
- Analyysi ei anna identiteettiä, lähetä viestejä, nosta luokitusta,
  muuta hypervisoria eikä suorita Python- tai shell-koodia havaintotekstin perusteella.
- Nimimerkit ovat sallittuja. Ulkopuolelle lähtevä viesti ilmoittaa
  tekoälyluonteensa, vaikka se ei kerro omistajan henkilöllisyyttä,
  KLONEn sisäistä arkkitehtuuria tai yksityisiä muistoja.
- Yhteydenotot vaativat ennakkotarkistuksen. Ei koordinoitua harhaanjohtamista.
