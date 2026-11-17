# Council72 Intelligence Bridge v1 — oikeat GPT-analyysit, 72 roolia

## Miksi tämä tehdään

KLONEn E11.11 päättyi 17.11.2026 Androidissa onnistuneesti:
10 todellista korttia, 1 Atom- ja PDF-tekstivastaavuus, 1 pelkkä
Atom-vastaavuus, 2 numero- ja yksikkövastaavuutta sekä 6 korttia,
joille tekstivastaavuutta ei löydetty. Näitä tuloksia ei pidä
esittää tutkimuksen vahvistamisena.

E11.1–E11.11:n offline-tarkisteketju toimii nyt lähdepakettina.
Se **ei** muodosta 72 kielimallin tutkija-arviota. Tämän v1-bridge
on ensimmäinen aidon kielimallipäättelyn kokeilu:
- kahdeksan oikeaa kielimallikutsua, yksi per rinki 1–8
- jokaisessa rinkivastauksessa kahdeksan nimettyä jäsenarviota (64 roolia)
- yhdeksäs kielimallikutsu kahdeksan perustajan (rinki 9) synteesille
- täsmälleen yhdeksän API-pyyntöä onnistuneessa live-ajossa
- **ei** 72 erillistä malliprosessia; **ei** autonomisia agenttisuorituksia

