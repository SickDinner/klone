# KLONE: tutkimus- ja kehityssuunnat

Tämä tiedosto säilyttää ehdotukset projektin versionhallinnassa. Se ei väitä
toiminnallisuuksia tuotantovalmiiksi. Kaikki kokeet ovat aluksi offline-tilassa,
deterministisiä ja Hypervisorin ulkopuolella ilman toimintavaltuuksia.

## Viisi rinnakkaista tutkimuslinjaa

1. **Neurokemiallinen ohjausmalli**: dopamiini = uutuuden tutkiminen,
   noradrenaliini = kiireellisyys, asetyylikoliini = tarkkaavaisuus,
   inhibitio = jarru. Mittarit: tehtävän onnistuminen, virheet,
   laskentakustannus ja uusittavuus. Nimet ovat analogioita.
2. **Vastatodisteita etsivä Memory**: väite, puolesta/vastaan-todisteet,
   lähderiippuvuudet, korjaukset, ristiriidat, provenance ja audit trail.
   Ei automaattista muistin uudelleenkirjoittamista.
3. **Digitaalinen agenttikoelaboratorio**: eristetyt agenttistrategiat,
   sama syöte, vakioidut siemenet, sokkoutettu arviointi, hallusinaatio-
   ja kustannusmittarit sekä toistokokeet.
4. **72 solmun neuvoa-antava hallintoverkko**: 9 rengasta × 8 solmua,
   eri arviointiroolit, dissent, abstain ja päätösten perusteluketjut.
   Äänestys ei ohita käyttöoikeuksia eikä hyväksy käyttöönottoa.
5. **Falsifiointimoottori**: ennalta lukitut hypoteesit, mittarit,
   hylkäysrajat, koeversiot ja negatiivisten tulosten arkistointi.
   Hypoteesin hylkäämättä jääminen ei todista sitä oikeaksi.

## Muut aiemmin ehdotetut suunnat, säilytettävä jonossa

- **Allekirjoitetut Android-todisteet**: laitekohtainen avain, avaimen
  julkisen osan rekisteröinti, nonce-haaste, aikaleima ja commit-sidonta.
  Allekirjoitus todistaa avaimen hallinnan, ei automaattisesti laitteen
  fyysistä identiteettiä tai testin rehellistä suoritusta.
- **Pysyvä auditointihistoria**: SQLite append-only -tapahtumat,
  ketjutetut tiivisteet, varmuuskopiointi, korjausten versiointi,
  eheystarkistukset ja palautusharjoitukset.
- **Suomenkielinen kehitystyöpöytä**: komponentit, CI/Termux,
  portit, terveystarkistukset, regressiot, evidence, Git-vertailu,
  vaiheistus ja erotus vahvistettu/oletus/avoin kysymys.
- **Automaattinen mutta rajattu testausputki**: GitHubin CI-hakija,
  paikallinen puhdas checkout, samat commitit, alkuperä- ja
  hyväksyntäportit; ei automaattista deployta.
- **Memory Phase 2B.3**: read-only corrected-lippu ja correction state,
  deterministinen replay, permissions/rooms/hypervisor sekä audit.
- **Cognition ja muistien konsolidointi**: rajatut oppimiskokeet,
  ei agentin omatoimista oikeuksien laajentamista.
- **Media Lake, Art Lab, Genomics Lab ja World Memory**: omat
  tietoluokittelut, eristetyt huoneet, lähteet ja hyväksymisrajat.
- **Silent Speech, äänen kloonaus, EEG/BCI, WorldAgents ja 3D-paikkamuisti**:
  erilliset vapaaehtoiseen käyttöön perustuvat kokeet, yksityisyys
  ja suostumus ensin.
- **72-paikkainen simulaatio**: adversaariset koalitiot, päätösten
  vakaus, vähemmistön vastalauseet, riippumattomat arvioijat.

## Toteutusjärjestys

**P0**: korjaa epäonnistuvat CI-testit, varmista Hypervisor,
permissions, audit, Memory, paikallinen Android-commit ja lähteet.

**P1**: todistemanifestin ja hyväksyntäportin integraatio,
pysyvä audit trail, laiteavaimen prototyyppi, regressioiden historia.

**P2**: viiden tutkimuslinjan koeajot ja mitattavat vertailut,
suomenkielinen raporttinäkymä.

**P3**: multimodaalinen muistijärjestelmä, ääni, EEG/BCI ja
maailmamallit erillisissä luvitetuissa kokeissa.

Kaikki kokeet: testit ensin, eksplisiittinen hylkäyskriteeri,
pienin tarvittava oikeus, ei salaisuuksia raporteissa,
ihmisen hyväksyntä ennen ulkoisia vaikutuksia.
