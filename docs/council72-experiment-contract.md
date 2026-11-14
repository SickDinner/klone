# Neuvosto 72: tavoitesopimus ja alkuperäiseen testiajoon sidottu havainto

Tämä yhdistää [perustajien katselmuksen](council72-briefing.md) nykyiseen
v2-testipatteriin ja Evidence Forensicsiin. Työketju on:

1. Valitse katselmuksesta budjettiin mahtuva `development_check`-tehtävä.
2. Valmistele koesopimus puhtaasta testattavasta checkoutista.
3. Anna sopimus testipatterille ennen ajoa.
4. Arvioi sopimus alkuperäisen manifestin, evidenssipaketin ja lokien avulla.
5. Tarkista tuloshavainto ja liitä se halutessasi uuteen neuvoston kierrokseen.

## Mitä lukitaan

Sopimus sisältää kokonaisen toistettavan katselmuksen, valitun tehtävän ja
sen nykyisen perustaja–viestinviejä-sidonnan. Testattavan kohteen identiteettiin
kuuluvat commit, testisarjan SHA-256, kerääjän kahden tiedoston SHA-256 sekä
alusta (`linux`, `win32` tai `android`). Kriteerit ovat kaikkien neljän
pakollisen vaiheen onnistuminen, läpäisseiden testien vähimmäismäärä ja
ohitusten enimmäismäärä. Täyden pytest-ajon poissuljettuja testejä ei sallita.

Sopimuksen `contract_sha256` kattaa kaikki nämä kentät. Muutos esimerkiksi
testirajaan tuottaa eri sopimuksen. Vanhan ajon tulosta ei voi sovittaa uuteen
sopimukseen muuttamatta myös ajon alkuperäistä manifestia ja pakettia.

Testipatterin uusi `--experiment-contract`-valinta lukee ja toistaa sopimuksen
ennen ensimmäistä testivaihetta ja ennen uuden ajohakemiston varaamista.
Väärä commit, muuttunut testisarja tai kerääjä, väärä alusta tai likainen
checkout pysäyttää ajon. Valittu sopimustiiviste tulee alkuperäiseen
`run.json`-tiedostoon kenttään `experiment_contract_sha256`; nykyinen
evidenssipaketti sitoo manifestin tavut ja lokit yhteen. Ilman valintaa
testipatterin nykyinen käyttö säilyy ennallaan.

Tämä on kerääjän toteuttama järjestys ja paikallinen tiivistesidonta.
Se ei todista sopimuksen ulkopuolista laatimisajankohtaa, autentikoi
testien suorittamista tai estä koko aineiston tietoista väärentämistä.
`chronology_authenticated`, `test_execution_authenticated` ja
`provenance_authenticated` pysyvät false-arvoina. Kuningas ei voi muuttaa
lukittua kriteeriä samaksi kokeeksi; uusi kriteeri on uusi sopimus.

## Tulosten merkitys

| Tulos | Merkitys | Neuvoston havainto |
| --- | --- | --- |
| `criteria_met` | Tiedostojen sidonnat täsmäävät ja kaikki ilmoitetut testiehdot täyttyvät | `supports` |
| `criteria_failed` | Sidonnat täsmäävät ja vähintään yksi testiehto epäonnistuu | `contradicts` |
| `indeterminate` | Sidonta, alkuperäisaineisto, lokin tunnistettavuus tai konteksti ei riitä | `unknown` |

Väärän commitin tai alustan vihreä ajo ei ole tämän kokeen hyväksytty tulos
eikä tämän kokeen todistettu epäonnistuminen. Se jää avoimeksi.
Legacy-v1-ajo ilman kontekstia tai v2-ajo ilman sopimustiivistettä jää myös
avoimeksi. Puuttuva loki ei muutu epäonnistumiseksi tai onnistumiseksi.

Arviointi käyttää Evidence Forensicsin yhtä rajattua lähdeotosta. Se
tarkistaa evidenssipaketin ja alkuperäisten tavujen vastaavuuden, manifestin
ja lokien ristiriidat, puhtaan checkoutin sekä ajon kontekstin ja talteenoton
täydellisyyden. Testisarjan ja kerääjän täytyy täsmätä sekä ennen että jälkeen.
Täyden testiajon argv:n täytyy olla kerääjän nykyinen suodattamaton pytest-ajo.
Arviointi ei suorita lokien tekstiä tai avaa verkko-osoitteita.

Tulos on **testipatterin ehtoja koskeva havainto**. Se ei sulje koko
muistimoduulin, genomiikan, median tai muun osa-alueen kehitystä, todenna
kaikkia kyseisen ringin lähdeväitteitä tai myönnä käyttöönoton lupaa.

## Käyttö Termuxissa

Käytä jo muodostettua katselmusraporttia, jossa haluamasi `domain:memory`
tai muu `domain:*`-tehtävä on `selected`. Tarvittaessa muuta kehitysjonon
budjettia ja tiloja ennen katselmuksen muodostamista. Sopimus ei ohita jonon
valintaa. Lähderistiriidan tai muun ei-teknisen selvitystehtävän totuutta
ei yritetä ratkaista pytest-ajolla.

Määritä polut nykyiselle asennuksellesi. Kaikki tuotokset säilytetään
checkoutin ulkopuolella, jotta ne eivät tee testattavaa checkoutia likaiseksi:

