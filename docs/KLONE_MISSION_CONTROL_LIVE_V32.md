# KLONE v3.2 – Mission Control Live Observer (laboratorioversio)

2026-11-24. Perustana PR #202 / `8b649bd488d158ec036524f1336d3c1f465d626a`.

## Toteutettu

- `mission_control_live_v32.py` kysyy vain kiinteää listaa **IPv4-loopbackin** palveluja. Ei DNS-hakuja, yleistä porttiskannausta, mielivaltaisia URL-osoitteita, evästeitä, kirjautumista, HTTP-uudelleenohjausten seuraamista tai tausta-ajastimia.
- Tuetut portit: pää-API 8000 (`/api/health`), next-API 8001 (`/api/health`), tilapalvelu 8010 (`/status.json`), Mission Control UI 8011 (`/`), chat UI 8012 (`/`) ja recovery-tilapalvelu 8020 (`/status.json`). Muuta URL-osoitetta tai porttia ei hyväksytä käyttäjän syötteenä.
- Tarkistus on **erikseen käynnistettävä** `--probe-local`-valinnalla. Ei avaa KLONEn sisäistä tuotanto-APIa eikä muokkaa mitään palvelua.
- Yhden pyynnön aikakatkaisu oletuksena 750 ms; 100–3000 ms sallittu. API:n JSON-vastauksesta luetaan enintään 8192 tavua. UI:n HTML-sisältöä ei lueta. JSON-parsinta torjuu kaksoisavaimet ja ei-äärelliset arvot. HTTP 302, 401 ja 500 eivät muutu onnistuneiksi terveystarkistuksiksi.
- Näyttää paikalliset havaintotilat `reported_ok_unattested`, `reachable_unverified`, `unverified` ja `unavailable`. Palvelinversiota, tietokantapolkua, otsakkeita ja raakatietoa ei kopioida raporttiin.
- `build_live_mission_control_review()` **laskee oikean v3.1-raportin uudelleen alkuperäisistä syötteistä ennen yhteydenottoa** ja yhdistää sen live-tilaan. `compose_live_mission_control_review()` on erikseen merkitty pelkäksi valmiin v3.1-raportin digest-tarkastukseksi; se ei yksin varmista syötteiden aitoutta.
- Palvelin voi esittää väärän `status: ok`-arvon. Raportin tiiviste ei tee siitä autentikoitua. HTTP ei todista palvelimen identiteettiä, prosessin oikeuksia, omistajaa, version aitoutta tai tuotantovalmiutta.

## Miten näet puhelimella tilan

Aja erikseen v3.2:n uuden työpuun sisältä:

```sh
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" -m klone.mission_control_live_v32 --probe-local
```

Yhden palvelun lyhyt tarkistus:

```sh
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" -m klone.mission_control_live_v32 --probe-local --service main-api --timeout-ms 500
```

Tämä **ei** käynnistä palvelimia tai nosta itsenäisesti niiden tilaa. Tuloste on raportti vain tarkistushetkellä.

## Testit

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_mission_control_live_v32.py' -v
PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py' -q
```

## SQLite-varoitusten jäljitys erikseen

Aiemmissa Android/Termux-testeissä näkyi `ResourceWarning: unclosed database in <sqlite3.Connection ...>` Starlette-moduulin rivillä. Tämä voi olla vain se kohta, jossa roskienkeruu paljasti varoituksen, ei yhteyden alkuperäinen avausrivi. Repositorion `KloneRepository.connection()` sulkee yhteyden `finally`-osassa, joten sen syyllisyys ei ole osoitettu. **Älä tee satunnaisia korjauksia tuotantotietokantaan tämän perusteella.**

Vahvista lähde ajamalla kohdennettua testiryhmää erillisessä prosessissa, tracemalloc päällä (tässä komennossa ei ole migrations/production-kirjoituksia):

```sh
cd "$HOME/klone-v32-live"
PYTHONPATH="$PWD/src" PYTHONTRACEMALLOC=20 PYTHONWARNINGS=always::ResourceWarning \
"$HOME/klone-next/.venv/bin/python" -m unittest discover -s tests -p 'test_memory_phase_2b3.py' -q
```

Jos testit tarvitsevat venvistä puuttuvaa järjestelmäpakettia, käytä alla kuvattua erillistä testiajon hakupolkuapuria. Varoituspinosta tulee tarkistaa yhteyden **allokaatiokohta**; sitä ei voi päätellä yksin Starlette-viittauksesta.

## Termux-riippuvuuksien luotettava asennus

Edellinen v3.1:n ympäristövirhe johtui siitä, että venv ei nähnyt järjestelmä-Pythonin `cryptography`-asennusta. Pitkäaikainen ratkaisu on tehdä projektin virtuaaliympäristöstä toistettava: asenna `.[test]` sen omaan `.venv`-ympäristöön ja tarkista `cryptography`-tuonti ja Ed25519 ennen testiä. Androidissa `cryptography`-paketin lähdekäännös voi vaatia Termuxin rakennustyökalut, eikä tämän laboratorion asennus muuta automaattisesti käyttäjän nykyistä venv:iä.

Vain väliaikaisena, **ei tuotantoasennuksen** korvikkeena, testiajossa voi lisätä Termuxin järjestelmä-Pythonin `site-packages`-polun ajonaikaisesti (kuten aiemmin v3.1:n onnistuneessa testiajossa). Tämä tulee dokumentoida testiraportissa, koska se vaikuttaa toistettavuuteen.

## Edelleen avoimet turvallisuuskriteerit

- Endpointin luotettu, eristetty identiteetti ja allekirjoitettu tilakuitti.
- Muistin täydellinen transaktio- ja provenienssivarmennus.
- Council72:n agenttikohtaiset resurssi- ja tuloskuittaukset.
- Suojattu Mission Control -web-UI todellisella käyttöoikeuskontrollilla.
- SQLite-yhteysvuodon alkuperän osoittaminen tracemalloc-pinolla.
- Androidin koko regressiosarja uuden commitin perusteella.

Ei uusia julkaisuoikeuksia, muistin kirjoituksia, automaattista agenttiajastusta eikä `main`-haaramuutoksia.
