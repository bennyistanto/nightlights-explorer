// The night-by-night explorer of a case study: a night slider, a map that opens a district and then a
// sub-district on a click (moving to each one's extent), and under it what the chosen night says about the
// selection. It follows the main page: one level at a time, and the text follows what is selected.
//
// Every unit figure comes from the event's units.json (ntl.events.unit_nights): the summed light of the unit's
// cells seen that night over their summed reference, the share of its reference light that was seen, and the
// share of its seen cells under half of their own reference. Nothing is computed here beyond counting units.
import * as d3 from "npm:d3";
import * as Plot from "npm:@observablehq/plot";
import {html} from "npm:htl";
import {drawMap, boundsOf} from "./map.js";

const UNCERTAIN = 0; // states of meta.unit.states: uncertain, down, same, up
const STATE_COLOUR = ["#c9ced6", "#8c510a", "#898781", "#35978f"]; // brown and teal as on the cell maps
const FEW_CELLS = 20; // under this a unit's figure is flagged; the main page's minimum for judging a unit (conventions.MIN_UNIT_CELLS)
const LEVEL_NAME ={district: "district", subdistrict: "sub-district"};
const LEVEL_PLURAL = {district: "districts", subdistrict: "sub-districts"};
const pct = (v, digits = 0) => `${(100 * v).toFixed(digits)}%`;
const n0 = (v) => v.toLocaleString("en");
const cellWord = (n) => (n === 1 ? "cell" : "cells");

/**
 * @param meta        the event's meta.json (dates, marks, unit thresholds, key)
 * @param units       the event's units.json: {district, subdistrict}, each {code, cells, ratio, adjusted, coverage, down, state}
 *                    with the nightly columns as [unit][night]
 * @param lon, lat    Float32Array: centre of each of the event's lit cells
 * @param levelAt     (night) => Uint8Array: the class of each cell that night, as drawn (an index into `colours`)
 * @param colours     "r, g, b" per class, null for a class that is not drawn
 * @param provinces   GeoJSON features drawn as land
 * @param districts   GeoJSON features of every district outline (only those in `units` are used)
 * @param subOutlines (province code) => promise of a feature collection of that province's sub-districts, or null
 * @param focus       {key, bounds}: where the map opens, and returns to when nothing is selected
 * @param start       the night shown first
 * @param scope       name of the whole area, for the breadcrumb and the text
 * @param noteAt      (night) => text under the slider about that night
 * @param legend      a node placed under the map, or null
 * @returns an element; it redraws itself when its width changes
 */
