# KLONE 4A.15: paikallinen tutkimusjärjestelmän terveystarkistus

```bash
PYTHONPATH=src python -m klone.research_health_cli --database research.sqlite
```

Tulostaa yhden JSON-rivin. Paluuarvo 0 = ok, 1 = huomiota vaativa
tilanne, 2 = tietokannan lukuvirhe tai puuttuva skeema.
Tarkistus ei kirjoita tietokantaan. Sopii Termuxiin ja paikallisiin
CI-tarkistuksiin; tulos ei ole käyttöoikeustodistus eikä lupaa
automaattiseen korjaukseen. `pending_audit_delivery` raportoidaan
erillisenä lukuna, eikä yksinään tee tilasta virheellistä.
