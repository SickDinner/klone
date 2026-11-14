# Neuvosto 72: lähteiden poistokokeet ja kehitysjono

Jatko: [kahdeksan perustajan katselmus, väitehakemisto ja tarkistuspaketit](council72-briefing.md).

Istunnon päälle saa nyt toistettavan katselmuksen. Se selvittää, mitä tapahtuu,
jos yksi ilmoitettu lähderyhmä poistuu viimeisen kierroksen käytössä olevasta
aineistosta. Katselmus muodostaa myös aikabudjettiin sopivan tehtäväehdotuksen
rinkien lähdeaukoista, ristiriidoista, avoimista havainnoista, perustajien
eriävistä kannoista ja kahdestatoista kehityksen osa-alueesta.

## Poistokokeen täsmällinen merkitys

Alkuperäisen istunnon täytyy ensin toistua kokonaan nykyisellä koodilla ja
rooliluettelolla. Vain aktiiviset havainnot otetaan poistokokeeseen: korvattu
havainto säilyy historiassa mutta sen uusi korjaus edustaa nykyistä väitettä.
Saman lähderyhmän kaikki aktiiviset havainnot poistetaan yhdessä, myös silloin,
kun niitä on useassa ringissä. Lähderyhmien nimistä ei päätellä riippumattomuutta.

Jokainen vaihtoehto alkaa **viimeisen kierroksen alkuperäisestä saapuvasta
jäsenkohtaisesta säädintilasta**. Ryhmän aiemmilla kierroksilla jättämä vaikutus
siis säilyy alkutilassa. Tämä ei ole koko historian vastakkainen tapahtumakulku,
eikä sillä mitata lähteen koko elinkaaren kausaalivaikutusta. Viimeiselle
kierrokselle erikseen annetut perustajaäänet säilyvät myös vaihtoehdoissa.

Rinkien signaalit, lähdekiintiöt, ristiriidat, jäsenäänet ja laskennalliset
perustajakannat lasketaan uudelleen. Jos kaikki aktiiviset havainnot poistuvat,
puuttuva lähdekiintiö estää puollon. Konfliktin poistuminen voi puolestaan
parantaa vaihtoehdon tarkistustilaa; se ei ratkaise sitä, kumpi lähde on oikeassa.
Alkuperäinen istunto, sen viestijono ja aiemmat tapahtumat pysyvät samana.

Oletuksena tutkitaan aakkosjärjestyksen ensimmäiset 16 aktiivista lähderyhmää.
Rajan voi nostaa enintään 32:een. `coverage_complete`, `tested_source_groups`
ja `omitted_source_groups` kertovat täsmällisesti kattavuuden. Osittainen koe
ei väitä tutkimattomia ryhmiä vakaiksi. Muuttumaton tarkistustila ei yksin
tarkoita muuttumattomia jäsenääniä tai luotettavia lähteitä.

## Selitettävä tehtäväjono

| Tehtävä | Paino | Suunnitteluaika |
| --- | ---: | ---: |
| Ristiriidan selvitys kullekin osalliselle ringille | 30 | 20 min |
| Epäonnistuneen osa-alueen tarkistus | nykyinen impact × 5 | 25 min |
| Puuttuvan lähdekiintiön tutkiminen | 20 | 15 min |
| Avoimen havainnon tutkiminen | 18 | 10 min |
| Eriävän tai odottavan perustajakannan käsittely | 17 | 10 min |
| Lähderyhmän poistamiselle herkän kannan tutkiminen | 16 | 10 min |
| Muut osa-alueiden tarkistukset | nykyinen impact × tilapaino | 15 min |

Osa-alueiden painotus käyttää olemassa olevaa `development_priorities`-mallia.
Järjestys on paino laskevasti ja tunniste nousevasti. Kokonainen tehtävä
valitaan, jos se mahtuu jäljellä olevaan aikabudjettiin ja tehtävärajaan.
Liian suuren tehtävän jälkeen pienempi voi vielä mahtua. Tulos näyttää myös
budjetin tai tehtävärajan vuoksi odottavat tehtävät. Oletus on 60 minuuttia
ja kahdeksan tehtävää, rajat 1–480 minuuttia ja 1–32 tehtävää.

Ajat ovat näkyviä suunnitteluarvioita. Ajuria, ajonaikaista keskeytystä,
token- tai energiabudjetin toteutusta ei tässä lisätä. Jokaisella tehtävällä
on valmistumiskriteeri, alkuperäisten havaintojen tunnisteet silloin kun niitä
on, vastuuringin perustaja ja hänen oma Limbon viestinviejänsä. Tehtäviä
ei lähetetä eikä suoriteta. Herkkyyden tutkiminen ei tarkoita hyväksynnän
pakottamista; pidättyvä kanta voi olla oikea lopputulos.

