# Council72 Debate Diversity Audit – 24.11.2026

Tämä on **vain luettava**, nollan uuden mallikutsun auditointityökalu.
Analyysi laskee saman valmiin kolmen vuoron debate-v2-raportin kahden
ensimmäisen vuoron rooli- ja lähdekorttijoukkojen päällekkäisyyden sekä
koeteltavien testien *sanastollisen* samankaltaisuuden. Tarkistaa raportin
sisäisen kanonisen SHA-256-summan, ei ulkopuolista autenttisuutta.

Ei kirjoita mitään tiedostoihin eikä KLONE Memory Coreen, ei pyydä API-avainta,
ei verkkoyhteyttä, ei suorita mallia eikä muokkaa aikaisempia raportteja.

## Termux, käyttäjän aikaisempi todellinen raportti

Aja siitä worktreestä, joka sisältää tämän tiedoston:

~~~sh
cd ~/klone-council72-diversity
~/klone-next/.venv/bin/python -m unittest discover \
  -s tests -p 'test_council72_debate_diversity.py' -v

~/klone-next/.venv/bin/python \
  src/klone/council72_debate_diversity.py \
  "$HOME/klone-var/e11/council72-quality-debate-live-20261119-121640-21516.json" \
  --text
~~~

Aito aiemmin tulostettu ajo kertoi viisi samaa roolia kummassakin
arviointivaiheessa: [31,50,66,55,40]. Tästä seuraa puhtaasti
joukkoteoreettisesti roolien Jaccard-päällekkäisyys 1.0. Lähdekorttien ja
tekstien muut arvot tulee mitata alkuperäisestä JSON:sta tällä työkalulla.
Sanastollinen samankaltaisuus ei ole semanttinen eikä tieteellinen arvio.

## Seuraava kokeilu

1. Mittaa roolien, lähdekorttien ja testien nykyinen päällekkäisyys.
2. Määrittele eri arviointirooleille erotettavat episteemiset tehtävät:
   esimerkiksi teksti-/versiotarkistus vastaan julkaisutuloksen
   menetelmäkriittinen tarkistus. Pelkkä roolilistan pakotettu erottaminen
   ei automaattisesti tuota riippumatonta analyysiä.
3. Kokeile vastaväitteiden uutuuden laatukriteeriä ensin täysin offline
   tallennetulla aineistolla ennen uusien maksullisten mallikutsujen sallimista.
4. Pidä kliiniset tai tieteelliset päätelmät ja lopulliset hyväksynnät
   ihmisen arvioitavina.

Tämä muutos perustuu PR #182:n kokeelliseen debate-v2-raporttimuotoon.
Se EI ole valmis uusi väittelymoottori eikä riippumattomuusvalidointi.

## V1.1 – aineiston osoittaman puutteen lisämittari

Käyttäjän oikeassa 19.11. tallennetussa väittelyssä roolien ja lähdekorttien
joukkopäällekkäisyys oli 1,0 / 1,0, mutta falsifiointitestien sanastolliset
Jaccard-arvot olivat vain [0.143, 0.294, 0.2]. Tämä osoittaa, että pelkkä
sanatason vertailu ei riitä tunnistamaan samasta tutkimusongelmasta puhumista.

Lisätty erillinen, dokumentoitu **aiheakselien sääntöpohjainen heuristiikka**:
lähteen versio, PDF-poiminta/sivukuvat, tekstivastineet, numeroiden konteksti,
tutkimusmenetelmät ja yleistettävyys. Molempien vuorojen selityksistä
johdetaan näiden kuuden rajatun aiheen joukko, päällekkäisyys ja puolustajan
uudet aiheakselit. Jos samat tutkimusaiheet toistuvat eri sanamuodoin, arvio
voi merkitä `shared_issue_axes_candidate` vaikka sana-Jaccard jäisi pieneksi.

Nämä ovat **hakusanoihin perustuvia ehdokkaita**, eivät semanttisia
totuusluokituksia, tiedevertailua tai varmuuslupauksia. Tyhjä aihejoukko
tarkoittaa tunnistamatta jääneitä aiheita, ei riippumattomuutta.

GitHubin CI ja Android-ajot tarkistetaan täsmälleen uusimmalla commitilla.


## V1.2 – maininnan ja koeteltavan testin erottaminen

Android-lokissa 24.11.2026 edellinen v1.1 hyväksyttiin paikallisesti:
**11 testiä / 11 OK**, commit `4b59006`. Alkuperäisen raportin
aiheakselien Jaccard oli 0,833. Tämä koskee vain v1.1:tä.

V1.2 korjaa kaksiselitteisen `kattav*`-hakusanan: PDF:n
tarkistuksen **kattavuus** (`inspection_coverage`) ei sellaisenaan
tarkoita tutkimustulosten **yleistettävyyttä**
(`scope_or_generalization`). Luokittelu on edelleen varovainen
sääntöpohjainen seulonta, ei semanttinen totuusarvio.

Uusi tuloste näyttää myös:

- `cross_examiner_axis_evidence` ja `defender_axis_evidence`:
  argumentin numeron, kentän (väite, perustelu, falsifiointitesti)
  ja siinä mainitut lähdekorttitunnukset kunkin aihehakusanan kohdalla.
  Tunnukset eivät vahvista aineiston aitoutta.
- `defender_new_axes_in_falsification_tests`: puolustajan uusi aihe
  **mainitaan** myös testiehdotuksessa.
- `defender_new_axes_only_outside_falsification_tests`: aihe esiintyy
  ainoastaan väitteessä tai perustelussa, ei ehdotetussa testissä.

Huomaa raja: testiehdotuksessa esiintyvä aihehakusana ei todista,
että testi olisi toteutettavissa, uusi tai aidosti falsifioiva.

### Android / Termux – uuden version tarkistus

Käytä **uutta erillistä hakemistoa**, koska aiempi testattu worktree
on lukittu commitille `4b59006`:

~~~sh
cd ~/klone-next || exit 1
git fetch origin feat/council72-debate-diversity-audit-20261124
git worktree add --detach "$HOME/klone-council72-diversity-v12" FETCH_HEAD
cd "$HOME/klone-council72-diversity-v12" || exit 1
git rev-parse --short HEAD
~/klone-next/.venv/bin/python -m unittest discover -s tests \
  -p 'test_council72_debate_diversity.py' -v
~/klone-next/.venv/bin/python src/klone/council72_debate_diversity.py \
  "$HOME/klone-var/e11/council72-quality-debate-live-20261119-121640-21516.json" --text
~~~

Tässä kehitysvaiheessa on **14 määriteltyä kohdennettua testiä**.
CI ja Android-hyväksyntä tulee todeta täsmälleen testatun commitin
perusteella. Mitään GPT-avainta tai maksettua keskustelukutsua ei tarvita.
