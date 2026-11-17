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

## 17.11.2026: ensimmäinen oikea live-ajokoe ja korjaus

Androidin ensimmäinen live-ajo pysähtyi ensimmäiseen mallivastaukseen
\`model response incomplete or failed\`. Varsinainen yhdeksän kutsun
neuvostoajo ei valmistunut. Vanha ohjelma ei kirjannut vastauksen
\`status\`-, \`incomplete_details.reason\`- tai tokeninkäyttötietoja,
joten tarkka syy jäi vahvistamatta.

Todennäköinen mahdollinen selitys on liian pieni
\`max_output_tokens=1700\` kahdeksalle rakenteiselle jäsenarviolle,
kun oletusarvoinen päättelytila voi käyttää osan tokenbudjetista.
**Tätä ei pidä esittää varmistettuna ilman API:n todellista metadataa.**

Korjaus:
- \`gpt-6-luna\`: \`reasoning.effort=none\`, koska tehtävä on
  rajattu JSON-muotoisten jäsenhavaintojen generointiin.
- \`gpt-6.1-sol\` ja \`gpt-6-astra\`: \`reasoning.effort=low\`.
- \`max_output_tokens=3400\` rinkikutsuille ja perustajasynteesille.
- Jos Responses API palauttaa kesken jääneen vastauksen,
  ohjelma tulostaa vain sallitut metatiedot:
  \`status\`, \`reason\`, rajatun virhekoodin,
  \`output_tokens\` sekä \`reasoning_tokens\`.
  Raakavastausta, API-avainta ja tutkimuskatkelmia ei tulosteta.
- **Yhden kutsun probe:** erillinen hyväksyntä ja vain rinki 1
  (kahdeksan roolia). Ei automaattisia uudelleenyrityksiä eikä
  loppujen rinkien tai perustajien kutsua.
- Vanhoja E11.11-raportteja ja päämuistia ei muuteta.

Aiempi epäonnistunut API-pyyntö voi näkyä laskutuksessa,
vaikka raporttia ei syntynyt. Älä käynnistä
yhdeksän kutsun live-ajoa uudelleen ennen yhden kutsun
probe-kokeen onnistumista.

### Suositeltu Android-järjestys

1. Päivitä haara, suorita täysin maksuton preview.
2. Tarkista hyväksyttävä julkinen sisältö.
3. Hyväksy erikseen **yksi maksullinen koekutsu** ja aja probe.
4. Vasta toimivan probe-raportin jälkeen harkitse täyden
   yhdeksän kutsun live-ajoa erillisellä hyväksynnällä.

\`\`\`bash
cd ~/klone-arxiv-e1 || exit 1
git fetch origin feat/council72-intelligence-bridge-v1-20261117
git switch --detach FETCH_HEAD
bash scripts/klone-council72-intelligence-phone.sh preview

# Vain uuden nimenomaisen yhden maksullisen API-kutsun hyväksynnän jälkeen:
read -r -s -p 'OPENAI_API_KEY: ' OPENAI_API_KEY
printf '\n'
export OPENAI_API_KEY
export KLONE_COUNCIL72_CONFIRM_PUBLIC=VAHVISTAN_JULKISUUDEN
export KLONE_COUNCIL72_PROBE_APPROVAL=HYVAKSY_1_GPT_KUTSU
bash scripts/klone-council72-intelligence-phone.sh probe
unset OPENAI_API_KEY KLONE_COUNCIL72_PROBE_APPROVAL KLONE_COUNCIL72_CONFIRM_PUBLIC
\`\`\`

Jos probe onnistuu, raporttiin tulee
\`mode=api_one_ring_probe_completed\`,
\`model_api_requests_performed=1\`, ja vain ensimmäisen
ringin kahdeksan jäsenen arvio. Se ei valtuuta täyttä ajoa.

## Android 17.11.2026: ringin 2 muototarkistus ja maksullisen työn jatkaminen

Seuraavassa Android-kokeessa yksi ringin 1 GPT-analyysi valmistui,
mutta rinki 2 pysähtyi virheeseen \`invalid seat statement\`.
Vanha tarkistin edellytti jokaiselta kahdeksalta jäseneltä
enintään 300 merkin \`observation\`- ja \`challenge\`-lausuntoa.
Tiedämme vain, että jokin kenttä ei täyttänyt tarkistusta;
emme tiedä alkuperäisen, hylätyn vastauksen pituutta tai sisältöä.

Tässä versiossa:
- Lausunnon sallittu maksimipituus nostetaan 900 merkkiin.
  Tyhjä, vääräntyyppinen tai tätä pidempi teksti hylätään edelleen.
- Virhe ilmoittaa turvallisesti \`member_id\`-, \`field\`- ja
  \`chars\`-tiedot, ei yksityisiä tekstikatkelmia.
- Jokainen API:lta vastaanotettu vastaus tallentuu
  \`ring-XX-received-unverified.json\`-tiedostoon ennen validointia,
  \`ring-XX-accepted.json\` vasta validoinnin jälkeen.
- Perustajien yhdeksäs vastaus tallennetaan samalla tavalla.
- Paikallisia vastauksia luetaan vain, jos tietueen SHA-tarkiste,
  kysymys, malli, lähdeketju, luettelo, täsmällinen
  rinkikohtainen pyyntö ja rooli-/lähde-ID:t täsmäävät.
- Virheellistä vastaanotettua vastausta ei tilata automaattisesti
  uudelleen. Se jää paikalliseksi, ei-hyväksytyksi
  tietueeksi, jota voidaan tutkia ja kelpuuttaa vain
  edelleen hyväksyttävän rakenteen mukaisesti.
- Tarkiste on eheysmekanismi, **ei kryptografinen allekirjoitus**.
- \`store=false\`, ei uusia muistikirjoituksia, ulkoisia
  toimia eikä automaattisia uusintayrityksiä.

**Vanhan keskeytyneen live-ajon** onnistunut ringin 1 vastaus
ei tallentunut, eikä vanhaa hylättyä ringin 2 vastausta
voi palauttaa paikallisesta raportista. Sen sijaan 16:26
onnistunut erillinen probe-ajo teki ringin 1 vastauksesta
uuden, pysyvän \`council72-intelligence-probe-...\`-raportin.

\`resume\`-tila voi käyttää **juuri tätä aiemmin maksettua ja
validia** ringin 1 tulosta, jolloin vain jäljellä olevat
rinkien 2–8 seitsemän kutsua ja perustajien yksi
kutsu tehdään uutena: **enintään 8 uutta API-kutsua**.

### Suositeltu käyttö, vasta uuden erillisen maksullisen hyväksynnän jälkeen

\`\`\`bash
cd ~/klone-arxiv-e1 || exit 1
git fetch origin feat/council72-intelligence-bridge-v1-20261117 || exit 1
git switch --detach FETCH_HEAD || exit 1

# Turvallinen preview ja regressiotestit, ei verkkokutsuja:
bash scripts/klone-council72-intelligence-phone.sh preview

# Vain jos hyväksyt enintään kahdeksan UUTTA maksullista mallikutsua
# jo tarkistamiisi julkisiin tutkimuskatkelmiin:
read -r -s -p 'OpenAI API -avain: ' OPENAI_API_KEY
printf '\n'
export OPENAI_API_KEY
export KLONE_COUNCIL72_CONFIRM_PUBLIC=VAHVISTAN_JULKISUUDEN
export KLONE_COUNCIL72_RESUME_APPROVAL=HYVAKSY_ENINTAAN_8_GPT_KUTSUA

bash scripts/klone-council72-intelligence-phone.sh resume
RESULT=$?

unset OPENAI_API_KEY
unset KLONE_COUNCIL72_CONFIRM_PUBLIC
unset KLONE_COUNCIL72_RESUME_APPROVAL

echo "Lopetuskoodi: $RESULT"
\`\`\`

Uusi \`resume\` etsii viimeisimmän \`probe-*.json\`-raportin
(jonka identiteetti varmennetaan) ja luo yksilöllisen,
mutta samalla lähdepaketilla, kysymyksellä, mallilla ja probella
toistettavan istuntokansion
\`~/klone-var/e11/council72-sessions/resume-<tarkiste>\`.
Uusi ajokerta löytää samat tarkistuspisteet eikä lähetä
uudelleen jo hyväksyttyjä vastauksia.

**Jokainen resume-yritys vaatii silti uuden nimenomaisen
hyväksynnän mahdollisille puuttuville uusille API-kutsuille.**
Virheen jälkeen tarkista tarkistuspisteet ja varoitukset
ennen uutta yritystä. Jos keskeytys johtui sisällön
validointivirheestä, sama vastaus säilyy ja uusi yritys
hylkää sen uudelleen ilman lisälaskutusta. Maksullinen,
mutta täysin saamatta jäänyt API-vastaus ei ole
jälkikäteen palautettavissa näistä paikallisista tiedostoista.

Hyväksytysti koottu täysi raportti sisältää
\`model_analyses_total=9\`, \`model_api_requests_performed=8\`
ja \`model_api_requests_reused=1\` ensimmäisessä
onnistuneessa resume-ajossa. Jos aiempia rinkejä on
jo tallennettu, uusien kutsujen määrä voi olla pienempi.

## Termux — tarkka käyttö

Käytä viimeisintä E11.11-raporttiasi. Tätä tehtävää varten mitään
uutta PDF:ää ei haeta eikä paketteja tarvitse asentaa (Python 3.13
stdlib). Koodi ei muuta paikallisia KLONE-palvelimia eikä päämuistia.

\`\`\`bash
cd ~/klone-arxiv-e1 || exit 1
git fetch origin feat/council72-intelligence-bridge-v1-20261117 || exit 1
git switch --detach FETCH_HEAD || exit 1

# Ensiksi verkottomat regressiotestit ja offline-esikatselu:
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
V1 sisältää verkottomat regressiotestit myös yhden kutsun probesta, API:n kesken jääneen vastauksen virhediagnostiikasta ja laskutetun mallivastauksen paikallisesta palautuksesta.

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
