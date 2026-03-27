# Phase 2A Handoff

## Tavoite

Phase 2A:n tarkoitus oli rakentaa `file/dataset ingest` + `initial index spine`
supervisor-first arkkitehtuuriin ilman, että järjestelmä muuttuu geneeriseksi asset manageriksi.

Tässä vaiheessa painopiste on:

- paikallisen datan turvallinen ingest
- dataset- ja room-linkitetty asset-indeksi
- eksplisiittinen audit trail
- näkyvä governance mission control -frontendissa

## Toteutettu lopputulos

### 1. Contracts ja skeemat

`contracts.py` on nyt governance-kriittisten literaalien lähde:

- `classification_level`
- `asset_kind`
- `ingest_status`
- `room_status`
- `extraction_status`
- `dedup_status`
- `guard_decision`
- `room_type`

`schemas.py` sisältää eksplisiittiset mallit:

- `DatasetIngestRequest`
- `DatasetRecord`
- `AssetRecord`
- `IngestRunRecord`
- `AuditEventRecord`
- `RoomRecord`
- `GuardResultRecord`
- `GovernanceGuardRecord`
- `MissionControlStatus`
- `IngestStatusResponse`
- `IngestExecutionResponse`

### 2. Huone- ja governance-malli

`rooms.py` toimii room-registry palveluna, ei vain staattisena UI-listana.

Room-olio sisältää:

- `id`
- `label`
- `room_type`
- `classification`
- `supervisor`
- `status`
- `allowed_agents`
- `allowed_roles`
- `retention_policy`
- `permissions`
- `audit_visibility`
- `approval_rules`

Tällä hetkellä registryssä on:

- `public-room`
- `restricted-room`
- `sealed-room`
- `sandbox-room`
- `debug-room`

### 3. Guardit

`guards.py` sisältää deterministiset shellit:

- `AccessGuard`
- `ClassificationGuard`
- `AuditGuard`
- `OutputGuard`

Guardit eivät vielä ole täysi policy engine, mutta ne ovat nyt osa oikeaa request-polkuja.

## Persistenssi

`repository.py` käyttää SQLitea ja alustaa skeeman automaattisesti.

Taulut:

- `datasets`
- `assets`
- `ingest_runs`
- `audit_events`

Repository on vielä yhdessä tiedostossa, mutta vastuuta on jo eroteltu konseptuaalisesti:

- schema bootstrap
- dataset persistence
- asset persistence
- ingest run persistence
- audit persistence
- room-scoped queryt

Tärkeä nykyrajaus:

- repository ei tee implisiittisiä all-room queryjä
- API kokoaa monihuonenäkymän vain eksplisiittisesti ratkaistun room-scope-listan yli

## Actual data flow

### Ingest

`POST /api/ingest/scan`

1. API vastaanottaa `DatasetIngestRequest`-pyynnön.
2. `ingest.py` normalisoi root-polun ja ratkaisee roomin `classification_level`:n perusteella.
3. `AuditService` kirjoittaa `ingest_requested`.
4. `ClassificationGuard` tarkistaa luokituksen ja roomin yhteensopivuuden.
5. `AccessGuard` tarkistaa kirjoitusoikeuden huoneeseen.
6. Dataset luodaan tai päivitetään repositoryn kautta.
7. `ingest_run` luodaan.
8. Jokainen tiedosto:
   - luokitellaan `asset_kind`:iin
   - hashataan `sha256`:lla
   - tallennetaan assetina dataset- ja room-linkityksellä
9. `AuditService` kirjoittaa `dataset_registered|dataset_updated`, `ingest_started` ja `ingest_completed`.
10. API palauttaa typed response -objektin.

### Read routes

Read-polut ratkaisevat ensin room-scope-listan:

- `discover` dataset- ja status-näkymiin
- `read` asset-listaan ja asset detailiin
- `summarize` audit previewyn

Vasta sen jälkeen repositorya kutsutaan room-kohtaisesti.
`OutputGuard` ajetaan ennen frontend-vastetta.

## Käytössä olevat Phase 2A -reitit

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
- `POST /api/ingest/scan`

## Mission control UI

Frontend on read-oriented ja governance-first.

Näkymät:

- `Mission Control Summary`
- `Dataset Intake`
- `Dataset List`
- `Indexed Asset Browser`
- `Asset Detail`
- `Room Registry`
- `Governance Guards`
- `Audit Preview`
- `Modules`
- `Ingest Runs`
- `Agents`
- `Build Phases`

Frontend ei vielä yritä olla laaja hallintapaneeli.
Se on tarkoituksella Phase 2A:n tarkastelu- ja ingest-käyttöliittymä.

## Varmennettu

Paikallisesti varmennettu:

- app käynnistyy puhtaasti
- DB alustuu automaattisesti
- ingest toimii oikealle paikalliselle kansiolle
- audit-eventit syntyvät
- room enforcement toimii
- root HTML + static assetit palvelevat uuden mission control -rakenteen

## Tietoiset placeholderit

Ei vielä toteutettu:

- Memory Core `Event` / `Entity` / `Episode`
- Art and Drawing Lab -mittarien varsinainen analyysimoottori
- Genomics intake sandboxin formaattikohtaiset putket
- Constitution Layer -arvojen muuttaminen tai versionhallinta
- OCR / transkriptio / embeddings
- taustajobit tai queue
- DB-pohjainen room-hallinta
- syvempi approval workflow

## Suositeltu seuraava askel

Luontevin jatko tästä on Phase 2B:

- `Event`
- `Entity`
- `Episode`

Tämä kannattaa rakentaa nykyisen dataset + asset + audit + room -rungon päälle, ei sen ohi.
