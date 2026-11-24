"""DMSP yearly composites: names, the window of a box on the global grid, and an archive cropped to a box."""

import gzip
import io
import tarfile

import numpy as np
import pytest

from ntl import dmsp


def test_satellite_and_year_from_a_file_name():
    assert dmsp.satellite_year("F101992.v4.tar") == ("F10", 1992)
    assert dmsp.satellite_year(r"E:\somewhere\F182013.v4c.global.intercal.stable_lights.avg_vis.tif") == ("F18", 2013)
    with pytest.raises(ValueError, match="satellite-year"):
        dmsp.satellite_year("readme.txt")


def test_the_window_of_a_box_lines_up_with_the_viirs_grid():
    rows, cols, grid = dmsp.box_window(dmsp.INDONESIA_BOX)
    # 47 degrees by 18 degrees at 120 cells a degree, plus the cells the box edges cut through
    assert grid.shape == (rows.stop - rows.start, cols.stop - cols.start) == (2161, 5641)
    west, south, east, north = grid.bounds
    assert west <= 94.5 < west + dmsp.DMSP_CELL and north >= 6.5 > north - dmsp.DMSP_CELL
    assert east >= 141.5 and south <= -11.5
    # cell centres sit on multiples of 1/120 degree, so a DMSP cell is exactly two by two 15 arc-second cells:
    # its edges fall on odd multiples of 1/240 degree
    lon, lat = grid.centres()
    np.testing.assert_allclose(lon * 120, np.round(lon * 120), atol=1e-6)
    np.testing.assert_allclose(lat * 120, np.round(lat * 120), atol=1e-6)
    edge = grid.bounds[0] * 240
    assert abs(edge - round(edge)) < 1e-6 and round(edge) % 2 == 1
    # the whole grid is its own window
    full_rows, full_cols, full = dmsp.box_window((-180.0, -65.0, 180.0, 75.0))
    assert full.shape == dmsp.DMSP_SHAPE and (full_rows.start, full_cols.start) == (0, 0)
    with pytest.raises(ValueError, match="not inside"):
        dmsp.box_window((94.5, -70.0, 141.5, 6.5))
    with pytest.raises(ValueError, match="west, south, east, north"):
        dmsp.box_window((141.5, -11.5, 94.5, 6.5))


def test_a_grids_own_bounds_give_the_grid_back():
    rng = np.random.default_rng(3)
    for _ in range(300):
        west, south = rng.uniform(-179, 170), rng.uniform(-64, 60)
        grid = dmsp.box_window((west, south, west + rng.uniform(0.01, 9), south + rng.uniform(0.01, 9)))[2]
        assert dmsp.box_window(grid.bounds)[2] == grid          # edges on cell edges gain no row or column
        row, col = dmsp.grid_offsets(grid)
        assert dmsp.box_window(grid.bounds)[:2] == (slice(row, row + grid.shape[0]), slice(col, col + grid.shape[1]))
    # a box inside one cell is that cell
    assert dmsp.box_window((100.001, 0.001, 100.002, 0.002))[2].shape == (1, 1)


def _tif(array, west=10.0, north=4.0, cell=1.0):
    """A small single-band GeoTIFF as bytes, with its corner and cell in the header."""
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    memory = rasterio.MemoryFile()
    with memory.open(driver="GTiff", height=array.shape[0], width=array.shape[1], count=1, dtype=array.dtype, crs="EPSG:4326",
                     transform=from_origin(west, north, cell, cell)) as target:
        target.write(array, 1)
    return memory.read()


def _tif_gz(array):
    return gzip.compress(_tif(array))


def _toy_grid(monkeypatch):
    """A toy "global" grid of 4 rows by 6 columns of one degree, north-west corner at 10 E, 4 N."""
    monkeypatch.setattr(dmsp, "DMSP_SHAPE", (4, 6))
    monkeypatch.setattr(dmsp, "DMSP_CELL", 1.0)
    monkeypatch.setattr(dmsp, "DMSP_WEST", 10.0)
    monkeypatch.setattr(dmsp, "DMSP_NORTH", 4.0)


