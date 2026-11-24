# KLONE 3.1 — Mission Control Observability (laboratorio)

Perustana GitHubin PR #201, commit `98e71af126bca7573f101309242bd8d08cc194bc`.

## Miksi tämä toteutettiin?

KLONEn nykyiset moduulit osaavat jo tuottaa paikallisesti yhdenmukaisia
muistin jatkuvuusraportteja (v3.0), neuvoston päätöstodisteraportteja (v2.9),
resurssiarvioita (v2.8) ja lähteiden riippuvuusanalyysejä (v2.6–v2.7).
Tätä ei silti pidä esittää yhtenä globaalisti varmennettuna "vihreänä"
tilana. Tässä julkiselle huoneelle tarkoitetussa kerroksessa muodostetaan
**yksi deterministinen ja uudelleen laskettava tilannekatsaus**.

## Toteutetut rajapinnat

`src/klone/mission_control_observatory_v31.py`:

- `RegressionRunClaim`: rajoitettu, tyypitetty **väite** yhdestä ajosta. Edellyttää
  täsmällistä Git-committia, testimäärää, ohituksia, tulosväitettä ja lähtölähteen
  luokkaa. Android 3.13 ja Windows/Ubuntu 3.11–3.12 ovat tuettu 5 ajon matriisi.
  Muita versioita varten matriisi on päivitettävä tarkoituksella; niitä ei
  pidä lukea hiljaisesti onnistuneiksi.
- `summarize_regression_claims`: tunnistaa puuttuvat alustat, eri commitin,
  ristiriitaiset testimäärät, epäonnistuneet ajot, duplikaatit ja puuttuvat
  raporttitiivisteet. Tulos on aina **varmentamaton**: syötetty commit tai
  SHA-256 ei todista alkuperää, identiteettiä eikä laitetta.
- `build_mission_control_review`: käyttää nykyistä
  `build_system_review_pulse`-funktiota, joka puolestaan laskee muistin
  jatkuvuuden ja 12 osa-alueen hyväksyntämatriisin uudelleen. Valinnainen
  `ProofRebuildInputs` laskee v2.9:n proof-dossierin alkuperäisistä syötteistä;
  siitä raporttiin kopioidaan vain tiiviste, tarkastelutila ja yleiset
  pidätyssyyt. Työkalukutsuja, agentin käynnistystä tai muistin muokkausta ei ole.
- `verify_mission_control_review`: deterministinen raportin uudelleenlaskenta,
  joka havaitsee muokatut tai toiseen syötejoukkoon kuuluvat tulokset.
  Ei digitaalista allekirjoitusta eikä itsenäistä identiteetin todentamista.

### Turvaominaisuuksien rajat

1. Raporttiin ei kopioida muistin raakasisältöä, lähdeosoitteita tai
   arkaluonteisten huoneiden tunnisteita. V3.0:n `PublicMemoryEvent` torjuu
   muut kuin `public-room`-luokan muistit.
2. **Edes viisi "passed"-raporttia ei tuota lupaa tai tuotantovalmiusväitettä.**
   Koodi asettaa `report_sources_authenticated=false`,
   `memory_snapshot_completeness_verified=false`,
   `external_audit_anchor_verified=false`, `production_readiness_verified=false`
   ja `deployment_approval=false`.
3. Muistin metatiedot ovat vasta lähteestä annettuja otoksia, eivät
   transaktiossa todistettu täydellinen tietokanta. V2.9:n hypervisor-kutsu on
   sääntöesikatselu eikä käyttöoikeusvaltuutus.
4. Tiivisteet eivät ole nimettömyystakuita, jos syöte on pienestä tunnetusta
   joukosta. Raporttia ei tule lähettää avoimeen verkkoon ennen erillistä
   julkaisukelpoisuuden arviointia.
5. `source_kind` kertoo vain, mistä syötteen **väitetään** tulevan. Sen
   aitouden tarkistamiseen vaaditaan erillinen palvelun todennus ja
   ulkoinen allekirjoitettu, järjestysluvullinen tarkistuspiste.

## Suunnitellut seuraavat integraatiot — eivät vielä toteutettuja

| KLONEn osa | Seuraava varsinainen toteutus | Turvakriteeri |
|---|---|---|
| Memory | Transaktiossa rajattu koko muistin snapshot ja muutoslokin pysyvä ankkuri | Ei kadonnutta historiaa eikä korjausten uudelleenaktivoitumista |
| Council72 | Tarkastelupaketin kautta erimielisten agenttien tehtäväehdotukset | Neuvoston yksimielisyys ei kasvata riippumattomien lähteiden määrää |
| Research | Allekirjoitettu lähdemanifesti ja alkuperäinen tekstiviite | Taustalla oleva lähde voidaan tarkistaa riippumatta agenttitekstistä |
| Hypervisor | OS-tasolla eristetty luvanantopalvelu ja revokoitava grant | Vain suorittava palvelu voi käyttää scoped-lupaa; review-JSON ei kelpaa luvaksi |
| Android | CPU/RAM/akun lämpötilan, energiakulun ja palvelun elvytyksen erilliset mittarit | Puuttuva mittaus on tuntematon, ei 0 |
| Cognition | Held-out aineistoon perustuva kalibraatiomittaus ja kustannustehokas scheduler | Ensin validointi, vasta sitten sääntömuutos |
| Genomics | Omassa suojatussa huoneessa eristetty lähdevarmennus | Julkisen Mission Controlin metatiedot eivät paljasta henkilötietoja |
| Media | Sisältötiivisteet + suostumus/lisenssi/tekijä -metatieto | Suojattu media ei päädy julkiseen yhteenvetoon |
| Simulation | Eristetyt maailmantilat ja simulaation alkuperäliput | Simuloitu havainto ei saa muuttua todelliseksi todisteeksi |
| CI | Automatisoitu todistusten ja allekirjoitusten tarkastus | CI:n vihreä status ei yksin ole omistajan hyväksyntä |
| Mission Control UI | Rajattu, lukuoikeuksilla suojattu näyttö ja vain tarkistetut raporttilähteet | Ei salaisia lähteitä, eikä riskitason piilottamista |
| Deployment | Erillinen hyväksymismenetelmä ja palautussuunnitelma | Päähaara ja tuotantopalvelut ennallaan ilman erillistä hyväksyntää |

## Testaus

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_mission_control_observatory_v31.py' -v
PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py'
```

Yksi uusi testi käyttää todellista v2.9:n hypervisor- ja moduulikerrosta.
Jos koko KLONEn riippuvuudet eivät ole käytettävissä, se ohitetaan
paikallisesti, mutta se tulee suorittaa GitHubin täydellisessä regressiossa.
Tuotantopalveluun ei lisätä uutta endpointia, eikä käynnissä olevia Android-
palvelimia tai päähaaraa muuteta.