export function nightExplorer({meta, units, lon, lat, levelAt, colours, provinces, districts, subOutlines, focus, start = 0, scope, noteAt = () => "", legend = null}) {
  const D = meta.dates.length, U = meta.unit;
  const dates = meta.dates.map((s) => new Date(`${s}T00:00:00Z`));
  const day = (k, long = true) => dates[k].toLocaleDateString("en-GB", {day: "numeric", month: long ? "long" : "short", timeZone: "UTC"});
  const year = dates[0].getUTCFullYear();
  const at = {district: new Map(units.district.code.map((code, u) => [code, u])), subdistrict: new Map(units.subdistrict.code.map((code, u) => [code, u]))};
  const names = {district: new Map(districts.map((f) => [f.properties.code, f.properties.name])), subdistrict: new Map()};
  const shown = districts.filter((f) => at.district.has(f.properties.code));
  const nameOf = (level, code) => names[level].get(code) ?? `Unnamed (${code})`;
  // a unit on a night, or null when it has no lit cell with a reference
  const row = (level, code, k) => {
    const u = at[level].get(code);
    if (u === undefined) return null;
    const t = units[level];
    return {level, code, name: nameOf(level, code), cells: t.cells[u], ratio: t.ratio[u][k], adjusted: t.adjusted[u][k], coverage: t.coverage[u][k], down: t.down[u][k], state: t.state[u][k]};
  };
  const read = (r) => r !== null && r.state !== UNCERTAIN && r.ratio !== null; // seen well enough to be read

  let k = Math.max(0, Math.min(D - 1, start));
  let district = null, sub = null; // codes of what is open
  let subs = []; // sub-district features of the open district
  let message = "";

  // ---- the fixed parts
  const slider = html`<input type="range" min="0" max=${D - 1} step="1" value=${k} aria-label=${`Night, from ${day(0)} to ${day(D - 1)}`}>`;
  const labelEl = html`<div class="night-label" aria-live="polite"></div>`;
  const noteEl = html`<p class="fine" style="margin:0 0 0.7rem; max-width:none;"></p>`;
  const crumbEl = html`<p class="fine" style="margin:0 0 0.6rem; max-width:none; font-size:0.9rem;"></p>`;
  const mapEl = html`<div></div>`, insightEl = html`<div style="margin-top:1rem;"></div>`;
  const setNight = (next) => { k = Math.max(0, Math.min(D - 1, next)); slider.value = k; render(); };
  slider.addEventListener("input", () => setNight(+slider.value));
  const step = (label, title, by) => html`<button type="button" class="step" title=${title} aria-label=${title} onclick=${() => setNight(k + by)}>${label}</button>`;
  const root = html`<div class="card">
    <div class="when">${labelEl}<div class="steps">${step("‹", "One night back", -1)}${step("›", "One night forward", 1)}</div>${slider}</div>
    ${noteEl}${crumbEl}${mapEl}${legend ?? ""}${insightEl}
  </div>`;

  // ---- selecting: a district, then one of its sub-districts
  async function open(level, code) {
    message = "";
    if (level === null) { district = null; sub = null; subs = []; return render(); }
    if (level === "district") {
      district = code; sub = null; subs = [];
      render();
      const collection = await subOutlines(Math.floor(code / 100));
      if (district !== code) return; // another unit was opened while the outlines loaded
      subs = collection ? collection.features.filter((f) => Math.floor(f.properties.code / 100) === code) : [];
      for (const f of subs) names.subdistrict.set(f.properties.code, f.properties.name);
      return render();
    }
    if (!at.subdistrict.has(code)) { message = `${nameOf("subdistrict", code)} has no lit cell with a reference, so no figure.`; return render(); }
    sub = code;
    render();
  }
  const pick = (id) => { if (id) open(id.level, id.code); };

  // ---- the map
  const describe = (level, code) => {
    const r = row(level, code, k), head = `${nameOf(level, code)} (${LEVEL_NAME[level]})`;
    if (r === null) return `${head}: no lit cell with a reference.`;
    if (r.ratio === null) return `${head}: not seen that night.`;
    return `${head}: ${pct(r.ratio)} of its reference light on the ${pct(r.coverage)} of it that was seen${r.state === UNCERTAIN ? ", too little to read" : ""}. Click to open it.`;
  };
  const outline = (level) => (feature) => ({feature, id: {level, code: feature.properties.code}, state: null, weak: false, fill: "transparent", text: describe(level, feature.properties.code)});
  function drawTheMap(width) {
    const openFeature = district === null ? null : shown.find((f) => f.properties.code === district) ?? null;
    const subFeature = sub === null ? null : subs.find((f) => f.properties.code === sub) ?? null;
    const others = shown.filter((f) => f.properties.code !== district || !subs.length).map(outline("district"));
    const selected = [openFeature, subFeature].filter(Boolean);
    const node = drawMap({
      width, land: provinces, units: [...others, ...subs.map(outline("subdistrict"))], context: [], selected,
      lights: {lon, lat, level: levelAt(k), colours},
      focus: selected.length ? {key: `${focus.key}/${district}/${sub}`, bounds: boundsOf([selected.at(-1)])} : focus,
      sync: `explorer-${meta.key}`, // a view of its own: the other maps of the page keep theirs
      idle: "Hover a unit for its figure that night. Click a district to open it, then one of its sub-districts. Scroll or drag to zoom and pan.",
      label: `Map of ${scope} on one night: lit cells coloured by their light against their reference. The text below gives the figures of what is selected.`,
      onPick: pick
    });
    const hover = node.querySelector(".map-hover"); // the story maps of these pages hide theirs; this one is the control
    if (hover) hover.style.cssText = "display:block; font-size:0.85rem; color:#52514e; min-height:1.4em; margin-top:0.5rem;";
    return node;
  }

  // ---- the text and charts for the selection
  const dyn = (text) => html`<span class="dyn">${text}</span>`;
  const stateWord = (r) => (r.state === UNCERTAIN ? "too little seen to read" : ["", "down", "about the same", "up"][r.state]);
  // one dot per unit along its light that night; a click opens the unit
  function strip(rows, mine, width, level) {
    const seen = rows.filter(read).map((r) => ({...r, v: 100 * r.ratio}));
    if (seen.length < 2) return html`<p class="fine" style="margin:0;">Fewer than two ${LEVEL_PLURAL[level]} were seen well enough that night to be placed.</p>`;
    const me = mine ? seen.find((r) => r.code === mine.code) : null;
    const plot = Plot.plot({
      width, height: 84, marginLeft: 14, marginRight: 14, marginTop: 18, marginBottom: 34,
      x: {label: "% of its reference light that night", nice: true}, y: {axis: null, domain: [-1, 1]},
      marks: [
        Plot.ruleY([0], {stroke: "#e1e0d9"}), Plot.ruleX([100], {stroke: "#898781", strokeDasharray: "3,3"}),
        Plot.dot(seen.filter((r) => r !== me), {x: "v", y: 0, r: 4, fill: (r) => STATE_COLOUR[r.state], fillOpacity: 0.7, stroke: "#ffffff", strokeWidth: 0.5}),
        ...(me ? [Plot.dot([me], {x: "v", y: 0, r: 7, fill: STATE_COLOUR[me.state], stroke: "#0b0b0b", strokeWidth: 1.5}),
                  Plot.text([me], {x: "v", y: 0, dy: -15, text: "name", fontSize: 11, fontWeight: 600, fill: "#0b0b0b", stroke: "#ffffff", strokeWidth: 3})] : []),
        Plot.tip(seen, Plot.pointerX({x: "v", y: 0, title: (r) => `${r.name}\n${r.v.toFixed(0)}% of its reference light\n${pct(r.coverage)} of it seen, ${n0(r.cells)} lit cells`}))
      ]
    });
    plot.addEventListener("click", () => { if (plot.value && plot.value.code !== undefined && !(mine && plot.value.code === mine.code)) open(plot.value.level, plot.value.code); });
    plot.style.cursor = "pointer";
    return plot;
  }
  // a unit's light on every night: filled where it was seen well enough, hollow where it was not
  function nights(level, code, width) {
    const series = d3.range(D).map((n) => ({n, date: dates[n], ...row(level, code, n)})).filter((r) => r.ratio !== null).map((r) => ({...r, v: 100 * r.ratio}));
    const marks = (meta.marks ?? []).map((m) => dates[meta.dates.indexOf(m.date)]).filter(Boolean);
    const plot = Plot.plot({
      width, height: 200, marginLeft: 48, marginRight: 14,
      x: {label: null, domain: [dates[0], dates[D - 1]]}, y: {label: "% of its reference light", grid: true, nice: true},
      marks: [
        Plot.ruleY([100], {stroke: "#898781"}),
        Plot.ruleX(marks, {stroke: "#c53030", strokeDasharray: "2,3"}),
        Plot.ruleX([dates[k]], {stroke: "#0b0b0b", strokeOpacity: 0.4}),
        Plot.dot(series.filter((r) => r.state === UNCERTAIN), {x: "date", y: "v", r: 3, fill: "#ffffff", stroke: "#898781"}),
        Plot.dot(series.filter((r) => r.state !== UNCERTAIN), {x: "date", y: "v", r: (r) => (r.n === k ? 6 : 4), fill: (r) => STATE_COLOUR[r.state], stroke: "#0b0b0b", strokeWidth: (r) => (r.n === k ? 1.5 : 0.4)}),
        Plot.tip(series, Plot.pointerX({x: "date", y: "v", title: (r) => `${day(r.n)}\n${r.v.toFixed(0)}% of its reference light\n${pct(r.coverage)} of it seen${r.state === UNCERTAIN ? ": too little to read" : ""}`}))
      ]
    });
    plot.addEventListener("click", () => { if (plot.value && Number.isInteger(plot.value.n)) setNight(plot.value.n); });
    plot.style.cursor = "pointer";
    return plot;
  }
  function insight(width) {
    const half = width >= 720 ? Math.floor((width - 18) / 2) : width;
    const grid = (a, b) => html`<div style=${`display:grid; grid-template-columns:${width >= 720 ? "1fr 1fr" : "1fr"}; gap:1.1rem; align-items:start;`}><div>${a}</div><div>${b}</div></div>`;
    const h4 = (text) => html`<h4 style="font:600 0.78rem var(--sans-serif); margin:0.7rem 0 0.15rem; color:#52514e;">${text}</h4>`;
    const fine = (text) => html`<p class="fine" style="margin:0.2rem 0 0; max-width:none;">${text}</p>`;
    const text = (content) => html`<p style="max-width:none; margin:0 0 0.5rem; font-size:0.95rem; line-height:1.5;">${content}</p>`;
    const rule = `A unit is read only on a night when at least ${pct(U.min_coverage)} of its reference light was seen: down is under ${pct(U.down_ratio)} of the reference, up is ${pct(U.up_ratio)} or more. These figures use the plain reference nights; the viewing angle is not matched in them, and they say nothing about why a place was dim.`;
    const all = units.district.code.map((code) => row("district", code, k));
    const current = sub !== null ? row("subdistrict", sub, k) : district !== null ? row("district", district, k) : null;
    const title = html`<h3 style="margin-top:0;">${current ? current.name : scope}, ${day(k)} ${year}</h3>`;
    if (!current) {
      const seen = all.filter(read), count = (s) => seen.filter((r) => r.state === s).length;
      return html`${title}
        ${text(html`Of the ${dyn(n0(all.length))} districts with lit cells in ${scope}, ${dyn(n0(seen.length))} ${seen.length === 1 ? "was" : "were"} seen well enough to read on this night: ${dyn(n0(count(1)))} down, ${dyn(n0(count(2)))} about the same and ${dyn(n0(count(3)))} up against ${seen.length === 1 ? "its" : "their"} reference nights. No district is open: click one on the map, or a dot below.`)}
        ${h4("The districts that night")}${strip(all, null, width, "district")}
        ${fine(`One dot per district seen well enough, coloured brown for down, grey for about the same, teal for up. ${rule}`)}`;
    }
    const level = current.level;
    const siblings = level === "district" ? all : units.subdistrict.code.filter((code) => Math.floor(code / 100) === district).map((code) => row("subdistrict", code, k));
    const holder = level === "district" ? scope : nameOf("district", district);
    const others = siblings.filter((r) => read(r) && r.code !== current.code);
    const lower = read(current) ? others.filter((r) => r.ratio < current.ratio).length : 0, higher = read(current) ? others.filter((r) => r.ratio > current.ratio).length : 0;
    const figure = current.ratio === null
      ? html`${current.name} was not seen on this night: none of its ${dyn(n0(current.cells))} lit ${cellWord(current.cells)} had a reading. That is not the same as dark.`
      : html`${current.name} gave ${dyn(pct(current.ratio))} of its reference light, on the ${dyn(pct(current.coverage))} of that light that was seen${current.state === UNCERTAIN ? html`: ${dyn("too little to read")}, so the figure is shown and not to be leaned on` : html`, which reads as ${dyn(stateWord(current))}`}. ${dyn(pct(current.down))} of its cells seen were under ${pct(U.cell_down_ratio)} of their own reference. It has ${n0(current.cells)} lit ${cellWord(current.cells)} with a reference${current.cells < FEW_CELLS ? html`: ${dyn("few")}, so its figure swings on its own from night to night` : ""}.${current.adjusted !== null ? html` Divided by what the control did that night: ${dyn(pct(current.adjusted))}.` : ""}`;
    const place = read(current) && others.length ? html` Of the other ${n0(others.length)} ${LEVEL_PLURAL[level]} of ${holder} read that night, ${dyn(n0(lower))} ${lower === 1 ? "is" : "are"} lower and ${dyn(n0(higher))} higher.` : "";
    const children = level === "district" ? units.subdistrict.code.filter((code) => Math.floor(code / 100) === district).map((code) => row("subdistrict", code, k)) : [];
    return html`${title}
      ${text(html`${figure}${place}`)}
      ${grid(html`${h4(`Among the ${LEVEL_PLURAL[level]} of ${holder} that night`)}${strip(siblings, current, half, level)}${fine(`The large dot is ${current.name}. Click a dot to open that ${LEVEL_NAME[level]}.`)}
                  ${children.length ? html`${h4(`Its ${n0(children.length)} sub-districts that night`)}${strip(children, null, half, "subdistrict")}${fine("Click a dot, or the map, to open a sub-district.")}` : ""}`,
             html`${h4(`${current.name}, night by night`)}${nights(level, current.code, half)}${fine("Filled points are nights it was seen well enough to read, hollow ones nights it was not; no point is a night it was not seen at all. The red lines are the marked events. Click a night to move the map there.")}`)}
      ${fine(rule)}`;
  }

  // ---- drawing
  let width = 0;
  function render() {
    if (!width) return;
    labelEl.textContent = `${day(k)} ${year}`;
    slider.setAttribute("aria-valuetext", `${day(k)} ${year}`);
    noteEl.textContent = noteAt(k);
    const crumb = (label, go) => html`<a role="button" tabindex="0" style="cursor:pointer;" onclick=${go} onkeydown=${(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } }}>${label}</a>`;
    crumbEl.replaceChildren(html`${district === null ? html`<strong>${scope}</strong>` : crumb(scope, () => open(null))}
      ${district !== null ? html` › ${sub === null ? html`<strong>${nameOf("district", district)}</strong>` : crumb(nameOf("district", district), () => open("district", district))}` : ""}
      ${sub !== null ? html` › <strong>${nameOf("subdistrict", sub)}</strong>` : ""}
      ${message ? html`<span style="margin-left:0.6rem;">${message}</span>` : ""}`);
    mapEl.replaceChildren(drawTheMap(width));
    insightEl.replaceChildren(insight(width));
  }
  const observer = new ResizeObserver(([entry]) => {
    const next = Math.floor(entry.contentRect.width);
    if (next > 0 && next !== width) { width = next; render(); }
  });
  observer.observe(mapEl);
  return root;
}