```bash
KLONE_ROOT="$HOME/klone-next"
KLONE_PY="$HOME/klone-next/.venv/bin/python"
mkdir -p "$HOME/klone-var/experiments"
KLONE_EXPERIMENT_DIR="$(mktemp -d "$HOME/klone-var/experiments/experiment-XXXXXX")"

PYTHONPATH="$KLONE_ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$KLONE_PY" \
  -m klone.council72_experiment \
  --prepare-briefing "$HOME/klone-var/katselmus.json" \
  --task domain:memory --root "$KLONE_ROOT" \
  --minimum-full-passed 983 --maximum-full-skipped 1 \
  --output "$KLONE_EXPERIMENT_DIR/sopimus.json"

PYTHONDONTWRITEBYTECODE=1 "$KLONE_PY" \
  "$KLONE_ROOT/tools/termux_evidence_battery.py" \
  --root "$KLONE_ROOT" --python "$KLONE_PY" \
  --experiment-contract "$KLONE_EXPERIMENT_DIR/sopimus.json" \
  --output "$KLONE_EXPERIMENT_DIR/ajo"

PYTHONPATH="$KLONE_ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$KLONE_PY" \
  -m klone.council72_experiment \
  --evaluate-contract "$KLONE_EXPERIMENT_DIR/sopimus.json" \
  --run-dir "$KLONE_EXPERIMENT_DIR/ajo" \
  --output "$KLONE_EXPERIMENT_DIR/tulos.json"
```

Valitse testimäärän rajat itse **ennen** ajoa. Luku 983 on käyttöesimerkki,
ei muuttuvaa testisarjaa koskeva automaattinen hyväksymisraja. Jos patteri
epäonnistuu, sen alkuperäinen tulos jää talteen ja arviointi ajetaan silti
erikseen. Vientitiedostoja ei korvata eikä raporttia saa kirjoittaa valitun
ajon tai suojatun testiajohakemiston sisään.

Sopimuksen toisto ja tuloksen tarkistus ovat erilliset:

```bash
PYTHONPATH="$KLONE_ROOT/src" "$KLONE_PY" \
  -m klone.council72_experiment \
  --verify-contract "$KLONE_EXPERIMENT_DIR/sopimus.json"

PYTHONPATH="$KLONE_ROOT/src" "$KLONE_PY" \
  -m klone.council72_experiment \
  --verify-evaluation "$KLONE_EXPERIMENT_DIR/tulos.json" \
  --run-dir "$KLONE_EXPERIMENT_DIR/ajo"
```

Tulos vaatii alkuperäiset lähdetiedostot myös myöhemmässä tarkistuksessa.
Raportissa ovat manifestin, paketin ja pakollisten lokien tiivisteet.
Samat tavut toisessa hakemistossa säilyttävät saman tuloshavainnon; tiedostojen
siirtäminen ei ole uusi riippumaton lähde. Yhdenkin lähdetiedoston muutos
rikkoo aiemman tulosraportin toiston.

## Rajapinta ja neuvostonäkymä

`POST /api/cognition/council72/experiment-contract` muodostaa sopimuksen
puhtaana laskentana. Pyynnössä ovat `review` (nykyinen review-tehtävä),
`task_id`, `expected` (`commit`, `test_suite_sha256`, `collector_sha256`,
`platform`) sekä haluttaessa `minimum_full_passed` ja `maximum_full_skipped`.
API:n identiteetit ovat kutsujan syöttämiä, ja patteri tarkistaa ne vasta
oikeaa checkoutia vastaan. API ei ota tiedostopolkuja tai lue testiajoja.

`/council72` avaa sopimus- ja tulosraportit samalla JSON-painikkeella kuin
muut neuvoston raportit. Se näyttää lukitut ehdot, sidonnat, kunkin ehdon
tuloksen ja manifestiviitteen. Selaimen tarkistus on rakenteellinen: se
ei tarkista alkuperäislokeja eikä laske Pythonin toistoa.

Paikallisen näkymän painike lisää tuloshavainnon vain seuraavan kierroksen
lomakkeelle. Muuttunut lomake, väärä lähtöistunto, toistuva havaintotunniste
tai kahdeksan täyttä kierrosta estää lisäämisen. Käyttäjä ajaa uuden
kierroksen erikseen. Sites-kopiossa paikallinen lisäystoiminto on estetty.

Havainto kulkee alkuperäisen tehtävän omalle Limbon viestinviejälle.
Kaikki tämän adapterin ajot kuuluvat yhteen `klone-test-evidence`-lähderyhmään.
Toistuva testaus ei siis täytä kahden riippumattoman lähderyhmän kiintiötä.
Tulos säilyttää koko alkuperäisen istunnon luokittelun; suljettua historiaa
ei voi alentaa julkiseksi tulosraportiksi.

Koodi ei kirjoita Memory Coreen, muuta oikeuksia, lähetä viestejä, käynnistä
kielimallityöntekijöitä tai hyväksy käyttöönottoa. Testipatteri suorittaa
testit vain käyttäjän erillisellä CLI-kutsulla. Varsinainen ajonaikainen
agentti-, token- ja energiabudjetti on edelleen seuraavaa kehitystä.
