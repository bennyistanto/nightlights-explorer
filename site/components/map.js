// The map: admin units filled by their status on a dark surface, with the lit
// cells drawn on top as points of light.
//
// Longitude and latitude are mapped linearly to the page (Indonesia straddles
// the equator, where this distorts little), so outlines need no spherical
// geometry and the lit cells fall on a regular grid.
//
// Zoom and pan: scroll or pinch, drag, or the buttons. The view is kept across
// redraws (the map is rebuilt when the month or the selection changes). When
// the focus changes (another province is opened), the map moves to it.
import * as d3 from "npm:d3";
import {SURFACE, LAND, fillOf, patternDefs, STATUS, swatchStyle, LEGEND} from "./palette.js";

const MAX_ZOOM = 80;
const BOUNDS = {west: 94.5, east: 141.5, south: -11.5, north: 6.5}; // the country with a margin, degrees
// One remembered view per group of maps: maps that share a `sync` name share one, every other map uses "single".
// (One view for all maps let Reset or a resize on one map drag unrelated maps with it.)
const views = new Map();
const viewOf = (name) => { if (!views.has(name)) views.set(name, {focus: undefined, k: 1, x: 0, y: 0}); return views.get(name); };
// Maps drawn with the same `sync` name move together: zoom or pan one and the others follow.
const synced = new Map(); // name -> Set of {wrap, apply}
const IDLE = "Hover a unit for its status. Click to select it. Scroll or drag to zoom and pan.";

/**
 * @param width      page width in pixels
 * @param land       GeoJSON features drawn as plain land under everything (the provinces)
 * @param units      [{feature, state, weak, fill, text, id}] the units of the level shown; fill, if given, is used
 *                   as it is (the other variables); otherwise the status decides, and state null = plain land
 *                   (no lit cell, or another province); weak = a low reading on a unit that cannot be judged at its own level
 * @param context    features outlined thinly on top (for example provinces over districts)
 * @param selected   features outlined in white, the last one boldest
 * @param lights     {lon: Float32Array, lat: Float32Array, level: Uint8Array, colours?: string[]} or null: the lit
 *                   cells. Without `colours`, level 0 to 3 is their USUAL brightness over the record, drawn as
 *                   points of light. With `colours` ("r, g, b" per level), level is a class drawn in that colour.
 * @param lines      [{coords: [[lon, lat], ...][], colour: "r, g, b", width, opacity?, dash?}] or null: line layers
 *                   (roads, for example) drawn above the lit cells, each a list of lines; widths are in screen pixels
 * @param describeCell (lon, lat) => text about the lit cell there, or null. Shown after the unit's text.
 * @param sync       a name: maps sharing it mirror each other's zoom and pan
 * @param focus      {key, bounds: [[west, south], [east, north]]} or null: where to move when the key changes
 * @param idle       the hint shown when the pointer is on no unit (default: about statuses)
 * @param onPick     (id or null) => void
 */
