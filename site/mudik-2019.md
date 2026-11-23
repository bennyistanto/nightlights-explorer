---
title: "Mudik 2019: looking for an exodus in the dark"
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
  <p class="brand"><a href="./">Nightlights Explorer</a> · Case study</p>
  <h1><svg class="logo" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10.5" fill="#10151c"/><path d="M12 1.5a10.500 10.500 0 0 1 0 21 13.500 13.500 0 0 0 0-21Z" fill="#2a3644"/><circle cx="8.300" cy="9.400" r="3" fill="#ffd76a" opacity=".22"/><circle cx="8.300" cy="9.400" r="1.500" fill="#ffd76a"/><circle cx="12.700" cy="13.700" r="1.100" fill="#ffd76a"/><circle cx="7.300" cy="14.900" r=".800" fill="#f2b24a"/><circle cx="11.300" cy="6.700" r=".600" fill="#f2b24a"/><circle cx="10.200" cy="17.600" r=".600" fill="#f2b24a"/></svg>Mudik 2019: looking for an exodus in the dark</h1>
  <p class="lede">Every year before Eid al-Fitr a great many people leave Jakarta and its neighbouring cities for their home towns. In 2019 Eid fell on Wednesday 5 June. If a city empties, does it dim? This page looks for the exodus in six weeks of nightly light. It does not show where it was expected, in the cities. On the roads, one night stands out: the Sunday of the return.</p>
</header>

<div class="notice">
  <p><strong>What this page can and cannot say.</strong> The cities give a negative result: a rhythm of the satellite's own is large enough to hide whatever Eid does to Jakarta's light. On the roads one night stands out, the Sunday of the return (part 4). None of it has been checked against traffic counts or any other record on the ground. The reference nights are 15 to 27 May, inside Ramadan, which has night-time habits of its own.</p>
</div>

```js
import {files} from "./data/events/mudik2019/files.js";
import {files as national} from "./data/files.js";
import {loadTyped} from "./components/load.js";
import {drawMap} from "./components/map.js";
import {NO_VALUE} from "./components/palette.js";
import * as d3 from "npm:d3";
```

