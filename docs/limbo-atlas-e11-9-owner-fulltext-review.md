# KLONE E11.9 – offline kokotekstin paikallinen sanallinen tarkistus

## Tavoite ja rajat

E11.8 tuotti 10 lähdesidonnaista korttia kahdelle versiolle:
- A / muistimerkintä 26 / arXiv `2611.13801v1`
- B / muistimerkintä 24 / arXiv `2611.15598v1`

E11.9 **ei väitä tarkistaneensa alkuperäisiä kokotekstejä**, ennen kuin
omistaja on toimittanut niistä erikseen versionumeroon sidotut
UTF-8-muotoiset tekstikopiot. Näitä käsitellään edelleen
`owner_supplied_plain_text_unverified_against_publisher` -aineistona.
Varmennettu arXiv-PDF, julkaisijan aitoustarkistus, menetelmien arvio,
riippumattomat toisinnukset ja tieteellinen johtopäätös ovat myöhempiä vaiheita.

## Mitä koodi tekee

`src/klone/limbo_fulltext_review.py` laskee E11.8:n uudelleen
**alkuperäisestä kahdeksan tiedoston ketjusta** nykyiseen kanoniseen
Memory Core -lähdepariin verraten. Se hylkää muutetut, vanhentuneet,
väärään artikkeliin tai versioon sidotut kortit.

Kummankin oikeuksien mukaisesti omistajan toimittaman tekstitiedoston
käytölle vaaditaan erillinen suostumus ja käyttöoikeushuomautus.
Järjestelmä tarkastaa tiedostokoon (enintään 2 MiB),
UTF-8-sisällön, versio-ID:t, identiteetit ja tiedostojen erilaisuuden.
PDF- ja HTML-tiedostoja ei hyväksytä sellaisinaan.

Jokaiselle kortille muodostetaan:
- alkuperäisen E11.8-kortin tunniste, arXiv-versio ja lähdetunnus
- paikallisen tekstin SHA-256, merkkimäärä ja tarkastusaseman ketjutarkiste
- mahdolliset kirjainkoolle ja välilyönneille sallivat tekstiosumat sekä merkkipaikat
- erilliset samalukuiset ja **samayksikköiset** numeroesiintymät
- perusteltu luokka: tekstiosuma, vain numeroesiintymä tai ei paikannusta
- jäljellä olevat aitous-, menetelmä-, mittaus- ja toistotarkistukset

Sanallinen ja numeerinen osuma on **vain paikallinen esiintymätarkistus**.
Esimerkiksi `31%` ei vastaa `31 percentage points` ja pieni `k`
ei ole automaattisesti kelvin. Puuttuva osuma ei todista väitettä vääräksi
(eikä suomenkielinen paikallinen selostus välttämättä esiinny sanasta sanaan
englanninkielisessä kokotekstissä).

## Termux – valmistelu ja erillinen käyttäjän hyväksyntä

Hanki itse molempien oikeiden arXiv-versioiden kokotekstit
omaan käyttöösi sallituin ehdoin. Jos sinulla on alkuperäiset PDF:t,
voit muuntaa tekstin esimerkiksi `pdftotext`-ohjelmalla.
PDF:n teksti saattaa rikkoutua palstojen, taulukoiden tai kaavojen
takia, joten sen alkuperäisyyttä tai täydellisyyttä ei tästä päätellä.

Esimerkki, kun tekstikopiot ovat jo hakemistossa
`~/klone-var/e11/`:

```bash
cd ~/klone-arxiv-e1 || exit 1
git fetch origin feat/limbo-e11-9-offline-fulltext-20261117
git switch --detach FETCH_HEAD

# Hyväksy vain jos nämä ovat itse tarkistamasi A/B-versiot
export KLONE_E11_9_OWNER_APPROVAL=HYVAKSY_KOKOTEKSTI
export KLONE_E11_9_RIGHTS_A="Kirjaa tähän lähdeteksti A:n todellinen käyttöoikeus"
export KLONE_E11_9_RIGHTS_B="Kirjaa tähän lähdeteksti B:n todellinen käyttöoikeus"
bash scripts/klone-e11-9-phone.sh \
  ~/klone-var/e11/2611.13801v1.txt \
  ~/klone-var/e11/2611.15598v1.txt
```

**Älä käytä E11:n A/B- tekoälyselostuksia tässä vaiheessa
alkuperäisjulkaisun tekstinä.**

Tuloksena syntyy uusi, vanhoja tiedostoja korvaamaton raportti
`~/klone-var/e11/e11-9-kokotekstivertailu-YYYYMMDD-HHMMSS.json`.

Ohjelma ei itsenäisesti tee verkkopyyntöjä, muokkaa paikallista Memory Corea,
suorita Council72-tehtäviä, anna sitovia neuvostoääniä tai merkitse mitään
tieteellistä väitettä vahvistetuksi.

## Seuraava laajennus E11.10

Tarkistettu arXiv-PDF:n tai lähdepakkauksen hankinta vain erillisellä
käyttäjän verkkoluvalla, tiukalla arXiv-host-rajauksella, kokorajoilla,
SHA-256-tarkisteella, version tarkistuksella ja alkuperäisen PDF:n
sivukohtaisilla viitteillä. Vasta tämän jälkeen on mielekästä rakentaa
kontekstisidonnaista tieteellistä arviointia ja Council72:n erillistä
arviointi-/hyväksyntätyönkulkua.
