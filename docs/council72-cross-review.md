# Neuvosto 72: kaksinkertainen ristikkäisarviointi (9 × 8 / 8 × 9)

## Tavoite ja rajaus

Tämä laajennus ei luo uusia jäseniä, oikeuksia, erillisiä mallikutsuja eikä
itsenäisiä todistuslähteitä. Se kokoaa nykyisen toistettavan
`klone.council72.deliberate`-kierroksen kahteen näkökulmaan:

1. **Rinkit (9 × 8)**: alkuperäiset yhdeksän osaamisrinkiä,
   jokaisessa kahdeksan jäsentä.
2. **Perustajalinjat (8 × 9)**: kahdeksan saraketta, kussakin
   yhden paikan edustaja jokaisesta yhdeksästä ringistä. Ringin 9
   sarakejäsen on linjan perustaja.

Näin jäsen on täsmälleen yhdessä rivissä ja yhdessä sarakkeessa. Kyse on
samoista 72 osallistujasta kahdessa eri ryhmittelyssä, **ei 144 agentista**.
Määrittely perustuu olemassa olevan luettelon `ring.member_ids`-järjestykseen.
Goetia-nimet ovat kirjallisia roolinimiä, eivät suoritusoikeuksia.

## Ristiriitatutka

Jokaisesta 64 erikoisrinki–perustajalinja-leikkauspisteestä tarkastellaan
jäsenen kahta eri vertaisjoukkoa:

- saman ringin muut **7** jäsentä;
- saman perustajalinjan muut **8** jäsentä, perustajan mukaan lukien.

Kummallekin vertaisjoukolle muodostetaan vahva kanta vain, jos vähintään
kaksi kolmasosaa kannattaa tai vastustaa. Tällöin tarvitaan vähintään
5/7 tai 6/8 samanlaista kantaa. `defer` ei täytä kummankaan puolen
enemmistöä.

Jos ringin vertaiset puoltavat ja linjan vertaiset vastustavat — tai
päinvastoin — raportoidaan eksplisiittinen ristiriita
`cross_review_required`. Muussa tapauksessa tulos on
`no_structural_split_detected`, **ei** "hyväksytty" tai "totta".
Ringin 9 perustajia ei käsitellä ylimääräisinä riippumattomina äänenä.

Perustajan linjan äänenä käytetään todellisen kierrosraportin
`founder_ballots`-arvoa, myös silloin kun se on syötetty manuaalisesti
(`explicit_input`). Raporttiin kirjataan äänen lähde.

## Evidenssi, luokittelu ja oikeudet

- Sama jäsen ja havaintoviite eivät muutu kahdeksi riippumattomaksi lähteeksi
  kahden tarkastelun seurauksena.
- `references_total` kertoo viitteiden kokonaismäärän ja
  `unique_reference_strings` ainoastaan erilaisten viitetekstien määrän.
  Jälkimmäinen **ei** ole riippumattomien alkuperäislähteiden lukumäärä.
- Viitteitä ei todenneta tämän moduulin sisällä.
- Alkuperäisen kierroksen päätöstä, luokittelua, perustajan veto-oikeutta,
  hypervisorin oikeuksia tai auditointihistoriaa ei muuteta.
- Kaikissa tuloksissa `AUTHORITY`-kentät pysyvät epätosina.
- Luonnoksia ei julkaista, mitään ei lähetetä verkkoon eikä
  pysyvään KLONE-muistiin tehdä kirjoituksia.
- Syötekierroksen eheys vaatii nykyisen `replay_matches`-tarkistuksen.
  Tuotos sisältää kierros- ja jälkitiivisteet;
  `cross_review_replays(round, overlay)` vertaa uusintalaskentaan.
  Tiiviste ei todista lähteen aitoutta tai riippumattomuutta.

## Käyttö Android/Termuxissa

```bash
cd ~/klone-next
export PYTHONPATH="$PWD/src"
PY="$PWD/.venv/bin/python"

"$PY" -m pytest -q tests/test_council72_cross_review.py
"$PY" -m klone.council72_cross_review --demo
```

Oma tehtävä voidaan antaa samassa rajatussa JSON-muodossa kuin
`klone.council72 --input`:

```bash
"$PY" -m klone.council72_cross_review --input tehtava.json \
  --output "$HOME/klone-var/council-cross-review-$(date +%Y%m%d-%H%M%S)-$$.json"
```

`--output` luo uuden raportin ja kieltäytyy korvaamasta aiempaa.
`--demo` käyttää synteettistä syötettä, eikä osoita todellista
lähdevarmennusta. API:n reitti
`POST /api/cognition/council72/cross-review` vastaanottaa olemassa
olevan `CouncilProposal`-rakenteen ja palauttaa pelkän
ristikkäisarvioinnin.

## Jatkokehitys

Seuraava oleellinen vaihe on lähdeprovenienssin kytkeminen
`council72_evidence`-kerrokseen. Näin voidaan verrata riippumattomien
lähderyhmien määrää pelkkien viitetekstien asemesta. Lisäksi
ristiriitojen selitykset voidaan näyttää paikallisessa Council72-näkymässä.
