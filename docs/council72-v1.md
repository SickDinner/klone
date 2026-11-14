# Neuvosto 72 v1 · yhdeksän rinkiä ja kahdeksan perustajaa

Toteutus on toimiva, deterministinen tutkimusmalli. Se sisältää 72 yksilöllistä
roolia, henkilökohtaiset kuuden säätimen lähtövektorit, ringeittäin kulkevat
raportit, perustajien viimeisen sisäisen kannan, jaetun toiminnallisen työmuistin
sekä erillisen viestiluonnoksen reitityksen. Se ei käynnistä 72 kielimallia,
todista subjektiivista tietoisuutta tai muuta KLONEn oikeuksia.

## Rakenne

| Rinki | Kirjallinen nimi | Tekninen vastuu | Vastuuperustaja | Oma Limbon viestinviejä |
| --- | --- | --- | --- | --- |
| 1 | Limbo | Ulkomaa ja viestintä | Bael | Naberius |
| 2 | Himo | Tahto, merkitys ja luovuus | Paimon | Ronove |
| 3 | Ylensyönti | Muisti ja kokemusten jäsentäminen | Purson | Forneus |
| 4 | Ahneus | Resurssit ja toteutusjärjestys | Asmoday | Caim |
| 5 | Viha | Tunne, esto ja kuormituksen säätely | Balam | Orobas |
| 6 | Harhaoppi | Tutkimus ja vaihtoehtoiset mallit | Zagan | Seere |
| 7 | Väkivalta | Arkkitehtuuri ja rajatut toiminnot | Vine | Gusion |
| 8 | Vilppi / Malebolge | Evidenssi, oikeudet ja auditointi | Belial | Dantalion |
| 9 | Kadotus / petollisuus | Kahdeksan perustajan yhteinen synteesi | Kaikki kahdeksan | Kahdeksan omaa sidosta |

Jokaisessa ringissä on täsmälleen kahdeksan paikkaa. Yhteensä on 72 jäsentä,
ei 72 + kahdeksaa ylimääräistä perustajaa. Kaikki jäsenet ja tehtävät ovat
`src/klone/static/council72-catalog.json`-tiedostossa. Sama luettelo palvelee
Python-moottoria ja selainkäyttöliittymää. Jäsenen ID on Goetia-luettelon numero;
se on eri asia kuin ringin paikkanumero. Persoonapiirteet ja tekniset tehtävät
ovat KLONEn omia suunnittelupäätöksiä.

Rinki 9 kokoaa ringit 1–8: yksi perustaja vastaa yhdestä ylemmästä ringistä.
Limbon kahdeksan viestinviejää palvelevat kukin yhtä perustajaa. Havaintoviitteiden
mallinnettu reitti on Limbon oma viestinviejä → erikoistunut rinki → sen
vastuuperustaja → perustajien yhteinen synteesi. Limbon oma rinki kuuluu Baelille,
mutta muut seitsemän viestinviejää välittävät oman perustajansa asioita.
Syöte sisältää vain käyttäjän jo antamia havaintoväitteitä; mallissa ei ole
itsenäistä verkkohakua tai pääsyä yksityiseen muistiin.

## Kirjalliset lähteet ja oma tulkinta

