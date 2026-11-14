# Neuvoston koesopimus ja alkuperäiseen aineistoon sidottu havainto

Testisarjan, kerääjän, tarkan alustan ja ohitusrajojen valinnaiset lukitukset
kuvataan [tarkempien koerajojen ohjeessa](council72-contract-limits.md).

Tavoite ja hyväksymiskriteerit kirjataan uuteen sopimustiedostoon ennen ajoa.
Sopimus sitoo tarkan commitin, 1–16 yksilöllistä väitettä, vaihetestin,
Work-/Android-ympäristön ja pytestin läpäisseiden testien vähimmäismäärän.
Kaikkien valittujen samaan commitiin ja ympäristöön kuuluvien ajojen on
täytettävä kriteeri. Yksi yhtäpitävä epäonnistuminen riittää `not_met`-tilaan.
Puuttuva tai ristiriitainen näyttö jää `unknown`-tilaan. Domain-kenttä on
tehtävän reititysluokka, ei väite koko osa-alueen testikattavuudesta.

## Sopimuksen sidonta testiajoon

`council72_contract` muodostaa kanonisen sopimuksen ja sen SHA-256:n.
Uusi vienti ei korvaa aiempaa. Nykyinen `termux_evidence_battery.py` hyväksyy
valinnan `--experiment-contract`. Se tarkistaa sopimuksen ja kohdecommitin
ennen ensimmäistä testiä ja kirjaa loogisen sopimustiivisteen sekä tiedoston
tavutiivisteen v2-manifestin execution-osaan. Testien jälkeen tavutiiviste
luetaan uudelleen. Muutos, katoaminen tai lukukelvottomuus estää yhtäpitävän
kontekstin ja vihreän kokonaisarvion; kerätyt lokit ja manifesti säilyvät.
Kokeen sopimus vaikuttaa myös execution comparison_id -arvoon.

Vanha ajo ilman sopimusta säilyy tuettuna nykyisissä työkaluissa. Sen
historiallista manifestia ei täydennetä eikä sitä esitetä ennakkoon sidottuna.
Sidonta on kerääjän raporttiväite. Se ei itsessään autentikoi ajankohtaa,
suorittajaa, laitetta tai testin rehellisyyttä. Jälkikäteen väärennettyä
manifestia ei voi erottaa aidosta pelkällä paikallisella tiivisteellä.

## Evidenssiliitäntä

`council72_evidence` lukee 1–8 nimettyä alkuperäistä ajohakemistoa nykyisellä
Evidence Forensics -tarkistuksella. Luku käyttää yhteensä enintään 32 MiB:n
budjettia ja olemassa olevia tiedostokohtaisia rajoja. Symlinkkejä tai
polkutraversointia ei hyväksytä. Lokitekstiä ei suoriteta.

Kriteerin täyttyminen tarvitsee v2-manifestin, oikean commitin ja ympäristön,
puhtaan checkoutin, muuttumattoman sopimuksen sidonnan, täydellisen kaappauksen,
yhtäpitävän execution-kontekstin, aineistoa vastaavan evidenssipaketin sekä
valitun vaiheen status/exit/loki-yhtäpitävyyden. Kokoelman tuntematon commit
tai ympäristö estää myönteisen päätelmän myös muiden ajojen mennessä läpi.
Workiksi tunnistetaan manifestin linux/win32/darwin-väite ja Androidiksi vain
android-väite. Nämäkin ovat ympäristöväitteitä, eivät laitteen tunnistusta.

Tyhjä loki, puuttuva paketti, vanha manifesti, puuttuva sopimussidonta tai
väärä commit eivät täytä sopimusta. Ilmoitettu failure ja sen kanssa
ristiriitainen success-loki eivät vahvista regressiota. Min_passed koskee
pytestin passed-määrää; unittestin kokonaismäärää ei tulkita läpäisseiksi.
Syntaksikriteerillä min_passed on nolla ja tarvitaan tunnistettu syntaksiloki.

GitHub CI:n erillisen snapshotin voi antaa `--ci`-valinnalla. Se ei korvaa
Android-kriteeriä. Allekirjoitukset käsitellään nykyisellä Ed25519-kerroksella
valinnoilla `--attestations` ja `--trusted-keys`. Molemmat annetaan erikseen;
aineiston sisältä löydettyä avainta ei oteta luotetuksi. Todistajan
allekirjoituksen tarkistus pysyy erillään testin suorituksen autentikoinnista.

Tuloksessa on yksi uusi havaintokierroksen ehdotus. Kaikki artefaktihavainnot
jakavat `local-artifact-claims`-lähderyhmän; kopioidut ajot eivät lisää
riippumattomia lähteitä. Väitteen domain määrää nykyisestä luettelosta
vastuuringin, perustajan ja hänen Limbon viestinviejänsä. Tuloksen luokittelu
on vähintään restricted, koska lähdelokeille ei ole todennettua julkista
luokitusta. Sealed-sopimuksen luokittelu säilyy sealed-arvona.

## Käyttö

```bash
"$PY" -m klone.council72_contract --template --commit "$REV" --output "$CONTRACT"

"$PY" "$ROOT/tools/termux_evidence_battery.py" --root "$ROOT" \
  --python "$PY" --experiment-contract "$CONTRACT" --output "$RUNS/$NAME"

"$PY" -m klone.council72_evidence --contract "$CONTRACT" \
  --runs-root "$RUNS" --run "$NAME" --output "$REPORT"

"$PY" -m klone.council72_evidence --contract "$CONTRACT" \
  --runs-root "$RUNS" --run "$NAME" --verify "$REPORT"
```

Aseta ensin `PYTHONPATH="$ROOT/src"` ja `PYTHONDONTWRITEBYTECODE=1`.
Oma määrittely annetaan sopimuksen CLI:lle `--input`-valinnalla tai paikallisen
API:n `POST /api/cognition/council72/contract`-reitille. API vain muodostaa
sopimuksen; se ei lue palvelimen tiedostoja eikä käynnistä testejä.

Sivun **Lukittu koe ja testievidenssi** JSON-tuonti toimii paikallisesti
selaimessa. Tallenna havaintokierros ja lisää se istuntoon erikseen.
Selaimen rakennetarkistus ei korvaa lähdeaineiston uudelleentarkistusta.
CLI:n `--verify` vertaa tallennettua raporttia nykyisiin alkuperäisiin
artefakteihin; changed-source-tulos säilyy uutena tutkimushavaintona.

Käyttöönoton hyväksyntä, oikeuksien muuttaminen, muistiin kirjoittaminen ja
ulkoisten viestien lähettäminen pysyvät raportissa pois käytöstä.
