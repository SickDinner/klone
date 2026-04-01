# Next Steps Assessment

Status: historical non-canonical assessment; superseded by completed `Phase 2C.5`, `Phase A1.9`, `Phase G1.5`, and `Phase V1.2` on 2026-04-01  
Date: 2026-03-28

Do not use this file as the current handoff or approval source.

Canonical phase control remains in:

- `docs/PROJECT_STATUS.md`
- `docs/HANDOFF_CURRENT.md`
- `docs/ROADMAP.md`

## Tavoite

Tämä selvitys kokoaa, mitä projektissa on jo valmiina, missä nykyinen käyttöliittymä jää jälkeen toteutetusta backendistä, ja mikä on järkevin seuraava etenemisjärjestys.

Tämä arvio kuvasi repoa ennen kuin `Memory Explorer`, julkinen read-only delivery surface, `A1.9`, `G1.5`, ja `V1.2` suljettiin kanonisesti valmiiksi. Se säilytetään historiallisena taustana, mutta monet sen alla olevista suosituksista on sittemmin toteutettu tai korvattu uudemmilla kanonisilla docseilla.

Arvio perustuu erityisesti näihin kohtiin:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/PHASE_2A_HANDOFF.md`
- `docs/PHASE_2B_4_CLOSEOUT.md`
- `src/klone/api.py`
- `src/klone/memory.py`
- `src/klone/static/index.html`
- `src/klone/static/app.js`
- `tests/`

## Nykytila lyhyesti

Projektissa on jo toimiva `Phase 2A` mission control -käyttöliittymä:

- dataset intake
- dataset list
- indexed asset browser
- asset detail
- room registry
- governance guards
- audit preview
- modules / agents / build phases

Tämä UI on oikeasti kytketty FastAPI-palvelimeen eikä ole pelkkä mockup.

Samaan aikaan backend on edennyt `Phase 2B` memory-tasolle pidemmälle kuin käyttöliittymä näyttää:

- `GET /api/memory/events`
- `GET /api/memory/events/{event_id}`
- `GET /api/memory/entities`
- `GET /api/memory/entities/{entity_id}`
- `GET /api/memory/episodes`
- `GET /api/memory/episodes/{episode_id}`
- `GET /api/memory/episodes/{episode_id}/events`

Lisäksi `MemoryService` sisältää jo sisäiset read-only context-paketit:

- `assemble_context_package(...)`
- `prepare_llm_context_payload(...)`

Käytännössä perusta ei ole enää vain runko. Data ingest, audit, memory-readit, correction-state ja provenance-logiikka ovat jo olemassa.

## Keskeinen havainto

Tärkein nykyinen pullonkaula ei ole backendin puute vaan tuotepinnan epäsynkka:

1. UI näyttää vielä vain `Phase 2A` mission controlin.
2. Backendissä on jo memory-kerros, jota UI ei hyödynnä.
3. Blueprint-status ei täysin vastaa toteutunutta koodia, koska `memory-core` näkyy edelleen `planned`-tilassa, vaikka memory API:t ja testit ovat jo olemassa.

Siksi seuraavan vaiheen paras hyöty tulee todennäköisimmin siitä, että jo rakennettu memory-kerros tehdään näkyväksi, selattavaksi ja turvallisesti rajatuksi käyttöliittymässä.

## Mitä on jo varmennettu

- Sovellus palvelee root-dashboardin ja static-assetit onnistuneesti.
- `uvicorn`-käynnistys + `GET /`, `GET /api/health`, `GET /api/status`, `GET /api/rooms` toimivat paikallisesti.
- Koko testisuite meni läpi: `33` testiä, kaikki vihreänä.

Tämä tarkoittaa, että seuraavat askeleet voivat painottua laajennukseen ja näkyvyyteen, eivät pelkkään vakautukseen.

## Suositeltu prioriteettijärjestys

### 1. Rakenna `Memory Explorer` UI

Tämä on paras seuraava askel.

Miksi:

- backend tarjoaa jo memory list/detail -reitit
- projektin roadmap sanoo, että `Phase 2B` on seuraava luonnollinen vaihe
- käyttäjälle näkyvä hyöty kasvaa paljon ilman, että täytyy keksiä uutta domain-logiikkaa alusta

Minimisisältö:

- uusi `Memory`-osio nykyiseen UI:hin
- room-valitsin
- event list
- episode list
- detail-paneeli valitulle eventille tai episodille
- filtterit:
  - `status`
  - `event_type`
  - `episode_type`
  - `ingest_run_id`
  - `include_corrected`

Miksi juuri tämä:

- suurin osa tarvittavasta datasta on jo olemassa
- toteutus on enimmäkseen frontend- ja kevyt API-integraatiotyö
- tekee memory-kerroksesta konkreettisen eikä vain sisäisen backend-ominaisuuden

### 2. Tee read-only `Context Package` näkyväksi API:ssa

Tämä on toiseksi paras askel heti Memory Explorerin jälkeen tai sen kanssa samaan sprinttiin.

Nyt `MemoryService` osaa jo rakentaa:

- deterministic context package
- read-only LLM context payload

Mutta näille ei näy julkista API-pintaa.

Hyvä jatko olisi lisätä esimerkiksi:

- `GET /api/memory/context/event/{event_id}?room_id=...`
- `GET /api/memory/context/episode/{episode_id}?room_id=...`
- tai yksi yhdistetty `GET /api/memory/context`

Tämän hyöty:

- frontend voi näyttää provenance- ja context-paketin sellaisenaan
- myöhempi clone/chat-kerros saa valmiin turvallisen read-only syötteen
- järjestelmän “mitä dataa oikeasti käytettiin” -läpinäkyvyys paranee paljon

### 3. Päivitä blueprint ja status vastaamaan toteutusta

Tämä on pieni mutta tärkeä korjaus.

Tällä hetkellä `blueprint.py` kertoo `memory-core`-moduulin olevan `planned`, vaikka repository, API, service-kerros ja testit osoittavat sen olevan jo vähintään read-only käytössä.

Kannattaa päivittää:

- `memory-core` status
- mahdollisesti `build phase` -selitteet
- README / handoff-dokumenttien nykytilakuvaus

Miksi tämä kannattaa tehdä aikaisin:

- estää väärän tilannekuvan
- helpottaa roadmap-päätöksiä
- tekee UI:ssa näkyvästä moduulistatuksesta rehellisemmän

### 4. Lisää oikeat UI-smoke-testit

Nyt testit kattavat hyvin repository-, service- ja API-logiikkaa, mutta eivät juuri käyttöliittymän käyttäjäpolkuja.

Nykytilan aukot:

- ei browser-tason testiä mission control -näkymälle
- ei testiä memory-UI:lle, koska sitä ei vielä ole
- HTTP-smoke-testit ovat pääosin request-funktiokutsuja, eivät selaintason flow’ta

Suositus:

- lisää vähintään yksi selain- tai HTTP-smoke-polku
- tarkista ainakin:
  - root latautuu
  - mission control hakee datan
  - ingest-formin virhetila näkyy oikein
  - memory-näkymä toimii, kun se lisätään

Jos pysytään FastAPI:n `TestClient`-tasolla, dev/test-riippuvuuksiin kannattaa lisätä `httpx`.

### 5. Paranna ingest-UX:ää ennen uusia domain-moduuleja

Nykyinen ingest toimii, mutta UI on vielä melko suora tekninen paneeli.

Seuraavat parannukset olisivat hyödyllisiä:

- paremmat virheviestit polku- ja permission-ongelmiin
- näkyvä duplicate-/unchanged-yhteenveto
- mahdollisuus klikata datasetistä suoraan sen assetteihin
- asset detailiin helpommin luettava provenance / metadata -esitys
- ingest-runien tilaerot selkeämmin näkyviin

Tämä ei ole yhtä tärkeä kuin Memory Explorer, mutta parantaa heti käytettävyyttä.

## Mitä en tekisi seuraavaksi ensimmäisenä

### En aloittaisi vielä Art / Genomics / Constitution -kerroksista

Syyt:

- niille on roadmapissa paikka, mutta ne eivät vielä hyödynnä yhtä paljon jo valmista koodia kuin memory/UI-synkka
- uusi domain-logiikka kasvattaa pinta-alaa nopeasti
- nykyisessä tilanteessa isoin tuotearvo saadaan näkyvyydestä, ei uudesta tutkimusmoduulista

### En tekisi vielä write-enabled clone chat -kerrosta

Syyt:

- memory- ja context-read-polut kannattaa tehdä ensin täysin näkyviksi ja audit-kelpoisiksi
- read-only context payload on jo olemassa juuri tätä välivaihetta varten
- write-polku kasvattaa turvallisuus- ja governance-paineita selvästi enemmän

## Konkreettinen toteutusjärjestys

Jos tämä vietäisiin käytäntöön seuraavassa kehitysjaksossa, suosittelen tätä järjestystä:

1. Lisää UI:hin `Memory Explorer` nykyisen mission controlin rinnalle.
2. Kytke explorer olemassa oleviin `/api/memory/...` read-reitteihin.
3. Lisää context package -API read-only muodossa.
4. Näytä context/provenance explorerissa.
5. Päivitä blueprint-status ja dokumentaatio vastaamaan toteumaa.
6. Lisää vähintään yksi oikea UI-smoke-testi.
7. Palaa ingest-UX:n hiomiseen.

## Käytännön toteutuspaketit

### Paketti A: Nopein näkyvä hyöty

- Memory Explorer UI
- memory list/detail -integraatio
- blueprint-status päivitys

Tämä on paras, jos tavoitteena on saada käyttöliittymä näyttämään selvästi valmiimmalta nopeasti.

### Paketti B: Paras arkkitehtuurinen jatko

- context package API
- LLM context preview UI
- provenance- ja correction-tilan näkyvä esitys

Tämä on paras, jos tavoitteena on valmistella turvallista clone/chat-kerrosta.

### Paketti C: Tuotteen viimeistely

- ingest-UX parannukset
- UI-smoke-testit
- dokumentaation synkkaus

Tämä on paras, jos tavoitteena on tehdä nykyisestä rungosta vakaampi demo tai sisäinen v1.

## Suora suositus

Jos pitäisi valita vain yksi seuraava työ:

`Rakenna Memory Explorer UI olemassa olevien memory-read API:en päälle.`

Perustelu:

- korkein näkyvä hyöty
- pienempi riski kuin kokonaan uuden domainin avaaminen
- käyttää jo toteutettua ja testattua backend-työtä
- siirtää projektia aidosti kohti roadmapin `clone interaction layer` -vaihetta

## Tiivistelmä yhdellä rivillä

Projektin seuraava paras askel ei ole uuden datadomainin rakentaminen, vaan jo toteutetun memory-kerroksen nostaminen näkyväksi read-only käyttöliittymäksi ja context-API:ksi.