```js
const meta = await files["meta.json"].json();
const units = (await files["units.json"].json()).district;
const S = meta.story, F = S.focus, M = S.matched;
const D = meta.dates.length;
const dates = meta.dates.map((s) => new Date(`${s}T00:00:00Z`));
const night = (iso) => meta.dates.indexOf(iso);
const K = night(meta.marks[0].date);
const day = (k, long = true) => dates[k].toLocaleDateString("en-GB", {day: "numeric", month: long ? "long" : "short", timeZone: "UTC"});
const pct = (v, digits = 0) => `${(100 * v).toFixed(digits)}%`;
const districtGeo = await national["outlines/district.geojson"].json();
const provinces = await national["outlines/province.geojson"].json();
const names = new Map(districtGeo.features.map((f) => [f.properties.code, f.properties.name]));
const brbg = d3.schemeBrBG[7];
const MIN_SEEN = 2000; // of the cities' cells, for a night to count
// Jakarta and its neighbouring cities, night by night: null where too little was seen
const x = F.light.map((v, k) => (v !== null && F.raw.seen[k] >= MIN_SEEN ? v : null));
const good = x.map((v, k) => ({k, date: dates[k], value: v})).filter((p) => p.value !== null);
const spread = d3.deviation(good, (p) => Math.log(p.value));
// how alike are two nights a given number of nights apart?
const lags = d3.range(1, 22).map((lag) => {
  const pairs = d3.range(lag, D).filter((k) => x[k] !== null && x[k - lag] !== null).map((k) => [Math.log(x[k - lag]), Math.log(x[k])]);
  const a = pairs.map((p) => p[0]), b = pairs.map((p) => p[1]), ma = d3.mean(a), mb = d3.mean(b);
  const r = pairs.length < 6 ? null : d3.sum(pairs, (p) => (p[0] - ma) * (p[1] - mb)) / Math.sqrt(d3.sum(a, (v) => (v - ma) ** 2) * d3.sum(b, (v) => (v - mb) ** 2));
  return {lag, r, pairs: pairs.length};
}).filter((d) => d.r !== null);
const lagR = (n) => lags.find((d) => d.lag === n)?.r;
// nights of the same viewing angle are 16 nights apart: compare each Eid night with those partners
const EID = [K, K + 1].filter((k) => x[k] !== null); // Eid was 5 and 6 June; 7 June was collective leave
const isEid = (k) => k >= K && k <= K + 1;
const pairs = [16].flatMap((lag) => d3.range(0, D - lag).filter((k) => x[k] !== null && x[k + lag] !== null).map((k) => {
  const a = k, b = k + lag;
  if (isEid(a) === isEid(b)) return {kind: "Two ordinary nights", lag, a, b, ratio: x[b] / x[a]};
  return isEid(b) ? {kind: "An Eid night over an ordinary one", lag, a, b, ratio: x[b] / x[a]} : {kind: "An Eid night over an ordinary one", lag, a: b, b: a, ratio: x[a] / x[b]};
})).filter((p) => !(p.kind === "Two ordinary nights" && (isEid(p.a) || isEid(p.b))));
const eidPairs = pairs.filter((p) => p.kind !== "Two ordinary nights"), plainPairs = pairs.filter((p) => p.kind === "Two ordinary nights");
const eidMedian = d3.median(eidPairs, (p) => p.ratio);
const plainScatter = d3.median(plainPairs, (p) => Math.abs(Math.log(p.ratio)));
const plainMedian = d3.median(plainPairs, (p) => p.ratio);
// every night against reference nights seen from within M.tolerance degrees of the same angle; a night needs 1,000 cells
const likeNights = d3.range(D).filter((k) => M.focus.light[k] !== null && M.focus.cells[k] >= 1000).map((k) => ({k, date: dates[k], value: M.focus.light[k], cells: M.focus.cells[k], zenith: M.zenith[k], ref: meta.reference.dates.includes(meta.dates[k])}));
const likeEid = likeNights.filter((p) => isEid(p.k)), likeOther = likeNights.filter((p) => !isEid(p.k));
// the districts on Eid night, and how well "where people leave" and "where they go" separate on every night
const ORIGIN = new Set(F.districts), DEST = new Set([3205, 3206, 3207, 3208, 3210, 3301, 3302, 3303, 3304, 3305, 3306, 3307, 3326, 3327, 3328, 3329]);
const seenWell = (u, k) => units.ratio[u][k] !== null && units.coverage[u][k] >= 0.5;
const separation = d3.range(D).map((k) => {
  const a = units.code.map((c, u) => (ORIGIN.has(c) && seenWell(u, k) ? units.ratio[u][k] : null)).filter((v) => v !== null);
  const b = units.code.map((c, u) => (DEST.has(c) && seenWell(u, k) ? units.ratio[u][k] : null)).filter((v) => v !== null);
  return a.length < 5 || b.length < 5 ? null : {k, date: dates[k], share: d3.mean(a.flatMap((p) => b.map((q) => (q > p ? 1 : 0)))), eid: k >= K - 1 && k <= K + 5};
}).filter(Boolean);
const ordinary = separation.filter((d) => !d.eid);
const cleanOrdinary = ordinary.filter((d) => d.share >= 0.95).length;
```

<section class="part">
<p class="kicker">1 · What the satellite adds of its own</p>

## A city that seems to breathe

