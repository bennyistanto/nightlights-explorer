"""How long a unit has been reading low, and how often that has happened before.

Run theory on a unit's own status series (``ntl.monitor``): an *episode* is a
stretch of windows in which the unit reads low, and the questions are "does
it persist, for how long, has it happened before".

Everything here is about the UNIT's figure. It says nothing about each place
inside the unit: a district can read low for six months while different
sub-districts take turns being dim (project skill, section 6). Per-cell
persistence is not computed yet.

Rules, revised after the method critique of 2026-11-23 (figures from the
national run to 2026-10; ``temp/status-design.md``):

- **Low** is WATCH or ALARM: the unit is dimmer than its own past explains
  and clearly dimmer than the rest of its parent. REGIONAL is not counted:
  it is dimming shared with the surrounding area, it made up 62% of
  sub-district low windows and all province ones, and it is reported on its
  own (``UnitSummary.regional_windows``). A REGIONAL window inside an
  episode neither ends it nor adds to it. Provinces, which never show
  WATCH or ALARM, therefore have no episodes.
- **An episode ends** at the first window that reads NORMAL or "seen, no
  light" (DARK) after it, or once ``MAX_SILENT`` windows in a row have said
  nothing (not observed, no reference, no threshold). After a low window
  the next judged window was low 29.6% of the time against 3.5% after a
  normal one; across a gap of 3 to 5 unjudged windows that fell to 14.7%
  against 7.1%, so a short gap is bridged and a long one is not.
- **Length and span**: the length of an episode counts its low windows
  only; its span is the calendar windows from its first low window to its
  last, silent and regional windows included. Both are returned, because
  "low in 5 months over a span of 11" is not "low for 5 months".
- A low reading on a unit that cannot be judged at its own level counts like
  any other here: the caller decides whether to show it (the page hides
  these figures for units under ``conventions.MIN_UNIT_CELLS`` cells).

Four in five episodes last a single window (81% at sub-district level under
the earlier rules, which also counted REGIONAL).

The running counters (a loop over time with one counter per unit, reset by
``np.where``) follow the pattern of ``running`` in ``drywet-explorer``'s
``pipeline/status.py``, the same owner's project. The rules and the episode
list are this module's own.
"""

from __future__ import annotations

from typing import Final, NamedTuple

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import conventions as c

#: States that count as "reading low".
LOW_STATES: Final[tuple[int, ...]] = (c.STATUS_WATCH, c.STATUS_ALARM)
#: States that end an episode.
ENDING_STATES: Final[tuple[int, ...]] = (c.STATUS_NORMAL, c.STATUS_DARK)
#: States that say nothing about the unit that window.
SILENT_STATES: Final[tuple[int, ...]] = (c.STATUS_NOT_OBSERVED, c.STATUS_NO_REFERENCE, c.STATUS_NO_THRESHOLD)
#: Silent windows in a row that end an open episode. [B] from the critique's gap test.
MAX_SILENT: Final[int] = 3


#: Every code a status array may hold.
_KNOWN_STATES: Final[tuple[int, ...]] = tuple(c.STATUS_NAMES)


