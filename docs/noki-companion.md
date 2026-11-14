# Noki – KLONE-korppikumppani (v0.1)

Tämä vaihe lisää itsenäisen, paikallisessa selaimessa toimivan korppihahmon.
Se ei muuta KLONEn muistia, room-permissioneita, audit-ketjua eikä ingest-logiikkaa.

## Käynnistys ja käyttö

Kun haara on käytössä palvelimen lähdekoodissa, avaa
`http://127.0.0.1:8000/noki` samassa Android-laitteessa, jolla KLONE-palvelin toimii.

- **Puhu:** laitteen selaimen `speechSynthesis` yrittää puhua suomeksi. Äänen saatavuus riippuu asennetuista äänistä.
- **Lennähdä:** Nokin liikeanimaatio.
- **Hiljennä:** keskeyttää puhesynteesin ja aktiivisen puheentunnistuksen.
- **Viesti:** prototyypin paikallisia, avainsanapohjaisia vastauksia; ei kielimallia.
- **Mikrofoni:** erikseen käynnistyvä, selaimen tukema puheentunnistus. Selaimen tunnistus saattaa käyttää etäpalvelua; siksi käyttö on vapaaehtoista ja siitä kerrotaan näkymässä.
- **Valitse / kuvaa teos:** kuvan avaus selaimessa ja paikallinen kirkkauden, kontrastin, värivaihtelun, reunavarianssin ja peilisymmetrian mittaus. Ei tunnista kuvan aiheita. Kuvien kokoa rajoitetaan 12 megaan.
- **Tyhjennä:** poistaa tämän sivun kuvaesikatselun ja vapauttaa väliaikaisen object URL:n.

## Android / Termux – kokeile ilman nykyisen KLONEn vaihtamista

Jos nykyinen kehityskopio on `~/klone-next` ja palvelin käyttää sitä:

```sh
cd ~/klone-next
git fetch origin feat/noki-raven-companion-20261114
git show origin/feat/noki-raven-companion-20261114:src/klone/static/noki.html > src/klone/static/noki.html
```

Tämän jälkeen vanha palvelin tarjoaa prototyypin osoitteessa
`http://127.0.0.1:8000/static/noki.html` ilman uudelleenkäynnistystä,
jos se jo käyttää samaa `src/klone/static`-hakemistoa. Tämä vain kopioi
uuden staattisen tiedoston eikä ota uutta backend-koodia käyttöön.

Jos haluat nimenomaan siistin `/noki`-osoitteen, ota haara myöhemmin
käyttöön hallitusti ja käynnistä palvelin uudelleen.

## Testit

```sh
PYTHONPATH=src python -m unittest tests.test_noki_companion
```

## Turvallisuusrajat / jatkokehitys

- Ei piilotettua kameran tai mikrofonin aktivointia.
- Ei API-avaimia, datan ulosvientiä, taustalatausta tai pysyvää tallennusta.
- Ei pääsyä KLONEn memory-/room-/audit-dataan ilman erillistä, suunniteltua lupamallia.
- Hahmon huoneeseen integrointi, kuvan semanttinen analyysi ja keskustelumalli ovat myöhempiä erillisiä vaiheita; niitä ei pidä väittää toteutetuiksi.