<p>Measured night by night, the light of Jakarta, Bekasi, Depok and Tangerang rises and falls by about <span class="dyn">${pct(Math.exp(spread) - 1)}</span>. Much of it follows the viewing angle, not the city. The swings come back every five to six nights, and again at eleven and at sixteen: two nights eleven apart resemble each other closely (correlation <span class="dyn">${lagR(11).toFixed(2)}</span>), two nights eight apart are opposites (<span class="dyn">${lagR(8).toFixed(2)}</span>). That is the rhythm of the satellite. Its viewing angle repeats every sixteen nights and swings from overhead to the side and back three times in between: over Jakarta in these six weeks it ran from <span class="dyn">${d3.min(M.zenith.filter((z) => z !== null)).toFixed(0)}</span> to <span class="dyn">${d3.max(M.zenith.filter((z) => z !== null)).toFixed(0)} degrees</span> from overhead (hover a point). A city looked at straight down and from the side is not the same brightness.</p>

```js
const lightChart = (width) => Plot.plot({
  width, height: 280, marginLeft: 48, marginRight: 20,
  x: {label: null}, y: {label: "% of the reference nights", domain: [0, 160], grid: true},
  marks: [
    Plot.ruleY([100], {stroke: "#898781"}),
    Plot.rectY([{a: dates[K], b: dates[K + 1]}], {x1: "a", x2: "b", y1: 0, y2: 160, fill: "#c53030", fillOpacity: 0.08}),
    Plot.text([dates[K]], {x: (d) => d, y: 160, text: ["Eid, 5 and 6 June"], dy: 8, dx: 4, textAnchor: "start", fontSize: 10, fill: "#c53030"}),
    Plot.lineY(good, {x: "date", y: (p) => 100 * p.value, stroke: "#b5b3aa", strokeWidth: 1.2}),
    Plot.dot(good, {x: "date", y: (p) => 100 * p.value, r: 4, fill: (p) => (isEid(p.k) ? "#c53030" : "#0b0b0b")}),
    Plot.tip(good, Plot.pointerX({x: "date", y: (p) => 100 * p.value, title: (p) => `${day(p.k)}\n${(100 * p.value).toFixed(0)}% of the reference nights\n${F.raw.seen[p.k].toLocaleString("en")} of ${F.raw.cells.toLocaleString("en")} cells seen\nseen from ${M.zenith[p.k] === null ? "an unknown angle" : M.zenith[p.k].toFixed(0) + " degrees"}`}))
  ]
});
const lagChart = (width) => Plot.plot({
  width, height: 280, marginLeft: 48,
  x: {label: "Nights apart", tickFormat: (d) => String(d)}, y: {label: "How alike two nights are (correlation)", domain: [-1, 1], grid: true},
  marks: [Plot.ruleY([0]), Plot.barY(lags, {x: "lag", y: "r", fill: (d) => (d.r > 0 ? brbg[5] : brbg[1])}),
          Plot.tip(lags, Plot.pointerX({x: "lag", y: "r", title: (d) => `${d.lag} nights apart\ncorrelation ${d.r.toFixed(2)} over ${d.pairs} pairs of nights`}))]
});
```

<div class="grid grid-cols-2" style="gap:1.1rem; grid-auto-rows:auto;">
  <div class="card">
    <h3>The cities' light, night by night</h3>
    <p class="fine">Summed light of the cells seen over their summed reference, on the ${good.length} of ${D} nights with at least ${MIN_SEEN.toLocaleString("en")} of the ${F.raw.cells.toLocaleString("en")} cells seen. Red points are the nights of Eid with enough cells seen (${EID.length} of 2).</p>
    ${resize(lightChart)}
  </div>
  <div class="card">
    <h3>The swings repeat</h3>
    <p class="fine">Each bar compares all pairs of nights that many nights apart. Teal: they move together. Brown: when one is high the other is low.</p>
    ${resize(lagChart)}
  </div>
</div>
</section>

<section class="part">
<p class="kicker">2 · The question</p>

## The exodus that barely shows

