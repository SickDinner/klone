# Neuvosto 72: kokemusten jatkumo ja Limbon viestijono

Tämä jatkaa [72 roolin rakennetta](council72-v1.md). Yhdeksän rinkiä,
kahdeksan paikkaa kussakin sekä kahdeksan perustajaa säilyvät samassa
luettelossa. Istunto tuo niiden päälle lähteistettyjä **havaintoväitteitä**,
simuloidun tunnetilan jatkumon ja tarkistettavan viestijonon. Roolit ovat
edelleen deterministisiä laskennallisia profiileja; 72 kielimalliprosessia
ei käynnistetä.

## Mitä voi nyt tehdä

1. Anna Limbon viestinviejälle havainto, lähdeviite ja ilmoitettu lähderyhmä.
   Viestinviejän sidonta määrää vastuuringin ja perustajan. Viitteitä ei avata
   verkosta, eikä havaintotekstiä suoriteta.
2. Aja 1–8 kierrosta. Yhdellä kierroksella on 1–32 havaintoa ja enintään
   kahdeksan viestiluonnosta. Istuntojen JSON-raja on 2 MiB.
3. Tutki lähderyhmät, avoimet havainnot ja saman `claim_key`-tunnisteen
   puoltavien ja vastakkaisten väitteiden ristiriidat myös rinkien välillä.
4. Korjaa havainto uudella tunnisteella ja `supersedes`-viitteellä.
   Alkuperäinen jää aiempaan kierrokseen. Saman viestinviejän, lähderyhmän
   ja väitteen aktiivinen havainto voidaan korvata kerran. Luokittelua ei
   saa alentaa korjauksella, ja yksityisen historian luokittelu säilyy
   koko istunnossa.
5. Tallenna uusi raportti ja jatka siitä. Aiemman raportin täytyy toistua
   kokonaan ennen jatkamista. Uusi vienti ei korvaa vanhaa tiedostoa.

## Lähteet eivät muutu todeksi äänestämällä

Jokainen rinki tarvitsee vähintään kaksi puoltavaa **ilmoitettua** lähderyhmää.
Saman ryhmän kopiointi ei kasvata kiintiötä eikä muuta signaalien painoa.
Saman ryhmän sisällä käytetään varovaisia minimi-/maksimiarvoja: esimerkiksi
epävarmuus ja riski kasvavat korkeimman arvon mukaan, laatu laskee heikoimman
arvon mukaan. Samaa varovaisuusperiaatetta käytetään ryhmien välillä.

Lähderyhmä on käyttäjän antama tunniste. Se ei todenna lähteiden todellista
riippumattomuutta, laatua tai alkuperää. `authenticated_sources` pysyy nollana.
`unknown` ei ole puoltava havainto eikä vahvistettu regressio.
Eksplisiittinen ristiriita pysäyttää tutkimuskannan, vaikka kaikki perustajat
puoltaisivat. Puuttuva lähdekiintiö pysäyttää sen samoin. Tämän jälkeen
sovelletaan nykyistä kahdeksan perustajan sääntöä: vastustus säilyy,
odottava kanta jättää asian kesken, yksimielinen puolto vie tarkistukseen.

Istunto ei tee semanttista totuusanalyysia tekstistä. Ristiriita tarkoittaa
tässä käyttäjän samalla väitetunnisteella merkitsemiä vastakkaisia kantoja.
Kaksi väärää mutta eri ryhmään nimettyä lähdettä voi edelleen johtaa harhaan;
tämä raja on raportissa näkyvä eikä autentikointia väitetä toteutetuksi.

## Miten simuloitu tunne jatkuu

Jokaisella 72 jäsenellä on kuuden säätimen oma lähtövektori. Kierroksen
laskenta käyttää edellisen kierroksen säilytettyä vektoria. Seuraava tila on
90 % nykyisen arvion säädinvektorista ja 10 % jäsenen alkuperäisestä profiilista.
Nykyinen arvio käyttää edelleen 75 % edellistä tilaa ja 25 % havaintojen
tuottamaa tavoitetta. Kaikki arvot pysyvät välillä 0–1.

