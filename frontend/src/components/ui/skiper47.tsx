"use client";
import {useRef,useState,useEffect} from 'react';
import {useReducedMotion} from 'framer-motion';
import {Swiper,SwiperSlide} from 'swiper/react';
import {EffectCoverflow,A11y,Keyboard} from 'swiper/modules';
import type {Swiper as SwiperInstance} from 'swiper';
import 'swiper/css';
import 'swiper/css/effect-coverflow';

type Offer={id:string;title:string;description:string;cost:number;sample:boolean;price_kind:string;source:string;retrieved_at:string;arrival?:string;departure?:string;url?:string};
export type OfferPlan={selected:{flights:Offer[];stays:Offer[]};alternatives:{flights:Offer[];stays:Offer[]}};
const money=(value:number)=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(value/100);
function safeURL(value?:string){try{const url=new URL(value||'');return url.protocol==='https:'?url.href:undefined;}catch{return undefined;}}
function OfferDetails({role,plan,onResize}:{role:'flights'|'stays';plan:OfferPlan;onResize:()=>void}){
  const offer=plan.selected[role][0],alternatives=plan.alternatives[role]||[];
  return <article className={`panel offer perspective-offer ${role}`}>
    <div className="offer-label"><div className="offer-symbol" aria-hidden="true">{role==='flights'?'↗':'⌂'}</div>
    <p className="eyebrow">{role==='flights'?'GETTING THERE':'YOUR HOME BASE'}</p></div>
    <div className="offer-scroll" role="region" aria-label={role==='flights'?'Flight details':'Stay details'}>
    {!offer?<><h3>No option found</h3><p>This part of the trip needs attention. The total is incomplete.</p></>:<>
      <h3>{offer.title}</h3><div className="offer-price">{money(offer.cost)}</div><p>{offer.description}</p>
      {role==='flights'&&<p className="flight-times">Arrival {offer.arrival?.slice(11,16)||'TBC'} · Return departure {offer.departure?.slice(11,16)||'TBC'}<br/>Airport-local times</p>}
      <div className="source">{offer.source} · {offer.sample?'Sample':offer.price_kind==='estimate'?'Estimate':'Search price'}<br/>Retrieved {new Date(offer.retrieved_at).toLocaleString()}</div>
      {safeURL(offer.url)&&<p><a target="_blank" rel="noopener noreferrer" href={safeURL(offer.url)}>Check with provider ↗</a></p>}
      {!!alternatives.length&&<details className="alternatives swiper-no-swiping" onToggle={onResize}><summary>{alternatives.length} other options</summary>{alternatives.map(item=><p key={item.id}>{item.title} · {money(item.cost)}</p>)}</details>}
    </>}
    </div>
  </article>;
}
export function Skiper47({plan}:{plan:OfferPlan}){
  const swiper=useRef<SwiperInstance|null>(null);
  const [active,setActive]=useState(0),[all,setAll]=useState(true),[paused,setPaused]=useState(false);
  const reduced=useReducedMotion();const still=!!reduced||paused;
  useEffect(()=>{window.dispatchEvent(new CustomEvent('roam:result-motion',{detail:!still}));},[still]);
  const roles=['flights','stays'] as const;
  const resize=()=>swiper.current?.updateAutoHeight(0);
  return <section className={`offer-showcase ${still?'dock-motion-off':'dock-motion-on'}`} data-component="skiper47" aria-label="Your selected flight and stay">
    <div className="offer-showcase-heading"><div><p className="eyebrow">TWO PIECES. ONE GREAT TRIP.</p><h2>Your flight & your stay</h2></div><button className="secondary" type="button" onClick={()=>setAll(value=>!value)} aria-pressed={all}>{all?'Focus one card':'Show both cards'}</button></div>
    {!all&&<div className="offer-navigation"><div className="offer-tabs" aria-label="Choose a card">{roles.map((role,i)=><button key={role} type="button" aria-pressed={active===i} onClick={()=>swiper.current?.slideTo(i)}>{role==='flights'?'↗ Flight':'⌂ Stay'}</button>)}</div><div className="offer-arrows"><button type="button" aria-label="Previous card" disabled={active===0} onClick={()=>swiper.current?.slidePrev()}>←</button><button type="button" aria-label="Next card" disabled={active===1} onClick={()=>swiper.current?.slideNext()}>→</button></div></div>}
    {all?<div className="offer-dock" aria-label="Flight and stay cards in a horizontal row">{roles.map(role=><div className="offer-dock-item" key={role}><OfferDetails role={role} plan={plan} onResize={()=>{}}/></div>)}</div>:
      <Swiper key={still?'flat':'perspective'} initialSlide={active} modules={[EffectCoverflow,A11y,Keyboard]} effect={still?'slide':'coverflow'}
        onSwiper={instance=>{swiper.current=instance;}} onSlideChange={instance=>setActive(instance.activeIndex)}
        slidesPerView={1.08} spaceBetween={18} centeredSlides grabCursor loop={false} autoHeight
        speed={still?0:450} keyboard={{enabled:true,onlyInViewport:true}} a11y={{enabled:true,containerMessage:'Flight and stay details. Use the card buttons or swipe.'}}
        coverflowEffect={{rotate:5,slideShadows:false,stretch:0,depth:110,modifier:1.6}}
        breakpoints={{720:{slidesPerView:1.18,spaceBetween:24}}} className="offer-perspective" noSwipingSelector="a,button,summary,details,input">
        {roles.map((role,i)=><SwiperSlide key={role}><div inert={active!==i} aria-hidden={active!==i}><OfferDetails role={role} plan={plan} onResize={resize}/></div></SwiperSlide>)}
      </Swiper>}
    <div className="offer-showcase-footer"><span role="status" aria-live="polite">{all?'Your selected options · expand to compare alternatives':`${active+1} / 2 · ${active===0?'Flight':'Stay'} details`}</span><button className="motion-text" type="button" disabled={!!reduced} aria-pressed={still} onClick={()=>setPaused(value=>!value)}>{reduced?'Reduced motion on':paused?'Enable card animations':'Turn off card animations'}</button></div>
  </section>;
}
/** Skiper47 / Carousel_001 — adapted from the requested Skiper UI registry.
 * Uses original Swiper EffectCoverflow pattern for real offer content.
 * Free personal/commercial use and modification; Skiper UI attribution required.
 * Original author: @gurvinder-singh02, https://gxuri.me. */