<p>The fair comparison is between nights seen from the same angle, sixteen nights apart. Set each Eid night against its partners and it comes out at <span class="dyn">${pct(d3.min(eidPairs, (p) => p.ratio))}</span> to <span class="dyn">${pct(d3.max(eidPairs, (p) => p.ratio))}</span> of them, across ${eidPairs.length} comparisons. Now do the same for pairs in which neither night is Eid: the later night comes out at <span class="dyn">${pct(d3.min(plainPairs, (p) => p.ratio))}</span> to <span class="dyn">${pct(d3.max(plainPairs, (p) => p.ratio))}</span> of the earlier, median <span class="dyn">${pct(plainMedian)}</span>, across ${plainPairs.length}. The Eid nights sit inside that spread. A second way uses more nights: measure every cell only against reference nights seen from within ${M.tolerance} degrees of the same angle. The Eid nights then read <span class="dyn">${likeEid.map((p) => pct(p.value)).join(", ")}</span>; the other nights run from <span class="dyn">${pct(d3.min(likeOther, (p) => p.value))}</span> to <span class="dyn">${pct(d3.max(likeOther, (p) => p.value))}</span>. Whatever Eid did to the light of Jakarta and its neighbours, this data cannot tell it from two ordinary nights.</p>

```js
const pairChart = (width) => Plot.plot({
  width, height: 190, marginLeft: Math.min(220, Math.round(0.42 * width)), marginRight: 30,
  x: {label: "A night as % of the night 16 before or after it", domain: [70, 130], grid: true}, y: {label: null, domain: ["An Eid night over an ordinary one", "Two ordinary nights"]},
  marks: [Plot.ruleX([100], {stroke: "#898781"}),
          Plot.dot(pairs, {y: "kind", x: (p) => 100 * p.ratio, r: 5, fill: (p) => (p.kind === "Two ordinary nights" ? "#9aa3ad" : "#c53030"), fillOpacity: 0.85, stroke: "#0b0b0b", strokeWidth: 0.5}),
          Plot.tip(pairs, Plot.pointer({y: "kind", x: (p) => 100 * p.ratio, title: (p) => `${day(p.b, false)} over ${day(p.a, false)} (${p.lag} nights apart): ${(100 * p.ratio).toFixed(0)}%`}))]
});
```

<div class="card">
  <h3>Eid nights against nights of the same viewing angle</h3>
  ${resize(pairChart)}
  <p class="fine" style="margin-top:0.6rem;">Each point is one pair of nights 16 apart, both with at least ${MIN_SEEN.toLocaleString("en")} cells seen. Red: one of the two is an Eid night (5 or 6 June), shown as the Eid night over the other. Grey: neither is, shown as the later night over the earlier.</p>
</div>
</section>

<section class="part">
<p class="kicker">3 · A warning from the data</p>

## A map that looks like a finding

<p>Rank the districts by their light on Eid night and the result is almost too neat. Every city people leave sits at the bottom; every home district that was seen that night sits at the top. It looks like the exodus drawn in light. It is not evidence. A split as clean, with the home district the brighter in at least 95% of pairs, appears on <span class="dyn">${cleanOrdinary} of ${ordinary.length}</span> ordinary nights in these six weeks. Why was not measured here; the two groups lie at opposite ends of the map, far enough apart to be seen through different air and from a slightly different angle. A pattern that fits the story on the night of the story has to be checked on all the other nights too.</p>