def test_a_file_is_read_by_its_header_and_a_wrong_corner_is_refused(tmp_path, monkeypatch, caplog):
    _toy_grid(monkeypatch)
    monkeypatch.setattr(dmsp, "HEADER_SLIP", (10.5, 3.5))
    values = np.arange(24, dtype=np.float32).reshape(4, 6) / 2
    good, slipped, shifted, coarse = (tmp_path / n for n in ("good.tif", "slipped.tif", "shifted.tif", "coarse.tif"))
    good.write_bytes(_tif(values))
    slipped.write_bytes(_tif(values, west=10.5, north=3.5))       # the one corner known to be a slip of the header
    shifted.write_bytes(_tif(values, west=11.0))                  # any other corner
    coarse.write_bytes(_tif(values, cell=2.0))
    block, grid = dmsp.read_box(good, (11.5, 1.2, 13.2, 2.9))
    assert block.dtype == np.float32 and block.tolist() == [[3.5, 4.0, 4.5], [6.5, 7.0, 7.5]] and grid.bounds == (11.0, 1.0, 14.0, 3.0)
    with caplog.at_level("WARNING", logger="ntl.dmsp"):
        again = dmsp.read_window(slipped, grid)
    assert again.tolist() == block.tolist() and "read by position" in caplog.text
    with pytest.raises(ValueError, match="corner at"):
        dmsp.read_window(shifted, grid)
    with pytest.raises(ValueError, match="cell of"):
        dmsp.read_window(coarse, grid)


def test_an_archive_is_cropped_to_a_box_with_its_three_layers_kept_apart(tmp_path, monkeypatch):
    _toy_grid(monkeypatch)
    stable = np.arange(24, dtype=np.uint8).reshape(4, 6)
    layers = {"F121999.v4b_web.stable_lights.avg_vis.tif.gz": stable, "F121999.v4b_web.avg_vis.tif.gz": stable + 100,
              "F121999.v4b_web.cf_cvg.tif.gz": (stable + 200).astype(np.uint8)}
    archive = tmp_path / "share" / "F121999.v4.tar"
    archive.parent.mkdir()
    with tarfile.open(archive, "w") as tar:
        for name, array in layers.items():
            data = _tif_gz(array)
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        note = b"read me"
        info = tarfile.TarInfo("README_V4.txt")
        info.size = len(note)
        tar.addfile(info, io.BytesIO(note))
    before = archive.read_bytes()
    # the box 11.5 to 13.2 E, 1.2 to 2.9 N touches columns 1 to 3 and rows 1 to 2
    written = dmsp.crop_archive(archive, tmp_path / "out", tmp_path / "scratch", box=(11.5, 1.2, 13.2, 2.9))
    crop = dmsp.load_crop(written)
    assert (crop.satellite, crop.year) == ("F12", 1999) and written.name == "F121999.npz"
    assert crop.stable.tolist() == [[7, 8, 9], [13, 14, 15]]
    assert crop.average.tolist() == [[107, 108, 109], [113, 114, 115]]            # the raw average, not the stable lights again
    assert crop.observations.tolist() == [[207, 208, 209], [213, 214, 215]]
    assert crop.grid.bounds == (11.0, 1.0, 14.0, 3.0)
    assert archive.read_bytes() == before and not list((tmp_path / "scratch").iterdir())     # the archive is only read; nothing is left behind
    assert crop.stable.dtype == crop.observations.dtype == np.uint8
    # a layer missing from the archive is named
    broken = tmp_path / "share" / "F121998.v4.tar"
    with tarfile.open(broken, "w") as tar:
        data = _tif_gz(stable)
        info = tarfile.TarInfo("F121998.v4b_web.stable_lights.avg_vis.tif.gz")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    with pytest.raises(ValueError, match="expected one average layer"):
        dmsp.crop_archive(broken, tmp_path / "out", tmp_path / "scratch", box=(11.5, 1.2, 13.2, 2.9))
    # a failure leaves no part file and nothing unpacked
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["F121999.npz"] and not list((tmp_path / "scratch").iterdir())
    # the command: the one good archive is skipped the second time, the bad one makes the run fail and is named
    box = ["--box", "11.5", "1.2", "13.2", "2.9"]
    common = ["--archives", str(archive.parent), "--out", str(tmp_path / "out"), "--scratch", str(tmp_path / "scratch")]
    (tmp_path / "out" / "F121999.npz").unlink()
    assert dmsp.main(common + box) == 1 and (tmp_path / "out" / "F121999.npz").is_file()
    stamp = (tmp_path / "out" / "F121999.npz").stat().st_mtime_ns
    broken.unlink()
    assert dmsp.main(common + box) == 0 and (tmp_path / "out" / "F121999.npz").stat().st_mtime_ns == stamp      # skipped
    assert dmsp.main(common + ["--box", "11.5", "1.2", "14.2", "2.9"]) == 0                                    # another box: cropped again
    assert dmsp.load_crop(tmp_path / "out" / "F121999.npz").stable.shape == (2, 4)
    assert dmsp.main(["--archives", str(tmp_path / "nowhere"), "--out", str(tmp_path / "o"), "--scratch", str(tmp_path / "s")]) == 1
    # a file that is not on the global grid is refused
    monkeypatch.setattr(dmsp, "DMSP_SHAPE", (5, 6))
    with pytest.raises(ValueError, match="expected the global DMSP grid"):
        dmsp.crop_archive(archive, tmp_path / "out2", tmp_path / "scratch", box=(11.5, 1.2, 13.2, 2.9))
