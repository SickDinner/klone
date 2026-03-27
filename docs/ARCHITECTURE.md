# Architecture

## 0. Nykyinen toteutustila

Phase 2A:n ingest/index spine sisältää nyt:

- `contracts.py`
  kriittisten luokitusten ja päätösten literaalit
- `schemas.py`
  eksplisiittiset dataset-, asset-, ingest run-, audit event-, room- ja guard-skeemat
- `rooms.py`
  room-registry palveluna
- `guards.py`
  deterministiset `AccessGuard`, `ClassificationGuard`, `AuditGuard` ja `OutputGuard`
- `ingest.py`
  recursive scan, tiedostoluokittelu, hashing ja metadata extraction
- `repository.py`
  SQLite-persistenssi dataset-, asset-, ingest run- ja audit-event-olioille room-scoped kyselyillä
- `api.py`
  ohut API-kerros, joka kokoaa frontendille vain eksplisiittisesti ratkaistut room-skoopit
- `static/`
  mission control -frontend dataset intakea, asset browseria, room registryä ja governance-tilaa varten

## 1. Ensisijainen ajatus

Paras malli ei ole yksi jättiagentti, vaan `federated clone system`:

- yksi yhteinen `hypervisor`
- useita `domain supervisors`
- paljon kapeita `worker agents`
- yksi yhteinen `evidence and policy layer`

Tämä on parempi kuin yhden mallin "kaikkitietävä persona", koska:

- henkilökohtainen data on eri riskitasoilla
- eri analyysit vaativat eri työkalut
- epävarmuus täytyy pystyä näyttämään
- debuggaus on muuten mahdotonta

## 2. Hypervisorin rooli

Hypervisor ei "tiedä kaikkea". Sen tehtävä on:

1. vastaanottaa tehtävä
2. päättää, mitkä roomit ja moduulit saavat osallistua
3. tarkistaa käyttöoikeus, datan luottamustaso ja guard-päätökset
4. kutsua oikeat supervisorit
5. yhdistää tulokset yhdeksi vastaukseksi
6. merkitä epävarmuus, lähteet ja audit trail

Se toimii siis enemmän rehtorina, liikenteenohjaajana ja laatuporttina kuin sisältöasiantuntijana.

## 3. Moduulit

### Identity Core

- pysyvä identiteettimalli
- profiili, arvot, rajat, aikajana
- ei tee johtopäätöksiä yksin

### Memory System

- viestit, muistiinpanot, dokumentit, päiväkirjat, keskustelut
- episodinen muisti
- semanttinen muisti
- muistojen versiointi ja lähdeviittaukset

### Media Lake

- kuvat
- videot
- äänet
- piirrokset
- OCR, transkriptio, embeddingit, formaalit kuvamittarit

### Art and Drawing Lab

- muodollinen analytiikka piirroksille ja visuaaliselle materiaalille
- ei tee pseudodiagnostiikkaa
- mittaa tyyliä, sommittelua, toistuvuutta, väriä, muotoryhmiä ja muutosta ajassa

### Genomics Lab

- raw DNA / varianttidata omassa vyöhykkeessään
- laatukontrolli, varianttien annotointi, geenikonteksti, tunnetut tietokantaviitteet
- ei sekoitu suoraan keskustelumuistiin

### Structural Bio Layer

- proteiini-, kompleksi- tai reittitasoinen rakennetulkinta
- toimii valikoiduille kohteille, ei "koko ihmiselle atomitasolla"
- hyödyntää tunnettuja rakenteita ja ennusteita

### Knowledge Graph

- yhdistää muistot, median, biologian ja julkisen tietämyksen
- pitää relaatiot näkyvinä
- kaikki väitteet sidotaan lähteisiin

### Orchestrator and Evaluation

- tehtävien pilkkominen
- agenttien kutsuminen
- scoring, eval, hallusinaatioiden tunnistus
- hyväksyntä ja debug-kanava omistajalle

