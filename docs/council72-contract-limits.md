# Koesopimuksen tarkempi kohdistus ja hyväksymisrajat

Tämä täydentää [samaa koesopimus- ja evidenssiliitäntää](council72-evidence-contracts.md).
Sopimusmallia tai kerääjää ei korvata toisella järjestelmällä. Aiemmat
sopimukset säilyttävät kanonisen sisältönsä ja tiivisteensä, kun uusia
valinnaisia kenttiä ei käytetä.

## Valinnaiset lukitukset

| Kenttä | Sijainti | Vaikutus |
| --- | --- | --- |
| `execution_identity.test_suite_sha256` | Sopimuksen `spec` | Lukitsee testisarjan tavut ennen ja jälkeen ajon |
| `execution_identity.collector_sha256` | Sopimuksen `spec` | Lukitsee kerääjän ja kontekstikoodin tavut |
| `platform` | Kriteeri | Rajaa Work-kriteerin tarkasti linux/win32/darwin-alustaan tai Android-kriteerin android-alustaan |
| `max_skipped` | Kriteeri | Pytest-yhteenvedon ohitusten enimmäismäärä |
| `max_deselected` | Kriteeri | Pytest-yhteenvedon poissuljettujen testien enimmäismäärä |
| `full_suite: true` | `full`-kriteeri | Vaatii kerääjän suodattamattoman koko pytest-ajon ja nolla poissuljettua testiä |

Syntaksikriteerille ei anneta pytestin laskurirajoja. `full_suite` on sallittu
vain koko testisarjan vaiheelle ja true-arvona. Samassa kriteerissä ei voi
hyväksyä poissuljettuja testejä. Laskurit ovat kokonaislukuja; boolean ei kelpaa.

Yhteiset testisarjan ja kerääjän lukitukset tarkistetaan kerääjässä ennen
uuden ajohakemiston varaamista ja ennen ensimmäistä testikutsua. Samalla
vaaditaan puhdas checkout ja vähintään yksi kyseiselle alustalle sopiva
kriteeri. Väärä kohdistus pysäyttää ajon. Jo olemassa olevaa evidenssiä ei
muuteta tai täydennetä.

Näiden lukitusten puuttuessa aikaisempi kerääjän käyttö säilyy ennallaan.
`--experiment-contract` tarkistaa edelleen kohdecommitin ja sopimustiedoston
loogisen sekä ennen/jälkeen-tavutiivisteen nykyisellä tavalla.

## Sopimuksen valmistelu

Laadi kriteerit ennen koetta. Alla olevat testimäärät ovat valittavia
käyttöesimerkkejä, eivät automaattisesti muuttuvia rajoja:

```json
{
  "id": "work-full",
  "claim_key": "work-full-passed",
  "domain": "memory",
  "stage": "full",
  "environment": "work",
  "platform": "linux",
  "min_passed": 1001,
  "max_skipped": 1,
  "max_deselected": 0,
  "full_suite": true
}
```

Lisää tämä kriteeri nykyisen sopimusmäärittelyn `criteria`-listaan ja aseta
`target_commit` tarkaksi testattavaksi commitiksi. Tallenna määrittely ja
kaikki tuotokset checkoutin ulkopuolelle. Lukitse todellisen puhtaan checkoutin
testisarja ja kerääjä yhdellä komennolla:

```bash
PYTHONPATH="$KLONE_ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$KLONE_PY" \
  -m klone.council72_contract --input "$SPEC_JSON" \
  --lock-checkout "$KLONE_ROOT" --output "$NEW_CONTRACT_JSON"
```

Valinta `--lock-checkout` ei suorita testejä. Se lukee Gitin tilan ja
kohdecommitin sekä laskee nykyiset testisarjan ja kerääjän tiivisteet.
Checkoutin täytyy olla puhdas samassa commitissa myös lukituksen jälkeen.
Valmistelu suoritetaan samalla luotetulla paikallisella projektilla kuin
testipatteri; API ei hyväksy tiedostopolkuja.

Testipatterin ja evidenssikatselmuksen nykyiset komennot säilyvät:

```bash
PYTHONDONTWRITEBYTECODE=1 "$KLONE_PY" \
  "$KLONE_ROOT/tools/termux_evidence_battery.py" \
  --root "$KLONE_ROOT" --python "$KLONE_PY" \
  --experiment-contract "$NEW_CONTRACT_JSON" --output "$NEW_RUN_DIRECTORY"

PYTHONPATH="$KLONE_ROOT/src" "$KLONE_PY" -m klone.council72_evidence \
  --contract "$NEW_CONTRACT_JSON" --runs-root "$RUNS_ROOT" \
  --run "$RUN_BASENAME" --output "$NEW_EVIDENCE_JSON"
```

Sopimuksen muuttaminen tuloksen näkemisen jälkeen tuottaa uuden tiivisteen.
Vaikka uusi sopimus on rakenteellisesti kelvollinen ja rajat ovat löysemmät,
vanha ajo ei täytä sen sidontaa. Uusi koe tarvitsee uuden ajon.

## Tulkinta ja lähteet

Väärän testisarjan, kerääjän tai suodatetun komennon vihreä ajo jää
`unknown`-tilaan. Oikein kohdistettu, yhtäpitävä pytest-ajo, jonka ohituksia
tai poissuljettuja testejä on liikaa, antaa `not_met`-tuloksen. Tunnistamaton
tai unittest-muotoinen yhteenveto ei täytä pytest-laskurien ehtoja.

`platform: "win32"` ei täyty Linux-ajolla, vaikka molempien ympäristöluokka
on Work. Yhteisen identiteettilukituksen testisarja tarkoittaa täsmälleen
samoja tavuja: esimerkiksi rivinvaihtojen muuttuminen voi vaatia oman
ennakkoon valmistellun sopimuksen. Näitä eroja ei peitetä tulkinnassa.

Havaintotunniste muodostetaan kriteeristä, tilasta ja yksilöllisistä
sisältötiivisteistä. Ajohakemiston uudelleennimeäminen tai saman aineiston
kopioiminen toiseen hakemistoon ei luo uutta havaintoa. Katselmuksessa
valitut hakemistot näkyvät edelleen erikseen tarkistettavina tapauksina.
Kaikki havainnot kuuluvat samaan nykyiseen `local-artifact-claims`-lähderyhmään.

Selain näyttää valinnaiset lukitukset ja rajat nykyisessä evidenssinäkymässä.
Tuodun tuloksen kriteerien täytyy sisältää myös samat valinnaiset kentät kuin
sopimuksen. Rakennetarkistus ei korvaa alkuperäislokien Python-tarkistusta.

Tiivisteiden täsmääminen ei autentikoi testien suorittamista, laitetta,
rekisteröinnin ajankohtaa tai koko osa-alueen valmistumista. Work, Android,
CI-väitteet ja todistajan allekirjoitus pysyvät erillisinä. Oikeuksia,
muisti-ingestiä tai käyttöönoton hyväksyntää ei muuteta.
