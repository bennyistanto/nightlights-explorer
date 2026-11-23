// Colours and wording, in one place so that the map, the charts, the legend and
// the text cannot drift apart.
//
// Every class scheme here is a ColorBrewer scheme (colorbrewer2.org, Cynthia
// Brewer), taken from d3-scale-chromatic so that the hex values are not retyped:
//   qualitative  Set1    the four statuses, and the then-and-now classes of cells
//   diverging    BrBG    ratios and trends: brown is dimmer or slower, teal brighter or faster
//   sequential   YlOrBr  radiance;  Blues  share seen;  OrRd  months reading low;
//                Purples months not observed;  BuGn  share of newly lit cells;  GnBu  observations
// The map's surface is dark, so where "more" should read as brighter (radiance,
// share seen, observations) the scheme is used in reverse order. That is the
// only change made to any scheme.
//
// Statuses (codes are conventions.STATUS_* of the pipeline; meta.status names
// them). Set1's grey, orange, red and purple, checked with the dataviz validator
// against a dark surface, all pairs: colour-vision-deficiency separation 13.9 at
// worst, normal vision 17.5. The states that are not a judgement are NOT carried
// by a hue: "seen, no light" is dark with pale dots, "not observed" is hatched,
// "not judged" is a flat dark grey. A watch, alarm or regional reading on a unit
// too small or too noisy to judge at its own level is drawn striped ("weak").
// A status never appears as colour alone: the legend, the hover line and the
// panel all name it.
import * as d3 from "npm:d3";

export const SURFACE = "#10151c"; // the map's sea
export const LAND = "#1c242e"; // land with no lit cell, or outside the level shown
export const INK = "#0b0b0b";
export const MUTED = "#52514e";
export const NO_VALUE = "#39424d";
const WEAK_BASE = "#3a4654";
const [SET1_RED, SET1_BLUE, , SET1_PURPLE, SET1_ORANGE, SET1_YELLOW, , , SET1_GREY] = d3.schemeSet1;

export const STATUS = {
  0: {key: "not_observed", label: "Not observed", colour: NO_VALUE, pattern: "hatch",
      says: "under half of its usual light sat in cells with a usable value this month (cloud, too few observations, or a month whose files are not complete). This is not darkness."},
  1: {key: "no_reference", label: "Not judged", colour: "#4a5767", pattern: null,
      says: "it was seen, but too few of its earlier months were observed, overall or in this calendar month, to say what to expect."},
  2: {key: "no_threshold", label: "Not judged", colour: "#4a5767", pattern: null,
      says: "an expected value exists, but there is not yet enough history to say how unusual a difference is."},
  3: {key: "normal", label: "Normal", colour: SET1_GREY, pattern: null,
      says: "its light is within what its own past explains."},
  4: {key: "watch", label: "Watch", colour: SET1_ORANGE, pattern: null,
      says: "it is below its watch line: dimmer than its own past explains, and clearly dimmer than the rest of its parent unit where that comparison exists."},
  5: {key: "alarm", label: "Alarm", colour: SET1_RED, pattern: null,
      says: "it is below its alarm line: much dimmer than its own past explains, and clearly dimmer than the rest of its parent unit where that comparison exists."},
  6: {key: "regional", label: "Regional dimming", colour: SET1_PURPLE, pattern: null,
      says: "it is dimmer than its own past explains, but not clearly dimmer than the rest of its parent unit. The cause is not identified.",
      saysProvince: "it is dimmer than its own past explains. A province has nothing to be compared with, so a low reading is always shown as regional dimming, never as Watch or Alarm. The cause is not identified."},
  7: {key: "dark", label: "Seen, no light", colour: SURFACE, pattern: "dots",
      says: "enough of it was seen and none of its usable cells showed detectable light (the product stores radiance under 0.5 as zero). Nearly all such readings are in units of fewer than 20 lit cells."}
};

/** The legend's entries, in reading order; states that share a look are listed once. */
export const LEGEND = [3, 4, 5, 6, 7, 1, 0];
/** States that say "dimmer than its own past explains": the ones that can be drawn striped. */
export const LOW = new Set([4, 5, 6]);

/**
 * Fill for an SVG shape: a colour, or a reference to a pattern defined by patternDefs.
 * `weak` is for a low reading on a unit that cannot be judged at its own level.
 */
export function fillOf(state, weak = false) {
  if (weak && LOW.has(state)) return `url(#st-weak-${state})`;
  return STATUS[state].pattern ? `url(#st-${STATUS[state].pattern})` : STATUS[state].colour;
}

// Each pattern carries its base transform in data-base; the map divides the pattern's scale by the
// zoom factor so that a texture keeps its size on screen.
const stripes = (id, colour) => `
  <pattern id="${id}" width="7" height="7" patternUnits="userSpaceOnUse" data-base="rotate(-45)" patternTransform="rotate(-45)">
    <rect width="7" height="7" fill="${WEAK_BASE}"></rect><rect width="2.5" height="7" fill="${colour}"></rect>
  </pattern>`;
export const patternDefs = `
  <pattern id="st-hatch" width="6" height="6" patternUnits="userSpaceOnUse" data-base="rotate(45)" patternTransform="rotate(45)">
    <rect width="6" height="6" fill="#262e38"></rect><rect width="1.5" height="6" fill="#5b6672"></rect>
  </pattern>
  <pattern id="st-dots" width="6" height="6" patternUnits="userSpaceOnUse" data-base="" patternTransform="">
    <rect width="6" height="6" fill="${SURFACE}"></rect><circle cx="3" cy="3" r="1.3" fill="#e9e7df"></circle>
  </pattern>
  ${stripes("st-weak-4", STATUS[4].colour)}${stripes("st-weak-5", STATUS[5].colour)}${stripes("st-weak-6", STATUS[6].colour)}`;

