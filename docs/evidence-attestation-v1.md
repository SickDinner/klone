# Evidence Attestation v1: rajattu allekirjoituksen tarkistus

Tämä jatkaa PR:n #140 alkuperäistä toteutusta. Ed25519-allekirjoitus sitoo
paketin kanonisen SHA-256-tiivisteen, commitin ja witness-tunnisteen erilliseen
`KLONE-EVIDENCE-ATTESTATION-V1`-protokollaviestiin. Tarkistaja hyväksyy vain
erikseen annetun luottamuskartan julkiset avaimet. Paketin tai allekirjoituksen
mukana tuleva avain ei luo luottamusta.

## Mitä kelvollinen allekirjoitus kertoo?

`signature_valid`, `trusted_witness` ja `witness_authenticated` voivat olla
`true`, kun eksplisiittisesti luotetun avaimen allekirjoitus täsmää tähän
viestiin. `key_in_trust_map` kertoo erikseen, löytyikö sopiva avain kartasta.
Julkisen avaimen SHA-256 auttaa vertaamaan avaimia toisessa kanavassa.

Seuraavat pysyvät aina `false`:

- `origin_authenticated`: historiallista lähdeketjua ei ole varmennettu.
- `device_identity_verified`: avain ei yksin yksilöi Android-laitetta.
- `test_execution_authenticated`: allekirjoittaja voi allekirjoittaa virheellisen
  tai jälkikäteen muodostetun väitteen.
- `deployment_approval`: tarkistustulos ei myönnä käyttöönottolupaa.

Tämä tarkistaa allekirjoitetun pakettiolion perustiedot ja oman tiivisteen.
Se ei lue tai varmista paketin nimeämiä alkuperäisiä testilokeja. Tee niiden
vertailu erikseen Evidence Forensicsilla. Näiden kahden tarkistuksen tuloksia ei
saa yhdistää yleiseksi onnistumiseksi.

## Käyttö

Perusasennus ja Forensics eivät tarvitse cryptography-pakettia. Allekirjoitukset
käyttävät valinnaista `evidence`-riippuvuusryhmää. Androidissa riippuvuuden
asennus ja Ed25519-tuki täytyy tarkistaa kyseisessä virtuaaliympäristössä.
Moduuli ei asenna mitään itse. Puuttuva backend näkyy `crypto_unavailable`-syynä.

Valmiin paketin ja erillisen allekirjoituksen tarkistus:

```bash
PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" \
  -m klone.evidence_attestation \
  --packet "$PACKET" \
  --attestation "$ATTESTATION" \
  --trusted-keys "$TRUSTED_KEYS"
```

Muuttujat ovat käyttäjän tarkistamia polkuja. `TRUSTED_KEYS` on käyttäjän
hallinnoima JSON-olio: witness-tunniste -> 64 pientä heksamerkkiä sisältävä
Ed25519-julkinen avain. Älä poimi tätä luottamuskarttaa tarkistettavasta
evidenssistä. Varmista avain toisessa luotetussa kanavassa ennen sen lisäämistä.
Exit code 0 tarkoittaa vain allekirjoituksen ja luottamuskartan täsmäämistä;
exit code 2 tarkoittaa puuttuvaa tai hylättyä tarkistusta.

CLI lukee kolme enintään 128 KiB JSON-tiedostoa rajatulla no-follow-lukijalla.
Duplikaattiavaimet, ei-finiittiset luvut, symlinkit ja virheelliset rakenteet
hylätään. CLI ei kirjoita tiedostoja, käynnistä komentoja tai käytä verkkoa.

`sign(packet, witness_id, private_key_bytes)` on erillinen ohjelmointirajapinta
tuleville ajoille. Se ottaa muistinvaraisen 32 tavun avaimen ja palauttaa
allekirjoitusolion. Avaimen luonti, tallennus, säilytys tai historian
allekirjoittaminen ei tapahdu automaattisesti. Testien vakioavain on julkinen
synteettinen testivektori, eikä sitä saa käyttää oikeaan evidenssiin.

## Seuraava todistusketju

1. Tallenna tulevaan testiajoon tarkka testiympäristö, testikomennot ja
   vaihekohtaiset tulokset. Säilytä aiemmat manifestiversiot luettavina.
2. Tarkista lähteet ennen uuden paketin allekirjoittamista. Allekirjoitus on
   erillinen tiedosto; lähdelokit ja alkuperäinen paketti säilyvät.
3. Hallinnoi luottamusavainten omistajia, rooleja, perumista ja voimassaoloa
   erikseen. V1:n kartta on yksittäinen tarkistuksen syöte, ei avainpalvelu.
4. Liitä CI:n virallisesti haettu commit/run-tunniste ja valittu julkinen
   avain toisistaan riippumattomilla tarkistuksilla. CI ei korvaa Android-ajoa.
5. Lisää myöhemmin ulkoinen aikaleima-ankkuri ja riippumaton todentaja.
   V1 ei anna luotettua aikaleimaa tai estä saman allekirjoitetun paketin replayta.

Vanhoille 19 ajolle ei tämän työn yhteydessä ole luotu allekirjoituksia, avaimia,
manifestia, puuttuvaa pakettia tai takautuvaa provenienssia.

## Varmistus ja lähde

Testit kattavat oikean allekirjoituksen, väärän avaimen, muuttuneen commitin myös
uudelleen tiivistettynä, muuttuneen protokolladomainin, witnessin vaihdon,
epäluotetun avaimen, puuttuvan backendin, liian suuren allekirjoituksen,
virheelliset JSONit ja lähteiden muuttumattomuuden. Erillinen CI-jobi asentaa
valinnaisen backendin ja varmistaa, ettei kryptografinen testaus jää pelkäksi
ohitukseksi.

Ed25519 toteutetaan PyCA cryptographylla, ei omalla kryptografialla. Rajapinnan
perusta: [PyCA Ed25519 signing](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/).
