# Klone

`Klone` on modulaarinen, paikallisesti hallittu tutkimus- ja käyttöliittymärunko henkilökohtaiselle "virtuaalikloonille". Tämän version tarkoitus on luoda turvallinen perusta, jossa muistot, media, genomidata, piirros- ja kuvamittaristot sekä myöhemmät simulaatiot voidaan koota saman supervisor-kerroksen alle.

## Mitä tämä on

- Oma käyttöliittymä koko järjestelmälle.
- Supervisor/hypervisor-arkkitehtuuri, jossa jokaisella osa-alueella on oma vastuullinen moduulinsa.
- Luottamustasoihin jaettu tietomalli, jotta raaka DNA, yksityisviestit, kuvat ja äänet eivät elä samassa avoimessa säiliössä.
- Ensimmäinen API + dashboard, josta näkee järjestelmän moduulit, agentit ja toteutusvaiheet.

## Mitä tämä ei vielä ole

- Ei valmis "digitaalinen ihminen".
- Ei kliininen diagnoosityökalu.
- Ei koko genomin atomitason simulaattori.

## Nykyinen vaihe

Nykyinen kanoninen tila on:

- `Phase A1 approved`
- `A1.1 public control-plane seam kickoff complete`
- `A1.2 append-only audit chain foundation complete`
- `A1.3 local blob metadata shell complete`
- `A1.4 local object envelope shell complete`
- `A1.5 public room-scoped object get complete`
- `A1.6 public room-scoped query shell complete`
- `A1.7 public room-scoped blob metadata get complete`

Uutta tässä versiossa:

- `public v1 seam`
  versionoitu `GET /v1/capabilities` nykyisen järjestelmän näkyvyyden päälle
- `request context`
  `request_id`, `trace_id`, `principal` ja `actor_role` kulkevat nyt pyynnön mukana
- `service boundaries`
  `MemoryFacade`, `PolicyService`, `AuditService` ja `BlobService` näkyvät nyt eksplisiittisinä in-process seameina
- `contract shells`
  stable `object`, `query`, `change` ja `blob` contract shellit näkyvät nyt `/v1/capabilities`-vastauksessa
- `append-only control-plane audit chain`
  `/v1/capabilities` kirjoittaa nyt deterministisen audit-ketjun `request_id`, `trace_id`, `principal` ja hash-linkityksen kanssa
- `local blob metadata shell`
  `BlobService` projisoi nyt olemassa olevat `assets`-rivit deterministisiksi `blob:asset:<id>` metadata-recordeiksi ilman uusia `/v1` blob-routeja
- `blob capability mapping`
  `/v1/capabilities` näyttää nyt, että nykyinen blob-shell nojaa olemassa oleviin `/api/assets`- ja `/api/assets/{asset_id}`-read-routeihin
- `local object envelope shell`
  sisäinen local object projector projisoi nyt olemassa olevat dataset-, asset-, memory event- ja memory episode -read-mallit deterministisiksi object envelope -riveiksi ilman uutta julkista object-envelope service seamia
- `object shell readiness`
  `/v1/capabilities` näyttää nyt object-shellin backing-routet ja olemassa olevien governed read-routejen kautta näkyvän readiness-tilan
- `public room-scoped object get`
  `POST /v1/rooms/{room_id}/objects/get` lukee nyt yksittäisen room-scoped object envelope -rivin versionoidun public control-plane seamin kautta ja reuseaa append-only audit chainin
- `public room-scoped query shell`
  `POST /v1/rooms/{room_id}/query` ajaa nyt deterministiset room-scoped `memory_events`- ja `memory_episodes`-haut versionoidun public control-plane seamin kautta ilman semantic searchia tai write-surfacea
- `public room-scoped blob metadata get`
  `POST /v1/rooms/{room_id}/blobs/get` lukee nyt yhden deterministisen asset-backed `blob_id`-metadatarecordin versionoidun public control-plane seamin kautta ilman upload- tai mutation-surfacea

Samalla repo sisältää jo valmiina `Phase 2C.5` read-only delivery surfacen, joka näkyy käyttöliittymässä asti:

- `dataset intake`
  paikallisen kansion skannaus, luokittelu, hashit ja metadata
- `indexed assets`
  tiedostot pysyvinä asset-objekteina dataset- ja room-linkityksellä
- `audit trail`
  ingest-pyynnöt, käynnistykset, valmistumiset ja estot kirjataan audit-eventeinä
- `room registry`
  public/restricted/sealed/sandbox/debug-huoneet supervisor- ja roolirajoilla
- `deterministic guards`
  access, classification, audit ja output toimivat sääntöpohjaisina tarkistuksina
- `mission control UI`
  dataset intake, dataset list, asset browser, room registry, governance guards, audit preview
- `memory explorer UI`
  room-scoped events, episodes, detail-paneeli, provenance lens, context payload ja bounded read-only answer preview
