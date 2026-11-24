# KLONE Evidence Counterfactual v2.7 — laboratoriototeutus

## Tavoite

Lähderyhmän poistamiskoe (*leave-one-declared-source-group-out*) kertoo,
mitkä Council72:n ja tutkimuksen väitetyt johtopäätökset muuttuvat, jos yksi
syötteessä ilmoitettu lähderyhmä menettää uskottavuutensa.

## Toiminta

- Lähtötila validoidaan aiemmalla `analyze_lineage`-tarkistimella.
- Kustakin tarkasteltavasta lähderyhmästä poistetaan sen havainnot ja kaikki
  niihin riippuvuudella tai korjausviittauksella kytkeytyvät jälkeläiset.
- Vaihtoehtoinen tila lasketaan uudelleen ja verrataan alkuperäiseen.
- Aiemmin korjattu väite ei saa muuttua uudeksi puoltavaksi kandidaatiksi
  vain siksi, että korjaus poistetaan simulaatiosta. Tällainen mahdollinen
  historian palautuminen merkitään
  `unresolved_historical_supersession_requires_review`.
- Raportin lähderyhmiä kuvataan SHA-256-vihjeillä, ei raakasisällöllä.
  **Vihjeet eivät ole anonymisointia**; tunnetut lyhyet nimet voidaan arvata.
- Jos lähderyhmiä on enemmän kuin testausbudjetti,
  `coverage_complete=false` eikä analyysi esitä kattavuusväitettä.

## Rajat ja uhkamalli

Tämä on deterministinen, vain muistissa toimiva **arviointikomponentti**.
Se ei kirjoita tietokantaan, lähetä verkkoon, muuta muistia, käynnistä agentteja,
myönnä oikeuksia eikä hyväksy julkaisuja.

Ryhmät, riippuvuudet ja tiivisteet ovat ilmoitettuja tietoja, eivät
itsessään varmennettua alkuperää. Yksi lähteestä riippumaton nimi ei
osoita riippumatonta todistetta. Simulaatio ei korjaa tätä ongelmaa;
se auttaa tunnistamaan riippuvuuksista aiheutuvan päätösten herkkyyden.

`candidate_for_manual_review` ei tarkoita valtuutusta. Hypervisor, eri
käyttöjärjestelmäidentiteetti, allekirjoitettu hyväksyntäketju ja ulkoinen
auditointitarkistuspiste pysyvät erillisinä vaatimuksina.

## KLONEn moduulien yhdistäminen myöhemmin

1. **Council72:** lähderyhmän poistosta syntyvä hauraus tuottaa ehdotuksen
   lisätodisteen hakemisesta — ei automaattista neuvoston päätöstä.
2. **Memory Core:** korjaukset, supersession ja alkuperäinen tapahtumahistoria
   säilyvät; vanhaa väitettä ei aktivoida uudelleen ilman uutta näyttöä.
3. **Hypervisor:** mahdolliset toiminnot vaativat erillisen, auditoidun
   capability-tarkistuksen, jota tämä moduuli ei toteuta.
4. **Genomics, media ja simulation:** lähderyhmästä riippuvien tulosten
   simuloitu poistuminen ei avaa arkaluonteisia huoneita toisille agenteille.
5. **Mission Control:** voidaan näyttää hauraiden väitteiden lukumäärät,
   kattavuus ja ristiriidat paljastamatta lähteiden raakasisältöä.
6. **Cognition Lab:** verrataan lähtöväitteiden kalibrointia ja
   lähderyhmittäistä riippuvuutta erillisessä, todennetussa testiaineistossa.

## Testinäyttö

Paikallinen eristetty laboratorio: 17 uutta v2.7-testiä OK,
41 v2.6:n riippuvuusverkkotestiä OK ja 22 Council72-työjonotestiä OK.
Koko GitHubin ja Android/Termuxin regressiot koskevat vasta tulevaa PR-committia,
eikä niitä saa merkitä läpäistyiksi ennen varsinaista ajoa.
