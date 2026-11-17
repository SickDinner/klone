# KLONE Atlas E9 – jäljitettävät tutkimusparien lähdekortit

## Miksi E9 rakennettiin?

Todellinen Android/Termux E8.3-ajo 16.11.2026:

- \`feature_version=E8.3\`
- 148 julkista Memory Core -tutkimusviitettä
- 24 genetiikkahakuun sopivaa lähdettä, 124 muiden alojen lähdettä tutkittu
- seitsemän laatuseulan läpäissyttä, **vahvistamatonta** tieteidenvälistä sanastoyhteyttä
- \`writes_memory=False\`

Seuraavat **todelliset muistien parit** näkyivät E8.3:n raportissa:
- 26 / 118: \`gene\`, \`network\` (genetiikka / mieli & lääketiede)
- 26 / 128: \`expression\`, \`gene\` (genetiikka / mieli & lääketiede)
- 94 / 77: \`detection\`, \`virus\` (genetiikka / luonnontieteet)
- 26 / 24: \`graph\`, \`network\` (genetiikka / luonnontieteet)
- 26 / 57: \`learning\`, \`network\` (genetiikka / teknologia)
- 90 / 9 ja 90 / 58: \`agent\`, \`automating\` (genetiikka / teknologia)

Nämä muistien ID:t ovat **käyttäjän nykyisen päämuistin viitteitä**,
eivät pysyviä maailmanlaajuisia julkaisutunnisteita. E9 tarkistaa
ajon yhteydessä, että lähdepari on yhä nykyisten aktiivisten,
julkisten \`research-room\`-havaintojen joukossa sekä E8.3:n
laatuseulalla hyväksytty. Mikäli muisti tai suodatus muuttuu,
vanha pari voidaan hylätä eikä sitä esitetä vahvistettuna.

## E9.1 – saman julkaisun kaksoiskappaleet ja lähdetyypit

Androidin todellinen E9-ajo 17.11.2026 raportoi **7 muistitapahtumaparia**
mutta AgentSSL-esijulkaisu
`https://arxiv.org/abs/2611.17323v1` esiintyi kummassakin:
`90/9` ja `90/58`. Näin **vain 6 eri julkaisuparia**
on edustettuna esitetyn seitsemän muistitapahtumaparin joukossa.

E9.1 laskee julkaisuparin identiteetin **molempien alkuperäisten
HTTPS-julkaisuosoitteiden** perusteella, ei muistin tapahtumatunnuksesta
tai pelkästä otsikosta. Tunnettujen julkaisujen RSS-seurantaparametrit
(esim. `at_campaign`) poistetaan vertailusta. Erilaisia julkaisuosoitteita
ei yhdistetä pelkän samankaltaisen otsikon takia. Saman tutkimuksen
eri julkaisualustoille tallennetut versiot voivat silti jäädä
tunnistamatta ilman DOI- ja tekijätason lisätietoja.

Raportti säilyttää kaikki alkuperäiset muistiviitteet:
`raw_memory_pair_count`, `candidate_count`,
`duplicate_memory_pair_count`, `duplicate_memory_pairs`
ja kunkin pääkortin `duplicate_memory_event_pairs`.
Yksikään alkuperäinen muistitapahtuma ei poistu tietokannasta.

Jokainen lähde saa luokittelun `source_class`:
- `research_preprint`: arXiv-esijulkaisu, vertaisarviointi ei vahvistettu
- `indexed_research`: Europe PMC:n tutkimusviite, tutkimusmenetelmiä tai
  vertaisarviointia ei ole varmistettu
- `news_or_reference_feed`: RSS-uutis-/viitelähde, **ei suoraan toinen
  riippumaton tutkimus**

Lähdeparin `source_comparison_type` on joko
`research_metadata_pair` tai `mixed_news_or_reference_pair`.
Esimerkiksi genetiikan nanopore-virustutkimus / BBC:n
sinikielitautiuutinen on jälkimmäinen. Sitä ei pidä käsitellä
kahden tutkimuksen vahvistamana löydöksenä.

