/* Model C pilot is read-only and never touches saved pool picks or frozen A/B records. */
(()=>{
const nav=document.querySelector('nav'),main=document.querySelector('main');
const button=document.createElement('button');button.textContent='Model C — Advanced';button.dataset.tab='model-c';nav.appendChild(button);
const section=document.createElement('section');section.id='model-c';section.hidden=true;
section.innerHTML='<h2>Model C — Advanced Matchup</h2><div class="note">NEW · Week 7 pilot: analyst-adjusted reassessment, NOT an automated recalculation. Model A and B frozen picks remain unchanged. No approved wagers.</div><div class="card"><div class="row"><h3>Week 7 predictions</h3><button id="modelCRefresh">Refresh</button></div><p class="muted" id="modelCStatus">Loading Model C…</p><div id="modelCContent"></div></div>';
main.appendChild(section);
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
button.onclick=()=>{document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b===button));document.querySelectorAll('main section').forEach(s=>s.hidden=s!==section);load()};
document.getElementById('modelCRefresh').onclick=load;
})();