# KLONE Atlas E11.2 – lähdetekstin tarkistusehdokkaat ja Council72-työjono

## Mitä on toteutettu

E11.2 on **offline-toimiva deterministinen apuväline**, joka lukee E11:n
jo täytetyn manifestin (esimerkiksi
`~/klone-var/e11/e11-taytetty.json`) ja ehdottaa enintään
8 tekstikohtaa kumpaakin lähdettä kohti.

Kukin ehdokas on **kirjaimellisesti** syötemanifestiin tallennetusta
omistajan toimittamasta tekstistä. Mukaan tallentuvat:

- lähteen E9.1:n kanoninen muistintunnus, alkuperäinen HTTPS-osoite
  ja tutkimusotsikko, julkisen lähteen Memory Core -tarkiste
- alku- ja loppusijainti Unicode-merkkeinä, lainaus ja sen SHA-256
- välilehden aihe: menetelmät, tulokset, rajoitukset tai asiayhteys
- todellisen Council72-jäsenluettelon jäsen, rinki ja paikka, jolle
  **arviointitehtävää ehdotetaan**.

Aiheet perustuvat rajattuun sanastoon, *eivät* kielimallin
johtopäätöksiin, eivätkä osoita varsinaista tulosta tai ristiriitaa.
Kaikki ehdotetut näkemykset saavat vain ehdotetun
`context`-luokan.

**Tärkein lähde-erottelu:** jos käyttöoikeusmerkintä kertoo tekstin olevan
`selostus`, `referointi`, `tiivistelmä`, `summary` tai
`AI-generated`, järjestelmä kirjaa sen
`owner_declared_summary_unverified`.
Muutenkin lähdesisällön alkuperäinen aitous jää vahvistamatta.
Tämän vuoksi omistajan aiemmin ChatGPT:ltä saamat
2 666 ja 2 905 tavun selostukset **eivät muutu**
alkuperäisten tutkimusjulkaisujen autenttisiksi teksteiksi.
E11.2 ei ota oikeutta kopioida tai käyttää aineistoa uutena
riippumattomana tieteellisenä evidenssinä.

## Android/Termux – yksi komento

```bash
cd ~/klone-arxiv-e1 &&
git fetch origin feat/limbo-external-intelligence-20261115 &&
git switch --detach FETCH_HEAD &&
bash scripts/klone-e11-2-phone.sh
```

Skripti ensin ajaa kohdennetun E7–E11.2-regression,
lukee jo täytetyn `e11-taytetty.json`-manifestin ja kirjoittaa
**vain uuden raportin** kansioon `~/klone-var/e11/` muodossa
`e11-2-ehdokkaat-YYYYMMDD-HHMMSS.json`.
Se **ei** muuta täytettyä manifestia, käynnistä palvelimia uudelleen
eikä tee E7-päiväkirjaan, Memory Coreen tai yksityisiin huoneisiin
muutoksia.

Vaihtoehtoinen täsmällinen komento:

```bash
cd ~/klone-arxiv-e1
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_evidence_candidates \
  --klone-db "$HOME/klone/data/klone_mission_control.db" \
  --manifest "$HOME/klone-var/e11/e11-taytetty.json" \
  --per-source-limit 8 \
  --output "$HOME/klone-var/e11/e11-2-uusi-raportti.json"
```

`--output` on kirjoitussuojattu: uuden ajon pitää valita
uusi tiedostonimi. Pidä raportit Termuxin yksityisessä hakemistossa,
koska ne voivat sisältää lyhyitä katkelmia omistajan toimittamista
teksteistä.

## E11.3 – omistajan hyväksymä asiayhteysvalinta ja tarkistus

E11.3 toteuttaa erillisen, **nimenomaisesti vahvistettavan**
lainausmerkintöjen valintavaiheen. Se laskee E11.2:n ehdotusraportin
uudelleen käyttäjän E11-manifestista ja alkuperäisen julkisen Memory
Core -lähdeparin metatiedoista. Väärennetyt ehdokastunnukset,
lähdetekstin muutokset, keksityt tarkistajajäsenet tai muuttuneet
tekstisijainnit estävät hyväksynnän.

`src/klone/limbo_evidence_accept.py` käyttää kaikille valituille
katkelmille vain luokkaa `stance=context`.
Se **ei koskaan** merkitse niitä automaattisesti väitettä tukeviksi
tai kumoaviksi tutkimushavainnoiksi. Omistajan vahvistus tarkoittaa
lainausten valintaa, ei tutkimusjulkaisujen autentikointia.

### Termux-komento

Aja ensin E11.2 yllä kuvatulla komennolla. Tämän jälkeen:

```bash
cd ~/klone-arxiv-e1
bash scripts/klone-e11-3-phone.sh
```

Skripti etsii viimeisimmän yksityiseen
`~/klone-var/e11/`-kansioon tallennetun
`e11-2-ehdokkaat-*.json`-raportin ja näyttää
lähteiden alkuperäluokan. Se odottaa käyttäjän kirjoittamaa
täsmällistä vahvistusta **HYVAKSY KONTEKSTI** ennen
kuin yhtään merkintätiedostoa syntyy.
Jos et halua hyväksyä kaikkia ehdokkaita, keskeytä
`Ctrl+C` ja valitse yksittäiset ehdokastunnukset
komentorivin `--candidate-id`-valinnalla.

Vahvistuksen jälkeen syntyvät kaksi **uutta, alkuperäiset tiedostot
säilyttävää** raporttia:
- `e11-3-konteksti-YYYYMMDD-HHMMSS.json`:
  käyttäjän hyväksymät kontekstimerkinnät
- `e11-3-tarkistus-YYYYMMDD-HHMMSS.json`:
  varsinaisen E11 `--review`-ajon tarkistamat lainausankkurit

Kumpikaan ei kirjoita päämuistiin, E7-päiväkirjaan tai
neuvoston äänestyksiin. Lähdeselostuksia ei esitetä varmennettuina
kokoteksteinä.

## Mitä ei vielä ole

Raportissa `council_completed_reviews=0`,
`council_vote_count=0`, `scientific_truth_verified=false`,
`memory_write=false`, `external_network_actions=false`.
Jäsenten ehdotettu tehtävänjako ei tarkoita, että nämä henkilöhahmot
tai mallit olisivat tehneet yhtään itsenäistä arviointia.
Samoin `suggested_stance=context` ei ole todistus, eikä
sana "results" tekstissä todenna tulosta.

E11.3:n kontekstimerkintöjen omistajavahvistus on nyt toteutettu.
E11.4 voi sitten tuottaa
riippumattoman kokotekstitarkistuksen reititysehdotuksen ja
erottaa aidon tarkistussuorituksen suunnitellusta tehtävästä.
