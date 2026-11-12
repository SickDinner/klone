"use strict";
(function () {
  const picker = document.getElementById("evidence-file");
  const status = document.getElementById("status");
  const summary = document.getElementById("summary");
  const details = document.getElementById("details");
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
    return result;
  }
  function render(data) {
    summary.replaceChildren();
    details.replaceChildren();
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
  picker.addEventListener("change", async () => {
    const file = picker.files && picker.files[0];
    if (!file) return;
    if (file.size > MAX_BYTES) {
      status.textContent = "Tiedosto on liian suuri (enintään 2 MiB).";
      return;
    }
    try {
      const data = JSON.parse(await file.text());
      if (!data || typeof data !== "object" || Array.isArray(data)) {
        throw new Error("Raportin on oltava JSON-olio");
      }
      render(data);
      status.textContent = "Raportti luettu paikallisesti: " + file.name;
    } catch (error) {
      summary.replaceChildren();
      details.replaceChildren();
      status.textContent = "Raporttia ei voitu lukea: " + error.message;
    }
  });
}());
