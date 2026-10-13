"use client";

import { motion, type MotionValue, useScroll, useTransform, useReducedMotion } from 'framer-motion';
import { useRef, useState } from 'react';

// Adapted from the user's Skiper UI registry component (original saved in registry/).
// Keep native scrolling: the planner's menus and form must never fight a global
// Lenis loop. Bounded column movement replaces the demo's full-screen spacers.
const images = [
  {src:'/images/mountain.jpg', alt:'Snow-capped mountain valley with evergreen forests', label:'Take the scenic route'},
  {src:'/images/beach.jpg', alt:'Turquoise waves on a sandy beach at sunset', label:'Find your slower pace'},
  {src:'/images/alpine-night.jpg', alt:'Star-filled sky above snowy mountain peaks', label:'A little closer to the stars'},
  {src:'/images/lakeside.jpg', alt:'Wooden boat on an alpine lake surrounded by mountains', label:'Room to breathe'},
  {src:'/images/forest.jpg', alt:'Sunlight filtering through a quiet green forest', label:'Wander a little further'},
  {src:'/images/shoreline.jpg', alt:'Golden sandy shoreline beneath a blue sky', label:'Follow the coastline'},
  {src:'/images/tropical-coast.jpg', alt:'Clear turquoise sea beside a sunlit sandy beach', label:'A brighter kind of getaway'},
];
type TravelImage = typeof images[number];
function Column({photos,y,paused,index}:{photos:TravelImage[];y:MotionValue<number>;paused:boolean;index:number}){
  return <motion.div className={`travel-column travel-column-${index}`} style={paused?{y:0}:{y}}>
    {photos.map((photo,i)=><figure className="travel-photo" key={`${photo.src}-${i}`}>
      <img src={photo.src} alt={photo.alt} width={720} height={480} loading={i===0?'eager':'lazy'} decoding="async"/>
      <figcaption>{photo.label}</figcaption>
    </figure>)}
  </motion.div>;
}
export function Skiper30(){
  const gallery=useRef<HTMLDivElement>(null);
  const reduced=useReducedMotion();
  const [paused,setPaused]=useState(false);
  const {scrollYProgress}=useScroll({target:gallery,offset:['start end','end start']});
  const y=useTransform(scrollYProgress,[0,1],[-35,35]);
  const y2=useTransform(scrollYProgress,[0,1],[40,-40]);
  const y3=useTransform(scrollYProgress,[0,1],[-55,55]);
  const y4=useTransform(scrollYProgress,[0,1],[30,-30]);
  const still=!!reduced||paused;
  return <section className="travel-hero" aria-labelledby="travel-hero-title" data-component="skiper30">
    <div className="travel-story">
      <span className="travel-kicker"><span aria-hidden="true">✦</span> LESS PLANNING. MORE LIVING.</span>
      <h2 id="travel-hero-title">Go somewhere<br/><em>you’ll remember.</em></h2>
      <p>Mountain mornings. Barefoot afternoons. One thoughtful plan that brings your whole trip together.</p>
      <a className="travel-cta" href="#trip-form">Let’s plan your escape <span aria-hidden="true">↗</span></a>
      <div className="travel-promises"><span>Flights + stays + experiences</span><span>Your budget, your pace</span></div>
    </div>
    <div className="travel-gallery" ref={gallery} aria-label="Travel inspiration gallery" data-motion={still?'paused':'playing'}>
      <Column photos={[images[0],images[5],images[4]]} y={y} paused={still} index={0}/>
      <Column photos={[images[6],images[3],images[2]]} y={y2} paused={still} index={1}/>
      <Column photos={[images[3],images[2],images[0]]} y={y3} paused={still} index={2}/>
      <Column photos={[images[4],images[0],images[1]]} y={y4} paused={still} index={3}/>
    </div>
    <button className="travel-motion" type="button" aria-pressed={still} disabled={!!reduced} onClick={()=>setPaused(value=>!value)}>{reduced?'Reduced motion on':paused?'Resume motion':'Pause motion'}</button>
  </section>;
}

/**
 * Skiper 30 Parallax_002 — React + framer motion + lenis (upstream).
 * Inspired by and adapted from https://www.siena.film/films/my-project-x
 * Original component: @gurvinder-singh02, https://gxuri.me
 * Free personal/commercial use and modification; attribution to Skiper UI required.
 * Roam Team adaptation: local travel photos, compact columns, native scrolling,
 * accessible pause/reduced motion, descriptive alt text, no demo spacer screens.
 */
