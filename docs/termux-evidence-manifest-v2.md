# Tulevien testiajojen manifesti v2

V2 lisää tarkat komennot ja vertailtavan ajokontekstin. Se muodostetaan vain
uudelle testiajolle. Vanhoja `run.json`- tai pakettitiedostoja ei päivitetä eikä
niille päätellä puuttuvia ympäristötietoja.

## Uusi ajo erillisessä worktreessä

Aseta `ROOT` tarkistamasi puhtaan worktreen poluksi ja `PY` olemassa olevan
virtuaaliympäristön Pythoniksi. Se voi sijaita worktreen ulkopuolella.
Kerääjä tarkistaa valitun Pythonin erillisellä `-I`-prosessilla. Pytestin täytyy
olla siinä valmiina. Riippuvuuksia ei asenneta automaattisesti.

```bash
ROOT="$HOME/klone-manifest-v2"
PY="$HOME/klone-next/.venv/bin/python"
RUN="$HOME/klone-var/test-runs/v2-$(date +%Y%m%d-%H%M%S)"

PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" \
  "$ROOT/tools/termux_evidence_battery.py" \
  --root "$ROOT" --python "$PY" --output "$RUN" --timeout 240
```

`RUN` ei saa olla olemassa tai sijaita testattavan checkoutin tai `.git`-polun
sisällä. Myös symlinkit ja reparse pointit hylätään. Uusi hakemisto varataan
eksklusiivisesti, ja artefaktit luodaan ilman olemassa olevien tiedostojen
korvaamista. Ennen testejä epäonnistuva ympäristötarkistus ei luo testiajoa.

Kerääjä ajaa syntax-, cognition-, full- ja local_deploy-vaiheet sekä valinnaisen
torch-kokeen, jos sen tiedosto löytyy. Syntax-vaihe kääntää lähteen muistiin,
eikä suorita sitä tai kirjoita bytecodea. Täysi pytest ja Local Deploy käyttävät
`-p no:cacheprovider`-valintaa. Komennot suoritetaan argv-listoina ilman shelliä.
Lokien sisältöä ei käytetä komentoina.

Uuteen ajoon tallentuvat viisi lokia, `run.json` v2 ja samalle uudelle aineistolle
muodostettu alkuperäinen `evidence-packet.json`. Paketin schema pysyy versiona 1;
sen `run_json_sha256` sitoo myös uuden manifestin kontekstitiedot. Kerääjä ei
allekirjoita mitään tai käynnistä palvelinta.

## Tallennettavat tiedot

| Kenttä | Sisältö |
| --- | --- |
| `schema_version` | 2 uudelle ajolle |
| `environment` | Python-versio ja toteutus, alusta, konearkkitehtuuri, kernelin versio, sysconfig-alusta ja asennettujen jakelupakettien versiot |
| `execution.commands` | Jokaisen vaiheen tarkka argv; puuttuvalla torch-kokeella `null` |
| `execution.cwd`, `python_executable`, `python_prefix` | Ilmoitetut suorituspolut |
| `execution.environment_overrides` | PYTHONPATH, bytecode-kielto ja pytestin ulkoisten pluginien automaattilatauksen esto |
| `test_suite_before`, `test_suite_after` | Testitiedostojen ja asetusten sisällöstä laskettu tiiviste ja tiedostomäärä |
| `collector_sha256`, `collector_after_sha256` | Kerääjän ja kontekstimoduulin lähdetiivisteet |
| `environment_after_sha256` | Ajon jälkeisen ympäristökyselyn tiiviste |
| `context_consistent` | Täsmäävätkö ennen–jälkeen-kontekstiväitteet? |
| `comparison_id` | Ympäristön, testiaineiston, kerääjän, komentojen ja aikarajan vertailutunniste |
| `stages.*.capture_complete` | Saatiinko kyseisen vaiheen loki kokonaan talteen rajojen puitteissa? |
| `collection_complete` | Kaikkien vaiheiden talteenoton yhteistila |

