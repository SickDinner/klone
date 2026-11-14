# Neuvosto 72: perustajien katselmus ja muistin konsolidointiehdotus

Katselmus kokoaa [kehitysjonon ja lähteiden poistokokeiden](council72-review.md)
päälle kahdeksan perustajan vastuut. Kukin näkee oman rinkinsä kahdeksan
jäsentä, tehtävät, lähteistetyt väitteet, avoimet kysymykset, eriävät kannat,
äänestyshistorian, kuuden laskennallisen säätimen muutoksen sekä aikabudjetista
omalle ringille varatut minuutit. Kaikki 72 roolia ovat mukana luettelon
nykyisillä sidonnoilla. Limbon kahdeksan viestinviejän signaalit kulkevat
edelleen kunkin oman perustajan vastuuringistä.

## Mitä konsolidointi tarkoittaa

Tulos on viitteistetty väitehakemisto, ei vapaa tekstiyhteenveto eikä
automaattinen kirjoitus Memory Coreen. Jokainen väite säilyttää aktiiviset
puoltavat, vastakkaiset ja avoimet havaintotunnisteet sekä koko historiansa
tunnisteet. Alkuperäiset tekstit ja lähdeviitteet ovat mukana alkuperäisessä
katselmusraportissa. Korvattu havainto ei osallistu nykyiseen kantaan, mutta
korjausketju ja aiemmat tapahtumat säilyvät.

Sama väitetunniste voi riidellä myös eri rinkien välillä. Molemmat
perustajat näkevät ristiriidan. `reported_support` tarkoittaa vain ilmoitettua
puoltavaa aineistoa; `truth_verified` on aina false. Tuntematon pysyy avoimena.
Kaikkien johdettujen väitteiden luokittelu on vähintään koko istunnon
historiallinen luokittelu. Yksityistä historiaa ei voi siivota pois yhteenvedolla.

Perustajien eriävät ja odottavat kannat säilyvät yhteisessä katselmuksessa.
Kantahistoriassa erotetaan laskennallinen kanta ja erikseen annettu ääni.
Yhteisen päämäärän toteutuminen on `null`, koska sitä ei voi päätellä
äänistä tai säätimien arvoista. Säädinten delta vertaa viimeistä säilytettyä
tilaa rooliprofiilin lähtöarvoon; se ei mittaa biologista toipumista.

## Yksi seuraava askel ja 12 tarkistuspakettia

Seuraava askel valitaan kehitysjonon budjettiin mahtuvista kokonaisista
tehtävistä: korkein valittu prioriteetti, sen sisällä lyhin arvio ja lopuksi
tunniste. Jos mitään ei mahdu budjettiin, askel on null. Lähdekiistan tai
avoimen havainnon selvitystehtävälle ei keksitä koodikorjausta tai testiä,
joka todistaisi lähteen todeksi. `change_proposal` pysyy null-arvona, kun
toistettua virhettä ja lähdekoodiin sidottua muutosta ei ole.

Kaikilla 12 osa-alueella on lähdetiedostot ja rajattu tarkistuskohde.
Testit ovat nykyisen repositorion nimettyjä regressiotestejä. Median paketti
kattaa Art Labin kuvamittarit ja huonerajojen vertailun, ei koko Media Lakea,
puhetta, videota tai neuroteknologiaa. CI:n paketti osoittaa workflow-tiedostoon;
sille ei anneta paikallista pytest-komentoa GitHubin CI-todisteena.

Komennot ovat erillisessä kopioitavassa lohkossa. Oletus on `~/klone-next`
ja sen `.venv/bin/python`. Aseta `KLONE_ROOT` erilliseen worktree-hakemistoon
ja tarvittaessa `KLONE_PY` ennen lohkon ajoa. Lohko tarkistaa polut, kirjaa
git-tilan ja commitin, ajaa vain nimettyjä testejä sekä tarkistaa diffiä.
Raportti ei suorita niitä. Koko testisarjan varmistus tehdään mahdollisen
korjauksen jälkeen erikseen samalla commitilla.

Selain vertaa kopioitavia komentoja mukana toimitettuun, repositorion
kiinteistä poluista muodostettuun sallittujen komentojen luetteloon.
Tuodun raportin tavoitetta, havaintoja tai muokattua komentotekstiä ei
upoteta ajettavaan lohkoon. Muu raportin rakennetarkistus ei korvaa Pythonin
täydellistä toistoa.

Johdetut tiivisteet käyttävät uudelleen muodostettua kanonista istuntoa ja
katselmusta. Selaimen JSON-viennin `0.0` → `0` -esitysmuutos säilyttää toiston;
boolean-arvon false vaihtaminen nollaksi hylätään edelleen.

## Käyttö Termuxissa

```bash
PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" \
  -m klone.council72_briefing --input "$REVIEW_JSON" --output "$NEW_BRIEFING_JSON"

PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" \
  -m klone.council72_briefing --verify "$NEW_BRIEFING_JSON"
```

`--demo` muodostaa synteettisen esimerkin. Syötteen ja tuloksen enimmäiskoko
on 2 MiB. Uusi vienti ei korvaa vanhaa tiedostoa eikä kirjoita historiallisen
testiaineiston hakemistoon. Koko alkuperäinen katselmus ja istunto toistetaan
ennen koonnin muodostamista. Raportin tiiviste ei autentikoi alkuperää.

Paikallinen `POST /api/cognition/council72/briefing` ottaa saman tehtäväolion
ja asetukset kuin `/review`. Sivun **Kuninkaiden yhteinen katselmus** näyttää
tuloksen. Sites-sivulla avaa JSON samalla tiedostopainikkeella; tiedostoa
ei lähetetä verkkoon. Koodin suoritus, oikeuksien muutos, Memory-ingest,
verkkoviestien lähetys ja käyttöönoton hyväksyntä eivät kuulu katselmukseen.

## Seuraavat aidot toteutusrajat

1. Fyysisen Androidin uusi ajo ja saman commitin evidenssi ennen/jälkeen.
2. Väitteen ja alkuperäisen testimanifestin välinen viitteistetty adapteri.
   Se erottaa Work-, CI- ja Android-näytön sekä allekirjoittajan luottamuksen.
3. Mitattava tavoitesopimus: hyväksymiskriteeri ja epäonnistumiskriteeri
   ennen koetta; perustajat eivät voi vaihtaa niitä tuloksen nähtyään.
4. Budjettiin rajattu agenttiajuri nykyisen Hypervisor-dispatchin takana,
   peruutus ja auditointi ennen ensimmäistä malli- tai työkalukutsua.
5. Nimetyn ulkoisen kanavan tilisidonta, käyttöoikeus ja lähetyskuitti.
   Nykyinen Limbon jono säilyy omistajan tarkistettavina luonnoksina.

Nämä ovat jatkokehityskohteita. Tämä muutos toteuttaa toistettavan koonnin,
väitehakemiston ja tarkistusohjeet; se ei käynnistä 72 kielimallia eikä
osoita subjektiivisen tietoisuuden syntymistä.