Päämuisti 8000, nykyiset 148 tutkimusmuistia ja E7-päiväkirja ovat
edelleen muuttumattomia. E9.1:n `/health`-versio auttaa päivittämään
vain localhost:8041-tutkimuslukijan.

## E9:n toteutus

\`src/klone/limbo_source_dossiers.py\`:

- lukee vain oikean, julkisen Memory Coren **nykyiset** tutkimusmuistot;
- palauttaa molempien julkaisujen alkuperäiset tallennetut
  otsikot, kuvaukset, lähteiden HTTPS-osoitteet, tapahtuma-ID:t,
  muistiversiot, tieteenalat, julkaisijaryhmät ja lähdetarkisteet;
- näyttää yhteiset termit ja molempien otsikoiden käsitteet;
- muodostaa erillisen listan jatkoselvityksistä: tutkimusasetelma,
  näytekoko ja populaatio, mittarit, mahdollinen yhteinen data,
  tekijät, preprint-kopiot, vaihtoehtoisten selitysten testit sekä
  riippumattoman toistotutkimuksen tarve;
- **ei väitä** lukeneensa julkaisuja kokonaan, tarkistaneensa
  menetelmiä, selvittäneensä riippumattomuutta tai todenneensa
  yhtäkään väitettä;
- ei käytä verkkopyyntöjä, kirjoita KLONE-muistiin tai luo
  E7-hypoteesipäiväkirjamerkintöjä.

E9:n dataa voi lukea sekä Atlas-työpöydästä portissa 8031 että
päämuistin erillisestä **vain luku** -työpöydästä portissa 8041.
Jokaisen ehdokasparin kohdalla on painike
**Avaa E9-lähdeparin tutkimuskortti**.

GET-rajapinnat:

\`\`\`text
http://127.0.0.1:8041/api/limbo-atlas/dossiers?q=genetiikka
http://127.0.0.1:8041/api/limbo-atlas/dossier?q=genetiikka&first_event_id=26&second_event_id=128
\`\`\`

Toiminta edellyttää, että mainittujen muistien versiot ovat yhä
voimassa ja että pari läpäisee nykyisen E8.3:n laatuseulan.

## Ota E9 käyttöön turvallisesti Termuxissa

\`\`\`bash
cd ~/klone-arxiv-e1 &&
git fetch origin feat/limbo-external-intelligence-20261115 &&
git switch --detach FETCH_HEAD &&
bash scripts/klone-atlas-e7-e8-phone.sh
\`\`\`

Skripti suorittaa E1–E9-tutkimustestit, päivittää 8031:n ja vain
8041:n tunnistetun tutkimuslukijan, luo erillisen E9-JSON-raportin
ja kopioi sen Androidin Lataukset-kansioon nimellä
\`KLONE-E9-lahdeparit.json\`. Se ei muuta
\`~/klone/data/klone_mission_control.db\`-tietokantaa,
pääpalvelinta 8000 tai E7:n hypoteesipäiväkirjaa.

Halutessasi yksittäisen lähdeparin raportin ilman palvelinten
käynnistämistä:

\`\`\`bash
cd ~/klone-arxiv-e1 || exit 1
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_source_dossiers \
  --klone-db "$HOME/klone/data/klone_mission_control.db" \
  --question "genetiikka" --pair 26 128 \
  --output "$HOME/klone-var/e9-gene-expression-review.json"
\`\`\`

**Raja:** Julkaisun otsikko ja lyhyt tallennettu kuvaus eivät riitä
todistamaan yhteistä tulosta, tutkimusmenetelmän yhteismitallisuutta
tai biologista mekanismia. Seuraava E10-askel on omistajan
hyväksymä, lähteisiin sidottu täystekstin tutkimusasetelma-analyysi,
jossa myös vastanäytön etsiminen ja lähdeaineiston kaksoiskäyttö
tarkistetaan. Sitä ei ole toteutettu tässä E9-versiossa.
