# KLONE E10: 72-agenttineuvoston tutkimustyöpöytä ja puhelimen Doctor

## Mikä muuttui oikeasti

Aiempi oikea Termux E9.1 -tulos 17.11.2026:
- 148 julkista lähdehavaintoa, 7 raakaa muistiparia,
- **6 eri julkaisuparia**, joista 5 tutkimusmetatietoparia ja
  1 tutkimuksen ja uutisen yhdistelmä,
- 1 päällekkäinen AgentSSL-julkaisun muistipari,
- \`memory_write=False\`, pääpalvelin 8000 pysyi käynnissä.

E10:ssa nämä **kuusi todellista, yhä aktiivista ja E8.3:n laatuseulan
läpäissyttä julkaisuparia** voidaan jakaa koko 72-jäsenisen
neuvoston tarkistustehtäviksi ilman tutkimuspäätöksiä tai muistikirjoituksia.

### Council72 – neuvoston 72 työtehtävää

\`src/klone/limbo_council_workbench.py\` lukee oikean
\`council72-catalog.json\`-tiedoston ja tarkistaa sen
**9 × 8 = 72** paikkaa ennen työnjakoa. Se ei luo
72 uutta LLM-instanssia eikä väitä simuloituja tehtäväehdotuksia
valmiiksi tutkimustuloksiksi.

Rinkikohtaiset arviointitehtävät:
1. **Limbo** – lähteiden alkuperä, julkaisukanava ja viestinnän rajat
2. **Himo** – väitteen merkitys, nollahypoteesi, viestinnän vinoumat
3. **Ylensyönti** – muistihistoria, versiot ja korjaukset
4. **Ahneus** – resurssit, tutkimuskokeiden kapeat toteutusrajat
5. **Viha** – riskit, harhat, turvallisuus ja yksityisyys
6. **Harhaoppi** – tutkimusmenetelmät, vastanäyttö ja toistettavuus
7. **Väkivalta** – järjestelmäarkkitehtuuri, eristys ja testattavuus
8. **Vilppi** – evidenssi, lähteiden riippumattomuus ja auditointi
9. **Kadotus** – kahdeksan perustajan valvonta, yksi perustaja alempaa
   rinkiä kohden

Jokaisella jäsenellä on **oma yksilöity arviontitehtävänsä**,
neuvostoluettelon todellinen ID, nimi, rinki ja paikka.
Perustajien valvottavat ringit tarkistetaan
alkuperäisestä Council72-katalogista.

Kaikki tehtävät alkavat tilasta \`pending_human_or_agent_review\`.
Raportissa on **0 suoritettua tarkistusta, 0 ääntä, 0 myönnettyä
toimintaoikeutta, 0 tieteellisesti hyväksyttyä väitettä**.
Myös mallinnetut tunteet tai välittäjäaineet pysyvät
pelkkinä numeerisina tutkimusanalogi­oina eivätkä päätösvallan
tai tietoisuutta koskevan väitteen perustana.

Evidenssivelka sisältää esimerkiksi puuttuvat kokotekstit,
tutkimusmenetelmät, yhteiskäytetyn aineiston mahdollisuuden,
vertaisarvioinnin epävarmuuden ja riippumattoman toistotutkimuksen.
Jokaisella työpöydällä on lähtömuistien alkuperäiset otsikot,
HTTPS-viitteet ja lähdetarkisteet sekä deterministinen
\`source_snapshot_sha256\` ja \`report_sha256\`.

### E10 Doctor – turvallinen kunnonvalvonta

\`src/klone/limbo_doctor.py\` lukee vain **ennalta määritellyt**
localhost-osoitteet:

- \`127.0.0.1:8000/api/health\` – alkuperäinen KLONE
- \`127.0.0.1:8031/api/health\` – Atlas
- \`127.0.0.1:8041/health\` – alkuperäisen muistin erillinen lukija

Doctor:
- ei seuraa HTTP-uudelleenohjauksia ulkoisiin osoitteisiin,
- vertaa pää-KLONEn \`database_path\`-arvoa alkuperäiseen
  \`~/klone/data/klone_mission_control.db\`-tiedostoon;
- vaatii tavallisen, ei-symbolisen, yksilinkkisen tietokantatiedoston;
- avaa SQLite-tietokannan muodossa \`mode=ro\` eikä luo uutta
  tietokantaa, skeemaa tai muistimerkintöjä;
- ajaa \`PRAGMA quick_check\`, tarkistaa keskeisten taulujen
  olemassaolon sekä laskee vain julkisen tutkimushuoneen
  aktiivisten tapahtumien ja audit-tapahtumien määrät;
- varmistaa, että 8041-lukija ilmoittaa oikean päämuistin
  tietokantapolun ja \`read_only=True\`;
- antaa \`health=ok\` tai \`health=attention_required\` ja
  ongelmakoodit ilman palvelinten käynnistämistä tai pysäyttämistä.

Doctorin audit-laskenta on pelkkä metadata-arvo, ei sisältöjen
luku. Se ei selaa yksityisiä muistihuoneita.

### Kaksi käyttötapaa Termuxissa

**Koko E10-kehityspäivitys** (testit ja vain tutkimuspalvelinten
8031/8041 päivitys):

\`\`\`sh
cd ~/klone-arxiv-e1 &&
git fetch origin feat/limbo-external-intelligence-20261115 &&
git switch --detach FETCH_HEAD &&
bash scripts/klone-atlas-e7-e8-phone.sh
\`\`\`

Uudet raportit tallentuvat myös puhelimen Lataukset-kansioon:
- \`KLONE-E9-lahdeparit.json\` – nykyiset deduplikoidut
  tutkimusparit.
- \`KLONE-E10-neuvosto.json\` – kuuden julkaisuparin
  72-paikkaiset **avoimet tutkimustehtävät** (enintään 8 paria).
- \`KLONE-E10-doctor.json\` – päämuistin, palvelimien ja
  paikallisen auditoinnin terveystarkistus.

**Pelkkä terveystarkistus ilman palvelinten päivittämistä:**

\`\`\`sh
cd ~/klone-arxiv-e1 &&
bash scripts/klone-e10-doctor-phone.sh
\`\`\`

### Rajapinnat ja käyttöliittymä

Mobiilityöpöydillä on E9:n lähdekortin sisällä uusi painike
**Avaa E10 · kaikki 72 neuvoston tehtävää**.

Sama tehtäväjako on saatavilla vain lukemiseen esimerkiksi:

\`\`\`text
GET http://127.0.0.1:8041/api/limbo-atlas/council-workbench?q=genetiikka&first_event_id=26&second_event_id=24
\`\`\`

Palvelin **tarkistaa ID:t ajon hetkellä** E9.1:n
nykyisistä canonical-lähdepareista. Vanhoja tai keksittyjä
paritunnuksia ei hyväksytä.

### Todellinen E10:n rajaus

Kumpikaan uusi komponentti ei tee tekoälymallin avulla
tutkimusten kokotekstianalyysiä, autonomisia toimia,
oikeita riippumattomia 72 jäsenen LLM-päättelyitä,
päämuistikirjoituksia, päätösvaltaisia äänestyksiä,
automaattista julkaisemista tai tieteellistä verifiointia.
E10 on **auditoitavissa oleva työnsuunnittelu ja luotettavuuden
valvonta**, ei uusi tietoisuutta tai tutkimustotuuksia
automaattisesti synnyttävä järjestelmä.

## Seuraava perusteltu kehitysporras

E11:ssa voi toteuttaa omistajan erikseen hyväksymän
alkuperäisten tutkimusten **kokotekstien hankinnan**
(sallitut lähteet, mahdollinen kirjautuminen, lisenssi,
ennalta tarkistettava latauskoko), niistä johdetut
mittausmenetelmäkortit sekä varsinaisen vastanäytön.
Vasta omistajan allekirjoittama tarkistus voisi kirjata
tuloksen erilliseen E7-hypoteesipäiväkirjaan.
