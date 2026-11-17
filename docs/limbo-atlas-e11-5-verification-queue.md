# KLONE E11.5 – lähdevarmennuksen tutkimusjono, neuvoston kaksoistarkastus

## Lähtökohta: oikea Android E11.4 -testiajo 17.11.2026

Viimeisin omistajan vahvistama E11.4-tulos:
- 53/53 kohdennettua Termux-testiä läpäisty
- julkaisupari 26 / 24, yhteensä 16 kontekstimerkintää
- 4 kirjoittajan/tiivistelmän esittämää tulosväitettä, jotka on tarkistettava alkuperäislähteestä
- 6 muuta vahvistamatonta kontekstikatkelmaa
- 3 toimituksellista varoitusta, 2 otsikkoa ja 1 avoin kysymys
- 0 riippumattomasti vahvistettua tutkimustulosta, 0 neuvoston suorittamaa arviota, 0 päämuistikirjoitusta

E11.4:n todellinen yksityinen raportti oli:
\`~/klone-var/e11/e11-4-laatuauditointi-20261117-041520.json\`.

Nämä ovat **luokittelun** tuloksia, eivät todisteita artikkelien
kokeista tai kokotekstien aitoudesta.

## E11.5:n toteutus

\`src/klone/limbo_evidence_verification_queue.py\` rakentaa seuraavan
rajatun tutkimusjonon viidestä alkuperäisestä tiedostosta:

1. E11:n alkuperäinen omistajan täyttämä manifesti
2. E11.2:n alkuperäinen ehdotusraportti
3. E11.3:n omistajan kontekstiksi hyväksymä manifesti
4. E11.3:n ankkuroitu offline-tarkistusraportti
5. E11.4:n laaduntarkistusraportti

Kaikki tietojen ketjun osat **lasketaan uudelleen** julkisen
Memory Coren kanonisesta lähdeparista ennen tehtävänjakoa.
Ohjelma torjuu vaihdetun lainauksen, lähdetunnuksen, muokatun
omistajan hyväksynnän, väärän tutkimusparin ja virheellisen
raporttitarkisteen. Tähän ei tarvita verkkohakua eikä
muutoksia tietokantaan.

Jono erottelee E11.4:n luokat:
- \`attributed_research_claim_needs_primary_check\`:
  prioriteetti 1 – väitteen tarkastus alkuperäisestä tutkimuksesta
- \`unverified_context_needs_primary_check\`:
  prioriteetti 2 – varmistettava, onko teksti alkuperäistä vai referaattia
- \`publication_title_not_evidence\`,
  \`open_question_not_evidence\` ja \`editorial_caution_not_evidence\`:
  **sivuun siirrettyä metatietoa**, jota ei esitetä varsinaisena
  tutkimustuloksena.

Kumpaankin varmistettavaan tekstiin kohdistuu kaksi
**suunniteltua** Council72-tehtävää:
1. E11.2:ssa aihetta varten määritetty kanoninen neuvoston jäsen
   (esimerkiksi Marax 21, Botis 17 tai Andrealphus 65)
2. Alkuperäislähteen ja lainauksen erillinen provenance-tarkistus
   Council72:n kahdeksannen ringin ensimmäisessä tehtäväpaikassa.

Näin esimerkiksi 10 relevantin kontekstikatkelman tapauksessa
muodostuisi **20 avointa tarkistustehtävää**, ei yhtään
valmista tieteellistä arviointia.

Jokaiselle tehtävälle tulee konkretiaa:
lähteen alkuperäinen URL, lähdetunnus, lainaus SHA-256, tarkka
sijainti, vaaditut tutkimuksen menetelmien ja mittareiden tarkistukset,
mahdolliset numeeristen tulosten yksikkö-/baseline-tarkistukset
sekä kaksi erillistä keskeneräiseksi merkittyä neuvostorooleja.

### Puhelimen käyttöönotto

\`\`\`bash
cd ~/klone-arxiv-e1 &&
git fetch origin feat/limbo-external-intelligence-20261115 &&
git switch --detach FETCH_HEAD &&
bash scripts/klone-e11-5-phone.sh
\`\`\`

Skripti valitsee viimeisimmän E11.4:n laaduntarkistusraportin,
etsii sen SHA-256-tarkisteisiin täsmäävät E11.3:n
valinta- ja tarkistusraportit sekä E11.2:n alkuperäisen ehdotusraportin.
Sen jälkeen se ajaa kohdennetut testit ja tuottaa uuden
**vain paikalliseen yksityiseen hakemistoon**
tallennettavan JSON-jonon:

\`~/klone-var/e11/e11-5-tarkistusjono-YYYYMMDD-HHMMSS.json\`.

Skripti ei lataa julkaisuja internetistä, käynnistä palvelimia,
tee neuvostoäänestyksiä, kirjoita KLONE-päämuistiin eikä
muuta alkuperäisiä manifesti- tai auditointitiedostoja.

### Tieteelliset rajat

E11.5-raportissa \`source_material_authenticated=false\`,
\`verified_scientific_results=0\`,
\`completed_council_reviews=0\` ja
\`authority.memory_write=false\`.
Tehtävänjako on toistettavissa, mutta **ei itsessään
riippumatonta tutkimusta**.
Näitä aikaisemmin tekoälyn laatimia selostuksia ei saa
käyttää osoittamaan alkuperäisjulkaisun tarkkaa tulosta ilman
erillistä ensisijaisen lähdetekstin tarkistamista.

Seuraava vaihe olisi omistajan erikseen hyväksymä,
lisenssiehdot huomioiva autenttisen alkuperäisjulkaisun
hankinta ja vastaanottotarkistus. Silloin E11.5-jono voisi
siirtyä varsinaiseen tekstien, menetelmien, datan ja
toistettavuuden riippumattomaan arviointiin.
