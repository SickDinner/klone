# KLONE Limbo Atlas E4 – koko tutkimusarkiston tasapainoinen tutkimusjono

E3 säilyttää kaikki julkiset tutkimusviitteet; E4 antaa niille
**deterministisen, toistettavan käsittelyjärjestyksen** neuvostoa varten.

Käyttäjän Android-lokissa 16.11.2026 E3 raportoi:
- 2 arkistointikierrosta;
- 147 eri julkaisuviitettä ja 147 metadata-versiota;
- toisessa ajossa 99 uutta ja 48 ennestään tunnettua havaintoa;
- 1 tyhjä lähde, \`arxiv-finance\` (tilana \`empty\`),
  joka ei sellaisenaan tarkoita verkon toimintahäiriötä.

E4:n tavoitteena on varmistaa, ettei 48 havainnon neuvoston
istuntoraja jätä yhtään arkistoon tallennettua viitettä ilman
**mahdollisuutta** päätyä erikoisagenttien arvioitavaksi.

## E4:n rakenne

1. Lue E3:n **jokaisen artikkelin viimeisin** versio
   erillisestä \`atlas-memory.sqlite3\`-tietokannasta, readonly.
2. Varmista uudelleen URL, lähde-ID, Limbo-agentin ID,
   vastaanottava tieteenala ja alkuperäinen SHA-256-kuitti.
3. Tasaa jonotus kaikille kahdeksalle aihealueelle, ja sen sisällä
   lähdeasetuksille. Kaikki artikkeli-ID:t säilyvät: ei hiljaisia pudotuksia
   tai kopioita.
4. Jaa jono enintään 48 havainnon eriin:
   nykyisillä 147 viitteellä **48 + 48 + 48 + 3 = 147**.
5. Luo \`snapshot_sha256\`, joka muuttuu, jos arkistossa on uusi artikkeli
   tai sen viimeisin metadata-versio muuttuu. Jokaisella erällä on
   oma ID ja sisältötiiviste.
6. Tuota turvallisesti uusi E4-JSON. Työpöytä voi avata sen paikallisesti,
   valita yhden erän ja käyttää olemassa olevaa
   \`POST /api/limbo-atlas/plan\`-rajapintaa.
7. Valinnainen \`--batch N\` muodostaa yhden erän neuvoston
   ideointirungot suoraan Termuxissa. Käyttäjä voi antaa myös
   \`--ring 2..8\` ja \`--question\`-kysymyksen.

**Arkistoitu ≠ tutkimusjonossa ≠ tarkastettu ≠ varmennettu.**
E4:n jonoon lisääminen tai ideointiluonnoksen tuottaminen ei muuta
tutkimusjulkaisua tieteellisesti varmennetuksi eikä merkitse
automaattista tutkimussuoritusta.

## Päivitä nykyinen Android-asennus

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
git fetch origin feat/limbo-external-intelligence-20261115 || exit 1
git switch --detach FETCH_HEAD || exit 1

PY="$HOME/klone-next/.venv/bin/python"
PYTHONPATH="$PWD/src" "$PY" -m unittest discover \
  -s tests -p 'test_limbo_queue.py' || exit 1

bash scripts/klone-atlas-e3-phone.sh
\`\`\`

E3-käynnistysskripti lataa saman nykyisen työpuun
\`127.0.0.1:8031\`-palveluun. Se ei pysäytä muita portteja.

## Vie kaikki arkistoidut tutkimukset työjonoon

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
STAMP="$(date +%Y%m%d-%H%M%S)"

PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_queue \
  --db "$HOME/klone-var/atlas-memory.sqlite3" \
  --output "$HOME/klone-var/atlas-e4-queue-$STAMP.json" || exit 1

cp "$HOME/klone-var/atlas-e4-queue-$STAMP.json" \
   "$HOME/storage/downloads/KLONE-E4-tyojono.json"
\`\`\`

Avaa \`http://127.0.0.1:8031/limbo-atlas\` ja tuo
\`KLONE-E4-tyojono.json\`. Voit valita ensimmäisen, toisen,
kolmannen tai neljännen erän. Paina
**Lataa valittu erä neuvoston ideointiin**.
Valitse lopuksi vastaanottava rinki tai automaattinen
monialainen reititys ja käynnistä ideointiluonnosten luonti.

## Valinnainen täysin offline-hahmotelma yhdelle erälle

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
STAMP="$(date +%Y%m%d-%H%M%S)"
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_queue \
  --db "$HOME/klone-var/atlas-memory.sqlite3" \
  --batch 1 \
  --output "$HOME/klone-var/atlas-e4-council-1-$STAMP.json"
\`\`\`

Muuta \`--batch 1\` arvoksi 2, 3 tai 4. Tämä **ei** avaa internetiä,
ei tee muistiarkiston muutoksia eikä lähetä viestejä ringin ulkopuolelle.
Tiedosto sisältää yhden 48 havainnon (viimeisessä erässä 3 havainnon)
neuvostoistunnon luonnoksen.

## arXiv Finance: empty vs. error

E4:n mukana E2-hakuloki erottaa:
- \`empty_sources\`: lähde vastasi, mutta ei tarjonnut hyväksyttyjä
  havaintoja. Näin käyttäjän \`arxiv-finance\` merkitään.
- \`fetch_errors\`: verkon / XML:n / ulkoisen palvelun todellinen virhe.

Vanhoissa E2/E3-raporteissa nämä saatettiin laskea samaan
\`fetch_errors\`-listaan, vaikka tyhjällä lähteellä oli status \`empty\`.
Rajoitus: \`empty\` ei yksin kerro, oliko lähde todella julkaisuton
vai oliko julkaisuista vain nolla hyväksyttävissä URL- ja sisältörajoilla.

## Seuraava E4.1

- Manuaalinen hyväksyttyjen tutkimustehtävien ja käsittelytilojen
  seuranta erillisessä kirjattavassa journalissa, joka ei ole
  sama kuin tieteellisen näytön varmennus.
- Tutkimushypoteesin tarkka periytyvä historia: väite,
  falsifioitava ennuste, kannattava evidenssi, vastaevidenssi,
  päätös sekä perustelut ja tarkistuksen suorittaja.
- Tieteidenväliset ristiriitakartat, joissa tilastolliset
  tulokset, peer review -tila ja lähderiippuvuus esitetään
  toisistaan erillisinä.
