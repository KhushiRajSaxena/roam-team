/* Local PDF export. Uses only the completed plan; no network or model calls. */
function buildPlanPDF(plan){
  if(!window.jspdf?.jsPDF||!window.roamPdfFont)throw Error('PDF tools did not load. Refresh the page and try again.');
  const doc=new window.jspdf.jsPDF({unit:'mm',format:'a4',compress:true,putOnlyUsedFonts:true});
  doc.addFileToVFS('RoamSans.ttf',window.roamPdfFont);
  doc.addFont('RoamSans.ttf','RoamSans','normal');doc.setFont('RoamSans','normal');
  doc.setProperties({title:`${plan.destination_name} travel plan`,author:'Roam Team',subject:'Your itinerary and estimated trip budget'});
  const ink=[41,36,66],purple=[105,80,200];let y=27;
  const clean=value=>String(value??'').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g,'').replace(/[–—‑]/g,'-');
  const cash=value=>'INR '+new Intl.NumberFormat('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(value)/100);
  const date=value=>new Date(value+'T12:00:00').toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
  function space(height){if(y+height>276){doc.addPage();y=27;}}
  function text(value,size=10,color=ink){
    doc.setFontSize(size);doc.setTextColor(...color);
    const lines=doc.splitTextToSize(clean(value),174);
    for(const line of lines){space(size*.43+2);doc.text(line,18,y);y+=size*.43+1;}
    y+=3;
  }
  function title(value){space(24);y+=3;text(value,14,purple);}
  function table(head,body,widths,caption){
    doc.autoTable({startY:y,head:caption?[[{content:clean(caption),colSpan:head.length}],head]:[head],body,margin:{top:27,bottom:22,left:18,right:18},
      theme:'striped',rowPageBreak:'avoid',styles:{font:'RoamSans',fontStyle:'normal',fontSize:9,cellPadding:3,lineColor:[232,226,244],textColor:ink,overflow:'linebreak'},
      headStyles:{fontStyle:'normal',fillColor:purple,textColor:255},alternateRowStyles:{fillColor:[247,245,252]},columnStyles:widths||{}});
    y=doc.lastAutoTable.finalY+7;
  }
  function link(label,url){
    try{const u=new URL(url);if(u.protocol!=='https:')return;space(9);doc.setFontSize(9);doc.setTextColor(...purple);doc.textWithLink(label,18,y,{url:u.href});y+=8;}catch{}
  }
  const retrieved=value=>value?new Date(value).toLocaleString('en-GB',{dateStyle:'medium',timeStyle:'short'})+' (export local time)':'Not recorded';
  const t=plan.request;
  text(`${plan.destination_name} travel plan`,23,purple);
  text(`${t.origin} to ${t.destination} | ${date(t.start)} - ${date(t.end)}`,11);
  text(`${plan.itinerary.length-1} nights | ${t.travelers} adult${t.travelers===1?'':'s'} | Budget ${cash(t.budget*100)}`);
  text(t.mode==='live'?'Live search results - prices and availability need reconfirmation.':'SAMPLE PLAN - fictional offers, schedules and prices. Not a booking.',9,[99,91,115]);
  const status={within_budget:'Within estimated budget',over_budget:'Over budget',incomplete:'Incomplete - some travel options are missing'};
  title('Your budget');text(status[plan.status]||plan.status,11);
  const labels={flights:'Flights',stays:'Accommodation',activities:'Activities',meals:'Meals allowance',local_transport:'Local transport allowance',contingency:'Contingency'};
  table(['Category','Estimated cost'],[...Object.entries(plan.costs).map(([k,v])=>[labels[k]||k,cash(v)]),[plan.status==='incomplete'?'Partial estimated total':'Estimated total',cash(plan.total)],[plan.remaining>=0?'Budget remaining':'Amount over budget',cash(Math.abs(plan.remaining))]],{1:{cellWidth:51,halign:'right'}});
  if(plan.status==='incomplete')text('The total excludes any missing options and is not a complete trip price.',9);
  for(const [role,label] of [['flights','Your flights'],['stays','Your stay']]){
    title(label);
    if(!plan.selected[role]?.length){text('No suitable option found. This part of the trip still needs planning.');continue;}
    for(const offer of plan.selected[role]){
      space(45);
      text(offer.title,12);text(offer.description,9);
      text(`${cash(offer.cost)} | ${offer.sample?'Sample price':offer.price_kind==='estimate'?'Estimated price':'Search price'}`,10);
      if(role==='flights'){
        const times=[['Outbound departure',offer.outbound_departure],['Destination arrival',offer.arrival],['Return departure',offer.departure],['Return arrival',offer.return_arrival]].filter(([,v])=>v);
        table(['Flight timing (airport-local)','Date and time'],times.map(([label,value])=>[label,clean(value).replace('T',' ')]));
      }
      text(`Source: ${offer.source}. Retrieved: ${retrieved(offer.retrieved_at)}`,8,[99,91,115]);
      link('Open provider to confirm details',offer.url);
    }
  }
  title('Your day-by-day itinerary');
  for(const day of plan.itinerary){
    space(38);
    table(['Time','Plan','Cost'],day.items.map(item=>[
      `${item.time||'TBC'}${item.end&&item.end!=='TBC'?' - '+item.end:''}`,
      [item.title,item.description,item.opening_hours?'Listed hours: '+item.opening_hours+' (confirm for your date)':'',item.transfer_minutes?item.transfer_minutes+' min transfer block including buffer':''].filter(Boolean).join('\n'),
      item.kind==='activity'?(item.cost?(item.price_kind==='estimate'?'Est. ':'')+cash(item.cost):item.price_kind==='listed_free'?'Listed free*':'No added cost'):'Included'
    ]),{0:{cellWidth:28},1:{cellWidth:113},2:{cellWidth:33}},`Day ${day.day} - ${date(day.date)} | ${day.title}`);
  }
  title('Activity information and links');
  for(const offer of plan.selected.activities||[]){
    space(25);text(`${offer.title} | ${offer.price_kind==='estimate'?'Estimated fee: ':''}${cash(offer.cost)}`,10);
    text(`${offer.source} | ${offer.sample?'Sample activity':offer.price_kind==='listed_free'?'Source lists free entry; reconfirm':'Confirm admission and opening hours'}. Retrieved: ${retrieved(offer.retrieved_at)}`,8);
    link('Open activity information',offer.url);
  }
  title('Before you travel');
  for(const note of plan.notes||[]){if(!note.startsWith('Demo specialists'))text('- '+note,9);}
  text('This is a travel plan, not a booking confirmation. All amounts are in INR. Allowances and unknown entry fees are estimates; verify prices, taxes, access and schedules before booking.',9);
  if(t.mode==='live'){
    text('Places and routes: Geoapify / OpenStreetMap contributors. Flight and hotel search results: Google via SerpApi.',8);
    link('Geoapify', 'https://www.geoapify.com/');link('OpenStreetMap attribution','https://www.openstreetmap.org/copyright');
  }
  const pages=doc.getNumberOfPages();
  for(let i=1;i<=pages;i++){
    doc.setPage(i);doc.setDrawColor(225,218,242);doc.line(18,18,192,18);doc.setFontSize(9);doc.setTextColor(...purple);doc.text('ROAM TEAM / YOUR TRIP, TOGETHER',18,13);
    doc.setFontSize(8);doc.setTextColor(110,102,127);doc.text('Keep this plan handy. Confirm details before travel.',18,286);doc.text(`${i} / ${pages}`,192,286,{align:'right'});
  }
  return doc;
}
async function downloadPlanPDF(plan,button){
  if(!plan||button.disabled)return;
  button.disabled=true;button.textContent='Preparing PDF…';
  try{
    await new Promise(resolve=>setTimeout(resolve,30));
    const doc=buildPlanPDF(plan);
    await doc.save(`roam-${plan.request.destination.toLowerCase()}-${plan.request.start}.pdf`,{returnPromise:true});
    const status=document.querySelector('#download-status');if(status)status.textContent='PDF download started. Check your downloads.';
  }catch(error){
    const status=document.querySelector('#download-status');if(status)status.textContent='Could not create the PDF. Please refresh and try again.';
  }finally{button.disabled=false;button.textContent='Download PDF ↓';}
}
