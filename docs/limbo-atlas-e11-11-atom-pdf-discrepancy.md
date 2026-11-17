# KLONE E11.11 – arXiv-tiivistelmän ja paikallisen PDF-tekstin erot

## Todennettu lähtötilanne

Android/Termux E11.10 (17.11.2026):
- 10 paikallista tutkimuskorttia
- 1 sanatarkka PDF-sivuosuma (A, sivu 1)
- 2 korttia, joissa ainoastaan lukuarvo/yksikköesiintymiä
- 7 korttia ilman paikannettua osumaa
- 0 uutta typografisella normalisoinnilla löytynyttä kokonaisosumaa
- 0 hyväksyttyä tieteellistä väitettä, neuvostoarviota, verkkopyyntöä tai muistin kirjoitusta
- A / arXiv \`2611.13801v1\` / 11 PDF-sivua
- B / arXiv \`2611.15598v1\` / 23 PDF-sivua

Ongelma: E11.7 arXiv Atom -tiivistelmävertailusta oli kaksi sanatarkkaa
osumaa, mutta E11.10:n PDF-sivuista poimitusta tekstistä vain yksi
niistä säilyi. E11.10 ei palauttanut toista rivitavutuksen/Unicode-
normalisoinnin avulla.

Tämä ero ei yksin tarkoita PDF:n virheellisyyttä, muuttunutta
tutkimustulosta tai tieteellistä ristiriitaa. Atom-tiivistelmä,
PDF:n tekstinpoiminta ja omistajan aiempi selostus ovat **kolme eri
tekstipintaa**.

## E11.11:n rajattu toteutus

\`src/klone/limbo_abstract_pdf_diagnostics.py\` tarkistaa uudelleen
E11.10:n lähdeketjun sekä paikallisten PDF:ien SHA-256-tarkisteet,
tekstinpoiminnan yhdenmukaisuuden E11.9:ään ja erillisen E11.6-
tiivistelmätositteen identiteetit.

Joka kortille:
- onko alkuperäinen paikallinen lainaus sanatarkasti arXiv Atom -tiivistelmässä
- onko se löydetty PDF-sivutekstistä täsmällisesti tai typografisesti normalisoituna
- ovatko sivulla vain samat numerot ja yksiköt (ei merkityksen varmennus)
- missä sivuilla mahdolliset kirjain/käsite-osumat ovat, **ei evidenssiväitteinä**
- erillinen diagnoosiluokka ja tarkistamattomien tulkintojen kysymyslista

Lisäksi lähteittäin selvitetään, esiintyykö koko arXiv Atom
-tiivistelmän teksti yhtenäisenä normalisoituna tekstinä jollakin PDF-sivulla.
Jos ei, tulos ei ole todiste paperin eri versiosta tai tieteellisestä ristiriidasta.

Toteutus ei käännä kieliä eikä tee LLM-pohjaista semanttista
päättelyä. Esimerkiksi AI:n kirjoittama suomenkielinen selostus
ei voi tulla automaattisesti tulkituksi englanninkielisen
alkuperäislähteen vahvistamaksi väitteeksi.

Arviointipöytäkirja on erillinen uusi JSON, ei korvaa E11.1–E11.10
tiedostoja. Ei uusia verkkopyyntöjä, Memory Core -kirjoituksia,
Council72-ajettujen arvioiden merkintöjä tai tieteellisen
varmennuksen lupauksia.

## Termux, kun aiemmat PDF:t ovat paikallisesti valmiina

\`\`\`bash
cd ~/klone-arxiv-e1 || exit 1
git fetch origin feat/limbo-e11-11-abstract-pdf-diagnostics-20261117
git switch --detach FETCH_HEAD

export KLONE_E11_10_PDF_SHA_A=816ae5ead2636238e76bb5a8ba5bac98af3c664f5367f4c22c5aa4b710ceb80f
export KLONE_E11_10_PDF_SHA_B=93e0863d9f56e6e1201ae4b17b1317018c5bda5a27dc4b7086f5bfc94cd2e7ec
export KLONE_E11_11_OWNER_APPROVAL=HYVAKSY_ABSTRAKTI_PDF

bash scripts/klone-e11-11-phone.sh \
  ~/klone-var/e11/2611.13801v1.pdf \
  ~/klone-var/e11/2611.15598v1.pdf
\`\`\`

Varmista ennen ajoa, että PDF:ien omistamasi paikalliskopiot edelleen
vastaavat aiemmin mitattuja tarkisteita. Hyväksyntä koskee vain
paikallista, offline-tilassa tehtävää alkuperäis-/PDF-tekstien
vertailua.

## E11.12:n perusteltu jatko

Vasta E11.11:n diagnoosin jälkeen voidaan suunnitella aidosti
asiayhteyden tarkistava tutkimusneuvoston tarkastus:
sivulla oleva väite, todellinen metriikka, aineisto,
vertailutaso ja epävarmuus sekä erikseen ihmisen hyväksymä tulkinta.
Council72-toimijat eivät automaattisesti saa kirjoitusoikeutta
päämuistiin eivätkä oikeutta julistaa väitettä todeksi.
