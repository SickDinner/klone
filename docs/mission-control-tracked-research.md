# KLONE 4A.6: jäljitettävät tutkimusajot

`MissionControlTrackedResearch` yhdistää 4A.4:n luotetun
palvelurajan ja 4A.5:n pysyvän tapahtumakirjan.

## Työnkulku

1. Tarkista isännän tunnistus, Hypervisorin julkisen huoneen
   käyttöoikeus, resurssikohtainen valtuutus ja admission-auditointi.
2. Varaa yksilöllinen `run_id` pysyvällä `started`-tapahtumalla.
3. Tarkista käyttöoikeudet uudelleen juuri ennen tutkimuksen suoritusta.
4. Suorita lähteiden tarkistus, tutkimuksen tallennus ja raportointi.
5. Kirjaa `completed` tai `failed`. Historiatiedot luetaan
   `history(run_id, request)`-operaatiolla käyttöoikeuksien jälkeen.

Samaa `run_id`-tunnusta ei voi suorittaa uudelleen. Historiatiedot
rajataan tutkimustunnuksen mukaan.

## Rajoitukset

- Tämä on Python-palvelukerros, ei Androidin graafinen käyttöliittymä.
- Isännän callbackien on oltava luotettuja, eivät asiakkaan määrittämiä.
- Auditointi ja dossierin tallennus eivät vielä ole sama atominen
  transaktio.
- Jos prosessi kaatuu tallennuksen jälkeen, ajon tila voi jäädä
  `started`-tilaan. Tällainen ajo on *epäselvä*, ei turvallisesti
  uudelleenkäynnistettävä. Operaattorin on täsmäytettävä tietokanta.
- Jos virhe tapahtuu tallennuksen jälkeen, `failed`-tila ei tarkoita,
  ettei dossier-versiota olisi syntynyt.
- Ei automaattista tutkimusväitteiden hyväksymistä tai julkaisua.
