# KLONE 72: kokonaisjärjestelmän kehitysarkkitehtuuri (v2.5, luonnos)

**Lähdepohja:** `SickDinner/klone`, PR #193, commit `1d5503fa4f03e94e8eb7cae2d4c01c5898279d12` (2026-11-24). Koodipuussa 169 Python-moduulia `src/klone/`-hakemistossa; moduulin olemassaolo **ei** merkitse tuotantovalmiutta. PR #193 pysyy luonnoksena ja myös tämän vaiheen muutokset ovat vain erillinen laboratorio-PR.

## Yksi arkkitehtuurisääntö

**Kaikki päätösvallat sidotaan tiettyyn versioon, osapuoleen, eristettyyn suorituskontekstiin ja tarkistettavaan näyttöön.** Mallin kirjoittama teksti, Council72:n yksimielisyys tai hyväksytty testi eivät yksin anna oikeutta julkaista, muuttaa muistia, käyttää laitteita tai hyväksyä tuotantoon siirtoa.

## Konkreettinen v2.5-toteutus tässä PR:ssä

- `approval_checkpoint_v25.py`: julkisesti siirrettävä, **Ed25519-allekirjoitettu** versioitu tarkistuspiste v2.4:n auditoidusta saapumisportista. Sisältää käyttöalueen (scope), tarkistuspistejärjestysluvun, edellisen tarkistuspisteen tiivisteen, lokin tapahtumamäärän, hyväksyttyjen esitarkistusten määrän, toistontorjunnan tietuemäärän ja HMAC-lokin viimeisen tunnisteen. Ei lokin raakasisältöä tai avaimia.
- Yksi SQLite-lukutransaktio varmistaa yhtenäisen hetken; tarkistaa olemassa olevan v2.4:n HMAC-ketjun **ja** `screened`-tapahtumien lukumäärän suhteessa replay-tauluun.
- Allekirjoitusavain tulee erikseen luotetulta kutsujalta; moduuli ei generoi, tallenna, lataa tai julkista avainta. Eristettyä Android-allekirjoittajaa ei vielä ole.
- Varmennus vaatii: erikseen luotetun julkisen avaimen, oikean sovelluskontekstin, vähimmäisjärjestysnumeron **sekä ulkopuolisesta lähteestä hankitun odotetun tarkistuspisteen tiivisteen**. Sama tiiviste ei saa tulla tarkistettavasta artefaktista.
- Siirtoformaatti on tiukka, rajoitettu, kanoninen JSON; duplikaattiavaimet torjutaan. Esitarkistus ei salli hyväksyntä-, julkaisu-, aktivointi- eikä verkko-operaatioita.
- Poistetun *screened*-tapahtuman voi havaita toisinaan jo replay-tietueiden lukumääräerosta; poistetun hylkäystapahtuman havainto edellyttää aiemmin ulos ankkuroidun tarkistuspisteen vertaamista.

### Testiympäristön riippuvuudet

V2.5:n Ed25519-testit tarvitsevat `cryptography`-kirjaston. GitHubin koko regressiosarja asentaa `.[test]`; lisäsimme sen testiriippuvuuksiin (sama `cryptography>=44,<51` kuin jo olemassa olevassa `.[evidence]`-lisäosassa). Tuotannon perusasennukseen ei lisätä automaattista hyväksyntätoimintoa. Käytettäessä v2.5-moduulia ilman testiriippuvuuksia valitaan erikseen `.[evidence]`.

### Turvarajoitukset

Tämä PR **ei** toteuta ulkopuolista ankkurirekisteriä tai sen atomista CAS-päivitystä; se ei takaa uusimman tarkistuspisteen hallintaa, avaimen yksinoikeutta, laitteen identiteettiä, erillisiä käyttöjärjestelmätunnuksia, suojattua IPC-palvelua eikä automaattista tuotantoon siirtoa. Vanha aito allekirjoitettu tarkistuspiste voi hyväksytyksi tulla, jos hyökkääjä samalla korvaa sekä tarkistetun DB:n **että** väitetyn ulkoisen odotetun tiivisteen. Vain erikseen suojattu, rollback-resistant uusin ankkuri ja palvelun muu eristys voivat estää tämän. Ed25519-signaturen aitous ei yksin vahvista tapahtumalokin täydellisyyttä tai kronologiaa.

