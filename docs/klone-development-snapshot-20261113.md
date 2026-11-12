# KLONE: kehitystilanne ja seuraava työ 13.11.2026

Tämä on lähdekoodiin, GitHubin vastauksiin ja Work Linuxissa tehtyihin testeihin
perustuva tilannekuva. Androidin tiedostojärjestelmä, palvelin ja portit eivät ole
Work-ympäristön kautta tarkastettavissa. Käyttäjän jakamat Android-tulokset
merkitään erikseen raportoiduiksi havainnoiksi.

## Repositorio ja tämän työn rajaus

- Repositorio: [SickDinner/klone](https://github.com/SickDinner/klone), oletushaara `main`.
- Lähtöcommit oli `bbbbb6f478f0aeacbe2547c4be224b640a9708a0`.
- [PR #162](https://github.com/SickDinner/klone/pull/162) yhdistettiin commitilla
  `448f7f684aec7a7395f643ace4a83bbe847b320a` kaikkien kahdeksan tarkistuksen jälkeen.
  Inspectorin tulostus ei enää saa korvata lähde-evidenssiä. JSON- ja tiedostoluku
  on rajattu ja symlinkit hylätään. Virheellinen sisäkkäinen manifesti ei kaada ajoa.
- [PR #163](https://github.com/SickDinner/klone/pull/163) yhdistettiin commitilla
  `11a3ea5f4ae59c4c6f7871997aa0b06b116b9266`. Sen lopullinen head oli
  `d455759f2ca451ca9c8343fa954bdfdb42d44bfa`; kaikki kahdeksan CI-tarkistusta läpäisivät.
  Mukana on Forensics v1, turvallinen lokianalyysi ja olemassa olevan `/evidence`-
  näkymän laajennus. Katselmoinnissa havaittu päätösraportin ristiriitapolku korjattiin.
- Allekirjoituskerros jatkaa olemassa olevaa [PR:ää #140](https://github.com/SickDinner/klone/pull/140).
  Sen lopullinen CI- ja yhdistämistila täytyy tarkistaa PR:stä; tämä dokumentti ei
  ennakoi yhdistämistä. Riippuvuus on valinnainen, eikä mitään avainta tai vanhaa
  evidenssiä allekirjoiteta tämän kehitystyön yhteydessä.

Tarkistushetkellä `main`-haaran metadata ilmoitti `protected: false` ja
ruleset-lista oli tyhjä. Tämä työ odotti silti jokaisen headin kaikki CI-tarkistukset.
Muiden avoimien luonnos-PR:ien yhdistäminen ei kuulunut tähän muutokseen.

## Arkkitehtuurin nykyiset ilmoitukset

Seuraava taulukko tulee `src/klone/blueprint.py`:stä. Se kuvaa koodin
moduulikortteja, ei puhelimen tämänhetkistä prosessi- tai terveystilaa.

| Moduuli | Vaihe | Koodin ilmoittama tila |
| --- | --- | --- |
| Mission Control | active | operational |
| Hypervisor | active | operational |
| Rooms and Permissions | phase-2a | registry_shell |
| Memory Core | phase-2c4 | read_only_operational |
| Dialogue Corpus | phase-2b8 | read_only_chat_shell |
| Media Lake | phase-2a | indexing_foundation |
| Art Lab | phase-2c | read_only_visual_lab |
| Genomics Lab | phase-2d | planned_sandbox |
| Constitution Layer | phase-2e | read_only_shell |
| Simulation Lab | phase-w1 | world_memory_place_shell |

CORElle on paikallinen FastAPI/SQLite- ja auditointiperusta. KOTIPESÄN
muisti- ja suunnittelurajapintoja on olemassa. PILVIPARVEN koko vision tai
autonomisen hajautetun käytön valmistumista ei tästä päätellä.

Memory Phase 2B.3:n `corrected` löytyy `MemoryEventDetailRecord`-vastauksesta.
Kohdennetut testit kattavat korjauksen, replayn, huone-eristyksen, detail/list-
rajan ja vain luettavan API-pinnan. Tätä toteutusta ei tässä työssä muutettu.

Kuuden säätömuuttujan NeuroCortex-simulaatio on jo `cognition_neurocortex.py`:ssä:
dopamine, noradrenaline, acetylcholine, serotonin, gaba ja glutamate. Se on
rajattu deterministinen laskennallinen koe, ei biologisten aivojen validointi.
Tämän työn 53 Cognition-testiä läpäisivät; uusia biologisia johtopäätöksiä ei tehty.

## Evidenssikomponenttien olemassaolo

Kaikki master promptissa nimetyt osat löytyivät. Olemassaolo ei yksin tarkoita
alkuperän tai käytössä olevan Android-asennuksen varmennusta.

| Osa | Toteutus |
| --- | --- |
| Integrity Gate | `src/klone/test_evidence_integrity.py` |
| Pipeline | `tools/termux_evidence_pipeline.py` |
| Network | `src/klone/evidence_network.py` |
| Triage | `src/klone/evidence_triage.py` |
| Trust Boundary | `src/klone/evidence_trust_boundary.py` |
| Quorum | `src/klone/evidence_quorum.py` |
| Status | `src/klone/evidence_status.py` |
| Observatory ja Diff | `src/klone/evidence_observatory.py`, `compare_history` |
| GitHub CI Bridge | `src/klone/evidence_github_bridge.py` |
| Android–GitHub Cross Check | `src/klone/evidence_cross_environment.py` |
| Claims Ledger | `src/klone/evidence_claims_ledger.py` |
| Shadow Review | `src/klone/evidence_shadow_review.py` |
| Decision Dossier | `src/klone/evidence_decision_dossier.py` |
| Regression Graph | `src/klone/evidence_regression_graph.py` |
| All-in-One | `src/klone/evidence_all_in_one.py` |
| Quality | `src/klone/evidence_quality.py` |
| Recovery Planner | `src/klone/evidence_recovery_planner.py` |
| Artifact Inspector | `src/klone/evidence_artifact_inspector.py` |
| Mission Control Viewer | `src/klone/static/evidence.html`, `evidence-view.js` |
| Uusi Forensics | `src/klone/evidence_forensics.py`, `evidence_log_analysis.py` |

Vanhojen erillisten CLI-komponenttien kaikkia I/O-polkuja ei tässä työssä
kovennettu. Forensicsin pääpolku käyttää rajattua lukijaa ja vain purettuja
tilannekuvia. Vanhoja komentoja ei pidä tulkita yhtä kattavasti kovennetuiksi.

## Varmistukset

Work Linux / Python 3.12.14, projektin riippuvuusrajat:

- PR #162:n kokonaisuus: 751 testiä, OK, yksi ohitus.
- Forensicsin lopullinen kokonaisuus: 794 testiä, OK, yksi ohitus; 43 uutta
  Forensics-testiä. Allekirjoituskerroksen oma ajo: 18 testiä, OK.
- Forensicsin ja allekirjoituskerroksen yhdistetty Work-ajo: 812 testiä, OK,
  yksi ohitus, cryptography 50.0.2. Tämän uuden yhdistelmän Android-ajo puuttuu.
- Erikseen ajettiin Memory 2B.3 (4), hypervisor contract (5), arkkitehtuuri (2),
  hypervisor audit adapter (8), security policy (17), persistent memory audit (3),
  Local Deploy (9), Cognition (53), signed grants (4), nonce ledger (2), atomic
  grant commit (2) ja approval atomic gateway (3). Kaikki läpäisivät.
- Selaintesti käytti synteettisiä ajoja. JSON-avaus, suodatus, vertailu ja
  puutteellisen ajon tiedot toimivat. Puhelinleveyden 390 px testissä korjattiin
  tiivisteen aiheuttama vaakavuoto. Tämä ei ole fyysisen Android-laitteen testi.

Käyttäjän raportoimat Android-tulokset ovat eri ajankohtien evidenssiä:
commitilla `fda10a535a527e68efc2efb5f4e2723d2ddb499f` kohdistus 1 läpi,
Local Deploy 9 läpi ja koko pytest 616 läpi / 1 ohitettu / 1 varoitus sekä
172 subtestiä. Inspectorin vanhalla headilla `32e9243…` 4 testiä läpäisi.
Niitä ei siirretä tämän päivän uudelle commitille.

Master promptissa nimettyjä vanhoja `KLONE-luvat.py`-testejä ei löytynyt näillä
nimillä nykyisestä repositoriosta. Tässä raportissa niitä ei väitetä ajetuiksi.
Nykyisen oikeus-, grant-, replay- ja auditointipinnan testit on eroteltu yllä.

## Avoimet tiedot ja riippuvuuksien mukainen jatko

| Prioriteetti | Seuraava rajattu työ | Edellytys ja hyväksymisnäyttö |
| --- | --- | --- |
| P0 | Aja Forensics alkuperäisille 19 Android-ajolle | Alkuperäiset tiedostot puhelimessa; JSON/HTML ulos lähdepuun ulkopuolelle |
| P0 | Selvitä neljä manifesti+lokit-ajoa, joista paketti puuttuu | Sisällöllinen lokivertailu; puuttuva paketti pysyy puuttuvana |
| P0 | Etsi viiden puuttuvan manifestin alkuperäiset kopiot | Ei jälkikäteen luotua alkuperäisväitettä |
| P1 | Uusi manifestiversio tuleville ajoille | Tarkat komennot, ympäristö, testijoukon tunniste ja backward compatibility -testit |
| P1 | Liitä erillinen witness-tarkistus Forensicsiin | Valmis tarkistin ja käyttäjän hallinnoimat avaimet; provenienssin muut tasot erillään |
| P1 | Riippumaton CI- ja aikaleima-ankkuri | Todellinen lähdeketju; CI ei korvaa Android-näyttöä |
| P2 | Yksi Memory/hypervisor-kehitysaskel | Nykyiset oikeus- ja auditointitestit vihreinä; ei kirjoituspinnan laajennusta vahingossa |
| P2 | Cognition-hypoteesin vertailukelpoinen koe | Ennalta valittu mittari, verrokki ja deterministinen replay |
| P3 | Multimodaalisuus, EEG/BCI ja pilvityökuormat | Eristetyt kokeet, resurssibudjetti ja omat käyttöoikeudet |

Puhelimen nykyinen health-vastaus, portin 8000 omistava prosessi, checkout,
paikalliset muokkaamattomat/likaiset tiedostot ja uusi täysi Android-testitulos
jäävät avoimiksi, kunnes ne tarkistetaan puhelimessa. Symbolinen 72-paikkainen
malli tai simulaatio ei myönnä todellisia käyttöoikeuksia.
