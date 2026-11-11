# KLONE 4.0: paikallinen tutkimusajo

Ensimmäinen offline-käyttöliittymä olemassa olevalle Integrated Research Corelle.
Ei verkkohakua, käyttäjän tunnistusta, automaattista hyväksyntää tai
henkilökohtaisten DNA-tietojen käsittelyä.

## Tiedostot

`dossier.json`:
```json
{
  "hypotheses": [{"hypothesis_id": "h1", "statement": "Arkistoväite"}],
  "evidence": [{
    "evidence_id": "e1",
    "source_ref": "archive:1",
    "hypothesis_id": "h1",
    "stance": "supports",
    "quality": "medium",
    "rationale": "Lähde mainitsee tapahtuman",
    "dependency_group": "archive"
  }]
}
```

`sources.json`:
```json
{"archive:1": {"file": "record.txt", "media_type": "text/plain"}}
```

Tallenna julkinen lähdetiedosto hakemistoon `public_sources/record.txt`.

## Ajo

```bash
PYTHONPATH=src python -m klone.integrated_research_cli \
  --database ./research.sqlite \
  --dossier-id demo \
  --dossier ./dossier.json \
  --sources ./sources.json \
  --source-dir ./public_sources \
  --output-dir ./results
```

Tulokset: `results/research-report.md` ja
`results/research-result.json`. Tietokantaan lisätään uusi
muuttumaton versio jokaisella onnistuneella ajolla.

## Turvarajat

- Vain käyttäjän eksplisiittisesti määrittelemät paikalliset julkiset lähteet.
- Lähteiden polut rajataan lähdehakemistoon, myös symlinkit tarkistetaan.
- Lähteen enimmäiskoko 2 Mt, dossier-JSON enintään 1 Mt.
- SHA-256 tarkistaa tavujen yhtäpitävyyden, ei historian paikkansapitävyyttä.
- Jo tallennettu versio voi jäädä tietokantaan, jos myöhempi tulosvienti epäonnistuu.
- Komentorivityökalu ei toteuta Hypervisorin tunnistus- ja valtuutusrajaa.