Jokaisen jäsenen nimi, vastuu ja ID tulevat KLONEn varsinaisesta
\`council72.catalog()\`-luettelosta. Rinkien "tunteet" ja äänet jäävät
erillisiksi nykyisiksi sääntöpohjaisiksi simulaatioiksi: mallin teksti
ei saa tehdä sitovia äänestyksiä eikä muuttaa välittäjäainearvoja.

## Turvallisuus ja tietosuoja

Oletus on **offline-preview**, jossa mitään ei lähetetä verkkoon,
mallia ei kutsuta eikä API-avainta tarvita.

Live edellyttää erikseen
1. omistajan vahvistusta, että **jokainen** E11.11:n
   \`quote_sample_for_owner_review\` -katkelma ja tutkimuskysymys
   voidaan lähettää ulkoiseen OpenAI API:in
2. ympäristömuuttujaa \`OPENAI_API_KEY\` — API-avainta ei koskaan
   sijoiteta repositorioon, viesteihin, URL:iin tai lokiin
3. \`KLONE_COUNCIL72_CONFIRM_PUBLIC=VAHVISTAN_JULKISUUDEN\`
4. \`KLONE_COUNCIL72_API_APPROVAL=HYVAKSY_9_GPT_KUTSUA\`
5. erillistä \`live\`-käyttötilaa

E11.11:n tietueista lähetetään vain korkeintaan 20 kappaletta
enintään 240 merkin lyhyitä katkelmia, arXiv-versio,
SHA-tarkiste, lähdekortin ID ja aiemman eroluokan tiedot. Täysiä
PDF-tiedostoja, paikallisen muistin raakadataa, salasanoja,
yksityisiä terveys- tai geenitietoja ei lähetetä.

Teksti on epäluotettavaa lähdedataa (prompt injection):
sen sisältämiä toimintaohjeita ei noudateta. Mallilla ei ole
tool-calleja, nettihakua, shelliä, tiedostokirjoituksia
tai mahdollisuutta suorittaa Council72:n viestijonoa.
Responses API kutsutaan kiinteän HTTPS-osoitteen kautta;
\`tools=[]\`, \`store=false\`, rajoitetut tokenit, ei uudelleenyrityksiä.
\`store=false\` ei ole lupaus OpenAI:n kaikista säilytysajoista;
katso palveluntarjoajan tietojen käsittelyehdot.

Laskutus on OpenAI API -laskutusta, joka on erillinen ChatGPT-tilauksesta.
Valittu malli oletuksena \`gpt-6-luna\`; muut sallitut mallivalinnat
\`gpt-6.1-sol\` ja \`gpt-6-astra\`. Tarkista hinnat
<https://platform.openai.com/pricing/>. Yksi epäonnistunut live-ajo
voi maksaa jo tehtyjen API-kutsujen verran; v1 ei tallenna kesken
jääneitä suorituksia jatkamista varten. Uudelleenajo voi veloittaa uudestaan.

Mallin lähdeviitteet tarkistetaan paikallisten 10 lähdekortin ID:itä
vasten; keksityt ID:t, jäsenet, perustajat tai liian pitkät vastaukset
estävät lopullisen raportin. Tämä ei varmista väitteiden semanttista
oikeellisuutta eikä alkuperäis-PDF:n julkaisija-autenttisuutta.
Hallintaraporttiin merkitään aina \`owner_review_required\` ja
\`scientific_truth_verified=false\`.

## Termux — tarkka käyttö

Käytä viimeisintä E11.11-raporttiasi. Tätä tehtävää varten mitään
uutta PDF:ää ei haeta eikä paketteja tarvitse asentaa (Python 3.13
stdlib). Koodi ei muuta paikallisia KLONE-palvelimia eikä päämuistia.

\`\`\`bash
cd ~/klone-arxiv-e1 || exit 1
git fetch origin feat/council72-intelligence-bridge-v1-20261117 || exit 1
git switch --detach FETCH_HEAD || exit 1

# Ensiksi 10 testiä ja täysin offline-esikatselu:
bash scripts/klone-council72-intelligence-phone.sh preview
\`\`\`

Preview kirjoittaa \`council72-intelligence-preview-*.json\`-raportin.
Tarkista sen \`public_evidence_preview\`-kentän katkelmat.
Esikatselussa on \`planned_api_requests=9\`, mutta
\`model_api_requests_performed=0\`.

**Älä tee seuraavia vaiheita, ellei kysymys ja katkelmat ole
todella julkisia ja hyväksytty OpenAI API -palveluun lähetettäviksi.**
Näitä ei tarvitse tehdä turvallisen offline-testin onnistumiseksi.

Luo API-avain omalla OpenAI API -tilillä:
<https://platform.openai.com/api-keys/>.

Syötä avain vain puhelimen Termuxiin niin, ettei se päädy
komentohistoriaan (älä liitä avainta ChatGPT:hen tai GitHubiin):

\`\`\`bash
read -r -s -p 'OPENAI_API_KEY: ' OPENAI_API_KEY
printf '\n'
export OPENAI_API_KEY

# VAIN jos olet tarkistanut julkisuuden ja hyväksyt yhdeksän maksullista kutsua:
export KLONE_COUNCIL72_CONFIRM_PUBLIC=VAHVISTAN_JULKISUUDEN
export KLONE_COUNCIL72_API_APPROVAL=HYVAKSY_9_GPT_KUTSUA

bash scripts/klone-council72-intelligence-phone.sh live
\`\`\`

Vaihda tarvittaessa tutkimuskysymys:

\`\`\`bash
bash scripts/klone-council72-intelligence-phone.sh preview \
  'Mikä on molempien tutkimusten keskeinen avoin todentamiskysymys?'
\`\`\`

Live-tuloksen \`ring_calls\` sisältää kahdeksan erillistä
mallivastausta, joissa jokaisessa on kahdeksan
\`seat_assessments\`-kohtaa. \`founder_synthesis\` sisältää
kahdeksan perustajan ehdotetut kannat ja jatkokokeet.
Näitä ei saa sekoittaa aiempaan deterministiseen
\`council72.deliberate()\`-äänestykseen.

## Mikä on valmis ja mikä vielä ei

Tämä PR toteuttaa API-adapterin, roolitetut mallikutsut,
jäsenten ID- ja lähdeviitevalidoinnin, offline-esikatselun,
jäljitettävät tulos-/kutsutiivisteet, kulutuksen
token-laskurit ja eksplisiittisen käytön eston oletustilassa.
V1 sisältää myös 10 verkottomasti mockattua regressiotestiä.

PR ei sisällä piilotettuja API-avaimia, live-ajoa, avointa
hakuagenttia, agenttien toimivaltuutta tai Memory Core -muutoksia.

Hyväksymiskriteeri: omistaja ajaa previewn Androidissa ja vahvistaa
raportin, sitten (vain erillisellä suostumuksella) live-ajon,
joka palauttaa 8×8 roolikohtaiset arviot sekä kahdeksan
perustajan synteesin; lähdekorttien ID:t ovat oikeita,
ulkoisia toimia ja muistikirjoituksia ei ole, eikä
tieteellistä totuusstatusta koroteta.

## Kehitysjono, kun v1:n live-ajo on onnistunut

Seuraava tarkoituksenmukainen vaihe ei ole uusi E11-mikroauditointi,
vaan malliarvioiden laatukoe:

- sokkotestaus: verrataan tavallista yhden mallin vastausta
  8+1-neuvoston vastaukseen samoilla tutkimuskysymyksillä
- mitataan löydettyjen metodisten puutteiden määrä ja
  virheellisten lähdeviitteiden määrä, ei "tietoisuuden tasoa"
- kahden perustajan erimielisyys jää näkyväksi eikä katoa
  synteesin ansiosta
- vasta sitten itse toimivien oikeusrajattujen agenttien
  työkalukäyttö Hypervisorin valvonnassa, omistajan luvalla

Tämä pitää kehityksen hyödyssä eikä kasvata turhia
numeerisia vaiheita.
