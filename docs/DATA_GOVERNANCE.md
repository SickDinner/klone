# Data Governance

## Luottamustasot

### Tier 0: Public

- julkiset artikkelit
- avoimet tietokannat
- referenssirakenteet

### Tier 1: Personal

- omat kuvat
- omat piirrokset
- omat äänitteet
- omat dokumentit

### Tier 2: Intimate

- yksityisviestit
- päiväkirjat
- henkilökohtaiset muistot
- suhdehistoria

### Tier 3: Restricted Bio

- raw DNA
- varianttiaineistot
- biotulkinnat
- biomolekyylien syväanalyysit

## Säännöt

1. Tier 3 -data ei saa mennä suoraan yleisen keskusteluagentin käyttöön.
2. Tier 2 -dataa ei saa käyttää ilman eksplisiittistä tehtäväsyytä.
3. Kaikesta ingestistä tallennetaan lähde, aikaleima, tiiviste ja käyttöoikeusluokka.
4. Jokainen moduuli ilmoittaa tarvitsemansa oikeustason etukäteen.
5. Omistajalla on aina audit- ja debug-oikeus koko järjestelmään.
6. Room-scope pitää ratkaista eksplisiittisesti ennen kuin dataa listataan tai luetaan.
7. `AccessGuard`, `ClassificationGuard`, `AuditGuard` ja `OutputGuard` toimivat deterministisinä minimitarkistuksina ennen agenttitason logiikkaa.
8. Audit-eventit kirjataan myös silloin, kun ingest-pyyntö estetään guard-päätöksellä.

## Miksi tämä on tärkeää

Muuten "virtuaalikloonista" tulee nopeasti yksi musta laatikko, joka:

- vuotaa dataa moduulien välillä
- antaa liian itsevarmoja vastauksia
- sekoittaa henkilökohtaisen muistin ja biologiset tulkinnat
- on mahdoton korjata hallitusti

## Minimirajaukset alkuun

- `memory` saa lukea Tier 1-2 dataa
- `genomics` saa lukea Tier 3 dataa
- `art metrics` saa lukea Tier 1 mediaa
- `clone chat` saa oletuksena lukea vain supervisorin hyväksymää johdettua tietoa
- `teacher/evaluator` saa lukea vain tehtävän kannalta tarvittavat artefaktit

## Phase 2A käytännössä

- `dataset intake`
  luo tai päivittää datasetin, ratkaisee sille roomin `classification_level`:n perusteella ja kirjaa audit-eventit
- `asset browser`
  näyttää vain room-scopea, johon pyydetty oikeus sallii pääsyn
- `audit preview`
  näyttää summary-tason audit-eventit room-kohtaisesti
- `sandbox-room`
  on löydettävissä, mutta ei vielä yleisesti `read`-tilassa frontendin asset browserissa
