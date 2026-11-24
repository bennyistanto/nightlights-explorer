"""Writing output files so that a reader never sees half of one.

Every writer in the package that produces a file another program may be
reading (the page's data under ``site/data``, a cache on a data drive) goes
through :func:`replace_with`: the content is written under a temporary name
and renamed over the target once it is complete. On Windows a file that a
preview server or a sync client holds open cannot be replaced for a moment,
so the rename is retried for a few seconds before it is reported.

No science here, and no dependence on the rest of the package.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger("ntl.files")

#: Tries at renaming a finished file over one that another program holds open. Picked:
#: with the waits below it comes to about 7 seconds, longer than a preview server's reload.
REPLACE_ATTEMPTS = 8


def replace_with(path: Path, write: Callable[[Path], object]) -> int:
    """Write through a temporary file and rename it over ``path``.

    Parameters
    ----------
    path : Path
        Target file; its folder is created. An existing file is replaced
        only once the new one is complete.
    write : callable
        Called with the temporary path; must write the whole content there.

    Returns
    -------
    int
        Size of the file written, bytes.

    Raises
    ------
    PermissionError
        If the target is still held open by another program after
        ``REPLACE_ATTEMPTS`` tries (about 7 seconds). The first failed try
        is logged, so the wait is not silent. Any error leaves the old file
        as it was and removes the temporary one.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    try:
        write(temporary)
        # On Windows a file that another program has open (a preview server
        # watching the folder, a sync client) cannot be replaced for a moment.
        for attempt in range(REPLACE_ATTEMPTS):
            try:
                os.replace(temporary, path)
                break
            except PermissionError as exc:
                if attempt == REPLACE_ATTEMPTS - 1:
                    raise PermissionError(f"{path} is still held open by another program (a preview server or a sync client?): {exc}") from exc
                if attempt == 0:
                    log.warning("%s is held open by another program; retrying for a few seconds", path)
                time.sleep(0.25 * (attempt + 1))
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return path.stat().st_size


def write_bytes(path: Path, data: bytes) -> int:
    """Write bytes atomically. Returns the size written."""
    return replace_with(path, lambda temporary: temporary.write_bytes(data))


def write_json(path: Path, payload: Any, indent: int | None = None) -> int:
    """Write JSON atomically, as UTF-8 with ``\\n`` line ends on every platform.

    Parameters
    ----------
    path : Path
        Target file.
    payload : any
        JSON-serialisable content. NaN and infinity are refused
        (``ValueError``): a reader in a browser cannot parse them.
    indent : int, optional
        Indentation for a file meant to be read by people. Default: compact.

    Returns
    -------
    int
        Size of the file written, bytes. The same payload gives the same
        bytes on every platform.
    """
    separators = (",", ":") if indent is None else None
    text = json.dumps(payload, ensure_ascii=False, separators=separators, indent=indent, allow_nan=False)
    return write_bytes(path, text.encode("utf-8"))


def save_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> int:
    """Write a compressed ``.npz`` atomically. Returns the size written."""
    def write(temporary: Path) -> None:
        with open(temporary, "wb") as handle:  # a handle, so that numpy does not append ".npz" to the temporary name
            np.savez_compressed(handle, **arrays)

    return replace_with(path, write)