Testiaineiston tiiviste kattaa `tests/`-puun tiedostot (cache ja bytecode pois)
sekä olemassa olevat `pyproject.toml`, `pytest.ini`, `setup.cfg`, `tox.ini` ja
juuren `conftest.py`. Se ei ole luettelo kaikista testien mahdollisesti käyttämistä
ulkoisista aineistoista tai käyttöjärjestelmän kirjastoista.

Vertailutunniste normalisoi vain Pythonin suoritettavan tiedoston ja checkoutin
polut. Eri worktreepolut voivat siten täsmätä, mutta eri paketit, testitiedostot,
kerääjä, aikaraja tai komentovalinnat eivät. Ympäristöstä ei tallenneta täydellistä
muuttujalistaa, avaimia, salasanoja, sarjanumeroita tai laitteen identiteettiväitettä.
Muut käyttöympäristön erot voivat silti vaikuttaa testeihin.

Pytestin pluginien automaattilataus on tässä profiilissa pois käytöstä. Se on
tietoinen ero aiempaan profiiliin. `PYTEST_ADDOPTS` ja `PYTEST_PLUGINS` täytyy
tyhjentää ennen ajoa, jotta lisävalinnat eivät jää kirjaamatta.

## Tuloksen ja vertailun rajat

`required_tests_passed` kertoo vaadittujen prosessivaiheiden exit code -tuloksen.
`overall: passed` vaatii lisäksi saman puhtaan commitin, muuttumattoman kontekstin
ja täydellisen talteenoton. Exit code 0 ja vaillinainen loki pysyvät erillisinä
tietoina. Aikarajan ylitys saa kerääjän koodin 124 ja keskeneräisen talteenoton.

Forensics lukee sekä v1- että v2-manifestit. V2-siirtymä voidaan vahvistaa vain
muiden ehtojen lisäksi samoilla vertailutunnisteilla ja täydellisillä, vakaina
pysyneillä konteksteilla. V1:n ja v2:n sekoitus jää epävarmaksi. Vanhojen kahden
v1-ajon vertailun ennestään dokumentoitu ympäristöväite säilyy erillisenä
heikompana vertailutasona.

Myös Pipelinesta muodostettu SQLite-dashboard tarkistaa v2-kontekstit. Saman
lähde/alustaryhmän kaikkien vertailtavien tietueiden täytyy ilmoittaa sama,
vakaa ja kokonaan talteenotettu v2-konteksti. Muut ryhmät näkyvät
`unknown_contexts`-havaintoina, eivät regressioina tai palautumisina.

Luotettavan laitteen identiteetti, historiallisen suorituksen aitous ja
käyttöönoton hyväksyntä eivät seuraa kontekstitiivisteestä. Niiden liput pysyvät
`false`. Forensicsin päätösraportti estää muuttuneen kontekstin tai vaillinaisen
talteenoton etenemisen yhteensopivana läpäisynä myös vihreän CI-viennin kanssa.

## Rajat ja keskeytykset

Enintään 1024 testipuun tiedostoa, 4096 hakemistomerkintää, 1 MiB tiedostolle ja
16 MiB testipuulle. Ympäristökyselyn raja on 32 KiB, manifestin 64 KiB ja
julkaistavan vaihelogin 16 MiB. Vaiheiden väliaikaistiedoston levykokoa ei
kiintiöidä tällä julkaisurajalla; testivaiheella on erillinen aikaraja.

Stdout ja stderr ohjataan samaan väliaikaistiedostoon. Julkaistava loki luetaan
rajatusti muistiin. Ylitys merkitään keskeneräiseksi; aikakatkaisun osittainen
tuloste säilyy rajan puitteissa. Äkillinen keskeytys voi jättää uuden osittaisen
ajohakemiston. Sitä ei ylikirjoiteta uusinnalla, vaan uusi yritys saa uuden nimen.

Android/Termux-tuki vaatii uuden fyysisen laitteen ajon. Work Linuxin tai GitHubin
Windows-testien läpäisy ei ole Android-käyttöönoton hyväksyntä.
