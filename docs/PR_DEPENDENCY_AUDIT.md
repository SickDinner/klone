# KLONE – kehityshaarojen riippuvuustarkistus (offline)

Tämä työkalu lukee GitHubin PR-metadataa **vain paikallisesta JSON-tiedostosta**.
Se ei tee verkkopyyntöjä, käynnistä palvelimia, aja testejä, lue KLONEn muistia,
muuta oikeuksia, muuta PR:iä eikä yhdistä tai hyväksy mitään. Raportin
review_order_not_merge_permission on **tarkastusjärjestys**, ei yhdistämislupa.

## Android / Termux

Hae projektin juureen (esim. ~/klone-next) turvalliseen erilliseen polkuun.
Tee julkisen GitHubin metadatahaku erillisellä, omalla päätöksellä:

~~~sh
mkdir -p "$HOME/klone-var"
curl --fail --silent --show-error --location \
  'https://api.github.com/repos/SickDinner/klone/pulls?state=open&per_page=100' \
  -o "$HOME/klone-var/klone-open-prs.json"
python tools/klone_pr_train.py "$HOME/klone-var/klone-open-prs.json" --text
python -m unittest discover -s tests -p 'test_pr_train.py' -v
~~~

Jos tulos on JSON-käännösvirhe, liikaa tietueita, epäselvä pohjahaara tai sykli,
älykkäämpää yhdistämispäätelmää ei tehdä. GitHubin julkinen rajapinta voi asettaa
rajoituksia, eikä tässä avata yksityisiä PR-tietoja tai käytetä GitHub-tokeneita.

## Hyväksymisjärjestys

1. Varmista pohjahaara ja riippuvuus: base.ref joko main tai toisen avoimen PR:n head.ref.
2. Tarkista erikseen täsmälleen kyseisen commitin CI (Linux/Windows, Python-versiot, muut matriisit).
3. Tarkista Android/Termux-kokeet **samalla commitilla**, erota käyttäjän raportti riippumattomasta mittauksesta.
4. Tarkista tietoturva, tietokannan muutokset, ulkoverkko, tekoälyn rahalliset kulut ja arkaluontoiset tiedot.
5. Arvioi muutosehdotus ihmisen toimesta ja muuta pohjahaara/tee merge vasta erillisen päätöksen jälkeen.

Kehityshaaran koodin olemassaolo, CI:n vihreys, Androidin terveystarkistus ja
hyväksytty käyttöönotto ovat **neljä eri asiaa**. Tämä työkalu tarkistaa vain
ensimmäisen vaatiman *riippuvuusrakenteen*; jäljelle jäävät kolme ovat
aina false/tuntemattomia raportissa, kunnes ne tutkitaan erikseen.

Esimerkki marraskuussa 2026 havaitusta ketjusta:
#177 → #178 → #179 → #180 → #181 → #182 → #183.
Tämä esimerkki vanhenee ja on tarkistettava uudella PR-snapshotilla.
