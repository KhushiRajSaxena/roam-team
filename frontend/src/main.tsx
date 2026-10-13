import { createRoot, type Root } from 'react-dom/client';
import { TravelTileReveal } from './components/ui/travel-tile-reveal';
const host=document.getElementById('travel-inspiration');
const main=document.querySelector('main');
let root:Root|null=null;
function syncGallery(){
  if(!host||!main)return;
  if(main.hidden){root?.unmount();root=null;return;}
  if(!root){root=createRoot(host);root.render(<TravelTileReveal/>);}
}
if(main&&host){
  new MutationObserver(syncGallery).observe(main,{attributes:true,attributeFilter:['hidden']});
  syncGallery();
}

import {Skiper47,type OfferPlan} from './components/ui/skiper47';
import {mountSkiper17} from './components/ui/skiper17';
let offerRoot:Root|null=null;
let stopStack:(()=>void)|undefined;
let pendingFrame=0;
function clearResults(){cancelAnimationFrame(pendingFrame);stopStack?.();stopStack=undefined;offerRoot?.unmount();offerRoot=null;}
window.addEventListener('roam:clear-results',clearResults);
window.addEventListener('roam:plan-ready',event=>{
  clearResults();
  const host=document.getElementById('offer-carousel');
  const itinerary=document.querySelector<HTMLElement>('#result .itinerary');
  if(host){offerRoot=createRoot(host);offerRoot.render(<Skiper47 plan={(event as CustomEvent<OfferPlan>).detail}/>);}
  if(itinerary)pendingFrame=requestAnimationFrame(()=>{stopStack=mountSkiper17(itinerary);});
});
