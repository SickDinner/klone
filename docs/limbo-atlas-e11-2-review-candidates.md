# KLONE Atlas E11.2 – lähdetekstin tarkistusehdokkaat ja Council72-työjono

## Mitä on toteutettu

E11.2 on **offline-toimiva deterministinen apuväline**, joka lukee E11:n
jo täytetyn manifestin (esimerkiksi
\`~/klone-var/e11/e11-taytetty.json\`) ja ehdottaa enintään
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
\`context\`-luokan.

**Tärkein lähde-erottelu:** jos käyttöoikeusmerkintä kertoo tekstin olevan
\`selostus\`, \`referointi\`, \`tiivistelmä\`, \`summary\` tai
\`AI-generated\`, järjestelmä kirjaa sen
\`owner_declared_summary_unverified\`.
Muutenkin lähdesisällön alkuperäinen aitous jää vahvistamatta.
Tämän vuoksi omistajan aiemmin ChatGPT:ltä saamat
2 666 ja 2 905 tavun selostukset **eivät muutu**
alkuperäisten tutkimusjulkaisujen autenttisiksi teksteiksi.
E11.2 ei ota oikeutta kopioida tai käyttää aineistoa uutena
riippumattomana tieteellisenä evidenssinä.

## Android/Termux – yksi komento

\`\`\`bash
cd ~/klone-arxiv-e1 &&
git fetch origin feat/limbo-external-intelligence-20261115 &&
git switch --detach FETCH_HEAD &&
bash scripts/klone-e11-2-phone.sh
\`\`\`

Skripti ensin ajaa kohdennetun E7–E11.2-regression,
lukee jo täytetyn \`e11-taytetty.json\`-manifestin ja kirjoittaa
**vain uuden raportin** kansioon \`~/klone-var/e11/\` muodossa
\`e11-2-ehdokkaat-YYYYMMDD-HHMMSS.json\`.
Se **ei** muuta täytettyä manifestia, käynnistä palvelimia uudelleen
eikä tee E7-päiväkirjaan, Memory Coreen tai yksityisiin huoneisiin
muutoksia.

Vaihtoehtoinen täsmällinen komento:

\`\`\`bash
cd ~/klone-arxiv-e1
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.limbo_evidence_candidates \
  --klone-db "$HOME/klone/data/klone_mission_control.db" \
  --manifest "$HOME/klone-var/e11/e11-taytetty.json" \
  --per-source-limit 8 \
  --output "$HOME/klone-var/e11/e11-2-uusi-raportti.json"
\`\`\`

\`--output\` on kirjoitussuojattu: uuden ajon pitää valita
uusi tiedostonimi. Pidä raportit Termuxin yksityisessä hakemistossa,
koska ne voivat sisältää lyhyitä katkelmia omistajan toimittamista
teksteistä.

## Mitä ei vielä ole

Raportissa \`council_completed_reviews=0\`,
\`council_vote_count=0\`, \`scientific_truth_verified=false\`,
\`memory_write=false\`, \`external_network_actions=false\`.
Jäsenten ehdotettu tehtävänjako ei tarkoita, että nämä henkilöhahmot
tai mallit olisivat tehneet yhtään itsenäistä arviointia.
Samoin \`suggested_stance=context\` ei ole todistus, eikä
sana "results" tekstissä todenna tulosta.

Tämän jälkeen seuraava E11.3 voi saada omistajan **erikseen
hyväksymän** ehdokasvalinnan ja palauttaa siitä tarkistetun
E11 \`--review\`-manifestin. E11.4 voi sitten tuottaa
riippumattoman kokotekstitarkistuksen reititysehdotuksen ja
erottaa aidon tarkistussuorituksen suunnitellusta tehtävästä.
