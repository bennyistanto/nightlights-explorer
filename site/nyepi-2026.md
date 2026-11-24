---
title: "Nyepi 2026: an island at under a tenth of its light"
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
.steps {display: inline-flex;}
.steps .step {font: inherit; line-height: 1; min-width: 2rem; padding: 0.3rem 0.5rem; border: 1px solid #c3c2b7; border-left-width: 0; background: #fcfcfb; cursor: pointer;}
.steps .step:first-child {border-left-width: 1px; border-radius: 8px 0 0 8px;}
.steps .step:last-child {border-radius: 0 8px 8px 0;}
</style>

<header class="page-head">
  <p class="brand"><a href="./" title="Back to the main dashboard">&larr; Nightlights Explorer</a> · Case study</p>
  <h1><svg class="logo" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10.5" fill="#10151c"/><path d="M12 1.5a10.500 10.500 0 0 1 0 21 13.500 13.500 0 0 0 0-21Z" fill="#2a3644"/><circle cx="8.300" cy="9.400" r="3" fill="#ffd76a" opacity=".22"/><circle cx="8.300" cy="9.400" r="1.500" fill="#ffd76a"/><circle cx="12.700" cy="13.700" r="1.100" fill="#ffd76a"/><circle cx="7.300" cy="14.900" r=".800" fill="#f2b24a"/><circle cx="11.300" cy="6.700" r=".600" fill="#f2b24a"/><circle cx="10.200" cy="17.600" r=".600" fill="#f2b24a"/></svg>Nyepi 2026: an island at under a tenth of its light</h1>
  <p class="lede">Nyepi is the Balinese day of silence, when by custom lights are kept off for a night. It is the one night of the year when a dimming is known in advance, which makes it a test of what a satellite can measure.</p>
</header>

<div class="notice">
  <p><strong>What this page can and cannot say.</strong> March is the wet season: the only clear nights near Nyepi came ten nights later, so they are the reference, and readings the product marks as poor quality had to be admitted to see the island at all. In 2026 Nyepi also fell two nights before Eid al-Fitr, and the reference nights a week after it, so neither is an ordinary night. The page says how much light was seen. It does not measure how many people took part, it says nothing about electricity, and it has not been checked against any record on the ground.</p>
</div>

```js
import {files} from "./data/events/nyepi2026/files.js";
import {files as national} from "./data/files.js";
import {loadTyped} from "./components/load.js";
import {drawMap} from "./components/map.js";
import {nightExplorer} from "./components/explorer.js";
import {NO_VALUE} from "./components/palette.js";
import * as d3 from "npm:d3";
```

```js
const meta = await files["meta.json"].json();
const S = meta.story;
const units = (await files["units.json"].json()).district;
const cells = await loadTyped("nyepi-cells", files["cells.u32.gz"], Uint32Array);
const raw = await loadTyped("nyepi-nights", files["nights.u8.gz"], Uint8Array);
const D = meta.dates.length, N = cells.length;
const dates = meta.dates.map((s) => new Date(`${s}T00:00:00Z`));
const night = (iso) => meta.dates.indexOf(iso);
const K = night(meta.marks[0].date);
const provinces = await national["outlines/province.geojson"].json();
const districtOutlines = await national["outlines/district.geojson"].json();
const names = new Map(districtOutlines.features.map((f) => [f.properties.code, f.properties.name]));
const shown = districtOutlines.features.filter((f) => units.code.includes(f.properties.code));
const COLS = 86400, DEG = 1 / 240;
const lon = Float32Array.from(cells, (i) => -180 + ((i % COLS) + 0.5) * DEG);
const lat = Float32Array.from(cells, (i) => 90 - (Math.floor(i / COLS) + 0.5) * DEG);
const day = (k, long = true) => dates[k].toLocaleDateString("en-GB", {day: "numeric", month: long ? "long" : "short", timeZone: "UTC"});
const pct = (v, digits = 0) => `${(100 * v).toFixed(digits)}%`;
const brbg = d3.schemeBrBG[7];
const CLASS_COLOURS = [null, NO_VALUE, NO_VALUE, brbg[0], brbg[1], brbg[3], brbg[5], NO_VALUE];
const rgb = (hex) => [1, 3, 5].map((k) => parseInt(hex.slice(k, k + 2), 16)).join(", ");
const colours = CLASS_COLOURS.map((c) => (c ? rgb(c) : null));
const FOCUS = {key: "nyepi", bounds: [[114.25, -8.95], [116.45, -8.0]]};
const outlines = shown.map((feature) => ({feature, id: null, state: null, weak: false, fill: "transparent", text: ""}));
const nightMap = (k, sync = null) => (width) => {
  const level = new Uint8Array(N);
  for (let i = 0; i < N; i++) level[i] = raw[k * N + i] & 7;
  return drawMap({width, land: provinces.features, units: outlines, context: [], selected: [], lights: {lon, lat, level, colours}, focus: FOCUS, sync, onPick: () => {}});
};
const classLegend = html`<div class="legend">${[[3, "under 50% of its reference"], [4, "50 to 80%"], [5, "80 to 125%: about the same"], [6, "125% or more"]].map(([k, label]) =>
  html`<span class="legend-item"><span class="swatch" style=${`background:${CLASS_COLOURS[k]};`}></span>Cell at ${label}</span>`)}
  <span class="legend-item"><span class="swatch" style=${`background:${NO_VALUE};`}></span>Cell not seen that night (cloud or an unusable retrieval), which is not the same as dark</span></div>`;
const F = S.focus, C = S.control, M = S.matched;
const show = (v, digits = 0) => (v === null || v === undefined ? "no figure" : pct(v, digits));
const district = (code) => { const u = units.code.indexOf(code); return {name: names.get(code) ?? String(code), ratio: units.ratio[u][K], coverage: units.coverage[u][K], cells: units.cells[u]}; };
const [nyepiK, afterK, laterK] = meta.story_nights.map(night);
const refDates = meta.reference.dates.map((iso) => day(night(iso))).join(" and ");
```

<section class="part">
<p class="kicker">1 · A known darkness, measured</p>

## An island at under a tenth of itself

<p>On the night of ${day(K)} 2026 the lit cells of Bali that the satellite could see gave <span class="dyn">${pct(F.light[K], 1)}</span> of the light the same cells gave on ${refDates}. That is <span class="dyn">${F.raw.seen[K].toLocaleString("en")}</span> of Bali's ${F.raw.cells.toLocaleString("en")} lit cells; the rest had no usable reading. The neighbours across the straits read <span class="dyn">${show(C.light[K])}</span> of their own reference that night. That figure cannot be leaned on: it moves from about 60% to over 110% with how strictly the viewing angle is matched, so it says only that the neighbours were not dark. Bali's figure does not move like that. Nyepi night was seen from <span class="dyn">${M.zenith[K].toFixed(0)} degrees</span>; of the two reference nights only 30 March was seen from within ${M.tolerance} degrees of that, and against that night alone Bali gave <span class="dyn">${show(M.focus.light[K], 1)}</span> on ${M.focus.cells[K].toLocaleString("en")} cells. Under a tenth, whichever way it is measured.</p>

```js
const series = meta.dates.map((_, k) => ({k, date: dates[k], bali: F.light[k] === null ? null : 100 * F.light[k], seen: F.raw.seen[k],
  control: C.light[k] === null ? null : 100 * C.light[k]}));
const lightChart = (width) => Plot.plot({
  width, height: 300, marginLeft: 48, marginRight: 20,
  x: {label: null}, y: {label: "% of the reference nights", domain: [0, 160], grid: true},
  marks: [
    Plot.ruleY([100], {stroke: "#898781"}),
    Plot.ruleX([dates[K]], {stroke: "#c53030", strokeDasharray: "2,3"}),
    Plot.text([dates[K]], {x: (d) => d, y: 160, text: ["Nyepi night"], dy: 8, dx: 4, textAnchor: "start", fontSize: 10, fill: "#c53030"}),
    Plot.dot(series.filter((r) => r.control !== null), {x: "date", y: "control", r: 3.5, fill: "#5ab4ac", stroke: "#0b0b0b", strokeWidth: 0.5, symbol: "square"}),
    Plot.dot(series.filter((r) => r.bali !== null), {x: "date", y: "bali", r: (r) => (r.seen >= 1000 ? 5 : 2.5), fill: "#0b0b0b"}),
    Plot.tip(series.filter((r) => r.bali !== null), Plot.pointer({x: "date", y: "bali",
      title: (r) => `${day(r.k)}\nBali: ${r.bali.toFixed(0)}% of its reference light\n${r.seen.toLocaleString("en")} of ${F.raw.cells.toLocaleString("en")} cells seen\nNeighbours: ${r.control === null ? "not seen well enough" : r.control.toFixed(0) + "%"}`}))
  ]
});
```

<div class="card">
  <h3>Bali's light, night by night</h3>
  <div class="keys"><span><span class="swatch" style="background:#0b0b0b;"></span>Bali (small points: fewer than 1,000 of its cells seen)</span>
    <span><span class="swatch" style="background:#5ab4ac;border-radius:2px;"></span>Lombok and Banyuwangi the same night</span>
    <span><span class="key-line" style="border-top:2px dashed #c53030"></span>Nyepi night</span></div>
  ${resize(lightChart)}
  <p class="fine" style="margin-top:0.6rem;">Each point is the summed light of the cells seen that night over the summed reference of the same cells. Most nights have no point at all: the island was under cloud. The two reference nights, ${refDates}, sit near 100% by construction. The night after Nyepi reads ${show(F.light[afterK])}, above the reference, but the neighbours were not seen that night, so whether Bali was truly brighter cannot be said.</p>
</div>
</section>

<section class="part">
<p class="kicker">2 · What only a satellite could show</p>

## The darkness stops at the shore

<p>Seen from above, the dark has an edge, and the edge is the coast. On Nyepi night ${district(5171).name} stood at <span class="dyn">${pct(district(5171).ratio)}</span> of its reference and ${district(5103).name} at <span class="dyn">${pct(district(5103).ratio)}</span>. Across the Lombok Strait, ${district(5271).name} stood at <span class="dyn">${pct(district(5271).ratio)}</span> and ${district(5201).name} at <span class="dyn">${pct(district(5201).ratio)}</span>. Across the Bali Strait, ${district(3510).name} read ${pct(district(3510).ratio)}, but only ${pct(district(3510).coverage)} of its light was seen, too little to count. These district figures use the plain reference; the viewing angle is not matched in them.</p>

<div class="card">
  <div class="triptych">
    ${[[nyepiK, "Nyepi night"], [afterK, "The night after"], [laterK, "Ten nights later (a reference night)"]].map(([k, label]) => html`<div>
      <h4>${day(k)}</h4><p class="sub">${label}</p>
      ${resize(nightMap(k, "nyepi"))}
      <p>Bali: <strong>${F.light[k] === null ? "not seen" : pct(F.light[k])}</strong> of its reference light. ${F.raw.seen[k].toLocaleString("en")} of ${F.raw.cells.toLocaleString("en")} cells seen.</p>
    </div>`)}
  </div>
  ${classLegend}
  <p class="fine" style="margin-top:0.6rem;">Banyuwangi on the left, Bali in the middle, Lombok on the right. The three maps move together: zoom or drag one and the others follow. Each lit cell is coloured by its light that night over its own reference. A cell is about 460 m across and the sensor's view is wider, so read the pattern, not single cells.</p>
</div>
</section>

<section class="part">
<p class="kicker">3 · The shape of the silence</p>

## Everything fell to the same floor

<p>Sort Bali's cells by how bright they usually are and the percentages look like a finding: the brightest 1% gave <span class="dyn">${show(S.brightness[3].light[K], 1)}</span> of their reference light, the dimmer half <span class="dyn">${show(S.brightness[0].light[K])}</span>. It is arithmetic. In radiance, every group ended at about the same level: <span class="dyn">${S.brightness.map((b) => b.mean_nw[K].toFixed(1)).join(", ")}</span> nW from dimmest to brightest, down from <span class="dyn">${S.brightness.map((b) => b.reference_mean_nw.toFixed(0)).join(", ")}</span>. A cell that starts at ${S.brightness[3].reference_mean_nw.toFixed(0)} and one that starts at ${S.brightness[0].reference_mean_nw.toFixed(0)} both arrive near 1, and 1 is close to the least the product is designed to detect. So the honest reading is that Bali's light fell to the floor of the measurement on every group of cells seen, and the ${show(F.light[K], 1)} is nearer a ceiling than a measurement.</p>

```js
const bands = S.brightness.map((b) => ({name: b.name, range: b.nw[1] === null ? `over ${b.nw[0]}` : `${b.nw[0]} to ${b.nw[1]}`, value: 100 * b.light[K], seen: b.seen[K], cells: b.cells}));
const bandChart = (width) => Plot.plot({
  width, height: 220, marginLeft: 150, marginRight: 60,
  x: {label: "% of reference light on Nyepi night", domain: [0, 25], grid: true}, y: {label: null, domain: bands.map((b) => b.name)},
  marks: [Plot.barX(bands, {y: "name", x: "value", fill: brbg[0]}),
          Plot.text(bands, {y: "name", x: "value", text: (b) => `${b.value.toFixed(1)}%`, dx: 6, textAnchor: "start", fontSize: 11}),
          Plot.tip(bands, Plot.pointer({y: "name", x: "value", title: (b) => `${b.name}: cells usually at ${b.range} nW cm-2 sr-1\n${b.value.toFixed(1)}% of reference light\n${b.seen.toLocaleString("en")} of ${b.cells.toLocaleString("en")} cells seen`}))]
});
const rows = units.code.map((code) => ({code, ...district(code)})).filter((r) => r.ratio !== null && r.coverage >= 0.3 && r.cells >= 20).sort((a, b) => a.ratio - b.ratio);
const districtChart = (width) => Plot.plot({
  width, height: 26 * rows.length + 50, marginLeft: 130, marginRight: 60,
  x: {label: "% of reference light on Nyepi night", grid: true}, y: {label: null, domain: rows.map((r) => r.name)},
  marks: [Plot.ruleX([100], {stroke: "#898781"}),
          Plot.barX(rows, {y: "name", x: (r) => 100 * r.ratio, fill: (r) => (Math.floor(r.code / 100) === 51 ? brbg[0] : "#5ab4ac")}),
          Plot.text(rows, {y: "name", x: (r) => 100 * r.ratio, text: (r) => `${(100 * r.ratio).toFixed(0)}%`, dx: 6, textAnchor: "start", fontSize: 11}),
          Plot.tip(rows, Plot.pointerY({y: "name", x: (r) => 100 * r.ratio, title: (r) => `${r.name}${Math.floor(r.code / 100) === 51 ? " (Bali)" : " (neighbour)"}\n${(100 * r.ratio).toFixed(1)}% of its reference light on Nyepi night\n${(100 * r.coverage).toFixed(0)}% of its light seen, ${r.cells.toLocaleString("en")} lit cells`}))]
});
```

<div class="grid grid-cols-2" style="gap:1.1rem; grid-auto-rows:auto;">
  <div class="card">
    <h3>Bali's cells by how bright they usually are</h3>
    <p class="fine">The summed light of each group on Nyepi night over its summed reference, on the cells seen. The differences between the bars restate where each group started, not how far it fell. The brightest group is ${S.brightness[3].seen[K]} cells.</p>
    ${resize(bandChart)}
  </div>
  <div class="card">
    <h3>District by district</h3>
    <p class="fine">Districts of Bali in brown, their neighbours in teal. Only districts with at least 30% of their reference light seen that night and at least 20 lit cells are shown.</p>
    ${resize(districtChart)}
  </div>
</div>
</section>

<section class="part">
<p class="kicker">4 · What stayed lit, and what stayed invisible</p>

## A few bright cells, and two lost years

<p>Not everything went dark. The brightest cells on Bali that night are listed below with their positions. This page does not say what stands at each: that needs a map and local knowledge, and has not been checked. And the satellite's view of Nyepi is a matter of luck. It falls in the wet season: on Nyepi night 2024 and 2025 the share of Bali's cells with any reading rounds to 0%.</p>

<div class="tiles" style="margin-bottom:1.1rem;">
  <div class="card"><div class="tile-value">${F.raw.seen[K].toLocaleString("en")} of ${F.raw.cells.toLocaleString("en")}</div><div class="tile-label">Bali's lit cells with a usable reading on Nyepi night 2026.</div></div>
  <div class="card"><div class="tile-value">0 of 2</div><div class="tile-label">Earlier years that could be measured. On Nyepi night 2024 (11 March) and 2025 (29 March) the share of Bali's cells with a reading rounds to 0%.</div></div>
  <div class="card"><div class="tile-value">${meta.reference.nights} nights</div><div class="tile-label">Make up the reference, ${refDates}: the first clear nights after Nyepi, and a week after Eid al-Fitr. The nights before Nyepi were mostly under cloud.</div></div>
  <div class="card"><div class="tile-value">Poor quality</div><div class="tile-label">Is how the product marks most of Bali's readings that night. With only the readings it calls high quality, about one cell in twenty is left, and those cells alone read about a fifth of their reference, not under a tenth. The headline depends on admitting the poor-quality readings.</div></div>
</div>

<div class="card">
  <h3>The brightest cells on Bali on Nyepi night</h3>
  ${Inputs.table(S.brightest.cells.map((c) => ({District: names.get(c.district) ?? c.district, Longitude: c.lon, Latitude: c.lat, "Radiance that night": c.radiance, "Its reference": c.reference, "% of reference": 100 * c.radiance / c.reference})),
    {format: {Longitude: (v) => v.toFixed(4), Latitude: (v) => v.toFixed(4), "Radiance that night": (v) => v.toFixed(1), "Its reference": (v) => v.toFixed(1), "% of reference": (v) => v.toFixed(0)}, select: false, rows: 12})}
  <p class="fine" style="margin-top:0.6rem;">Radiance in nW cm-2 sr-1. A cell brighter than its reference on the night the island went dark is worth a visit; it can also be a fire, moonlit cloud that the product missed, or a single bad reading.</p>
</div>
</section>

<section class="part">
<p class="kicker">Every night, place by place</p>

## Step through the nights, district by district

<p>The sections above tell one story. This map is for looking yourself. Move the slider to a night, click a district to open it and move the map to it, then click one of its sub-districts. The text under the map follows what is open: its light that night against its reference, how much of it was seen, where it stands among its neighbours, and its own nights.</p>

```js
const nyepiUnits = await files["units.json"].json();
display(nightExplorer({
  meta, units: nyepiUnits, lon, lat, colours, provinces: provinces.features, districts: districtOutlines.features,
  focus: {key: "nyepi-explorer", bounds: FOCUS.bounds}, start: K, scope: "Banyuwangi, Bali and Lombok", legend: classLegend.cloneNode(true),
  subOutlines: (p) => { const f = national[`outlines/subdistrict/${p}.geojson`]; return f ? f.json() : Promise.resolve(null); },
  levelAt: (k) => { const level = new Uint8Array(N); for (let i = 0; i < N; i++) level[i] = raw[k * N + i] & 7; return level; },
  noteAt: (k) => `The night that began on the evening of ${day(k)}${k === K ? ", Nyepi night" : ""}${meta.reference.dates.includes(meta.dates[k]) ? ", one of the two reference nights" : ""}. `
    + `Cells are shown against their own reference. ${pct(meta.seen_share_by_night[k])} of the cells of the three areas were seen; on Bali, ${F.raw.seen[k].toLocaleString("en")} of ${F.raw.cells.toLocaleString("en")}.`
}));
```

</section>

<p class="fine" style="max-width:none;">Source: NASA Black Marble daily, VNP46A2, Collection 2, the moonlight-corrected radiance, readings flagged high quality or poor quality, over the ${N.toLocaleString("en")} lit cells of Banyuwangi, Bali and Lombok (${meta.cells.with_reference.toLocaleString("en")} with a reference). A file dated D is the night that begins on the evening of local date D. Nyepi 2026 (19 March) and Eid al-Fitr 2026 (21 to 22 March): the joint ministerial decree on national holidays for 2026, published by the State Secretariat (setneg.go.id). The 2024 date is in the 2024 decree (setkab.go.id); the 2025 date was not traced to its decree. View angles: the sensor zenith layer of VNP46A1 (the file for 18 March 2026 is missing from the archive; that night takes its angle from 2018, 171 cycles of 16 nights earlier, which was checked to agree within half a degree on the other nights). The product's stated detection-limit targets are 3.0 nW (threshold) to 0.25 nW (goal), from the product user guide. This page measures dimming and says nothing about electricity.</p>

<p class="fine" style="max-width:none; margin-top:1.2rem;"><a href="./">\&larr; Back to the main dashboard</a> · <a href="https://github.com/bennyistanto/nightlights-explorer" target="_blank" rel="noopener">Code and method on GitHub</a></p>
