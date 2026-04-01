# Kerroskoherenssi Ja Relevanssi

Taman reposta suurin riski ei ole yksittainen endpoint-bugi vaan hiljainen arkkitehtuurinen drift: uusi shell, projektiokerros tai UI-paneeli alkaa elaa omana "totuutenaan" ilman selkeaa omistajaa, room-scopea, audit-polkuja tai poistumissuunnitelmaa.

Tavoite ei ole lisata mahdollisimman monta kerrosta. Tavoite on pitaa jokainen uusi kerros:

- relevanttina oikeaan kayttotapaukseen
- koherenttina nykyisten trust-zone-, room- ja guard-saantojen kanssa
- palautettavissa takaisin olemassa olevaan truth layeriin
- evaluoitavana ja poistettavana, jos se ei tuota lisaarvoa

## Pakolliset portit uudelle kerrokselle

Jokainen uusi kerros, shell tai projektiopolku kannattaa paastaa sisaan vasta kun seuraavat kohdat on nimetty eksplisiittisesti:

1. Truth layer
   Mihin olemassa olevaan lahteeseen kerros nojaa? Uusi kerros ei saa luoda toista totuusvarastoa ilman erillista perustelua.

2. Trust zone ja room-scope
   Mihin vyohykkeeseen data kuuluu ja milla huone- tai roolirajauksella se saa nakya?

3. Read/write posture
   Onko kerros read-only shell, bounded local projection vai oikea write-surface? Oletus on aina read-only ensin.

4. Audit ja provenance
   Miten pyynto, reititys, paatokset ja mahdolliset muutokset kirjataan? Miten vastaus sidotaan lahteisiin?

5. Output guard
   Mita tapahtuu summary-only-tilassa tai korkeamman luokituksen huoneissa? Sama kerros ei saa ohittaa nykyista output-politiikkaa.

6. UI-sijoitus
   Missa nakymassa kerros elaa ja mita operaattori oikeasti tekee silla? Jos kayttotapausta ei voi kuvata yhdella lauseella, kerros on todennakoisesti liian epamaarainen.

7. Testit
   Uusi kerros tarvitsee:
   - feature-tason vaihetai regressiotestin
   - yhden cross-layer-testin, joka varmistaa route -> capability -> seam -> blueprint -linjauksen

## Suositeltu kypsymispolku

Turvallisin tapa kasvattaa jarjestelmaa on etta uusi kyvykkyys etenee seuraavassa jarjestyksessa:

1. Read-only shell
   Nayta vain mita nykyisesta datasta voidaan projisoida turvallisesti.

2. Bounded local projection
   Salli laskenta tai renderointi, mutta ala kirjoita johdettuja artefakteja takaisin pysyvaan indeksiin.

3. Cross-layer linkitys
   Kytke kerros muihin moduuleihin vasta kun room-scope, provenance ja audit-polku ovat selvilla.

4. Audited write surface
   Vasta taman jalkeen kannattaa harkita mutation-surfacea, ja silloinkin vain rajattuna, auditoituna ja roolisuojattuna.

5. Supervisor automation
   Automaattinen orkestrointi tulee viimeiseksi, ei ensimmaiseksi.

## Relevanssirubriikki

Kerros kannattaa pitaa hengissa vain jos kaikki seuraavat pysyvat totena:

- Se ratkaisee yhden selkean operaattoriongelman.
- Se reuseaa olemassa olevaa governed dataa.
- Sen kayttaytyminen on deterministic tai ainakin bounded ja selitettavissa.
- Silla on nimitetty omistaja tai supervisor.
- Sen voi poistaa ilman etta ensisijainen truth layer hajoaa.

Jos jokin naista ei tayty, kerros kannattaa joko sulauttaa olemassa olevaan moduuliin tai jattaa kokeelliseksi sivupoluksi, ei kanoniseksi ominaisuudeksi.

## Mista drift yleensa alkaa

Yleiset hajoamiskohdat ovat:

- sama data projisoidaan kahteen paikkaan eri semantiikalla
- uusi UI-paneeli tulee ennen capability- ja seam-kuvausta
- feature tekee "vain pienen" write-polun ilman audit-ketjua
- uusi laskentakerros ei kerro mita se ei tee
- luottamustaso ja room-scope jaavat implisiittisiksi

## Kaytannon laatukynnys

Ennen kuin uusi kerros merkitsee kanoniseksi, tarkista ainakin tama:

- blueprintissa on selvasti nimetty moduuli, tarkoitus ja output
- service seam kuvaa kerroksen turvallisuusposturen
- capability-katalogi osoittaa oikeaan routeen
- route toimii ilman uutta hallitsematonta tietovarastoa
- testit varmistavat feature-kayttaytymisen
- meta-testit varmistavat arkkitehtuurisen linjauksen

## Esimerkki: depth-map shell

Nykyinen `V1.3`-depth-map on hyva malli lisakerrokselle, koska se pysyy rajattuna:

- upload-polku on transientti
- asset-polku reuseaa olemassa olevaa indeksoitua image-assetia
- derived-kuvaa ei kirjoiteta takaisin asset-indexiin
- capability on eksplisiittinen
- UI kertoo etta kyse on 2.5D-approksimaatiosta, ei opitusta totuusmallista

Juuri taman mallin kannattaa toistua myos tulevissa lisa- ja simulointikerroksissa.
