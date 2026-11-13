# KLONE Evidence Forensics v1

Forensics lukee alkuperäiset testiartefaktit ja kokoaa yhden JSON-raportin sekä
itsenäisen HTML-näkymän. Se yhdistää Artifact Inspectorin, Qualityn, Recovery
Plannerin, Observatoryn, Regression Graphin ja Decision Dossierin nykyiset
rajapinnat. Lokin teksti on aina epäluotettava väite, ei suoritettava ohje.

## Ajo Termuxissa

Käytä erillistä worktreetä ja varmista sen commit. `git fetch` päivittää etäviitteet,
mutta ei nykyistä checkoutia. Komennot eivät käynnistä palvelinta tai koske porttiin
8000. Korvaa `ROOT` tarkistamasi worktreen polulla.

```bash
ROOT="$HOME/klone-forensics-v1"
PY="$HOME/klone-next/.venv/bin/python"
test -d "$ROOT/src/klone" || exit 1
test -x "$PY" || exit 1
test -d "$HOME/klone-var/test-runs" || exit 1
git -C "$ROOT" status --short
git -C "$ROOT" rev-parse HEAD
"$PY" --version

PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" -m unittest discover \
  -s "$ROOT/tests" -p 'test_evidence_forensics.py' -v

OUT="$HOME/klone-var/forensics-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT" || exit 1
PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" \
  -m klone.evidence_forensics \
  --runs-root "$HOME/klone-var/test-runs" \
  --json-output "$OUT/evidence-forensics.json" \
  --html-output "$OUT/evidence-forensics.html"
```

Avaa HTML selaimessa tai valitse JSON Mission Controlin `/evidence`-sivulla.
Molemmat toimivat paikallisesti. JSON-valitsin ei lähetä tiedostoa palvelimelle.
HTML sisältää saman renderöijän ja raportin; se ei tarvitse verkkoyhteyttä.
Selaimessa avattavan JSONin raja on 2 MiB. Suurelle raportille käytä mukana tulevaa
HTML:ää tai pienempää alkuperäisten ajojen joukkoa erillisessä tarkastelussa.

## Mitä raportti erottaa?

| Tieto | Merkitys |
| --- | --- |
| `manifest.state`, `artifacts.*.state` | Löytyminen ja tämän lukukerran tila |
| `readable`, `structure_valid` | Luettavuus ja rakenteen kelvollisuus erikseen |
| `sha256`, `bytes` | Luettujen nykyisten tavujen tiiviste ja määrä |
| `packet.matches_source` | Vastaako olemassa oleva paketti samaa rajattua tilannekuvaa? |
| `stages.*.declared_status`, `declared_exit_code` | Manifestin ilmoittamat tiedot |
| `stages.*.log_evidence` | Lokista tunnistettu yhteenvetoväite ja laskurit |
| `log_supports_claim` | Tukeeko tunnistettu lokiväite manifestin väitettä? |
| `quality.category` | Paikallisen aineiston laatu, ei testihyväksyntä |
| `contradictions` | Esimerkiksi status/exit code tai manifesti/loki-ristiriita |
| `recovery` | Käsin tarkistettava tutkimustoimi |
| `github`, `github_comparison` | Valinnaisen offline-CI-väitteen vertailu |
| `attestation` | Erillinen allekirjoituksen ja käyttäjän valitseman luottamuskartan tarkistus |
| `origin_authenticated` | Aina `false`: v1 ei todenna historiallista alkuperää |
| `test_execution_authenticated` | Aina `false`: lokirivi ei todista suoritusta |
| `deployment_approval` | Aina `false`: raportti ei hyväksy käyttöönottoa |

Kolmiarvoisissa tarkistuksissa `true` tarkoittaa paikallisesti todettua ehtoa,
`false` todettua puutetta tai ristiriitaa ja `null` puuttuvaa tarkistusnäyttöä.
Yleistä kaikki-onnistui-lippua ei ole.

`verified` tarkoittaa vain paikallisen tilannekuvan eheyttä. Myös epäonnistuneen
testin aineisto voi olla eheä. Sisällöllinen ristiriita muuttaa luokan
`contradictory`:ksi, vaikka paketin tiivisteet täsmäisivät.
Alkuperäinen manifestiväite säilyy `observatory_status`-kentässä, mutta
`decision_input_status` estää tunnetun ristiriidan etenemisen CI-vertailun tai
päätösraportin yhteensopivana testinäyttönä.

## Lokien tulkinnan rajat

- Tunnistetaan pytestin lopulliset yhteenvetorivit sekä unittestin `Ran …` / `OK`
  ja `FAILED (…)` -yhteenvedot. Viimeinen tunnistettu yhteenveto on lokin ilmoitus.
- Tyhjä `syntax.log` jää tuntemattomaksi. Se ei yksin osoita onnistumista tai
  epäonnistumista. Compileall voi onnistua kirjoittamatta mitään.