export function drawMap({width, land, units, context = [], selected = [], lights = null, lines = null, describeCell = null, focus = null, sync = null, label = null, idle = IDLE, onPick}) {
  const view = viewOf(sync ?? "single");
  const spanX = BOUNDS.east - BOUNDS.west;
  const spanY = BOUNDS.north - BOUNDS.south;
  const height = Math.round((width * spanY) / spanX);
  const sx = (lon) => ((lon - BOUNDS.west) / spanX) * width;
  const sy = (lat) => ((BOUNDS.north - lat) / spanY) * height;
  const path = d3.geoPath(d3.geoTransform({point(x, y) { this.stream.point(sx(x), sy(y)); }}));

  const svg = d3.create("svg").attr("width", width).attr("height", height).style("display", "block");
  svg.append("defs").html(patternDefs);
  const stage = svg.append("g");
  const line = (sel, colour, w, opacity = 1) => sel.attr("fill", "none").attr("stroke", colour).attr("stroke-width", w)
    .attr("stroke-opacity", opacity).attr("vector-effect", "non-scaling-stroke").attr("stroke-linejoin", "round");

  stage.append("g").selectAll("path").data(land).join("path").attr("d", path).attr("fill", LAND);
  // true when the unit fills are switched off: province borders are then drawn a little stronger than unit borders
  const outlinesOnly = units.some((d) => d.fill === "transparent");
  const hover = document.createElement("div");
  hover.className = "map-hover";
  hover.textContent = idle;
  let unitText = null; // set by the unit under the pointer; the cell's line is added on the way out
  stage.append("g").selectAll("path").data(units).join("path")
    .attr("d", (d) => path(d.feature))
    .attr("fill", (d) => d.fill ?? (d.state === null ? LAND : fillOf(d.state, d.weak)))
    // With the fills switched off the boundaries must carry the map: a soft white line, light enough
    // not to compete with the lit cells. With fills on, a dark hairline separates neighbours.
    .attr("stroke", (d) => (d.fill === "transparent" ? "rgba(255, 255, 255, 0.34)" : SURFACE))
    .attr("stroke-width", (d) => (d.fill === "transparent" ? 0.6 : 0.5)).attr("vector-effect", "non-scaling-stroke")
    .style("cursor", "pointer")
    .on("mousemove", (event, d) => { unitText = d.text; })
    .on("click", (event, d) => { event.stopPropagation(); onPick(d.id); });
  line(stage.append("g").style("pointer-events", "none").selectAll("path").data(context).join("path").attr("d", path),
       outlinesOnly ? "#ffffff" : "#0b0f14", outlinesOnly ? 0.9 : 1, outlinesOnly ? 0.6 : 0.9);
  // the selection: a white line on a dark casing, so that it shows on every fill
  const sel = stage.append("g").style("pointer-events", "none");
  line(sel.append("g").selectAll("path").data(selected).join("path").attr("d", path), "#0b0f14", 4)
    .attr("stroke-width", (d, i) => (i === selected.length - 1 ? 4.6 : 3.2));
  line(sel.append("g").selectAll("path").data(selected).join("path").attr("d", path), "#ffffff", 1.5)
    .attr("stroke-width", (d, i) => (i === selected.length - 1 ? 2.2 : 1.2));
  // textures keep their size on screen: the pattern is scaled down as the map is scaled up
  const patterns = svg.selectAll("pattern");
  const setPatternScale = (k) => patterns.attr("patternTransform", function () { return `${this.getAttribute("data-base")} scale(${1 / k})`; });

  // ---- lit cells on a canvas above the fills
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.style.cssText = "position:absolute;left:0;top:0;pointer-events:none;";
  const ctx = canvas.getContext("2d");
  const cellPx = (width / spanX) / 240; // one 15 arc-second cell at zoom 1
  const ALPHA = [0.28, 0.45, 0.7, 0.95];
  function drawLights(t) {
    ctx.clearRect(0, 0, width, height);
    if (lights) drawCells(t);
    if (lines) drawLines(t);
  }
  // line layers: a dark casing under each line so that it reads on bright cells and on dark land alike
  function drawLines(t) {
    ctx.lineJoin = "round";
    for (const pass of ["casing", "line"]) {
      for (const layer of lines) {
        ctx.setLineDash(layer.dash ?? []);
        ctx.strokeStyle = pass === "casing" ? `rgba(11, 15, 20, ${0.55 * (layer.opacity ?? 1)})` : `rgba(${layer.colour}, ${layer.opacity ?? 1})`;
        ctx.lineWidth = pass === "casing" ? layer.width + 1.6 : layer.width;
        ctx.beginPath();
        for (const coords of layer.coords) {
          let pen = false, wasOut = false;
          for (const [lon, lat] of coords) {
            const x = sx(lon) * t.k + t.x, y = sy(lat) * t.k + t.y;
            const out = x < -50 || x > width + 50 || y < -50 || y > height + 50;
            if (!pen || (out && wasOut)) ctx.moveTo(x, y); else ctx.lineTo(x, y);   // skip stretches wholly off the map
            pen = true;
            wasOut = out;
          }
        }
        ctx.stroke();
      }
    }
    ctx.setLineDash([]);
  }
  function drawCells(t) {
    const size = Math.max(1, cellPx * t.k);
    const dim = Math.min(1, (cellPx * t.k) / 2 + 0.05); // many cells share a pixel when zoomed out: keep the fills readable
    const classes = lights.colours ? lights.colours.length : 4;
    for (let level = 0; level < classes; level++) {
      if (lights.colours && lights.colours[level] === null) continue; // a class with no colour is not drawn
      // once a cell is several pixels wide it would hide the status under it: let the fill show through
      ctx.fillStyle = lights.colours
        ? `rgba(${lights.colours[level]}, ${Math.min(1, dim * 2.2 + 0.25) * (size > 3 ? 0.85 : 1)})`
        : `rgba(255, 244, 214, ${ALPHA[level] * dim * (size > 3 ? 0.4 : 1)})`;
      for (let i = 0; i < lights.lon.length; i++) {
        if (lights.level[i] !== level) continue;
        const x = sx(lights.lon[i]) * t.k + t.x;
        if (x < -size || x > width) continue;
        const y = sy(lights.lat[i]) * t.k + t.y;
        if (y < -size || y > height) continue;
        ctx.fillRect(x - size / 2, y - size / 2, size, size);
      }
    }
  }

  const wrap = document.createElement("div");
  wrap.style.cssText = `position:relative;width:${width}px;height:${height}px;overflow:hidden;cursor:grab;background:${SURFACE};border-radius:10px;touch-action:none;`;
  wrap.setAttribute("role", "group");
  wrap.setAttribute("aria-label", label ?? (describeCell
    ? "Map of Indonesia with admin units coloured by their night-lights status for the selected month. The menus above select a unit without a pointer, and the table below lists every unit shown."
    : "Map of lit cells, coloured as the legend beside it says. The text and charts around it give the same figures."));
  wrap.append(svg.node(), canvas);
  wrap.addEventListener("mouseleave", () => { unitText = null; hover.textContent = idle; });
  // Runs after the unit's own handler (the event bubbles up to here): the unit's line, then the cell's.
  wrap.addEventListener("mousemove", (event) => {
    if (event.target.closest(".map-buttons")) return;
    if (event.target === svg.node()) unitText = null; // sea
    let cellText = null;
    if (describeCell) {
      const r = wrap.getBoundingClientRect();
      const x = (event.clientX - r.left - view.x * width) / view.k;
      const y = (event.clientY - r.top - view.y * height) / view.k;
      cellText = describeCell(BOUNDS.west + (x / width) * spanX, BOUNDS.north - (y / height) * spanY);
    }
    hover.textContent = [unitText, cellText].filter(Boolean).join(" ") || "Sea, or outside Indonesia.";
  });
  svg.on("click", () => onPick(null));

  // ---- zoom and pan
  // where Reset returns to: the focus when the map has one, the whole country otherwise
  let home = d3.zoomIdentity;
  if (focus) {
    const [[w, s], [e, n]] = focus.bounds;
    const k = Math.max(1, Math.min(MAX_ZOOM, 0.8 / Math.max((sx(e) - sx(w)) / width, (sy(s) - sy(n)) / height)));
    home = d3.zoomIdentity.translate(width / 2 - (k * (sx(w) + sx(e))) / 2, height / 2 - (k * (sy(n) + sy(s))) / 2).scale(k);
  }
  const zoom = d3.zoom()
    .scaleExtent([1, MAX_ZOOM])
    .translateExtent([[0, 0], [width, height]])
    .extent([[0, 0], [width, height]])
    .filter((e) => !e.target.closest?.(".map-buttons") && (!e.button || e.type === "wheel"))
    .on("zoom", (e) => {
      const t = e.transform;
      stage.attr("transform", t);
      setPatternScale(t.k);
      drawLights(t);
      // a zoom the reader made here (not one mirrored from a sibling) is passed on, as fractions of each map's size
      if (sync && !mirroring) {
        for (const other of synced.get(sync) ?? []) {
          if (!other.wrap.isConnected) synced.get(sync).delete(other);
          else if (other.wrap !== wrap) other.apply(t.k, t.x / width, t.y / height);
        }
      }
      view.k = t.k;
      view.x = t.x / width;
      view.y = t.y / height;
      resetBtn.disabled = Math.abs(t.k - home.k) < 1e-6 && Math.abs(t.x - home.x) < 0.5 && Math.abs(t.y - home.y) < 0.5;
      outBtn.disabled = t.k <= 1;
      inBtn.disabled = t.k >= MAX_ZOOM;
    });
  const zsel = d3.select(wrap).call(zoom).on("dblclick.zoom", null);
  let mirroring = false; // true while this map is being moved by a sibling, so that it does not echo the move back
  if (sync) {
    if (!synced.has(sync)) synced.set(sync, new Set());
    synced.get(sync).add({wrap, apply: (k, fx, fy) => {
      mirroring = true;
      zsel.call(zoom.transform, d3.zoomIdentity.translate(fx * width, fy * height).scale(k));
      mirroring = false;
    }});
  }

  const button = (label, title, fn) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.title = title;
    b.setAttribute("aria-label", title);
    b.addEventListener("click", (e) => { e.stopPropagation(); fn(); });
    return b;
  };
  const inBtn = button("+", "Zoom in", () => zsel.transition().duration(150).call(zoom.scaleBy, 1.6));
  const outBtn = button("−", "Zoom out", () => zsel.transition().duration(150).call(zoom.scaleBy, 1 / 1.6));
  const resetBtn = button("Reset", focus ? "Reset the map to where it opened" : "Reset the map to the whole country", () => zsel.transition().duration(150).call(zoom.transform, home));
  const buttons = document.createElement("div");
  buttons.className = "map-buttons";
  buttons.append(inBtn, outBtn, resetBtn);
  wrap.append(buttons);

  // ---- where to look: the previous view, or the new focus when it changed
  const focusKey = focus ? focus.key : null;
  let start = d3.zoomIdentity.translate(view.x * width, view.y * height).scale(view.k);
  if (focusKey !== view.focus) {
    view.focus = focusKey;
    start = home;
  }
  // Placing the map is not a move by the reader: it is not passed on to siblings (which may not be on the page yet).
  mirroring = true;
  zsel.call(zoom.transform, start);
  mirroring = false;

  const root = document.createElement("div");
  root.append(wrap, hover);
  return root;
}

