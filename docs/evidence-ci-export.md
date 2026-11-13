# GitHub CI -viennin turvallinen käyttö

CI Bridge hakee vain `SickDinner/klone`-repositorion valitun kokonaisen
commit-SHA:n workflow-ajot GitHubin virallisesta HTTPS-rajapinnasta. Se ei aja,
uusi tai yhdistä mitään. Julkinen haku ei tarvitse tokenia. Valinnainen
`GITHUB_TOKEN` luetaan ympäristöstä eikä sitä tallenneta vientiin tai lokiin.

HTTP-uudelleenohjaukset hylätään ennen uutta pyyntöä. Vastausta luetaan enintään
2 MiB + yksi rajantarkistustavu. JSON luetaan tiukasti: duplikaattiavaimet,
ei-finiittiset luvut ja muut kuin oliot hylätään. Verkkovirheistä raportoidaan
tyyppi ilman mahdollista tunnistetietoa sisältävää palvelinviestiä.
15 sekunnin timeout koskee estävää verkko-operaatiota, ei koko operaation
riippumatonta seinäkelloaikarajaa.

## Valinta ja epävarmuus

Enintään 100 ajon listan pitää olla kokonainen (`total_count` vastaa luettua
määrää). Sivutusta ei arvata täydelliseksi. Viejä valitsee korkeimman run ID:n
vastaavista ajoista. Repository, nimi `KLONE regression guard`, workflow-polku
`.github/workflows/klone-regression.yml`, run ID, yritys, tapahtuma ja tilat
tarkistetaan. Epäselvä tai virheellinen vastaava ajo estää viennin; vanhaan
vihreään ajoon ei palata. Keskeneräisen ajon tulos on tuntematon, vaikka
syötteessä olisi irrallinen success-väite.

Tämä ei hae job-matriisia, artefaktien attestaatioita tai testilokeja.
`job_matrix_verified` pysyy `false`. GitHubin `head_sha` on ajotietueen väite;
esimerkiksi PR-ajo voi testata yhdistämisviitettä. Tällä ei varmenneta testatun
checkoutin sisältöä, Android-suoritusta, historiallista alkuperää tai
käyttöönoton hyväksyntää. `origin_authenticated` ja `deployment_approval`
pysyvät `false`.

## Uusi vienti ja Forensics

`--output` saa olla vain uusi tiedosto lähdejuuren ja `.git`-hakemistojen
ulkopuolella. Oletuksena suojattu lähdejuuri on `~/klone-var/test-runs`;
anna `--runs-root`, jos käytät muuta juurta. Tarkistus tehdään ennen verkkohakua
ja kirjoitus varataan lopuksi eksklusiivisesti. Symlinkit ja reparse pointit
hylätään. POSIXissa emohakemistot lukitaan deskriptoreilla. Siirrettävässä
vaihtoehdossa käytetään polkutarkistuksia ja eksklusiivista luontia.

Jo olemassa oleva tai haun aikana ilmestynyt tiedosto säilyy. Keskeytynyt
kirjoitus voi jättää uuden osittaisen vientitiedoston. Sitä ei poisteta tai
ylikirjoiteta automaattisesti; uusi yritys tarvitsee uuden nimen.

`--forensics-map` tuottaa suoraan Forensicsin `--github-ci`-syötteeksi sopivan
commit -> CI-väite -olion. Ilman valintaa yhden CI-olion aiempi vientimuoto säilyy.

```bash
COMMIT="$(git -C "$ROOT" rev-parse HEAD)"
CI="$HOME/klone-var/ci-$(date +%Y%m%d-%H%M%S)-$$.json"
PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" \
  -m klone.evidence_github_bridge --commit "$COMMIT" \
  --runs-root "$HOME/klone-var/test-runs" --forensics-map --output "$CI"
```

Viejän exit code 0 tarkoittaa valitun workflow-ajon ilmoitettua läpimenoa.
Exit code 2 voi tarkoittaa talletettua epäonnistunutta tai keskeneräistä ajoa,
tai virhettä, jolloin vientiä ei synny. Tarkista tiedoston syntyminen ja sisältö.
Forensicsissa `--github-ci "$CI"` käyttää vientiä paikallisesti eikä tee verkkohakua.
Se vertaa vain samalle commit-avaimelle löytyvää väitettä.

Myös Cross Environment- ja One Command -CLI:iden tulostiedostot ovat nyt
uusia tiedostoja: ne eivät korvaa aiempaa raporttia tai lähdesyötettä.
Cross Environment lukee enintään 128 KiB per JSON tiukalla no-follow-lukijalla.
Forensics estää eksplisiittisesti keskeneräisen ajon, puutteellisen listauksen,
väärän repositoryn tai väärän workflow-polun yhteensopivuuspolun.
Vanhojen vientien puuttuvia metatietoja ei täydennetä jälkikäteen; niiden
vertailu koskee edelleen vain heikompia ilmoitettuja väitteitä.

Lähteet: [GitHub workflow runs API](https://docs.github.com/en/rest/actions/workflow-runs)
ja [Python urllib.request](https://docs.python.org/3/library/urllib.request.html).
