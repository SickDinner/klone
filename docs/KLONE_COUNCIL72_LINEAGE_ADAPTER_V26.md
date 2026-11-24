# Council72 → Evidence Lineage v2.6: lukuadapteri, ei luottamusraja

Tämä draft-PR on jatkoa KLONEn v2.6:n riippuvuusverkolle (PR #196). Tarkoitus on kytkeä **oikea Council72:n session replay** v2.6:n lähdeverkkoon poistamatta raakadataa tai päättelemättä aineiston aitoutta. Toteutus on luku-/analyysikäyttöön; ei muistikoneen päivitystä, viestien lähettämistä, moduulien suoritusta eikä hyväksyntävaltaa.

- `project_replayable_council_session` tekee ensin `council72_session.session_replays`-tarkistuksen käyttäen nykyistä katalogia ja koodia. Replay on yhdenmukaisuustarkistus, **ei** lähettäjän/lähteen autentikointi.
- Käyttää jokaisen kierroksen olemassa olevaa `validate_step`-havaintoa. Tuottaa vain rajatut ID:t, ilmoitetun ryhmän ja stance-merkinnän sekä **kutsujan erikseen toimittaman SHA-256**-tiivisteen. Se ei keksi datan tiivistettä pelkästä lähdeviitteen merkkijonosta; puuttuva tai ylimääräinen tiiviste torjutaan.
- Muuntaa Council72:n `public/restricted/sealed`-luokat eksplisiittisesti huoneisiin `public-room/restricted-room/sealed-room` ja niiden `public/personal/intimate`-luokituksiin; havaintojen yhdisteleminen yli rajojen joutuu karanteeniin. Näin ei luovuteta raakasisältöä.
- Korjaukset säilyvät ketjussa ja vanhat kannat lakkaavat laskemasta uusia ääniä. Jos Council72:n korjaus nostaa luokittelua, v2.6:n nykyinen graafi **torjuu** suoran saman ketjun yli luokkien tekemisen, kunnes luotettu erillinen kohde- ja deklassifiointipolitiikka on suunniteltu. Tämä on tarkoituksellinen fail-closed-raja.
- Tuloksessa `eligible_for_real_world_use=false` **aina**, `approval_granted=false` ja `memory_write_enabled=false`; synteettinen demo saa `simulation_only`-statuksen.

**Puuttuvat portit:** oikea lähtöaineiston hashin varmennus erillisellä lukuadapterilla, yksityisen datan oikea `SafeReadPipeline` + audit + egress, Council72:n ylläpitäjien tunnistus, erillinen hyväksyntä-UID sekä laitekohtaiset hyökkäys- ja regressiotestit.

Testaa kohdennetusti: `PYTHONPATH=src python -m unittest discover -s tests -p 'test_council72_lineage_adapter_v26.py' -v`. Paikallisessa eristetyssä testipaketissa puuttuvia laajan KLONE-projektin riippuvuuksia vaativat oikeat Council72-integraatiotestit ohitetaan; täydet integraatiotestit tulee ajaa GitHubin CI:ssä ja Androidilla.
