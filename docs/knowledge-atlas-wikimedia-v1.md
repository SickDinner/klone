# KLONE Knowledge Atlas v1 — 72 erikoisalaa, Wikipedia ja yleistieto

## Tila ja tavoitteet

KLONElle toteutettu ensimmäinen paikallinen Wikipedia-tietopankki.
Tämän kehityshaaran **72 000 artikkelia on tavoite, EI ladattu määrä**.
Puhelimeen tai GitHubiin ei ole vielä ladattu Wikipedia-artikkelikokoelmaa.

Tavoitevaiheet: 2 000 → 12 000 → 30 000 → 72 000 erillistä
Wikipedia-artikkelia. Jokaisella 72 neuvoston jäsenellä on kolme
kuratoitua erikoisalan aihetta (216), ja kaikille yhteisen
yleissivistyksen runko käsittää 32 alaa. Roolit on johdettu olemassa
olevan Council72-katalogin täsmällisistä jäsenistä ja tehtävistä.

Kielipohja: suomi, englanti, ruotsi, norja, tanska, islanti,
saksa, ranska ja espanja. Suomen 32 yleisaiheen hakua on
kuratoitu suomeksi; erikoisalan hakujen aiheet ovat
aluksi englanniksi, joten kaikkia niistä ei voi suoraan
löytää muunkielisistä Wikipedioista.

Tieto tallennetaan YHTEEN yhteiseen, paikalliseen SQLite-
tietokantaan, ei 72 kertaa identtisinä kopioina. Jäsenen
hakunäkymä painottaa sille sopivia julkisia lähteitä.
Ei itsenäisten 72 LLM-agentin, oppimisen tai tietoisuuden väitteitä.

## Miten tietokanta toimii?

- Tiedosto: ~/klone-var/knowledge-atlas/wikipedia.sqlite3
- FTS5-kokotekstihaku, jos paikallinen SQLite sen tukee.
  Muussa tapauksessa haku on hitaampi ja rajoittuu otsikoihin.
- 12 000 merkin maksimisisältö per artikkeli tässä
  ensimmäisessä vaiheessa. Mahdollinen katkaisu merkitään.
- Uusinta Wikipedia-artikkelirevisiota käytetään, vanhempi
  versio ei korvaa uudempaa. Sama sivutunniste eri kielessä
  on eri artikkeli.
- Lähde-ID, version ID, revision päivämäärä, pysyvä
  linkki, tekijöiden muutoshistorian linkki,
  lähdetyyppi ja SHA-256-tarkiste säilytetään.
- Wikipedian teksti on ulkoista epäluotettavaa dataa.
  Se ei voi käynnistää toimia, tehdä päätöksiä,
  kirjoittaa päämuistiin tai muuttaa käyttöoikeuksia.
- SQLite-tietokannalle on oletuksena 512 MiB:n
  pehmeä kapasiteettiraja. Se ei ole 100-prosenttinen
  reaaliaikainen levykiintiö. Tarkista vapaa tallennustila
  ja huomioi FTS-indeksin lisäkulutus.

## Ensimmäinen käyttöönotto Android / Termux

Kopioi koko lohko Termuxiin.

~~~bash
cd ~/klone-arxiv-e1 || exit 1

git fetch origin feat/knowledge-atlas-wikimedia-20261119 || exit 1
git switch --detach FETCH_HEAD || exit 1

bash scripts/klone-knowledge-atlas-phone.sh test
bash scripts/klone-knowledge-atlas-phone.sh status
bash scripts/klone-knowledge-atlas-phone.sh member 24
~~~

Nämä ajot ovat offline. Ne eivät tarvitse OpenAI API-avainta
eivätkä lataa Wikipediaa.

### Ensimmäiset oikeat Wikipedia-sivut

MediaWiki API -lataus käyttää ulkoista internetyhteyttä, mutta
ei GPT-API:a eikä maksullisia mallikutsuja. Wikimedia voi
rajoittaa pyyntöjä; älä kierrä rajoituksia.

~~~bash
cd ~/klone-arxiv-e1 || exit 1

export KLONE_WIKIPEDIA_PUBLIC_FETCH_APPROVAL=HAE_JULKISIA_WIKIPEDIA_ARTIKKELEITA

# Korkeintaan 80 sivua kummassakin kielessä, harvempi jos
# sivut puuttuvat tai osuvat samoihin artikkeleihin.
bash scripts/klone-knowledge-atlas-phone.sh collect fi 4
bash scripts/klone-knowledge-atlas-phone.sh collect en 4

unset KLONE_WIKIPEDIA_PUBLIC_FETCH_APPROVAL

bash scripts/klone-knowledge-atlas-phone.sh status
bash scripts/klone-knowledge-atlas-phone.sh search "tieteen historia"
bash scripts/klone-knowledge-atlas-phone.sh ring 6 "Mikä on falsifioitava hypoteesi?"
~~~

Kukin erä käyttää enintään 12 API-pyyntöä, enintään 20 sivua
per pyyntö, vähintään 2 sekunnin taukoa ja yhteystiedolla
varustettua User-Agentia. Muutosta ei viedä KLONEn
Memory Core -tietokantaan eikä tallenneta neuvoston
roolien omaksi episodiseksi muistiksi.

## Miten kerätä kymmeniä tuhansia sivuja?

Käytä virallisia **MediaWiki Content File Exports**
XML-lähdepaketteja sen sijaan, että yrittäisit massakerätä
kymmeniä tuhansia artikkeleita Wikipedian API:sta.
Wikimedian vanhat XML-dumpit poistuvat käytöstä
tammikuussa 2027, joten toteutus keskittyy
uusimpien versioiden Content File Export -aineistoihin.

