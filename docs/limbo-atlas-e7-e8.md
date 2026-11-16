# KLONE Atlas E7/E8 – hypoteesien aikakirja ja tutkimuksen löytötutka

E1–E6 toivat ulkomaailman julkisten tutkimusten metatietoja oikeaan
KLONE Memory Coreen. Käyttäjän Android-lokit vahvistivat 16.11.2026:
- 148 muistilähdettä portin 8000 **päämuistissa** ja portin 8031
  kehitysmuistissa, julkisessa \`research-room\`-huoneessa;
- portin 8041 read-only E6-analyysissä 148 viitettä ja genetiikalla
  24 valittua osumaa, 18 vertailua, 1 neuvostoluonnos;
- ei automaattisia Memory Core -kirjoituksia E6-lukuhaussa.

**E7 ja E8 ovat uusia kehitysvaiheita, joita ei pidä merkitä puhelimessa
asennetuiksi ennen tässä dokumentissa annettua erillistä asennusajoa.**

## E7 – hypoteesin geneettinen sukupuu / tutkimuksen aikakirja

\`src/klone/limbo_hypotheses.py\` luo valinnaisen erillisen
\`~/klone-var/atlas-hypotheses.sqlite3\`-tietokannan.

- Hypoteesilla on nimi, tieteenala, rajattu kysymys ja
  **falsifioiva eli sen kumoava mitattava koe-ehdotus**.
- Jokainen tapahtuma (\`proposed\`, \`source_link\`, \`review\`)
  lisätään omaan, versioituun aikakirjaan; vanhaa merkintää ei
  ylikirjoiteta.
- \`source_link\` viittaa todelliseen, nykyiseen KLONEn
  \`research-room\`-Memory Core -tapahtumaan ja tallentaa
  lähteen URL:n, artikkelin ID:n, versiotunnisteen, lähde-ID:n ja
  alkuperäisen \`receipt_sha256\`-tarkisteen.
- Linkit merkitään \`support_candidate\`, \`counter_candidate\`
  tai \`context\`; nämä eivät ole vahvistettuja tuloksia.
- Versiolokissa käytetään determinististä SHA-256-ketjua;
  aiempi versio merkitään seuraavan tarkisteeseen.
  **Tämä havaitsee yksinkertaiset jälkikäteen tehdyt muutokset,
  mutta ei ole ulkoisesti ankkuroitu tai muuttumaton auditloki.**
- Omistaja voi merkitä työn tilaksi esimerkiksi \`in_review\`,
  \`needs_replication\`, \`inconclusive\` tai \`retired\`.
  **\`verified\` tai \`proven\` ei ole sallittu tila** pelkkien
  lähdetiivistelmien perusteella.
- Kullakin hypoteesilla on **evidenssivelka**: lähteiden
  alkuperäisen sisällön tarkastus, metodien analyysi, riippumattoman
  vastanäytön etsintä ja toistettavuuden varmistaminen.
- \`expected_revision\` torjuu vanhentuneesta ruudusta tehtävät
  päällekkäiset kirjoitukset.
- **Ei selainkirjoituksia eikä automaattista tuontia.**
  Komentorivin \`--commit\` on pakollinen ennen jokaista kirjoitusta.
  Yksityiset Memory Core -huoneet eivät ole lähdevalikoimassa.

### Esikatsele uusi hypoteesi

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
PY="$HOME/klone-next/.venv/bin/python"
CORE="$HOME/klone/data/klone_mission_control.db"
JOURNAL="$HOME/klone-var/atlas-hypotheses.sqlite3"

PYTHONPATH="$PWD/src" "$PY" -m klone.limbo_hypotheses \
  --propose --klone-db "$CORE" --journal-db "$JOURNAL" \
  --domain genetics \
  --title "Muinais-DNA:n riippumaton toistettavuus" \
  --question "Toistuvatko haploryhmäpäätelmät riippumattomassa aineistossa?" \
  --falsifier "Toisesta aineistosta tehty ennakkorekisteröity koe ei toista päätelmää."
\`\`\`

Tämä tulostaa \`mode=preview\`. Jos haluat **nimenomaisesti**
kirjata hypoteesin, suorita sama komento lisävalinnalla \`--commit\`.
Muutos menee vain erilliseen \`atlas-hypotheses.sqlite3\`-päiväkirjaan.
Pää-KLONEn Memory Coren olemassa olevia 148 havaintoa ei muokata.

### Liitä todellinen julkinen lähde ja arviointimerkintä

1. Tarkista halutun julkisen Memory Core -muistihavainnon \`event_id\`
   päämuistin \`http://127.0.0.1:8041/research\`-näkymästä.
2. Tarkista hypoteesin nykyinen ID ja versio:

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_hypotheses \
  --journal-db "$HOME/klone-var/atlas-hypotheses.sqlite3" \
  --list \
  --output "$HOME/klone-var/atlas-e7-list-$(date +%Y%m%d-%H%M%S).json"
\`\`\`

3. Esikatsele lähteen liittämistä; vaihda \`1\` oikeaksi hypoteesi-ID:ksi,
   \`123\` oikeaksi lähdemuistin ID:ksi sekä \`1\` tämän hypoteesin
   viimeisimmäksi versioksi:

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_hypotheses \
  --journal-db "$HOME/klone-var/atlas-hypotheses.sqlite3" \
  --klone-db "$HOME/klone/data/klone_mission_control.db" \
  --attach --hypothesis-id 1 --source-event-id 123 \
  --stance context --expected-revision 1 \
  --note "Tarkista riippumaton aineisto, menetelmät ja päätelmän rajat."
\`\`\`

Vasta nimenomaisella \`--commit\`-lisävalinnalla lähdelinkki
tallennetaan. Tilapäätös kirjataan erikseen \`--review --state
needs_replication --hypothesis-id 1 --expected-revision N --note
"Huomiot" --commit\`. Päätös koskee tutkimusprosessin tilaa,
ei väitteen automaattista totuusarvoa.

## E8 – tieteenalojen väliset heikot signaalit ja evidenssivelka

\`src/klone/limbo_discovery.py\` analysoi vain todellisia julkisia
Memory Core -havaintoja:
- Tunnistaa ehdokasyhteyksiä **eri tutkimusalojen** julkaisujen
  välillä yhteisten termien ja lähdemuistien avulla.
- Erottaa eri julkaisijaryhmät, mutta **ei kutsu sitä todisteeksi
  riippumattomista tutkimuksista**.
- Laskee eksplisiittisen **tutkimisen prioriteetin**, joka suosii
  puuttuvien tarkistusten täyttämistä – ei väitä tietävänsä
  hypoteesin todennäköisyyttä.
- Määrittää kahdeksan kriittistä tutkimusnäkökulmaa:
  nollahypoteesi, sekoittavat tekijät, mittausvirhe, käänteinen
  kausaalisuus, lähteiden riippuvuus, mallin rajat, kumoava
  havainto sekä eettiset ja turvallisuusriskit.
- **Muistien aikakone** vertaa kahta saman tutkimuskysymyksen
  E6-JSON-tilannekuvaa ja kertoo uudet, valinnasta pois jääneet
  ja versioltaan muuttuneet artikkelit. Poissaolo hausta ei ole
  julkaisun peruminen eikä tutkimusnäytön katoaminen.
- Ei ulkoisia verkko- tai muistioperaatioita.

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
STAMP="$(date +%Y%m%d-%H%M%S)"
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_discovery \
  --klone-db "$HOME/klone/data/klone_mission_control.db" \
  --question "genetiikka" --limit 48 \
  --output "$HOME/klone-var/e8-radar-$STAMP.json"
\`\`\`

## Yksi käyttöönottokomento puhelimessa

\`\`\`sh
cd ~/klone-arxiv-e1 || exit 1
git fetch origin feat/limbo-external-intelligence-20261115 || exit 1
git switch --detach FETCH_HEAD || exit 1

bash scripts/klone-atlas-e7-e8-phone.sh
\`\`\`

Skripti:
1. testaa E7:n ja E8:n sekä aiemmat E1–E6-rajat;
2. päivittää **vain** paikallisen Atlas-palvelimen 8031;
3. tunnistaa alkuperäisen 8000-pääpalvelimen todellisen tietokannan;
4. vie E8-löytötutkan raportin Lataukset-kansioon;
5. muodostaa E7:n hypoteesiesikatselun **ilman kirjoituksia**;
6. päivittää erillisen 8041-päämuistilukijan E8-versioon
   tarkistamalla ensin prosessin alkuperän ja tietokantapolun.

**Pääpalvelinta 8000 ei pysäytetä, eikä päämuistiin kirjoiteta.**

### Työpöydät

- \`http://127.0.0.1:8031/limbo-atlas\`: E7-päiväkirjan
  JSON-tuonti ja interaktiivinen E8-löytötutka.
- \`http://127.0.0.1:8041/research\`: päämuistin julkinen
  E6-tutkimusnäkymä ja uusi E8:n evidenssivelkanäkymä.

GitHub PR: \`https://github.com/SickDinner/klone/pull/177\`.

## E9 – tuleva jatko

Käyttäjän erillisen hyväksynnän jälkeen seuraavat vaiheet voisivat
olla omistajan auditointimerkinnät myös KLONEn Constitution-
tapahtumina, 72 neuvoston monikierroksinen arviointiprosessi,
jossa johtopäätökset ovat erillisiä lähdeväitteistä, sekä
valinnaiset lähderiippuvuuden tarkastukset täysistä julkaisuista
tekijöiden, aineistotunnisteiden ja preprint-versioiden avulla.
