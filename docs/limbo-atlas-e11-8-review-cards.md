# KLONE E11.8 – arXiv-tiivistelmien lähdekohtaiset tarkistuskortit

## Miksi E11.8 tarvitaan

Vahvistettu Android E11.7 -ajo (17.11.2026, julkaisupari 26–24) oli:
- 64/64 kohdennettua tutkimustestiä OK
- 10 selostuksesta nostettua tarkistettavaa katkelmaa
- 2 arXiv-tiivistelmään **sanatarkasti** osuvaa katkelmaa
- 1 osittainen numerovastaavuus
- 1 osittainen sanasto-osuma
- 6 katkelmaa, joille ei löytynyt vastaavuutta tiivistelmästä
- 0 tieteellisesti vahvistettua tutkimusväitettä
- 0 kokotekstiä, neuvostoarviota tai päämuistikirjoitusta

Oikea E11.7-tiedosto puhelimessa:

\`~/klone-var/e11/e11-7-tiivistelmavertailu-20261117-044328.json\`

## Mitä E11.8 tekee

\`src/klone/limbo_evidence_cards.py\` tarkistaa koko
**kahdeksan tiedoston** ketjun:

1. täytetty E11-lähdemanifesti
2. E11.2-evidenssiehdotukset
3. E11.3-omistajan kontekstivalinta
4. E11.3-ankkuroitujen lainausten tarkistus
5. E11.4-laatuauditointi
6. E11.5-alkuperäistutkimuksen tarkistusjono
7. E11.6:n omistajan nimenomaisella verkkoluvalla arXivista
   vastaanottama tiivistelmätosite
8. E11.7:n tiivistelmävastaavuusraportti

E11.7 lasketaan ohjelmallisesti uudelleen näistä lähteistä
kanonisen julkisen Memory Coren tilaa vasten.
Muutetut, vanhentuneet, väärään julkaisuun kuuluvat
ja keksityt raportit hylätään.

### Tarkistuskortin kentät

Kunkin tutkimuskatkelman kortissa on:
- lähteen muistintunnus ja arXiv-julkaisuversio
- paikallinen tekstikatkelma ja tarkiste
- arXiv-tiivistelmän vastaanotetun tekstin SHA-256
- E11.7:n sanallinen/numeerinen osumaluokka
- tarkka alku- ja loppumerkkisijainti, jos sama katkelma
  todella esiintyy sanatarkasti alkuperäisessä tiivistelmässä
- tiukasti **lukuarvon + yksikön** mukaan tunnistetut määrät
- saman arvon ja yksikön esiintyminen tiivistelmässä
- lähdetutkimuksesta ja menetelmistä jäljellä olevat kysymykset
- E11.5:n kanoninen alan tarkistaja sekä erillinen
  alkuperäislähteen tarkistaja – kummatkin *pending*, eivät suorittaneita

Lukuvertailu erottaa esimerkiksi
\`13,7 prosentin\` ja \`13.7%\` (sama yksikkö)
sekä \`31 prosenttiyksikköä\` ja \`31%\` (eri yksikkö).
\`0,997 kelvinin\` ja \`0.997 K\` kuuluvat samaan
lämpötilayksikköluokkaan. Pieni \`k\` naapuriverkon
parametrissa ei tarkoita automaattisesti kelviniä.

Tämäkään ei tarkista numeerisen väitteen **kontekstia,
mittarin suuntaa, aineistoa, baselinen oikeellisuutta tai
tilastollista epävarmuutta**. Sama luku voi esiintyä kahdessa
aivan eri merkityksessä. Osumasta ei voi päätellä
riippumatonta tieteellistä vahvistusta.

### Puhelimella yhdellä komennolla

\`\`\`bash
cd ~/klone-arxiv-e1 &&
git fetch origin feat/limbo-external-intelligence-20261115 &&
git switch --detach FETCH_HEAD &&
bash scripts/klone-e11-8-phone.sh
\`\`\`

Ohjelma etsii viimeisimmän E11.7-raportin ja muut oikeat
asiakirjat toisiinsa kytkettyjen SHA-256-tarkisteiden
perusteella. Se testaa ensin paikalliset tutkimusregressiot,
sitten luo **uuden**, alkuperäisiä raportteja korvaamattoman
JSON-tarkistuskortiston:

\`~/klone-var/e11/e11-8-tarkistuskortit-YYYYMMDD-HHMMSS.json\`

Ohjelma ei hae verkosta uutta tietoa, kirjaa väitteitä
päämuistiin, käynnistä KLONE-palvelimia uudelleen
eikä väitä suorittaneensa Council72-neuvoston arvioita.

### E11.9:n järkevä tavoite

Alkuperäisten, versionumeroon sidottujen tutkimusten
kokotekstien tarkastelu **erillisellä käyttäjän luvalla**
ja sopivien käyttöoikeus-/julkaisuehtojen mukaisesti.
Vasta varsinainen sisältö, menetelmät, taulukot,
aineistot ja riippumattomat toisinnukset voivat viedä
KLONEa tieteellisen näytön arviointiin.

**Tarkiste ei ole digitaalisesti allekirjoitettu
julkaisijatodistus**, vaan paikallisten aineistokopioiden
jäljitettävyystyökalu. Samasta tiivistelmästä saatu
tekstiosuma ei yksin todista väitteen tieteellistä pätevyyttä.