```js
const eidRows = units.code.map((c, u) => ({code: c, name: names.get(c) ?? String(c), ratio: units.ratio[u][K], group: ORIGIN.has(c) ? "Where people leave" : DEST.has(c) ? "Where many go" : null, ok: seenWell(u, K)}))
  .filter((r) => r.group && r.ok).sort((a, b) => a.ratio - b.ratio);
const rankChart = (width) => Plot.plot({
  width, height: 22 * eidRows.length + 50, marginLeft: Math.min(210, Math.round(0.45 * width)), marginRight: 50,
  x: {label: "% of reference light on Eid night", grid: true}, y: {label: null, domain: eidRows.map((r) => r.name)},
  marks: [Plot.ruleX([100], {stroke: "#898781"}),
          Plot.barX(eidRows, {y: "name", x: (r) => 100 * r.ratio, fill: (r) => (r.group === "Where people leave" ? brbg[0] : brbg[5])}),
          Plot.text(eidRows, {y: "name", x: (r) => 100 * r.ratio, text: (r) => `${(100 * r.ratio).toFixed(0)}%`, dx: 6, textAnchor: "start", fontSize: 11}),
          Plot.tip(eidRows, Plot.pointerY({y: "name", x: (r) => 100 * r.ratio, title: (r) => `${r.name}\n${r.group}\n${(100 * r.ratio).toFixed(0)}% of its reference light on Eid night`}))]
});
const sepChart = (width) => Plot.plot({
  width, height: 260, marginLeft: 48,
  x: {label: null}, y: {label: "Share of pairs in which the home district is the brighter", domain: [0, 1], grid: true, tickFormat: "%"},
  marks: [Plot.ruleY([0.5], {stroke: "#898781", strokeDasharray: "3,3"}),
          Plot.dot(separation, {x: "date", y: "share", r: 5, fill: (d) => (d.k === K ? "#c53030" : "#0b0b0b")}),
          Plot.tip(separation, Plot.pointerX({x: "date", y: "share", title: (d) => `${day(d.k)}\nhome district brighter in ${(100 * d.share).toFixed(0)}% of pairs`}))]
});
```

<div class="grid grid-cols-2" style="gap:1.1rem; grid-auto-rows:auto;">
  <div class="card">
    <h3>Districts on Eid night</h3>
    <div class="keys"><span><span class="swatch" style="background:#8c510a;border-radius:2px;"></span>Where people leave</span><span><span class="swatch" style="background:#5ab4ac;border-radius:2px;"></span>Where many go</span></div>
    ${resize(rankChart)}
  </div>
  <div class="card">
    <h3>The same split, on every night</h3>
    <p class="fine">For each night, every city people leave is paired with every home district. At 100% the home district is the brighter in every pair; at 50% there is no split. The red point is Eid night. Only districts with half of their reference light seen are used.</p>
    ${resize(sepChart)}
  </div>
</div>
</section>

<section class="part">
<p class="kicker">4 · Where it does show</p>

## One night stands out: the Sunday of the return

