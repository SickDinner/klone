# KLONE E11.4 – tutkimusmerkintöjen laaduntarkastus, ei näennäisiä tuloksia

## Todellinen syöte Androidissa 17.11.2026

E11.2 palautti oikeassa Termux-ajossa julkaisuparille 26 ja 24
**16 lainaus-/kontekstiehdokasta**, joille ehdotettiin
Council72-jäseniä **Marax (21), Botis (17) ja Andrealphus (65)**.
Kaikki olivat tilaansa "keskeneräinen", eikä yksikään saanut
tieteellisen näytön arvoa.

E11.3:ssa omistaja vahvisti kontekstimerkinnät kirjoittamalla
\`HYVAKSY KONTEKSTI\`. Ajossa syntyivät:

- \`~/klone-var/e11/e11-3-konteksti-20261117-040739.json\`
- \`~/klone-var/e11/e11-3-tarkistus-20261117-040739.json\`

E11:n vanha, täytetty manifesti säilyy:
\`~/klone-var/e11/e11-taytetty.json\`.
E11.2:n lähtöraportti oli
\`~/klone-var/e11/e11-2-ehdokkaat-20261117-040627.json\`.

**Näyttöstatus on edelleen \`scientific_truth_verified=false\`:**
kaksi paikallista tekstiä ovat tekoälyn laatimia selostuksia,
joista joukossa on väitetysti sanasta sanaan otettuja
katkelmia, mutta niitä ei ole tässä putkessa verrattu
julkaisijan alkuperäisiin kokoteksteihin.

## E11.4:n uusi toteutus

\`src/klone/limbo_evidence_quality.py\` on rakenteellinen
laaduntarkastus, ei tutkimuksen validointimoottori. Se lukee
neljä rajattua, nykyisen Memory Core -parin kanssa
verrattavaa **paikallista** JSON-tiedostoa:

1. alkuperäinen, hyväksytysti täytetty E11-manifesti,
2. alkuperäinen E11.2:n ehdotusraportti,
3. omistajan E11.3:ssa kontekstiksi hyväksymä manifesti,
4. E11.3:n varsinainen ankkuroitu E11-tarkistusraportti.

KLONE ajaa tämän ketjun ohjelmallisesti uudelleen. Se tarkistaa,
että kanoniset E9.1-lähteet, muistitarkisteet, E11.2-ehdokkaat,
lähde- ja lainausankkurit, omistajan valinnat ja lopullisen
tarkistusraportin rakenne **täsmäävät alkuperäisiin
syöttötietoihin**. Väärennetty ehdotus, toisesta erästä
otettu tiedosto, väärä lähde-ID, keinotekoinen sitaatti tai
myöhemmin muokattu hyväksyntä hylätään.

Sen jälkeen lainauksille asetetaan **heuristiset**
laatutarkastusluokat:

- \`publication_title_not_evidence\` – pelkkä otsikko,
  ei menetelmä- eikä tulosväite
- \`open_question_not_evidence\` – tutkittavaksi jätetty kysymys
- \`editorial_caution_not_evidence\` – selostuksen oma
  varoitus tai arviointikäytännön rajaus
- \`attributed_research_claim_needs_primary_check\` –
  esimerkiksi "Tekijöiden mukaan ..." tai "Tiivistelmän mukaan ..."
- \`unverified_context_needs_primary_check\` – muu paikallinen
  kontekstikatkelma, jonka aitous ja tulkinta ovat avoimia

Tämä ei ole täydellinen semanttinen analyysi. Myös
tunnistus voi erehtyä; luokka ei nosta lainauksen
tieteellistä näyttöarvoa. Kaikki luokitukset tallennetaan
pelkiksi **laaduntarkastusehdotuksiksi**.

### Käyttöönotto yhdellä komennolla

\`\`\`bash
cd ~/klone-arxiv-e1 &&
git fetch origin feat/limbo-external-intelligence-20261115 &&
git switch --detach FETCH_HEAD &&
bash scripts/klone-e11-4-phone.sh
\`\`\`

Skripti etsii viimeisimmän keskenään täsmäävän
E11.3-hyväksyntä- ja tarkistusraportin,
sekä sen alkuperäiseen hyväksyntään kuuluvan
E11.2-ehdotusraportin tarkisteen perusteella.
Se ajaa ensin kohdennetun testipaketin ja luo
**vain yhden uuden** yksityisen raportin polkuun:

\`~/klone-var/e11/e11-4-laatuauditointi-YYYYMMDD-HHMMSS.json\`

Uusi raportti näyttää laaduntarkastusluokkien määrät,
lainauskohtaiset alkuperät, SHA-256-tarkisteet ja
tarkistamatta olevat seuraavat toimet.

### Rajat ja seuraava merkityksellinen askel

- Ei päämuistiin kirjoittamista, palvelinten
  uudelleenkäynnistystä tai verkkohakuja.
- Ei E7-hypoteesipäiväkirjan muutoksia eikä neuvostoääniä.
- Ei väitettyä riippumatonta tekstintarkistusta,
  autenttista alkuperäisjulkaisun kokotekstiä tai
  varmistettua tieteellistä tulosta.
- E11.4 on ennen kaikkea **laadunparannus 16 jo
  hyväksyttyyn kontekstimerkintään**.

Seuraavaksi järkevin kehitys on omistajan luvalla
haettavan autenttisen arXiv-/Europe PMC -tekstin
versio- ja lisenssikohtainen tarkistus. Vasta sen jälkeen
voidaan verrata varsinaisia tutkimusmenetelmiä
ja niiden toistettavia tuloksia ilman
pelkkää otsikko- ja selostusperusteista päättelyä.
