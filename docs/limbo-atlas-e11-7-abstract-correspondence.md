# KLONE Atlas E11.7 – arXiv-tiivistelmien vastaavuustarkastus ilman uutta verkkohakua

## Todellinen lähtötilanne (Android/Termux 17.11.2026)

E11.5: **56/56** testiä OK, 10 julkaisuista tarkistettavaa katkelmaa,
6 sivuun siirrettyä otsikkoa/kysymystä/varoitusta,
20 *suunniteltua mutta suorittamatonta* neuvostotehtävää.

E11.6: **60/60** testiä OK; käyttäjä hyväksyi arXiv Atom -haun kirjoittamalla
\`HYVAKSY ARXIV\`. Vastaanotettiin alkuperäisen
\`export.arxiv.org\`-metatietorajapinnan tiivistelmät kahdelle
versionumeroidulle julkaisulle:
- muisti-ID **26** → \`2611.13801v1\`
- muisti-ID **24** → \`2611.15598v1\`

Molempien otsikot täsmäsivät muistiviitteisiin. Käyttäjän todellinen raportti:

\`~/klone-var/e11/e11-6-arxiv-vastaukset-20261117-043326.json\`

Vastaanotetut tekstit ovat **julkaisujen tiivistelmiä, eivät kokotekstejä**.
Käyttäjän aikaisemmat A/B-tiedostot ovat tekoälyn laatimia
selostuksia eivätkä varmennettuja alkutekstejä.

## E11.7:n rajattu toiminto

\`src/klone/limbo_arxiv_abstract_compare.py\` vertaa E11.5:n
**10** avoimeksi merkittyä kontekstikatkelmaa vain saman
tutkimuksen alkuperäiseen arXiv Atom -tiivistelmään.

Se tarkistaa ensin seitsemän olemassa olevaa raporttia:

1. E11:n alkuperäinen käyttäjän täyttämä manifesti
2. E11.2:n tekstilainausten ehdotusraportti
3. E11.3:n erikseen hyväksytyt kontekstimerkinnät
4. E11.3:n tarkistettu evidenssiraportti
5. E11.4:n rakenteellinen laatuauditointi
6. E11.5:n järjestetty lähdetarkistusjono
7. E11.6:n *nimenomaisella luvalla* saatu arXiv Atom -metatietotosite

E11.2–E11.5 ketju lasketaan uudelleen alkuperäisestä julkisesta
Memory Core -lähdeparista. E11.6:n lähdetunnusten, version,
Atom-vastaustietueiden, artikkeliotsikoiden ja tiivistelmän SHA-256-tarkisteiden
on täsmättävä samaan nykyiseen kanoniseen lähdepariin.
Väärennettyä, vanhentunutta tai väärään artikkeliin yhdistettyä
raporttia ei voi käyttää läpäisemättä kaikkia tarkastuksia.

### Mahdolliset löydösluokat

- \`verbatim_in_arxiv_abstract_not_independent_confirmation\` –
  täsmällinen tekstijono löytyy versionumeroidun lähteen tiivistelmästä
- \`numbers_mentioned_in_abstract_claim_not_verified\` –
  kaikki katkelman numeeriset esiintymät löytyvät vastaavasti
  tiivistelmästä, mutta varsinainen väite on vielä tarkistamatta
- \`partial_numeric_overlap_requires_primary_check\` –
  osa numeroista esiintyy, osa ei
- \`partial_keyword_overlap_not_claim_verification\` –
  joitakin yksittäisiä ei-geneerisiä sanoja esiintyy
- \`no_match_in_abstract_full_text_check_required\` –
  osumaa ei ole rajatussa tiivistelmässä, joten tarvitaan kokoteksti

Osuma **ei ole näyttö syy-seuraussuhteesta, tutkimusmenetelmän
pätevyyydestä eikä riippumattomasta toisinnuksesta**.
Puuttuva osuma ei tarkoita, että tutkimus olisi väärässä:
tiivistelmä jättää tavallisesti menetelmien ja tulosten
yksityiskohtia pois. Suomenkielisen selostuksen ja englanninkielisen
tiivistelmän sanallinen osuma on lisäksi erityisen puutteellinen mittari.
Numeerisia arvoja verrataan vain ilmaisumuodoltaan sellaisinaan,
ei yksikkömuunnoksin tai semanttisin tulkinnoin.

### Termux – yksi komento, ei uutta verkkolupaa eikä verkkohakua

\`\`\`bash
cd ~/klone-arxiv-e1 &&
git fetch origin feat/limbo-external-intelligence-20261115 &&
git switch --detach FETCH_HEAD &&
bash scripts/klone-e11-7-phone.sh
\`\`\`

Skripti valitsee E11.5-jonon ja E11.6:n arXiv-tositteen,
etsii niihin oikeasti kuuluvat E11.4:n, E11.3:n ja E11.2:n
alkuperäiset tiedostot SHA-tarkisteiden perusteella ja käyttää
vanhaa \`~/klone-var/e11/e11-taytetty.json\`-manifestia.

Se ajaa kohdennetut testit ja muodostaa vain **uuden**
raportin:

\`~/klone-var/e11/e11-7-tiivistelmavertailu-YYYYMMDD-HHMMSS.json\`

E11.7 ei lataa mitään verkosta, käynnistä palvelimia uudelleen,
kirjoita muistiin tai tee neuvoston todellisia arviointeja.
Se tallentaa vain käyttäjän olemassa olevien tekstikatkelmien
ja arXiv Atom -tiivistelmien rajatun vastaavuustarkastuksen.

### Seuraava vaihe – E11.8

Ennen kuin KLONE väittää mitään varsinaisesta tutkimusnäytöstä,
sen pitää pystyä käsittelemään käyttöoikeuksien sallimissa rajoissa
alkuperäisiä kokotekstejä, vertaamaan mittareita, otoksia ja
menetelmiä sekä varmistamaan riippumattomat toistot.
E11.7 on täsmällinen lähtökohta tähän työhön, ei vielä
tieteellinen johtopäätös.