Tuotantoympäristössä `V24AuditLedger` ja tarkistuspisteiden allekirjoittaja pitää erottaa muista Termux-prosesseista **erillisiin käyttöjärjestelmän suojaamiin identiteetteihin**. SQLite:n käyttö tiedostopolulla ei sitoudu v2.3:n tietokantakahvaan; sidecarien elinkaari ja attribuutit pitää tarkistaa omassa VFS-/tiedostojärjestelmärajauksessa. 

## Muiden KLONE-moduulien kehitys: priorisoitu toteutusmatriisi

| Moduulialue / nykyinen lähdekoodi | Seuraava parannus | Todentava hyväksymiskriteeri |
| --- | --- | --- |
| **Hypervisor / huoneet** (`hypervisor_runtime`, `hypervisor_dispatch`, `guards`, `rooms`) | Keskitetty kyvykkyystunniste: oletusarvoinen deny, huoneen luokitus, kohderesurssi, kustannusraja, toimeksiannon tarkoitus sekä päättymisaika | Kieltäydy ristihuonepyynnöstä; varmista auditoinnin epäonnistumisen rollback; malliteksti ei saa kasvattaa käyttöoikeuksia |
| **Memory Core** (`memory`, `cognition_memory`, `research_memory`) | Muistin tapahtumille sisältötiiviste, lähde-ID, oikaisuketju, TTL, huoneiden välinen kopiointikäytäntö ja poistettujen tietojen jäljet | Epäluotettava lähde ei muutu aktiivimuistiksi; rekonstruktio toistaa saman tilan; korjaus ei muuta alkuperäistä tapahtumaa |
| **Council72** (`council72_*`) | 9×8 erityisroolit; erottele ennuste, lähde, evidenssi, eriävä kanta, episteeminen epävarmuus ja päätösehdotus; skaalaa vain tarkoituksella | Saman lähteen monistus 72 jäsenelle lasketaan **yhdeksi** riippumattomaksi evidenssiksi; kontradiktiot estävät automaattisen hyväksynnän |
| **Cognition Lab** (`cognition_*`) | Neuromodulaattorianalogioille turvalliset parametrit, hintakatto, drift-rajat, deterministinen replay ja riippumaton eval-setti | Jokainen kokeilu voidaan toistaa; muistivuodot estyvät; muutos ei auta vain testidatan ylioppimisen vuoksi |
| **Research** (`research_*`, `evidence_*`) | Käytä jo olemassa olevia `research_checkpoint*`-rakenteita; erottele lähteen aitous, sisällön oikeellisuus ja mallin tulkinta | Alkuperän puute näkyy `unknown`, ei `verified`; ulkoinen ankkuri ei saa sijaita muokattavassa lähdetietokannassa |
| **Media / Art** (`art`, `dialogue`, media-rajapinnat) | Sisällön oikeudet, alkuperätiedot, tekijänoikeus- ja lisenssikentät, yksityisen materiaalin poisvuototestit | Julkinen renderöinti ei koskaan sisällä yksityisen huoneen tiedostoa; julkaisu tarvitsee erillisen hyväksynnän |
| **Genomics** (`genomics_*`) | Herkkien tietojen erillinen salattu hiekkalaatikko, aineiston suostumuksen käyttötarkoitus, populaatiorakenteen huomioiva analyysi | Sukulaisten tunnisteita ei vuoda yhdistelmäraportteihin; mallit eivät väitä geneettisten ryhmien määräävän älykkyyttä tai arvoa |
| **Simulation** (`simulation`) | World-memory-/3D-simulaation oletus on virtual-only; reaalimaailman toiminnot kulkevat hypervisorin läpi | Simuloitu komento ei avaa laitteen tiedostoja tai palveluita ilman kyvykkyystunnistetta |
| **Android/Termux** (`termux_*`) | Mobiili-first pienikulutuksinen orchestrator, wake-lock- ja kuumuusbudjetit, offline-palautuminen; hyväksyntä eri Android app -UID:hen | Eristetystä toisesta sovelluksesta tuleva **todellinen** eri-UID-kutsu testattu; sama UID torjuttu; poikkeava virrankulutus pysäyttää ajoja |
| **Mission Control / Sites** (`mission_control_*`) | Yksi selkeä luottamusnäkymä: vahvistettu, päätelty, avoin, epäonnistunut, eikä tuotantovalmiuden näyttöä sekoiteta | UI näyttää tarkan commitin, ympäristön, lokitodisteen ja korjaustehtävän; puuttuva näyttö ei muutu vihreäksi |
| **CI / deployment** (`ci_*`, `unified_quality_gate`, `acceptance_matrix`) | Erota regressiovihreys, turvallisuusarvio ja aktiivinen käyttöönotto; lisää Windows/Android-kilpailu- ja fail-close-matriisi | Mikään vihreä CI-kortti ei itsessään anna `deployment_approval=True` |
| **Yhteinen tietokerros** (`contracts`, `schemas`, `egress_policy`) | Versionoidut tapahtumakuoret ja käsittelyrajat kaikille moduuleille: kuka, mitä, miksi, missä huoneessa, millä lähteellä | Muuttunut schema, puuttuva provenance tai vanhentunut oikeus aiheuttaa kieltäytymisen ja kirjautuneen selityksen |

