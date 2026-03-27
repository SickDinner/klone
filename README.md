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

Tässä versiossa Phase 2A on toteutettu rungoksi asti:

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
│     ├─ repository.py
│     ├─ rooms.py
│     ├─ schemas.py
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

## Phase 2A API

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

## Seuraavat järkevät rakennusvaiheet

1. Memory Core: raw `Event`, `Entity` ja `Episode` -mallit sekä timeline retrieval.
2. Art and Drawing Lab: formaalit piirros- ja kuvamittarit ilman pseudopsykologista tulkintaa.
3. Genomics Lab: raw intake, normalisointi, annotation sandbox ja supervisor-gated summaries.
4. Constitution Layer: hitaasti muuttuvat parametrit, provenance ja change logit.
5. Syvempi ingest: OCR, transkriptio, extraction pipeline -tilat ja parempi dedup.
6. Hypervisor eval/debug: laajemmat policy-tracet, approval-flowt ja owner override -näkymät.
