# KLONE 4A.3: esikatselu ja historiatarkastelu

Uudet paikalliset vain-luku-komennot käyttävät samaa 4A.1-tutkimusydintä
kuin varsinainen tallentava 4A.2-ajo.

## Ennen tallennusta

```bash
PYTHONPATH=src python -m klone.integrated_research_readonly preview \
  --dossier ./dossier.json \
  --sources ./sources.json \
  --source-dir ./public_sources
```

Tulostaa JSON-muodossa tarkistetut lähteet, hypoteesien arvioinnin
ja Markdown-esikatselun. Ei luo tietokantaa.

## Aiemman version tarkastelu

```bash
PYTHONPATH=src python -m klone.integrated_research_readonly inspect \
  --database ./research.sqlite --dossier-id demo --version 1
```

Tulostaa tallennetun version, sen sisäisen eheyden ja Markdown-raportin.
Alkuperäisiä lähdetavuja ei tallenneta dossier-tietokantaan eikä niitä
tarkisteta uudelleen historiatarkastelussa.

## Rajat

Komennot eivät ole verkkopalvelu, käyttöoikeusraja, automaattinen
hyväksyntä tai Mission Control -käyttöliittymä. Käytä vain kuratoituja
julkisia tutkimusaineistoja.
