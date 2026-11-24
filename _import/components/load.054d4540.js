// Loading the files written by ntl.export (python -m ntl.export).
// Binary files are gzip-compressed and little-endian. A server may or may not
// already have decompressed a .gz file in transit, so the gzip magic bytes are
// checked first. The layout of every file is described in meta.json, and this
// module reads the layout from there instead of repeating it.

const cache = new Map();

async function bytes(file) {
  const buf = new Uint8Array(await file.arrayBuffer());
  if (buf.length > 2 && buf[0] === 0x1f && buf[1] === 0x8b) {
    const stream = new Blob([buf]).stream().pipeThrough(new DecompressionStream("gzip"));
    return new Uint8Array(await new Response(stream).arrayBuffer());
  }
  return buf;
}

/** Typed array from a file. `key` must be unique per file; results are cached. */
export function loadTyped(key, file, Type) {
  if (!cache.has(key)) {
    cache.set(
      key,
      bytes(file).then((u8) => {
        if (u8.byteLength % Type.BYTES_PER_ELEMENT !== 0) throw new Error(`${key}: length is not a multiple of the element size`);
        return new Type(u8.buffer, u8.byteOffset, u8.byteLength / Type.BYTES_PER_ELEMENT);
      })
    );
  }
  return cache.get(key);
}

const TYPES = {uint8: Uint8Array, int16: Int16Array, uint16: Uint16Array};

/**
 * A status bundle: the columns of meta.encoding.columns one after another, each [window, unit].
 * Returns {windows, count, <column>: array}, where array[t * count + u] is the value of unit u
 * in window t. Columns with a missing code become Float32Array with NaN for "no value";
 * `state` and `flags` stay integers.
 */
export function decodeBundle(u8, meta, count) {
  const windows = meta.windows;
  const n = windows * count;
  const out = {windows, count};
  let at = 0;
  for (const col of meta.encoding.columns) {
    const Type = TYPES[col.dtype];
    if (!Type) throw new Error(`unknown column type ${col.dtype}`);
    const size = n * Type.BYTES_PER_ELEMENT;
    const stored = new Type(u8.slice(at, at + size).buffer); // slice copies, so the view is aligned
    at += size;
    if (col.missing === null) {
      out[col.name] = stored;
    } else {
      const values = new Float32Array(n);
      for (let i = 0; i < n; i++) values[i] = stored[i] === col.missing ? NaN : stored[i] / col.scale;
      out[col.name] = values;
    }
  }
  if (at !== u8.byteLength) throw new Error(`bundle has ${u8.byteLength} bytes, expected ${at}`);
  return out;
}

/** Load and decode one bundle of a level ("all" for provinces, a province code otherwise). */
export function loadBundle(files, meta, level, bundle) {
  const key = `${level}/${bundle}`;
  if (!cache.has(key)) {
    const entry = meta.level_detail[level].bundles[bundle];
    if (!entry) return Promise.resolve(null);
    cache.set(key, bytes(files[entry.file]).then((u8) => ({...decodeBundle(u8, meta, entry.count), first: entry.first})));
  }
  return cache.get(key);
}

export function loadJSON(key, file) {
  if (!cache.has(key)) cache.set(key, file.json());
  return cache.get(key);
}

/** One unit's values of one column, as a plain array over the windows. */
export function seriesOf(bundle, column, unit) {
  const out = new Array(bundle.windows);
  const a = bundle[column];
  for (let t = 0; t < bundle.windows; t++) out[t] = a[t * bundle.count + unit];
  return out;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
/** "2018-08" to "August 2018", and to a Date at the first of the month (UTC). */
export const monthLabel = (ym) => `${MONTHS[+ym.slice(5, 7) - 1]} ${ym.slice(0, 4)}`;
export const monthDate = (ym) => new Date(Date.UTC(+ym.slice(0, 4), +ym.slice(5, 7) - 1, 1));
/** A share (0 to 1) as a whole percentage, or a dash-free "no value". */
export const pct = (v, digits = 0) => (Number.isFinite(v) ? `${(100 * v).toFixed(digits)}%` : "no value");