- Valinnaisen torch-vaiheen tunnettu puuttumisviesti on `not_present`, ei
  läpäisty testi. Ristiriita läpäisyväitteen kanssa kirjataan.
- Satunnaisesta tekstistä tai tiedoston koosta ei päätellä tulosta.
- Analyysi ei suorita komentoja, lue lokissa nimettyjä polkuja tai noudata tekstin
  ohjeita. Näkymä käyttää `textContent`:ia, ei lokitekstin HTML-tulkintaa.

## Siirtymien vertailu

Observatoryn hakemistonimijärjestys säilyy. Se ei takaa tapahtumajärjestystä.
Paikallinen `passed -> failed` vahvistetaan vain, kun molempien paketti vastaa
lähteitä, aikaväitteet ovat järjestyksessä, ympäristöväitteet ovat samat ja
ei-tyhjät, exit codet täsmäävät ja lokit tukevat kyseisen vaiheen väitteitä.
Kummassakaan ajossa ei saa olla ristiriitaa.

`passed -> unknown` pysyy epävarmana. `failed -> passed` on vastaavilla ehdoilla
paikallinen palautuminen. `confirmed_regression_transitions` laskee vaiheiden
siirtymiä, ei automaattisesti uusia ohjelmistovikoja tai syy-yhteyksiä.
V1 ei varmista, että kaksi saman nimistä vaihetta suoritti täsmälleen samat testit.
Sama ympäristöväite on vertailun edellytys, ei riippumattomasti varmennettu fakta.

Historiallinen `termux_evidence_battery.py` ei tallentanut ympäristöväitettä.
Sellaisesta aineistosta ei jälkikäteen keksitä ympäristöä tai hyväksyntää.

Uusien ajojen [manifesti v2](termux-evidence-manifest-v2.md) tallentaa tarkat
komennot ja vertailutunnisteen. V2-ajoilla myös sen täytyy täsmätä. Ajon aikana
muuttunut konteksti tai keskeneräinen lokien talteenotto estää päätösraportin
yhteensopivuuspolun. V1/v2-sekavertailua ei vahvisteta. Syntax-vaiheen uusi
rakenteinen yhteenveto tunnistetaan edelleen epäluotettavana lokiväitteenä.

## Valinnainen CI-vienti

`--github-ci /polku/ci-by-commit.json` lukee enintään 2 MiB JSON-olion. Sen avaimet
ovat kokonaisia commit-SHA-arvoja ja arvot nykyisen GitHub CI Bridgen normalisoimia
raportteja (`commit`, `workflow`, `conclusion`, `run_id`, `run_status`). Käytä
työnkulun oikeaa nimeä `KLONE regression guard`. Yksittäinen vienti täytyy siis
asettaa oman commit-avaimensa alle. CLI ei hae verkosta mitään.

Puuttuva CI on `unavailable`; epäonnistunut CI pysyy epäonnistumisväitteenä.
CI:n läpäisy ilman paikallista Android-evidenssiä ei vahvista Android-testiä.
Myös yhteensopiva CI-vienti vaatii alkuperän erillisen tarkistamisen.

[CI Bridgen turvallinen vienti](evidence-ci-export.md) tuottaa suoraan tämän
commit-kartan `--forensics-map`-valinnalla. Ajon tunnistetiedot ja listauksen
tila säilyvät raportissa. Eksplisiittisesti keskeneräinen ajo tai puutteellinen
listaus estää yhteensopivuuspolun. Job-matriisin tarkistus on erillinen tieto;
workflow-tuloksesta ei päätellä Android-suoritusta.

## Valinnainen erillisen allekirjoituksen tarkistus

Forensics voi tarkistaa jo olemassa olevan paketin erillisen
[Ed25519-allekirjoituksen](evidence-attestation-v1.md) samalla lukukerralla.
Se käyttää täsmälleen samaa pakettioliota kuin lähdeaineiston vertailu. Pakettia
ei avata allekirjoitusta varten uudelleen.

Lisää tavalliseen Forensics-komentoon molemmat valinnat:

```bash
--attestations "$ATTESTATIONS" --trusted-keys "$TRUSTED_KEYS"
```

Polut ovat itse tarkistamiasi JSON-tiedostoja lähdejuuren ulkopuolella.
`ATTESTATIONS` on suora olio: ajohakemiston nimi -> olemassa oleva erillinen
allekirjoitusolio. Ajonnimen muoto on `[A-Za-z0-9][A-Za-z0-9_.-]{0,199}`.
`TRUSTED_KEYS` on witness-tunniste -> 64 pientä heksamerkkiä sisältävä
Ed25519-julkinen avain. Varmista avaimen sormenjälki toisessa luotetussa kanavassa.
Paketti, loki tai allekirjoitustiedosto ei voi itse lisätä luotettua avainta.

