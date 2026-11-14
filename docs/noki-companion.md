# Noki – KLONE-korppikumppani (v0.2 – raadollinen Noki)

Tämä vaihe lisää itsenäisen, paikallisessa selaimessa toimivan korppihahmon.
Se ei muuta KLONEn muistia, room-permissioneita, audit-ketjua eikä ingest-logiikkaa.

## Käynnistys ja käyttö

Kun haara on käytössä palvelimen lähdekoodissa, avaa
`http://127.0.0.1:8000/noki` samassa Android-laitteessa, jolla KLONE-palvelin toimii.

- **KRRRÄÄ! Huuda:** paikallinen WebAudio raakuntageneraattori ja selaimen `speechSynthesis`-puhe, jossa on vaihtelevia foneettisia äänteitä, matala äänenkorkeus ja painotettuja huudahduksia. Suomiäänen laatu riippuu selaimen saatavilla olevista puheäänistä.
- **Sätki!:** korpin repaleiset siivet ja ruiskut heiluvat retroanimaatiossa.
- **Nalkuta:** kiertää paikallisia synkän ironisia/sarkastisia repliikkejä. Tämä on käsikirjoitettu persoona eikä kielimalli.
- **Matki sanojani:** puheentunnistus poimii lausutut sanat ja Noki sanoo ne takaisin omalla TTS-tyylillään. Chrome saattaa lähettää puheen palvelimelle tunnistusta varten, joten ominaisuus on vapaaehtoinen.
- **Matki ääntäni (4 s):** kameraa ei avata. Käyttäjän painikkeella sallima mikrofoni tallentaa vain enintään neljän sekunnin pätkän selaimen muistiin. Ääni käsitellään paikallisesti (0,68× toistonopeus, suotimet, särö, kompressori), minkä jälkeen sitä ei säilytetä. Tämä on suora äänenmuokkaus, ei pysyvä ääniklooni.
- **Raakunnan voimakkuus:** äänen sisäinen taso on rajoitettu; puhelimen äänenvoimakkuus on edelleen käyttäjän hallussa. Käytä kohtuullista äänenvoimakkuutta kuulokkeilla.
- **Turpa tukkoon:** keskeyttää puheen, raakunnan ja käynnissä olevan mikrofoni-/matkimistoiminnon.
- **Viesti:** avainsanoihin reagoiva, tarkoituksella ronski paikallinen nalkutus; ei kielimallia.
- **Valitse / kuvaa teos:** kuvan avaus selaimessa ja paikallinen kirkkauden, kontrastin, värivaihtelun, reunavarianssin ja peilisymmetrian mittaus. Ei tunnista kuvan aiheita. Kuvien kokoa rajoitetaan 12 megaan.
- **Tyhjennä:** poistaa tämän sivun kuvaesikatselun ja vapauttaa väliaikaisen object URL:n.

## Android / Termux – kokeile ilman nykyisen KLONEn vaihtamista

Jos nykyinen kehityskopio on `~/klone-next` ja palvelin käyttää sitä:

```sh
cd ~/klone-next
git fetch origin feat/noki-raven-companion-20261114
git show origin/feat/noki-raven-companion-20261114:src/klone/static/noki.html > src/klone/static/noki.html
```

Tämän jälkeen vanha palvelin tarjoaa prototyypin osoitteessa
`http://127.0.0.1:8000/static/noki.html` ilman uudelleenkäynnistystä,
jos se jo käyttää samaa `src/klone/static`-hakemistoa. Tämä vain kopioi
uuden staattisen tiedoston eikä ota uutta backend-koodia käyttöön.

Jos haluat nimenomaan siistin `/noki`-osoitteen, ota haara myöhemmin
käyttöön hallitusti ja käynnistä palvelin uudelleen.

## Testit

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_noki_companion.py'
```

## Turvallisuusrajat / jatkokehitys

- Ei piilotettua kameran tai mikrofonin aktivointia. Ainoastaan erillinen kameravalinta tai mikrofonipainike aktivoi laitteet.
- Ei API-avaimia, taustalatausta tai pysyvää tallennusta. Huom: **Matki sanojani** käyttää selaimen puheentunnistusta, joka voi käsitellä ääntä verkossa; **Matki ääntäni** tekee käsittelyn paikallisesti.
- Ei pääsyä KLONEn memory-/room-/audit-dataan ilman erillistä, suunniteltua lupamallia.
- Hahmon huoneeseen integrointi, kuvan semanttinen analyysi ja keskustelumalli ovat myöhempiä erillisiä vaiheita; niitä ei pidä väittää toteutetuiksi.