def _grid(state: ArrayLike) -> tuple[NDArray, tuple[int, ...]]:
    """The states as a (T, U) array of integers, and the caller's shape; refuses anything that is not a status."""
    state = np.asarray(state)
    if state.ndim not in (1, 2):
        raise ValueError(f"state must have shape (T,) or (T, U), got {state.shape}")
    if state.dtype.kind not in "iu":
        raise TypeError(f"state must hold integer status codes, got dtype {state.dtype}")
    if state.size and not np.isin(state, _KNOWN_STATES).all():
        raise ValueError("state holds a code that is not a conventions.STATUS_* value")
    return state.reshape(state.shape[0], state.size // max(state.shape[0], 1) if state.ndim == 2 else 1), state.shape


def _walk(state: ArrayLike) -> tuple[NDArray[np.int32], NDArray[np.int32]]:
    """Length and span so far of the episode each low window belongs to."""
    grid, shape = _grid(state)
    low = np.isin(grid, LOW_STATES)
    ending = np.isin(grid, ENDING_STATES)
    silent = np.isin(grid, SILENT_STATES)
    length = np.zeros(grid.shape, dtype=np.int32)
    span = np.zeros(grid.shape, dtype=np.int32)
    units = grid.shape[1]
    count = np.zeros(units, dtype=np.int32)       # low windows in the open episode
    start = np.full(units, -1, dtype=np.int32)    # its first low window, -1 if none is open
    streak = np.zeros(units, dtype=np.int32)      # silent windows in a row
    for t in range(grid.shape[0]):
        streak = np.where(silent[t], streak + 1, 0)
        closed = ending[t] | (streak >= MAX_SILENT)
        count[closed] = 0
        start[closed] = -1
        start = np.where(low[t] & (start < 0), t, start)
        count[low[t]] += 1
        length[t] = np.where(low[t], count, 0)
        span[t] = np.where(low[t], t - start + 1, 0)
    return length.reshape(shape), span.reshape(shape)


def low_runs(state: ArrayLike) -> NDArray[np.int32]:
    """Number of low windows so far in the episode each window belongs to.

    Parameters
    ----------
    state : array_like of int, shape ``(T,)`` or ``(T, U)``
        ``conventions.STATUS_*`` per window (and unit), in time order.

    Returns
    -------
    ndarray of int32, same shape
        For a window that reads low (WATCH or ALARM): how many low windows
        its episode holds up to and including it (1 for the first). 0 for
        every other window.

    Raises
    ------
    ValueError
        If ``state`` has no window axis or more than two axes, or holds a
        code that is not a status.
    TypeError
        If ``state`` is not an integer array.

    Notes
    -----
    Past only: the value of window ``t`` uses windows up to ``t``.
    """
    return _walk(state)[0]


def run_spans(state: ArrayLike) -> NDArray[np.int32]:
    """Calendar windows from the first low window of an episode to each low window.

    Parameters
    ----------
    state : array_like of int, shape ``(T,)`` or ``(T, U)``

    Returns
    -------
    ndarray of int32, same shape
        For a window that reads low: the number of windows from its
        episode's first low window to it, both included, counting the
        silent and regional windows in between. 0 for every other window.
        Never less than :func:`low_runs` at the same place.
    """
    return _walk(state)[1]


class Episodes(NamedTuple):
    """The episodes of several units, one row per episode, columnar.

    Attributes
    ----------
    unit : ndarray of int64
        Position of the unit (column of the state array).
    start, end : ndarray of int64
        First and last low window of the episode (window positions).
    length : ndarray of int64
        Low windows in it.
    span : ndarray of int64
        ``end - start + 1``: calendar windows covered.
    open : ndarray of bool
        True if nothing had ended it by the last window given: it may
        still be running.
    worst : ndarray of int64
        ``STATUS_ALARM`` if any window was an alarm, else ``STATUS_WATCH``.
    """

    unit: NDArray[np.int64]
    start: NDArray[np.int64]
    end: NDArray[np.int64]
    length: NDArray[np.int64]
    span: NDArray[np.int64]
    open: NDArray[np.bool_]
    worst: NDArray[np.int64]


def episodes(state: ArrayLike) -> Episodes:
    """Every low episode of every unit.

    Parameters
    ----------
    state : array_like of int, shape ``(T, U)``
        ``conventions.STATUS_*`` per window and unit.

    Returns
    -------
    Episodes
        Ordered by unit, then by start.

    Raises
    ------
    ValueError
        If ``state`` is not two-dimensional.
    """
    state = np.asarray(state)
    if state.ndim != 2:
        raise ValueError(f"state must have shape (T, U), got {state.shape}")
    _grid(state)  # the same checks as the running counts
    length, span = _walk(state)
    low = length > 0
    rows: list[tuple[int, int, int, int, bool, int]] = []
    last = state.shape[0] - 1
    for u in range(state.shape[1]):
        where = np.nonzero(low[:, u])[0]
        if where.size == 0:
            continue
        # a new episode begins wherever the running length is 1
        starts = where[length[where, u] == 1]
        for i, first in enumerate(starts):
            members = where[(where >= first) & (where < (starts[i + 1] if i + 1 < starts.size else last + 1))]
            end = int(members[-1])
            after = state[end + 1:, u]
            ended = np.isin(after, ENDING_STATES)
            silent = np.isin(after, SILENT_STATES)
            # closed by an ending window, by a later episode, or by MAX_SILENT silent windows in a row
            streak = best = 0
            for flag, stop in zip(silent.tolist(), ended.tolist()):
                if stop:
                    break
                streak = streak + 1 if flag else 0
                best = max(best, streak)
            closed = bool(ended.any()) or i + 1 < starts.size or best >= MAX_SILENT
            worst = c.STATUS_ALARM if (state[members, u] == c.STATUS_ALARM).any() else c.STATUS_WATCH
            rows.append((u, int(first), end, int(members.size), not closed, worst))
    columns = list(zip(*rows)) if rows else [[], [], [], [], [], []]
    unit, first, end, count, still_open, worst = (np.asarray(x) for x in columns)
    return Episodes(
        unit=unit.astype(np.int64), start=first.astype(np.int64), end=end.astype(np.int64), length=count.astype(np.int64),
        span=(end - first + 1).astype(np.int64) if rows else np.zeros(0, dtype=np.int64),
        open=still_open.astype(bool), worst=worst.astype(np.int64),
    )


class UnitSummary(NamedTuple):
    """Per-unit counts. One value per unit.

    Attributes
    ----------
    count : ndarray of int64, shape ``(U,)``
        Episodes in the record.
    longest : ndarray of int64, shape ``(U,)``
        Low windows in the longest one; 0 if none.
    longest_span : ndarray of int64, shape ``(U,)``
        Calendar windows covered by the episode of the greatest span.
    low_windows : ndarray of int64, shape ``(U,)``
        Windows that read WATCH or ALARM.
    regional_windows : ndarray of int64, shape ``(U,)``
        Windows that read REGIONAL.
    judged_windows : ndarray of int64, shape ``(U,)``
        Windows that read NORMAL, WATCH, ALARM or REGIONAL: what the two
        counts above should be set against.
    """

    count: NDArray[np.int64]
    longest: NDArray[np.int64]
    longest_span: NDArray[np.int64]
    low_windows: NDArray[np.int64]
    regional_windows: NDArray[np.int64]
    judged_windows: NDArray[np.int64]


def summarise(state: ArrayLike) -> UnitSummary:
    """Episode counts per unit.

    Parameters
    ----------
    state : array_like of int, shape ``(T, U)``
        ``conventions.STATUS_*`` per window and unit, in time order.

    Returns
    -------
    UnitSummary

    Raises
    ------
    ValueError, TypeError
        As :func:`episodes`.
    """
    state = np.asarray(state)
    found = episodes(state)
    units = state.shape[1]
    longest = np.zeros(units, dtype=np.int64)
    longest_span = np.zeros(units, dtype=np.int64)
    np.maximum.at(longest, found.unit, found.length)
    np.maximum.at(longest_span, found.unit, found.span)
    low = np.isin(state, LOW_STATES)
    regional = state == c.STATUS_REGIONAL
    judged = low | regional | (state == c.STATUS_NORMAL)
    return UnitSummary(
        count=np.bincount(found.unit, minlength=units).astype(np.int64), longest=longest, longest_span=longest_span,
        low_windows=low.sum(axis=0).astype(np.int64), regional_windows=regional.sum(axis=0).astype(np.int64),
        judged_windows=judged.sum(axis=0).astype(np.int64),
    )


def unseen_runs(state: ArrayLike) -> NDArray[np.int32]:
    """How many windows in a row a unit has gone unobserved.

    Parameters
    ----------
    state : array_like of int, shape ``(T,)`` or ``(T, U)``
        ``conventions.STATUS_*`` per window (and unit), in time order.

    Returns
    -------
    ndarray of int32, same shape
        For a window that is "not observed" (under half of the unit's usual
        light in cells with a usable value): the number of consecutive
        such windows up to and including it. 0 for every window that was
        observed, whatever it then read.

    Raises
    ------
    ValueError
        If ``state`` has no window axis or more than two axes.

    Notes
    -----
    Past only. Long runs are mostly small units: 114 of the 155
    sub-districts with a run of 12 or more have under 20 lit cells.
    """
    grid, shape = _grid(state)
    unseen = grid == c.STATUS_NOT_OBSERVED
    out = np.zeros(grid.shape, dtype=np.int32)
    count = np.zeros(grid.shape[1], dtype=np.int32)
    for t in range(grid.shape[0]):
        count = np.where(unseen[t], count + 1, 0)
        out[t] = count
    return out.reshape(shape)
