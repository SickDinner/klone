# KLONE E11.10 – PDF-sivujen forensinen paikannus (offline)

## Lähtötulos Androidissa 17.11.2026

E11.9:n todellisessa paikallisessa tekstivertailussa 10 tarkistuskorttia:
- **1** yhtenäinen tekstiosuma
- **2** pelkkiä saman arvoisia ja saman yksikköisiä numeroesiintymiä
- **7** ilman löydettyä tekstiosumaa
- **0** tieteellisesti vahvistettua väitettä, **0** muistin kirjoitusta, **0** neuvostoarviota

E11.7:n tiivistelmävertailussa oli **2** sanatarkkaa osumaa.
Erityisesti B:n arXiv-version \`2611.15598v1\` tiivistelmän
sanatarkka katkelma ei löytynyt E11.9:n PDF:stä erotetusta tekstistä.
Tämä **ei** ole osoitus tieteellisestä ristiriidasta.

## Mitä E11.10 tekee

\`src/klone/limbo_pdf_page_locator.py\`:
1. Toistaa E11.9:n kahdeksan alkuperäisen raportin ja nykyisen Memory Coren kautta, hylkää muuttuneen tai vanhentuneen ketjun.
2. Vastaanottaa **vain kahden käyttäjän itse hankkiman paikallisen PDF:n** polut sekä ennen ajoa ilmoitetut SHA-256-tarkisteet.
3. Tarkistaa PDF-rakenteen, koon (enintään 15 Mt), sivumäärän (enintään 160) sekä irrottaa tekstin turvallisesti rajatuilla \`pdfinfo\`- ja \`pdftotext\`-komennoilla ilman shelliä, aikakatkaisulla.
4. Vahvistaa, että kummankin PDF:n *kokonaisuudessaan uudelleen irrotetun tekstin* tarkiste vastaa täsmälleen E11.9-raportin aiempaa tekstin SHA-256-tarkistetta.
5. Paikantaa kymmenen katkelman mahdolliset sanalliset osumat, kevyet NFKC/ligatuuri- ja rivitavutusnormalisoidut osumat sekä mittayksiköiden mukaiset numeroesiintymät **PDF-sivuille**.
6. Näyttää lisäksi vain navigointia varten kolme ehdotettua sivua yleisen sanasto-osuman perusteella.

Tulos: \`~/klone-var/e11/e11-10-pdf-sivupaikannus-YYYYMMDD-HHMMSS.json\`.

Tämä on omistajan toimittaman PDF:n **paikallinen sivu- ja tekstivastaavuustarkistus**.
SHA-256 todistaa, että laskettu tarkiste on sama kuin käyttäjän
ennalta ilmoittama tarkiste – **ei** todista arXivin julkaisuautentikointia.
PDF-tekstin sijainti tai numerolöytö ei varmista tieteellistä väitettä.

Ohjelma ei lataa verkosta mitään, käynnistä palvelimia, muokkaa
Memory Corea, suorita Council72-agentteja tai anna neuvostoääniä.

## Android/Termux

Oletus: E11.9 on onnistunut; kansiossa \`~/klone-var/e11\`
ovat \`2611.13801v1.pdf\`, \`2611.15598v1.pdf\`, samanversion
\`.txt\`-kopiot sekä raporttiketju.

\`\`\`bash
cd ~/klone-arxiv-e1 || exit 1
git fetch origin feat/limbo-e11-10-pdf-pages-20261117
git switch --detach FETCH_HEAD

# Tarkisteet on luettu PDF-latauksen jälkeen Termuxin sha256sum-tulosteesta.
# Käytä näitä vain, jos nykyisten PDF:ien tarkisteet vastaavat.
export KLONE_E11_10_PDF_SHA_A=816ae5ead2636238e76bb5a8ba5bac98af3c664f5367f4c22c5aa4b710ceb80f
export KLONE_E11_10_PDF_SHA_B=93e0863d9f56e6e1201ae4b17b1317018c5bda5a27dc4b7086f5bfc94cd2e7ec

# Omistajan nimenomainen lupa tarkastaa jo paikalliset PDF-tiedostot.
export KLONE_E11_10_OWNER_APPROVAL=HYVAKSY_PDF_SIVUT

bash scripts/klone-e11-10-phone.sh \
  ~/klone-var/e11/2611.13801v1.pdf \
  ~/klone-var/e11/2611.15598v1.pdf
\`\`\`

Tulosteen yhteenvedon saa avaamalla raportin \`cards\`-listan
\`page_locator_status\`-kenttien jakauman sekä
\`normalized_page_spans\`- ja \`literal_page_spans\`-sivunumerot.

## E11.11:n avoin kysymys

Tämän työkalun normalisointi ei ymmärrä suomen- ja englanninkielistä
samaa merkitystä, tutkimuksen muuttujia tai mittarien kontekstia.
E11.11:n tavoite olisi **asiayhteyteen perustuva ihmisen tarkistama
tutkimusväitteiden arvio**, jossa lähteen sivu-, taulukko- ja
viiteankkurit liittyvät PDF:n autentikoituun versioon ja mahdollisiin
korjaus-/toisinnusjulkaisuihin.
