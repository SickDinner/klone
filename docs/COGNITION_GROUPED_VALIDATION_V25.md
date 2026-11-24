# KLONE Cognition × Council72: lähderyhmittäinen luotettavuusmittaus v2.5

**Laboratoriomoduuli, ei tuotannon päätösvaltaa.** Suunniteltu rinnalle `cognition_metrics.py`-moduulin tavallisen Brier-pisteytyksen sekä `council72_cross_review.py`-neuvostotarkastelun. Alustava syy toteutukselle: 72 toisilleen kopioitua mielipidettä eivät ole 72 toisistaan riippumatonta havaintoa.

## Toiminta

`evaluate_grouped_predictions(predictions, training_source_groups, minimum_declared_groups=5, calibration_bins=10)` laskee:

- `naive_brier`: jokainen ennuste samanarvoisena (näyttää harhaisen kertautumisen).
- `source_group_balanced_brier`: ensin keskiarvo kullekin *väitetylle* lähderyhmälle ja sitten lähderyhmien keskiarvo.
- `source_group_balanced_ece`: ryhmittäin painotettu expected calibration error, jossa yhden ryhmän kokonaispaino on sama riippumatta ennusteiden määrästä.
- `largest_declared_group_fraction`: suurimman ryhmän osuus kaikista arvioiduista esimerkeistä; korrelaation riskisignaali.
- `assessment`: jos väitettyjä ryhmiä on liian vähän, `insufficient_declared_groups`, muuten `manual_review_required`.

Jokainen ennuste vaatii yksikäsitteisen `item_id`:n, väitetyn `declared_source_group`:n, todennäköisyyden `[0,1]` ja jälkikäteen mitatun binäärisen totuusarvon. Harjoitusaineiston ryhmä saa olla **vain** harjoitusjoukossa: tietovuodon tunnistaminen hylkää koko mittauksen eikä vain merkitse varoitusta. Laskenta on determinististä, täysin offline ja vain lukua; ei laitteistotoimintoja eikä muistin päivityksiä.

## Esimerkkitulkinta

Jos Council72:n 72 agenttia tuottaa 72 ennustetta, jotka kaikki perustuvat samaan lähdeketjuun, `prediction_count=72` mutta `declared_source_group_count=1`. Silloin `assessment=insufficient_declared_groups` riippumatta ryhmän mahdollisesti täydellisestä ennustetarkkuudesta. Tämä ei väitä yksittäisten agenttien olevan tarpeettomia — niiden tehtävänä voi olla tulkinnan riippumaton virheentarkastus.

**Keskeinen rajoitus:** lähderyhmätunnisteet tulevat kutsujalta; moduuli ei tarkista niiden todellista riippumattomuutta, havaintojen oikeellisuutta tai lähteen autentikointia. Siksi `origin_authenticated=False`, `independent_sources_verified=False` ja `deployment_approval=False` myös silloin, kun pisteet ovat täydelliset. Usean tahallaan eri nimellä merkityn alias-lähteen tunnistus vaatii erillisen, luotetun provenance-verkon (suunniteltu seuraavaksi).

## Integraation ehdot

Cognition Lab lähettää ainoastaan verifioidun jälkikäteisen arviointiaineiston; Council72:n teksti tai simuloitu agentin itsearvio ei kelpaa totuusarvoksi. Mission Controlissa pistemittarit tulee näyttää rinnakkain, mutta **tarkkuutta ja todennettua lähteiden riippumattomuutta ei pidä yhdistää yhdeksi luvuksi**. Hypervisor ja Approval-palvelu eivät saa päätellä käyttöoikeuksia näistä pistemittareista.

## Testit

`PYTHONPATH=src python -m unittest discover -s tests -p test_cognition_grouped_validation_v25.py -v`

22 paikallista unit-testiä: korreloitu 72-agentin joukko, lähderyhmien epätasainen painotus, harjoitus-/testivuoto, puuttuvat tai vääräntyyppiset arvot, väärentämättömyysväitteiden kielto ja determinismi.