Viralliset osoitteet:

- https://dumps.wikimedia.org/other/mediawiki_content_current/
- https://wikitech.wikimedia.org/wiki/MediaWiki_Content_File_Exports

Tarkista ladattavan dumpin jakelijan SHA256SUMS.
V1:n paikallinen XML-tuonti ei vielä automaattisesti
vahvista tiedoston alkuperän allekirjoitusta tai SHA-summaa.
Eri tiedostojen tuontia ei pidä merkitä todistetusti
Wikimediasta saaduksi, ellei tarkistusta ole suoritettu.

Tuetut paikalliset tiedostot: XML, XML.gz ja XML.bz2.
Tuonti käyttää virtaavaa XML-jäsennintä ja vie vain
nimiavaruuden 0 artikkelit. Uudelleenohjaukset,
keskustelut ja käyttäjäsivut ohitetaan.
Teksti tallennetaan WIKITEXTINÄ, ei näennäisenä
valmiiksi puhdistettuna luonnollisena tekstinä.

Esimerkki jo valmiiksi omalla laitteella olevasta,
tarkistetusta pienestä dump-osiosta:

~~~bash
bash scripts/klone-knowledge-atlas-phone.sh import-dump \
  "$HOME/storage/downloads/wiki-part.xml.bz2" en 2000 0
~~~

Seuraava osa voidaan tuoda offset-arvolla 2000,
jos sama tiedosto sisältää riittävästi artikkeleita.
Huomaa: v1 jäsentää alusta asti myös ohitettavat
sivut, joten valtavien XML-dumppien käsittelyssä
pienemmät paikalliset osat ovat huomattavasti
käytännöllisempiä.

Älä lataa englanninkielisen Wikipedian valtavaa
raakadumppia suoraan puhelimen sisäiseen muistiin
ilman tilan ja nopeuden tarkistusta. Käytä PC:tä tai
ulkoista levyä, jos aineistot ovat hyvin suuria.
Tietokannan pehmeää rajaa voi nostaa esimerkiksi
ympäristömuuttujalla KLONE_WIKIPEDIA_ATLAS_MAX_MB=2048.

## Neuvoston ja KLONEn muiden osien integraatio

Polku:
Wikipedia API / XML → erillinen julkinen
tietokanta → SQLite/FTS5 → 72 erikoistunutta
hakunäkymää → lähdeviitteellinen lukupaketti
→ omistajan erillinen arviointi.

Knowledge Atlas ei sisällä GPT-API-kutsuja.
Uusi lähteisiin perustuva neuvostopaketti
sisältää enintään kahdeksan jäsenen tehtävät ja
niille löydetyt rajatut tekstikatkelmat lähdelinkkeineen.

Uusina API-reitteinä:
- /api/knowledge-atlas/status
- /api/knowledge-atlas/plan
- /api/knowledge-atlas/members
- /api/knowledge-atlas/members/{member_id}
- /api/knowledge-atlas/search
- /api/knowledge-atlas/council/{ring_id}

Suomenkielinen verkkonäkymä:
http://127.0.0.1:8000/knowledge-atlas

Ota KLONEn vanha palvelin hallitusti uudelleen käyttöön
päivitetyllä ohjelmistolla; älä käynnistä toista
palvelinta jo käytössä olevaan 8000-porttiin.

Hypervisor, huoneet ja päämuisti pysyvät erillään.
Hakutulokset ovat ulkoista, epäluotettavaa tietoa,
eivät itseensä kohdistuvia komentoja, mallin koulutusta,
sitovia tutkimuspäätelmiä tai neuvoston äänestyksiä.

## Tekijänoikeudet, luotettavuus ja rajoitukset

Wikipedian teksti on yleensä CC BY-SA 4.0 -lisenssin
alaista. Säilytä artikkelin versiolinkki,
tekijöiden muokkaushistoria ja lisenssiehdot.
Kuvat, videot ja ääni voivat käyttää eri lisenssejä,
eivätkä ne kuulu tietopankin tähän versioon.
Tekstimuunnelmien julkinen jakelu voi vaatia
samaa lisenssiä ja muutosten ilmoittamista.

Viranomais-, lääke- tai tutkimusväitettä ei vahvisteta
vain sillä, että se esiintyy Wikipediassa.
Wikipedian lähdeluetteloiden ja alkuperäisten
tutkimusten tarkistus kuuluu seuraavaan vaiheeseen.

Lähteet:
- https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_API_Usage_Guidelines/en
- https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits
- https://www.mediawiki.org/wiki/Extension:TextExtracts
- https://wikitech.wikimedia.org/wiki/MediaWiki_Content_File_Exports

## Seuraava KLONE-kokonaiskehitys

1. 2 000 artikkelin Android-pilotti: todelliset
   tallennustilamittarit, hakunopeus, lähdeketjun auditointi.
2. 12 000 artikkelin tietokanta: jokaiselle 72 roolille
   mittari todellisesta lähdekattavuudesta.
3. 30 000 artikkelin vaihe: Wikidata-QID, suomi–ruotsi–
   englanti-linkitys ja semanttisen toiston mittaus.
4. 72 000 artikkelin vaihe: viralliset delta-päivitykset,
   alkuperäisen dumpin checksumit ja toistettavat julkaisut.
5. Council72: katkelmien sijaan väitekohtaiset
   lähdeviitteet, aidosti vastakkaiset tulkinnat ja
   vertailu yhtä GPT-mallia vastaan.
6. Cognition Lab: erikoisalojen käsitteellinen yhteys
   ja oppimishypoteesit, mutta EI päämuistin tai
   käyttöoikeuksien muuttamista ilman erillistä auditointia.
