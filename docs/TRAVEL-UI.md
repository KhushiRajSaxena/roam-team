# Skiper30 travel UI

Updated September 16, 2026. Uses the exact registry selected by the user: [Skiper30 JSON](https://skiper-ui.com/registry/skiper30.json). The original response is preserved at `frontend/registry/skiper30.json`; the adapted component is `frontend/src/components/ui/skiper30.tsx`.

This supersedes the interrupted Skiper40 setup. Skiper30 is a React/Framer Motion parallax gallery. Its column/scroll-transform pattern is retained, with changes for a travel planner:

- Compact hero with a direct link to the trip form, instead of the original empty full-screen spacer sections.
- Five travel photographs, reused across four animated columns; three columns on narrow screens.
- Native browser scrolling instead of the original global Lenis RAF loop. Mount/unmount follows signed-in visibility, so sign-out cleans up the gallery.
- Pause/resume control, automatic reduced-motion preference, descriptive alternative text and keyboard focus styles.
- Beach photography on the sign-in card, violet/mint styling and visible Skiper UI attribution.
- No additional API/model requests or external image calls during use. Images and JS are served locally under the existing CSP.

## Photography

Images are downloaded from Unsplash's standard image CDN and stored in `dist/images`. These are editorial travel-inspiration images, not photos of a selected hotel or a promise about the selected destination. [Unsplash license](https://unsplash.com/license).

| Local file | Original source |
|---|---|
| mountain.jpg | https://images.unsplash.com/photo-1464822759023-fed622ff2c3b |
| beach.jpg | https://images.unsplash.com/photo-1507525428034-b723cf961d3e |
| alpine-night.jpg | https://images.unsplash.com/photo-1519681393784-d120267933ba |
| lakeside.jpg | https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1 |
| forest.jpg | https://images.unsplash.com/photo-1448375240586-882707db888b |

Downloaded at width 720, quality 80. All five images were visually inspected. Total image payload is approximately 400 KB.

## Build

The application still runs with Python alone; `dist/skiper-ui.js` is already built. To edit the React component, use Node and pnpm:

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
```

`build.mjs` bundles React and Framer Motion into a local production IIFE with no runtime CDN. The locked dependencies are included in `pnpm-lock.yaml`. No .env contents are injected into the bundle. Native esbuild binaries come from its optional platform package; dependency build scripts are not enabled. Plain CSS in `dist/styles.css` styles the gallery; Tailwind and Next.js are not runtime requirements.

## Checks

- TypeScript checking and production bundling passed.
- Real HTTP app + jsdom: login gate, gallery mount, 12 image tiles, form anchor, pause control, authenticated demo trip, real PDF generation, logout-all and gallery unmount passed.
- Separate reduced-motion test: animation paused automatically, toggle disabled, every image has descriptive alt text and a local URL.
- Running server confirmed to serve the latest bundle.
- All source photographs were visually inspected. Browser screenshot validation was unavailable because no browser was exposed to the computer-use tool; full-page visual appearance is not claimed as screenshot-verified.

The component's free license requires Skiper UI attribution, provided visibly in the app and retained in the source. See [Skiper30](https://skiper-ui.com/v1/skiper30).

## Skiper17 + Skiper47 result cards

The following user-requested registry responses are preserved in `frontend/registry/`:
- https://skiper-ui.com/registry/skiper17.json
- https://skiper-ui.com/registry/skiper47.json

Skiper17's scale/rotation GSAP ScrollTrigger timeline is adapted to the existing daily itinerary cards. Desktop cards stack gently during scrolling, using natural document flow instead of a full-screen pinned section. Tall cards, small screens, and reduced-motion preferences disable this stacking. Only this integration's GSAP context is reverted on cleanup; it never kills unrelated ScrollTriggers. Resize observers, listeners and pending frames are cleaned up on new plans and sign-out.

Skiper47's Swiper EffectCoverflow carousel now displays the selected flight and stay. Tabs, previous/next buttons, swipe and viewport keyboard navigation switch between the two cards. There is no autoplay or looping. Inactive-card interactive elements are inert; Show both cards provides the ordinary grid. All offer descriptions, prices, source timestamps, links and alternative disclosures are retained. Disclosures update carousel height. Turn off card animations flattens the carousel and disables the itinerary stacking. Reduced motion is automatic. PDF generation continues to use plan data, not the animated DOM.

The new dependencies are GSAP and Swiper, bundled locally. The build now emits `dist/skiper-ui.js` and `dist/skiper-ui.css`. The app includes both before its own style overrides. No backend or API changes were needed.

Validation: TypeScript and production build passed. Running-app jsdom checks passed for carousel creation, next-card navigation, inactive-card accessibility, Show both cards, alternative disclosures, motion toggle, desktop stack initialization/teardown, login, authenticated demo planning, PDF generation and logout cleanup. These are functional and lifecycle checks; native browser scrolling/rendering has not been screenshot-verified in this environment. No provider/model searches were used.

## Square Dock-style offer cards

Skiper47 now defaults to two square cards in one horizontal, non-wrapping row. Narrow screens scroll sideways rather than stacking the cards. Hover lifts and magnifies the active card, with a smaller neighboring lift; keyboard focus has a similar effect. Reduced motion and the existing animation toggle disable these transforms. Each card has a labeled, keyboard-focusable scrolling detail region so long descriptions and alternatives remain accessible within the square. Focus one card retains the perspective carousel as an optional view. Prices appear near the top. TypeScript/build and offline DOM checks passed for default layout, complete content, disclosure, switching views, disabling motion and teardown. Pixel geometry and hover animation were not verified in a native browser.

## Full-width results and structured itinerary

The completed plan now lives directly under the main page, outside the two-column setup/sidebar workspace. Budget, flight/stay cards and the itinerary occupy the whole available page width. The page uses responsive side gutters without the previous maximum-width cap. A View your completed plan link appears in the team panel after completion. Section navigation jumps to budget, offers, itinerary or trip editing; a separate day navigation links to each day.

On larger screens each day has a date/title column beside its time/activity/cost schedule. Mobile layouts put the date above the schedule and move amounts below activity details. The indigo (#4658a8), teal (#147d76), warm ivory (#f7f8f4) palette also covers headers, controls, the travel hero and budget chart. Square Dock cards, scroll-stack behavior and PDF data remain intact.

Offline DOM checks passed for result placement outside the sidebar, every itinerary row, valid section/day links, two offer cards, PDF plan handoff and clearing results on sign-out. JavaScript syntax passed. Native-browser pixel layout was not screenshot-verified.


## Compact layout and coastal palette

Trip setup now uses three balanced groups across the full width (two at tablet widths, one on mobile), removing the blank area beside the former sidebar. Offer cards have equal, content-driven heights instead of viewport-width-driven squares. Their complete descriptions and alternatives flow normally without inner scrolling. The original strong Dock magnification is retained at the user's request, with motion controls and reduced-motion support.

The latest palette combines coastal blue, leafy green and sunshine yellow. Two additional locally served Unsplash photos appear in the existing gallery:
- `shoreline.jpg`: John Hernandez, https://unsplash.com/photos/svmVoAaa4lI — https://images.unsplash.com/photo-1542864630-e176545e4138
- `tropical-coast.jpg`: Mink Mingle, https://unsplash.com/photos/g0Qdolm3K14 — https://images.unsplash.com/photo-1491378630646-3440efa57c3b

The requested travel-wallpaper search page was reviewed; direct downloads from that page were blocked by Unsplash's bot check. These related free Unsplash images were downloaded from its image CDN and visually inspected instead.

## Free travel tile reveal

The paid React Bits integration has been replaced by an original component at `frontend/src/components/ui/travel-tile-reveal.tsx`. It uses native scroll events, requestAnimationFrame and scoped transforms; no new dependencies, registry, license or API calls are needed. The former Skiper30 hero is retained in source but is no longer mounted.

Six local photographs enter in staggered columns within a sticky stage, then expand outward to reveal the travel headline and Plan my trip link. The persistent Skip to planner link bypasses the sequence. The reveal CTA is inert until visible. A motion toggle and automatic reduced-motion setting show a static collage and immediately accessible headline/CTA. Listeners, animation frames and ResizeObserver are removed on sign-out. The strong offer-card Dock hover remains unchanged.

Validation: TypeScript and production build passed. Offline DOM checks exercise entry/exit scroll positions, CTA accessibility, switching animation off/on, image availability and sign-out cleanup. Existing itinerary and PDF handoff regression checks passed. Native-browser pixel and scrolling appearance have not been visually verified in this environment.


### Faster entrance and clean result footer

Tiles now start entering when the hero reaches 85% of viewport height and finish within at most 240px of scrolling. Entrance timing is independent of the sticky zoom-out phase. The overall scroll track is shorter (about 1.5–1.65 viewports instead of 2.1–2.4). API calls, cache hits, model tokens, latency and other internal run statistics are no longer rendered beneath the trip. Budget information and required provider attribution remain. TypeScript/build, simulated 240px entrance, result rendering and PDF handoff checks passed.


## Supplied fonts and Coolors palette

Applied amber #edae49, coral #d1495b, teal #00798c, blue #30638e and navy #003d5b, with pale tints for surfaces. Arexa is the large Roam Team wordmark and display headline face. Vioneta Sloane is the lighter prose face; strong sans-serif section headings and smaller sans-serif labels distinguish the hierarchy. Demo fonts are restricted to Latin letters in CSS so numbers, currency and punctuation use complete fallback fonts. Kod's Hulling was inspected but not applied because several letters render as missing glyphs.

The uploaded font license notices are preserved in dist/fonts. These are personal-use demo fonts; commercial deployment requires appropriate licenses or replacement fonts. No font files were modified. Font previews were inspected locally; full-page rendering has not been screenshot-verified.


## October 5 typography foundation

`dist/ui-foundation.css` applies the requested Google Sans Flex / Google Sans / Noto Sans / Arial stack, 16px body text, #191c1d text, border-box sizing, pretty wrapping, text-size adjustment and antialiasing. The stack uses installed fonts; no Google font binaries are included. Content uses normal weights, subheadings 600–650, and headings 700. The transparent body sits over a light neutral canvas; the Coolors accents and travel animations remain. The copied 915px width and 100px height become a responsive heading-text maximum width and minimum heading-block height, rather than clipping the application to fixed dimensions.
