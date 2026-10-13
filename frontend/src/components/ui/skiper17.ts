import gsap from 'gsap';
import {ScrollTrigger} from 'gsap/ScrollTrigger';
/** Skiper17 StickyCard_002 adaptation: scoped scale/rotation scroll timeline.
 * Original @gurvinder-singh02 / Skiper UI; free use with attribution.
 * Natural document flow replaces full-screen pinning so long itineraries remain readable.
 */
export function mountSkiper17(container:HTMLElement){
  gsap.registerPlugin(ScrollTrigger);
  const cards=Array.from(container.querySelectorAll<HTMLElement>('.day'));
  let context:gsap.Context|undefined;
  let enabled=true;
  const media=window.matchMedia('(min-width: 901px) and (prefers-reduced-motion: no-preference)');
  function reset(){context?.revert();context=undefined;container.classList.remove('has-scroll-stack');}
  function setup(){
    reset();
    if(!enabled||!media.matches||cards.length<2||cards.some(card=>card.offsetHeight>window.innerHeight-130))return;
    container.classList.add('has-scroll-stack');
    context=gsap.context(()=>{
      for(let i=0;i<cards.length-1;i++){
        gsap.timeline({scrollTrigger:{trigger:cards[i+1],start:'top 65%',end:'top 70px',scrub:.5,invalidateOnRefresh:true}})
          .to(cards[i],{scale:.95,rotation:i%2?-1.5:1.5,transformOrigin:'center top',ease:'none',duration:1},0)
          .fromTo(cards[i+1],{y:20},{y:0,ease:'none',duration:1},0);
      }
    },container);
    ScrollTrigger.refresh();
  }
  const change=(event:Event)=>{enabled=Boolean((event as CustomEvent).detail);setup();};
  let timer:ReturnType<typeof setTimeout>;
  const resize=()=>{clearTimeout(timer);timer=setTimeout(setup,150);};
  media.addEventListener('change',setup);window.addEventListener('resize',resize);window.addEventListener('roam:result-motion',change);
  const observer=new ResizeObserver(resize);cards.forEach(card=>observer.observe(card));
  setup();
  return ()=>{clearTimeout(timer);observer.disconnect();media.removeEventListener('change',setup);window.removeEventListener('resize',resize);window.removeEventListener('roam:result-motion',change);reset();};
}
