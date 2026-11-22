/* Read-only historical four-model display. No persistence, publication, or pick changes. */
(() => {
  'use strict';
  const nav = document.querySelector('main nav');
  const main = document.querySelector('main');
  if (!nav || !main) return;
  const button = document.createElement('button');
  button.type = 'button';
  button.dataset.tab = 'four-models';
  button.textContent = 'Four Models';
  nav.appendChild(button);
  const section = document.createElement('section');
  section.id = 'four-models';
  section.hidden = true;
  section.innerHTML = '<h2>Four Models — NFL 2026</h2><div class="note">HISTORICAL REVIEW ONLY. Archived winners are not a current verified four-model card. Original frozen picks remain unchanged. NO BET.</div><div class="card"><div class="row"><h3>Week 8 — original frozen archive</h3><button type="button" id="refreshFourModels">Refresh archives</button></div><p id="fourModelsStatus" class="muted">Not loaded</p><div id="fourModelsContent"></div></div><div class="card"><h3>Current week</h3><p>NO CURRENT VERIFIED FOUR-MODEL CARD</p><p class="muted">Current-week A/B/C/C-QB predictions are not available from these archived files. Do not substitute the unreviewed weekly baseline.</p></div>';
  main.appendChild(section);
  const status = section.querySelector('#fourModelsStatus');
  const content = section.querySelector('#fourModelsContent');
  const base = './data/four-model-head-to-head/';
  const models = ['A', 'B', 'C', 'C-QB'];
  const files = [
    {name:'2026-week-8.json', label:'Original frozen archive', expected:'FROZEN_PREKICKOFF'},
    {name:'2026-week-8-all-four-rerun-oct-28.json', label:'October 28 retrospective — REVIEW ONLY', expected:'UPDATED_FOUR_MODEL_COMPARISON_REVIEW_ONLY'}
  ];
  function node(tag, value, cls) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (value !== undefined) e.textContent = String(value);
    return e;
  }
  function valid(card, expected) {
    if (!card || card.season !== 2026 || card.week !== 8 || card.status !== expected ||
        !Array.isArray(card.games) || card.games.length !== 14) return false;
    const ids = new Set();
    for (const g of card.games) {
      if (!g || !g.id || !g.home || !g.away || !g.date || !g.picks ||
          ids.has(String(g.id)) || models.some(m => ![g.home, g.away].includes(g.picks[m]))) return false;
      ids.add(String(g.id));
    }
    return true;
  }
  function render(card, info) {
    const block = node('div');
    block.appendChild(node('h3', info.label));
    block.appendChild(node('p', 'Week 8 · 14 games · ' + card.status, 'muted'));
    const stamp = card.frozenAt || card.generatedAt;
    block.appendChild(node('p', 'Recorded timestamp: ' + (stamp || 'NOT VERIFIED'), 'muted'));
    if (info.expected !== 'FROZEN_PREKICKOFF')
      block.appendChild(node('p', 'RETROSPECTIVE REVIEW ONLY — does not replace the original frozen archive.', 'note'));
    for (const g of card.games) {
      const details = node('details');
      const heading = node('summary', g.away + ' @ ' + g.home);
      details.appendChild(heading);
      const grid = node('div', undefined, 'stats');
      for (const m of models) {
        const cell = node('div', undefined, 'stat');
        cell.appendChild(node('small', 'Model ' + m));
        cell.appendChild(node('b', g.picks[m]));
        grid.appendChild(cell);
      }
      details.appendChild(grid);
      details.appendChild(node('p', 'Spread: NOT VERIFIED · Total: NOT VERIFIED · Projected score: NOT VERIFIED · Confidence: NOT VERIFIED · NO BET', 'muted'));
      block.appendChild(details);
    }
    return block;
  }
  async function load() {
    status.textContent = 'Loading historical archives…';
    content.replaceChildren();
    let loaded = 0;
    for (const info of files) {
      try {
        const response = await fetch(base + info.name, {cache:'no-store'});
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const card = await response.json();
        if (!valid(card, info.expected)) throw new Error('Missing or inconsistent Week 8 four-model data');
        content.appendChild(render(card, info));
        loaded++;
      } catch (err) {
        content.appendChild(node('p', info.label + ': NOT VERIFIED — ' + err.message, 'note'));
      }
    }
    status.textContent = loaded + ' of 2 historical archives loaded; historical provenance not independently certified. DELIVERY_UNVERIFIED.';
  }
  button.addEventListener('click', () => {
    document.querySelectorAll('main nav button').forEach(b => b.classList.toggle('active', b === button));
    document.querySelectorAll('main section').forEach(s => {s.hidden = s !== section;});
    load();
  });
  section.querySelector('#refreshFourModels').addEventListener('click', load);
})();
