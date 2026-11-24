---
title: "Lombok 2018: two dark nights, one of them unexplained"
---

<style>
.page-head {margin: 0.5rem 0 1.25rem;}
.page-head h1 {margin: 0 0 0.4rem; font-size: 2rem; line-height: 1.15; max-width: none; display: flex; align-items: center; gap: 0.6rem;}
.page-head h1 .logo {width: 32px; height: 32px; flex: none;}
.brand {margin: 0 0 0.35rem; max-width: none; font: 600 0.78rem var(--sans-serif); letter-spacing: 0.06em; text-transform: uppercase; color: #a2431a;}
.brand a {color: inherit; text-decoration: none;}
.brand a:hover {text-decoration: underline;}
.lede {margin: 0; max-width: none; color: #52514e; font-size: 1rem; line-height: 1.5;}
.notice {border-left: 4px solid #eda100; padding: 0.6rem 0.9rem; background: #fdf6e3; font-size: 0.9rem; border-radius: 0 8px 8px 0; margin: 0 0 1.5rem;}
.notice p {margin: 0; max-width: none;}
section.part {margin: 0 0 2.25rem;}
section.part:last-of-type {margin-bottom: 1rem;}
.kicker {font: 600 0.72rem/1 var(--sans-serif); letter-spacing: 0.08em; text-transform: uppercase; color: #8a5a00; margin: 0 0 0.4rem;}
section.part h2 {margin: 0 0 0.5rem; font-size: 1.45rem; line-height: 1.2; max-width: none;}
/* the story text fills the page in two balanced columns on a wide screen, one on a narrow one (as drywet-explorer) */
section.part > p:not(.kicker) {max-width: none; margin: 0 0 1rem; line-height: 1.55; columns: 2 26rem; column-gap: 2.5rem; text-align: justify; hyphens: auto;}
.card {padding: 1.1rem 1.25rem;}
.card h3 {max-width: none; margin: 0 0 0.45rem; font-family: var(--sans-serif); font-size: 1.02rem; font-weight: 600; color: #0b0b0b;}
.card > .fine {margin: 0 0 0.8rem; max-width: none; line-height: 1.45;}
.fine {font-size: 0.8rem; color: #52514e;}
/* values that come from the data */
.dyn {font-weight: 600; font-family: var(--sans-serif); font-size: 0.95em; color: #a2431a; white-space: nowrap;}
.keys {display: flex; flex-wrap: wrap; gap: 0.3rem 1rem; font-size: 0.8rem; color: #52514e; margin: 0 0 0.6rem;}
.keys span {display: inline-flex; align-items: center; gap: 0.35rem;}
.key-line {display: inline-block; width: 22px; height: 0; border-top: 2px solid #0b0b0b;}
.triptych {display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.8rem;}
.triptych h4 {margin: 0; font: 600 0.95rem/1.2 var(--sans-serif);}
.triptych p.sub {margin: 0.1rem 0 0.4rem; min-height: 1.2em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
#observablehq-main {min-height: 0;}        /* Framework keeps the main column a screen tall: no gap above the footer */
#observablehq-footer {margin-top: 1.5rem;}
.triptych p {margin: 0.3rem 0 0; font-size: 0.8rem; color: #52514e; max-width: none;}
.triptych .map-buttons {display: none;}   /* three small maps side by side: drag and scroll still zoom */
@media (max-width: 800px) {.triptych {grid-template-columns: 1fr;}}
.map-hover {display: none;}
.map-buttons {position: absolute; top: 8px; right: 8px; display: flex; gap: 4px;}
.map-buttons button {font: inherit; font-size: 0.8rem; min-width: 1.8rem; padding: 0.15rem 0.45rem; border: 1px solid #c3c2b7; border-radius: 6px; background: #fcfcfb; color: #0b0b0b; cursor: pointer;}
.map-buttons button:disabled {color: #898781; cursor: default;}
.legend {display: flex; flex-wrap: wrap; gap: 0.35rem 1rem; font-size: 0.8rem; color: #52514e; margin: 0.7rem 0 0;}
.legend-item {display: inline-flex; align-items: center; gap: 0.35rem;}
.swatch {width: 14px; height: 14px; display: inline-block; border-radius: 50%; border: 1px solid #c3c2b7; flex: none;}
.tiles {display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 1rem;}
.tile-value {font-size: 1.7rem; font-weight: 600; line-height: 1.15; margin-bottom: 0.3rem;}
.tile-label {font-size: 0.82rem; color: #52514e; line-height: 1.4;}
.when {display: grid; grid-template-columns: auto auto minmax(160px, 1fr); gap: 1rem 1.5rem; align-items: center; margin: 0 0 0.6rem;}
.night-label {font-size: 1.15rem; font-weight: 600; width: 10.5rem; white-space: nowrap;}
.when input[type=range] {width: 100%;}
@media (max-width: 560px) {.when {grid-template-columns: 1fr auto;} .when input[type=range] {grid-column: 1 / -1;}}
.steps {display: inline-flex;}
.steps .step {font: inherit; line-height: 1; min-width: 2rem; padding: 0.3rem 0.5rem; border: 1px solid #c3c2b7; border-left-width: 0; background: #fcfcfb; cursor: pointer;}
.steps .step:first-child {border-left-width: 1px; border-radius: 8px 0 0 8px;}
.steps .step:last-child {border-radius: 0 8px 8px 0;}
</style>

<header class="page-head">
  <p class="brand"><a href="./" title="Back to the main dashboard">&larr; Nightlights Explorer</a> · Case study</p>
  <h1><svg class="logo" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10.5" fill="#10151c"/><path d="M12 1.5a10.500 10.500 0 0 1 0 21 13.500 13.500 0 0 0 0-21Z" fill="#2a3644"/><circle cx="8.300" cy="9.400" r="3" fill="#ffd76a" opacity=".22"/><circle cx="8.300" cy="9.400" r="1.500" fill="#ffd76a"/><circle cx="12.700" cy="13.700" r="1.100" fill="#ffd76a"/><circle cx="7.300" cy="14.900" r=".800" fill="#f2b24a"/><circle cx="11.300" cy="6.700" r=".600" fill="#f2b24a"/><circle cx="10.200" cy="17.600" r=".600" fill="#f2b24a"/></svg>Lombok 2018: two dark nights, one of them unexplained</h1>
  <p class="lede">Three large earthquakes, among many smaller ones, struck Lombok between 29 July and 19 August 2018. A satellite passed over every night at about 01:30. This page asks what it saw that nobody on the island could have seen, and what it could not see at all.</p>
</header>

<div class="notice">
  <p><strong>What this page can and cannot say.</strong> None of it has been checked against records of power or damage. The page compares light with the eleven nights before the main earthquake, with the same cells on reference nights seen from a similar angle, and with Bali. It does not say why a place was dim, and nothing here is a statement about electricity.</p>
</div>

```js
import {files} from "./data/events/lombok2018/files.js";
import {files as national} from "./data/files.js";
import {loadTyped} from "./components/load.js";
import {drawMap} from "./components/map.js";
import {NO_VALUE} from "./components/palette.js";
import * as d3 from "npm:d3";
```

```js
const meta = await files["meta.json"].json();
const S = meta.story;
const cells = await loadTyped("lombok-cells", files["cells.u32.gz"], Uint32Array);
const adjusted = await loadTyped("lombok-adjusted", files["adjusted.u8.gz"], Uint8Array);
const raw = await loadTyped("lombok-nights", files["nights.u8.gz"], Uint8Array);
const info = await loadTyped("lombok-info", files["cell_info.u8.gz"], Uint8Array);
const D = meta.dates.length, N = cells.length;
const dates = meta.dates.map((s) => new Date(`${s}T00:00:00Z`));
const night = (iso) => meta.dates.indexOf(iso);
const provinces = await national["outlines/province.geojson"].json();
const districtOutlines = await national["outlines/district.geojson"].json();
const island = districtOutlines.features.filter((f) => S.focus.districts.includes(f.properties.code));
const COLS = 86400, DEG = 1 / 240;
const lon = Float32Array.from(cells, (i) => -180 + ((i % COLS) + 0.5) * DEG);
const lat = Float32Array.from(cells, (i) => 90 - (Math.floor(i / COLS) + 0.5) * DEG);
const day = (k, long = true) => dates[k].toLocaleDateString("en-GB", {day: "numeric", month: long ? "long" : "short", timeZone: "UTC"});
const marks = meta.marks.map((m) => ({k: night(m.date), date: dates[night(m.date)], label: m.label}));
const pct = (v) => `${(100 * v).toFixed(0)}%`;
// ColorBrewer BrBG: brown is dimmer than the reference, teal brighter. Class 0 (no reference) is not drawn.
const brbg = d3.schemeBrBG[7];
const CLASS_COLOURS = [null, NO_VALUE, NO_VALUE, brbg[0], brbg[1], brbg[3], brbg[5], NO_VALUE];
const rgb = (hex) => [1, 3, 5].map((k) => parseInt(hex.slice(k, k + 2), 16)).join(", ");
const colours = CLASS_COLOURS.map((c) => (c ? rgb(c) : null));
const FOCUS = {key: "lombok", bounds: [[115.95, -8.95], [116.75, -8.15]]};
const outlines = island.map((feature) => ({feature, id: null, state: null, weak: false, fill: "transparent", text: ""}));
// a map of the island for one night; `source` is the adjusted or the raw class array
const nightMap = (k, source, sync = null) => (width) => {
  const mask = 7;
  const level = new Uint8Array(N);
  for (let i = 0; i < N; i++) level[i] = source[k * N + i] & mask;
  return drawMap({width, land: provinces.features, units: outlines, context: [], selected: [], lights: {lon, lat, level, colours}, focus: FOCUS, sync, onPick: () => {}});
};
const classLegend = html`<div class="legend">${[[3, "under 50% of its reference"], [4, "50 to 80%"], [5, "80 to 125%: about the same"], [6, "125% or more"]].map(([k, label]) =>
  html`<span class="legend-item"><span class="swatch" style=${`background:${CLASS_COLOURS[k]};`}></span>Cell at ${label}</span>`)}
  <span class="legend-item"><span class="swatch" style=${`background:${NO_VALUE};`}></span>Cell not seen that night (cloud or a poor-quality retrieval), which is not the same as dark</span></div>`;
// figures used in the text: every unit figure is the summed light of the cells seen over their summed reference
const C = S.control, F = S.focus, B = S.bands, G = S.same_geometry;
const lit = (iso) => F.light[night(iso)], against = (iso) => F.light_adjusted[night(iso)];
const controlNights = C.light.filter((v) => v !== null).length;
const [beforeK, duringK, afterK] = meta.story_nights.map(night);
const litBefore = d3.sum(S.went_dark.rings, (r) => r.lit_before), wentDark = d3.sum(S.went_dark.rings, (r) => r.went_dark);
const show = (v) => (v === null || v === undefined ? "no figure" : pct(v));
// against references from nights seen from a similar angle (within M.tolerance degrees): the figure the text leans on
const M = S.matched;
const like = (iso) => M.focus.light[night(iso)], baliLike = (iso) => M.control.light[night(iso)];
const refK = d3.range(night(meta.reference.last) + 1);
const spread = (values) => d3.deviation(refK.filter((k) => values[k] !== null && M.focus.light[k] !== null && F.light[k] !== null), (k) => Math.log(values[k]));
```

<section class="part">
<p class="kicker">1 · What the island could not see</p>

## Most of the dimming was the angle of view

<p>On the ground, a darker night after an earthquake looks like damage. On <span class="dyn">${day(night("2018-08-08"))}</span>, three nights after the magnitude 6.9, Lombok's lit cells gave <span class="dyn">${show(lit("2018-08-08"))}</span> of their light on the reference nights. But Bali, farther from every one of these epicentres, gave <span class="dyn">${show(C.light[night("2018-08-08")])}</span> of its own. Neither drop survives a fair comparison. That night the satellite looked almost straight down, <span class="dyn">${M.zenith[night("2018-08-08")].toFixed(0)} degrees</span> from overhead, and over these two islands in these weeks cells read dimmer from nearly overhead than from the side. (The product's guide reports the opposite over dense city centres, so this is a finding about these places, not a law.) So compare each cell only with reference nights seen from within ${M.tolerance} degrees of the same angle: Lombok then stood at <span class="dyn">${show(like("2018-08-08"))}</span> and Bali at <span class="dyn">${show(baliLike("2018-08-08"))}</span>. Done for every night, this halves the scatter of the reference nights. What is left after the main earthquake is small: <span class="dyn">${show(like("2018-08-05"))}</span> on the night itself, <span class="dyn">${show(like("2018-08-06"))}</span> and <span class="dyn">${show(like("2018-08-07"))}</span> on the two that followed, about a fifth down and close to the edge of the noise.</p>

```js
const series = meta.dates.map((_, k) => ({k, date: dates[k], bali: C.light[k] === null ? null : 100 * C.light[k],
  raw: F.light[k] === null ? null : 100 * F.light[k], adjusted: M.focus.light[k] === null || M.focus.cells[k] < 400 ? null : 100 * M.focus.light[k], seen: F.raw.seen[k],
  baliLike: M.control.light[k] === null || M.control.cells[k] < 400 ? null : 100 * M.control.light[k], cells: M.focus.cells[k], zenith: M.zenith[k]}));
const skyChart = (width) => Plot.plot({
  width, height: 300, marginLeft: 48, marginRight: 20,
  x: {label: null}, y: {label: "% of the reference nights", domain: [0, 170], grid: true},
  marks: [
    Plot.ruleY([100], {stroke: "#898781"}),
    Plot.ruleX(marks, {x: "date", stroke: "#c53030", strokeDasharray: "2,3"}),
    Plot.text(marks, {x: "date", y: 170, text: (m) => m.label.split(",")[0], dy: 8, dx: 4, textAnchor: "start", fontSize: 10, fill: "#c53030"}),
    Plot.lineY(series.filter((r) => r.raw !== null), {x: "date", y: "raw", stroke: "#b5b3aa", strokeWidth: 1.2}),
    Plot.dot(series.filter((r) => r.raw !== null), {x: "date", y: "raw", r: 2.5, fill: "#b5b3aa"}),
    Plot.dot(series.filter((r) => r.baliLike !== null), {x: "date", y: "baliLike", r: 3.5, fill: "#5ab4ac", stroke: "#0b0b0b", strokeWidth: 0.5, symbol: "square"}),
    Plot.dot(series.filter((r) => r.adjusted !== null), {x: "date", y: "adjusted", r: 5, fill: "#0b0b0b"}),
    Plot.tip(series.filter((r) => r.raw !== null), Plot.pointerX({x: "date", y: "raw",
      title: (r) => `${day(r.k)}, seen from ${r.zenith === null ? "an unknown angle" : r.zenith.toFixed(0) + " degrees"}\nLombok against all reference nights: ${r.raw.toFixed(0)}% (${r.seen.toLocaleString("en")} of ${F.raw.cells.toLocaleString("en")} cells seen)\nLombok against nights seen alike: ${r.adjusted === null ? "no figure" : r.adjusted.toFixed(0) + "% (" + r.cells.toLocaleString("en") + " cells)"}\nBali against nights seen alike: ${r.baliLike === null ? "too few cells" : r.baliLike.toFixed(0) + "%"}`}))
  ]
});
```

<div class="card">
  <h3>Lombok's light, before and after the angle is taken out</h3>
  <div class="keys"><span><span class="key-line" style="border-color:#b5b3aa"></span>Lombok against all reference nights</span>
    <span><span class="swatch" style="background:#0b0b0b;"></span>Lombok against nights seen alike</span>
    <span><span class="swatch" style="background:#5ab4ac;border-radius:2px;"></span>Bali against nights seen alike</span>
    <span><span class="key-line" style="border-top:2px dashed #c53030"></span>First night after an earthquake</span></div>
  ${resize(skyChart)}
  <p class="fine" style="margin-top:0.6rem;">Each point is the summed light of the cells seen that night over the summed reference of the same cells. Grey: a cell's reference is its median on the eleven nights to ${day(night(meta.reference.last))}. Black and teal: its median on those of the eleven nights seen from within ${M.tolerance} degrees of the night in question, never the night itself, so fewer cells have a figure (the tip gives the count; both islands are drawn with at least 400 cells). Many of these references are a single night, which makes each point noisier than it looks. Seven of the eleven reference nights follow the first earthquake of 29 July, so "reference" is not "before any shaking". Over the reference nights the grey figure scatters by ${pct(Math.exp(spread(F.light)) - 1)} and the black by ${pct(Math.exp(spread(M.focus.light)) - 1)}.</p>
</div>
</section>

<section class="part">
<p class="kicker">2 · What only a satellite could catch</p>

## Two dark nights, and only one has an earthquake

<p>The third earthquake struck at 22:56 on 19 August. The satellite passed about two and a half hours later. Against nights seen from a similar angle, the <span class="dyn">${M.focus.cells[night("2018-08-19")].toLocaleString("en")}</span> cells of Lombok seen that night gave <span class="dyn">${show(like("2018-08-19"))}</span> of their light; Bali gave <span class="dyn">${show(baliLike("2018-08-19"))}</span>. A second test agrees: sixteen nights earlier the satellite saw the island from nearly the same angle, and over the ${G.focus.cells[night("2018-08-19")].toLocaleString("en")} cells seen on both nights Lombok gave <span class="dyn">${show(G.focus.ratio[night("2018-08-19")])}</span> of what it gave then. The night after, it was back at <span class="dyn">${show(like("2018-08-20"))}</span>. So about half the light of the cells seen was missing for one night. Only <span class="dyn">${pct(F.raw.seen[duringK] / F.raw.cells)}</span> of the island's cells were seen, so this is not a statement about the whole island.</p>

<p>The darkest night of the month is a different one. On <span class="dyn">${day(night("2018-08-12"))}</span> Lombok gave <span class="dyn">${show(like("2018-08-12"))}</span> of its light at that angle, with <span class="dyn">${F.raw.seen[night("2018-08-12")].toLocaleString("en")}</span> of its ${F.raw.cells.toLocaleString("en")} cells seen, and it was back the next night. Bali was mostly under cloud, but the <span class="dyn">${M.control.cells[night("2018-08-12")]}</span> of its cells that were seen read <span class="dyn">${show(baliLike("2018-08-12"))}</span>: nothing unusual there. None of the three large earthquakes fell on that night. This page cannot say whether it was a power failure, something in the sky that the quality flag missed, or a fault of the product, and it has not been checked against any record. It is the most unusual thing the satellite saw this month, and nothing here explains it.</p>

<div class="card">
  <div class="triptych">
    ${[[beforeK, "Before"], [duringK, "The night of the third earthquake"], [afterK, "The night after"]].map(([k, label]) => html`<div>
      <h4>${day(k)}</h4><p class="sub">${label}</p>
      ${resize(nightMap(k, adjusted, "triptych"))}
      <p>Lombok against nights seen alike: <strong>${show(M.focus.light[k])}</strong>. ${F.raw.seen[k].toLocaleString("en")} of ${F.raw.cells.toLocaleString("en")} cells seen.</p>
    </div>`)}
  </div>
  ${classLegend}
  <p class="fine" style="margin-top:0.6rem;">The three maps move together: zoom or drag one and the others follow. Each lit cell is coloured by its light that night, divided by its reference and by what Bali did the same night. On the middle night about ${pct(F.raw.seen[duringK] / F.raw.cells)} of the cells were seen: the rest of the island is grey, not dark. Even on an ordinary night many single cells read under half their reference, so read the pattern, not single cells. A cell is about 460 m across and the sensor's view is wider.</p>
</div>
</section>

<section class="part">
<p class="kicker">3 · Where the shaking was, and how little light is there</p>

## Near the epicentre there is almost nothing to watch

<p>The obvious question is whether places nearer the epicentre dimmed more. Night lights cannot answer it here. Of Lombok's ${F.raw.cells.toLocaleString("en")} lit cells, only <span class="dyn">${B[0].raw.cells + B[1].raw.cells}</span> lie within 30 km of the epicentre of the main earthquake. Three nights after it the band 15 to 30 km out read <span class="dyn">${show(B[1].light_adjusted[night("2018-08-08")])}</span> against Bali, and the same ${B[1].raw.cells} cells, followed through the nights before the main earthquake, ranged from <span class="dyn">${show(d3.min(B[1].light_adjusted.slice(0, night(meta.reference.last) + 1).filter((v) => v !== null)))}</span> to <span class="dyn">${show(d3.max(B[1].light_adjusted.slice(0, night(meta.reference.last) + 1).filter((v) => v !== null)))}</span>. A handful of cells swings that much on its own. After the main earthquake the bands beyond 30 km, which hold nearly all the light, show no drop larger than the scatter. On 19 August every band is down by about half: that is the dark night of the section above, not something that depends on distance. Night lights watch the towns of the south and west, not the north of the island.</p>

```js
const bandLabel = (b) => `${b.km[0]} to ${b.km[1]} km`;
const bandNights = ["2018-08-03", "2018-08-08", "2018-08-13", "2018-08-19", "2018-08-20"].filter((iso) => C.light[night(iso)] !== null);
const bandRows = B.flatMap((b) => bandNights.map((iso) => ({band: bandLabel(b), night: day(night(iso), false), order: night(iso),
  value: b.light_adjusted[night(iso)] === null ? null : 100 * b.light_adjusted[night(iso)], seen: b.raw.seen[night(iso)], cells: b.raw.cells}))).filter((r) => r.value !== null);
const bandChart = (width) => Plot.plot({
  width, height: 280, marginLeft: 48, marginBottom: 46,
  x: {label: "Distance from the epicentre of 5 August, km (each bar is a 15 or 25 km band starting here)", domain: B.map(bandLabel), tickFormat: (d) => d.split(" ")[0]},
  y: {label: "% of the reference nights, against Bali", domain: [0, 150], grid: true},
  fx: {domain: bandNights.map((iso) => day(night(iso), false)), label: null},
  marks: [
    Plot.ruleY([100], {stroke: "#898781"}),
    Plot.barY(bandRows, {fx: "night", x: "band", y: "value", fill: (r) => (r.cells < 100 ? "#d9d7cf" : "#9aa3ad"), insetLeft: 1, insetRight: 1}),
    Plot.text(bandRows, {fx: "night", x: "band", y: "value", text: (r) => r.value.toFixed(0), dy: -6, fontSize: 10}),
    Plot.tip(bandRows, Plot.pointer({fx: "night", x: "band", y: "value", title: (r) => `${r.night}, ${r.band}\n${r.value.toFixed(0)}% against Bali\n${r.seen} of ${r.cells} cells seen`}))
  ]
});
const countChart = (width) => Plot.plot({
  width, height: 150, marginLeft: 90, marginRight: 50,
  x: {label: "Lit cells with a reference", grid: true}, y: {label: null, domain: B.map(bandLabel)},
  marks: [Plot.barX(B, {y: bandLabel, x: (b) => b.raw.cells, fill: "#9aa3ad"}), Plot.text(B, {y: bandLabel, x: (b) => b.raw.cells, text: (b) => b.raw.cells.toLocaleString("en"), dx: 6, textAnchor: "start", fontSize: 11}),
          Plot.tip(B, Plot.pointerY({y: bandLabel, x: (b) => b.raw.cells, title: (b) => `${bandLabel(b)} from the epicentre\n${b.raw.cells.toLocaleString("en")} lit cells with a reference\n${((100 * b.raw.cells) / F.raw.cells).toFixed(1)}% of Lombok's lit cells`}))]
});
```

<div class="grid grid-cols-2" style="gap:1.1rem; grid-auto-rows:auto;">
  <div class="card">
    <h3>Light against Bali, by distance from the epicentre</h3>
    <p class="fine">Nights on which Bali was seen well enough: before the main earthquake, three and eight nights after it, the night of the third earthquake, and the night after that. A bar is the band's summed light over its summed reference, divided by Bali's; pale bars are the two nearest bands, of ${B[0].raw.cells} and ${B[1].raw.cells} cells, shown so their scatter can be seen, not to be read. Distances are from the epicentre of 5 August; the earthquake of 19 August was elsewhere.</p>
    ${resize(bandChart)}
  </div>
  <div class="card">
    <h3>Where Lombok's light is</h3>
    <p class="fine">Lit cells by distance from the epicentre. The two nearest bands hold ${B[0].raw.cells + B[1].raw.cells} cells between them.</p>
    ${resize(countChart)}
  </div>
</div>
</section>

<section class="part">
<p class="kicker">4 · What stayed invisible</p>

## Nothing was seen to go out for good, and nothing new lit up

<p>Two things that a survey on the ground might report were not found in these nights. Of the lit cells on Lombok that could be judged, none went dark and stayed dark. And no dark cell within 40 km of the epicentre became lit: lighting too faint for this sensor, if there was any, leaves no trace. On the night of the main earthquake too few of Bali's cells were seen for the plain comparison; against nights seen alike Lombok reads about a fifth down, which is inside the spread of its quiet nights.</p>

<div class="tiles">
  <div class="card"><div class="tile-value">${wentDark} of ${litBefore.toLocaleString("en")}</div><div class="tile-label">Lit cells on Lombok, of the ${litBefore.toLocaleString("en")} of ${F.raw.cells.toLocaleString("en")} seen often enough to judge, that went dark and stayed dark through ${day(night(S.went_dark.after[0]))} to ${day(night(S.went_dark.after[1]))}. Bali: ${S.went_dark.control.went_dark} of ${S.went_dark.control.lit_before.toLocaleString("en")}.</div></div>
  <div class="card"><div class="tile-value">${S.new_light.near.lit_after} of ${S.new_light.near.dark_before.toLocaleString("en")}</div><div class="tile-label">Dark cells within 40 km of the epicentre, land and sea, that became lit in the same nights. West of Lombok over the same nights: ${S.new_light.control_side.lit_after} of ${S.new_light.control_side.dark_before.toLocaleString("en")}.</div></div>
  <div class="card"><div class="tile-value">${controlNights} of ${D}</div><div class="tile-label">Nights on which Bali was seen well enough to compare with. It was not on ${day(night("2018-08-04"), false)} to ${day(night("2018-08-07"), false)}, which includes the night of the main earthquake, nor on ${day(night("2018-08-09"), false)} to ${day(night("2018-08-12"), false)}.</div></div>
  <div class="card"><div class="tile-value">16 nights</div><div class="tile-label">Until the satellite sees a place from the same angle again. Between two such nights a town's light can read tens of percent apart with nothing changed on the ground. It passes at about 01:30: power lost and restored between passes leaves no trace.</div></div>
</div>
</section>

<section class="part">
<p class="kicker">Every night</p>

## Step through the nights yourself

```js
const nightInput = html`<input type="range" min="0" max="${D - 1}" step="1" value="${duringK}" aria-label="Night, from ${day(0)} to ${day(D - 1)}">`;
const chosen = Generators.input(nightInput);
const setNight = (k) => { nightInput.value = Math.max(0, Math.min(D - 1, k)); nightInput.dispatchEvent(new Event("input", {bubbles: true})); };
const step = (label, title, by) => html`<button type="button" class="step" title=${title} aria-label=${title} onclick=${() => setNight(+nightInput.value + by)}>${label}</button>`;
const labelEl = html`<div class="night-label" aria-live="polite"></div>`;
const noteEl = html`<p class="fine" style="margin:0 0 0.7rem; max-width:none;"></p>`;
const mapEl = html`<div></div>`;
display(html`<div class="card">
  <div class="when">${labelEl}<div class="steps">${step("‹", "One night back", -1)}${step("›", "One night forward", 1)}</div>${nightInput}</div>
  ${noteEl}${mapEl}${classLegend}
</div>`);
```

```js
{
  const hasControl = C.light[chosen] !== null;
  const mark = marks.find((m) => m.k === chosen);
  labelEl.textContent = `${day(chosen)} 2018`;
  nightInput.setAttribute("aria-valuetext", `${day(chosen)} 2018`);
  noteEl.textContent = `The night that began on the evening of ${day(chosen)}. ` + (mark ? `First night after the earthquake of ${mark.label}. ` : "")
    + (hasControl ? `Cells are shown against Bali, which stood at ${pct(C.light[chosen])} of its own reference. ` : "Bali was not seen well enough this night, so cells are shown uncorrected: a shared dip cannot be told from a local one. ")
    + `${pct(meta.seen_share_by_night[chosen])} of the cells of Bali, Lombok and west Sumbawa were seen; on Lombok, ${F.raw.seen[chosen].toLocaleString("en")} of ${F.raw.cells.toLocaleString("en")}.`;
  mapEl.replaceChildren(resize(nightMap(chosen, hasControl ? adjusted : raw)));
}
```
</section>

<p class="fine" style="max-width:none;">Source: NASA Black Marble daily, VNP46A2, Collection 2, the moonlight-corrected radiance, high-quality retrievals only, over the ${N.toLocaleString("en")} lit cells of Bali, Lombok and west Sumbawa (${meta.cells.with_reference.toLocaleString("en")} with a reference). A cell's reference is its median over the nights of ${day(0)} to ${day(night(meta.reference.last))}, with at least ${meta.reference.min_nights} of them seen. Earthquake times, magnitudes and the epicentre: USGS catalogue. A file dated D is the night that begins on the evening of local date D.</p>

<p class="fine" style="max-width:none; margin-top:1.2rem;"><a href="./">\&larr; Back to the main dashboard</a> · <a href="https://github.com/bennyistanto/nightlights-explorer" target="_blank" rel="noopener">Code and method on GitHub</a></p>
