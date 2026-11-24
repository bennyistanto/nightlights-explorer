---
title: Nightlights Explorer
---

<style>
/* ---------- page ---------- */
.page-head {margin: 0.5rem 0 1.25rem;}
.page-head h1 {margin: 0 0 0.4rem; font-size: 2rem; line-height: 1.15; max-width: none; display: flex; align-items: center; gap: 0.6rem;}
.page-head h1 .logo {width: 32px; height: 32px; flex: none;}
.lede {margin: 0; max-width: none; color: #52514e; font-size: 1rem; line-height: 1.5;}
h2 {margin-top: 2rem;}

/* ---------- control panel: what, where, when ---------- */
.panel {background: var(--theme-background-alt, #fff); border: 1px solid #e1e0d9; border-radius: 12px; padding: 1.1rem 1.25rem; margin: 0 0 1.25rem; display: grid; gap: 1rem;}
.panel-row {display: grid; gap: 1rem 1.5rem; align-items: end;}
.panel-row > * {min-width: 0;}
.panel-row.what {grid-template-columns: auto minmax(180px, 1fr) minmax(180px, 1fr); align-items: end;}
@media (max-width: 760px) {.panel-row.what {grid-template-columns: 1fr;}}
.panel-row.where {grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); padding-top: 1rem; border-top: 1px solid #e1e0d9;}
.panel-row.when {grid-template-columns: auto auto minmax(160px, 1fr); align-items: center; padding-top: 1rem; border-top: 1px solid #e1e0d9;}
.field > label, .panel form > label {display: block; width: auto; margin: 0 0 0.35rem; padding: 0; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; color: #52514e;}
.panel form {display: block; margin: 0; width: auto; max-width: none; min-height: 0; --label-width: auto; --input-width: 100%;}
/* radios as a segmented control: the circle is hidden, the label is the button */
.panel form > div {display: flex; flex-wrap: wrap; gap: 0; width: auto;}
.panel form > div > label {position: relative; display: inline-flex; align-items: center; margin: 0; padding: 0.4rem 0.8rem; border: 1px solid #c3c2b7; border-left-width: 0; background: #fcfcfb; color: #0b0b0b; font-size: 0.9rem; line-height: 1.2; cursor: pointer; white-space: nowrap; user-select: none;}
.panel form > div > label:first-child {border-left-width: 1px; border-radius: 8px 0 0 8px;}
.panel form > div > label:last-child {border-radius: 0 8px 8px 0;}
.panel form > div > label > input[type=radio] {position: absolute; opacity: 0; width: 1px; height: 1px; margin: 0; pointer-events: none;}
.panel form > div > label:hover {background: #f0efec;}
.panel form > div > label:has(input:checked) {background: #0b0b0b; border-color: #0b0b0b; color: #fff;}
.panel form > div > label:has(input:focus-visible) {outline: 2px solid #2a78d6; outline-offset: 2px; z-index: 1;}
.panel select {width: 100%; max-width: 100%; padding: 0.42rem 0.6rem; font: inherit; font-size: 0.9rem; color: #0b0b0b; background: #fcfcfb; border: 1px solid #c3c2b7; border-radius: 8px;}
.panel select:disabled {color: #898781; background: #f0efec;}
.panel select:focus-visible {outline: 2px solid #2a78d6; outline-offset: 2px;}
.crumbs {display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.4rem; margin: 0; font-size: 0.95rem;}
.crumbs a {text-decoration: underline; cursor: pointer;}
.crumb-sep {color: #898781;}
.month-label {font-size: 1.35rem; font-weight: 600; width: 9.6rem; white-space: nowrap;}
.month-note {margin: 0; max-width: none; font-size: 0.85rem; color: #52514e; line-height: 1.45;}
.month-note strong {color: #7a4b00;}
.month-slider {display: flex; align-items: center;}
.month-slider input[type=range] {-webkit-appearance: none; appearance: none; width: 100%; height: 4px; margin: 0; padding: 0; background: #c3c2b7; border-radius: 2px; cursor: pointer;}
.month-slider input[type=range]::-webkit-slider-runnable-track {height: 4px; background: transparent;}
.month-slider input[type=range]::-moz-range-track {height: 4px; background: #c3c2b7; border-radius: 2px;}
.month-slider input[type=range]::-webkit-slider-thumb {-webkit-appearance: none; appearance: none; width: 16px; height: 16px; margin-top: -6px; border-radius: 50%; background: #0b0b0b; border: 2px solid #fcfcfb; box-shadow: 0 0 0 1px #0b0b0b;}
.month-slider input[type=range]::-moz-range-thumb {width: 12px; height: 12px; border-radius: 50%; background: #0b0b0b; border: 2px solid #fcfcfb; box-shadow: 0 0 0 1px #0b0b0b;}
.month-slider input[type=range]:focus-visible {outline: 2px solid #2a78d6; outline-offset: 6px;}
.steps {display: inline-flex;}
.steps .step {font: inherit; font-size: 1rem; line-height: 1; min-width: 2.1rem; padding: 0.35rem 0.5rem; border: 1px solid #c3c2b7; border-left-width: 0; background: #fcfcfb; color: #0b0b0b; cursor: pointer;}
.steps .step:first-child {border-left-width: 1px; border-radius: 8px 0 0 8px;}
.steps .step:last-child {border-radius: 0 8px 8px 0;}
.steps .step:hover {background: #f0efec;}
.steps .step:focus-visible {outline: 2px solid #2a78d6; outline-offset: 2px; position: relative; z-index: 1;}
/* a layer: its on/off switch, then its menu */
.layer {display: flex; align-items: flex-end; gap: 0.6rem; min-width: 0;}
.layer > form {flex: 1 1 auto; min-width: 0;}
.switch {position: relative; flex: none; width: 2.3rem; height: 1.3rem; margin-bottom: 0.45rem; cursor: pointer;}
.switch input {position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: pointer;}
.switch span {position: absolute; inset: 0; border-radius: 1rem; background: #c3c2b7; transition: background 0.15s;}
.switch span::after {content: ""; position: absolute; top: 2px; left: 2px; width: calc(1.3rem - 4px); height: calc(1.3rem - 4px); border-radius: 50%; background: #fcfcfb; transition: transform 0.15s;}
.switch input:checked + span {background: #0b0b0b;}
.switch input:checked + span::after {transform: translateX(1rem);}
.switch input:focus-visible + span {outline: 2px solid #2a78d6; outline-offset: 2px;}
@media (max-width: 640px) {
  .panel-row.when {grid-template-columns: 1fr auto;}
  .month-slider {grid-column: 1 / -1;}
}

/* ---------- map ---------- */
.map-hover {font-size: 0.85rem; color: #52514e; min-height: 1.4em; margin-top: 0.5rem;}
.map-buttons {position: absolute; top: 8px; right: 8px; display: flex; gap: 4px;}
.map-buttons button {font: inherit; font-size: 0.85rem; min-width: 2rem; padding: 0.2rem 0.55rem; border: 1px solid #c3c2b7; border-radius: 6px; background: #fcfcfb; color: #0b0b0b; cursor: pointer;}
.map-buttons button:disabled {color: #898781; cursor: default;}
.map-buttons button:focus-visible {outline: 2px solid #2a78d6; outline-offset: 1px;}
.legend {display: flex; flex-wrap: wrap; gap: 0.35rem 1rem; font-size: 0.8rem; color: #52514e; margin: 0.6rem 0 0.5rem;}
.legend-item {display: inline-flex; align-items: center; gap: 0.35rem;}
.swatch {width: 14px; height: 14px; display: inline-block; border-radius: 2px; border: 1px solid #c3c2b7; flex: none;}

/* ---------- cards and charts ---------- */
.card {padding: 1.1rem 1.25rem;}
.card h3 {max-width: none; margin: 0 0 0.45rem; font-family: var(--sans-serif); font-size: 1.02rem; font-weight: 600; color: #0b0b0b;}
.card > .fine {margin: 0 0 1rem; max-width: none; line-height: 1.45;}
.card figure {margin: 0;}
.grid {gap: 1.1rem; grid-auto-rows: auto;}
.tile-value {font-size: 1.6rem; font-weight: 600; line-height: 1.15; margin-bottom: 0.3rem; display: flex; align-items: center; gap: 0.5rem;}
.tile-value .swatch {width: 18px; height: 18px;}
.tile-label {font-size: 0.8rem; color: #52514e; line-height: 1.4;}
.notice {border-left: 4px solid #eda100; padding: 0.6rem 0.9rem; background: #fdf6e3; font-size: 0.9rem; border-radius: 0 8px 8px 0; margin: 0 0 1.25rem;}
.notice p {margin: 0 0 0.4rem; max-width: none;}
.notice p:last-child {margin: 0;}
/* the summary fills the page in two columns on a wide screen */
.narrative {columns: 2 26rem; column-gap: 2.5rem; margin: 0 0 1.25rem;}
.narrative p {max-width: none; margin: 0 0 0.7rem; break-inside: avoid;}
/* values that come from the data */
.dyn {font-weight: 600; font-family: var(--sans-serif); font-size: 0.95em; color: #a2431a;}
.fine {font-size: 0.8rem; color: #52514e;}
.keys {display: flex; flex-wrap: wrap; gap: 0.3rem 1rem; font-size: 0.8rem; color: #52514e; margin: 0 0 0.6rem;}
.keys span {display: inline-flex; align-items: center; gap: 0.35rem;}
.key-line {display: inline-block; width: 22px; height: 0; border-top: 2px solid #0b0b0b;}
.time-brush .handle {cursor: ew-resize;}
.time-brush .selection {cursor: grab;}
.time-card {padding-bottom: 0.7rem;}
.card table {width: 100%; max-width: none;}
details {margin: 0.4rem 0;}
details p, details li {max-width: 80ch; font-size: 0.9rem;}
/* on a wide screen the reading lists run in two columns instead of leaving the right half empty */
@media (min-width: 1100px) {details ul {columns: 2; column-gap: 3rem; max-width: none;} details li {break-inside: avoid; max-width: none;}}
#observablehq-main {min-height: 0;}        /* Framework keeps the main column a screen tall: no gap above the footer */
#observablehq-footer {margin-top: 1.5rem;}
.insight h4 {font: 600 0.78rem var(--sans-serif); margin: 0.7rem 0 0.15rem; color: #52514e;}
.insight .narrative p {margin-top: 0;}
.chips {margin: 0.55rem 0 0; display: flex; flex-wrap: wrap; gap: 0.3rem 0.4rem; align-items: center; max-width: none;}
.chips-label {font: 0.78rem var(--sans-serif); color: #52514e; margin-right: 0.2rem;}
.chip {font: 0.78rem var(--sans-serif); border: 1px solid #d9d7cf; background: #fff; border-radius: 999px; padding: 0.15rem 0.6rem; cursor: pointer;}
.chip:hover, .chip:focus-visible {border-color: #a2431a;}
.chip span {color: #a2431a; margin-left: 0.4rem; font-weight: 600;}
.below-col > .observablehq:first-child h2 {margin-top: 0.4rem;}
.below-col .card {overflow-x: auto;}
.below-col .card table {min-width: 46rem;}
@media (min-width: 1800px) {
  .below {display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 0 1.75rem; align-items: start;}
  .below .narrative {columns: 1;}
  .below .grid-cols-4 {grid-template-columns: repeat(2, minmax(0, 1fr));}
  /* the list of units stays in view while the story of the selected unit scrolls beside it */
  .below-col:last-child {position: sticky; top: 0.75rem;}
}
</style>

<header class="page-head">
  <h1><svg class="logo" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10.5" fill="#10151c"/><path d="M12 1.5a10.500 10.500 0 0 1 0 21 13.500 13.500 0 0 0 0-21Z" fill="#2a3644"/><circle cx="8.300" cy="9.400" r="3" fill="#ffd76a" opacity=".22"/><circle cx="8.300" cy="9.400" r="1.500" fill="#ffd76a"/><circle cx="12.700" cy="13.700" r="1.100" fill="#ffd76a"/><circle cx="7.300" cy="14.900" r=".800" fill="#f2b24a"/><circle cx="11.300" cy="6.700" r=".600" fill="#f2b24a"/><circle cx="10.200" cy="17.600" r=".600" fill="#f2b24a"/></svg>Nightlights Explorer</h1>
  <p class="lede">Indonesia after dark, by province, district and sub-district. Month by month, the night-time radiance a satellite records over each area's lit cells, set against what the area's own past would lead one to expect.</p>
</header>

<p class="fine" style="max-width:none; margin: -0.6rem 0 1rem;">Before 2012: <a href="./long-view">the long view, 1992 to 2026: a review of the older DMSP record, shown beside VIIRS and not joined</a>. Case studies, night by night: <a href="./lombok-2018">Lombok 2018, two dark nights, one of them unexplained</a>; <a href="./palu-2018">Palu 2018, the light that took weeks to return</a>; <a href="./nyepi-2026">Nyepi 2026, an island at under a tenth of its light</a>; <a href="./mudik-2019">Mudik 2019, looking for an exodus in the dark</a>.</p>

<div class="notice">
  <p><strong>How to read a status.</strong> A status says how a unit's light compares with its own past. It does not say why: this page makes no claim about electricity, outages or the economy, and none of it has been checked against records on the ground.</p>
</div>

```js
import {files} from "./data/files.js";
import {loadTyped, loadJSON, loadBundle, seriesOf, monthLabel, monthDate} from "./components/load.js";
import {STATUS, STRIP, LOW, LEVEL_NAME, LEVEL_PLURAL, PARENT_NAME, swatchStyle, RAMPS, NO_VALUE, CELL_LAYERS, colourOf, classOf} from "./components/palette.js";
import {drawMap, legend, boundsOf} from "./components/map.js";
import {timeSlider, rangeStore} from "./components/timezoom.js";
```

```js
// ---- fixed data, loaded once
const meta = await files["meta.json"].json();
// The record can end with a month whose files hold no usable observation yet. The slider ends at the
// latest month with observations (meta.latest, set by the export), and the page opens one month before
// it: the newest month is the one most likely to be revised.
const LAST = meta.latest.window;
const START = Math.max(0, LAST - 1);
const HIDDEN = meta.months.slice(LAST + 1); // months in the files that are not shown
const dates = meta.months.map(monthDate);
// The span of months the unit's charts show, kept when the unit or the month changes. It opens on the whole
// record; the overview above the charts narrows or moves it. `rangeStore` holds the same span for that overview
// (see timezoom.js), so that it is not rebuilt, and a drag not cut off, when the span changes.
rangeStore.value = [0, LAST];
const timeRange = Mutable(rangeStore.value);
const setTimeRange = (a, b) => { timeRange.value = [a, b]; };
const LEVELS = meta.levels; // province, district, subdistrict
const DIVISOR = {province: 1, district: 100, subdistrict: 10000}; // code / divisor = province code
const MIN_CELLS = meta.thresholds.min_unit_cells;
const MAX_DROP = meta.thresholds.max_detectable_drop;
const FLAG = meta.encoding.flags;
const cap = (text) => text.charAt(0).toUpperCase() + text.slice(1);
const n0 = (v) => v.toLocaleString("en");

async function unitList(level) {
  const u = await files[`units_${level}.json`].json();
  return u.code.map((code, pos) => ({level, pos, code, name: u.name[pos] ?? `Unnamed (${code})`, cells: u.cells[pos], light: u.light[pos],
                                    province: Math.floor(code / DIVISOR[level]), reporting: u.reporting ? u.reporting[pos] : null,
                                    // over the record, up to the latest month shown (ntl.trend, ntl.persistence)
                                    trend: u.trend[pos], trendLow: u.trend_low[pos], trendHigh: u.trend_high[pos], trendYears: u.trend_years[pos],
                                    episodes: u.episodes[pos], longestRun: u.longest_run[pos], lowWindows: u.low_windows[pos], judgedWindows: u.judged_windows[pos],
                                    longestUnseen: u.longest_unseen[pos], litKm2: u.lit_km2[pos],
                                    longestSpan: u.longest_span[pos], regionalWindows: u.regional_windows[pos],
                                    // the same trend over only the cells lit from the first year of the record
                                    trendCore: u.trend_core[pos], trendCoreLow: u.trend_core_low[pos], trendCoreHigh: u.trend_core_high[pos], coreCells: u.core_cells[pos],
                                    // cells per class of light then (first three years) and now (last three): ntl.firstlight.then_and_now
                                    thenNow: u.then_now[pos]}));
}
const units = {province: await unitList("province"), district: await unitList("district"), subdistrict: await unitList("subdistrict")};
const byCode = Object.fromEntries(LEVELS.map((lv) => [lv, new Map(units[lv].map((u) => [u.code, u]))]));
const outlines = {
  province: await files["outlines/province.geojson"].json(),
  district: await files["outlines/district.geojson"].json()
};
const provinceBundle = await loadBundle(files, meta, "province", "all");
// the first month in which a level has each pooled factor (a monitor has no line before it)
const firstWith = (level, key) => {
  const t = meta.level_detail[level].factors[key].findIndex((v) => v !== null);
  return t < 0 ? null : t;
};
const FIRST = Object.fromEntries(LEVELS.map((lv) => [lv, {watch: firstWith(lv, "watch"), alarm: firstWith(lv, "alarm")}]));

// lit cells: position on the global 15 arc-second grid, and a brightness class from their usual radiance
const cellIndex = await loadTyped("cells", files["cells.u32.gz"], Uint32Array);
const cellUsual = await loadTyped("usual", files["cell_usual.u16.gz"], Uint16Array);
const COLS = meta.encoding.cells.columns;
const lightsData = (() => {
  const n = cellIndex.length;
  const lon = new Float32Array(n), lat = new Float32Array(n), level = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    lon[i] = -180 + ((cellIndex[i] % COLS) + 0.5) * meta.encoding.cells.cell_degrees;
    lat[i] = 90 - (Math.floor(cellIndex[i] / COLS) + 0.5) * meta.encoding.cells.cell_degrees;
    const r = cellUsual[i] / meta.encoding.cells.usual_scale; // nW cm-2 sr-1
    level[i] = r < 5 ? 0 : r < 15 ? 1 : r < 40 ? 2 : 3;
  }
  return {lon, lat, level};
})();
// the same cells, classed by their light in the first and the last three years of the record
const cellThenNow = await loadTyped("thennow", files["cell_then_now.u8.gz"], Uint8Array);
// Faint sources (ntl.sources): cells too dim to count as lit that still stand above their surroundings. On the map only.
const FAINT = meta.variables.faint ?? null;
const faintIndex = FAINT ? await loadTyped("faint", files["faint_cells.u32.gz"], Uint32Array) : new Uint32Array(0);
const faintProvince = FAINT ? await loadTyped("faint_province", files["faint_province.u16.gz"], Uint16Array) : new Uint16Array(0);
const cellProvince = await loadTyped("cell_province", files["cell_province.u16.gz"], Uint16Array); // position + 1 in the province list
const TN = meta.variables.then_now;
const rgb = (hex) => [1, 3, 5].map((k) => parseInt(hex.slice(k, k + 2), 16)).join(", ");
const thenNowData = {lon: lightsData.lon, lat: lightsData.lat, level: cellThenNow, colours: CELL_LAYERS.thennow.colours.map(rgb)};
// the lit cells and the faint sources drawn together: class 0 lit, class 1 faint
const faintData = (() => {
  const n = cellIndex.length, m = faintIndex.length, deg = meta.encoding.cells.cell_degrees;
  const lon = new Float32Array(n + m), lat = new Float32Array(n + m), level = new Uint8Array(n + m);
  lon.set(lightsData.lon); lat.set(lightsData.lat);
  for (let j = 0; j < m; j++) {
    lon[n + j] = -180 + ((faintIndex[j] % COLS) + 0.5) * deg;
    lat[n + j] = 90 - (Math.floor(faintIndex[j] / COLS) + 0.5) * deg;
    level[n + j] = 1;
  }
  return {lon, lat, level, colours: CELL_LAYERS.faint.colours.map(rgb)};
})();
// position of a lit cell from a longitude and latitude, or -1: the cells are sorted by their grid index
const CELL_DEG = meta.encoding.cells.cell_degrees;
function cellAt(lon, lat) {
  const col = Math.floor((lon + 180) / CELL_DEG), row = Math.floor((90 - lat) / CELL_DEG);
  if (col < 0 || col >= COLS || row < 0) return -1;
  const want = row * COLS + col;
  let lo = 0, hi = cellIndex.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (cellIndex[mid] === want) return mid;
    if (cellIndex[mid] < want) lo = mid + 1; else hi = mid - 1;
  }
  return -1;
}
const CM = meta.variables.cell_maps;
```

```js
// ---- what is selected. One object, so that a click on the map can set every level at once.
const selection = Mutable({province: null, district: null, subdistrict: null, note: null});
const select = (lv, code, note = null) => {
  if (lv === null) selection.value = {province: null, district: null, subdistrict: null, note};
  else if (lv === "province") selection.value = {province: code, district: null, subdistrict: null, note};
  else if (lv === "district") selection.value = {province: Math.floor(code / 100), district: code, subdistrict: null, note};
  else selection.value = {province: Math.floor(code / 10000), district: Math.floor(code / 100), subdistrict: code, note};
};
```

```js
// ---- controls that do not depend on the selection (built once, so they keep keyboard focus)
const levelInput = Inputs.radio(new Map([["Provinces", "province"], ["Districts", "district"], ["Sub-districts", "subdistrict"]]), {label: "Map shows", value: "district"});
const level = Generators.input(levelInput);
const variableInput = Inputs.select(new Map([["Status", "status"], ["Light against expected", "expected"], ["Light against usual", "usual"],
                                             ["Radiance", "radiance"], ["How well seen", "seen"], ["Months not observed", "unseen"],
                                             ["Months reading low", "run"], ["Trend against the median", "trend"], ["Newly lit cells", "newlit"]]),
                                    {label: "Units coloured by", value: "status"});
const variableChoice = Generators.input(variableInput);
// what the lit cells themselves show: pixel by pixel, under the same month slider
const cellsInput = Inputs.select(new Map([["Usual light", "usual"], ["Radiance this month", "radiance"], ["Change from a year earlier", "change"],
                                          ["Observations this month", "observations"], ["Then and now", "thennow"],
                                          ...(FAINT ? [["Faint sources too", "faint"]] : [])]), {label: "Lit cells show", value: "usual"});
const cellChoice = Generators.input(cellsInput);
// each layer has its own switch: units only, lit cells only, or both
const layerSwitch = (name) => html`<input type="checkbox" checked role="switch" aria-label=${`Show ${name} on the map`}>`;
const unitsSwitch = layerSwitch("the unit fills"), cellsSwitch = layerSwitch("the lit cells");
const unitsOn = Generators.input(unitsSwitch), cellsOn = Generators.input(cellsSwitch);
const monthInput = html`<input type="range" min="0" max="${LAST}" step="1" value="${START}" style="width: 100%;" aria-label="Month, from ${monthLabel(meta.months[0])} to ${monthLabel(meta.months[LAST])}">`;
const month = Generators.input(monthInput);
const setMonth = (t) => {
  monthInput.value = Math.max(0, Math.min(LAST, t));
  monthInput.dispatchEvent(new Event("input", {bubbles: true}));
};
const stepButton = (label, title, by) => html`<button type="button" class="step" title=${title} aria-label=${title} onclick=${() => setMonth(+monthInput.value + by)}>${label}</button>`;
const monthLabelEl = html`<div class="month-label" aria-live="polite"></div>`;
const monthNoteEl = html`<p class="month-note"></p>`;
const whereEl = html`<div></div>`;
display(html`<div class="panel">
  <div class="panel-row what">
    <div>${levelInput}</div>
    <div class="layer"><label class="switch" title="Show or hide the unit fills">${unitsSwitch}<span></span></label>${variableInput}</div>
    <div class="layer"><label class="switch" title="Show or hide the lit cells">${cellsSwitch}<span></span></label>${cellsInput}</div>
  </div>
  ${whereEl}
  <div class="panel-row when">
    ${monthLabelEl}
    <div class="steps">${stepButton("«", "One year back", -12)}${stepButton("‹", "One month back", -1)}${stepButton("›", "One month forward", 1)}${stepButton("»", "One year forward", 12)}</div>
    <div class="month-slider">${monthInput}</div>
  </div>
  ${monthNoteEl}
</div>`);
```

```js
// ---- what each layer shows: its menu's choice while its switch is on. Off: units become outlines, cells are hidden.
const variable = unitsOn ? variableChoice : "none";
const cellMode = cellsOn ? cellChoice : "off";
variableInput.querySelector("select").disabled = !unitsOn;
cellsInput.querySelector("select").disabled = !cellsOn;
```

```js
// ---- the month label and the note on how far the month can be trusted
{
  const count = provinceBundle.count;
  let unseen = 0;
  for (let u = 0; u < count; u++) if (provinceBundle.state[month * count + u] === 0) unseen++;
  const notes = [];
  if (month === LAST) notes.push(html`<strong>Low confidence: this is the latest month.</strong> Nothing later exists yet to show whether a low reading here persisted or was a one-month dip${HIDDEN.length ? html`. ${HIDDEN.map(monthLabel).join(", ")} is in the files but holds no usable observation yet, so it is not shown` : ""}.`);
  if (unseen * 4 >= count) notes.push(html`<strong>Low confidence: thinly observed month.</strong> ${unseen} of ${count} provinces were not observed (cloud, or too few observations).`);
  if (FIRST.district.alarm !== null && month < FIRST.district.alarm) notes.push(html`<strong>No thresholds yet.</strong> A monitor needs several years of history before it can say how unusual a reading is: districts and sub-districts are "not judged" before ${monthLabel(meta.months[FIRST.district.alarm])}, provinces before ${monthLabel(meta.months[FIRST.province.watch])}.`);
  if (!notes.length) notes.push(html`Data run from ${monthLabel(meta.months[0])} to ${monthLabel(meta.months[LAST])}. The page opens one month before the latest.`);
  monthLabelEl.textContent = monthLabel(meta.months[month]);
  monthInput.setAttribute("aria-valuetext", monthLabel(meta.months[month]));
  monthNoteEl.replaceChildren(...notes.flatMap((n, i) => (i ? [" ", html`<span>${n}</span>`] : [html`<span>${n}</span>`])));
}
```

```js
// ---- the selected objects, and the data of the open province
const prov = selection.province === null ? null : byCode.province.get(selection.province) ?? null;
const dist = selection.district === null ? null : byCode.district.get(selection.district) ?? null;
const sub = selection.subdistrict === null ? null : byCode.subdistrict.get(selection.subdistrict) ?? null;
const unit = sub ?? dist ?? prov; // the deepest unit selected, or null for the whole country

// The map cannot show sub-districts for the whole country (their files are per province).
const shown = level === "subdistrict" && !prov ? "district" : level;
const bundles = {province: {all: provinceBundle}, district: {}, subdistrict: {}};
if (prov) {
  bundles.district[prov.code] = await loadBundle(files, meta, "district", String(prov.code));
  bundles.subdistrict[prov.code] = await loadBundle(files, meta, "subdistrict", String(prov.code));
} else if (shown === "district") {
  const all = await Promise.all(units.province.map((p) => loadBundle(files, meta, "district", String(p.code))));
  units.province.forEach((p, i) => { bundles.district[p.code] = all[i]; });
}
const subOutlines = prov && shown === "subdistrict" && files[`outlines/subdistrict/${prov.code}.geojson`]
  ? await loadJSON(`outlines/subdistrict/${prov.code}`, files[`outlines/subdistrict/${prov.code}.geojson`]) : null;

// value of one column for a unit in a window, or undefined if its bundle is not loaded
const bundleOf = (u) => (u.level === "province" ? bundles.province.all : bundles[u.level][u.province]) ?? null;
const valueOf = (u, column, t) => {
  const b = bundleOf(u);
  return b ? b[column][t * b.count + (u.pos - b.first)] : undefined;
};
```

```js
// ---- wording shared by the hover line, the tiles, the table and the text
// "Judged here": can a reading of this unit be trusted at its own level in this window?
//   "yes"       at least MIN_CELLS lit cells and a smallest detectable drop of MAX_DROP or less
//   "no"        too few cells, or too noisy
//   "unknown"   enough cells, but no alarm factor yet, so the detectable drop is not measured
function judged(u, t) {
  if (u.cells < MIN_CELLS) return "no";
  if ((valueOf(u, "flags", t) & FLAG.monitorable) > 0) return "yes";
  return Number.isFinite(valueOf(u, "detectable", t)) ? "no" : "unknown";
}
// a low reading on a unit that cannot be judged at its own level
const isWeak = (u, t) => LOW.has(valueOf(u, "state", t)) && judged(u, t) !== "yes";
const ratioText = (anomaly) => `${(100 * Math.exp(anomaly)).toFixed(0)}% of the light expected`;
// Stored coverage is rounded to half a percent, so a "not observed" month can round up to the 50% line.
const seenText = (coverage, state) => (state === 0 && Math.round(100 * coverage) >= 100 * meta.thresholds.min_coverage ? "just under 50%" : `${(100 * coverage).toFixed(0)}%`);
function describe(u, t) {
  const state = valueOf(u, "state", t);
  if (state === undefined) return u.name;
  const weak = isWeak(u, t);
  const parts = [`${u.name} (${LEVEL_NAME[u.level]}): ${STATUS[state].label.toLowerCase()}${weak ? ", low confidence" : ""}`];
  const anomaly = valueOf(u, "anomaly", t);
  if (state >= 2 && state !== 7 && Number.isFinite(anomaly)) parts.push(ratioText(anomaly));
  parts.push(`${seenText(valueOf(u, "coverage", t), state)} of its usual light seen`);
  if (u.cells < MIN_CELLS) parts.push(`only ${u.cells} lit cell${u.cells === 1 ? "" : "s"}`);
  return parts.join(". ") + ".";
}
```

```js
// ---- where: menus and breadcrumb, rebuilt when the selection changes
{
  const option = (u, chosen) => html`<option value=${u.code} selected=${chosen && chosen.code === u.code}>${u.name}</option>`;
  const byName = (a, b) => a.name.localeCompare(b.name);
  const provSelect = html`<select id="sel-province" onchange=${(e) => (e.target.value === "" ? select(null) : select("province", +e.target.value))}>
    <option value="">All of Indonesia</option>${units.province.slice().sort(byName).map((u) => option(u, prov))}</select>`;
  const distSelect = html`<select id="sel-district" disabled=${!prov} onchange=${(e) => (e.target.value === "" ? select("province", prov.code) : select("district", +e.target.value))}>
    <option value="">${prov ? "All districts with lit cells" : "Choose a province first"}</option>
    ${prov ? units.district.filter((u) => u.province === prov.code).sort(byName).map((u) => option(u, dist)) : []}</select>`;
  const subSelect = html`<select id="sel-subdistrict" disabled=${!dist} onchange=${(e) => (e.target.value === "" ? select("district", dist.code) : select("subdistrict", +e.target.value))}>
    <option value="">${dist ? "All sub-districts with lit cells" : "Choose a district first"}</option>
    ${dist ? units.subdistrict.filter((u) => Math.floor(u.code / 100) === dist.code).sort(byName).map((u) => option(u, sub)) : []}</select>`;
  const crumb = (label, go) => html`<a onclick=${go} role="button" tabindex="0" onkeydown=${(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } }}>${label}</a>`;
  whereEl.replaceChildren(html`<div class="panel-row where">
      <div class="field"><label for="sel-province">Province</label>${provSelect}</div>
      <div class="field"><label for="sel-district">District</label>${distSelect}</div>
      <div class="field"><label for="sel-subdistrict">Sub-district</label>${subSelect}</div>
    </div>`,
    html`<p class="crumbs" style="margin-top: 1rem;">${crumb("Indonesia", () => select(null))}
      ${prov ? html`<span class="crumb-sep">›</span>${crumb(prov.name, () => select("province", prov.code))}` : ""}
      ${dist ? html`<span class="crumb-sep">›</span>${crumb(dist.name, () => select("district", dist.code))}` : ""}
      ${sub ? html`<span class="crumb-sep">›</span><strong>${sub.name}</strong>` : ""}
      ${selection.note ? html`<span class="fine" style="margin-left: 0.6rem;">${selection.note}</span>` : ""}</p>`);
}
```

```js
// ---- the other variables: a fill and a few words for a unit in a window; null fill = no value to show
const TR = meta.variables.trend;
const big = (u) => u.cells >= MIN_CELLS; // figures over the record are shown only for units with enough lit cells
const SMALL = `under ${MIN_CELLS} lit cells: too few for this figure`;
const trendMedian = (u) => TR.median_by_level[u.level].all;
// faster or slower than the median unit of its level, when the range excludes the median; otherwise "unclear"
const trendSide = (u) => (u.trend === null || trendMedian(u) === null ? null : u.trendLow > trendMedian(u) ? "faster" : u.trendHigh < trendMedian(u) ? "slower" : "unclear");
const signed = (v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}`;
const trendText = (u) => {
  if (!big(u)) return SMALL;
  if (u.trend === null) return `no trend: fewer than ${TR.min_years} years with enough observed months`;
  const side = trendSide(u);
  return `${signed(u.trend)}% a year over the ${u.trendYears} years with enough observed months between ${TR.years[0]} and ${TR.years[1]} (${(100 * TR.confidence).toFixed(0)}% range ${signed(u.trendLow)} to ${signed(u.trendHigh)}); the median ${LEVEL_NAME[u.level]} is ${signed(trendMedian(u))}%, and this one is ${side === "unclear" ? "not clearly different from it" : `clearly ${side}`}`;
};
// Mean radiance of the unit's lit cells this month, nW cm-2 sr-1: its usual mean times this month's
// like-for-like ratio. An estimate: it assumes the cells not seen this month moved like the ones that were.
const radianceOf = (u, t) => (u.light / u.cells) * Math.exp(valueOf(u, "index", t));
// cells of the unit by their light then and now: [unknown, lit both, brightened, emerged, faded, dim both]
const classed = (u) => u.thenNow.slice(1).reduce((a, b) => a + b, 0);
const newLitText = (u) => {
  const n = classed(u);
  if (!n) return "none of its lit cells could be compared between the start and the end of the record";
  const share = (k) => `${n0(u.thenNow[k])} (${((100 * u.thenNow[k]) / n).toFixed(u.thenNow[k] && (100 * u.thenNow[k]) / n < 1 ? 1 : 0)}%)`;
  return `of its ${n0(n)} cells that can be compared, ${share(3)} were dark in ${TN.then[0]} to ${TN.then[1]} and lit in ${TN.now[0]} to ${TN.now[1]}, ${share(2)} were dimly lit and are now lit, ${share(1)} were lit at both ends, and ${share(4)} were lit and no longer are`;
};
function variableOf(u, t) {
  const state = valueOf(u, "state", t);
  if (variable === "none") return {fill: "transparent", text: null};
  if (variable === "expected") {
    const a = valueOf(u, "anomaly", t);
    return Number.isFinite(a) && state !== 0 && state !== 7 ? {fill: colourOf(RAMPS.expected, 100 * Math.exp(a)), text: ratioText(a)} : {fill: null, text: "no expected value this month"};
  }
  if (variable === "usual") {
    if (state === 7) return {fill: RAMPS.usual.colours[0], text: "no detectable light"};
    const i = valueOf(u, "index", t);
    return Number.isFinite(i) ? {fill: colourOf(RAMPS.usual, 100 * Math.exp(i)), text: `${(100 * Math.exp(i)).toFixed(0)}% of its usual light`} : {fill: null, text: "not observed this month"};
  }
  if (variable === "radiance") {
    if (state === 7) return {fill: RAMPS.radiance.colours[0], text: "no detectable light"};
    const r = radianceOf(u, t);
    return Number.isFinite(r) ? {fill: colourOf(RAMPS.radiance, r), text: `about ${r.toFixed(1)} nW cm-2 sr-1 on average over its lit cells`} : {fill: null, text: "not observed this month"};
  }
  if (variable === "seen") {
    const cov = valueOf(u, "coverage", t);
    return {fill: colourOf(RAMPS.seen, 100 * cov), text: `${seenText(cov, state)} of its usual light seen`};
  }
  if (variable === "unseen") {
    const gone = valueOf(u, "unseen", t);
    return gone > 0 ? {fill: colourOf(RAMPS.unseen, gone), text: `no usable reading for ${gone} month${gone === 1 ? "" : "s"} in a row`} : {fill: STATUS[3].colour, text: "observed this month"};
  }
  if (variable === "run") {
    if (!big(u)) return {fill: null, text: SMALL};
    const run = valueOf(u, "run", t), span = valueOf(u, "span", t);
    if (run > 0) return {fill: colourOf(RAMPS.run, run), text: `watch or alarm in ${run} month${run === 1 ? "" : "s"}${span > run ? ` over a span of ${span}` : " in a row"}`};
    return state === 3 || state === 6 || state === 7 ? {fill: STATUS[3].colour, text: "not in watch or alarm"} : {fill: null, text: "no reading this month"};
  }
  if (variable === "trend") {
    const side = big(u) ? trendSide(u) : null;
    return {fill: side === null ? null : side === "unclear" ? "#8a8f96" : colourOf(RAMPS.trend, u.trend - trendMedian(u)), text: trendText(u)};
  }
  if (variable === "newlit") {
    const n = big(u) ? classed(u) : 0;
    return {fill: n ? colourOf(RAMPS.newlit, (100 * u.thenNow[3]) / n) : null, text: big(u) ? newLitText(u) : SMALL};
  }
  return null; // status: the map's own fills
}
const variableLegend = variable === "status" ? null : variable === "none" ? [] : (() => {
  const ramp = RAMPS[variable];
  const items = ramp.colours.map((colour, i) => ({style: `background:${colour};`, label: ramp.labels[i]}));
  if (variable === "run") items.unshift({style: `background:${STATUS[3].colour};`, label: "Not in watch or alarm"});
  if (variable === "unseen") items.unshift({style: `background:${STATUS[3].colour};`, label: "Observed this month"});
  if (variable === "trend") items.push({style: "background:#8a8f96;", label: "Not clearly different from the median"});
  if (variable !== "unseen" && variable !== "seen") items.push({style: `background:${NO_VALUE};`, label: variable === "trend" ? `No trend, or under ${MIN_CELLS} lit cells` : variable === "newlit" || variable === "run" ? `No value, or under ${MIN_CELLS} lit cells` : "No value this month"});
  return items;
})();
const VARIABLE_NOTE = {
  status: `Each ${LEVEL_NAME[shown]} is filled by its status this month. A striped fill is a low reading on a unit too small or too noisy to judge at its own level: treat it as low confidence. Provinces never show Watch or Alarm.`,
  expected: `Each ${LEVEL_NAME[shown]} is filled by its light this month as a percentage of what up to six of its own previous years lead one to expect. Brown is dimmer than expected, teal brighter. This is the number the statuses are judged from, shown without the judgement: a small or noisy unit swings widely.`,
  usual: `Each ${LEVEL_NAME[shown]} is filled by its light this month as a percentage of its usual level over the whole record, on the cells seen this month. Because lights have grown, early years read brown and recent years teal almost everywhere: use "Light against expected" to see what is unusual.`,
  radiance: `Each ${LEVEL_NAME[shown]} is filled by the mean radiance of its lit cells this month, in nW cm-2 sr-1. It is an estimate: the unit's usual mean times this month's ratio on the cells that were seen, which assumes the unseen cells moved the same way. It compares places by how bright their lit cells are, not by how much light they give off in all.`,
  seen: `Each ${LEVEL_NAME[shown]} is filled by the share of its usual light that sat in cells with a usable value this month. Under 50% a unit is "not observed". This decides what every other figure is worth.`,
  unseen: `Each ${LEVEL_NAME[shown]} that was not observed this month is filled by how many months in a row it has gone without a usable reading (under half of its usual light seen). Whatever happened there in that time cannot be read from this page.`,
  run: `Each ${LEVEL_NAME[shown]} in Watch or Alarm this month is filled by how many months of its current spell have read that way. Regional dimming is not counted: it is shared with the surrounding area. A normal month, or a month seen with no light, ends a spell, and so do ${meta.variables.persistence.max_silent} months in a row without a reading; shorter gaps are skipped, not counted. Four spells in five last a single month. Units under ${MIN_CELLS} lit cells are left out, and provinces never show Watch or Alarm, so they have no spells. This is about the unit as a whole: it does not say each place in it stayed dim.`,
  trend: `Each ${LEVEL_NAME[shown]} is filled by how its rate of change over ${TR.years[0]} to ${TR.years[1]} compares with the median ${LEVEL_NAME[shown]} (${trendMedian({level: shown}) === null ? "not available" : `${signed(trendMedian({level: shown}))}% a year`}): brown is slower, teal faster, grey not clearly different. Nearly every unit grew, so the rate itself says little; the comparison says where growth was unusual. It does not change with the month. The cells counted are those lit on average over the whole record, a set that favours places that grew. No trend is given where cloud leaves too few months, which is much of northern Sumatra and Papua, or for units under ${MIN_CELLS} lit cells.`,
  newlit: `Each ${LEVEL_NAME[shown]} is filled by the share of its cells that were dark in ${TN.then[0]} to ${TN.then[1]} (under ${TN.dark_max} nW cm-2 sr-1, which the product stores as zero) and lit in ${TN.now[0]} to ${TN.now[1]} (at least ${TN.lit_min}). It does not change with the month. Choose "Then and now" under "Lit cells show" to see each cell. Most cells that are brighter now were already dimly lit, and are counted as brightened, not as newly lit. Newly lit cells are undercounted: a cell must be lit on average over the whole record to be looked at.`,
  none: `The unit fills are switched off: units are drawn as outlines only, so that the lit cells can be read on their own. Hover or click still works on a unit.`
};
const VARIABLE_TITLE = {status: "status", expected: "light against expected", usual: "light against usual", seen: "how well seen", run: "months reading low",
                        trend: "trend against the median", radiance: "radiance of lit cells", unseen: "months not observed", newlit: "newly lit cells", none: "outlines only"};
const STATIC = variable === "trend" || variable === "newlit"; // variables that do not change with the month
```

```js
// ---- the lit cells, pixel by pixel: this month's classes come from the year's file (ntl.cellmaps)
const monthYear = meta.months[month].slice(0, 4);
const cellMonth = (cellMode === "radiance" || cellMode === "change" || cellMode === "observations") && CM.files[monthYear]
  ? await (async () => {
      const entry = CM.files[monthYear];
      const all = await loadTyped(entry.file, files[entry.file], Uint8Array);
      const n = cellIndex.length, at = (month - entry.first_window) * n;
      return all.subarray(at, at + n); // one packed byte per cell for this month
    })()
  : null;
const classOfCell = (i, mode) => (cellMonth[i] >> CM[mode].shift) & CM[mode].mask;
// which lit cells are drawn, and their legend entries (true = the default points of light)
const cellLayer = (() => {
  if (cellMode === "off") return null;
  if (cellMode === "usual") return lightsData;
  if (cellMode === "thennow") return thenNowData;
  if (cellMode === "faint") return faintData;
  if (!cellMonth) return null;
  const level = new Uint8Array(cellMonth.length);
  for (let i = 0; i < level.length; i++) level[i] = classOfCell(i, cellMode);
  return {lon: lightsData.lon, lat: lightsData.lat, level, colours: CELL_LAYERS[cellMode].colours.map(rgb)};
})();
const dotLegend = (colours, labels) => colours.map((colour, i) => ({style: `background:${colour};border-radius:50%;`, label: labels[i]}));
const cellLegend = cellMode === "off" ? false : cellMode === "usual" ? true
  : dotLegend(CELL_LAYERS[cellMode].colours, CELL_LAYERS[cellMode].labels.map((l) => `Cell: ${l.charAt(0).toLowerCase()}${l.slice(1)}`)).filter((item, i) => !(cellMode === "thennow" && i === 5));
const CELL_NOTE = {
  usual: " The points of light are the lit cells the figures rest on, drawn by their usual brightness over the record, so they do not change with the month.",
  radiance: " The lit cells are coloured by their radiance this month, in classes. Grey cells have no usable value this month (cloud, or too few observations).",
  change: " The lit cells are coloured by this month's radiance against the same month a year earlier: brown is dimmer, teal brighter. Where lights are growing, brighter than a year ago is the normal state. Grey cells cannot be compared.",
  observations: " The lit cells are coloured by how many observations stand behind this month's value. A value needs at least 4 and good quality.",
  faint: FAINT ? ` Blue points are faint sources: cells whose mean radiance is under ${meta.source.domain.lit_min} nW cm-2 sr-1, so they are not lit cells, but which are brighter than a distance-weighted mean of the cells within ${FAINT.radius_km} km by more than ${FAINT.contrast} nW in at least ${(100 * FAINT.share).toFixed(0)}% of their good months. They are close to the least the product registers, they are in no status or figure on this page, and what they are has not been checked. Cream points are the lit cells.` : "",
  thennow: ` The lit cells are coloured by their light in ${TN.then[0]} to ${TN.then[1]} against ${TN.now[0]} to ${TN.now[1]}: lit at both ends, brightened from dim, emerged from dark, or faded.`,
  off: ""
};
// a line about the cell under the pointer, whatever layer is shown
function describeCell(lon, lat) {
  const i = cellAt(lon, lat);
  if (i < 0) return null;
  const parts = [`usual radiance ${(cellUsual[i] / meta.encoding.cells.usual_scale).toFixed(1)} nW cm-2 sr-1`];
  if (cellMonth) {
    parts.push(CELL_LAYERS.radiance.labels[classOfCell(i, "radiance")].toLowerCase() + (classOfCell(i, "radiance") > 1 ? " this month" : ""));
    if (classOfCell(i, "change") > 0) parts.push(`${CELL_LAYERS.change.labels[classOfCell(i, "change")].toLowerCase()} of a year earlier`);
    parts.push(`observations: ${CELL_LAYERS.observations.labels[classOfCell(i, "observations")].toLowerCase()}`);
  }
  parts.push(CELL_LAYERS.thennow.labels[cellThenNow[i]].toLowerCase());
  return `Lit cell here: ${parts.join("; ")}.`;
}
```

```js
// ---- the map
const mapUnits = (() => {
  const make = (lv, features) => features.map((feature) => {
    const u = byCode[lv].get(feature.properties.code);
    const state = u ? valueOf(u, "state", month) : undefined;
    const holder = lv === "subdistrict" ? "district" : lv === "district" ? "province" : null;
    const extra = u && state !== undefined ? variableOf(u, month) : null;
    return {feature, id: {level: lv, code: feature.properties.code, name: feature.properties.name ?? "Unnamed"},
            state: state === undefined ? null : state,
            weak: state !== undefined && isWeak(u, month),
            fill: extra ? extra.fill ?? NO_VALUE : undefined,
            extra,
            text: u && state !== undefined ? (extra && extra.text ? `${u.name} (${LEVEL_NAME[lv]}): ${extra.text}. Status: ${STATUS[state].label.toLowerCase()}.` : describe(u, month))
              : `${feature.properties.name ?? "Unnamed"} (${LEVEL_NAME[lv]}): no lit cell, so no status.${holder ? ` A click selects its ${holder}.` : ""}`};
  });
  // other provinces stay clickable when one is open
  const others = prov && shown !== "province"
    ? outlines.province.features.filter((f) => f.properties.code !== prov.code).map((feature) => ({
        feature, id: {level: "province", code: feature.properties.code, name: feature.properties.name}, state: null, weak: false,
        text: `${feature.properties.name} (province): click to open it.`}))
    : [];
  if (shown === "province") return make("province", outlines.province.features);
  if (shown === "district") {
    const features = prov ? outlines.district.features.filter((f) => Math.floor(f.properties.code / 100) === prov.code) : outlines.district.features;
    return [...others, ...make("district", features)];
  }
  return [...others, ...make("subdistrict", subOutlines ? subOutlines.features : [])];
})();
const selectedFeatures = [
  prov && outlines.province.features.find((f) => f.properties.code === prov.code),
  dist && outlines.district.features.find((f) => f.properties.code === dist.code),
  sub && subOutlines && subOutlines.features.find((f) => f.properties.code === sub.code)
].filter(Boolean);
const focus = selectedFeatures.length
  ? {key: `${selection.province}/${selection.district}`, bounds: boundsOf([selectedFeatures[Math.min(1, selectedFeatures.length - 1)]])}
  : null;
// A click on a unit selects it. A unit without lit cells has no status, so the click selects what holds it, and says so.
const pick = (id) => {
  if (id === null) return;
  if (byCode[id.level].has(id.code)) return select(id.level, id.code);
  const why = (held) => `${id.name} has no lit cell, so no status: showing ${held} instead.`;
  const d = id.level === "subdistrict" ? byCode.district.get(Math.floor(id.code / 100)) : null;
  if (d) return select("district", d.code, why(d.name));
  const p = byCode.province.get(Math.floor(id.code / DIVISOR[id.level]));
  if (p) select("province", p.code, why(p.name));
};
```

<div class="card">
  <h3>${STATIC ? "" : `${monthLabel(meta.months[month])}: `}${cap(variable === "none" && CELL_LAYERS[cellMode] ? `lit cells by ${CELL_LAYERS[cellMode].title}` : VARIABLE_TITLE[variable])}, ${LEVEL_PLURAL[shown]} of ${prov && shown !== "province" ? prov.name : "Indonesia"}</h3>
  <p class="fine">${level === "subdistrict" && !prov ? "Sub-districts are shown one province at a time: choose a province, or click one. Until then the map shows districts. " : ""}${VARIABLE_NOTE[variable]}${CELL_NOTE[cellMode]} A cell is about 460 m across but the sensor's view of the ground is wider, so read patterns rather than single cells. Outlines are simplified for display: near a border, a lit cell can be drawn in the neighbouring unit (about 2% of cells at sub-district level), while the figures use the exact boundaries.</p>
  ${resize((width) => drawMap({width, land: outlines.province.features, units: mapUnits, context: shown === "province" ? [] : outlines.province.features, selected: selectedFeatures, lights: cellLayer, describeCell, focus, onPick: pick}))}
  ${legend({lights: cellLegend, items: variableLegend})}
</div>

```js
// ---- the insight under the map (1): one number per unit and month for the layer shown.
// Kept apart from the month so that moving the slider does not recount every month.
const scopeUnits = (shown === "province" ? units.province : prov ? units[shown].filter((u) => u.province === prov.code) : units[shown]).filter((u) => bundleOf(u));
const scopeName = prov && shown !== "province" ? prov.name : "Indonesia";
const fin = (v) => v !== null && v !== undefined && Number.isFinite(v);
const share = (test) => (values) => d3.mean(values, (v) => +test(v));
const INSIGHT = {
  status: {value: (u, t) => { const st = valueOf(u, "state", t); return st >= 3 && st <= 6 ? +LOW.has(st) : null; }, stat: d3.mean,
           what: `share of judged ${LEVEL_PLURAL[shown]} reading low`, fmt: (v) => `${(100 * v).toFixed(1)}%`},
  expected: {value: (u, t) => { const st = valueOf(u, "state", t), a = valueOf(u, "anomaly", t); return fin(a) && st !== 0 && st !== 7 ? 100 * Math.exp(a) : null; }, stat: d3.median,
             what: `light of the median ${LEVEL_NAME[shown]}, against what its past leads one to expect`, fmt: (v) => `${v.toFixed(0)}%`},
  usual: {value: (u, t) => { const st = valueOf(u, "state", t), i = valueOf(u, "index", t); return fin(i) && st !== 0 && st !== 7 ? 100 * Math.exp(i) : null; }, stat: d3.median,
          what: `light of the median ${LEVEL_NAME[shown]}, against its usual level over the record`, fmt: (v) => `${v.toFixed(0)}%`},
  radiance: {value: (u, t) => { const st = valueOf(u, "state", t), r = radianceOf(u, t); return fin(r) && st !== 0 && st !== 7 ? r : null; }, stat: d3.median,
             what: `mean radiance of the lit cells of the median ${LEVEL_NAME[shown]}`, fmt: (v) => `${v.toFixed(1)} nW`},
  seen: {value: (u, t) => 100 * valueOf(u, "coverage", t), stat: share((v) => v >= 100 * meta.thresholds.min_coverage),
         what: `share of ${LEVEL_PLURAL[shown]} observed`, fmt: (v) => `${(100 * v).toFixed(0)}%`},
  unseen: {value: (u, t) => valueOf(u, "unseen", t), stat: share((v) => v >= 3),
           what: `share of ${LEVEL_PLURAL[shown]} without a reading for three months or more`, fmt: (v) => `${(100 * v).toFixed(1)}%`},
  // only units with a reading this month count: an unobserved unit is not "not in watch or alarm"
  run: {value: (u, t) => { const st = valueOf(u, "state", t), run = valueOf(u, "run", t); return big(u) && (run > 0 || st === 3 || st === 6 || st === 7) ? run : null; }, stat: share((v) => v >= 2),
        what: `share of ${LEVEL_PLURAL[shown]} two months or more into a spell of Watch or Alarm`, fmt: (v) => `${(100 * v).toFixed(1)}%`}
};
const insight = INSIGHT[variable] ?? null;
const insightSeries = insight ? d3.range(LAST + 1).map((t) => {
  const values = scopeUnits.map((u) => insight.value(u, t)).filter(fin);
  return {t, date: dates[t], n: values.length, value: values.length >= Math.min(5, scopeUnits.length) && values.length ? insight.stat(values) : null};
}) : null;
```

```js
// ---- the selected unit, window by window
const rows = unit && bundleOf(unit) ? (() => {
  const b = bundleOf(unit), u = unit.pos - b.first;
  const col = Object.fromEntries(meta.encoding.columns.map((c) => [c.name, seriesOf(b, c.name, u)]));
  const f = meta.level_detail[unit.level].factors;
  return dates.slice(0, LAST + 1).map((date, t) => {
    const dark = col.state[t] === 7;
    const expected = col.index[t] - col.anomaly[t]; // ln of expected light over usual light
    const line = (factor) => (factor === null || !Number.isFinite(col.scale[t]) || !Number.isFinite(expected) ? NaN : 100 * Math.exp(expected + factor * col.scale[t]));
    return {t, date, state: col.state[t], status: STATUS[col.state[t]].label,
            // "seen, no light" has no logarithm: it is drawn at zero, which is what was seen
            observed: dark ? 0 : 100 * Math.exp(col.index[t]), expected: 100 * Math.exp(expected),
            watchLine: line(f.watch[t]), alarmLine: line(f.alarm[t]),
            anomaly: col.anomaly[t], scale: col.scale[t],
            coverage: col.coverage[t], nights: col.nights[t], detectable: col.detectable[t],
            held: (col.flags[t] & FLAG.held) > 0, joint: (col.flags[t] & FLAG.joint) > 0,
            judged: judged(unit, t)};
  });
})() : null;
const now = rows ? rows[month] : null;
// clicking a chart with a time axis moves the map to that month
const clickToMonth = (plot) => {
  plot.addEventListener("click", () => { if (plot.value && Number.isInteger(plot.value.t)) setMonth(plot.value.t); });
  plot.style.cursor = "pointer";
  return plot;
};
const hasTiers = unit ? meta.level_detail[unit.level].tiers : true;
```

```js
// ---- text for the selected unit
function unitNarrative(u, r) {
  const out = [];
  const when = monthLabel(meta.months[r.t]);
  const parent = PARENT_NAME[u.level];
  const low = LOW.has(r.state);
  const lead = low && r.judged !== "yes" ? html`<strong>Low confidence.</strong> ` : "";
  out.push(html`<p>${lead}In <span class="dyn">${when}</span> the status of ${u.name} was <span class="dyn">${STATUS[r.state].label}</span>: ${u.level === "province" && STATUS[r.state].saysProvince ? STATUS[r.state].saysProvince : STATUS[r.state].says}</p>`);
  if (Number.isFinite(r.anomaly) && r.state !== 7 && r.state !== 0) {
    out.push(html`<p>Its lit cells gave <span class="dyn">${(100 * Math.exp(r.anomaly)).toFixed(0)}%</span> of the light expected from up to six of its own previous years${Number.isFinite(r.scale) ? html`. Around that expectation its readings usually spread by about <span class="dyn">${(100 * (Math.exp(r.scale) - 1)).toFixed(0)}%</span>` : ""}. <span class="dyn">${seenText(r.coverage, r.state)}</span> of its usual light was seen${Number.isFinite(r.nights) ? html`, from a mean of <span class="dyn">${r.nights.toFixed(1)}</span> observations per cell` : ""}.</p>`);
  } else if (r.state === 0) {
    out.push(html`<p><span class="dyn">${seenText(r.coverage, r.state)}</span> of its usual light was seen, against the ${(100 * meta.thresholds.min_coverage).toFixed(0)}% needed for a reading.</p>`);
  }
  if ((r.state === 4 || r.state === 5) && !r.joint) {
    out.push(html`<p>This reading rests on the unit's own past alone: the comparison with the rest of its ${parent} was not available this month.</p>`);
  }
  if (r.held) out.push(html`<p>Against its own past alone this month is below the alarm line${r.state === 4 ? html`; it is Watch and not Alarm because, against the rest of its ${parent}, it is below the watch line only` : r.state === 6 && parent ? html`; it is regional dimming because it is not clearly dimmer than the rest of its ${parent}` : ""}. The month is left out when the following ${meta.thresholds.hold_months} months are judged, so that a drop that persists does not become the new normal.</p>`);
  // can a reading of this unit be trusted at its own level?
  const drop = Number.isFinite(r.detectable) ? Math.round(100 * r.detectable) : null;
  const up = parent ? ` Its ${parent} is the safer reading.` : "";
  if (u.cells < MIN_CELLS) {
    out.push(html`<p><strong>Read this unit with care.</strong> It has <span class="dyn">${n0(u.cells)}</span> lit cell${u.cells === 1 ? "" : "s"}, under the ${MIN_CELLS} needed to judge a unit at its own level.${up}</p>`);
  } else if (r.judged === "yes") {
    out.push(html`<p>It is steady enough to be judged at its own level: it has ${n0(u.cells)} lit cells${hasTiers ? html`, and a one-month drop of about <span class="dyn">${drop}%</span> or more would cross its alarm line four times in five` : ""}.</p>`);
  } else if (r.judged === "no") {
    const text = drop <= 100 * MAX_DROP ? `just over ${(100 * MAX_DROP).toFixed(0)}%` : `about ${drop}%`;
    out.push(html`<p><strong>Read this unit with care.</strong> It has ${n0(u.cells)} lit cells but is too noisy to judge at its own level: only a one-month drop of <span class="dyn">${text}</span> or more would cross its alarm line four times in five, and the limit is ${(100 * MAX_DROP).toFixed(0)}%.${up}</p>`);
  } else {
    out.push(html`<p>Whether it is steady enough to be judged at its own level is not measured for this month: that needs an alarm line, which a monitor has from ${monthLabel(meta.months[FIRST[u.level].alarm])} at this level.</p>`);
  }
  // over the record: how often it has read low, and where its light has been heading
  const run = valueOf(u, "run", r.t), span = valueOf(u, "span", r.t);
  if (big(u) && run > 1) out.push(html`<p>This is month <span class="dyn">${run}</span> of Watch or Alarm in its current spell${span > run ? html`, which began ${span} months ago` : ""}. That is about the unit as a whole: it does not mean each place in it stayed dim.</p>`);
  if (big(u) && u.judgedWindows > 0) {
    out.push(html`<p>Over the record to ${monthLabel(meta.months[LAST])}, of <span class="dyn">${n0(u.judgedWindows)}</span> judged months it was in Watch or Alarm in <span class="dyn">${n0(u.lowWindows)}</span>${u.episodes ? html`, in ${n0(u.episodes)} spell${u.episodes === 1 ? "" : "s"}, the longest of ${u.longestRun} month${u.longestRun === 1 ? "" : "s"}` : ""}, and in regional dimming in <span class="dyn">${n0(u.regionalWindows)}</span>.</p>`);
  }
  if (u.longestUnseen > 1) out.push(html`<p>Its longest stretch without a usable reading was <span class="dyn">${u.longestUnseen}</span> months in a row.</p>`);
  out.push(html`<p>Its lit cells cover about <span class="dyn">${u.litKm2 < 10 ? u.litKm2.toFixed(1) : n0(Math.round(u.litKm2))} km2</span>. ${big(u) ? html`Then and now: ${newLitText(u)}.` : ""}</p>`);
  if (big(u)) {
    out.push(html`<p>Trend of its light: <span class="dyn">${trendText(u)}</span>.${u.trendCore !== null ? html` Counting only its ${n0(u.coreCells)} cells that were already lit in ${TR.years[0]}, the rate is <span class="dyn">${signed(u.trendCore)}%</span> a year (${signed(u.trendCoreLow)} to ${signed(u.trendCoreHigh)}): the first figure includes cells that are in the count because they grew.` : ""}</p>`);
  }
  return html`<div class="narrative">${out}</div>`;
}
```

<!-- below the map: one column, or two on a wide screen (the story of the map and of the selected unit, beside the list of units) -->
<div class="below">
<div class="below-col">

```js
// ---- the insight under the map (2): what the layer shown says this month. Always displays something.
display((() => {
  const when = monthLabel(meta.months[month]), calendar = when.split(" ")[0];
  const plural = LEVEL_PLURAL[shown], one = LEVEL_NAME[shown];
  const dyn = (text) => html`<span class="dyn">${text}</span>`;
  const chip = (u, text) => html`<button type="button" class="chip" title=${`Open ${u.name}`} onclick=${() => select(u.level, u.code)}>${u.name}<span>${text}</span></button>`;
  const chips = (label, list) => (list.length ? html`<p class="chips"><span class="chips-label">${label}</span>${list}</p>` : "");
  // the legend, counted: one bar, a segment per class of the map
  const countBar = (segments, noun) => {
    const total = d3.sum(segments, (d) => d.n);
    const shownSegments = segments.filter((d) => d.n > 0);
    return resize((width) => Plot.plot({
      width, height: 58, marginLeft: 0, marginRight: 0, marginTop: 4, marginBottom: 4, x: {axis: null, domain: [0, Math.max(1, total)]}, y: {axis: null},
      marks: [
        Plot.barX(shownSegments, Plot.stackX({x: "n", fill: (d) => d.colour, stroke: "#ffffff", strokeWidth: 0.6, order: null})),
        Plot.text(shownSegments.filter((d) => d.n / total >= 0.045), Plot.stackX({x: "n", text: (d) => n0(d.n), fill: "#0b0b0b", stroke: "#ffffff", strokeWidth: 3, fontSize: 11, fontWeight: 600, order: null})),
        Plot.tip(shownSegments, Plot.pointerX(Plot.stackX({x: "n", title: (d) => `${d.label}\n${n0(d.n)} ${noun} (${((100 * d.n) / total).toFixed(1)}%)`, order: null})))
      ]
    }));
  };
  const rampSegments = (ramp, values, head = []) => {
    const counts = ramp.colours.map(() => 0);
    for (const v of values) counts[classOf(ramp, v)]++;
    return [...head, ...ramp.colours.map((colour, i) => ({label: ramp.labels[i], colour, n: counts[i]}))];
  };
  const out = [];
  let bar = null, barTitle = `The ${plural} on the map, counted by colour`, side = null;

  // ---- the units
  if (variable !== "none") {
    const rowsNow = scopeUnits.map((u) => ({u, v: insight ? insight.value(u, month) : null, state: valueOf(u, "state", month)}));
    const STATIC_LAYER = variable === "trend" || variable === "newlit";
    const seenNow = rowsNow.filter((r) => fin(r.v));
    const point = insightSeries ? insightSeries[month] : null;
    const history = insightSeries ? insightSeries.filter((d) => d.value !== null) : [];
    const sameMonth = history.filter((d) => d.t !== month && meta.months[d.t].slice(5, 7) === meta.months[month].slice(5, 7));
    const typical = sameMonth.length >= 3 ? d3.median(sameMonth, (d) => d.value) : null;
    const ranked = point && point.value !== null && history.length > 12;
    const below = ranked ? d3.mean(history, (d) => +(d.value < point.value)) : null, above = ranked ? d3.mean(history, (d) => +(d.value > point.value)) : null;
    const since = history.length ? meta.months[history[0].t].slice(0, 4) : "";
    const rankText = below === null || variable === "usual" || variable === "radiance" ? ""
      : below >= 0.5 ? html` That is higher than in ${dyn(`${(100 * below).toFixed(0)}%`)} of the months since ${since}.`
      : above >= 0.5 ? html` That is lower than in ${dyn(`${(100 * above).toFixed(0)}%`)} of the months since ${since}.`
      : html` That is about what most months since ${since} give.`;
    // how much of the map this month's figures rest on: said whenever a fifth or more of the units were not observed
    const unseenNow = rowsNow.filter((r) => r.state === 0).length;
    const thin = !STATIC_LAYER && variable !== "seen" && variable !== "unseen" && unseenNow >= 0.2 * rowsNow.length
      ? html`<p><strong>Read this month with care.</strong> ${dyn(n0(unseenNow))} of the ${n0(rowsNow.length)} ${plural} of ${scopeName} were not observed (cloud, or too few clear nights), so the figures here describe the ${n0(rowsNow.length - unseenNow)} that were, and say nothing about the rest.</p>` : null;
    const grey = (n, label = "No value this month") => (n > 0 ? [{label, colour: NO_VALUE, n}] : []);
    // "usual" and "radiance" rise with the years, so a typical month or a rank among months would only restate growth
    const grows = variable === "usual" || variable === "radiance";
    const typicalText = typical === null || grows ? "" : html` A typical ${calendar} gives ${dyn(insight.fmt(typical))}.`;
    const sized = seenNow.filter((r) => big(r.u));
    const lowest = (list, k = 3) => list.slice().sort((a, b) => a.v - b.v).slice(0, k), highest = (list, k = 3) => list.slice().sort((a, b) => b.v - a.v).slice(0, k);

    if (variable === "status") {
      const judgedNow = rowsNow.filter((r) => r.state >= 3 && r.state <= 6), low = judgedNow.filter((r) => LOW.has(r.state));
      const trusted = low.filter((r) => judged(r.u, month) === "yes");
      out.push(html`<p>In ${dyn(when)}, ${dyn(n0(low.length))} of the ${dyn(n0(judgedNow.length))} ${plural} of ${scopeName} that could be judged read low: ${dyn(point && point.value !== null ? insight.fmt(point.value) : "no figure")}.${typicalText}${rankText} ${low.length ? html`Of the ${n0(low.length)}, ${dyn(n0(trusted.length))} ${trusted.length === 1 ? "is" : "are"} steady enough to judge at ${trusted.length === 1 ? "its" : "their"} own level; the rest are striped on the map.` : ""}</p>`);
      // the map's own colours; "not observed" is hatched on the map and drawn pale here, with its name in the tip
      bar = [3, 4, 5, 6, 7, 1, 0].map((k) => ({label: STATUS[k].label, colour: k === 0 ? "#c9ced6" : k === 7 ? "#0b0b0b" : STATUS[k].colour, n: rowsNow.filter((r) => r.state === k || (k === 1 && r.state === 2)).length}));
      side = chips("Low and steady enough to judge:", trusted.sort((a, b) => [5, 4, 6].indexOf(a.state) - [5, 4, 6].indexOf(b.state)).slice(0, 6).map((r) => chip(r.u, STATUS[r.state].label)));
    } else if (variable === "expected" || variable === "usual") {
      const under = seenNow.filter((r) => r.v < 85).length, over = seenNow.filter((r) => r.v >= 120).length;
      out.push(html`<p>In ${dyn(when)} the median ${one} of ${scopeName} gave ${dyn(point && point.value !== null ? insight.fmt(point.value) : "no figure")} of ${variable === "expected" ? "the light its own past leads one to expect" : "its usual light over the record"}. ${dyn(n0(under))} of ${n0(seenNow.length)} were under 85% and ${dyn(n0(over))} at 120% or more.${typicalText}${rankText}${variable === "usual" && history.length ? html` In ${meta.months[history[0].t].slice(0, 4)} the same figure stood near ${dyn(insight.fmt(d3.median(history.slice(0, 12), (d) => d.value)))}: the climb is growth, which is why this layer cannot say what is unusual.` : ""}</p>`);
      bar = [...rampSegments(RAMPS[variable], seenNow.map((r) => r.v)), ...grey(rowsNow.length - seenNow.length)];
      side = html`${chips("Dimmest:", lowest(sized).map((r) => chip(r.u, `${r.v.toFixed(0)}%`)))}${chips("Brightest:", highest(sized).map((r) => chip(r.u, `${r.v.toFixed(0)}%`)))}`;
    } else if (variable === "radiance") {
      const top = highest(sized, 1)[0], bottom = lowest(sized, 1)[0];
      out.push(html`<p>In ${dyn(when)} the lit cells of the median ${one} of ${scopeName} averaged ${dyn(point && point.value !== null ? insight.fmt(point.value) : "no figure")}.${top && bottom ? html` Between the brightest and the dimmest ${one} with enough lit cells the gap is a factor of ${dyn((top.v / bottom.v).toFixed(0))}: ${top.u.name} at ${top.v.toFixed(0)} nW, ${bottom.u.name} at ${bottom.v.toFixed(1)}.` : ""}${rankText} This compares how bright lit cells are, not how much light a place gives off in all.</p>`);
      bar = [...rampSegments(RAMPS.radiance, seenNow.map((r) => r.v)), ...grey(rowsNow.length - seenNow.length)];
      side = html`${chips("Brightest:", highest(sized).map((r) => chip(r.u, `${r.v.toFixed(0)} nW`)))}${chips("Dimmest:", lowest(sized).map((r) => chip(r.u, `${r.v.toFixed(1)} nW`)))}`;
    } else if (variable === "seen") {
      const observed = seenNow.filter((r) => r.v >= 100 * meta.thresholds.min_coverage).length;
      out.push(html`<p>In ${dyn(when)} the satellite got a usable look at ${dyn(n0(observed))} of the ${n0(seenNow.length)} ${plural} of ${scopeName}: ${dyn(point && point.value !== null ? insight.fmt(point.value) : "no figure")}.${typicalText}${rankText} Everything else on this page is only as good as this number: where it is low, no status means no news, not good news.</p>`);
      bar = rampSegments(RAMPS.seen, seenNow.map((r) => r.v));
      side = chips("Least seen:", lowest(seenNow, 5).map((r) => chip(r.u, `${r.v.toFixed(0)}%`)));
    } else if (variable === "unseen") {
      const gone = seenNow.filter((r) => r.v > 0), long = seenNow.filter((r) => r.v >= 3);
      out.push(html`<p>In ${dyn(when)}, ${dyn(n0(gone.length))} of the ${n0(seenNow.length)} ${plural} of ${scopeName} had no usable reading, and ${dyn(n0(long.length))} of them had gone three months or more without one (${dyn(point && point.value !== null ? insight.fmt(point.value) : "no figure")} of all).${typicalText}${rankText} Whatever happened in a place during a long silence cannot be read from this page.</p>`);
      bar = rampSegments(RAMPS.unseen, gone.map((r) => r.v), [{label: "Observed this month", colour: STATUS[3].colour, n: seenNow.length - gone.length}]);
      side = chips("Longest without a reading:", highest(gone, 5).map((r) => chip(r.u, `${r.v} months`)));
    } else if (variable === "run") {
      const inSpell = seenNow.filter((r) => r.v > 0), long = seenNow.filter((r) => r.v >= 2);
      const sizedAll = rowsNow.filter((r) => big(r.u)).length;
      out.push(html`<p>In ${dyn(when)}, ${dyn(n0(inSpell.length))} of the ${dyn(n0(seenNow.length))} ${plural} of ${scopeName} with enough lit cells and a reading this month ${inSpell.length === 1 ? "was" : "were"} in Watch or Alarm, and for ${dyn(n0(long.length))} it was at least the second month of the spell (${dyn(point && point.value !== null ? insight.fmt(point.value) : "no figure")}).${rankText} A single low month is common; a spell that lasts is the thing to look at.</p>`);
      bar = [...rampSegments(RAMPS.run, inSpell.map((r) => r.v), [{label: "Not in watch or alarm", colour: STATUS[3].colour, n: seenNow.length - inSpell.length}]),
             ...grey(sizedAll - seenNow.length, "No reading this month"), ...grey(rowsNow.length - sizedAll, `Under ${MIN_CELLS} lit cells`)];
      side = chips("Longest spells now:", highest(long, 5).map((r) => chip(r.u, `${r.v} months`)));
    } else if (variable === "trend") {
      const withTrend = scopeUnits.filter((u) => big(u) && trendSide(u) !== null).map((u) => ({u, v: u.trend - trendMedian(u), side: trendSide(u)}));
      const faster = withTrend.filter((r) => r.side === "faster"), slower = withTrend.filter((r) => r.side === "slower");
      out.push(html`<p>Over ${TR.years[0]} to ${TR.years[1]} the median ${one} of Indonesia grew by ${dyn(`${signed(trendMedian({level: shown}))}%`)} a year. Of the ${dyn(n0(withTrend.length))} ${plural} of ${scopeName} with a trend, ${dyn(n0(faster.length))} grew clearly faster than that and ${dyn(n0(slower.length))} clearly slower; for the other ${dyn(n0(withTrend.length - faster.length - slower.length))} the data cannot tell. Almost everything grew, so the map is about who pulled ahead and who fell behind, and it does not move with the month.</p>`);
      bar = [...rampSegments(RAMPS.trend, withTrend.filter((r) => r.side !== "unclear").map((r) => r.v), [{label: "Not clearly different from the median", colour: "#8a8f96", n: withTrend.length - faster.length - slower.length}]),
             ...grey(scopeUnits.length - withTrend.length, `No trend, or under ${MIN_CELLS} lit cells`)];
      side = html`${chips("Furthest ahead:", highest(faster).map((r) => chip(r.u, `${signed(r.u.trend)}% a year`)))}${chips("Furthest behind:", lowest(slower).map((r) => chip(r.u, `${signed(r.u.trend)}% a year`)))}`;
    } else if (variable === "newlit") {
      const sums = [1, 2, 3, 4].map((k) => d3.sum(scopeUnits, (u) => u.thenNow[k])), all = d3.sum(sums);
      const withShare = scopeUnits.filter((u) => big(u) && classed(u)).map((u) => ({u, v: (100 * u.thenNow[3]) / classed(u)}));
      const pc = (k) => dyn(`${((100 * sums[k]) / Math.max(all, 1)).toFixed(sums[k] / Math.max(all, 1) < 0.1 ? 1 : 0)}%`);
      out.push(html`<p>Of the ${dyn(n0(all))} cells of ${scopeName} that were lit at one end of the record or both (${TN.then[0]} to ${TN.then[1]}, ${TN.now[0]} to ${TN.now[1]}), ${pc(2)} emerged from dark, ${pc(1)} brightened from dim, ${pc(0)} were lit at both ends and ${pc(3)} faded. Among the cells this page counts, brightening from dim outnumbers emerging from dark many times over; the count favours it, since a cell must be lit on average over the whole record to be looked at. This does not move with the month.</p>`);
      bar = [...rampSegments(RAMPS.newlit, withShare.map((r) => r.v)), ...grey(scopeUnits.length - withShare.length, `No value, or under ${MIN_CELLS} lit cells`)];
      side = chips("Largest share of cells emerged from dark:", highest(withShare, 5).map((r) => chip(r.u, `${r.v.toFixed(1)}%`)));
    }
    if (thin && out.length) out.push(thin);
    // where the selected unit sits among the others
    if (unit && unit.level === shown && insight && fin(insight.value(unit, month)) && seenNow.length > 3 && variable !== "status") {
      const mine = insight.value(unit, month), lower = seenNow.filter((r) => r.v < mine).length;
      out.push(html`<p>${dyn(unit.name)} is at ${dyn(variable === "radiance" ? insight.fmt(mine) : variable === "unseen" || variable === "run" ? `${mine} month${mine === 1 ? "" : "s"}` : `${mine.toFixed(0)}%`)}: ${dyn(n0(lower))} of the other ${n0(seenNow.length - 1)} ${plural} are below it.</p>`);
    }
  }

  // ---- the lit cells
  let cellBar = null, cellTitle = null;
  if (cellMode !== "off") {
    const mine = prov && shown !== "province" ? prov.pos + 1 : 0;
    const inScope = (i) => mine === 0 || cellProvince[i] === mine;
    const layer = CELL_LAYERS[cellMode], N = cellIndex.length;
    if (cellMode === "faint") {
      let lit = 0, faintHere = 0;
      const litBy = new Map(), faintBy = new Map();
      for (let i = 0; i < N; i++) { if (inScope(i)) lit++; litBy.set(cellProvince[i], (litBy.get(cellProvince[i]) ?? 0) + 1); }
      for (let j = 0; j < faintIndex.length; j++) { if (mine === 0 || faintProvince[j] === mine) faintHere++; faintBy.set(faintProvince[j], (faintBy.get(faintProvince[j]) ?? 0) + 1); }
      cellBar = [{label: layer.labels[0], colour: layer.colours[0], n: lit}, {label: layer.labels[1], colour: layer.colours[1], n: faintHere}];
      cellTitle = "Lit cells and faint sources, counted";
      // where faint sources are most common beside the lit cells: provinces with at least 200 lit cells
      const ranked = units.province.map((p) => ({p, lit: litBy.get(p.pos + 1) ?? 0, faint: faintBy.get(p.pos + 1) ?? 0})).filter((r) => r.lit >= 200).sort((a, b) => b.faint / b.lit - a.faint / a.lit);
      const per100 = (r) => `${((100 * r.faint) / r.lit).toFixed(0)} per 100 lit cells`;
      out.push(html`<p>The faint sources: beside its ${dyn(n0(lit))} lit cells, ${scopeName} has ${dyn(n0(faintHere))} cells too dim to count as lit that still stand above their surroundings in half of their good months, ${dyn(((100 * faintHere) / Math.max(lit, 1)).toFixed(0))} for every 100 lit cells.${mine === 0 && ranked.length > 4 ? html` They are a small addition where light is dense and a large one where it is sparse: ${dyn(per100(ranked.at(-1)))} in ${ranked.at(-1).p.name}, ${dyn(per100(ranked[0]))} in ${ranked[0].p.name}.` : ""} They sit near the least the product registers, so no status here is judged from them, and whether each is a village, a mine, a plantation or a flare has not been checked.</p>`);
      side = html`${side ?? ""}${mine === 0 ? chips("Most faint sources for their lit cells:", ranked.slice(0, 5).map((r) => chip(r.p, per100(r)))) : ""}`;
    } else if (cellMode === "usual") {
      const light = [];
      for (let i = 0; i < N; i++) if (inScope(i)) light.push(cellUsual[i]);
      light.sort((a, b) => b - a);
      const total = d3.sum(light);
      let run = 0, k = 0;
      while (k < light.length && run < total / 2) run += light[k++];
      // the four classes the points are drawn in (see lightsData), brighter cream for brighter cells
      const breaks = [5, 15, 40].map((b) => b * meta.encoding.cells.usual_scale), colours = ["#8a8263", "#b9ad7d", "#e2d49b", "#fff4d6"], labels = ["under 5", "5 to 15", "15 to 40", "40 or more nW cm-2 sr-1"];
      const counts = colours.map(() => 0);
      for (const v of light) counts[breaks.reduce((n, b) => n + (v >= b ? 1 : 0), 0)]++;
      cellBar = colours.map((colour, i) => ({label: `Usual radiance ${labels[i]}`, colour, n: counts[i]}));
      cellTitle = "The lit cells, counted by their usual radiance";
      out.push(html`<p>The points of light: ${scopeName} has ${dyn(n0(light.length))} lit cells, and half of all their light comes from the brightest ${dyn(`${((100 * k) / Math.max(light.length, 1)).toFixed(1)}%`)} of them (${n0(k)} cells).</p>`);
    } else {
      const counts = layer.colours.map(() => 0);
      for (let i = 0; i < N; i++) if (inScope(i)) counts[cellMode === "thennow" ? cellThenNow[i] : cellMonth ? classOfCell(i, cellMode) : 0]++;
      const total = d3.sum(counts), pc = (n, of = total) => dyn(`${((100 * n) / Math.max(of, 1)).toFixed(0)}%`);
      cellBar = layer.colours.map((colour, i) => ({label: layer.labels[i], colour: colour === "#000000" ? "#0b0b0b" : colour, n: counts[i]}));
      cellTitle = `The lit cells, counted by ${layer.title}`;
      if (cellMode === "radiance") {
        const valued = total - counts[0];
        out.push(html`<p>Cell by cell in ${dyn(when)}: ${pc(valued)} of the ${n0(total)} lit cells of ${scopeName} had a usable value. Of those, ${pc(counts[5] + counts[6] + counts[7], valued)} read 10 nW or more and ${pc(counts[1] + counts[2], valued)} read under 2, cells that are lit on average but were faint or dark this month.</p>`);
      } else if (cellMode === "change") {
        const compared = total - counts[0], dimmer = counts[1] + counts[2] + counts[3], brighter = counts[5] + counts[6] + counts[7];
        out.push(html`<p>Cell by cell, ${dyn(when)} against the same month a year earlier: of the ${dyn(n0(compared))} cells of ${scopeName} that can be compared (${pc(compared)} of all), ${pc(brighter, compared)} are brighter than 115%, ${pc(counts[4], compared)} about the same and ${pc(dimmer, compared)} dimmer than 85%. ${brighter > dimmer ? "Brighter outnumbers dimmer, which is the ordinary state of a country whose lights are growing." : "Dimmer outnumbers brighter this month, which is not the ordinary state of a country whose lights are growing: check how well the two months were seen before reading anything into it."}</p>`);
      } else if (cellMode === "observations") {
        out.push(html`<p>Cell by cell in ${dyn(when)}: ${pc(counts[2] + counts[3])} of the lit cells of ${scopeName} had the four observations a value needs, ${pc(counts[3])} had ten or more, and ${pc(counts[0])} were not observed at all. A month is only a handful of clear nights, and here is how many.</p>`);
      } else if (cellMode === "thennow") {
        const compared = total - counts[0] - counts[5];
        out.push(html`<p>Cell by cell, ${TN.then[0]} to ${TN.then[1]} against ${TN.now[0]} to ${TN.now[1]}: of the ${dyn(n0(compared))} cells of ${scopeName} that can be compared, ${pc(counts[3], compared)} emerged from dark, ${pc(counts[2], compared)} brightened from dim, ${pc(counts[1], compared)} were lit at both ends and ${pc(counts[4], compared)} faded.</p>`);
      }
    }
  }
  if (!out.length) return html`<p class="fine" style="max-width:none;">Both layers are switched off: the map shows outlines only, and there is nothing to summarise.</p>`;

  // ---- every month, with this one marked (only for layers that change with the month)
  const timeline = insightSeries && insightSeries.some((d) => d.value !== null) ? resize((width) => clickToMonth(Plot.plot({
    width, height: 150, marginLeft: 44, marginRight: 12,
    x: {label: null}, y: {label: null, grid: true, nice: true, tickFormat: (v) => insight.fmt(v).replace(" nW", "")},
    marks: [
      Plot.lineY(insightSeries.filter((d) => d.value !== null), {x: "date", y: "value", stroke: "#898781", strokeWidth: 1}),
      Plot.dot(insightSeries.filter((d) => d.value !== null && meta.months[d.t].slice(5, 7) === meta.months[month].slice(5, 7)), {x: "date", y: "value", r: 2.5, fill: "#a2431a"}),
      Plot.ruleX([dates[month]], {stroke: "#0b0b0b", strokeOpacity: 0.4}),
      Plot.dot(insightSeries.filter((d) => d.t === month && d.value !== null), {x: "date", y: "value", r: 5, fill: "#a2431a", stroke: "#0b0b0b"}),
      Plot.tip(insightSeries.filter((d) => d.value !== null), Plot.pointerX({x: "date", y: "value", channels: {t: "t"}, title: (d) => `${monthLabel(meta.months[d.t])}\n${insight.fmt(d.value)}\n${n0(d.n)} ${plural} counted`}))
    ]
  }))) : null;
  return html`<div class="card insight">
    <h3>What this map says${STATIC || variable === "none" ? "" : `, ${when}`}</h3>
    <div class="narrative">${out}</div>
    <div class="grid grid-cols-2" style="gap:1.1rem; grid-auto-rows:auto; margin-top:0.4rem;">
      <div>${bar ? html`<h4>${barTitle}</h4>${countBar(bar, plural)}` : ""}${cellBar ? html`<h4>${cellTitle}</h4>${countBar(cellBar, "cells")}` : ""}${side ?? ""}</div>
      <div>${timeline ? html`<h4>Every month: ${insight.what}</h4>${timeline}<p class="fine" style="margin:0.2rem 0 0;">Rust points are every ${when.split(" ")[0]}; the large one is the month on the map. Click to move the map to a month.</p>` : ""}</div>
    </div>
  </div>`;
})());
```

```js
// ---- the panel for the selected unit: text and tiles. Always displays something, so nothing stale is left.
display(unit && rows ? (() => {
  const s = STATUS[now.state];
  const weak = LOW.has(now.state) && now.judged !== "yes";
  const judgedText = {yes: "judged at its own level", no: "not judged at its own level: read the level above", unknown: "not yet known whether it can be judged at its own level"}[now.judged];
  return html`<h2>${unit.name}, ${monthLabel(meta.months[month])}</h2>
  ${unitNarrative(unit, now)}
  <div class="grid grid-cols-4">
    <div class="card"><div class="tile-value"><span class="swatch" style=${swatchStyle(now.state, weak)}></span>${s.label}</div><div class="tile-label">Status this month${weak ? " (low confidence)" : ""}</div></div>
    <div class="card"><div class="tile-value">${Number.isFinite(now.anomaly) && now.state !== 7 ? `${(100 * Math.exp(now.anomaly)).toFixed(0)}%` : "No value"}</div><div class="tile-label">Light against what its own past leads one to expect (100% = as expected)</div></div>
    <div class="card"><div class="tile-value">${seenText(now.coverage, now.state)}</div><div class="tile-label">Of its usual light seen this month${Number.isFinite(now.nights) ? `, from a mean of ${now.nights.toFixed(1)} observations per cell` : ""}</div></div>
    <div class="card"><div class="tile-value">${n0(unit.cells)}</div><div class="tile-label">Lit cells the figures rest on; ${judgedText}</div></div>
  </div>`;
})() : html`<p class="fine" style="max-width:none;">No unit is selected: the table below lists every ${LEVEL_NAME[shown === "province" ? "province" : "district"]} this month. Click the map or use the menus to see one unit over time.</p>`);
```

```js
// ---- the months the charts below show: an overview of the whole record with a draggable window.
// This block must not read `timeRange`: it would be rebuilt during a drag (see timezoom.js).
display(unit && rows ? html`<div class="card time-card">
  <h3>Months shown in the charts below</h3>
  <p class="fine">The unit's light over the whole record. Drag the shaded window to move it, drag an edge to show more or fewer months (a year at least), double-click to show everything. The thin line is the month on the map.</p>
  ${resize((width) => timeSlider({width, dates: dates.slice(0, LAST + 1), values: rows.map((r) => (Number.isFinite(r.observed) ? r.observed : null)), marker: month,
    colours: {line: "#0b0b0b", fill: "#e1e0d9", axis: "#c3c2b7", ink: "#52514e", window: "#a2431a"}, onChange: setTimeRange}))}
</div>` : html`<span></span>`);
```

```js
// ---- the charts for the selected unit
display(unit && rows ? (() => {
  const [T0, T1] = timeRange;
  const inWindow = rows.filter((r) => r.t >= T0 && r.t <= T1); // the months inside the window of the overview above
  const span = [dates[T0], new Date(Date.UTC(dates[T1].getUTCFullYear(), dates[T1].getUTCMonth() + 1, 1))];
  const here = month >= T0 && month <= T1 ? [dates[month]] : []; // the month on the map, if it is in the window
  const seen = inWindow.filter((r) => Number.isFinite(r.observed));
  const flagged = seen.filter((r) => LOW.has(r.state));
  const lightPlot = (width) => clickToMonth(Plot.plot({
    width, height: 300, marginLeft: 48,
    x: {label: null, domain: span},
    y: {label: "% of usual light", grid: true, nice: true},
    marks: [
      ...(hasTiers ? [Plot.lineY(inWindow, {x: "date", y: "alarmLine", stroke: "#c53030", strokeWidth: 1.2, strokeDasharray: "1.5,3"}),
                      Plot.lineY(inWindow, {x: "date", y: "watchLine", stroke: "#8a5a00", strokeWidth: 1.2, strokeDasharray: "7,3"})]
                   : [Plot.lineY(inWindow, {x: "date", y: "watchLine", stroke: "#6b46c1", strokeWidth: 1.2, strokeDasharray: "7,3"})]),
      Plot.lineY(inWindow, {x: "date", y: "expected", stroke: "#898781", strokeWidth: 1.5}),
      Plot.lineY(inWindow, {x: "date", y: "observed", stroke: "#0b0b0b", strokeWidth: 1.2}),
      Plot.dot(seen, {x: "date", y: "observed", r: 1.6, fill: "#0b0b0b"}), // so that a single observed month between gaps is visible
      Plot.dot(flagged, {x: "date", y: "observed", r: 4.5, fill: (d) => STATUS[d.state].colour, stroke: "#0b0b0b", strokeWidth: 0.75,
                         symbol: (d) => (d.state === 5 ? "diamond" : d.state === 4 ? "circle" : "square")}),
      Plot.ruleX(here, {stroke: "#0b0b0b", strokeOpacity: 0.35}),
      Plot.dot(seen, Plot.pointerX({x: "date", y: "observed", r: 6, stroke: "#0b0b0b", fill: "none"})),
      Plot.tip(seen, Plot.pointerX({x: "date", y: "observed", channels: {t: "t"},
        title: (d) => `${monthLabel(meta.months[d.t])}\n${d.status}${LOW.has(d.state) && d.judged !== "yes" ? " (low confidence)" : ""}\nObserved ${d.observed.toFixed(0)}% of usual light${Number.isFinite(d.expected) ? `\nExpected ${d.expected.toFixed(0)}%` : ""}\n${seenText(d.coverage, d.state)} of its light seen`}))
    ]
  }));
  const key = (style, label) => html`<span><span class="key-line" style=${style}></span>${label}</span>`;
  const dot = (code, shape) => html`<span><span class="swatch" style=${swatchStyle(code) + shape}></span>${STATUS[code].label}</span>`;

  const band = inWindow.map((r) => ({...r, next: new Date(Date.UTC(r.date.getUTCFullYear(), r.date.getUTCMonth() + 1, 1))}));
  const stripPlot = (width) => clickToMonth(Plot.plot({
    width, height: 70, marginLeft: 12, marginRight: 12, marginTop: 6,
    x: {label: null, domain: span}, y: {axis: null},
    marks: [
      Plot.frame({stroke: "#e1e0d9"}),
      ...Object.keys(STRIP).filter((code) => STRIP[code]).map((code) => Plot.rect(band.filter((r) => r.state === +code), {x1: "date", x2: "next", y1: 0, y2: 1, fill: STRIP[code], inset: 0.3})),
      Plot.ruleX(here, {stroke: "#0b0b0b"}),
      Plot.tip(band, Plot.pointerX({x: "date", y: 0.5, channels: {t: "t"}, title: (d) => `${monthLabel(meta.months[d.t])}: ${d.status}`}))
    ]
  }));
  const seenPlot = (width) => clickToMonth(Plot.plot({
    width, height: 170, marginLeft: 44,
    x: {label: null, domain: span}, y: {label: "% of usual light seen", domain: [0, 100], grid: true},
    marks: [
      Plot.areaY(inWindow, {x: "date", y: (d) => 100 * d.coverage, fill: "#6f8598", fillOpacity: 0.35, curve: "step"}),
      Plot.lineY(inWindow, {x: "date", y: (d) => 100 * d.coverage, stroke: "#4f6475", strokeWidth: 1.2, curve: "step"}),
      Plot.ruleY([100 * meta.thresholds.min_coverage], {stroke: "#0b0b0b", strokeDasharray: "3,3"}),
      Plot.text([[dates[T0], 100 * meta.thresholds.min_coverage]], {text: ["minimum for a reading"], dy: -6, textAnchor: "start", fontSize: 11, fill: "#52514e"}),
      Plot.ruleX(here, {stroke: "#0b0b0b", strokeOpacity: 0.35}),
      Plot.tip(inWindow, Plot.pointerX({x: "date", y: (d) => 100 * d.coverage, channels: {t: "t"},
        title: (d) => `${monthLabel(meta.months[d.t])}\n${seenText(d.coverage, d.state)} of its usual light seen${Number.isFinite(d.nights) ? `\nmean ${d.nights.toFixed(1)} observations per cell` : ""}`}))
    ]
  }));
  return html`<div class="card">
    <h3>Light, observed and expected</h3>
    <p class="fine">The light of the unit's lit cells each month, as a percentage of its usual level over the record, on the cells that were seen that month. The grey line is what up to six of its own previous years lead one to expect for that month. Below a dashed line a reading counts as low. A gap is a month that was not observed well enough; a point at zero is a month that was seen with no detectable light. Click the chart to move the map to a month.</p>
    <div class="keys">${key("border-color:#0b0b0b", "Observed")}${key("border-color:#898781", "Expected from its own past")}
      ${hasTiers ? html`${key("border-top:2px dashed #8a5a00", "Watch line (long dashes)")}${key("border-top:2px dotted #c53030", "Alarm line (dots)")}` : key("border-top:2px dashed #6b46c1", "Line for regional dimming")}
      ${hasTiers ? html`${dot(4, "border-radius:50%;")}${dot(5, "transform:rotate(45deg) scale(0.8);")}` : ""}${dot(6, "")}</div>
    ${resize(lightPlot)}
  </div>
  <div class="grid grid-cols-2">
    <div class="card">
      <h3>Status, month by month</h3>
      <p class="fine">Blank: not observed. Light grey: seen but not judged. Slate: normal. Amber, red and violet: watch, alarm and regional dimming, as on the map. Black: seen, no light.</p>
      ${resize(stripPlot)}
    </div>
    <div class="card">
      <h3>How much of it was seen</h3>
      <p class="fine">The share of the unit's usual light that sat in cells with a usable value that month. Below the dashed line the month is "not observed", never "dark".</p>
      ${resize(seenPlot)}
    </div>
  </div>`;
})() : html`<span></span>`);
```

</div>
<div class="below-col">

```js
// ---- the units inside the selection (or of the country), this month. Always displays something.
display((() => {
  let lv, list;
  if (dist) { lv = "subdistrict"; list = units.subdistrict.filter((u) => Math.floor(u.code / 100) === dist.code); }
  else if (prov) { lv = "district"; list = units.district.filter((u) => u.province === prov.code); }
  else { lv = shown === "province" ? "province" : "district"; list = units[lv]; }
  const table = list.filter((u) => bundleOf(u)).map((u) => {
    const state = valueOf(u, "state", month), anomaly = valueOf(u, "anomaly", month);
    const weak = isWeak(u, month);
    return {Name: u.name, Status: STATUS[state].label + (weak ? ", low confidence" : ""), label: STATUS[state].label, state, weak,
            "Light vs expected": Number.isFinite(anomaly) && state !== 7 && state !== 0 ? Math.exp(anomaly) : null,
            "Light seen": seenText(valueOf(u, "coverage", month), state), "Lit cells": u.cells,
            "Months low": big(u) ? valueOf(u, "run", month) || null : null,
            "Trend over the record, % a year": big(u) ? u.trend : null,
            "Judged here": {yes: "yes", no: "no", unknown: "not known"}[judged(u, month)]};
  });
  if (!table.length) return html`<span></span>`;
  // low readings that can be trusted first, then the low-confidence ones, then everything else
  const rank = (r) => (LOW.has(r.state) ? (r.weak ? 3 : 0) + [5, 4, 6].indexOf(r.state) : 6 + [7, 3, 2, 1, 0].indexOf(r.state));
  const sorted = table.slice().sort((a, b) => rank(a) - rank(b) || a.Name.localeCompare(b.Name));
  const counts = d3.rollups(table, (v) => v.length, (d) => d.label).sort((a, b) => b[1] - a[1]);
  const weakLow = table.filter((r) => r.weak).length, allLow = table.filter((r) => LOW.has(r.state)).length;
  return html`<h2>${cap(LEVEL_PLURAL[lv])} of ${dist ? dist.name : prov ? prov.name : "Indonesia"}, ${monthLabel(meta.months[month])}</h2>
  <div class="card">
    <p class="fine">${n0(table.length)} ${LEVEL_PLURAL[lv]} with at least one lit cell: ${counts.map(([label, n]) => `${n0(n)} ${label.toLowerCase()}`).join("; ")}. ${allLow ? `Of the ${n0(allLow)} reading low (watch, alarm or regional dimming), ${n0(weakLow)} ${weakLow === 1 ? "is" : "are"} low confidence: the unit is too small or too noisy to judge at its own level, or that is not yet known. ` : ""}Low readings that can be judged are listed first.</p>
    ${Inputs.table(sorted, {
      columns: ["Name", "Status", "Light vs expected", "Light seen", "Months low", "Trend over the record, % a year", "Lit cells", "Judged here"],
      format: {"Light vs expected": (v) => (v === null ? "" : `${(100 * v).toFixed(0)}%`), "Months low": (v) => (v === null ? "" : v),
               "Trend over the record, % a year": (v) => (v === null ? "" : `${v > 0 ? "+" : ""}${v.toFixed(1)}`)},
      align: {"Light vs expected": "right", "Light seen": "right", "Lit cells": "right", "Months low": "right", "Trend over the record, % a year": "right"},
      rows: 14, select: false
    })}
  </div>`;
})());
```

</div>
</div>

## Reading this page

<details open>
<summary>What the statuses mean</summary>

- **Normal**: the unit's light is within what its own past explains.
- **Watch** and **Alarm**: the unit is dimmer than its own past explains, and clearly dimmer than the rest of its district or province. The two lines are set to be crossed in about 5% and 1% of months. Measured over 2018 to 2026 they were crossed in 5.1% and 1.1 to 1.3% of months across all districts and sub-districts, and in 5.7 to 5.8% and 1.3 to 1.4% across the ones that can be judged at their own level; single years ran from 0.1% to 3.4% at the alarm line. Those are crossings of the unit's own line; with the comparison against the surrounding area added, Watch or Alarm was shown in about 2% of judged months and Alarm in 0.3 to 0.4%. Where the comparison with the rest of the district or province is not available, the unit's own past decides alone, and the text under the map says so.
- **Regional dimming**: the unit is dimmer than its own past explains, but not clearly dimmer than the rest of its district or province. Year-to-year movement shared across an area looks like this. Smoke haze is a possible cause in some months, but that has not been checked against a fire or aerosol record. For a province no comparison is made, so a province only ever shows this status, never Watch or Alarm.
- **Low confidence (striped on the map)**: a watch, alarm or regional reading on a unit with fewer than ${MIN_CELLS} lit cells, or one whose readings vary too much from month to month, or one for which that is not yet measured. Read the district or province above it instead.
- **Seen, no light**: enough of the unit was seen and none of its usable cells showed detectable light. The product stores radiance under 0.5 nW cm-2 sr-1 as zero. Nearly all such readings since 2018 (2,262 of 2,364 at sub-district level) are in units of fewer than 20 lit cells.
- **Not judged**: the unit was seen, but too few of its earlier months were observed, overall or in that calendar month, for an expected value, or there is not yet enough history for thresholds. A monitor has no alarm line before ${monthLabel(meta.months[FIRST.district.alarm])} for districts and sub-districts, and provinces have no line before ${monthLabel(meta.months[FIRST.province.watch])}.
- **Not observed**: under half of the unit's usual light sat in cells with a usable value. This is never the same as dark.

</details>

<details>
<summary>What else the map can be coloured by</summary>

- **Against expected**: this month's light as a percentage of what up to six of the unit's own previous years lead one to expect. It is the number the statuses are judged from, without the judgement.
- **Against usual**: this month's light as a percentage of the unit's usual level over the whole record. It shows level and growth, not what is unusual.
- **How well seen**: the share of the unit's usual light that sat in cells with a usable value. It decides what every other figure is worth.
- **Months reading low**: how many months of its current spell a unit has been in Watch or Alarm. Regional dimming is not counted. A normal month, or a month seen with no light, ends a spell, and so do ${meta.variables.persistence.max_silent} months in a row without a reading; shorter gaps are skipped. Four spells in five last one month. Shown for units of at least ${MIN_CELLS} lit cells. The count is about the unit as a whole, not about each place in it.
- **Newly lit cells**: each lit cell is classed by its typical yearly radiance in ${TN.then[0]} to ${TN.then[1]} and in ${TN.now[0]} to ${TN.now[1]}: lit at both ends, brightened (dimly lit then, lit now), emerged (dark then, lit now) or faded. Dark is under ${TN.dark_max} nW cm-2 sr-1 and lit is at least ${TN.lit_min}. A unit is filled by the share of its cells that emerged. Across the country about 2% of lit cells emerged and about 39% brightened. Lit area is the area of the lit cells, about 0.21 km2 each near the equator.
- **Trend against the median**: the rate of change of the unit's light over ${TR.years[0]} to ${TR.years[1]}, in percent a year: the median slope between every pair of yearly values (Theil-Sen), where a year's value is the median of its months and needs at least ${TR.min_months_per_year} of them, and a unit needs at least ${TR.min_years} such years and ${MIN_CELLS} lit cells. The range is a ${(100 * TR.confidence).toFixed(0)}% interval widened for the way one year resembles the next. Units are coloured by whether that range lies above or below the median unit of their level. A second figure in the text counts only cells that were already lit in ${TR.years[0]}: it is lower, because the first includes cells that are counted only because they grew.

These rules were revised after a critique on 2026-11-23. None has been checked against events or records on the ground.

</details>

<details>
<summary>What the lit cells can show</summary>

The points on the map are the ${n0(meta.source.cells)} lit cells, each about 460 m across. "Lit cells show" changes what they are coloured by, and the month slider moves them.

- **Usual light**: the cell's mean radiance over the record. It does not change with the month.
- **Radiance this month**: the cell's radiance in classes, from no detectable light to ${CM.radiance.breaks.at(-1)} nW cm-2 sr-1 or more. Only values the product marks good quality with at least ${meta.thresholds.min_nights} observations are used; other cells are grey.
- **Change from a year earlier**: this month's radiance over the same calendar month a year earlier. It removes the time of year but not growth: where lights are growing, brighter than a year ago is the ordinary state.
- **Observations this month**: how many observations stand behind the month's value. It shows why a cell is grey in the other layers.
- **Faint sources too**: ${FAINT ? `adds, in blue, the ${n0(FAINT.cells)} cells that are too dim to count as lit (their median is ${FAINT.median_usual} nW cm-2 sr-1) but stand above their surroundings in at least half of their good months. They show where dim light is, mostly outside Java. They are not in any status: counting them made the monitor less sensitive everywhere. What they are has not been checked.` : "not available in this export."}
- **Then and now**: the cell's light in ${TN.then[0]} to ${TN.then[1]} against ${TN.now[0]} to ${TN.now[1]}: lit at both ends, brightened from dim, emerged from dark, or faded. It does not change with the month.

These describe single cells. No status is judged from them, and the sensor's view of the ground is wider than one cell, so neighbouring cells are not independent: read patterns, not single pixels. Each layer has a switch beside its menu: turn the unit fills off to read the cells on their own, or the cells off to read the fills.

</details>

<details>
<summary>What the figures rest on</summary>

- **Source**: NASA Black Marble monthly composites (VNP46A3, Collection 2), all view angles. A cell's monthly value is used when the product marks it good quality and it rests on at least ${meta.thresholds.min_nights} observations. No step removes fires or gas flares as such: a persistent flare stays in.
- **Lit cells**: land cells inside a coded admin unit whose mean radiance over their good-quality months is at least ${meta.source.domain.lit_min} nW cm-2 sr-1, with at least ${meta.source.domain.min_good_months} such months${meta.source.domain.source_contrast ? `, or which stand above their surroundings: brighter than a distance-weighted mean of the cells within ${meta.source.domain.source_radius_km} km by more than ${meta.source.domain.source_contrast} nW in at least ${(100 * meta.source.domain.source_share).toFixed(0)}% of those months. That second rule brings in dim, isolated settlements (${n0(meta.source.domain.source_cells)} cells); they are faint, so a unit made mostly of them is rarely steady enough to judge` : ""}: ${n0(meta.source.cells)} in all. ${meta.source.domain.look_ahead ? "Both rules use the whole record, so which cells count as lit uses knowledge a monitor would not have had at the time." : ""}
- **Expected light**: fitted to up to six of the unit's own previous years (at least 24 observed months), allowing for growth and for the time of year. Each month is judged with thresholds read from earlier years only.
- **Judged at its own level**: a unit with at least ${MIN_CELLS} lit cells for which a one-month drop of ${(100 * MAX_DROP).toFixed(0)}% or less would cross its alarm line four times in five.
- **Months**: ${monthLabel(meta.months[0])} to ${monthLabel(meta.months[LAST])}. About 40% of unit-months are not observed.
- **What this page cannot say**: why a unit is dim. A one-month composite also hides short events: a drop that lasts days can leave the month looking normal. A unit's figure describes its lit cells taken together, not each place in it.
- **Outlines** are simplified for display. No figure is computed from them.

</details>