Rinkien signaalit ovat erilliset. Erikoistuneet jäsenet käsittelevät oman
rinkinsä signaaleja; perustaja ja hänen Limbon viestinviejänsä saavat saman
vastuuringin signaalin. Siksi Paimonin ringin uhka muuttaa Paimonin, Ronoven
ja ringin kahdeksan jäsenen tilaa suhteessa rauhalliseen vertailuun.
Muiden jäsenten tavallinen ajallinen kehitys jatkuu omista havainnoistaan.

Nämä ovat näkyviä suunnittelukertoimia, eivät mitattuja biologisia pitoisuuksia.
Toiminnallista työmuistia ja itsemallia voi tutkia toistettavilla kokeilla.
Raportti ei anna tietoisuuspistettä eikä väitä subjektiivista kokemusta.

## Limbon viestijono ja oikeudet

Viestiluonnoksessa täytyy olla perustaja ja hänen oma viestinviejänsä.
Väärä pari, tavallinen jäsen perustajana tai ylimääräinen toimivaltakenttä
hylätään. Vain julkinen, lähdekiintiöt täyttävä, ristiriidaton ja perustajien
puoltama asia pääsee `pending_owner_review`-tilaan. Mukana on myös nykyisen
Hypervisorin julkisen huoneen `evaluator/propose`-säännön esikatselu.
Esikatselu ei autentikoi kutsujaa tai valtuuta lähettämistä.

Jokainen myöhempi kierros muuttaa aiemmat viestit `stale_requires_review`-tilaan.
Vanhan kierroksen tapahtuma ja alkuperäinen syöte säilyvät. Viestijono on
uudelleen laskettava näkymä niistä. Vastaanottaja ja tili ovat `null`,
`delivery_enabled` on `false` ja omistajan tarkistus tarvitaan aina.
Foorumi-, some-, dokumentaatio- ja tutkimuskanavat ovat tässä luokkia,
eivät toteutettuja verkkolähettäjiä.

Istunnon tapahtumaketju on erillinen tutkimusloki. Sen tiivisteet auttavat
toistossa, mutta eivät autentikoi historiaa. Varsinaista KLONEn muistitietokantaa
ei käytetä tunnetilan säilytykseen. Tila säilytetään käyttäjän valitsemassa
uudessa JSON-viennissä; palvelin ei pidä istuntoja muistissa kutsujen välillä.

## Oikea mutta rajattu Memory Core -liitäntä

Paikallisen API:n erillinen `POST /api/cognition/council72/memory-observation`
ottaa vain `limit`-luvun (1–200, oletus 50). Se käyttää nykyistä
`SafeReadPipeline`-putkea, Hypervisoria ja Output Guardia. Huone on kiinteä
`public-room` ja rooli `evaluator`. Pyynnössä ei voi valita omistajaroolia,
muuta huonetta tai raakasisältöä.

Tulokseen tulevat vain rajatun otoksen tapahtuma-, episodi-, entiteetti- ja
korjattujen tapahtumien määrät sekä katkaisun tieto. Forneus saa siitä
`unknown`-havainnon yhdestä `klone-memory-core`-lähderyhmästä. Määrä ei ole
sisällön laatutesti. Muistiin ei kirjoiteta tapahtumia tai korjauksia.

Luku lisää kaksi uutta auditointitapahtumaa olemassa olevalla repositoryllä:
`council72_memory_delegated` ja `council72_memory_completed`. Auditoinnin virhe
ennen lukua estää lukemisen; lopun auditointivirhe estää tuloksen palautuksen.
Tämän liitännän auditointi on siis oikeaa pysyvää auditointia. Istunnon muu
hash-ketju on edelleen erillinen tutkimusloki. Nykyisten muiden API:en
identiteettikäyttäytymistä ei muuteta tällä liitännällä.

## Käyttö Termuxissa

