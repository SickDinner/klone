# Noki v0.4 – HELVETTIMYLLY / lähteistetty Grimoire

Noki on fiktiivinen, sarkastinen kauhupunk-korppi KLONEn paikallisessa käyttöliittymässä.
Sen yliluonnollinen rooli, myrkylliset herjat, kauhukuvasto ja demonin äänet ovat **näyttelijäpersoona**.
Taustalla oleva lähdehakemisto on **tietokirjasto**, jossa käsikirjoitusperinteet,
nykyiset uskonnot, akateeminen tutkimus ja taideideat erotetaan toisistaan.

## Ominaisuudet

1. **Ulkoasu:** groteski, tarkoituksella rikkinäinen pikselikorppi, ilman hahmon diagnooseja tai väitteitä todellisista demoneista.
2. **Hellvoice:** WebAudio tuottaa noitanaurun, sylkevät kurkkuäänet, hissin, pitkän kimeän huudon, matalan murinan,
   metallikolinoita, käkätyksen, synteettisen hautajaissoinnin, häiriöäänen ja **9 × 8 = 72 -äänen kuoron**.
   Kuoro on 72 lyhyttä synteettistä äänitapahtumaa, ei 72 itsenäistä persoonallisuutta.
3. **Puhe:** laitteen oma `speechSynthesis` tuottaa puhutut sanat neljällä hahmotusprofiililla.
   Ääni-ilme syntyy foneettisesta muunnoksesta, korkeudesta, nopeudesta ja päälle miksatuista
   WebAudio-äänistä. Selaimen puhesynteesiä ei pysty yleisesti ohjaamaan koko DSP-ketjun läpi,
   joten tämä **ei ole täysin mukautettu neural voice model**.
4. **Grimoire-tietokirjasto:** `noki-grimoire.json` sisältää 72 Goetia-nimeä + 66 käsitteellistä
   merkintää (yhteensä **138 tietuetta**) ja **18 nimettyä julkista lähdettä**.
   Tiivistelmät linkitetään alkuperäisiin lähteisiin. Tämä on rajattu tutkittu hakemisto,
   **ei koko internetin sisältö eikä reaaliaikainen tutkimusindeksi**.
5. **Lähdehaku:** hakusana, aihealue, nimien klikkaaminen, näytettävä selitys ja alkuperäinen lähde.
   Hakutulos voi myös antaa Nokin paikalliseen keskusteluun lähteeseen sidotun vastauksen.
6. **Poikkialainen taideideoiden generaattori:** yhdistää kaksi satunnaista tietuetta
   luovaksi kuvalliseksi/äänelliseksi ehdotukseksi. Merkintä on aina "fiktiivinen assosiaatio";
   se ei ole tieteellinen väite tai uuden okkulttisen opin paljastus.
7. **Keskustelu KLONEssa:** vain eksplisiittisellä valinnalla ja annettuun dialogue corpus -lähdepolkuun.
   `/api/clone-chat/status` sekä `/api/clone-chat/respond`, `mode=bounded`, max 12 historian viestiä.
   Ulkoinen kielimalli ei ole tällä hetkellä käytössä, vaikka käyttäjä antaisi API-avaimen.
8. **Matki ääntäni:** enintään 4 sekuntia paikallista ääninäytettä,
   madallettu ja rosoiseksi suodatettu toisto. Puheentunnistusnapit erikseen;
   selaimen speech recognition voi käyttää ulkoista tunnistuspalvelua.
9. **Turpa kiinni:** keskeyttää äänen, mikrofonin ja KLONEen mahdollisesti odottavan HTTP-pyynnön.

### Tiedepohjaiset rajat

- **Ars Goetia / Pseudomonarchia**: historiallisia tekstejä, joilla on käsikirjoitus- ja nimivariantteja.
- **Satanismi**: tutkittuja moderneja liikkeitä ja historiallisia syytöksiä; ei yhtä yhtenäistä oppia.
- **Haitilainen Vodou**: elävä uskonto ja kulttuuri; **ei synonyymi demonologialle**, eikä sen henkiä nimeta Ars Goetian demoneiksi.
- **Šamanismi**: useita eri perinteitä; huomioidaan termien ja yhteisöjen moninaisuus.
- **Tajunnan tutkimus**: neurotiedettä, vaikutus- ja riskitutkimusta;
  ei annoksia, hankintaohjeita, käyttöneuvoja eikä teoksista pääteltyjä diagnooseja.

## Käynnissä oleva KLONE Termuxissa – päivitä staattiset neljä tiedostoa turvallisesti

Näin saat Nokin toimimaan ilman palvelimen uudelleenkäynnistystä ja
ilman että vaihdat KLONEn nykyisen Git-haaran.

```sh
cd ~/klone-next || exit 1
git fetch origin feat/noki-raven-companion-20261114 || exit 1

TMP="$(mktemp -d)"
for f in noki.html noki-hellvoice.js noki-grimoire.js noki-grimoire.json; do
  git show "FETCH_HEAD:src/klone/static/$f" > "$TMP/$f" || {
    echo "Puutteellinen lataus: $f"; rm -rf "$TMP"; exit 1;
  }
done

mkdir -p src/klone/static ~/klone-var/noki-backup
for f in noki.html noki-hellvoice.js noki-grimoire.js noki-grimoire.json; do
  if [ -f "src/klone/static/$f" ]; then
    cp "src/klone/static/$f" "$HOME/klone-var/noki-backup/$f" 2>/dev/null || true
  fi
  cp "$TMP/$f" "src/klone/static/$f" || exit 1
done
rm -rf "$TMP"

for f in noki.html noki-hellvoice.js noki-grimoire.js noki-grimoire.json; do
  curl -sS -o /dev/null -w "$f: HTTP %{http_code}\n" "http://127.0.0.1:8000/static/$f"
done
```


Avaa selaimessa: `http://127.0.0.1:8000/static/noki.html?v=4`.
Jos `/noki`-reitti ei vielä ole käytössä, käytä nimenomaan `/static/noki.html`.

## Testit haaran lähdekoodissa

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_noki_companion.py'
```

Testaa myös selaimessa käyttöoikeudet: mikrofonin tulee aktivoitua vain napista;
KLONEen viestejä tulee lähteä vain erikseen käyttöön otetusta keskustelutilasta.
Muista, että selaimen speech recognition -tunnistus voi käyttää verkkopalvelua.

## Lisäkehitys

- Kontrollerin oikeustarkastus, jos tietokirjaston tietueet halutaan myöhemmin KLONEn varsinaiseen Media Lakeen.
- Lähteiden päivitys uutena kontrolloituna importterina, joka erottaa tekijänoikeuslisenssit,
  lähdeprovenienssin, luokitellut huoneet ja julkiset metatiedot.
- Turvallisessa paikallisympäristössä erillinen DSP-putki tai tarkoitukseen koulutettu TTS,
  jos Androidin vakio-`speechSynthesis` ei ole tarpeeksi groteski.
- Eri aineistojen käyttäminen automaattiseen keskusteluun edellyttää uutta
  luokitellun ulosmenevän tiedonsiirron ja pääsyoikeuksien suunnittelua.
