// A small overview of the whole record with a draggable window that chooses the months the charts show:
// drag the window to move it, drag an edge to widen or narrow it, double-click to show everything again.
//
// The span on show lives in `rangeStore`, a plain object. The slider reads it when it is built and writes it
// when the reader lets go; the page's reactive value is set through `onChange`. The slider must NOT be rebuilt
// because the range changed, or a drag would be cut off half way: the page builds it in a block that does not
// depend on the range.
import * as d3 from "npm:d3";

export const rangeStore = {value: null}; // [first month position, last month position], both shown

/**
 * @param width     pixels
 * @param dates     Date of the first day of every month of the record
 * @param values    one number per step, or null where there is none: drawn as the overview line
 * @param layers    instead of `values`: [{values, line, fill}], each drawn on its own vertical scale
 *                  (for series in different units; the overview shows their shapes, not their levels)
 * @param centred   true when a step is a whole year drawn at its middle: tick labels then sit under the middle
 * @param marker    month position to mark with a thin line (the month on the map), or null
 * @param minSpan   narrowest window allowed, in steps (months, or years when a step is a year)
 * @param label     what the window chooses, for screen readers
 * @param colours   {line, fill, axis, ink, window}
 * @param onChange  (firstMonth, lastMonth) => void, called when the reader lets go
 */
export function timeSlider({width, dates, values = null, layers = null, centred = false, marker = null, minSpan = 12, label = "Months shown in the charts", colours, onChange}) {
  const last = dates.length - 1;
  const height = 72, top = 6, bottom = 18, left = 48, right = 14;
  const x = d3.scaleLinear([0, last + 1], [left, width - right]);
  const svg = d3.create("svg").attr("width", width).attr("height", height).attr("role", "group")
    .attr("aria-label", `${label}. Drag the window to move it, drag an edge to change its length, double-click to show the whole record.`)
    .style("display", "block").style("max-width", "100%");

  const defined = (d) => d !== null && Number.isFinite(d);
  for (const layer of layers ?? [{values, line: colours.line, fill: colours.fill}]) {
    const y = d3.scaleLinear([0, Math.max(1e-9, d3.max(layer.values.filter(defined)) ?? 1)], [height - bottom, top]);
    if (layer.fill) svg.append("path").attr("fill", layer.fill).attr("d", d3.area().defined(defined).x((d, t) => x(t + 0.5)).y0(height - bottom).y1((d) => y(d))(layer.values));
    svg.append("path").attr("fill", "none").attr("stroke", layer.line).attr("stroke-width", 1.2)
      .attr("d", d3.line().defined(defined).x((d, t) => x(t + 0.5)).y((d) => y(d))(layer.values));
    // a value with a gap on both sides would draw nothing as a line: mark it with a dot
    svg.append("g").selectAll("circle").data(layer.values.map((v, t) => [v, t]).filter(([v, t]) => defined(v) && !defined(layer.values[t - 1]) && !defined(layer.values[t + 1])))
      .join("circle").attr("cx", ([, t]) => x(t + 0.5)).attr("cy", ([v]) => y(v)).attr("r", 1.5).attr("fill", layer.line);
  }
  svg.append("line").attr("x1", left).attr("x2", width - right).attr("y1", height - bottom).attr("y2", height - bottom).attr("stroke", colours.axis);

  // a tick and a label at each January, thinned so that labels do not collide
  const januaries = d3.range(0, last + 1).filter((t) => dates[t].getUTCMonth() === 0);
  const every = Math.max(1, Math.ceil(januaries.length / Math.max(2, Math.floor((width - left - right) / 44))));
  svg.append("g").selectAll("line").data(januaries).join("line")
    .attr("x1", (t) => x(t)).attr("x2", (t) => x(t)).attr("y1", top).attr("y2", height - bottom).attr("stroke", colours.axis).attr("stroke-opacity", 0.5);
  svg.append("g").selectAll("text").data(januaries.filter((_, i) => i % every === 0)).join("text")
    .attr("x", (t) => x(t + (centred ? 0.5 : 0))).attr("y", height - 4).attr("font-size", 10).attr("fill", colours.ink).attr("text-anchor", "middle")
    .text((t) => dates[t].getUTCFullYear());
  if (marker !== null) svg.append("line").attr("x1", x(marker + 0.5)).attr("x2", x(marker + 0.5)).attr("y1", top).attr("y2", height - bottom)
    .attr("stroke", colours.ink).attr("stroke-opacity", 0.6);

  const clamp = (a, b) => {
    const span = Math.max(Math.min(minSpan, last + 1), Math.min(last + 1, Math.round(b - a)));
    const from = Math.max(0, Math.min(last + 1 - span, Math.round(a)));
    return [from, from + span - 1];
  };
  const brush = d3.brushX().extent([[left, top], [width - right, height - bottom]]).handleSize(10);
  const g = svg.append("g").attr("class", "time-brush");
  const show = ([a, b]) => g.call(brush.move, [x(a), x(b + 1)]);
  const set = (a, b) => {
    rangeStore.value = [a, b];
    show([a, b]); // snap to whole months and to the minimum length
    onChange(a, b);
  };
  brush.on("end", (event) => {
    if (!event.sourceEvent) return;                        // our own brush.move, not the reader
    if (!event.selection) return show(rangeStore.value);   // a click outside the window would clear it: put it back
    set(...clamp(x.invert(event.selection[0]), x.invert(event.selection[1])));
  });
  g.call(brush);
  g.on("dblclick", () => set(0, last));
  g.select(".selection").attr("fill", colours.window).attr("fill-opacity", 0.16).attr("stroke", colours.window);
  g.selectAll(".handle").attr("fill", colours.window).attr("fill-opacity", 0.75).attr("rx", 3);
  show(rangeStore.value ?? [0, last]);
  return svg.node();
}
