# KLONE v2.8 — Cognitive Metabolism, resurssimittauslaboratorio

**Tila:** draft-PR:n read-only, vain arviointiin tarkoitettu osa. Ei tuotantoeristystä eikä automaattista agenttien suoritusta. Päälähtökohtana KLONEn v2.7:n todisteriippuvuusverkko ja v2.6:n Council72-työjonon laskennalliset tokenbudjetit.

## Tarkistettavat mittarit

- `capture_process_snapshot()` käyttää Pythonin `time.monotonic_ns()` ja `time.process_time_ns()` sekä käyttöjärjestelmän PID:tä. Nämä ovat **koko prosessin** seinäkello- ja CPU-aikamittareita, eivät yhden agentin eristettyä käyttöä.
- Linux/Termux: `/proc/self/status`-tiedoston `VmRSS` on nykyinen fyysisen muistin käyttö näytteenottohetkellä; **ei huippumuisti** eikä kunkin tehtävän oma muistinkulutus. Windowsilla tai muissa ei-tuetuissa ympäristöissä ilmoitetaan `null` eikä keksitä nollaa.
- `ProviderTokenUsage` vastaanottaa **mallipalvelun tai kutsujan ilmoittaman** prompt- ja vastaustokenien määrän. Näitä ei voi todistaa oikeiksi tämän moduulin avulla. Puuttuva raportti on `null`, ei nolla.
- **Mitattua energiankulutusta, lämpötilaa tai akkukustannusta ei vielä ole**. Kentät jätetään tuntemattomiksi, kunnes erillinen mittausrajapinta validoidaan.

## Council72:n budjettien sovittaminen todellisuushavaintoihin

`reconcile_council_metabolism(plan, receipts)` vertaa rajattua 9 × 8 -työjonoa tehtävien ulkoisesti toimitettuihin kuittauksiin.

- Suunnitelman kanoninen SHA-256 tarkistetaan ja tehtäväidentiteetti sidotaan täsmälliseen suunnitelmaversioon, ringiin ja paikkaan. **SHA-256 ei autentikoi suunnitelman laatijaa**.
- Suorituskuitit hyväksytään vain tehtävistä, jotka vanha portfolio todella asetti ihmisarviointijonoon. Tuotettu raportti ei ole suorituslupa tai työn suorituksen varmennus.
- Kokonais- ja ringikohtaiset ilmoitetut tokenbudjettien ylitykset havaitaan. Yksittäisen tehtävän ennusteen ylitystä käsitellään erillisenä signaalina; pelkkä ennusteen ylitys ei ole automaattinen ulkoinen oikeuksien estotoimi.
- Kesken jääneet, peruutetut tai mittaamattomat tehtävät käsitellään tuntemattomina. Päällekkäiset saman PID:n mittausjaksot merkitään, jotta niiden CPU-aikoja ei lasketa virheellisesti riippumattomiksi.
- Raportti sisältää vain numeerista ja tehtäväkohtaista metadataa; ei alkuperäisiä tutkimusväitteitä, DNA-/terveysaineistoa, keskusteluja eikä mallien tekstivastauksia.
- Jokaisessa raportissa `telemetry_authenticated=false`, `resource_limit_enforced=false`, `human_review_required=true`, `execution_enabled=false` ja `approval_granted=false`.

## Kokonais-KLONEn jatkokehitys

| Kerros | Seuraava turvallinen toteutus ja hyväksymistesti |
|---|---|
| Council72 | Laske uuden resurssiraportin perusteella *ehdotus* tulevasta budjetista; testaa, ettei yksikään ehdotus ohita hypervisoria eikä hyväksyntäpalvelua |
| Cognition Lab | Lisää mallikohtaiset kustannusjakaumat, energiatehokas vertailu ja kalibraation laatu per token; tarvitsee riippumattoman arviointiaineiston |
| Hypervisor | Erillinen, OS:n valvoma resurssiraja (esim. Androidilla sovelluksen oma prosessi ja cgroup-/sandbox-vaihtoehdot); testaa todellinen estäminen, ei Python-luokan palautearvoa |
| Memory Core | Leimaa muistoon tallennettavien tulosten lähteet, versiot, korjaukset ja suorituskuitin tiiviste; älä liitä tokenkulua tiedon totuusarvoon |
| Evidence Genome v2.7 | Vertaa riippuvuusklusterin poistamisen *vaikutusta* sen laskentakustannukseen: mitkä lisätarkistukset tuottavat eniten todellista epävarmuuden vähennystä? |
| Media / Genomics | Pidä henkilökohtaiset ja perimäaineistot erillisissä huoneissa; resurssilokissa vain sallittu metadata ja minimaaliset tunnisteet |
| Simulation Lab | Tee energia-/muistibudjetin toistettavat ajoitus- ja kuormituskokeet, mutta pidä simulaatiot erossa oikeista järjestelmätoimista |
| Mission Control | Näytä resurssien *mittaustapa ja puuttuvat mittaukset* sekä ennustettu vs raportoitu budjetti ilman virheellisiä "todelliset tokenit" -väitteitä |
| Android | Mittaa oikealla Termux-laitteella yhden eristetyn prosessin kuormitus; lisää RAM-paineen ja akku-/lämpötelemetrian lähteen dokumentoitu arviointi |
| Turvallisuus | Säilytä allekirjoitus- ja auditointipolku erillään kutsujan toimittamasta resurssiraportista; estä raportin käyttäminen hyväksyntänä |

## Varmennus

Paikallinen Linux: v2.8:n uudet **43** yksikkötestiä ja aiemmat v2.6:n **63** testiä, yhteensä **106/106 OK**. Android/Termux- sekä GitHub CI -testit tarkistettava erikseen tällä commitilla. Kokonaisregression arvioitu testimäärä on **1336** (v2.7 1293 + 43), ellei testikokoelma muutu.

**Rajat:** mittausajot eivät todista agentin aikaansaamia tuloksia. Oikeuksia ei ole lisätty. Tämä on valmis moduulitason laboratoriokoodi, ei valmis alustan resurssihallinta.
