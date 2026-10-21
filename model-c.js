/* Model C pilot is read-only and never touches saved pool picks or frozen A/B records. */
(()=>{
const nav=document.querySelector('nav'),main=document.querySelector('main');
const button=document.createElement('button');button.textContent='Model C — Advanced';button.dataset.tab='model-c';nav.appendChild(button);
const section=document.createElement('section');section.id='model-c';section.hidden=true;
section.innerHTML='<h2>Model C — Advanced Matchup</h2><div class="note">NEW · Week 7 pilot: analyst-adjusted reassessment, NOT an automated recalculation. Model A and B frozen picks remain unchanged. No approved wagers.</div><div class="card"><div class="row"><h3>Week 7 predictions</h3><button id="modelCRefresh">Refresh</button></div><p class="muted" id="modelCStatus">Loading Model C…</p><div id="modelCContent"></div></div>';
section.innerHTML+='<div class="card"><div class="row"><h3>Automated Model C draft — review only</h3><button id="modelCAutoRefresh">Refresh draft</button></div><p class="muted" id="modelCAutoStatus">Loading automated draft…</p><div id="modelCAutoContent"></div></div>';main.appendChild(section);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function load(){
const status=document.getElementById('modelCStatus'),box=document.getElementById('modelCContent');status.textContent='Loading saved pilot card…';
try{
const [cr,sr]=await Promise.all([fetch('./data/model-c-week7-2026.json?t='+Date.now(),{cache:'no-store'}),fetch('./data/nfl-scoreboard.json?t='+Date.now(),{cache:'no-store'})]);
if(!cr.ok)throw Error('Model C pilot card not published yet');
const card=await cr.json(),board=sr.ok?await sr.json():{},events=board.week?.number===card.week?(board.events||[]):[];
let wins=0,losses=0,pending=0;
const rows=card.games.map(g=>{
const event=events.find(e=>String(e.id)===String(g.id));
const complete=event?.status?.type?.completed===true;
const competitors=event?.competitions?.[0]?.competitors||[];
const actual=complete?competitors.find(x=>x.winner)?.team?.displayName:null;
const result=actual?(actual===g.pick?'✓ Correct':'✕ Incorrect'):'Pending';
if(!actual)pending++;else if(actual===g.pick)wins++;else losses++;
return '<details class="card"><summary><b>'+esc(g.away)+' @ '+esc(g.home)+'</b><br>Model C: '+esc(g.pick)+' · '+result+'</summary><p>'+esc(g.reason)+'</p>'+(g.conditional?'<p class="muted">Conditional pick: starting-QB status must be checked before kickoff.</p>':'')+'</details>';
}).join('');
status.textContent='Week '+card.week+' · '+wins+'–'+losses+' graded · '+pending+' pending';
box.innerHTML='<p class="muted">'+esc(card.disclaimer)+'</p>'+rows;
}catch(e){status.textContent='Unable to load Model C: '+e.message;box.innerHTML=''}
}
async function loadAuto(){const status=document.getElementById('modelCAutoStatus'),box=document.getElementById('modelCAutoContent');try{const r=await fetch('./data/model-c-automated-draft.json?t='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('Awaiting first scheduled GitHub Actions run');const d=await r.json();status.textContent='Week '+d.week+' · generated '+d.generatedAt+' · review required';box.innerHTML='<p class="muted">'+esc(d.disclaimer)+'</p>'+d.games.map(g=>'<details class="card"><summary><b>'+esc(g.away)+' @ '+esc(g.home)+'</b><br>Draft: '+esc(g.pick)+' · NO BET</summary><p>Projected home margin: '+esc(g.homeEdgePoints)+' points</p><p>'+esc(g.reason)+'</p><p><b>Depth-chart QB1 candidate (not confirmed starter):</b></p>'+['away','home'].map(side=>'<p><small>'+esc(g[side])+': '+esc(g.quarterbacks?.[side]?.depthChartQB1Candidate||'Unavailable')+'</small></p>').join('')+'<p><b>Recent primary passer (not confirmed next starter):</b></p>'+['away','home'].map(side=>'<p><small>'+esc(g[side])+': '+esc(g.quarterbacks?.[side]?.recentPrimaryPasser||'No completed-game data')+' · '+esc(g.quarterbacks?.[side]?.recentPrimaryPasserGameDate||'Date unavailable')+'</small></p>').join('')+'<p><b>Quarterback status:</b></p>'+['away','home'].map(side=>'<p><small>'+esc(g[side])+': '+esc(g.quarterbacks?.[side]?.starter||'Starter not verified')+' · Injury: '+esc(g.quarterbacks?.[side]?.injuryStatus||'Unknown')+' · Availability: '+esc(g.quarterbacks?.[side]?.availability||'Unknown')+'</small></p>').join('')+'<p>'+esc(g.dataWarnings.join('; ')||'Documented adjustment applied')+'</p><p><b>Reported injuries (not confirmed starters):</b></p>'+['away','home'].map(side=>'<p><small>'+esc(g[side])+': '+esc((g.injuryReports?.[side]||[]).slice(0,12).map(p=>p.name+' ('+p.position+': '+p.status+')').join('; ')||'No listing available')+'</small></p>').join('')+'<p><small>Injury snapshot: '+esc(g.injuryRetrievedAt||'Unavailable')+'</small></p></details>').join('')}catch(e){status.textContent=e.message;box.innerHTML=''}}
button.onclick=()=>{document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b===button));document.querySelectorAll('main section').forEach(s=>s.hidden=s!==section);load();loadAuto()};
document.getElementById('modelCRefresh').onclick=load;document.getElementById('modelCAutoRefresh').onclick=loadAuto;
})();