Allekirjoituskartan raja on 2 MiB / 1000 ajoa ja luottamuskartan 128 KiB /
1000 avainta. Syötteet luetaan samalla rajatulla no-follow-lukijalla kuin muutkin
JSONit. Raportti ei saa korvata kumpaakaan syötettä. CLI ei luo allekirjoituksia,
avaimia tai historiallisia paketteja eikä asenna valinnaista cryptography-backendiä.
Ilman valintoja allekirjoituksia tai avaimia ei etsitä ajohakemistoista.

`attestation.state` erottaa puuttuvan syötteen (`not_provided`), puuttuvan tai
virheellisen paketin (`packet_unavailable`), kelvollisen luotetun avaimen
allekirjoituksen (`verified_signature`), hylkäyksen (`rejected`) ja puuttuvan
backendin (`verification_unavailable`). `reason` antaa tarkemman syyn.
Tuntemattomiin ajonnimiin liitetyt allekirjoitukset näkyvät
`attestation_policy.unmatched_run_names`-listassa. Niitä ei arvata toiselle ajolle.

`attestation_policy` tallentaa molempien jäsennettyjen syötteiden kanonisen JSONin
SHA-256-tiivisteet. Ne ovat tämän analyysin syötesormenjälkiä, eivät tiedoston
alkuperän tai historiallisen luottamuksen todisteita. Julkisia avaimia tai
allekirjoitusolion sisältöä ei kopioida raporttiin; avaimen sormenjälki ja
witness-tunniste näkyvät erillisinä tietoina.

Kelvollinen allekirjoitus voi esiintyä yhdessä muuttuneiden lähdelokien,
epäonnistuneen testin tai keskeneräisen v2-talteenoton kanssa. Se ei muuta
laatuluokkaa, vertailukelpoisuutta, CI-vertailua tai päätösraporttia.
`origin_authenticated`, `device_identity_verified`, `test_execution_authenticated`
ja `deployment_approval` pysyvät `false`. Forensicsin exit code 0 tarkoittaa
raportin muodostumista; se ei lupaa kelvollisia allekirjoituksia tai testien läpäisyä.
Ajonnimikartta valitsee tarkistettavan paketin; allekirjoitusprotokolla ei sido
hakemistonimeä tai estä replayta eikä anna luotettua aikaleimaa.

Näkymä näyttää raportin tarkistustulokset tekstinä. Selain ei tee uutta
kryptografista tarkistusta eikä ota käyttäjän avaamaa raporttia luottamusjuureksi.

## Luku- ja kirjoitusrajat

Enintään 1000 juurihakemiston merkintää, 64 KiB manifesti, 16 MiB loki, 1 MiB
paketti ja yhteensä 128 MiB luettuja lähdetavuja. Ylitys näkyy raportissa;
juurihakemiston merkintärajan ylitys keskeyttää ajon. Lokien polut ovat kiinteät.
Tuntemattomia paketin tiedostopolkuja ei seurata.

Symlinkit ja Windowsin reparse pointit hylätään. POSIX-luku kulkee lukituilla
hakemistodeskriptoreilla ja `O_NOFOLLOW`:lla. Siirrettävä vaihtoehto tarkistaa
tiedoston identiteetin ennen ja jälkeen luvun. Muuttuva tiedosto hylätään.

Oletuspaketti on `evidence-packet.json`. Jos se puuttuu, yksi `packet`-niminen
JSON-ehdokas voidaan tarkistaa. Useita ehdokkaita ei arvata oikeaksi paketiksi.
Puuttuvaa historiallista pakettia ei luoda.

Raportit saa kirjoittaa vain lähdejuuren ulkopuolelle. Kohteiden täytyy olla
erilliset eivätkä ne saa korvata CI- tai allekirjoituksen tarkistuksen syötteitä. Kukin raporttitiedosto korvataan
atomisesti; kahden tiedoston julkaisu ei ole yhteinen transaktio. CLI:n virhettä
ei saa tulkita valmiiksi raporttipariksi. Alkuperäisiä lähteitä ei kirjoiteta.
Sama muuttumaton syöte ja samat rajat tuottavat saman JSONin ja analyysitiivisteen.

## Varmistus

Forensics-testit käyttävät vain synteettisiä tilapäishakemistoja. Ne kattavat
puuttuvat, tyhjät, suuret ja virheelliset lähteet, ristiriidat, symlinkit,
polkutraversoinnin, siirtymät, CI-puutteet, vahingollisen lokitekstin,
deterministisen raportin ja lähteiden tavujen sekä mtime-arvojen säilymisen.

Käyttäjän 19 Android-ajon yhteenvetoluvut ovat erillistä raportoitua evidenssiä.
Niiden alkuperäisiä tiedostoja ei ollut Work-ympäristössä. Niiden sisällöllinen
forensiikka täytyy ajaa yllä olevalla komennolla Androidissa.
