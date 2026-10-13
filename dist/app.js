const dateAfter = days => {const d=new Date();d.setDate(d.getDate()+days);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
document.querySelector('#start').value=dateAfter(30);
document.querySelector('#end').value=dateAfter(34);
document.querySelector('#start').min=dateAfter(1);
document.querySelector('#end').min=dateAfter(2);
const $=selector=>document.querySelector(selector);
const escapeHTML=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const rupees=paise=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(paise/100);
const friendlyDate=value=>new Date(value+'T12:00:00').toLocaleDateString('en-GB',{day:'numeric',month:'short'});
const clockTime=value=>value?value.slice(11,16):'TBC';
const names={orchestrator:'Orchestrator',flights:'Flight agent',stays:'Stay agent',activities:'Activity agent',team:'Team',user:'You'};
const colors={flights:'#4658a8',stays:'#147d76',activities:'#93bda6',meals:'#d8ad80',local_transport:'#869fba',contingency:'#dce4e9'};
const costNames={flights:'Flights',stays:'Accommodation',activities:'Activities',meals:'Meals allowance',local_transport:'Local transport',contingency:'Contingency'};
let busy=false,lastPlan=null,eventCount=0,capabilities={},activeRequest=null;
window.clearPrivatePlan=()=>{window.dispatchEvent(new Event('roam:clear-results'));activeRequest?.abort();lastPlan=null;$('#result').replaceChildren();$('#result').hidden=true;$('#view-plan').hidden=true;$('#trace').replaceChildren();$('#empty').hidden=false;};
function safeURL(value){try{const u=new URL(value);return u.protocol==='https:'?u.href:null;}catch{return null;}}
function showError(message){$('#error').textContent=message;$('#error').hidden=false;}
function updateMode(){
  const mode=$('#mode').value;
  $('#mode-badge').textContent=mode==='live'?'Real search data':'Sample data';
  $('#mode-note').textContent=mode==='demo'?'Demo runs the real coordination workflow using fictional offers and rule-based specialists. No AI calls or bookings.':mode==='ai'?'Separate AI agents coordinate over fictional travel offers. Uses Groq with validated results and cached decisions. Your Groq account limits apply.':'Groq agents use real flight, hotel and place searches. Up to 3 new SerpApi searches per trip; cached searches are reused. Attraction fees may be estimates.';
}
let airports={}, locationLabels=new Map();
const airportLabel=(code,city)=>`${city.name}, ${city.country} · ${code} — ${city.airport||code}`;
function airportCode(value){
  const text=value.trim(), code=text.toUpperCase();
  if(airports[code])return code;
  if(locationLabels.has(text))return locationLabels.get(text);
  const matches=Object.keys(airports).filter(c=>airports[c].name.toLowerCase()===text.toLowerCase());
  return matches.length===1?matches[0]:null;
}
function validateLocation(input){
  const code=airportCode(input.value);
  input.setCustomValidity(code?'':'Select a matching airport suggestion or enter its three-letter code.');
  if(code && input.id==='destination' && code===airportCode($('#origin').value))input.setCustomValidity('Choose a different destination airport.');
  return code;
}
let activePicker=null, pickerMatches=[], pickerIndex=-1;
const fold=value=>value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
function refreshLocationLabels(){
  for(const id of ['origin','destination']){
    const code=$('#'+id).value,city=airports[code];
    $('#'+id+'-selected').textContent=city?`${city.name} · ${code}`:'Choose a city';
    $('#'+id+'-trigger').title=city?`${city.name}, ${city.country} — ${city.airport}`:'';
  }
}
function closePicker(returnFocus=false){
  if(!activePicker)return;
  const id=activePicker;
  $('#'+id+'-menu').hidden=true;
  $('#'+id+'-trigger').setAttribute('aria-expanded','false');
  $('#'+id+'-search').setAttribute('aria-expanded','false');
  $('#'+id+'-search').removeAttribute('aria-activedescendant');
  activePicker=null;pickerIndex=-1;
  if(returnFocus)$('#'+id+'-trigger').focus();
}
function selectAirport(code){
  if(!activePicker||busy)return;
  $('#'+activePicker).value=code;
  refreshLocationLabels();closePicker(true);
}
function highlightAirport(index){
  pickerIndex=index;
  const options=$('#'+activePicker+'-options').children;
  [...options].forEach((option,i)=>option.classList.toggle('highlighted',i===index));
  const option=options[index],search=$('#'+activePicker+'-search');
  if(option){search.setAttribute('aria-activedescendant',option.id);option.scrollIntoView?.({block:'nearest'});}
  else search.removeAttribute('aria-activedescendant');
}
function filterAirports(){
  const id=activePicker;if(!id)return;
  const query=fold($('#'+id+'-search').value.trim());
  const other=$('#'+(id==='origin'?'destination':'origin')).value;
  const matches=Object.entries(airports).filter(([code,city])=>code!==other&&query.split(/\s+/).every(word=>fold(`${code} ${city.name} ${city.country} ${city.airport}`).includes(word)));
  matches.sort(([a,x],[b,y])=>(b===query.toUpperCase())-(a===query.toUpperCase())||(y.country==='India')-(x.country==='India')||x.name.localeCompare(y.name));
  pickerMatches=matches.slice(0,40).map(([code])=>code);pickerIndex=-1;
  $('#'+id+'-count').textContent=matches.length?`${matches.length.toLocaleString()} airports${matches.length>40?' · Showing first 40. Type to narrow down.':''}`:'No matching airports. Try a city or a three-letter code.';
  const fragment=document.createDocumentFragment();
  for(const code of pickerMatches){
    const city=airports[code],option=document.createElement('button');
    option.type='button';option.tabIndex=-1;option.className='location-option';option.id=`${id}-option-${code}`;
    option.setAttribute('role','option');option.setAttribute('aria-selected',String(code===$('#'+id).value));
    option.innerHTML=`<span><strong>${escapeHTML(city.name)}</strong><small>${escapeHTML(city.country)} · ${escapeHTML(city.airport)}</small></span><b>${escapeHTML(code)}</b>`;
    option.addEventListener('click',()=>selectAirport(code));fragment.append(option);
  }
  $('#'+id+'-options').replaceChildren(fragment);
  $('#'+id+'-search').removeAttribute('aria-activedescendant');
}
function openPicker(id){
  if(busy||!Object.keys(airports).length)return;
  if(activePicker===id){closePicker();return;}
  closePicker();activePicker=id;
  $('#'+id+'-menu').hidden=false;$('#'+id+'-trigger').setAttribute('aria-expanded','true');
  const search=$('#'+id+'-search');search.value='';search.setAttribute('aria-expanded','true');filterAirports();search.focus();
}
for(const id of ['origin','destination']){
  $('#'+id+'-trigger').addEventListener('click',()=>openPicker(id));
  const search=$('#'+id+'-search');search.addEventListener('input',filterAirports);
  search.addEventListener('keydown',event=>{
    if(event.key==='Escape'){event.preventDefault();closePicker(true);}
    if(['ArrowDown','ArrowUp'].includes(event.key)){
      event.preventDefault();if(pickerMatches.length)highlightAirport(pickerIndex<0?(event.key==='ArrowDown'?0:pickerMatches.length-1):(pickerIndex+(event.key==='ArrowDown'?1:-1)+pickerMatches.length)%pickerMatches.length);
    }
    if(event.key==='Enter'){event.preventDefault();if(pickerMatches.length)selectAirport(pickerMatches[Math.max(0,pickerIndex)]);}
  });
}
document.addEventListener('pointerdown',event=>{if(activePicker&&!event.target.closest(`[data-picker="${activePicker}"]`))closePicker();});
document.addEventListener('focusin',event=>{if(activePicker&&!event.target.closest(`[data-picker="${activePicker}"]`))closePicker();});
$('#swap-route').addEventListener('click',()=>{
  if(busy)return;closePicker();const origin=$('#origin'),destination=$('#destination');
  [origin.value,destination.value]=[destination.value,origin.value];refreshLocationLabels();
});
function populateLocations(catalog){
  airports=catalog;locationLabels=new Map(Object.entries(catalog).map(([code,city])=>[airportLabel(code,city),code]));
  refreshLocationLabels();
  for(const id of ['origin','destination'])$('#'+id+'-trigger').disabled=busy;
  $('#location-note').textContent=`${Object.keys(catalog).length.toLocaleString()} airports, endless possibilities. Click a city to explore. No API credits used for suggestions.`;
}
async function loadConfig(){
  const ai=$('#mode option[value="ai"]'),live=$('#mode option[value="live"]');
  $('#refresh-config').disabled=true;
  try{
    if(location.protocol==='file:')throw Error('Open http://127.0.0.1:8003 after starting the app with .venv/bin/python run.py.');
    const response=await apiFetch('/api/config',{cache:'no-store',signal:AbortSignal.timeout(10000)});
    if(!response.ok)throw Error('The local server could not load configuration.');
    const config=await response.json();
    if(config.config_version!==3)throw Error('An older or different server is open. Restart Roam Team and open http://127.0.0.1:8003.');
    capabilities=config;
    ai.disabled=!config.ai_available;live.disabled=!config.live_available;
    ai.textContent=config.ai_available?'Groq team · sample travel data':'Groq team · key missing';
    live.textContent=config.live_available?'Live search · Groq + travel APIs':'Live search · keys missing';
    if($('#mode').selectedOptions[0].disabled)$('#mode').value='demo';
    populateLocations(config.destinations);
    $('#connection-status').textContent=config.live_available?'All three API keys detected. Live search is ready.':`Missing: ${config.missing_keys.join(', ')}. Save them in the project .env, then recheck.`;
    updateMode();
  }catch(error){
    capabilities={};ai.disabled=true;live.disabled=true;$('#mode').value='demo';
    ai.textContent='Groq team · server unavailable';live.textContent='Live search · server unavailable';
    updateMode();$('#connection-status').textContent=error.message+' Start .venv/bin/python run.py in the Roam Team folder, open http://127.0.0.1:8003, then recheck.';
  }finally{$('#refresh-config').disabled=false;}
}
function readForm(){
  const data=new FormData($('#trip-form'));
  const origin=validateLocation($('#origin')),destination=validateLocation($('#destination'));
  if(!origin||!destination||origin===destination){$('#trip-form').reportValidity();throw Error('Choose two different airports from the suggestions.');}
  return {origin,destination,start:data.get('start'),end:data.get('end'),budget:Number(data.get('budget')),travelers:Number(data.get('travelers')),interests:data.getAll('interests'),mode:data.get('mode')};
}
$('#refresh-config').addEventListener('click',()=>{if(!busy)loadConfig();});
for(const id of ['origin','destination'])$('#'+id).addEventListener('input',()=>{validateLocation($('#origin'));validateLocation($('#destination'));});
function receiveEvent(event){
  eventCount++;$('#event-count').textContent=`${eventCount} updates`;
  const item=document.createElement('li');
  item.innerHTML=`<time>${escapeHTML(new Date(event.at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'}))}</time><b>${escapeHTML(names[event.agent]||event.agent)} → ${escapeHTML(names[event.to]||event.to)}</b><br>${escapeHTML(event.message)}`;
  $('#trace').append(item);$('#trace').scrollTop=$('#trace').scrollHeight;
  const agent=document.querySelector(`[data-agent="${event.agent}"]`);
  if(agent){if(event.kind==='started')agent.classList.add('running');if(event.kind==='completed'){agent.classList.remove('running');agent.classList.add('done');}}
  if(event.kind==='revision'){$('#team-status').textContent=`Revising the budget · round ${event.round}`;document.querySelector(`[data-agent="${event.to}"]`)?.classList.remove('done');}
  else if(event.kind==='started')$('#team-status').textContent='The team is planning';
}
function offerCard(role,offers,alternatives){
  const o=offers[0];
  if(!o)return `<article class="panel offer"><p class="eyebrow">${escapeHTML(costNames[role])}</p><h3>No option found</h3><p>This part of the trip needs attention. The total is incomplete.</p></article>`;
  const times=role==='flights'?`<p>Arrival ${escapeHTML(clockTime(o.arrival))} · Return departure ${escapeHTML(clockTime(o.departure))}<br>Airport-local times</p>`:'';
  const url=safeURL(o.url);
  return `<article class="panel offer"><p class="eyebrow">${role==='flights'?'↗ GETTING THERE':'⌂ YOUR HOME BASE'}</p><h3>${escapeHTML(o.title)}</h3><p>${escapeHTML(o.description)}</p>${times}<div class="offer-price">${rupees(o.cost)}</div><div class="source">${escapeHTML(o.source)} · ${o.sample?'Sample':o.price_kind==='estimate'?'Estimate':'Search price'}<br>Retrieved ${escapeHTML(new Date(o.retrieved_at).toLocaleString())}</div>${url?`<p><a target="_blank" rel="noreferrer" href="${escapeHTML(url)}">Check with provider ↗</a></p>`:''}${alternatives.length?`<details class="alternatives"><summary>${alternatives.length} other options</summary>${alternatives.map(a=>`<p>${escapeHTML(a.title)} · ${rupees(a.cost)}</p>`).join('')}</details>`:''}</article>`;
}
function renderPlan(plan){
  window.dispatchEvent(new Event('roam:clear-results'));
  lastPlan=plan;const t=plan.request;
  const status=plan.status==='within_budget'?'Within estimated budget':plan.status==='incomplete'?'Incomplete · missing options':'Over budget';
  $('#result').innerHTML=`<section class="result-top"><p class="eyebrow">YOUR TRIP, BROUGHT TOGETHER</p><h2>${escapeHTML(plan.destination_name)} is calling.</h2><p>${friendlyDate(t.start)} – ${friendlyDate(t.end)} · ${plan.itinerary.length-1} nights · ${t.travelers} adult${t.travelers>1?'s':''} · From ${escapeHTML(t.origin)}</p><div class="result-actions"><span class="status-pill ${plan.status!=='within_budget'?'over':''}">${status}</span><button class="secondary" id="download-plan">Download PDF ↓</button></div><p id="download-status" role="status" aria-live="polite"></p></section>
  <nav class="plan-navigation" aria-label="Plan sections"><a href="#plan-budget">Budget</a><a href="#offer-carousel">Flight & stay</a><a href="#plan-itinerary">Daily itinerary</a><a href="#trip-form">Edit trip ↗</a></nav>
  <section id="plan-budget" class="panel cost-panel"><div class="cost-title"><h2>${plan.status==='incomplete'?'Partial cost estimate':'The budget, made clear'}</h2><div><strong>${rupees(plan.total)}</strong><small>of ${rupees(t.budget*100)} total budget</small></div></div><div class="budget-bar" aria-label="Cost breakdown">${Object.entries(plan.costs).map(([key,value])=>`<span style="width:${value/Math.max(plan.total,t.budget*100)*100}%;background:${colors[key]}"></span>`).join('')}</div><div class="cost-list">${Object.entries(plan.costs).map(([key,value])=>`<div class="cost-item"><span class="dot" style="background:${colors[key]}"></span>${costNames[key]}<b>${rupees(value)}</b></div>`).join('')}</div><p class="metrics">${plan.remaining>=0?`${rupees(plan.remaining)} remains after allowances.`:`${rupees(-plan.remaining)} above your budget.`} ${plan.status==='incomplete'?'Missing categories have no quote and are not included.':''}</p></section>
  <div id="offer-carousel"><div class="offer-grid">${offerCard('flights',plan.selected.flights,plan.alternatives.flights)}${offerCard('stays',plan.selected.stays,plan.alternatives.stays)}</div></div>
  <section id="plan-itinerary" class="panel itinerary"><div class="section-title"><div><p class="eyebrow">YOUR JOURNEY, DAY BY DAY</p><h2>A little structure. Room to wander.</h2></div><span>${plan.itinerary.length} days</span></div><nav class="day-navigation" aria-label="Jump to a day">${plan.itinerary.map(day=>`<a href="#itinerary-day-${day.day}">Day ${day.day}<small>${friendlyDate(day.date)}</small></a>`).join('')}</nav>${plan.itinerary.map(day=>`<section class="day" id="itinerary-day-${day.day}"><div class="day-title"><span class="day-number">${String(day.day).padStart(2,'0')}</span><div><h3>${escapeHTML(day.title)}</h3><small>${friendlyDate(day.date)}</small></div></div><div class="day-schedule">${day.items.map(item=>`<div class="schedule-item"><time>${escapeHTML(item.time)}${item.end&&item.end!=='TBC'?`<br>– ${escapeHTML(item.end)}`:''}</time><div><strong>${escapeHTML(item.title)}</strong><p>${escapeHTML(item.description)}</p>${item.opening_hours?`<p>Listed hours: ${escapeHTML(item.opening_hours)} · confirm for your date</p>`:''}${item.transfer_minutes?`<p>${item.transfer_minutes} min transfer block, including buffer</p>`:''}${safeURL(item.url)?`<a class="source" target="_blank" rel="noreferrer" href="${escapeHTML(safeURL(item.url))}">Check availability ↗</a>`:''}</div><span class="amount">${item.kind==='activity'?(item.cost?(item.price_kind==='estimate'?'~ ':'')+rupees(item.cost):'Listed free*'):''}</span></div>`).join('')}</div></section>`).join('')}</section>
  ${t.mode==='live'?'<p class="source attribution">Places and routes: <a href="https://www.geoapify.com/" target="_blank" rel="noreferrer">Geoapify</a> · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors</a>. Prices: Google search results via SerpApi. No bookings are made.</p>':''}<section class="notes"><strong>Before you pack</strong><ul>${plan.notes.map(note=>`<li>${escapeHTML(note)}</li>`).join('')}</ul></section>`;
  $('#download-plan').addEventListener('click',event=>downloadPlanPDF(plan,event.currentTarget));
  $('#result').hidden=false;$('#view-plan').hidden=false;$('#empty').hidden=true;
  window.dispatchEvent(new CustomEvent('roam:plan-ready',{detail:plan}));
}
async function submitTrip(trip){
  if(busy)throw Error('A trip is already being planned.');
  window.dispatchEvent(new Event('roam:clear-results'));
  closePicker();busy=true;activeRequest=new AbortController();lastPlan=null;$('#error').hidden=true;$('#result').hidden=true;$('#view-plan').hidden=true;$('#empty').hidden=false;$('#trace').replaceChildren();eventCount=0;$('#event-count').textContent='0 updates';$('#trace-details').open=true;
  $('#plan-button').disabled=true;$('#plan-button').innerHTML='Planning your trip <span class="spinner"></span>';
  document.querySelectorAll('#trip-form input, #trip-form select, .location-trigger, #swap-route').forEach(el=>el.disabled=true);
  document.querySelectorAll('.agent').forEach(el=>el.classList.remove('running','done','failed'));
  try{
    const response=await apiFetch('/api/plan/stream',{signal:activeRequest.signal,method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(trip)});
    if(!response.ok){const error=await response.json();throw Error(Array.isArray(error.detail)?error.detail.map(e=>e.msg).join(' '):error.detail||'Could not start planning.');}
    const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',complete=false;
    const consume=line=>{if(!line.trim())return;const message=JSON.parse(line);if(message.type==='event')receiveEvent(message.data);if(message.type==='error')throw Error(message.data);if(message.type==='result'){renderPlan(message.data);complete=true;}};
    try{while(true){const {done,value}=await reader.read();if(done){buffer+=decoder.decode();break;}buffer+=decoder.decode(value,{stream:true});const lines=buffer.split('\n');buffer=lines.pop();for(const line of lines)consume(line);}if(buffer.trim())consume(buffer);}finally{await reader.cancel();}
    if(!complete)throw Error('The connection ended before the plan was ready. Please try again.');
    $('#team-status').textContent='Planning complete';return {status:lastPlan.status,total:lastPlan.total,currency:'INR',money_unit:'paise',days:lastPlan.itinerary.length};
  }catch(error){showError(error.message||'Could not reach the planner.');$('#team-status').textContent='Needs attention';document.querySelectorAll('.agent.running').forEach(el=>{el.classList.remove('running');el.classList.add('failed');});throw error;}
  finally{loadUsage();busy=false;$('#plan-button').disabled=false;document.querySelectorAll('#trip-form input, #trip-form select, .location-trigger, #swap-route').forEach(el=>el.disabled=false);$('#plan-button').innerHTML='Build my trip <span>↗</span>';}
}
$('#trip-form').addEventListener('submit',event=>{event.preventDefault();try{submitTrip(readForm()).catch(()=>{});}catch(error){showError(error.message);}});
$('#mode').addEventListener('change',updateMode);
$('#start').addEventListener('change',()=>{const date=new Date($('#start').value+'T12:00:00');date.setDate(date.getDate()+1);const next=`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;$('#end').min=next;if($('#end').value<next)$('#end').value=next;});
window.authReady.then(ok=>{if(ok){loadConfig();loadUsage();}});
// Optional browser tool reads the same completed result shown in the interface.
if(document.modelContext?.registerTool){try{Promise.resolve(document.modelContext.registerTool({name:'read_travel_plan',description:'Read the completed travel plan currently visible in the planner. Does not create a plan or make bookings.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true,untrustedContentHint:true},execute:input=>{if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).length)throw Error('Expected an empty object.');if(!lastPlan)throw Error('No completed travel plan is available.');return lastPlan;}})).catch(()=>{});}catch{}}

async function loadUsage(){const summary=$('#quota-summary');if(!summary)return;try{const r=await apiFetch('/api/usage');if(!r.ok)return;const d=await r.json(),s=d.providers.serpapi,g=d.providers.geoapify;summary.textContent=`SerpApi: ${s.used}/${s.limit} local searches (${s.window}); ${s.daily_used} in 24h. Geoapify: ${g.used}/${g.limit} local credits (${g.window}).`;}catch{summary.textContent='Usage unavailable. Local safeguards still apply.';}}