## Vahvat arkkitehtoniset yhdistelmät

1. **Council72 × Research × Memory**: neuvoston jäsenillä on lähderiippumaton arvio, jonka provenance kulkee näkyvästi myös pitkäaikaismuistin korjaukseen; useiden agenttien sama lähde ei kasvata näyttöä keinotekoisesti.
2. **Cognition × Simulation × Quality**: jokainen uusi oppimissääntö kokeillaan ensin eristetyllä simulaatioradalla, jossa on kustannus-, riskitilasto- ja epävarmuustason mittarit ennen varsinaista mallireititystä.
3. **Approval × Hypervisor × Audit**: jokaiselle vaikutusta tuottavalle työkalukutsulle tarvitaan erillinen OS-identiteettiin sidottu palvelupäätös. Julkaisu, avainten käyttö ja muistin pysyvät kirjoitukset eivät ole keskustelumallin välittömiä sivuvaikutuksia.
4. **Media × Genomics × Rooms**: sensitiiviset kuvat ja geenitieto pysyvät eristettyinä, mutta tutkimukseen voidaan jakaa todennettuja, aggregoituja ja luvallisia tilastoja ilman raakadatan vuotoa.
5. **Mission Control × kaikki moduulit**: järjestelmäkohtainen laatuvektori (tietoturva, toistettavuus, hinta, viive, hyöty, korjattavuus) sekä suodatus vahvistettuihin ja simuloituihin tuloksiin. Riskit näkyvät ensin; vihreät testit eivät peitä tunnettua aukkoa.

## Seuraava toteutusjärjestys (ei tässä PR:ssä tehtyjä muutoksia)

1. **v2.5a:** oikea ulkoinen, vain lisäävä ankkuri + atominen compare-and-swap + avaimen pinnaus; testi myös välimuistista tarjottua vanhaa ankkuria vastaan. Julkaisua ei tule automatisoida ilman riippumatonta luottamusjuurta.
2. **v2.5b:** erillinen Android-sovellus / UID ja rajattu autentikoitu IPC; testaa kahden aidon eri UID:n välinen suhde, prosessin kaatuminen, DB WAL/SHM, oikeudet ja rollback.
3. **v2.6:** käytä samaa hyväksyntä-/evidenssirakennetta huonerajoihin ja neuvoston päätösehdotuksiin, mutta älä anna LLM:lle allekirjoitusavaimia.
4. **v2.7:** päästä turvallisesti todelliset, valtuutetut muutokset käyttöön opt-in-tilassa vasta erillisen käyttöönottoarvion jälkeen.

## Päätösmalli

**Varmennettu koodi/testi ≠ varmennettu käyttöoikeus ≠ sallittu tuotantotoimi.** Kaikista kolmesta vaaditaan oma näyttönsä. Tässä vaiheessa vain prototyyppikoodi ja testiympäristön näyttö on toteutettu.
