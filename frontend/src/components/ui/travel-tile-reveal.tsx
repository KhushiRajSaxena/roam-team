import {useEffect, useRef, useState} from 'react';

// Original Roam Team component. No React Bits source or licensed registry required.
const photos=[
  ['mountain.jpg','Snow-covered mountains above a green valley'],
  ['tropical-coast.jpg','Turquoise waves meeting a sandy beach'],
  ['forest.jpg','Sunlight through a green forest'],
  ['lakeside.jpg','A quiet lake surrounded by mountains'],
  ['shoreline.jpg','Golden sand and blue ocean beneath an open sky'],
  ['alpine-night.jpg','Stars above snowy alpine peaks'],
];
const clamp=(value:number)=>Math.max(0,Math.min(1,value));
export function TravelTileReveal(){
  const section=useRef<HTMLElement>(null);
  const [reduced,setReduced]=useState(()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [disabled,setDisabled]=useState(false);
  const still=reduced||disabled;
  useEffect(()=>{
    const media=window.matchMedia('(prefers-reduced-motion: reduce)');
    const update=()=>setReduced(media.matches);
    media.addEventListener('change',update);return()=>media.removeEventListener('change',update);
  },[]);
  useEffect(()=>{
    const host=section.current;if(!host||still)return;
    const tiles=Array.from(host.querySelectorAll<HTMLElement>('.reveal-tile'));
    const content=host.querySelector<HTMLElement>('.reveal-message')!;
    let frame=0;
    function paint(){
      frame=0;if(!host)return;
      const stage=host.querySelector<HTMLElement>('.reveal-stage')!;
      const bounds=host.getBoundingClientRect();
      const progress=clamp(-bounds.top/Math.max(1,host.offsetHeight-stage.offsetHeight));
      // Start as the hero enters the viewport, not after it reaches the top.
      // The entire grid arrives within roughly 240px of scrolling.
      const entrance=clamp((window.innerHeight*.85-bounds.top)/Math.min(240,window.innerHeight*.3));
      const zoom=clamp((progress-.3)/.62);
      tiles.forEach((tile,index)=>{
        const column=index%3,row=Math.floor(index/3);
        const entry=clamp((entrance-column*.045-row*.015)/.8);
        const eased=1-Math.pow(1-entry,3);
        const from=(column%2===0?1:-1)*(1-eased)*(stage.offsetHeight+tile.offsetHeight);
        const x=(column-1)*zoom*(stage.offsetWidth+tile.offsetWidth);
        const y=from+(row===0?-1:1)*zoom*(stage.offsetHeight+tile.offsetHeight);
        tile.style.transform=`translate3d(${x}px,${y}px,0) scale(${.88+eased*.12+zoom*.9})`;
        tile.style.opacity=String(Math.min(clamp(entry*6),1-clamp((zoom-.8)/.2)));
      });
      const reveal=clamp((progress-.65)/.22);
      content.style.opacity=String(reveal);
      content.style.transform=`translateY(${(1-reveal)*22}px)`;
      content.inert=reveal<.95;
      content.setAttribute('aria-hidden',String(reveal<.95));
    }
    const schedule=()=>{if(!frame)frame=requestAnimationFrame(paint);};
    const observer=new ResizeObserver(schedule);observer.observe(host);
    window.addEventListener('scroll',schedule,{passive:true});window.addEventListener('resize',schedule);
    paint();
    return()=>{
      cancelAnimationFrame(frame);observer.disconnect();
      window.removeEventListener('scroll',schedule);window.removeEventListener('resize',schedule);
      tiles.forEach(tile=>{tile.style.removeProperty('transform');tile.style.removeProperty('opacity');});
      content.style.removeProperty('opacity');content.style.removeProperty('transform');
      content.inert=false;content.removeAttribute('aria-hidden');
    };
  },[still]);
  return <section ref={section} className={`travel-reveal ${still?'reveal-static':'reveal-animated'}`} aria-label="Travel inspiration" data-component="travel-tile-reveal">
    <div className="reveal-stage">
      <div className="reveal-toolbar"><span>✦ YOUR NEXT CHAPTER</span><a href="#trip-form">Skip to planner ↗</a></div>
      <div className="reveal-grid">{photos.map(([file,alt])=><figure className="reveal-tile" key={file}><img src={`/images/${file}`} alt={alt} width="720" height="480" decoding="async"/></figure>)}</div>
      <div className="reveal-message">
        <p className="eyebrow">MOUNTAINS. COASTLINES. POSSIBILITIES.</p>
        <h2>Great places.<br/><em>Your kind of journey.</em></h2>
        <p>Flights, stays and little adventures — planned together, around your budget.</p>
        <a className="travel-cta" href="#trip-form">Plan my trip <span aria-hidden="true">↗</span></a>
      </div>
      <div className="reveal-controls"><span>{still?'A little inspiration for your next escape':'Scroll to find your next escape ↓'}</span><button type="button" className="motion-text" disabled={reduced} aria-pressed={still} onClick={()=>setDisabled(value=>!value)}>{reduced?'Reduced motion on':disabled?'Enable tile animation':'Turn off tile animation'}</button></div>
    </div>
  </section>;
}
