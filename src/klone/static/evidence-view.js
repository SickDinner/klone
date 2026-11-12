"use strict";
(function () {
  const picker = document.getElementById("evidence-file");
  const status = document.getElementById("status");
  const summary = document.getElementById("summary");
  const details = document.getElementById("details");
  const controls = document.getElementById("forensics-controls");
  const historySection = document.getElementById("forensics-history-section");
  const history = document.getElementById("forensics-history");
  const comparisonSection = document.getElementById("forensics-comparison");
  const pair = document.getElementById("forensics-pair");
  const search = document.getElementById("forensics-search");
  const qualityPicker = document.getElementById("forensics-quality");
  const ciPicker = document.getElementById("forensics-ci");
  const beforePicker = document.getElementById("forensics-before");
  const afterPicker = document.getElementById("forensics-after");
  let currentForensics = null;
  let readGeneration = 0;
  const MAX_BYTES = 2 * 1024 * 1024;
  const text = (value) => String(value == null ? "ei tietoa" : value);
  function node(tag, value) {
    const element = document.createElement(tag);
    element.textContent = text(value);
    return element;
  }
  function table(headers, rows) {
    const result = document.createElement("table");
    const head = document.createElement("tr");
    headers.forEach((item) => head.appendChild(node("th", item)));
    result.appendChild(head);
    rows.forEach((values) => {
      const row = document.createElement("tr");
      values.forEach((value) => row.appendChild(node("td", value)));
      result.appendChild(row);
    });
    const wrapper = document.createElement("div");
    wrapper.className = "scroll";
    wrapper.appendChild(result);
    return wrapper;
  }
  function render(data) {
    summary.replaceChildren();
    details.replaceChildren();
    history.replaceChildren();
    controls.hidden = true;
    historySection.hidden = true;
    comparisonSection.hidden = true;
    currentForensics = null;
    if (data.kind === "klone-evidence-forensics") {
      if (data.schema_version !== 1 || !Array.isArray(data.runs) || data.runs.length > 1000 ||
          data.runs.some((r) => !r || typeof r !== "object" || !r.stages || !r.artifacts || !r.quality)) {
        throw new Error("Virheellinen Forensics v1 -raportti");
      }
      currentForensics = data;
      controls.hidden = false;
      comparisonSection.hidden = false;
      beforePicker.replaceChildren();
      afterPicker.replaceChildren();
      data.runs.forEach((r, index) => {
        [beforePicker, afterPicker].forEach((select) => {
          const option = node("option", r.run_name);
          option.value = String(index);
          select.appendChild(option);
        });
      });
      afterPicker.value = String(Math.max(0, data.runs.length - 1));
      renderForensics(data);
      renderPair();
      return;
    }
    if (data.categories && Array.isArray(data.runs)) {
      const names = {
        verified: "Eheä paikallinen aineisto",
        incomplete: "Puutteellinen",
        contradictory: "Ristiriitainen",
        unexamined: "Tutkimaton"
      };
      summary.appendChild(node("p", "Laatuluokittelu, ajoja: " + data.runs.length));
      summary.appendChild(table(["Luokka", "Määrä"],
        Object.keys(names).map((key) => [names[key], data.categories[key] || 0])));
      summary.appendChild(node("p", "Vahvistetut regressiosiirtymät: " +
        text(data.confirmed_regression_transitions) +
        ", epävarmat siirtymät: " + text(data.unknown_transition_count)));
      details.appendChild(table(["Ajo", "Laatuluokka", "Peruste", "Testit", "Virheet"],
        data.runs.map((r) => [r.run_name, names[r.category] || "Tuntematon",
          r.reason, r.required_stages_passed === true ? "OK" : "Ei vahvistettu",
          Array.isArray(r.errors) ? r.errors.join(", ") : "Virheellinen muoto"])));
      summary.appendChild(node("p", "Alkuperää ei ole varmennettu. Käyttöönottoa ei ole hyväksytty."));
    } else if (Array.isArray(data.nodes) && Array.isArray(data.edges)) {
      summary.appendChild(node("p", "Regressioverkosto: " + data.nodes.length +
        " solmua, " + data.edges.length + " yhteyttä"));
      details.appendChild(table(["Solmu", "Tyyppi"],
        data.nodes.map((n) => [n.id, n.type])));
      details.appendChild(node("p", "Yhteydet ovat tutkimusvihjeitä, eivät syy-seuraustodisteita."));
    } else if (Array.isArray(data.runs)) {
      const runs = data.runs;
      summary.appendChild(node("p", "Testiajoja: " + runs.length));
      details.appendChild(table(
        ["Ajo", "Commit", "Eheys", "Testit", "Päätös"],
        runs.map((r) => [r.run_name, r.commit,
          r.integrity_ok === true ? "OK" : "EI",
          r.required_stages_passed === true ? "OK" : "EI", r.decision])
      ));
      if (Array.isArray(data.comparisons)) {
        details.appendChild(node("h2", "Regressiovertailut"));
        details.appendChild(table(
          ["Edellinen", "Seuraava", "Regressiot", "Palautumiset", "Epävarmat", "Vertailukelpoinen"],
          data.comparisons.map((c) => [
            c.from_run, c.to_run, (c.regressed_stages || []).join(", "),
            (c.recovered_stages || []).join(", "),
            (c.unknown_transitions || []).join(", "), c.comparable === true ? "Kyllä" : "Ei"
          ])
        ));
      }
    } else if (data.claims && data.shadow_review && Array.isArray(data.next_actions)) {
      summary.appendChild(node("p", "Päätös: " + text(data.decision)));
      details.appendChild(table(["Prioriteetti", "Tehtävä", "Peruste"],
        data.next_actions.map((a) => [a.priority, a.kind, a.reason])));
      details.appendChild(node("p", "Alkuperä varmennettu: EI. Käyttöönotto hyväksytty: EI."));
    } else {
      throw new Error("Tuntematon raporttimuoto");
    }
  }
  const labels = {verified: "Eheä paikallinen aineisto", incomplete: "Puutteellinen",
    contradictory: "Ristiriitainen", unexamined: "Tutkimaton"};
  const actionLabels = {
    inspect_source_artifacts: "Katso alkuperäinen manifesti ja lokit. Älä rakenna puuttuvaa historiallista pakettia.",
    original_manifest_missing: "Etsi alkuperäinen manifesti ja paketti. Pidä puuttuvat tiedot avoimina.",
    investigate_invalid_or_mismatched_files: "Tarkista virheelliset tai poikkeavat lähdetiedostot käsin.",
    investigate_content_mismatch: "Selvitä manifestin ja lokin ristiriita alkuperäisistä tiedostoista.",
    review_unverified_provenance: "Tarkista aineiston alkuperä erikseen. Tiivisteet kertovat nykyisistä tavuista.",
    verify_provenance: "Varmenna alkuperä erikseen",
    investigate_mismatch: "Selvitä puuttuva tai ristiriitainen vertailunäyttö",
    reproduce_in_clean_worktree: "Toista testit saman commitin erillisessä worktreessä"
  };
  const reasonLabels = {
    "Origin of local device and GitHub CI export is not authenticated": "Paikallisen laitteen ja CI-viennin alkuperää ei ole varmennettu.",
    "Cross-environment evidence incomplete or inconsistent": "Ympäristöjen vertailunäyttö on puutteellinen tai ristiriitainen.",
    "Re-run the same commit in an isolated environment": "Aja sama commit erillisessä testiympäristössä."
  };
  const tri = (value) => value === true ? "Kyllä (raportin mukaan)" : value === false ? "Ei" : "Tuntematon";
  function appendTable(target, headers, rows) { target.appendChild(table(headers, rows)); }
  function renderForensics(data) {
    summary.replaceChildren();
    details.replaceChildren();
    history.replaceChildren();
    const cards = node("div", "");
    cards.className = "forensic-cards";
    [["Ajoja", data.runs.length], ...Object.keys(labels).map((key) => [labels[key], data.categories?.[key] ?? "ei tietoa"]),
      ["Paikalliset regressiosiirtymät", data.confirmed_regression_transitions],
      ["Epävarmat siirtymät", data.unknown_transition_count]].forEach(([title, count]) => {
      const card = node("div", ""); card.className = "forensic-card";
      card.appendChild(node("strong", count)); card.appendChild(node("span", title)); cards.appendChild(card);
    });
    summary.appendChild(cards);
    summary.appendChild(node("p", "Tiedostoeheys, manifestin väite ja lokin väite ovat eri tietoja. Alkuperää tai historiallista testisuoritusta ei tällä näkymällä varmenneta. Käyttöönottoa ei hyväksytä."));
    summary.appendChild(node("p", "Raportin ilmoittama analyysitiiviste: " + text(data.analysis_sha256)));
    const filtered = data.runs.filter((r) =>
      (qualityPicker.value === "all" || r.quality.category === qualityPicker.value) &&
      (ciPicker.value === "all" || r.github?.state === ciPicker.value) &&
      (!search.value || [r.run_name, r.commit].some((v) => text(v).toLowerCase().includes(search.value.toLowerCase()))));
    details.appendChild(node("p", filtered.length + (filtered.length === 1 ? " ajo" : " ajoa") + " rajauksessa. Näytetään enintään 200 kerrallaan."));
    filtered.slice(0, 200).forEach((r) => {
      const item = document.createElement("details");
      item.appendChild(node("summary", text(r.run_name) + " · " + (labels[r.quality.category] || "Tuntematon") + " · " + text(r.commit)));
      appendTable(item, ["Tarkistus", "Tulos"], [
        ["Manifesti", r.manifest?.state], ["Manifesti rakenteellisesti kelvollinen", tri(r.manifest?.structure_valid)],
        ["Paketti", r.packet?.state], ["Paketti vastaa lähdeaineistoa", tri(r.packet?.matches_source)],
        ["CI-väite", r.github?.state], ["CI ja paikallinen väite yhteensopivat", tri(r.github_comparison?.consistent_claims)],
        ["Alkuperä", "Ei riippumattomasti varmennettu"], ["Käyttöönotto", "Ei hyväksyntää"]]);
      item.appendChild(node("h3", "Testivaiheet"));
      appendTable(item, ["Vaihe", "Manifestin status", "Exit code", "Lokin väite", "Näyttö"],
        Object.entries(r.stages).map(([name, stage]) => [name, stage?.declared_status,
          stage?.declared_exit_code, stage?.log_evidence?.reported_status,
          stage?.log_evidence?.summary || stage?.log_evidence?.reason]));
      item.appendChild(node("h3", "Artefaktien eheys"));
      appendTable(item, ["Tiedosto", "Tila", "Tavuja", "SHA-256"],
        [...Object.entries(r.artifacts).map(([name, a]) => [name, a?.state, a?.bytes, a?.sha256]),
          [r.packet?.filename, r.packet?.state, r.packet?.bytes, r.packet?.sha256]]);
      item.appendChild(node("h3", "Ristiriidat ja avoimet tiedot"));
      item.appendChild(node("p", Array.isArray(r.contradictions) && r.contradictions.length ? r.contradictions.join(", ") : "Ei raportoitua ristiriitaa. Tämä ei yksin vahvista onnistumista."));
      item.appendChild(node("p", Array.isArray(r.errors) ? r.errors.join(", ") || "Ei tiedostovirheitä raportissa." : "Virhetiedot puuttuvat."));
      item.appendChild(node("h3", "Palautus- ja tutkimustoimi"));
      item.appendChild(node("p", actionLabels[r.recovery?.action] ||
        text(r.recovery?.action) + ": " + text(r.recovery?.recommendation)));
      if (Array.isArray(r.decision_dossier?.next_actions)) {
        appendTable(item, ["Prioriteetti", "Tutkimustoimi", "Peruste"], r.decision_dossier.next_actions.map((a) =>
          [a?.priority, actionLabels[a?.kind] || a?.kind, reasonLabels[a?.reason] || a?.reason]));
      }
      details.appendChild(item);
    });
    historySection.hidden = false;
    history.appendChild(node("p", "Hakemiston nimen mukainen järjestys ei todista aikaa tai syy-yhteyttä. Vahvistus koskee vain paikallisesti yhteensopivia väitteitä."));
    appendTable(history, ["Edellinen", "Seuraava", "Regressiot", "Palautumiset", "Tuntemattomat", "Vertailukelpoinen"],
      (Array.isArray(data.comparisons) ? data.comparisons : []).map((c) => [c?.from_run, c?.to_run,
        (c?.regressed_stages || []).join(", "), (c?.recovered_stages || []).join(", "),
        (c?.unknown_transitions || []).join(", "), tri(c?.comparable)]));
    const rejected = Array.isArray(data.rejected_entries) ? data.rejected_entries : [];
    if (rejected.length) {
      history.appendChild(node("h3", "Hylätyt hakemistomerkinnät"));
      appendTable(history, ["Nimi", "Syy"], rejected.map((r) => [r?.name, r?.reason]));
    }
    const graph = data.regression_graph;
    history.appendChild(node("p", "Regressioverkosto: " + (Array.isArray(graph?.nodes) ? graph.nodes.length : "ei tietoa") +
      " solmua. Verkosto on tutkimusvihje, ei kausaalinen todistus."));
  }
  function renderPair() {
    pair.replaceChildren();
    const data = currentForensics;
    const a = data?.runs[Number(beforePicker.value)], b = data?.runs[Number(afterPicker.value)];
    if (!a || !b) return;
    appendTable(pair, ["Tieto", "Lähtöajo", "Vertailuajo"], [
      ["Ajo", a.run_name, b.run_name], ["Commit", a.commit, b.commit],
      ["Laatuluokka", labels[a.quality.category], labels[b.quality.category]],
      ...Object.keys(a.stages).map((name) => [name + " · manifesti / loki",
        text(a.stages[name]?.declared_status) + " / " + text(a.stages[name]?.log_evidence?.reported_status),
        text(b.stages[name]?.declared_status) + " / " + text(b.stages[name]?.log_evidence?.reported_status)])]);
    const known = (data.comparisons || []).find((c) => c.from_run === a.run_name && c.to_run === b.run_name);
    pair.appendChild(node("p", known ? "Raportin vertailukelpoisuus: " + tri(known.comparable) :
      "Raportti ei sisällä vahvistettua siirtymävertailua tälle parille. Näytetään vain kentät rinnakkain."));
  }
  [search, qualityPicker, ciPicker].forEach((element) => element.addEventListener("input", () => {
    if (currentForensics) renderForensics(currentForensics);
  }));
  [beforePicker, afterPicker].forEach((element) => element.addEventListener("change", renderPair));
  picker.addEventListener("change", async () => {
    const generation = ++readGeneration;
    const file = picker.files && picker.files[0];
    if (!file) return;
    if (file.size > MAX_BYTES) {
      currentForensics = null;
      summary.replaceChildren(); details.replaceChildren(); history.replaceChildren();
      controls.hidden = true; historySection.hidden = true; comparisonSection.hidden = true;
      status.textContent = "Tiedosto on liian suuri (enintään 2 MiB).";
      return;
    }
    try {
      const raw = await file.text();
      if (generation !== readGeneration) return;
      const data = JSON.parse(raw);
      if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("Raportin on oltava JSON-olio");
      render(data);
      status.textContent = "Raportti luettu paikallisesti: " + file.name;
    } catch (error) {
      if (generation !== readGeneration) return;
      currentForensics = null;
      summary.replaceChildren(); details.replaceChildren(); history.replaceChildren();
      controls.hidden = true; historySection.hidden = true; comparisonSection.hidden = true;
      status.textContent = "Raporttia ei voitu lukea: " + error.message;
    }
  });
  const embedded = document.getElementById("initial-evidence");
  if (embedded) {
    try { render(JSON.parse(embedded.textContent)); status.textContent = "Mukana oleva raportti luettu paikallisesti."; }
    catch (error) { status.textContent = "Mukana olevaa raporttia ei voitu lukea: " + error.message; }
  }
}());
