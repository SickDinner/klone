# KLONE E11 – omistajan hallitsema lähdeankkuroitu evidenssipäiväkirja

## Toteutettu muutos

E10:n oikea Android-ajotulos (17.11.2026): 148 julkista tutkimusmuistia,
6 erillistä julkaisuparia, 72 paikkaa neuvostossa,
432 *odottavaa* tarkistustehtävää, Doctor \`health=ok\` ja
päämuisti eheä. GitHubin edellinen E10-regressiomatriisi oli vihreä.

E11 on ensimmäinen rajattu askel varsinaiseen aineistoon perustuviin
arviointimerkintöihin. Sen ei tarvitse luottaa pelkkiin otsikoiden
sanastoyhtäläisyyksiin: omistaja voi antaa kaksi käytettäväksi
sallittua lähdetekstikatkelmaa ja poimia niistä eksplisiittiset lainaukset.

**E11 ei hae julkaisuja verkosta.** \`src/klone/limbo_evidence_review.py\`
lukee vain käyttäjän sille erikseen antaman **paikallisen JSON-tiedoston**.
Sillä ei ole HTTP-POST-API:a eikä automaattista internetin käyttöoikeutta.

## Turvallinen työnkulku

1. Tarkista E9.1:n oikeat, ajantasaiset julkaisut ja neuvoston E10-tehtävät.
2. Luo julkaisuparille yksilöllinen E11-manifestipohja
   \`--prepare\`-valinnalla. Pohjassa ovat lähteiden tapahtuma-ID:t,
   HTTPS-julkaisuosoitteet ja Memory Core -tarkisteet. Ei varsinaisia
   tutkimustekstejä tai uusia muistikirjoituksia.
3. Kopioi **itse käyttöoikeuksiesi puitteissa** kaksi katkelmaa
   \`sources.A.text\`- ja \`sources.B.text\`-kenttiin. Kirjaa molempiin
   \`owner_supplied: true\` ja selitys \`usage_rights_note\`.
   Tämä on käyttäjän ilmoitus, ei automaattinen lisenssivarmennus.
4. Lisää \`annotations\`-listaan omat tarkat lainaukset.
   Jokaisessa on \`source\`, \`claim_key\`, \`quote\`,
   \`stance\` ja \`note\`.
5. Suorita \`--review\`-ajo. KLONE tarkistaa, että jokainen lainaus
   löytyy **täsmälleen kerran** juuri annetusta tekstistä. Se merkitsee
   Unicode-merkkipohjaiset alku- ja loppuindeksit sekä SHA-256-tarkisteet
   lainaukselle ja lähdetekstille.
6. Raportti **ei kopioi lähteiden kokotekstejä** ulostuloon.
   Julkaisuparin, väitteen ja lainauksen tarkisteet riittävät
   myöhempään uudelleentoistoon samojen paikallisten syötteiden avulla.

### Asenna E11-pohja Termuxissa

\`\`\`bash
cd ~/klone-arxiv-e1 &&
git fetch origin feat/limbo-external-intelligence-20261115 &&
git switch --detach FETCH_HEAD &&
bash scripts/klone-e11-phone.sh
\`\`\`

Tämä suorittaa E7–E11:n kohdennetun testipaketin ja valitsee
automaattisesti olemassa olevan tutkimusparin, jossa on
\`graph\` ja \`network\`-käsitteet, jos sellainen on saatavilla.
Muutoin se valitsee ensimmäisen oikean E9.1:n tutkimusmetatietoparin.
Pohjan polku tulostuu Termuxiin kansioon \`~/klone-var/e11/\`.

Halutessasi voit antaa täsmälliset lähde-ID:t:

\`\`\`bash
bash scripts/klone-e11-phone.sh 26 24
\`\`\`

Lähde-ID:t kelpaavat vain jos ne edelleen kuuluvat oikeaan,
nykyiseen E9.1:n julkaisupariin.

### Esimerkkimerkintä E11:n JSON-manifestiin

Alla on **ainoastaan kuvitteellinen esimerkki** yhdestä lainauksesta,
joka käyttäjän täytyy korvata oikealla, lähdetekstistä kopioidulla
tekstillä:

\`\`\`json
{
  "source": "A",
  "claim_key": "graph-methods-transfer",
  "quote": "These methods were evaluated using graph data.",
  "stance": "context",
  "note": "Tarkista kohdejoukot, mittausmuuttujat ja käytetty aineisto."
}
\`\`\`

Mahdolliset \`stance\`-arvot ovat:
\`context\`, \`support_candidate\` ja \`counter_candidate\`.
Ne ovat **omistajan anotaatioita**. KLONE ei vahvista,
että lainausta tulkitaan oikein, että tutkimus on riippumaton tai
että lähteet ovat keskenään tieteellisesti ristiriidassa.

Jos samalla \`claim_key\`-nimellä on sekä tuki- että
vastanäyttöehdokkaiden anotaatiot, raporttiin tulee
\`opposing_owner_annotations_not_verified_contradiction\`.
Näin aiempi neutraali 72-paikkainen neuvosto voidaan myöhemmin
ohjata tutkimaan *molemmat* suunnat, mutta kukaan ei saa
automaattisesti hyväksyä väitettä.

### Helpompi tapa Termuxissa: kaksi tavallista .txt-tiedostoa

Sinun ei tarvitse liittää pitkiä tekstejä suoraan JSON-editorissa.
Tallenna itse käytettävissäsi oleva julkaisuteksti A tiedostoon
\`~/klone-var/e11/oma-lahde-A.txt\` ja teksti B tiedostoon
\`~/klone-var/e11/oma-lahde-B.txt\`. Pidä nämä tiedostot
Termuxin yksityisessä tallennustilassa.

Valitse oikea pohjatiedosto, jonka E11:n \`--prepare\` loi,
ja kirjoita esimerkiksi:

\`\`\`bash
cd ~/klone-arxiv-e1
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_evidence_review \
  --klone-db "$HOME/klone/data/klone_mission_control.db" \
  --fill "$HOME/klone-var/e11/OMA-POHJA.json" \
  --source-a-file "$HOME/klone-var/e11/oma-lahde-A.txt" \
  --source-b-file "$HOME/klone-var/e11/oma-lahde-B.txt" \
  --rights-note-a "Oma hyväksytty julkaisukatkelma A" \
  --rights-note-b "Oma hyväksytty julkaisukatkelma B" \
  --owner-confirms-supplied-text \
  --output "$HOME/klone-var/e11/OMA-TAyTETTY-MANIFESTI.json"
\`\`\`

Korvaa \`OMA-POHJA.json\` oikealla tiedostonimellä. Tämä vaihe
vaatii eksplisiittisen \`--owner-confirms-supplied-text\`-lipun,
tarkistaa tekstin UTF-8-koodauksen, tekstimäärien ylärajat ja
alkuperäisen Memory Coren lähdetunnisteet. Se ei vielä tee
tutkimuspäätelmiä. Tämän jälkeen sinun tarvitsee lisätä vain
haluamasi yksiselitteiset lainaukset \`annotations\`-kohtaan
ja ajaa alla oleva \`--review\`.

### Tarkista täytetty manifesti offline-tilassa

\`\`\`bash
cd ~/klone-arxiv-e1
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_evidence_review \
  --klone-db "$HOME/klone/data/klone_mission_control.db" \
  --review "$HOME/klone-var/e11/OMA-TAyTETTY-MANIFESTI.json" \
  --output "$HOME/klone-var/e11/e11-review-tulos.json"
\`\`\`

Vaihda manifestin nimi oikeaksi. Raporttia ei voi luoda uudelleen
samaan kohdepolkuun ilman uuden nimen valintaa: tämä on
tarkoituksellinen kirjoitusvirheiltä suojaava käytäntö.

### Rajat, jotka ovat tarkoituksella tiukkoja

- Vain nykyisten E9.1:n **julkisten ja deduplikoitujen**
  tutkimusparien lähdetunnukset kelpaavat.
- Lähteiden tapahtuma-ID:t, URL:t, lähdetarkisteet ja neuvoston
  lähtötilanne tarkistetaan uudelleen; vanhentuneet lähteet hylätään.
- Syötemanifesti on enintään 256 KiB, yksittäinen lähdeteksti
  enintään 60 000 merkkiä ja merkintöjä enintään 40.
- Kaikki lainaukset vaativat täsmällisen ja yksikäsitteisen tekstiosuman;
  lainauksia ei muotoilla uudelleen eikä päätellä automaattisesti.
- Syöttötiedostojen symlinkkejä ja rajattomia lukupyyntöjä ei sallita.
- Puhelimen päämuisti 8000, sen 148 julkista tutkimusviitettä,
  E7-hypoteesipäiväkirja ja 72 jäsenen päätösvalta jäävät ennalleen.
- E11:n \`completed_reviews=0\`, \`approval=false\`,
  \`scientific_truth_verified=false\` ja \`memory_write=false\`
  ovat tarkoituksellisia. Aito päättely ja päätösvallan käsittely
  vaatii erillisen, jäljitettävän hyväksyntämenettelyn.

## Seuraava vaihe

E11.1: omistajan toimittamien tietojen tekstijaksotason
menetelmä- ja rajoituspoiminnan ehdokkaat sekä
kriittinen neuvoston tarkistuslista. E11.2: itsenäisesti
arvioitujen raporttien aikajanalaskenta, jolla eri mallien
tekemät todelliset tarkistukset voidaan erottaa 72
*suunnitellusta* tehtävästä.
