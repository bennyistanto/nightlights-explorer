# Nightlights Explorer

**Indonesia after dark, by province, district and sub-district.**

Night-time lights over Indonesia from satellite: a Python pipeline (the
`ntl` package in `src/ntl/`) and a static dashboard (`site/`): a monthly
explorer and four case studies read from the daily files.

## What is here now

| Module | Does |
|---|---|
| `ntl.conventions` | Every product constant, with its source |
| `ntl.tiles` | The 10-degree Black Marble tile grid |
| `ntl.download` | Fetches NASA Black Marble files from LAADS: parallel, retry, resume, verified |
| `ntl.read` | Reads a layer in physical units, with missing values masked |
| `ntl.qa` | Decodes the quality flag and the cloud mask |
| `ntl.composite` | Fixed land mask and three-month composites from the monthly files |
| `ntl.zonal` | Cells to provinces, districts and sub-districts |
| `ntl.stack` | Reads a tile's monthly files into arrays for the lit cells, with a cache |
| `ntl.status` | A unit's light against its own past: expected value, anomaly, noise |
| `ntl.monitor` | Status of every unit of a level, month by month |
| `ntl.persistence` | How long a unit has read low, and how often before (run theory on its status) |
| `ntl.trend` | Rate of change of a unit's light over the record (Theil-Sen on yearly medians) |
| `ntl.firstlight` | Each lit cell's light at the start against the end of the record (lit at both ends, brightened, emerged, faded), counted per unit |
| `ntl.cellmaps` | Monthly classes for every lit cell (radiance, change from a year earlier, observations): the map's pixel layers |
| `ntl.sources` | Faint light sources: cells too dim to count as lit that stand above their surroundings (a map layer; no status uses them) |
| `ntl.events` | Daily case studies: each lit cell night by night against reference nights, a control area, and nights seen from a similar angle |
| `ntl.lightup` | Every land cell of a box, lit or not, in groups of nights around an event: which dark places lit up |
| `ntl.boundaries` | Small display outlines of the three levels from the detailed boundary file |
| `ntl.export` | Packs a monitor run into the files the dashboard loads |

## From files to the site's data

Four steps for the monthly explorer and two more for the case studies, each a command with `--help`. Paths are examples.

```powershell
python -m ntl.stack --root E:\temp\ntl --boundaries E:\temp\idn-bnd\idn_bnd_adm3.shp --out E:\temp\ntl\cache --tiles h28v09 h29v09
```

```powershell
python -m ntl.monitor --cache E:\temp\ntl\cache --out E:\temp\ntl\cache\run_monthly.npz
```

```powershell
python -m ntl.boundaries --boundaries E:\temp\idn-bnd\idn_bnd_adm3.shp --out E:\temp\ntl\cache\outlines
```

```powershell
python -m ntl.export --cache E:\temp\ntl\cache --run E:\temp\ntl\cache\run_monthly.npz --outlines E:\temp\ntl\cache\outlines --out site\data
```

1. `ntl.stack` reads each tile's monthly files into a cache of the lit
   cells inside an admin unit. A tile already cached is skipped unless
   `--force` is given. `--until` fixes the lit domain from the past.
2. `ntl.monitor` joins every cached tile and writes the status, for every
   month, of each province, district and sub-district that has a lit cell.
3. `ntl.boundaries` writes simplified outlines. They are for display only:
   no statistic reads them.
4. `ntl.export` packs the run, the cells and the outlines. The file
   formats are described at the top of `src/ntl/export.py` and in the
   `meta.json` it writes.

## Setup

Needs Python 3.11 or later with `httpx`, `numpy` and `h5py`; `rasterio` and
`geopandas` to map cells to admin units; `shapely` 2.1 or later for the
display outlines; `pytest` for the tests. Either install the package in your environment:

```
pip install -e . --no-deps
```

or run from the repo root with the source folder on the path:

```powershell
$env:PYTHONPATH = "src"
```

