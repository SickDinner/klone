# KLONE 4A.12: paikallinen Mission Control -tilanäkymä

Käynnistys (vain kehittäjän omalla koneella):

```bash
PYTHONPATH=src python -m klone.mission_control_status_ui --database research.sqlite --port 8767
```

Avaa `http://127.0.0.1:8767/` samassa laitteessa.

Näkymä listaa kesken jääneet tutkimusajot, valmistuneet ajot
ilman auditointitapahtumaa ja odottavat auditointitoimitukset.
Tietokanta avataan vain luku -tilassa. HTML-tuloste escapetaan.

**Turvallisuus:** HTTP-palvelin kuuntelee vain osoitetta
`127.0.0.1`, tarkistaa Host- ja Origin-otsakkeet eikä sisällä
tunnistusta. Se on tarkoitettu vain paikalliseen kehitykseen,
ei verkkoon, julkiseen palvelimeen tai monikäyttäjäkäyttöön.
Ei automaattista tutkimuksen palautusta tai julkaisemista.