```bash
PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" \
  -m klone.council72_session --demo --output "$NEW_SESSION_JSON"

PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" \
  -m klone.council72_session --verify "$NEW_SESSION_JSON"
```

Omalle tehtävälle käytä `--input tehtava.json`. Esimerkkisyöte on
`src/klone/static/council72-session-demo.json`. Jatkaminen ottaa yhden uuden
kierroksen JSONin ja tuottaa kokonaan uuden raportin:

```bash
PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" \
  -m klone.council72_session --previous "$OLD_SESSION_JSON" \
  --input uusi-kierros.json --output "$NEXT_SESSION_JSON"
```

Paikallinen `POST /api/cognition/council72/session` ottaa saman tehtäväolion.
`/council72` näyttää kierrokset, havainnot, korjaukset, lähdekiintiöt,
ristiriidat, perustajien kannat ja viestijonon. Sites-kopio avaa raportit
selaimessa, eikä kutsu paikallista API:a tai lähetä tiedostoja verkkoon.
Selaimen rakennetarkistus ei ole Pythonissa tehtävä täydellinen replay.
Vanhojen yhden kierroksen kokeiden käyttö säilyy ennallaan.

## Seuraavat ominaisuudet riippuvuuksien mukaan

| Kohde | Seuraava konkreettinen lisäys | Hyväksymiskoe |
| --- | --- | --- |
| CORE / Android | Uuden istunnon fyysinen koe ja v2-testievidenssi | Sama commit ennen/jälkeen, alkuperäinen loki ja uusi JSON |
| Limbo / Bael | Nimettyjen kanavien adapterit, ulkoiset tekstit karanteeniin | Vastaanottaja-, tili-, lupa- ja auditointitarkistus ennen jokaista lähetystä |
| Himo / Paimon | Päämäärän alitavoitteet ja selitettävä huomionjako | Sama aikabudjetti; jokaisella alitavoitteella mitattava tulos |
| Ylensyönti / Purson | Huonekohtainen muistin konsolidointiehdotus | Johdettu yhteenveto viittaa alkuperäisiin, ingest ei muutu |
| Ahneus / Asmoday | Androidin aika-, energia- ja tokenbudjetit | Keskeytys rajalla säilyttää tapahtumat ja keskeneräisen tilan |
| Viha / Balam | Kuormituksen palautumis- ja estokokeet | Uhkapulssi ei muuta oikeuksia, palautuminen toistuu |
| Harhaoppi / Zagan | Kilpailevat selitykset ja vastatodisteiden etsintätehtävät | Myös hylätty hypoteesi ja perustelut säilyvät |
| Väkivalta / Vine | Rajattu agenttiajuri olemassa olevan dispatch-portin taakse | Estetty delegointi ei kutsu työkalua tai mallia |
| Vilppi / Belial | Allekirjoitettu lähderekisteri ja forensics-liitäntä | Tiiviste, allekirjoittaja, lähdeaineisto ja Android-tulos erotellaan |
| Kadotus / kaikki perustajat | Vähemmistöraportti ja hallittu päätöksen uudelleenkäsittely | Päätösperustelut, vastustus ja vanha versio ovat toistettavissa |
| PILVIPARVI | Raskaan työn eristetty jonotus ja tulosten palautus | Työ ei saa nostaa omia oikeuksiaan tai hyväksyä omaa tulostaan |

Lisäksi hyödyllisiä tutkimuskokeita ovat lähderyhmän poistaminen kerrallaan
(muuttuuko kanta yhden lähteen varassa), perustajan vaihtovertailu samalla
aineistolla, havaintojen vaikutusketju jäsenestä päätökseen, sekä yön yli
tehtävä offline-konsolidointiehdotus. Multimodaalisen aineiston seuraava askel
on tuoda ääni-/kuva-analyysin rajatut havaintoväitteet samaan lähdeskeemaan.
Neuroteknologian syötteet tarvitsevat erillisen tutkimus- ja suostumusrajan.
Nämä rivit ovat jatkokehitysehdotuksia, eivät tässä toteutettuja ominaisuuksia.