/** CSS background for a legend swatch of a state. */
export function swatchStyle(state, weak = false) {
  const s = STATUS[state];
  if (weak) return `background: repeating-linear-gradient(-45deg, ${s.colour} 0 2.5px, ${WEAK_BASE} 2.5px 7px);`;
  if (s.pattern === "hatch") return "background: repeating-linear-gradient(45deg, #5b6672 0 1.5px, #262e38 1.5px 6px);";
  if (s.pattern === "dots") return `background: radial-gradient(circle, #e9e7df 1.3px, ${SURFACE} 1.5px) 0 0 / 6px 6px;`;
  return `background: ${s.colour};`;
}

/** Colours of the status strip, on the light page: blank for "not observed", so that it never reads as a state. */
export const STRIP = {0: null, 1: "#d9d9d9", 2: "#d9d9d9", 3: STATUS[3].colour, 4: STATUS[4].colour, 5: STATUS[5].colour, 6: STATUS[6].colour, 7: "#0b0b0b"};

export const LEVEL_NAME = {province: "province", district: "district", subdistrict: "sub-district"};
export const LEVEL_PLURAL = {province: "provinces", district: "districts", subdistrict: "sub-districts"};
export const PARENT_NAME = {province: null, district: "province", subdistrict: "district"};

// ---- the other variables: classes, not a continuous scale, so that a colour can be read off the legend
const BRBG = d3.schemeBrBG[7];
const reversed = (scheme) => [...scheme].reverse();
const RATIO_LABELS = ["under 50%", "50 to 70%", "70 to 85%", "85 to 95%", "95 to 105%", "105 to 120%", "120% or more"];
export const RAMPS = {
  expected: {breaks: [50, 70, 85, 95, 105, 120], colours: BRBG, labels: RATIO_LABELS},
  usual: {breaks: [50, 70, 85, 95, 105, 120], colours: BRBG, labels: RATIO_LABELS},
  radiance: {breaks: [3, 5, 10, 20, 40], colours: reversed(d3.schemeYlOrBr[6]),
             labels: ["under 3", "3 to 5", "5 to 10", "10 to 20", "20 to 40", "40 or more nW cm-2 sr-1"]},
  seen: {breaks: [25, 50, 75, 90], colours: reversed(d3.schemeBlues[5]),
         labels: ["under 25%", "25 to 50%", "50 to 75%", "75 to 90%", "90% or more"]},
  unseen: {breaks: [2, 4, 7], colours: d3.schemePurples[5].slice(1), labels: ["1 month", "2 to 3", "4 to 6", "7 or more"]},
  run: {breaks: [2, 4, 7, 13], colours: d3.schemeOrRd[5], labels: ["1 month", "2 to 3", "4 to 6", "7 to 12", "13 or more"]},
  // trend is classed by its distance from the median unit of the level, in percentage points a year
  trend: {breaks: [-5, -2, -0.5, 0.5, 2, 5], colours: BRBG,
          labels: ["5 or more points slower", "2 to 5 slower", "0.5 to 2 slower", "within 0.5 of the median", "0.5 to 2 faster", "2 to 5 faster", "5 or more points faster"]},
  newlit: {breaks: [1, 2, 5, 10], colours: d3.schemeBuGn[5],
           labels: ["under 1%", "1 to 2%", "2 to 5%", "5 to 10%", "10% or more of its cells"]}
};
/** Class position of a value on a ramp: the number of breaks at or below it. */
export const classOf = (ramp, value) => ramp.breaks.reduce((n, b) => n + (value >= b ? 1 : 0), 0);
export const colourOf = (ramp, value) => ramp.colours[classOf(ramp, value)];

// ---- pixel layers: every lit cell (ntl.cellmaps and ntl.firstlight). Codes are the classes in meta.variables.
export const CELL_LAYERS = {
  radiance: {title: "radiance this month",
             colours: [NO_VALUE, "#000000", ...reversed(d3.schemeYlOrBr[6])],
             labels: ["No usable value this month", "No detectable light", "under 2", "2 to 5", "5 to 10", "10 to 20", "20 to 40", "40 or more nW cm-2 sr-1"]},
  change: {title: "change from the same month a year earlier",
           colours: [NO_VALUE, ...BRBG],
           labels: ["No comparison (one of the two months has no usable value)", "under half", "50 to 70%", "70 to 85%", "85 to 115%: about the same", "115 to 140%", "140 to 200%", "double or more"]},
  observations: {title: "observations this month",
                 colours: [NO_VALUE, ...reversed(d3.schemeGnBu[3])],
                 labels: ["No observation", "1 to 3 (too few for a value)", "4 to 9", "10 or more"]},
  // classes of firstlight.then_and_now: unknown, lit both, brightened, emerged, faded, dim both
  // lit cells in the map's own cream, faint sources in the light blue of ColorBrewer Paired: two kinds, not two amounts
  faint: {title: "faint sources beside the lit cells",
          colours: ["#fff4d6", d3.schemePaired[0]],
          labels: ["Lit cell: in the figures", "Faint source: on the map only, in no figure"]},
  thennow: {title: "light at the start and at the end of the record",
            colours: [NO_VALUE, SET1_GREY, SET1_YELLOW, SET1_RED, SET1_BLUE, NO_VALUE],
            labels: ["Too few years to compare", "Lit then and now", "Brightened: dim then, lit now", "Emerged: dark then, lit now", "Faded: lit then, not now", "Not lit at either end"]}
};
