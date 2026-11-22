/* Read-only four-model review tab. Does not import, modify or publish user picks. */
(function () {
  "use strict";
  const nav = document.querySelector("nav");
  const main = document.querySelector("main");
  if (!nav || !main) return;
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Four Models";
  button.dataset.tab = "four-model-review";
  const section = document.createElement("section");
  section.id = "four-model-review";
  section.hidden = true;
  section.innerHTML = '<h2>Four-model Wednesday report</h2>' +
    '<div class="note">REVIEW ONLY · NOT OFFICIAL · NO BET. Existing pool picks and frozen records are unchanged.</div>' +
    '<div class="card"><div class="row"><h3>A / B / C / C-QB</h3><button type="button" id="refreshFourModelReview">Refresh</button></div>' +
    '<p id="fourModelReviewStatus" role="status">No verified report loaded.</p>' +
    '<div id="fourModelReviewContent"></div></div>';
  nav.appendChild(button);
  main.appendChild(section);
  const status = section.querySelector("#fourModelReviewStatus");
  const content = section.querySelector("#fourModelReviewContent");
  const models = ["A", "B", "C", "C-QB"];
  const show = value => value === undefined || value === null || value === "" ? "NOT AVAILABLE" : String(value);
  const textNode = (tag, value) => {
    const node = document.createElement(tag);
    node.textContent = show(value);
    return node;
  };
  async function refresh() {
    status.textContent = "Checking review-only report…";
    content.replaceChildren();
    try {
      const response = await fetch("./data/four-model-review-latest.json?refresh=" + Date.now(), {cache:"no-store"});
      if (!response.ok) throw Error("No review report file (HTTP " + response.status + ")");
      const report = await response.json();
      if (report.status !== "REVIEW_ONLY_INCOMPLETE" || !Array.isArray(report.games) || !report.games.length)
        throw Error("Unexpected report status or empty slate");
      const title = textNode("p", "Season " + show(report.season) + " · Week " + show(report.week) +
        " · Original snapshot: " + show(report.sourceFrozenAt) + " · NOT OFFICIAL");
      content.appendChild(title);
      for (const game of report.games) {
        if (!game.models || models.some(model => !game.models[model]))
          throw Error("Incomplete four-model row; refusing partial display");
        const article = document.createElement("article");
        article.className = "card";
        article.appendChild(textNode("h3", show(game.away) + " @ " + show(game.home)));
        article.appendChild(textNode("small", "Kickoff " + show(game.date) + " · ID " + show(game.id)));
        for (const model of models) {
          const row = game.models[model];
          const p = document.createElement("p");
          p.appendChild(textNode("b", model + ": " + show(row.winner)));
          p.appendChild(textNode("small", " · Spread: " + show(row.spread) +
            " · O/U: " + show(row.overUnder) + " · Projected away–home: " +
            show(row.projectedAway) + "–" + show(row.projectedHome) +
            " · Confidence: " + show(row.confidence) +
            " · " + show(row.wagerStatus) + " · " + show(row.projectionStatus)));
          article.appendChild(p);
        }
        content.appendChild(article);
      }
      const print = document.createElement("button");
      print.type = "button";
      print.textContent = "Print review report";
      print.addEventListener("click", () => window.print());
      content.appendChild(print);
      status.textContent = report.games.length + " matchups · 4 model rows each · REVIEW ONLY / INCOMPLETE";
    } catch (error) {
      content.replaceChildren();
      status.textContent = "Four-model review unavailable: " + error.message + ". Existing picks unchanged.";
    }
  }
  button.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach(item => item.classList.toggle("active", item === button));
    document.querySelectorAll("main section").forEach(item => { item.hidden = item !== section; });
    refresh();
  });
  section.querySelector("#refreshFourModelReview").addEventListener("click", refresh);
})();
