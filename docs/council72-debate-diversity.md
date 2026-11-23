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