- `memory context APIs`
  read-only context package, LLM context payload ja source-linked answer route

Käytännössä oikea tie on:

1. `genomics intelligence`
   raakadata -> laadunvarmistus -> variantit -> annotaatio -> geenit/proteiinit/reitit
2. `molecular modeling`
   valikoitu proteiini tai variantti -> rakennekonteksti -> simulaatio
3. `memory / media intelligence`
   viestit, kuvat, äänet, päiväkirjat -> aikajana, profiilit, muistiverkko
4. `clone interaction layer`
   käyttöliittymä, agentit, supervisor, arviointi, debuggaus

## Onko hypervisor minä?

Ei pysyvänä tuotantojärjestelmän komponenttina. Voin toimia arkkitehtina, pariohjelmoijana ja debuggerina, mutta oikea `hypervisor` kannattaa toteuttaa omana paikallisena ohjelmistokerroksenaan, jonka säännöt, lokitus, käyttöoikeudet ja debug-oikeudet ovat sinun hallinnassasi.

## Arkkitehtuurin ydin

Järjestelmä jakautuu neljään vyöhykkeeseen:

- `public knowledge`
  julkiset tietokannat, julkaisut, referenssit
- `personal knowledge`
  kuvat, äänet, piirrokset, dokumentit, aikajana
- `sensitive cognition`
  muistot, yksityisviestit, vuorovaikutushistoria, henkilökohtaiset mallit
- `restricted bio`
  genomidata, variantit, rakenteellinen biomallinnus, korkean riskin analytiikka

Supervisor hallitsee liikennettä vyöhykkeiden välillä. Moduulit eivät saa lukea kaikkea oletuksena.

## Projektin rakenne

```text
.
├─ docs/
│  ├─ ARCHITECTURE.md
│  ├─ DATA_GOVERNANCE.md
│  ├─ PHASE_2B_4_CLOSEOUT.md
│  └─ PHASE_2A_HANDOFF.md
├─ src/
│  └─ klone/
│     ├─ __init__.py
│     ├─ api.py
│     ├─ audit.py
│     ├─ blueprint.py
│     ├─ config.py
│     ├─ contracts.py
│     ├─ guards.py
│     ├─ ingest.py
│     ├─ main.py
│     ├─ models.py
│     ├─ request_context.py
│     ├─ repository.py
│     ├─ rooms.py
│     ├─ schemas.py
│     ├─ services.py
│     ├─ v1_api.py
│     └─ static/
│        ├─ app.js
│        ├─ index.html
│        └─ styles.css
└─ pyproject.toml
```

## Käynnistys

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
uvicorn klone.main:app --reload
```

Avaa sitten [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Nykyinen API

- `GET /api/health`
- `GET /api/status`
- `GET /api/blueprint`
- `GET /api/modules`
- `GET /api/agents`
- `GET /api/phases`
- `GET /api/rooms`
- `GET /api/permission-levels`
- `GET /api/governance/guards`
- `GET /api/datasets`
- `GET /api/assets`
- `GET /api/assets/{asset_id}`
- `GET /api/ingest/status`
- `GET /api/audit`
- `GET /api/memory/events`
- `GET /api/memory/events/{event_id}`
- `GET /api/memory/events/{event_id}/provenance`
- `GET /api/memory/entities`
- `GET /api/memory/entities/{entity_id}`
- `GET /api/memory/episodes`
- `GET /api/memory/episodes/{episode_id}`
- `GET /api/memory/episodes/{episode_id}/provenance`
- `GET /api/memory/episodes/{episode_id}/events`
- `GET /api/memory/context/package`
- `GET /api/memory/context/payload`
- `GET /api/memory/context/answer`
- `GET /v1/capabilities`
- `POST /v1/rooms/{room_id}/blobs/get`
- `POST /v1/rooms/{room_id}/objects/get`
- `POST /v1/rooms/{room_id}/query`
- `POST /api/ingest/scan`

## Seuraavat järkevät rakennusvaiheet

1. Seuraava post-A1-vaihe: älä widennä `/v1`-pintaa A1.7:n jälkeen ennen kuin seuraava vaihe on eksplisiittisesti hyväksytty kanonisissa docs-tiedostoissa.
2. Memory Explorerin jatko A1.6:n jälkeen: provenance-UX, kontekstin parempi visualisointi ja selaintason smoke-testit.
3. Art and Drawing Lab: formaalit piirros- ja kuvamittarit ilman pseudopsykologista tulkintaa.
4. Genomics Lab: raw intake, normalisointi, annotation sandbox ja supervisor-gated summaries.
5. Constitution Layer: hitaasti muuttuvat parametrit, provenance ja change logit.
6. Syvempi ingest: OCR, transkriptio, extraction pipeline -tilat ja parempi dedup.
