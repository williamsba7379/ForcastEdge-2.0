/* Read-only original ForecastEdge archive. Never writes localStorage. */
(()=>{
const nav=document.querySelector('nav'),main=document.querySelector('main');
const button=document.createElement('button');button.textContent='Original ForecastEdge';button.dataset.tab='original';nav.appendChild(button);
const section=document.createElement('section');section.id='original';section.hidden=true;
section.innerHTML='<h2>Original ForecastEdge — Week 6</h2><div class="note">October 14, 2026 baseline. Separate from your saved ForecastEdge 2.0 pool picks and experimental models. Original market lines are transcribed from the report you supplied, not independently verified. LEAN and NO BET are not wagers.</div><div class="card"><div class="row"><h3>Original predictions & grading</h3><button id="originalRefresh">Refresh finals</button></div><p class="muted" id="originalStatus">Loading archived card…</p><div id="originalContent"></div></div>';
main.appendChild(section);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const aliases={'Seattle':'SEA','Denver':'DEN','Houston':'HOU','Jacksonville':'JAX','Tennessee':'TEN','Indianapolis':'IND','Carolina':'CAR','Philadelphia':'PHI','Pittsburgh':'PIT','Tampa Bay':'TB','Baltimore':'BAL','Cleveland':'CLE','New Orleans':'NO','NY Giants':'NYG','Chicago':'CHI','Atlanta':'ATL','NY Jets':'NYJ','New England':'NE','Arizona':'ARI','LA Rams':'LAR','LA Chargers':'LAC','Kansas City':'KC','Buffalo':'BUF','Las Vegas':'LV','Dallas':'DAL','Green Bay':'GB','Washington':'WSH','San Francisco':'SF'};
const verdict=(v)=>v===null?'Pending':v===0?'Push':v>0?'✓ Win':'✕ Loss';
async function load(){
 const status=document.getElementById('originalStatus'),box=document.getElementById('originalContent');status.textContent='Checking archived predictions and final scores…';
 try{
 const [ar,sr]=await Promise.all([fetch('./data/original-forecastedge-week6-2026.json?t='+Date.now(),{cache:'no-store'}),fetch('./data/nfl-scoreboard.json?t='+Date.now(),{cache:'no-store'})]);
 if(!ar.ok)throw Error('Original prediction archive unavailable');
 const card=await ar.json();const board=sr.ok?await sr.json():{events:[]};const events=Array.isArray(board.events)?board.events:[];
 const stats={winner:[0,0,0],spread:[0,0,0],total:[0,0,0]};let html='';
 for(const g of card.games){
 const event=events.find(e=>{const t=e.competitions?.[0]?.competitors||[];return t.some(x=>x.homeAway==='away'&&x.team?.abbreviation===aliases[g.away])&&t.some(x=>x.homeAway==='home'&&x.team?.abbreviation===aliases[g.home])&&(!e.week?.number||e.week.number===6)});
 let graded=null;
 if(event?.status?.type?.completed===true){
 const t=event.competitions?.[0]?.competitors||[],a=t.find(x=>x.homeAway==='away'),h=t.find(x=>x.homeAway==='home'),as=Number(a?.score),hs=Number(h?.score);
 if(Number.isFinite(as)&&Number.isFinite(hs)){
 const predictedIsHome=g.winner===g.home,chosenScore=predictedIsHome?hs:as,otherScore=predictedIsHome?as:hs;
 const win=chosenScore===otherScore?0:chosenScore>otherScore?1:-1;
 const margin=chosenScore-otherScore+Number(g.spread);const sp=margin===0?0:margin>0?1:-1;
 const diff=as+hs-Number(g.total);const tot=diff===0?0:(g.totalDirection==='Over'?diff:-diff)>0?1:-1;
 graded={as,hs,win,sp,tot};[['winner',win],['spread',sp],['total',tot]].forEach(([k,v])=>stats[k][v>0?0:v<0?1:2]++);
 }
 }
 html+='<details class="card"><summary><b>'+esc(g.away)+' @ '+esc(g.home)+'</b> — '+esc(g.winner)+(graded?' · '+verdict(graded.win):' · Pending')+'</summary><p>Original projection: '+esc(g.scoreAway)+'–'+esc(g.scoreHome)+' · '+esc(g.rating)+'</p><p>Winner: '+esc(g.winner)+' · Spread: '+esc(g.winner)+' '+esc(g.spread)+' · Total: '+esc(g.totalDirection)+' '+esc(g.total)+'</p><p>'+(graded?'Final: '+esc(g.away)+' '+graded.as+' – '+esc(g.home)+' '+graded.hs+'<br>Winner '+verdict(graded.win)+' · Spread '+verdict(graded.sp)+' · Total '+verdict(graded.tot):'Awaiting confirmed final score in published Week 6 scoreboard.')+'</p></details>';
 }
 const summary=Object.entries(stats).map(([k,v])=>'<div class="stat">'+esc(k[0].toUpperCase()+k.slice(1))+'<b>'+v[0]+'–'+v[1]+'</b><small>'+v[2]+' push · '+(v[0]+v[1]+v[2])+' graded</small></div>').join('');
 box.innerHTML='<div class="grid">'+summary+'</div><p class="muted">Unfinished games are excluded. Spread and total are graded against the original October 14 snapshot, not closing lines. No wagers were approved.</p>'+html;
 status.textContent='Archived 14 original picks · '+stats.winner.reduce((a,b)=>a+b,0)+' confirmed finals graded'+(sr.ok?'':' · scoreboard unavailable');
 }catch(e){status.textContent='Unable to load original archive: '+e.message;box.innerHTML=''}
}
button.onclick=()=>{document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b===button));document.querySelectorAll('main section').forEach(s=>s.hidden=s!==section);load()};
document.getElementById('originalRefresh').onclick=load;
})();