## 4. Paras tapa "kouluttaa" moduulit

Useimmiten oikea vastaus ei ole varsinainen mallin hienosäätö ensimmäisessä vaiheessa. Parempi järjestys:

1. määritä skeemat
2. rakenna ingest-putki
3. rakenna retrieval + provenance
4. lisää evaluointidata
5. lisää korjaava palaute
6. vasta sitten harkitse hienosäätöä

Käytännössä moduulit paranevat aluksi eniten näin:

- paremmat datarajat
- paremmat työkalut
- paremmat evaluointitestit
- paremmat käyttöoikeussäännöt

## 5. Supervisor-hierarkia

### Shared hypervisor

- policy engine
- task router
- audit logger
- debugger bridge

### Domain supervisors

- `memory supervisor`
- `media supervisor`
- `genomics supervisor`
- `art supervisor`
- `simulation supervisor`

### Worker agents

- importer
- transcriber
- OCR agent
- image embedder
- drawing metrics worker
- variant annotator
- knowledge linker
- report composer

### Teacher / evaluator agent

Tämä on hyödyllinen lisä. Sen tehtävä on:

- ajaa tarkistuslistat
- vertailla tulosta lähteisiin
- havaita rikkoutuneet putket
- ehdottaa korjauksia supervisorille

Se ei saa yksin kirjoittaa "totuutta", vaan se toimii laadunvalvojana.

## 5.5 Rooms ja guardit

Phase 2A:n tärkeä käytännön sääntö on, että ingest ja indeksikyselyt eivät ohita room-rajoja:

- repository tekee vain room-scoped kyselyjä
- API kokoaa mahdollisen monihuonenäkymän eksplisiittisesti room-listan yli
- `AccessGuard` tarkistaa roolin ja pyydetyn oikeuden
- `ClassificationGuard` sitoo datasetin `classification_level`:n huoneen luokitukseen
- `AuditGuard` varmistaa, että ingest-operaatiot kirjautuvat rakenteisina audit-eventeinä
- `OutputGuard` päättää, palautetaanko frontendille täysi objekti vai summary-only versio

## 6. Miten oma DNA kannattaa kytkeä mukaan

Turvallinen ja käytännöllinen kerrosjako:

1. `raw intake`
   raakadata, tarkistussummat, lähde, formaatti
2. `variant interpretation`
   variantit, geenit, tunnetut annotaatiot, lähteet
3. `pathway mapping`
   geenit -> proteiinit -> reitit -> fenotyyppiset yhteydet
4. `structural questions`
   vain valittuja biomolekyylejä koskevat rakennekysymykset
5. `clone-facing summary`
   käyttöliittymään vain hallitut, epävarmuuden sisältävät tulkinnat

Koko genomin "atomitason simulointi" ei ole realistinen ensimmäinen tavoite. Oikea tavoite on valittujen varianttien biologinen ja rakenteellinen kontekstointi.

## 7. Tärkeimmät käytännön periaatteet

- local-first aina kun mahdollista
- encryption at rest sensitiiviselle datalle
- provenance pakolliseksi
- confidence scores näkyviin
- human override ja `/debug`-oikeus omistajalle
- moduulit saavat vain minimin tarvitsemastaan datasta

## 8. Käyttöliittymän idea

Yksi yhteinen frontend voi toimia hyvin, jos se näyttää eri kerrokset erikseen:

- `mission control`
- `memory`
- `media`
- `art metrics`
- `genomics`
- `structural bio`
- `agent audit`

Phase 2A:ssa mission control näyttää tarkoituksella vain:

- `dataset intake`
- `dataset list`
- `indexed asset browser`
- `room registry`
- `governance guards`
- `audit preview`
- `module status`

Frontendissa tärkeää ei ole vain vastaus, vaan myös:

- mitä moduuleja käytettiin
- mihin lähteisiin vastaus nojaa
- kuinka varma järjestelmä on
- missä kohtaa ihminen voi puuttua peliin
