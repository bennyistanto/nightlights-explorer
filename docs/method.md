# Method

How the dashboard's numbers are made, from the download to the page, written
so that someone holding the same files can repeat it. It also records what
was tried and dropped along the way, because several of the choices only make
sense once the failed alternatives are known.

Each statement here is either a property of the files (read from them),
computed by a named module of this repository, or cited. Choices that are
this project's own, and not a published standard, are marked **choice**.
Figures were measured on the record to October 2026.

Contents: [1 Data](#1-data) · [2 From files to cells](#2-from-files-to-cells) ·
[3 The monthly status](#3-the-monthly-status) ·
[4 Other things said about a unit](#4-other-things-said-about-a-unit) ·
[5 Things said about a cell](#5-things-said-about-a-cell) ·
[6 The case studies](#6-the-case-studies) ·
[7 What was tried and changed](#7-what-was-tried-and-changed) ·
[8 How it was checked](#8-how-it-was-checked) ·
[9 What reaches the browser](#9-what-reaches-the-browser) ·
[10 Known limits](#10-known-limits) · [11 Symbols](#11-symbols) ·
[12 Running it](#12-running-it) · [13 Practices worth keeping](#13-practices-worth-keeping)

## 1. Data

### 1.1 Products

All night-time light comes from NASA Black Marble, Collection 2, made from
the Day/Night Band of the VIIRS instrument on the Suomi NPP satellite. The
satellite passes at about 01:30 local time.

| Product | Step | Layer used | Used for |
|---|---|---|---|
| `VNP46A3` | monthly composite | `AllAngle_Composite_Snow_Free`, with `_Num` (observations) and `_Quality`; `Land_Water_Mask` | the explorer |
| `VNP46A2` | daily | `DNB_BRDF-Corrected_NTL`, with `Mandatory_Quality_Flag` and `Latest_High_Quality_Retrieval` | the case studies |
| `VNP46A1` | daily | `Sensor_Zenith` | the viewing angle of each night |

Radiance is in nW cm⁻² sr⁻¹ throughout (written nW below). A grid cell is 15
arc-seconds, about 463 m along a meridian. The sensor's footprint is wider
than a cell, so neighbouring cells are not independent: patterns can be
read, single cells cannot.

What the product corrects for and what it does not, as its user guide states
it: it corrects for the atmosphere, terrain, moonlight and stray light and
removes cloud. It does not correct for vegetation, and nothing read says it
removes fires, gas flares, fishing boats or lightning. The monthly composite
sets radiance under 0.5 nW to zero, so a zero there means "below the floor",
not "measured zero". The guide also warns of a strong effect of the viewing
angle on daily values; section 6.4 measures it.

### 1.2 Tiles and files

The product comes in tiles of 10 by 10 degrees, 2,400 cells on a side.
Indonesia needs eleven tiles with lit land:
`h27v08 h27v09 h28v08 h28v09 h29v08 h29v09 h30v08 h30v09 h30v10 h31v09 h32v09`.

| What | Files | Size |
|---|---|---|
| `VNP46A3`, 11 tiles, January 2012 to November 2026 (179 months) | 1,969 | 78.8 GB |
| `VNP46A2`, the nights of the four case studies | 42 to 50 per event and tile | about 0.8 GB per 42 nights |
| `VNP46A1`, at least 16 consecutive nights per tile and period | 48 MB each | 3.7 GB in all |

A national daily archive would be about 3.9 TB, which is why daily data is
used for chosen events only (**choice**).

### 1.3 Download

`ntl.download` lists a product's files from NASA's LAADS archive and fetches
them in parallel. It was written for an unreliable connection:

- a file is written under a temporary name and renamed only when complete,
  so a half file never carries a real name;
- a partial file is resumed, not restarted;
- each file is verified against the size and checksum the archive lists;
- the archive sometimes answers 404 or 502 for a file it lists and succeeds
  on the next try, so those answers are retried and not taken as "absent";
- one line per file goes to a manifest, so a rerun skips what is complete.

The access token is read from a local file and never written to a log, a
manifest or the repository.

## 2. From files to cells

### 2.1 Reading a value: three states, never two

`ntl.read` returns a layer in physical units with the fill value masked.
`ntl.qa` decodes the quality layers. Three states are kept apart everywhere,
because the whole monitor depends on not confusing them:

- **observed and usable**: a retrieval the rule accepts;
- **observed and rejected**: a retrieval exists but the rule refuses it;
- **not observed**: no retrieval. This is never "dark".

For the monthly composite the quality layer reads 0 good, 1 poor, 2 gap
filled, 255 fill. A **usable** monthly value is one with quality 0 and at
least 4 observations (**choice**). Two properties of the files matter:

- a gap-filled cell holds a number although nothing was observed that month
  (its observation count is 0). It is a memory, not an observation, and can
  never show an outage, so gap-filled values are never used;
- "poor" does not simply mean "under 4 observations": some cells with 4 or
  more are marked poor, so both the flag and the count are tested.

For the daily product only flag 0 (high quality) is used, with one stated
exception in section 6.3.

### 2.2 One land mask per tile

The land and water layer inside a monthly file is fill exactly where that
month's quality is fill, so a mask taken from one file shrinks in cloudy
months. `ntl.composite` therefore takes, for each cell, the commonest class
over every month of the record, and uses that single mask. Coastal cells are
left out of the status domain.

### 2.3 Which cells count as lit

The **lit domain** (`ntl.stack.lit_domain`) is the set of cells the statuses
are computed on (**choice**):

- land, inside a coded province;
- at least 12 good months in the record;
- a mean radiance over those months of at least 2 nW.

It holds 268,834 cells, 83% of them in the two tiles that cover Java and
southern Sumatra. The mean is taken over the whole record, which is
look-ahead: a monitor running in 2018 would not have known which cells would
be lit by 2026. The size of it is known for one tile: `h29v09` has 68,529
domain cells from the months before 2018 against 117,400 from the whole
record. The code can fix the domain from the past (`--until`); the published
run does not.

Each cell's mean over its good months is kept as its **usual radiance**
$\bar L_i$.

### 2.4 Admin units

A cell belongs to the unit whose polygon contains the cell's centre. Units
are identified at three levels by codes that nest by prefix: province (2
digits), district (4) and sub-district (6). A code of 0 at one level means
the area is held by the level above. 38 provinces, 490 districts and 4,479
sub-districts have at least one lit cell.

## 3. The monthly status

The status answers one question for a unit $u$ in a month $t$: is it dimmer
than its own past says it should be? It is this project's own design
(**choice**), built in `ntl.status` and `ntl.monitor`.

### 3.1 The unit's light, like for like

Let $V_u(t)$ be the cells of unit $u$ with a usable value in month $t$, and
$L_i(t)$ the radiance of cell $i$. The unit's index is its light over the
usual light of the same cells, on a log scale:

$$I_u(t) = \ln \frac{\sum_{i \in V_u(t)} L_i(t)}{\sum_{i \in V_u(t)} \bar L_i}$$

Dividing by the usual light of the cells that were seen, not of all cells,
makes months comparable when different cells are visible: a month that sees
only the bright centre of a town is not read as a bright month.

The share of the unit that was seen is weighted by usual light:

$$c_u(t) = \frac{\sum_{i \in V_u(t)} \bar L_i}{\sum_{i \in u} \bar L_i}$$

If $c_u(t) < 0.5$ the unit is **not observed** that month and has no index.
If enough was seen and the summed light is zero, the unit is **seen, no
light**, a state of its own.

### 3.2 What its own past predicts

For month $t$ the expected index $\hat I_u(t)$ comes from a robust regression
fitted to the unit's own earlier months only, at most 72 of them, needing at
least 24 observed months and at least 2 in the target's calendar month:

$$I_u(s) = \beta_u\,s + \alpha_{u,m(s)} + \varepsilon_s, \qquad s < t$$

One slope $\beta_u$ carries growth; one level $\alpha_{u,m}$ per calendar
month $m$ carries the time of year. The fit is by iteratively reweighted
least squares with Huber weights (tuning constant 1.345, 20 passes), so a
few hazy or half-seen months do not move it. With one level per month the
weighted fit has a closed form: with $\bar s_m$ and $\bar I_m$ the weighted
means of time and index within calendar month $m$,

$$\beta = \frac{\sum_s w_s\,(s - \bar s_{m(s)})\,(I(s) - \bar I_{m(s)})}{\sum_s w_s\,(s - \bar s_{m(s)})^2}, \qquad \hat I(t) = \bar I_{m(t)} + \beta\,(t - \bar s_{m(t)})$$

The **anomaly** is observed minus expected, and its exponential is the ratio
the page shows as "light against expected":

$$a_u(t) = I_u(t) - \hat I_u(t), \qquad e^{a_u(t)} = \frac{\text{observed light}}{\text{expected light}}$$

### 3.3 How noisy the unit is

Each unit has its own scale, from its own earlier anomalies (at least 24):

$$\sigma_u(t) = 1.4826 \cdot \operatorname{median}_{s<t} \left| a_u(s) - \operatorname{median}_{s<t} a_u(s) \right|$$

A month built from few observations is noisier, so the scale is multiplied
by a factor $f_k$ for the class $k$ of the month's mean observations per
cell (under 8, 8 to 11, 12 to 15, 16 or more). The factors are read each
January from earlier years only.

### 3.4 Thresholds from the past, pooled

A normal distribution is the wrong yardstick: the anomalies have heavier
tails, and in the backtest a normal threshold aimed at 1% gave about 1.6%.
So the threshold is a quantile of the standardised anomalies $a/\sigma$
pooled over every unit of the level, from earlier years only:

$$q_r(t) = \text{the } r \text{ quantile of } \left\{ \frac{a_v(s)}{\sigma_v(s)} : v \text{ at this level},\ \text{year}(s) < \text{year}(t) \right\}$$

with $r = 0.05$ for watch and $r = 0.01$ for alarm. A pool must hold at
least 300 values and at least 10 expected beyond the quantile, so 1,000
values for the 1% rate. That second rule was added after a first province
threshold, read from 452 values, gave an 11.9% alarm rate in its first year.

A unit is low against its own past when

$$a_u(t) < q_r(t)\,\sigma_u(t)$$

### 3.5 Its own, or the area's?

Haze, a wet season or a change in the product moves a whole region at once.
To tell a unit's own dimming from shared dimming, the same anomaly is
computed for the **rest of its parent**: the other cells of its district
(for a sub-district) or province (for a district), formed by subtracting the
unit's sums from the parent's so that it uses the same cells and weights.

$$d_u(t) = a_u(t) - a_{\text{rest}(u)}(t)$$

$d_u$ gets its own scale and its own pooled thresholds, exactly as above.

### 3.6 The status

| Status | Condition |
|---|---|
| Not observed | under half of the unit's usual light was seen |
| Not judged | seen, but too little past for an expected value, a scale or a threshold |
| Normal | not below the watch threshold |
| Watch | below the watch threshold on its own past and against the rest of its parent |
| Alarm | below the alarm threshold on its own past and against the rest of its parent |
| Regional dimming | below the watch threshold on its own past, but not against the rest of its parent |
| Seen, no light | enough was seen and no cell showed detectable light |

Where the comparison with the parent cannot be made (no usable rest that
month, or no threshold for it yet), the unit's own past decides alone. That
is not rare: 39% of sub-district alarms and 50% of district alarms rest on
own history alone. Provinces have no parent, so they only ever show regional
dimming (**choice**): with alarms allowed, their alarm rate measured 3.9%
against a target of 1%.

### 3.7 A lasting drop must not become the new normal

A regression on the last six years would learn a drop that lasts and stop
flagging it. So a month that falls below the alarm threshold is kept out of
the fits of the following 24 months, then readmitted (**choice**).

### 3.8 Can this unit be judged at all?

The smallest one-month drop a unit would catch four times in five follows
from its scale and the alarm threshold:

$$D_u(t) = 1 - \exp\!\Big(-\big(|q_{0.01}(t)| + z_{0.80}\big)\,\sigma_u(t)\Big), \qquad z_{0.80} = 0.8416$$

A unit is **steady enough to judge** at its own level when $D_u \le 0.40$
and it has at least 20 lit cells. Otherwise the page marks a low reading as
low confidence (striped) and points to the level above. The median
detectable drop is 31% for provinces, 34% for districts and 38% for
sub-districts: a monthly value sees only large changes.

The 20-cell minimum came from a measurement: of 2,364 sub-district months
that read "seen, no light" from 2018 on, 2,262 came from units under 20
cells. In August 2026, of the 4,479 sub-districts with a lit cell, 2,035
could be judged at their own level (they hold 73% of the light), 1,278
through their district, 876 through their province, and 290 not at all.

### 3.9 Does it hit its targets?

Measured on the national run from 2018 on, as the share of judged unit-months
below each threshold on own history:

| Level | Below watch (target 5%) | Below alarm (target 1%) |
|---|---|---|
| Province | 6.91% | 2.14% |
| District | 5.10% | 1.27% |
| Sub-district | 5.10% | 1.10% |

Close to target when pooled, but not steady: by year the sub-district alarm
rate ran from 0.5% to 2.0% and the district rate from 0.1% to 3.4%. Among
units steady enough to judge the rates are higher (1.25% to 2.72% at the
alarm level), because the hold makes the final scale smaller than the one
the thresholds were set on. Districts and sub-districts have an alarm
threshold from 2018 on, and provinces get their first status in 2020:
before that there is not enough history to read a threshold from.

One external check exists. In August 2018, the month of the Lombok
earthquakes, every Lombok district read normal. The monthly view did not
catch it, which is what section 6 is for.

## 4. Other things said about a unit

### 4.1 Spells of low readings

`ntl.persistence` applies run theory to a unit's status series (**choice**).

- **Low** is watch or alarm. Regional dimming is not counted: it made up 62%
  of sub-district low months and is shared with the area.
- A **spell** ends at the first month that reads normal or "seen, no light",
  or after 3 months in a row that say nothing. After a low month the next
  judged month was low 29.6% of the time, against 3.5% after a normal one;
  across a gap of 3 to 5 silent months that fell to 14.7% against 7.1%. So a
  short gap is bridged and a long one is not.
- A spell has a **length** (its low months) and a **span** (first low month
  to last, gaps included). "Low in 5 months over a span of 11" is not "low
  for 5 months", so both are kept.

About four spells in five last a single month.

### 4.2 Trend

`ntl.trend` works on the unit's index $I_u$.

1. One value per calendar year: the median of the year's monthly values, if
   it has at least 6.
2. The Theil-Sen slope over those yearly values $y_j$ at years $x_j$, needing
   at least 8 years:

$$b = \operatorname{median}_{j<k} \frac{y_k - y_j}{x_k - x_j}, \qquad \text{rate} = 100\,(e^{b} - 1)\ \%\ \text{per year}$$

The 90% interval comes from the same pairwise slopes, ranked, using the
variance of Kendall's $S$. Yearly values are correlated from one year to the
next (lag-1 autocorrelation about 0.55 in the residuals of the national
run), so that variance is inflated by the first-order correction:

$$\operatorname{Var}(S) = \frac{n(n-1)(2n+5)}{18} \cdot \frac{1 + r}{1 - r}, \qquad r = 0.55$$

On simulated series with no trend and that correlation, about 3% are called
a trend at the 90% level with the correction, against about a third without.

Nearly every unit grew, so the rate itself says little. The page colours a
unit by how its rate compares with the median unit of its level, and calls
it faster or slower only when its interval excludes that median. A second
rate, over only the cells that were already lit in 2012, is shown beside
the first, because the lit domain includes cells that are in it only
because they grew.

## 5. Things said about a cell

No status is judged from single cells. These layers describe.

### 5.1 Monthly classes

`ntl.cellmaps` packs three classes per cell and month into one byte:
radiance (breaks at 2, 5, 10, 20, 40 nW), change against the same calendar
month a year earlier (breaks at 0.5, 0.7, 0.85, 1.15, 1.4, 2.0 times), and
the number of observations (under 4, 4 to 9, 10 or more).

### 5.2 Then and now

`ntl.firstlight` compares the first three years of the record (2012 to
2014) with the last three (2024 to 2026). A cell's value in a period is the
median of its yearly medians there. With "dark" under 0.5 nW and "lit" at
2 nW or more:

| Class | Then | Now | Share of cells |
|---|---|---|---|
| Lit at both ends | lit | lit | 56.0% |
| Brightened | dim | lit | 39.1% |
| Emerged | dark | lit | 2.0% |
| Faded | lit | not lit | 1.2% |

So most of what looks new was already faintly there. The count favours
that result: a cell must be lit on average over the whole record to be
looked at, which leaves out cells that lit up only in the last years.

### 5.3 Faint sources

The flat 2 nW rule misses dim, isolated lights. `ntl.sources` finds them
with a local-background filter. The idea, estimating a background from a
weighted mean of the neighbours and keeping what stands above it
consistently over time, is described in a tutorial on a grid-prediction
model ("How to Replicate FB's distribution grid prediction model"); the
implementation and the numbers below are this project's own (**choice**).

Each month the background of cell $i$ is the weighted mean of its good
neighbours within $R = 6.1$ km, the cell itself left out:

$$B_i(t) = \frac{\sum_{j \ne i,\ d_{ij} \le R} w(d_{ij})\,L_j(t)}{\sum_{j \ne i,\ d_{ij} \le R} w(d_{ij})}, \qquad w(d) = \frac{1}{(1 + d/S)^3}, \quad S = 0.61\ \text{km}$$

A cell is a **source** in month $t$ when $L_i(t) - B_i(t) > 0.5$ nW, and a
**consistent source** when that holds in at least half of its good months.
The margin and the share were chosen on one tile so that almost no open sea
passes: with both rules, 0.003% of sea cells do.

A **faint source** is a consistent source that is not in the lit domain.
There are 28,948, with a median radiance of 1.36 nW. They are few where
light is dense and many where it is sparse: none per 100 lit cells in
Jakarta, 55 per 100 in Bangka Belitung.

They are shown on the map and used in no status. Section 7 says why.

### 5.4 Year by year: people by the light recorded where they live

`ntl.litshare` writes a yearly table per province, district and
sub-district, shown under the charts of the selected area (the country is
the sum of its provinces). It is meant as supporting information beside an
official figure such as the share of households with electricity. It is not
that figure.

**A first version was withdrawn the day it was built.** It counted a cell
as lit only if it belonged to the lit cells of section 2.3, and gave 52.8%
of people in lit cells in 2015 and 60.8% in 2026. A method critique
(`temp/litshare-critique.md`) showed that the people living in those cells
are 60.9% of the country in every year, so the 2026 figure was that
ceiling and the rise was the 2 nW line being crossed inside a fixed set of
cells (+0.2 points at 1 nW, +16.2 at 3 nW). Section 7 keeps the lesson.

Rules now (**choice**). The computation was checked by a method review
that recomputed two tiles and one district from the raw files without the
pipeline's code and found no difference; the choice of rules has not had a
second critique.

- **Support.** Every cell that lies in a province and holds people in at
  least one population year, in any land or water class: 2,354,937 cells.
  Coastal-class cells hold towns, and the lit cells of section 2.3 leave
  them out. Cells without people (a lit road, a plant) are in no count.
- **A value per cell and year, from that year alone.** The median of the
  year's usable months (quality 0, which the user guide's Table 12 defines
  as more than 3 observations), needing at least 3. Nothing is fixed with
  hindsight.
- **Four states.** *Unseen*: too few usable months. *No light*: median
  under 0.5 nW, the floor below which the product stores zero, so dimmer
  light is not told apart from none. *Faint*: from there to under 2 nW.
  *Lit*: 2 nW or more.
- **People of each year** (owner's decision). WorldPop R2025A v1,
  `idn_pop_<year>_CN_100m_R2025A_v1.tif`, licence tag CC-BY-4.0, one file
  a year from 2015 to 2026, summed five by five onto the cells (the
  3 arc-second pixels nest in them). **2012 to 2014 use the 2015 file**,
  carried back and marked with an asterisk on the page: nothing is
  extrapolated. An alternative, projecting the 2015 to 2026 trend of each
  cell backwards, was not taken; it would add a model on top of a model.
- **Shares** of the three light states are taken over the people in seen
  cells; the unseen share is given beside them, over everyone. The page's
  bars are the exception: they show all four states as shares of everyone.
- **Sub-districts lit**: those with at least 5 lit populated cells that
  year, out of the 7,264 sub-districts that hold people.
- **No people share at sub-district level**: there both the people and
  where they sit inside the unit are modelled. Cell counts are shown.

Measured on the run of 2026-11-24 (`temp/litshare-run-v3.log`,
`temp/litshare-check-v3.log`), people in seen cells:

| Year | People counted | No light | Faint | Lit | Unseen, of all | Sub-districts with 5 lit cells |
|---|---|---|---|---|---|---|
| 2012 * | 259.2 million | 15.6% | 31.7% | 52.7% | 1.6% | 3,131 |
| 2015 | 259.2 million | 14.1% | 30.0% | 56.0% | 0.1% | 3,343 |
| 2020 | 272.6 million | 15.5% | 22.4% | 62.2% | 0.8% | 3,763 |
| 2022 | 276.4 million | 8.4% | 22.3% | 69.4% | 6.9% | 4,045 |
| 2023 | 278.8 million | 5.2% | 21.3% | 73.5% | 0.9% | 4,526 |
| 2026, to October | 285.6 million | 6.5% | 16.3% | 77.1% | 0.2% | 4,815 |

\* people of 2015.

The 2026 raster holds 286.8 million people, of whom 285.6 million are in a
province and counted. In 2026 the share in "no light" cells runs from 0.0%
(DKI Jakarta) to 74.2% (Papua Pegunungan). Every cell is in exactly one
state each year, and each unit's people by state add up to its total
within 2 people (each figure is rounded on its own). Two tiles the
population grid touches have no monthly files (h31v08 and h29v10): their
59 cells are unseen in every year. The yearly files hold every unit with
people; the page can open only those that also have a lit cell of section
2.3, which leaves out 24 of 514 districts and 2,785 of 7,264
sub-districts.

**How much the population year matters.** The same run with the 2020
people in every year (`--population-year 2020`) moves the national "no
light" share by at most 0.04 points. A share of seen people moves by at
most 0.33 points for a province and 1.0 for a district, in any year and
state. The critique had measured why: the twelve grids differ by a
near-uniform rescaling (people grow 10.1 to 10.3% in every class of cell,
2015 to 2026). So the yearly grids change the people counts and hardly the
shares; WorldPop's release statement itself asks that comparisons between
timepoints be made with care at small scales.

**Against the official figure.** BPS publishes, from Susenas, the share of
households by main source of lighting, by province. The March 2025 tables
were read in a browser on 2026-11-24 and saved as
`temp/bps-penerangan-2025.csv` (the pages render by script, so a plain
fetch returns their titles only):

- electricity: https://www.bps.go.id/id/statistics-table/2/NzcyIzI=/persentase-rumah-tangga-menurut-provinsi-dan-sumber-penerangan-utama-dari-listrik-persen.html (Indonesia 99.55%)
- PLN electricity: https://www.bps.go.id/id/statistics-table/2/ODcjMg==/persentase-rumah-tangga-menurut-provinsi-dan-sumber-penerangan-utama-dari-listrik-pln.html (Indonesia 98.46%)

Across the 38 provinces, against the 2025 row of the table:

| Satellite share, 2025 | Households not lit by PLN | Not lit by any electricity |
|---|---|---|
| People in "no light" cells | Spearman 0.87 | 0.83 |
| People in lit cells (sign reversed) | 0.74 | 0.71 |

Without the six provinces lowest on PLN lighting the first figure is 0.83,
so it does not rest on Papua alone. The levels do not compare: nationally
7.0% of the people in seen cells are in "no light" cells (3.5% of all
were unseen), against 0.45% of households without electric lighting. One
year, province level only; districts have not been compared.

How to read it:

- "No light" is the firmer reading. Footprint and glow spread light onto
  neighbours, so a "no light" cell gave less than the floor even with its
  neighbours' spill, while a faint or lit cell may owe its light to the
  place next door. With an even number of usable months a cell can be "no
  light" with light recorded in half of them (1.1 to 1.4% of seen
  cell-years on the two tiles the method review counted).
- Do not read a rise in "lit" as people gaining light or power. The 2 nW
  line is picked, and the cells that were already lit nearly doubled their
  light: a balanced panel of 239,839 lit cells of section 2.3 has 1.94
  times its 2015 light in 2026 (critique finding 4; the populated cells
  outside that set were not measured). Read faint and lit together against
  no light.
- The "no light" share falls from 15.5% to 5.2% between 2020 and 2023,
  where no earlier three years fell by more than 2 points, and is 6.5% in
  2026. Whether that is light on the ground or a change in the record is
  not established.
- Unseen is not random: in 2025 it is 76.2% of people in Papua Tengah and
  43.8% in Papua Pegunungan.
- The population grid is a model. By WorldPop's release statement and
  covariate sheet (URLs in the critique, finding 5) it is constrained to
  mapped buildings, uses census counts of about district level for
  Indonesia (517 units in 2020), and has night-time lights among its
  covariates. Province and district totals are census-based, scaled to a
  national projection; where people sit inside a unit is not independent
  of light. The critique put an upper bound of 17 points on what that
  placement adds to the old lit share; it has not been measured for the
  new columns.
- The satellite passes in the small hours (nominally 01:30 local time;
  the time at a given cell moves from night to night) and records mostly
  outdoor lighting. Falchetta et al. 2019
  (https://pmc.ncbi.nlm.nih.gov/articles/PMC6610126/) put it as "limited
  interior lighting might not be visible from outside": a household with a
  connection and no outdoor lighting can sit in a "no light" cell.

## 6. The case studies

A month hides an event that lasts days. `ntl.events` and `ntl.lightup`
follow four events night by night.

### 6.1 Which night a file is

A daily file dated $D$ holds the overpass of about 01:30 local time on
$D + 1$: the night that begins on the evening of local date $D$. This was
read from the time layer of the files over Lombok. An event in the evening
of $D$ is first seen in the file dated $D$.

### 6.2 Reference and ratio

For each lit cell, the **reference** $\rho_i$ is the median of its usable
values on the event's reference nights, if it has enough of them. The light
of a group of cells $G$ on night $k$ is, as in section 3.1, like for like:

$$R_G(k) = \frac{\sum_{i \in G \cap V(k)} L_i(k)}{\sum_{i \in G \cap V(k)} \rho_i}$$

A first version used the median of the cells' own ratios for one event and
this sum for the others. The reviews found the two give different answers
(48% against 37% on the same night), so the sum is now used everywhere.

### 6.3 The four events

| Event | Tile and nights | Reference nights | Notes |
|---|---|---|---|
| Lombok earthquakes, 2018 | `h29v09`, 25 July to 25 August | 25 July to 4 August | 7 of the 11 reference nights follow the first earthquake |
| Palu earthquake, 2018 | `h29v09`, 12 September to 31 October | 12 to 27 September | cloud leaves most cells 2 reference nights |
| Nyepi, 19 March 2026 | `h29v09`, 6 to 31 March | 29 and 30 March, after the event | the nights before were under cloud |
| Mudik, Eid al-Fitr 5 and 6 June 2019 | `h28v09` and `h29v09`, 15 May to 25 June | 15 to 27 May | inside Ramadan |

For Nyepi the quality flag 1 ("poor: outlier, potential cloud
contamination") is admitted as well as flag 0, because on that night most of
Bali carries it; the cells flagged high quality alone read about a fifth of
their reference, not under a tenth. The page says the headline depends on
that choice.

### 6.4 The viewing angle

This is the main thing the case studies found, and it changed all four.

The satellite does not see a place from the same angle every night. Read
from the angle layer of `VNP46A1`, the view zenith over one point runs from
about 4 to 67 degrees and repeats every 16 nights:

| Nights apart | Median difference in view zenith | Largest |
|---|---|---|
| 16 | 0.14 degrees | 2.2 |
| 11 | 6.6 | 12.6 |
| 8 | 32 | 62 |

The repeat holds over years: 14 nights of March 2026 against September
2018, 171 and 172 cycles earlier, differ by a median of 0.2 degrees.

A place's light changes with that angle by tens of percent. Over Jakarta in
May and June 2019 the nightly light of the cities swung by about 19% and was
strongly correlated with itself 11 nights apart (0.86) and anti-correlated 8
nights apart (-0.77), with nothing happening on the ground. Over Lombok and
Bali in these weeks cells read dimmer from nearly overhead than from the
side. The product's guide reports the opposite over dense city centres, so
the direction is a property of the place, not a law.

Two consequences follow.

**A control area does not remove it.** A first version divided each night
by a neighbouring area (Bali for Lombok, three distant cities for Palu). A
neighbour is seen from a different angle on the same night, so the division
leaves the effect in: before the earthquake Palu already read 67% to 79% of
its control.

**Compare nights seen alike.** Two comparisons are used instead.

*Same view.* A night against the night 16 before, over the cells seen on
both:

$$S_G(k) = \frac{\sum_{i \in G \cap V(k) \cap V(k-16)} L_i(k)}{\sum_{i \in G \cap V(k) \cap V(k-16)} L_i(k-16)}$$

*Matched reference.* With $\theta_i(k)$ the view zenith at cell $i$ on night
$k$ and $\mathcal R$ the reference nights, the reference of a cell for night
$k$ uses only the reference nights seen from within 10 degrees of that
night's angle, never the night itself:

$$\rho_i(k) = \operatorname{median}\{\, L_i(j) : j \in \mathcal R,\ j \ne k,\ |\theta_i(j) - \theta_i(k)| \le 10^\circ \,\}$$

and the ratio of section 6.2 is taken with $\rho_i(k)$ in place of $\rho_i$.
A night without its own angle file takes the angle of a night a whole number
of 16-night cycles away.

Tested on nights where nothing is known to have happened, where the ratio
should read 100%, the scatter (standard deviation of the log ratio) falls by
about half:

| Area | Nights | Plain reference | Matched |
|---|---|---|---|
| Lombok | 10 | 0.212 | 0.119 |
| Bali | 19 | 0.169 | 0.099 |
| Palu's control cities | 23 | 0.218 | 0.114 |
| Jakarta and neighbours | 11 | 0.149 | 0.124 |

In this table the plain reference includes the night being judged and the
matched one does not, which favours the plain one. A reviewer's stricter
comparison, leaving the night out of both, gave larger gains: 0.245 to
0.121 for Lombok and 0.200 to 0.122 for Jakarta.

The tolerance of 10 degrees was picked (**choice**): 5 and 15 give results
too close to tell apart. About 45% of the cell-nights rest on a single
reference night, so each figure is noisier than it looks. Over Jakarta 12%
of scatter remains after matching, and matching the side of the swath as
well does not remove it.

### 6.5 What the four found

- **Lombok.** Three nights after the main earthquake the island read 73% of
  its reference and Bali 82%. Matched for angle they read 94% and 99%: the
  dimming was the angle. Two nights do stand out. On 19 August, hours after
  the third earthquake, the cells seen gave 54% (57% of the same view 16
  nights earlier) while Bali gave 103%, and they were back the next night.
  On 12 August, with no large earthquake, Lombok gave 16% on 2,306 cells
  while the 483 Bali cells seen read 108%. Nothing here explains that night,
  and it has not been checked against any record.
- **Palu.** 43% of the same view on the night of the earthquake, 6% and 17%
  on the few cells seen two and three nights later, about six tenths at ten
  nights and about nine tenths at twenty-six. Each of the last two is one
  night.
- **Nyepi.** Bali gave 8.6% of its reference light. Every brightness class
  ended near 1 nW (from 5, 13, 26 and 44), which is close to the least the
  product is designed to detect, so 8.6% is nearer a ceiling than a
  measurement.
- **Mudik.** The cities do not dim measurably at Eid: nights 16 apart with
  one of them an Eid night read 87% to 90%, ordinary pairs 80% to 108%. See
  the next section for the roads.

### 6.6 Which dark places lit up

A road is dark on an ordinary night and is not in the lit domain, so
`ntl.lightup` looks at every land cell of Java, lit or not.

For each cell, $M_i(W)$ is its mean over the nights of a window $W$ on which
it was seen (at least 2). The map shows $M_i(W) - M_i(\mathcal R)$ in
classes. The **line** is the set $\Lambda$ of land cells between 107.3 and
110.6 E that are dim on the reference nights and brightened on the return:

$$\Lambda = \{\, i : M_i(\mathcal R) < 3,\ \ M_i(W_{\text{return}}) - M_i(\mathcal R) \ge 1.5 \,\}$$

and the **background** $\Omega$ is the dim cells that did not move (within
0.3 nW). Cells chosen for having brightened will read brighter on those
nights, and dim cells also swing with the angle, so the comparison that
carries a claim is at the same view and net of the background:

$$N(k, k') = \overline{\big(L_i(k) - L_i(k')\big)}_{i \in \Lambda} - \overline{\big(L_i(k) - L_i(k')\big)}_{i \in \Omega}, \qquad |k - k'| = 16$$

| Night | Against | Net, nW |
|---|---|---|
| Sunday 9 June (the return) | 24 May | +4.91 |
| Sunday 9 June | 25 June | +3.44 |
| Monday 10 June | 25 May | +2.57 |
| 29 May (leaving) | 14 June | -1.06 |
| 30 May | 15 June | -0.19 |
| 31 May | 16 June | -0.15 |

Cells picked on 10 and 11 June alone, which says nothing about the 9th,
read +3.76 nW on 9 June. The same picking rule on three ordinary windows of
later June finds 666, 1,305 and 2,341 cells, against 5,251 on the return.

So one night stands out, the Sunday of the return, on cells whose usual
light is about 1.5 nW. The nights of leaving show nothing, and the last
nights before Eid were under cloud. What the light is remains a guess:
traffic, lamps at rest areas and toll gates, and the edges of towns all
qualify. The road overlay does not settle it, because dim cells that flicker
lie along main roads on ordinary nights too.

## 6a. The long view: DMSP 1992 to 2013 beside VIIRS

Modules `ntl.dmsp`, `ntl.longrecord`, `ntl.sensors`, `ntl.longview`; page `long-view`. The
older DMSP-OLS satellites give one composite per satellite and year from 1992
to 2013. The page shows them beside VIIRS on one time axis and does **not**
join them. This section says what is shown and why the join was given up.

### Data

- **DMSP-OLS Version 4 stable lights** from the Earth Observation Group: 34
  satellite-years (F10 1992 to F18 2013), 30 arc-seconds, a digital number
  from 0 to 63 with no on-board calibration. Two forms are used: the archives
  (stable lights, raw average, count of cloud-free observations) and EOG's
  own intercalibrated stable lights (Elvidge and others 2009,
  <https://doi.org/10.3390/en20300595>: a second-order polynomial per
  satellite-year, reference F12 1999, fitted over Sicily).
- A DMSP cell covers exactly two by two cells of the 15 arc-second VIIRS
  grid: cell centres sit on multiples of 1/120 degree.
- Three of EOG's intercalibrated files (F16 2009, F18 2010, F18 2011) state
  their corner half a cell away from the others. Measured: in all 34
  satellite-years the cells above zero are exactly those of the archive when
  read by position, and fewer agree when moved by one cell. The data are on
  the usual cells; only the header differs. `ntl.dmsp` reads such a file by
  position with a warning and refuses any other corner.
- **Flare outlines** drawn by NOAA for the DMSP years, one shapefile per
  country, dated 2009 (gone from NOAA's address; the Internet Archive keeps
  the page).

### What was tried for making the satellites agree

| Tried | Result | Kept |
|---|---|---|
| Use the archives as they are | Two satellites of the same year differ by -22% to +34% in national light over Indonesia | No |
| EOG's intercalibrated files | -18% to +11%; median province disagreement 0.022 to 0.151 | Yes, as the level |
| A chain through the 12 years with two satellites | Not identified: every overlap is two satellites in the SAME year, so none links one year to the next. A fake drift of 10% a year fits the overlaps exactly | No |
| An invariant set of Indonesian cells | Circular: cells of stable rank are blind to growth everywhere at once | No |
| A floor on the digital number for lit area | Removes 92% of newly lit cells; Sumatra's lit area turns from growth (1.30 times) to decline (0.87) | No |
| A dark-background reading of sensor gain (raw average over sea never lit) | Tracks the pair differences (r = 0.97, slope 0.60) and shows which satellite moved (F15 in 2003), but it misses in at least two satellite-years (F10 1994, F18 2013) and no publication using it was found | As a diagnostic only |

### The yearly record

For unit $u$ and satellite-year $s$, with corrected digital numbers $d_i$:
light $T_{u,s} = \sum_{i \in u} d_i$, lit cells
$A_{u,s} = \#\{i \in u : d_i > 0\}$ (no floor), and light outside the flare
outlines.

**Two satellites in a year.** The value is their mean, unless one plainly
misses the unit's dim light (recall, below).

**Recall of steady dim cells.** For satellite-year $s$, the steady dim cells
$S_s$ are those lit in at least 60% of the other satellite-years within three
years, with a median value below 8. For a unit with at least 50 of them,

$$R_{u,s} = \frac{\#\{i \in u \cap S_s : d_i > 0\}}{\#\{u \cap S_s\}} .$$

Where one satellite has $R < 0.7$ and the other is at least 0.15 higher, the
better one stands alone (65 province-years, 17 of them in 1999 and 19 in
2003). The median over provinces is 0.85 to 0.94 in 16 of the 22 years, 0.22
in 1992, 0.71 in 1993 and 0.78 in 2013.

**The band is disagreement between satellites, not a confidence interval.**
Per unit, over the years $P$ with two satellites $a$, $b$:

$$\sigma_u = \sqrt{\frac{1}{|P|} \sum_{y \in P} \left( \tfrac{1}{2} \ln \frac{T_{u,a}}{T_{u,b}} \right)^2 }$$

(a year in which one of them sees nothing counts as 1.0; a unit with fewer
than four such years takes the median of the others). The half width in log is

$$w_{u,y} = \sqrt{ (k\,\sigma_u)^2 + \tau^2 }, \qquad k = 1 \text{ for a mean of two},\; k = 2 \text{ for one satellite},$$

with $\tau$ = 0.05 for light and 0.08 for lit cells, the part common to all
provinces in a year (an upper estimate: it also takes in real change). The
band is $T e^{\pm w}$. Measured for light, leaving a year out: with $k = 1$ a
single-satellite band held the other satellite's reading 35% of the time, with
$k = 2$ about 68%. A year's own two readings reach beyond the band in about
one province-year in five (22% of the years that have two readings; 16% of
those where the point is their mean): the band is a typical width, not the
range of that year. The page gives "satellites typically differ by" as
$e^{2\sigma_u} - 1$, the whole typical difference, where the band's half width
uses $\sigma_u$. Typical half width for a province: 16% with one satellite,
8% with two (light); 30% and 15% (lit cells). A value of zero has no band: it
is "not detected".

**Flags** (none changes a value): lit area that drops below 75% of both the
three years before and after, and so returns; recall under 0.7; a median of
fewer than 15 cloud-free observations in the unit; no light detected; more
than half the light at the top of the scale. F12 1994 is left out for thin
observation (median 10 per cell; F10 covers the year). F18, 2010 to 2013, is a
segment of its own: for those years EOG's Version 4 series has a yearly
composite of F18 alone (other satellites flew, but none has a composite), so
nothing ties them to the years before. The step from F16 2009 to F18 2010 in
national light is +9% in the corrected files, +18% after the dark-background
reading and +45% uncorrected; how much of it is the ground is not known.

**Gas flares.** Up to 81% of a province's DMSP light lies inside NOAA's
outlines (South Sumatra in 1992, a thin year; 78% in 1996). The outlines are broad and include towns, and flare glow reaches
beyond them, so the choice of mask decides the result where flares are large
(one province reads 0.69, 1.17 or 0.71 of its 1996 light in 2007 with no
mask, these outlines, or a tight mask). "Light outside the outlines" is
marked usable only where the outlines never hold more than 10% of the unit's
light: 32 of 38 provinces.

### Why DMSP and VIIRS are not joined

Yearly Black Marble (median of each cell's good months, every cell, averaged
two by two onto the DMSP grid) was compared with F18 for 2012 and 2013
(`ntl.sensors`; the page shows its two outputs: what F18 sees in each class
of VIIRS radiance, and per place the share of F18's light in cells where
VIIRS reads under 0.25 nW, which has a median of 31% to 35% over provinces
and reaches 59% in East Nusa Tenggara).

- F18 calls lit 57% of cells where VIIRS reads 0.25 to 0.5 nW, 86% at 0.5 to
  1 and 98% at 1 to 2; it reaches the top of its scale above about 16 nW.
- Blurring VIIRS by 1.5 DMSP cells raises its correlation with F18 from 0.89
  to 0.94; a blur of 2 cells does nearly as well and was used for the fit
  below.
- A conversion in the form of Li and others (2020,
  <https://doi.org/10.1038/s41597-020-0510-y>), on blurred radiance $L$,

$$\widehat{DN} = d + \frac{D - d}{1 + e^{-k(\ln(1+L) - x_0)}}, \qquad \widehat{DN} = 0 \text{ below a floor},$$

  fitted on 2013 gives $d$ = 4.8, $k$ = 2.15, $x_0$ = 1.87, $D$ = 58.6 and a
  floor of 0.17 nW. Applied to 2012 it gives a national sum of 1.02 times F18
  and a lit area of 1.02.
- By province it fails: in the year not fitted on, the typical miss is 22% to
  25% (0.20 to 0.23 in log), and 9 or 10 of 38 provinces are within 10%.
- The national figure is a balance of opposite regional errors (0.92, 1.09
  and 1.16 for the three regions it was fitted on), moves from 1.14 to 0.92 with a floor between
  0.10 and 0.25 nW, and compresses growth: a doubling of radiance becomes 1.6
  times.
- A third of F18's lit cells (87 thousand of 267 thousand, 18% of its light)
  have less than 0.25 nW of VIIRS light under them. 86% of that light is
  within 3 cells of a VIIRS cell of 0.5 nW: mostly DMSP's wider footprint
  around lights VIIRS does see, with a little light below the VIIRS product's
  own floor (those cells read 0.04 to 0.06 nW above their dark neighbours).
- A second VIIRS product (EOG's annual VNL v2) disagrees with Black Marble by
  region, so any ratio between DMSP and VIIRS depends on the product chosen.

So the page shows three segments with gaps: DMSP 1992 to 2009, F18 2010 to
2013, and VIIRS from 2012 in its own measure (the yearly median of the
monthly index of section 3, as a share of the unit's usual light). No ratio
between the sensors is published.

### What the long view cannot support

A growth figure from two single years; any change across 2009 to 2010 or from
DMSP to VIIRS; a trend for a saturated unit; the words "electrification" or
"settlement light". The level across all DMSP years rests on the assumption
that the lighting of Sicily was largely stable (Elvidge and others 2009, for
1994 to 2008; EOG's later coefficient table extends it), and no band shows an
error in it. A joined series does exist (Li and others 2020): what is said
here is that the join does not hold below the country for Indonesia. The record has
not been compared with electricity sales or any other record on the ground.
Several causes named in the notes are inferences, not checked: fire and haze
for 1997 in central and south Kalimantan, and gas flaring for bright spots
that faded on the coasts of Aceh, North Sumatra and Riau.

## 7. What was tried and changed

| Tried | What the test showed | Now |
|---|---|---|
| Expected value as the median of earlier years | biased low wherever lights grow | a regression with a slope (3.2) |
| Lookback of 4, 6 or 10 years | noise 0.115, 0.107, 0.110; 10 years brought bias back | 6 years |
| A normal threshold | 1.6% of months flagged at a 1% target | pooled quantiles (3.4) |
| Own history alone | haze flagged whole regions | the test against the rest of the parent (3.5) |
| Alarms for provinces | 3.9% alarm rate | regional dimming only |
| No minimum size | 2,262 of 2,364 "seen, no light" months from tiny units | 20 cells to be judged |
| A threshold from any pool of 300 values | 11.9% alarms in a first year | at least 10 values beyond the quantile |
| Near-nadir and off-nadir monthly composites | usable in one corner of the country only | all-angle composites |
| A three-month composite | a season, not a month: 24% to 30% of its nights come from its centre month | built, not shown on the page |
| Parents confirming a low reading through their children | raised 8 district months in nine years | not applied |
| Spells counting regional dimming | 62% of low months were regional | watch and alarm only, with a gap rule (4.1) |
| The classical interval for a trend | a third of trendless series called a trend | the interval widened for serial correlation (4.2) |
| The year each cell became lit | it measured crossing a line, not new light | "then and now" classes (5.2) |
| Median of cell ratios for a unit | 37% where the summed light gave 48% | summed light everywhere (6.2) |
| Dividing by a control area | the control is seen from another angle | nights seen alike (6.4) |
| Lombok: a dim ring 15 to 30 km from the epicentre | 14 cells, which ranged from 86% to 117% before the earthquake | dropped |
| Mudik: cities against home districts | the same clean split on 4 of 14 ordinary nights | reported as a warning, not a finding |
| Mudik: brighter roads on the nights of leaving | no brighter than same-view nights in mid June | dropped; only the return is claimed (6.6) |
| Mudik: the line overlaps mapped roads | so do cells picked on ordinary nights (28% to 50%) | the overlay is shown, the claim is not made |
| The source filter in place of the 2 nW rule | it drops 49% of the light: it finds peaks, not extents | not used that way |
| Faint sources added to the lit domain | 281 of 759 alarm readings lost, 67 in units that gained no cell | a map layer only (5.3) |
| People in lit cells, counted on the lit cells of the statuses | capped at the 60.9% of people who live in those cells; 60.8% in 2026 was the cap | a state per year for every populated cell (5.4) |

The row on faint sources deserves a line. Adding the faint cells looked harmless on
averages (alarm rate 1.10% to 0.92%). Looked at reading by reading, the
extra cells had shifted the pooled thresholds of every unit, and they read
exactly zero in 7.8% of their good months against 1.8% for ordinary dim
cells. The change was taken back the same day.

## 8. How it was checked

- **Tests.** 286 tests, most of them small arrays worked by hand. Functions
  are pure wherever possible, so a statistic can be checked without a file.
- **Independent reproduction.** Reviewers recomputed published figures from
  the source files without importing the project's code: the lit-cell
  counts, and the nightly figures of the events. All matched.
- **Deliberate breaks.** For one round, 14 faults were planted in the
  variables' code; the tests caught all 14.
- **Placebos.** The road finding was tested on ordinary windows, the
  matched reference on quiet nights, the source filter over open sea.
- **Claims.** Every sentence a reader sees was traced to a measurement or a
  primary source, twice. The second pass found 14 wrong or stale statements
  out of about 120; they were corrected.
- **Written from scratch.** No code was taken from existing night-lights
  packages.

Two rounds of five reviews were run on the code and the pages. The fixes
that followed the second round have not themselves been reviewed.

## 9. What reaches the browser

`ntl.export` writes small binary files into `site/data`: 146 files, 39 MiB.

| File | Holds |
|---|---|
| `meta.json` | months, thresholds, encodings, where the data came from |
| `units_<level>.json` | one row per unit: code, name, cells, trend, spells, then-and-now counts |
| `bundle_<level>_<province>.gz` | per unit and month, 13 columns: state, index, anomaly, relative anomaly, the two scales, coverage, observations, detectable drop, flags, run, span, months unseen |
| `cells.u32.gz`, `cell_usual.u16.gz`, `cell_<level>.u16.gz` | each lit cell's position on the global grid, usual radiance and unit |
| `cells/<year>.u8.gz` | one packed byte per cell and month (5.1) |
| `cell_then_now.u8.gz` | the class of 5.2 |
| `faint_*.gz` | the faint sources (5.3) |
| `outlines/*.geojson` | simplified outlines, for display only: no statistic reads them |
| `events/<key>/` | each case study's nights, classes and story figures |

Numbers are little-endian, gzip compressed, and written under a temporary
name then renamed. The page is static: the browser does no statistics
beyond counting what is on the map.

## 10. Known limits

- **Not ground truth.** Nothing has been checked against records of power,
  damage or traffic. A status is a statement about light.
- **Look-ahead.** The lit domain and each cell's usual radiance use the
  whole record.
- **Cloud.** About 40% of unit-months are not observed, and far more in the
  wet season.
- **Sensitivity.** The median unit catches a one-month drop of about a
  third. Events of days are invisible in a month.
- **Early years.** No alarm threshold before 2018, and no province status before 2020.
- **Two sensors, not joined.** The statuses are VIIRS only, from 2012. The
  older DMSP-OLS yearly composites (1992 to 2013) are shown beside it on the
  long view page and are not joined to it (section 6a): a conversion between
  them comes within 3% for the country and misses provinces by a fifth to a quarter.
- **Thresholds drift.** The yearly alarm rate ranges from a tenth to three
  times its target.
- **One satellite pass.** About 01:30. Light lost and restored between
  passes leaves no trace.
- **Case studies.** One event each; some figures rest on one reference
  night; the angle repeat was checked on one tile.
- **Faint sources.** Thresholds chosen on one tile; what they are (villages,
  mines, plantations, flares) is unchecked.
- **Boundaries.** Display outlines are simplified; about 2% of cells at
  sub-district level are drawn in a neighbour. The figures use the exact
  boundaries.
- **Not corrected by the product.** Vegetation, fires, flares, boats.

## 11. Symbols

| Symbol | Meaning |
|---|---|
| $L_i(t)$ | radiance of cell $i$ in month or night $t$, nW cm⁻² sr⁻¹ |
| $\bar L_i$ | usual radiance of cell $i$: its mean over its good months |
| $V_u(t)$ | cells of unit $u$ with a usable value at $t$ |
| $I_u(t)$ | log index of unit $u$ (3.1) |
| $c_u(t)$ | share of the unit's usual light that was seen |
| $\hat I_u(t)$ | index expected from the unit's own past (3.2) |
| $a_u(t)$ | anomaly: observed minus expected |
| $\sigma_u(t)$ | the unit's scale (3.3) |
| $q_r(t)$ | pooled threshold at false-alarm rate $r$, in scales (3.4) |
| $d_u(t)$ | anomaly relative to the rest of the parent (3.5) |
| $D_u(t)$ | smallest detectable one-month drop (3.8) |
| $b$ | Theil-Sen slope of the yearly index (4.2) |
| $B_i(t)$, $w(d)$ | local background of a cell and its distance weights (5.3) |
| $\rho_i$, $\rho_i(k)$ | reference of a cell: plain, and matched to night $k$ (6.2, 6.4) |
| $\theta_i(k)$ | view zenith at cell $i$ on night $k$, degrees |
| $R_G(k)$, $S_G(k)$ | light of a group against its reference; against the same view 16 nights before |
| $M_i(W)$ | mean of a cell over the nights of a window (6.6) |
| $\Lambda$, $\Omega$ | the line, and the background (6.6) |
| $N(k, k')$ | net same-view difference of the line (6.6) |

## 12. Running it

Python 3.11 or later with `numpy`, `h5py` and `httpx`; `rasterio`,
`geopandas` and `shapely` for the steps that read boundaries. Node 18 or
later for the page. Every command has `--help`. Paths are examples.

An Earthdata token goes in a file `.env` in the repository root, as a line
`EARTHDATA_TOKEN=...`. The file is not tracked. Listings are public, so
`--dry-run` needs no token and shows what would be fetched.

### 12.1 The explorer

| Step | Command | Time measured |
|---|---|---|
| Fetch the monthly files | `python -m ntl.download --product VNP46A3 --start 2012-01-01 --end 2026-10-31 --indonesia --root E:\temp\ntl` | hours; 78.8 GB |
| Lit cells of each tile | `python -m ntl.stack --root E:\temp\ntl --boundaries <adm3 file> --out E:\temp\ntl\cache --tiles <the eleven>` | about 14 minutes a tile |
| Status of every unit | `python -m ntl.monitor --cache E:\temp\ntl\cache --out E:\temp\ntl\cache\run_monthly.npz` | about 15 minutes |
| Display outlines | `python -m ntl.boundaries --boundaries <adm3 file> --out E:\temp\ntl\cache\outlines` | minutes |
| Files for the page | `python -m ntl.export --cache E:\temp\ntl\cache --run E:\temp\ntl\cache\run_monthly.npz --outlines E:\temp\ntl\cache\outlines --out site\data` | about a minute |
| People by the light where they live | `python -m ntl.litshare --root E:\temp\ntl --population <folder of yearly population rasters> --boundaries <adm3 file> --work E:\temp\ntl\litshare --out site\data\yearly` | about 25 minutes the first time (rasters, unit maps, tiles); seconds once cached in `--work` |

The boundary file is a polygon file of sub-districts with integer fields
`a1siak`, `a2siak` and `a3siak`. A tile already cached is skipped unless
`--force` is given. `--until` fixes the lit domain from months before a
date.

For the layer of faint sources, build a second set of stacks with
`--sources` in a folder of their own and add `--faint <that folder>` to the
export. Never mix the two kinds of stack in one folder: the statuses must
use the ones built without `--sources`.

### 12.2 The case studies

Fetch `VNP46A2` for each event's tile and nights (section 6.3), and
`VNP46A1` for at least 16 consecutive nights of the same tile, which gives
the viewing angle of every night by the 16-night repeat. Without `VNP46A1`
the figures "against nights seen alike" are left out.

```
python -m ntl.events --event lombok2018 --root E:\temp\ntl --cache E:\temp\ntl\cache --out site\data
python -m ntl.lightup --study mudik2019 --root E:\temp\ntl --out site\data --roads E:\temp\ntl\osm\java_roads_overpass.json
python -m ntl.dmsp --archives <folder of FssYYYY.v4.tar> --out E:\temp\ntl\dmsp --scratch E:\temp\ntl\scratch\dmsp
python -m ntl.longrecord --crops E:\temp\ntl\dmsp --eog E:\temp\ntl\eog --boundaries <adm3 file> --flares <Flares_Indonesia_1.shp> --out E:\temp\ntl\longrecord
python -m ntl.sensors --root E:\temp\ntl --crops E:\temp\ntl\dmsp --eog E:\temp\ntl\eog --units <unit maps .npz> --cache E:\temp\ntl\dmsp_work --out E:\temp\ntl\longrecord\sensors.json
python -m ntl.longview --records E:\temp\ntl\longrecord --run E:\temp\ntl\cache\run_monthly.npz --sensors E:\temp\ntl\longrecord\sensors.json --out site\data\long
```

The first is run once per event (`lombok2018`, `palu2018`, `nyepi2026`,
`mudik2019`) and takes seconds. The second reads every cell of Java for 42
nights and takes about two minutes; `--roads` names a file for the roads of
the box from OpenStreetMap, read if it exists and fetched once if not.

### 12.3 The page, and publishing it

```
npm install
npm run build
npm run serve
```

`npm run dev` serves a live preview. `npm run deploy` builds the site and
publishes it to the `gh-pages` branch; `npm run deploy:check` does
everything except the push. The site is built on the machine that holds the
data, because `site/data` is not in the repository.

### 12.4 The modules

| Module | Does |
|---|---|
| `ntl.conventions` | every product constant and threshold, with its source |
| `ntl.tiles` | the 10-degree tile grid |
| `ntl.download` | fetches files: parallel, retry, resume, verified |
| `ntl.read` | reads a layer in physical units, with fill masked |
| `ntl.qa` | decodes the quality flag and the cloud mask |
| `ntl.composite` | the fixed land mask; three-month composites |
| `ntl.zonal` | cells to provinces, districts and sub-districts |
| `ntl.stack` | a tile's monthly files as arrays for the lit cells, with a cache |
| `ntl.status`, `ntl.monitor` | the status of one unit, and of every unit of a level |
| `ntl.persistence`, `ntl.trend` | spells of low readings; the long-run rate |
| `ntl.firstlight`, `ntl.cellmaps` | then-and-now classes; monthly classes per cell |
| `ntl.sources` | faint light sources |
| `ntl.litshare` | yearly cells and people by light state (no light, faint, lit, unseen) |
| `ntl.files` | writing a file under a temporary name and renaming it, with a retry |
| `ntl.events`, `ntl.lightup` | the daily case studies |
| `ntl.boundaries`, `ntl.export` | display outlines; the files the page loads |

## 13. Practices worth keeping

What this project learned about handling night-lights data, in the order
one meets the problems. None of it is specific to Indonesia.

**Files**

1. **Keep the archive off synced folders.** A sync client that locks a file
   mid-write corrupts both downloads and caches.
2. **Write under a temporary name, rename when complete.** A half-written
   file must never carry a real name, for downloads and for derived files
   alike.
3. **Do not trust one bad answer from the archive.** A listed file can
   answer 404 once and download on the next try.
4. **Record what was fetched.** One line per file, with size and checksum,
   makes a rerun cheap and an audit possible.
5. **Know which night a file is.** A daily file dated D over Indonesia is
   the night that begins on the evening of local date D. Check it against
   the time layer before dating an event.

**Values**

6. **Keep three states apart: usable, rejected, not observed.** Averaging
   "not observed" in as zero, or reading it as dark, is the commonest way to
   invent an outage.
7. **A gap-filled value is a memory, not an observation.** It holds a number
   where nothing was seen. Never use it to detect change.
8. **Read flags as stored.** A flag layer converted to floating point with
   missing values makes "not observed" look observed.
9. **Test the flag and the count.** A quality flag does not mean what its
   table suggests in every cell; "poor" is not "too few observations".
10. **A zero in a composite is a floor, not a measurement.** The monthly
    product sets radiance under 0.5 nW to zero.
11. **Use one land mask, built from every month.** A mask from a single
    file shrinks in cloudy months.

**Comparing**

12. **Compare like with like.** Sum the light of the cells that were seen
    and divide by the usual light of those same cells. A month that sees
    only a town's centre is otherwise read as a bright month.
13. **Say how much was seen.** Report coverage beside every figure, weighted
    by light, and refuse a figure when under half was seen.
14. **Fit growth before judging a drop.** Where lights grow by several
    percent a year, last year's level is a biased yardstick.
15. **Use the data's own tails for thresholds.** Anomalies are heavier
    tailed than a normal distribution; a normal threshold overshoots.
16. **Use the past only.** Fit, scale and threshold for a month must come
    from earlier months, or the result cannot be claimed for a monitor.
17. **Separate a place's own change from its region's.** Haze and season
    move whole provinces; compare a unit with the rest of its parent.
18. **Ask whether a unit can be judged before judging it.** A unit with few
    or noisy cells will produce readings; they should be marked, not
    trusted.
19. **Never compare single nights seen from different angles.** The same
    town reads tens of percent apart. Compare nights 16 apart, or match
    reference nights by view zenith. A neighbouring control area does not
    remove the effect.
20. **Add cells with care.** Faint cells near the floor change the pooled
    thresholds of every unit, not only their own.

**Claims**

21. **Choosing cells by an outcome guarantees the outcome.** Test a finding
    on nights that played no part in the choosing, and run the same recipe
    on ordinary nights as a placebo.
22. **Check a pattern on all the other nights too.** A split that fits the
    story on the night of the story may appear on ordinary nights as well.
23. **Look under an average before calling a change harmless.** Rates can
    stay near target while individual readings change.
24. **Light is not electricity.** Say what was measured, and name what was
    not checked.