Osa-alueiden tilat ovat kutsujan ilmoittamia, oletuksena kaikki `unverified`.
Kaikki 12 on annettava yhdessä, jos oletus korvataan: `hypervisor`,
`permissions`, `audit`, `memory`, `cognition`, `research`, `genomics`, `media`,
`simulation`, `android`, `ci`, `deployment`. Tuetut tilat ovat `passed`,
`failed`, `pending`, `unverified`, `not_applicable`. `passed` jättää kyseisen
osa-alueen tarkistustehtävän pois; raportti ei varmista ilmoitusta.
`not_applicable` jättää soveltuvuuden arvioinnin tehtäväksi.

Kartoitettu testitiedosto on tarkistuksen lähtökohta, ei koko osa-alueen
kattavuusväite eikä suoritettu testi. Median erillinen regressiotesti on vielä
kartoittamatta, joten `check_target` on sille `null`. CI:n kohde on workflow.
Work-, CI- ja fyysisen Androidin tulokset tallennetaan erikseen.

## Käyttö

Paikallisessa `/council72`-näkymässä avaa tai aja ensin istunto. Kohdassa
**Mitä tehdään seuraavaksi?** voit ilmoittaa osa-alueiden tilat, aikabudjetin
ja tehtävärajan. Tuloksessa näkyvät poistokokeet, valitut tehtävät ja odottava
jono. Tallenna raportti JSONina. Uuden istunnon avaaminen poistaa vanhan
kehitysjonon näkyvistä, jotta se ei jää uuden istunnon tulokseksi.

CLI käyttää olemassa olevaa istuntoraporttia:

```bash
PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" \
  -m klone.council72_review --input "$SESSION_JSON" \
  --budget-minutes 60 --max-tasks 8 --output "$NEW_REVIEW_JSON"

PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" \
  -m klone.council72_review --verify "$NEW_REVIEW_JSON"
```

`--states tilat.json` ottaa kaikkien 12 osa-alueen tilaolion. `--demo`
muodostaa selvästi synteettisen esimerkin. Syötteen ja tuloksen raja on
2 MiB; tilaolion raja on 4 KiB. CLI lukee rajatut tiedostot ilman symlinkkien
seuraamista ja luo vain uusia vientitiedostoja nykyisellä evidence-kirjoittajalla.
Vanhaa tiedostoa tai suojatun testiajohakemiston aineistoa ei korvata.

`POST /api/cognition/council72/review` ottaa `session`-kentässä saman
**tehtäväolion** kuin istunnon API, sekä haluttaessa `domain_states`,
`budget_minutes`, `max_tasks` ja `max_source_groups`. Se laskee alkuperäisen
istunnon ensin uudelleen. Raportti sisältää alkuperäisen istunnon ja asetukset,
joten CLI:n `--verify` voi toistaa myös katselmuksen ja tehtävävalinnan.

Raportin voi avata selaimessa samalla tiedostopainikkeella kuin istunnon.
Selain tarkistaa rakenteen ja budjettisummat; täysi laskennallinen toisto tehdään
Pythonissa. Tiivisteet eivät autentikoi alkuperää tai lähteiden totuutta.
Yksityisen istunnon luokittelu säilyy myös katselmuksessa. Katselmointi on
paikallinen puhdas laskenta eikä lue tietokantaa, kirjoita auditointia tai
avaa lähdeviitteitä verkosta.

## Varmennus 14.11.2026

Work Linux / Python 3.12: 17 uutta katselmuksen testiä; täysi sarja
963 läpi, yksi ohitettu, 283 alitestiä. Mukana ovat erikseen muodostettu
yhden kierroksen vertailu, aktiiviset korjaukset, tyhjä aineisto,
vastakkainen lähde, erikseen annettu vastustus, avoimet havainnot,
kattavuusraja, budjetit, roolisidonnat, tyypit, manipuloinnin hylkäys,
yksityinen luokittelu, tiedostojen säilytys ja API/CLI-yhtäläisyys.
JavaScriptin syntaksi ja whitespace-tarkistus läpäisevät. Memory Phase 2B.3:n
API-testissä varmistetaan lisäksi `corrected is True` korvatulle tapahtumalle.

Tämän muutoksen fyysistä Android-ajoa ei ole. Selain-QA jäi ympäristöesteeseen:
paikallinen Chromium ei käynnistynyt, ja cloud-selain esti esikatselun
avaamisen. Näkymän visuaalista toimivuutta ei siksi merkitä varmennetuksi.