On Windows with a conda environment that is not activated, put the
environment's folders on `PATH` first, or NumPy may fail to load its
libraries:

```powershell
$e = "C:\path\to\envs\climate"
$env:PATH = "$e;$e\Library\mingw-w64\bin;$e\Library\usr\bin;$e\Library\bin;$e\Scripts;$env:PATH"
```

## Earthdata token

Downloads need a free NASA Earthdata Login token (listings do not).

1. Log in at https://urs.earthdata.nasa.gov and choose **Generate Token**.
2. Put it in a file named `.env` in the repo root, one line, nothing else on it:

   ```
   EARTHDATA_TOKEN=paste_the_token_here
   ```

`.env` is ignored by git. Tokens expire after 60 days (LAADS, "Download Files
Using EDL Tokens"). The environment variable `EARTHDATA_TOKEN` works too and
takes precedence.

## Downloading

```powershell
python -m ntl.download --help
```

List what a request would fetch, without a token:

```powershell
python -m ntl.download --product VNP46A2 --start 2018-08-01 --end 2018-08-10 --tiles h29v09 --root E:\temp\ntl --dry-run
```

Then run it without `--dry-run`. Files land under
`<root>\blackmarble\<product>\<year>\<day of year>\`, with one row per file in
`<root>\blackmarble\manifest.jsonl`. A rerun skips what is complete and
resumes what is partial. Keep `<root>` outside any synced folder.

Dates are the UTC dates in the file names. For a daily file over Indonesia,
date D is the night that begins on the evening of local date D.

### The case studies

The four case studies need daily files, which the monthly steps do not use:
`VNP46A2` (the nightly radiance) for each event's tile and nights, and
`VNP46A1` (which carries the view angle) for at least sixteen consecutive
nights of the same tile. Fetch both with `python -m ntl.download`. Without
`VNP46A1` the figures "against nights seen from a similar angle" are left
out and the pages that use them will not render those sentences.

```powershell
python -m ntl.events --event lombok2018 --root E:\temp\ntl --cache E:\temp\ntl\cache --out site\data
```

Run it once per event (`lombok2018`, `palu2018`, `nyepi2026`, `mudik2019`).

```powershell
python -m ntl.lightup --study mudik2019 --root E:\temp\ntl --out site\data --roads E:\temp\ntl\osm\java_roads_overpass.json
```

This writes the Mudik page's map of every land cell of Java. `--roads`
names a file for the roads of the box from OpenStreetMap (Open Database
Licence): it is read if it exists and fetched once if it does not.

### Faint sources

The explorer's layer of faint sources is optional. Build a second set of
stacks with `--sources`, in a folder of their own, and name it on export:

```powershell
python -m ntl.stack --root E:\temp\ntl --boundaries E:\temp\idn-bnd\idn_bnd_adm3.shp --out E:\temp\ntl\cache_sources --tiles h28v09 h29v09 --sources
```

```powershell
python -m ntl.export --cache E:\temp\ntl\cache --run E:\temp\ntl\cache\run_monthly.npz --outlines E:\temp\ntl\cache\outlines --faint E:\temp\ntl\cache_sources --out site\data
```

The statuses are always computed on the stacks built WITHOUT `--sources`:
counting the faint cells made the monitor less sensitive everywhere. A tile
already cached is skipped, so never mix the two kinds in one folder.

## The dashboard

The page is built with Observable Framework from `site/` (source) to
`dist/` (built). It reads the files written to `site/data`, so
run the steps above first: the first four for the monthly explorer, all of
them for the case studies. Needs Node 18 or later.

```powershell
npm install
```

```powershell
npm run dev
```

```powershell
npm run build
```

`npm run dev` serves a live preview; `npm run build` writes the static
site. `site/data`, `dist/` and `node_modules/` are not tracked by git.

## Tests

```powershell
python -m pytest -q
```

A few tests read real files if they are present under `E:\temp\ntl` (or the
folder named by `NTL_DATA_ROOT`) and are skipped otherwise. No test uses the
network or a token.