/**
 * Legend as plain HTML. Without `items`: a swatch and a label per status, then the striped and plain-land
 * entries. With `items` ([{style, label}]): those entries instead (the other variables).
 */
export function legend({lights, items = null}) {
  const root = document.createElement("div");
  root.className = "legend";
  const add = (style, label) => {
    const s = document.createElement("span");
    s.className = "legend-item";
    s.innerHTML = `<span class="swatch" style="${style}"></span>`;
    s.append(label);
    root.append(s);
  };
  if (items) {
    for (const item of items) add(item.style, item.label);
  } else {
    for (const code of LEGEND) add(swatchStyle(code), STATUS[code].label);
    add(swatchStyle(5, true), "Striped: watch, alarm or regional dimming on a unit too small or too noisy to judge at its own level");
  }
  add(`background:${LAND};`, "No lit cell, or outside what is shown");
  if (lights === true) add(`background: radial-gradient(circle, rgba(255,244,214,0.95) 1.5px, ${SURFACE} 2px) 0 0 / 7px 7px;`, "Lit cells, by their usual light over the record (not this month's)");
  if (Array.isArray(lights)) for (const item of lights) add(item.style, item.label);
  return root;
}

/** Bounding box [[west, south], [east, north]] of GeoJSON features, planar. */
export function boundsOf(features) {
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  const visit = (c) => {
    if (typeof c[0] === "number") {
      if (c[0] < w) w = c[0];
      if (c[0] > e) e = c[0];
      if (c[1] < s) s = c[1];
      if (c[1] > n) n = c[1];
    } else for (const part of c) visit(part);
  };
  for (const f of features) visit(f.geometry.coordinates);
  return [[w, s], [e, n]];
}