[Danten Inferno](https://www.gutenberg.org/files/1001/1001-h/1001-h.htm) antaa
yhdeksän piirin nimistön. [Lesser Key of Solomonin Goetia](https://en.wikisource.org/wiki/The_Lesser_Key_of_Solomon)
antaa 72 nimen ja lyhyiden motiivien viitteen. Lähdetekstin arvoluokitus nimeää
yhdeksän kuningasta. KLONEn kahdeksan perustajan kokoonpano on oma valinta;
Beleth säilyy jäsenenä ringissä 2. Tämä on käyttäjän konseptin ensimmäinen
toteutettu kokoonpano, ei historiallista tekstiä väittävä kahdeksan kuninkaan lista.

## Harkinta ja viimeinen sana

Jokainen jäsen muodostaa pisteen ja kannan `endorse`, `oppose` tai `defer`.
Ylemmät ringit raportoivat kahdeksan jäsenensä kannat ja viitteet. Perustajan
laskennallinen synteesipiste yhdistää 65 % hänen omaa arviotaan ja 35 % hänen
vastuuringin kannatusta. Ringin kannatus on puoltojen määrä + puolet odottavista
jaettuna kahdeksalla. Kanta on puolto pisteestä 0.6 alkaen, vastustus pisteeseen
0.35 asti ja muuten lisätiedon odotus.

V1:n perustajien sääntö on tarkoituksella näkyvä suunnitteluoletus:

- Kaikkien kahdeksan ylemmän ringin vähintään yksi viite tarvitaan.
- Yksikin perustajan vastustus säilyttää erimielisyyden (`contested`).
- Odottava perustaja jättää synteesin kesken (`pending`).
- Kahdeksan puoltavaa perustajaa tuottaa `endorsed_for_review`-kannan.

`founder_votes` voi antaa kaikkien kahdeksan perustajan erilliset kannat.
Niiden lähde näkyy lokissa `explicit_input`:ina; niitä ei autentikoida aidoiksi
agenttien lausunnoiksi. Näin perustajat voivat poiketa ylempien ringkien kannasta,
mutta puuttuvat viitteet pysäyttävät synteesin silti. Vähemmistön kannat säilyvät.
Viite on opaque tunniste, ei automaattisesti luettu tai todennettu lähde.

Kuninkaiden viimeinen sana koskee tämän simulaation sisäistä tutkimuskantaa.
Omistaja ja varsinainen Hypervisor/Rooms/Permissions/Audit-järjestelmä säilyvät
suoritusvallan rajoina. Symbolinen rinki tai mieliala ei myönnä kyvykkyyttä.

## Tunteet ja kuusi laskennallista säädintä

Moottori käyttää nykyisiä `cognition_neurocortex.NAMES`- ja
`cognition_experiment_lab.neurochemical_policy`-rakenteita. Säädinten nimet ovat
dopamiini, noradrenaliini, asetyylikoliini, serotoniini, GABA ja glutamaatti.
Jäsenkohtainen lähtövektori on versioitu deterministinen persoona-arvo.
Se ei perustu mitattuun välittäjäainepitoisuuteen tai biologiseen malliin.

Syötteen laatu-, epävarmuus-, riski-, uutuus-, palaute-, uhka- ja sosiaalisen
palautteen luvut ovat välillä 0–1. Ne muuttavat laskennallisia tavoitteita.
Uusi säädinvektori on 75 % lähtöprofiilia + 25 % tavoitevektoria. Uteliaisuus,
huoli, rauhallisuus ja sosiaalinen avoimuus ovat niistä johdettuja analogioita.
Ne muuttavat pisteytystä, eivät viitteitä, luokittelua tai käyttöoikeuksia.

`experiment()` ajaa saman syötteen modulaatiolla ja ilman sitä sekä raportoi
muuttuneiden jäsenkantojen määrän ja keskimääräisen piste-eron. V1 on yhden
tilannekuvan koe; mieliala ei jatku itsenäisesti seuraavaan API-kutsuun.

Jaettu työmuisti käyttää olemassa olevaa `CognitionCore`-mallia kahdeksalla
ringin kannatushavainnolla. Tämä tarjoaa toistettavan työmuisti- ja
itsemallikokeen. Raportti ei anna tietoisuuspistettä tai väitä kokemuksellisuutta.

## Päätösloki ja toisto

Syöte, luettelo, 72 arviota, kahdeksan rinkiraporttia, kahdeksan perustajakantaa
ja lopullinen synteesi ovat deterministisiä. Hash-ketjun juuren lisäksi
`replay_matches()` vertaa koko kierrosta uudelleenlaskentaan. Muuttunut kanta,
syöte, trace tai oikeuslippu rikkoo toiston. Sama koodi ja luetteloversio tarvitaan
historiallisen kierroksen toistoon. Tiiviste ei yksin todenna alkuperää.

Muisti on kokeen sisäinen. Varsinaiseen KLONE-tietokantaan, tapahtumahistoriaan,
oikeustokeneihin tai auditointilokiin ei tehdä kirjoituksia. CLI:n valittu
raporttitiedosto on uusi tiedosto suojatun testiajojuuren ulkopuolella.

## Limbon viestiluonnokset

`draft_dispatch()` hyväksyy vain perustajan ja hänen oman Limbon viestinviejänsä.
Kierroksen täytyy toistua, kannan olla `endorsed_for_review` ja luokittelun
`public`. `restricted` ja `sealed` eivät pääse luonnosjonoon. Kanavatyyppi voi
olla foorumi, some, dokumentaatio tai tutkimus. Luonnokseen tulee tekoälymerkintä,
perustajan ja viestinviejän ID sekä päätöslokin viite.
Roolitunniste valitsee mallin reitin; se ei autentikoi todellista toimijaa.
`issuer_authenticated` pysyy `false` ja viestin sisältö on kutsujan antama.

Vastaanottaja ja tili ovat `null`, `delivery_enabled` on `false` ja omistajan
tarkistus tarvitaan. Oikeaa verkkolähettäjää, tilejä, salasanoja, automaattista
postausta tai aikataulutettua viestintää ei ole toteutettu. Seuraava liitäntä
vaatii nimetyn kanavan, tilin, vastaanottajan sekä nykyisen käyttöoikeus- ja
auditointijärjestelmän tarkistukset. Saapuvan ulkoisen tekstin ohjeet ovat dataa,
eivät oikeuksien myöntöjä tai suoritettavia komentoja.

## Käyttö

```bash
PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" \
  -m klone.council72 --demo --output "$HOME/klone-var/council-demo-$(date +%Y%m%d-%H%M%S)-$$.json"
```

Demo on selvästi merkitty synteettiseksi, eikä se kuvaa KLONEn todellista tilaa.
Omalle tehtävälle käytä `--input tehtava.json`; syötteen raja on 64 KiB.
Tuntemattomat kentät, boolean-luvut, ei-finiittiset luvut ja rajojen ylitykset
hylätään. Viitteitä on enintään kahdeksan per rinki ja tavoite enintään 2000 merkkiä.
Luettelon saa `--catalog`-valinnalla. Tulostiedostoa ei korvata uudelleenajolla.

Paikallinen näkymä on `/council72`. API:t:

- `GET /api/cognition/council72/catalog`
- `POST /api/cognition/council72/simulate`
- `POST /api/cognition/council72/draft`

Simulate ottaa tehtäväolion, draft ottaa `proposal`, `king_id`, `courier_id`,
`channel` ja `message`. Draft laskee päätöksen itse uudelleen; selain ei voi
toimittaa tekaistua hyväksyntälippua. API on rajattu ja tilaton.

Sites-näkymä esittää saman luettelon sekä paikallisesti avatun koeraportin.
Se ei kutsu käyttäjän localhostia tai lähetä raporttia verkkoon. Paikalliset
API-painikkeet poistetaan Sites-kopiosta. Käyttäjän selaintallennus ja aiemmat
testihistoriat säilyvät.

## Seuraavat kehitysvaiheet

1. Androidin fyysinen testi ja kokeen liittäminen uuteen v2-testievidenssiin.
2. Oikeuksilla rajattu agenttiajuri, joka tuottaa erilliset lähteistetyt
   ringin havainnot nykyisten simuloitujen pisteiden tilalle.
3. Pitkittäinen tunne- ja kokemustila append-only-tapahtumina ja hallittu replay.
4. Nimetty ulkoinen kanava ja lähetysten kyvykkyys-, yksityisyys-, kuittaus- ja
   auditointiraja. Vasta silloin luonnoksesta voidaan tehdä oikea lähetys.
5. Yhteisen itsemallin mitattavat ablaatiokokeet. Subjektiivinen tietoisuus
   säilyy tutkimuskysymyksenä.
