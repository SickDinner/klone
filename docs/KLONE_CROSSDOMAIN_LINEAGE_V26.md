# KLONE v2.6 — 12 osa-alueen todistelun riippuvuusverkko ja Council72-työjono

**Laboratoriototeutus; ei valtuutusta, ei aktiivista agenttiohjausta, ei tietojen siirtoa eri huoneiden välillä.**

## Nykyisen koodipuun tarkastus

Toteutus pohjautuu GitHubin `SickDinner/klone`-koodiin PR #195:n commitissa `da7722d633a6c49a60fd9c3a2e273d302f93acc8`. Silloin `src/klone/` sisälsi 169 Python-moduulia ja GitHub-testimatriisi oli vihreä. Osa moduuleista on suunniteltuja laboratorioita, eikä niiden olemassaolo osoita tuotantovalmiutta. Tämän PR:n base on PR #195:n haara; aiemmat draft-PR:t #188–#195 muodostavat pinon, eikä `main` muutu.

## Koodi ja rajat

1. `src/klone/evidence_lineage_v26.py` rakentaa enintään 512 rajatusta, ilman raakasisältöjä käsiteltävästä evidenssiviitteestä suunnatun riippuvuusverkon; torjuu puuttuvat viitteet, syklit, virheelliset huoneluokitukset ja väärän kohteen päälle tehtävän muistin korjauksen. Yhdistää samaan *konservatiiviseen riippuvuusklusteriin* viitteet, jotka ovat eksplisiittisesti riippuvaisia, joilla on identtinen ilmoitettu SHA-256 tai sama ilmoitettu lähderyhmä. Nämä **eivät** ole identiteetin tai provenienssin aitousvarmenteita.
2. Esittää jokaisesta väitteestä tukevien, kiistävien ja tuntemattomien klusterien lukumäärät, korjattujen havaintojen määrän sekä kontrafaktuaalisen *yhden klusterin poiston* herkkyyden. Ei anna hyväksyntää tai tuota ulospäin luokiteltua raakadataa. Ristiriitaiset/epävarmat havainnot eivät saa näennäistä enemmistöä.
3. Huoneiden tai turvaluokkien väliset viitteet merkitään `quarantined_cross_room_lineage`; **ei** oikeutta lukea/siirtää tietoa. `declared_input_sha256` sitoo vain kutsujan **ilmoittaman metadatan**; `analysis_sha256` sitoo raportin. Kumpikaan ei todenna alkuperäistä dataa, laitetta tai lähdettä.
4. `src/klone/council72_portfolio_v26.py` asettaa enintään **9 x 8 = 72** eri työpistettä yhdeksän ringin tasavuoroiseen *ihmisen arviointijonoon*. Hallitsee arviotokenit ringi- ja kokonaiskiintiöillä; korkean prioriteetin tehtävät järjestetään ringin sisällä. Kaikki suoritus-, hyväksyntä- ja varsinaiset Hypervisor-oikeustarkistukset ovat **pois käytöstä**. Tämä on vasta ehdotus siitä, mitä kannattaisi tarkastaa.

## Moduulien kehitysrajapinnat ja hyväksymisehdot

| Kokonaisuus | Käyttö v2.6:n jälkeen | Seuraava mitattava portti |
|---|---|---|
| Council72 | Saman lähteen toistot ja muutettu havainto vain yhteen klusteriin | Oikeasta sessiosta toistettava lähdepoistotesti ja ristiriidan säilyminen |
| Cognition | V2.5:n ryhmäpainotettua pisteytystä voi verrata ilmoitettuun riippuvuusverkkoon | Ei harjoitus/testi-lähderyhmien päällekkäisyyttä; osoita kalibrointi ulkoisilla nimikkeillä |
| Memory Core | Korjaus- ja `supersedes`-suhteet pysyvät näkyvissä ja vanhat versiot lakkaavat äänestämästä | Historiaketjun deterministinen toisto; rekisteröity oikea memory event adapter |
| Hypervisor & Rooms | Eri huoneiden riippuvuus merkitään tarkistettavaksi | Ennen *mitään* datan hakua oikea `SafeReadPipeline` + audit + output guard |
| Research | Lähdeviitteet eivät ole automaattisesti riippumattomia | Ulkoisesti varmennettu provenance + aineistoversion lukitus |
| Genomics | DNA:n/tutkimusaineiston huone-erotus | Yksityiset genomi-raakadatat eivät koskaan siirry julkiseen tulosteeseen |
| Media | Aineiston lähde ja tekijänoikeus/luokitus osaksi ketjua | Media-kohtainen regressiotesti (nykyisessä Council72-checklistassa media vielä `unmapped`) |
| Simulation | Simuloitu havainto erotetaan todellisesta tiedosta | Simulaatio ei nosta tuotantoväitettä varmennetuksi |
| Audit & Approval | V2.5:n Ed25519-tarkistuspiste + v2.4:n HMAC-hylkäysloki | Riippumaton, monotoninen, hyökkäyksiä kestävä ankkuritallennus; erillinen Android UID |
| Android | Budjettipohjainen jonotus suunnitelmana | Mitatut CPU, RAM, virta, lämpö ja OOM; testit puhelimella |
| CI | Samaa commitia koskevat erilliset Linux/Windows/Android-tulokset | Kaikki matriisit ja PR:n tilan tarkistus ennen muutosluvan harkintaa |
| Deployment | Tämän moduulin `approval_granted=false` aina | Erillinen turvallisuuskatselmointi ja eksplisiittinen omistajan valtuutus |

## Oletukset, uhkamalli ja jatko

- Ilmoitetut SHA-256-tiivisteet, lähdenimet ja `supports`/`contradicts`-merkinnät voivat olla vääriä tai yhden mallin tuottamia. Eri klusteri **ei ole riippumattomuustodistus**. Metadatan kryptografinen tiiviste ei auta, ellei datan alkuperää varmisteta erikseen.
- Yhteiseen klusteriin konservatiivisesti yhdistäminen voi aliarvioida aidosti riippumattomia lähteitä. Tämä on tarkoituksellinen epäsymmetria: epävarmassa tilanteessa ei keksitä lisänäyttöä.
- Resurssikiintiöt ovat *ennusteille*, eivät OS-/GPU-/API-kulutuksen todellisia rajoja; todellinen budjetti vaatii suorituksen tason valvonnan.
- `ReviewCandidate` ei ole autentikoitu Council72-jäsen. Rinkki ja paikka ovat kutsujan ilmoitusta; oikea roster, allekirjoitukset ja hypervisorin roolit on sidottava ulkoisesti.
- Moduleiden integrointi oikeisiin repo-entiteetteihin vaatii erilliset lukuadapterit, vahvistetut lähdetiivisteet ja classification/egress-politiikan. **Älä liitä tätä laboratoriototeutusta tuotannon muistikirjoittajaksi tai suoritustyöjonoksi.**

## Testaus

Paikallinen testi: `PYTHONPATH=src python -m unittest discover -s tests -p 'test_*v26.py' -v`. Todellisia KLONE-palvelimia ja tietokantoja ei avata. GitHub CI ja Android/Termux on varmistettava erikseen tarkalle uudelle commitille. Raportoi läpäistyjen testien todellinen määrä, mahdolliset ohitukset ja alustat erillisinä.