```js
const road = await FileAttachment("./data/events/mudik2019/road.json").json();
// toll roads and national main roads from OpenStreetMap, as mapped on the day they were fetched (not as in 2019)
const roads = await FileAttachment("./data/events/mudik2019/roads.json").json();
const ROAD_LINES = [{coords: roads.trunk, colour: "255, 255, 255", width: 0.8, opacity: 0.8, dash: [3, 3]},
                    {coords: roads.motorway, colour: "102, 224, 255", width: 1.4, opacity: 0.95}];
const SV = (night, partner) => road.same_view.find((d) => d.night === night && d.partner === partner);
const roadLon = await loadTyped("mudik-road-lon", FileAttachment("./data/events/mudik2019/road_lon.f32.gz"), Float32Array);
const roadLat = await loadTyped("mudik-road-lat", FileAttachment("./data/events/mudik2019/road_lat.f32.gz"), Float32Array);
const roadClass = await loadTyped("mudik-road-class", FileAttachment("./data/events/mudik2019/road_class.u8.gz"), Uint8Array);
const RN = roadLon.length;
// ColorBrewer: oranges (from PuOr) for more light than the reference nights, the palest the strongest; Blues for less
const puor = d3.schemePuOr[7];
const rgb = (hex) => [1, 3, 5].map((k) => parseInt(hex.slice(k, k + 2), 16)).join(", ");
const ROAD_CLASSES = [
  {colour: NO_VALUE, label: "Not seen on two nights"}, {colour: d3.schemeBlues[5][2], label: "1.5 nW or more dimmer"}, {colour: d3.schemeBlues[5][3], label: "0.5 to 1.5 dimmer"},
  {colour: null, label: "Within 0.5 (not drawn)"}, {colour: puor[6], label: "0.5 to 1.5 brighter"}, {colour: puor[5], label: "1.5 to 3 brighter"}, {colour: puor[4], label: "3 nW or more brighter"}
];
const roadColours = ROAD_CLASSES.map((c) => (c.colour ? rgb(c.colour) : null));
const java = districtGeo.features.filter((f) => [31, 32, 33, 34, 35, 36].includes(Math.floor(f.properties.code / 100)))
  .map((feature) => ({feature, id: null, state: null, weak: false, fill: "transparent", text: ""}));
const ROAD_FOCUS = {key: "mudik-java", bounds: [[105.2, -8.75], [114.6, -5.85]]};
const roadMap = (w, lines = null) => (width) => drawMap({width, land: provinces.features, units: java, context: [], selected: [], lines,
  lights: {lon: roadLon, lat: roadLat, level: roadClass.subarray(w * RN, (w + 1) * RN), colours: roadColours}, focus: ROAD_FOCUS, onPick: () => {}});
const WINDOW_LABELS = road.windows.map((w) => w.label);
const span = (w) => `${new Date(`${road.windows[w].first}T00:00:00Z`).toLocaleDateString("en-GB", {day: "numeric", month: "short", timeZone: "UTC"})} to ${new Date(`${road.windows[w].last}T00:00:00Z`).toLocaleDateString("en-GB", {day: "numeric", month: "long", timeZone: "UTC"})}`;
const roadNights = road.nights.filter((n) => n.excess !== null).map((n) => ({...n, when: new Date(`${n.date}T00:00:00Z`), net: n.excess - n.background_excess}));
const netOn = (iso) => roadNights.find((n) => n.date === iso)?.net;
const refNights = roadNights.filter((n) => n.date <= meta.reference.last);
const lateNights = roadNights.filter((n) => n.date >= "2019-06-12");
const signed = (v) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}`;
```

<p>Stop asking how bright the cities are and ask instead which dark places lit up. Take every land cell of Java, lit or not, from Banten to Banyuwangi, and subtract its light on the reference nights. On the nights of the return a line appears from Jakarta east along the north coast as far as Semarang, with a branch towards Bandung. To measure it, the line was traced on those nights, between 107.3 and 110.6 E where it is a line: <span class="dyn">${road.line.cells.toLocaleString("en")}</span> land cells that are near-dark on the reference nights (under 3 nW) and at least 1.5 nW brighter on 8 to 11 June. Cells chosen for having brightened will of course read brighter on those nights, and a dim cell's light also swings with the satellite's viewing angle. So the test that counts is a night against another night seen from the same angle, sixteen nights away, with the dark countryside around the line subtracted.</p>

<p>By that test, on <span class="dyn">Sunday 9 June</span> the line was <span class="dyn">${signed(SV("2019-06-09", "2019-05-24").net)} nW</span> brighter than on 24 May and <span class="dyn">${signed(SV("2019-06-09", "2019-06-25").net)} nW</span> brighter than on 25 June, on cells whose usual light is about ${road.line.reference_mean.toFixed(1)} nW. Monday 10 June stood <span class="dyn">${signed(SV("2019-06-10", "2019-05-25").net)} nW</span> above 25 May. It is not an effect of the choosing either: cells picked on 10 and 11 June alone, nights that say nothing about the 9th, read <span class="dyn">${signed(road.held_out.net)} nW</span> above the countryside on 9 June. The nights of leaving show nothing of the kind. Against their same-angle nights in mid June, 29, 30 and 31 May read <span class="dyn">${signed(SV("2019-05-29", "2019-06-14").net)}</span>, <span class="dyn">${signed(SV("2019-05-30", "2019-06-15").net)}</span> and <span class="dyn">${signed(SV("2019-05-31", "2019-06-16").net)} nW</span>: no brighter. And the last nights before Eid, 1 to 4 June, were under cloud.</p>

```js
const roadWindow = view(Inputs.radio([0, 1, 2, 3], {value: 2, label: "Nights", format: (w) => `${WINDOW_LABELS[w]}: ${span(w)}`}));
const showRoads = view(Inputs.toggle({label: "Show toll roads and main roads on the map", value: false}));
```

<div class="card">
  <h3>${WINDOW_LABELS[roadWindow]}, ${span(roadWindow)}: light against the reference nights</h3>
  ${resize(roadMap(roadWindow, showRoads ? ROAD_LINES : null))}
</div>
<div class="keys" style="margin-top:0.6rem;">${ROAD_CLASSES.filter((c) => c.colour).map((c) => html`<span><span class="swatch" style=${`background:${c.colour};border-radius:2px;`}></span>${c.label}</span>`)}<span>Within 0.5 nW: not drawn</span>${showRoads ? html`<span><span class="key-line" style="border-top:2px solid rgb(102, 224, 255)"></span>Toll road</span><span><span class="key-line" style="border-top:2px dashed #ffffff; background:#1c242e;"></span>National main road</span>` : ""}</div>
<p class="fine" style="max-width:none; margin-top:0.4rem;">Switch between the four groups of nights above; the map keeps its place. Every land cell is compared, not only the lit ones; the sea is left out, and boats and platforms with it: its mean light over the nights of the window it was seen, minus its mean over the reference nights, in nW per cm² per sr. A cell needs two nights in the window; ${pct(road.windows[roadWindow].seen)} of the land had them in the nights shown, and grey is not seen, which is not the same as dark. Sharp straight edges in the east are where the product marked a block of cells unusable, not something on the ground. The speckle over Jakarta and Bandung is the viewing rhythm of part 1, not traffic. On the leaving nights much of the countryside reads 0.5 to 1.5 nW brighter: that is mostly the viewing angle of those nights, not traffic. The nights of 1 to 4 June, the last before Eid, were almost wholly under cloud and cannot be shown.</p>

```js
const roadChart = (width) => Plot.plot({
  width, height: 280, marginLeft: 52, marginRight: 20,
  x: {label: null}, y: {label: "Light above the dark countryside, nW per cm² per sr", grid: true},
  marks: [
    Plot.ruleY([0], {stroke: "#898781"}),
    Plot.rectY([{a: dates[K], b: dates[K + 1]}], {x1: "a", x2: "b", y1: -0.5, y2: 5, fill: "#c53030", fillOpacity: 0.08}),
    Plot.text([dates[K]], {x: (d) => d, y: 5, text: ["Eid, 5 and 6 June"], dy: 8, dx: 4, textAnchor: "start", fontSize: 10, fill: "#c53030"}),
    Plot.rectY([{a: dates[0], b: dates[night(meta.reference.last)]}], {x1: "a", x2: "b", y1: -0.5, y2: 5, fill: "#898781", fillOpacity: 0.08}),
    Plot.text([dates[0]], {x: (d) => d, y: 5, text: ["Reference nights"], dy: 8, dx: 4, textAnchor: "start", fontSize: 10, fill: "#52514e"}),
    Plot.ruleX(roadNights, {x: "when", y1: 0, y2: "net", stroke: "#b35806", strokeWidth: 2}),
    Plot.dot(roadNights, {x: "when", y: "net", r: 4.5, fill: (n) => (n.picked ? "white" : "#b35806"), stroke: "#b35806", strokeWidth: 1.5}),
    Plot.tip(roadNights, Plot.pointerX({x: "when", y: "net", title: (n) => `${n.when.toLocaleDateString("en-GB", {weekday: "long", day: "numeric", month: "long", timeZone: "UTC"})}\nline ${signed(n.excess)} nW, dark countryside ${signed(n.background_excess)} nW over their reference\n${pct(n.seen)} of the line's cells seen${n.picked ? "\nThis night helped pick the cells" : ""}`}))
  ]
});
```

<div class="card" style="margin-top:1.1rem;">
  <h3>The line, night by night</h3>
  <p class="fine">Mean light of the line's cells over their reference, minus the same for ${road.line.background_cells.toLocaleString("en")} dark cells that did not change on the return. Nights with under 30% of the line seen are left out. Hollow points are the three nights used to trace the line.</p>
  ${resize(roadChart)}
</div>

<p style="margin-top:1rem;">What can be said, then, is narrow and firm: across the north of Java, dark cells along the corridor to Semarang were several times brighter than usual at about 01:30 on the morning of Monday 10 June, the end of the Sunday of the return, and nothing like it shows on the nights of leaving. What it was is a guess. Traffic is ours, but the light could as well be lamps at rest areas and toll gates, and the towns along the way were somewhat brighter that night too. The roads on the map do not settle it: dim cells that flicker lie along main roads and the edges of towns on any group of nights. What sets the return apart is how many there were: <span class="dyn">${road.line.cells.toLocaleString("en")}</span> cells passed the test on the return nights, against <span class="dyn">${road.placebo.map((w) => w.cells.toLocaleString("en")).join(", ")}</span> in three ordinary windows of later June. The chart above is drawn against the reference nights, so its bars on the nights of leaving are mostly the viewing angle and the choosing of the cells; only the comparisons at one angle carry a claim. Where the line ends was decided by looking at the map. And the satellite sees who is on the road in the small hours, not the day's traffic.</p>
</section>

<section class="part">
<p class="kicker">5 · What it would take</p>

## What would settle the cities

<p>For the cities the negative result stands, and it says where the limit is. Matching the viewing angle halves the scatter over Lombok and Bali; over Jakarta it removes much less, and the cities' light still moves by about <span class="dyn">${pct(Math.exp(d3.deviation(likeOther, (p) => Math.log(p.value))) - 1)}</span> between ordinary nights seen alike. Something other than the angle is at work there: the side of the swath, the air, or the city itself, and this page cannot say which. To go further would need a year of nights, a reference outside Ramadan, and a second year to tell a holiday from a coincidence. None of that is done here.</p>

<div class="tiles">
  <div class="card"><div class="tile-value">${pct(Math.exp(spread) - 1)}</div><div class="tile-label">Typical night-to-night swing of the cities' light over these six weeks, Eid included.</div></div>
  <div class="card"><div class="tile-value">${pct(Math.exp(plainScatter) - 1)}</div><div class="tile-label">Typical gap between two ordinary nights of the same viewing angle, sixteen apart. Eid nights differ from their partners by no more than ordinary nights do.</div></div>
  <div class="card"><div class="tile-value">${good.length} of ${D}</div><div class="tile-label">Nights with enough of the cities seen to be counted. The other nights were lost to cloud or poor retrievals.</div></div>
  <div class="card"><div class="tile-value">1 year</div><div class="tile-label">Of Mudik looked at, 2019. One year cannot separate a holiday from a coincidence.</div></div>
</div>
</section>

<p class="fine" style="max-width:none;">Source: NASA Black Marble daily, VNP46A2, Collection 2, the moonlight-corrected radiance, high-quality retrievals only, tile h28v09. The cities people leave: the five municipalities of Jakarta, Kota Bekasi, Kota Depok, Kota Tangerang and Kota Tangerang Selatan (${F.raw.cells.toLocaleString("en")} lit cells). Home districts: sixteen districts of eastern West Java and western Central Java in the same tile; a choice made for this page, not a survey of where travellers go. A cell's reference is its median over the nights of ${day(0)} to ${day(night(meta.reference.last))}. Eid date: Government of Indonesia, announcement of 3 June 2019 (setkab.go.id). Roads: OpenStreetMap contributors (Open Database Licence), ways tagged motorway (toll roads) and trunk (national main roads), as mapped on ${roads.fetched.slice(0, 10)}; stretches opened after June 2019 are included. View angles: the sensor zenith layer of VNP46A1, 21 May to 5 June 2019; other nights take the angle of the night 16 before or after. A file dated D is the night that begins on the evening of local date D.</p>
