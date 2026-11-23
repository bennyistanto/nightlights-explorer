"""Cells to admin units, on small cases worked by hand."""

import numpy as np
import pytest
from shapely.geometry import box

from ntl import zonal
from ntl.read import Grid


def test_to_level_follows_the_code_prefix():
    codes = np.array([520801, 317101, 0])
    assert zonal.to_level(codes, "subdistrict").tolist() == [520801, 317101, 0]
    assert zonal.to_level(codes, "district").tolist() == [5208, 3171, 0]
    assert zonal.to_level(codes, "province").tolist() == [52, 31, 0]
    with pytest.raises(ValueError):
        zonal.to_level(codes, "village")
    with pytest.raises(ValueError, match="unknown level"):
        zonal.to_level(codes, "regency")  # the name used for adm2 before 2026-11-22


def test_zero_code_defers_to_the_level_above():
    # Rows as in the sub-district boundary file:
    #   a coded sub-district; an area held by district 1218; an area held by
    #   province 81; an area with no code at all.
    province = np.array([11, 12, 81, 0])
    district = np.array([1101, 1218, 0, 0])
    subdistrict = np.array([110101, 0, 0, 0])
    out = zonal.resolve_levels(province, district, subdistrict)
    assert set(out) == {"province", "district", "subdistrict"}
    assert out["subdistrict"].tolist() == [110101, 0, 0, 0]
    assert out["district"].tolist() == [1101, 1218, 0, 0]
    assert out["province"].tolist() == [11, 12, 81, 0]


def test_finer_code_wins_and_contradictions_are_refused():
    # A stored province or district of 0 beside a coded sub-district is filled from the sub-district.
    out = zonal.resolve_levels(np.array([0]), np.array([0]), np.array([520801]))
    assert (out["province"][0], out["district"][0]) == (52, 5208)
    with pytest.raises(ValueError, match="does not start with its district"):
        zonal.resolve_levels(np.array([52]), np.array([5207]), np.array([520801]))
    with pytest.raises(ValueError, match="does not start with its province"):
        zonal.resolve_levels(np.array([51]), np.array([5208]), np.array([0]))
    with pytest.raises(ValueError, match="equal length"):
        zonal.resolve_levels(np.array([52]), np.array([5208, 5209]), np.array([0]))
    with pytest.raises(TypeError):
        zonal.resolve_levels(np.array([52.0]), np.array([5208]), np.array([0]))


def test_province_conflicts_finds_the_three_kinds():
    code_of_name = {"Jawa Timur": 35, "Sumatera Barat": 13, "Sulawesi Selatan": 73, "Maluku": 81}
    province = np.array([37, 82, 35, 81, 0, 35, 99])
    names = ["Sulawesi Selatan", "Jawa Timur", "Sumatera Barat", "Maluku", None, "Jawa Timur", float("nan")]
    found = zonal.province_conflicts(province, names, code_of_name)
    # 37 is no province (its name says 73); 82 is not a code in this table and
    # the name says 35; 35 is a real code but the name says 13; 99 is unknown
    # with no name. The consistent rows (81 Maluku, 35 Jawa Timur) and the
    # uncoded row are not reported.
    assert found == [(0, 37, 73), (1, 82, 35), (2, 35, 13), (6, 99, None)]


def test_province_conflicts_can_report_names_it_cannot_check():
    code_of_name = {"Daerah Khusus Ibukota Jakarta": 31, "Banten": 36}
    province = np.array([31, 36, 31])
    names = ["DKI Jakarta", "Banten", None]
    # By default a known code beside a name that is not in the table passes unseen.
    assert zonal.province_conflicts(province, names, code_of_name) == []
    # Asked, it is returned as "cannot be checked"; a missing name is not a name.
    assert zonal.province_conflicts(province, names, code_of_name, report_unknown_names=True) == [(0, 31, None)]


def test_burn_index_gives_the_position_of_the_polygon():
    grid = Grid(110.0, 0.0, 1.0, (2, 2))
    everything = box(110.0, -2.0, 112.0, 0.0)
    north_row = box(110.0, -1.0, 112.0, 0.0)
    # 1-based position; the later polygon wins where two overlap; 0 where none.
    assert zonal.burn_index([everything, north_row], grid).tolist() == [[2, 2], [1, 1]]
    assert zonal.burn_index([north_row], grid).tolist() == [[1, 1], [0, 0]]
    assert zonal.burn_index([], grid).tolist() == [[0, 0], [0, 0]]


def test_burn_units_uses_the_cell_centre():
    # 2 x 2 cells of one degree: centres at 110.5 and 111.5 E, 0.5 and 1.5 S.
    grid = Grid(110.0, 0.0, 1.0, (2, 2))
    # Reaches 111.4 E: covers 40% of the east column but not its centres.
    west_unit = box(110.0, -2.0, 111.4, 0.0)
    burned = zonal.burn_units([(west_unit, 520801)], grid)
    assert burned.tolist() == [[520801, 0], [520801, 0]]
    assert burned.dtype == np.int64


def test_burn_units_skips_uncoded_and_lets_the_later_polygon_win():
    grid = Grid(110.0, 0.0, 1.0, (2, 2))
    everything = box(110.0, -2.0, 112.0, 0.0)
    north_row = box(110.0, -1.0, 112.0, 0.0)
    burned = zonal.burn_units([(everything, 7), (north_row, 9), (everything, 0)], grid)
    assert burned.tolist() == [[9, 9], [7, 7]]
    assert zonal.burn_units([(everything, 0)], grid).tolist() == [[0, 0], [0, 0]]


def test_two_polygons_with_one_code_form_one_unit():
    grid = Grid(110.0, 0.0, 1.0, (1, 3))
    burned = zonal.burn_units([(box(110.0, -1.0, 111.0, 0.0), 5), (box(112.0, -1.0, 113.0, 0.0), 5)], grid)
    assert burned.tolist() == [[5, 0, 5]]


def test_unit_sums_by_hand():
    values = np.array([1.0, 2.0, np.nan, 4.0, 5.0])
    codes = np.array([10, 10, 10, 20, 0])
    weights = np.array([1.0, 1.0, 2.0, 3.0, 9.0])
    out = zonal.unit_sums(values, codes, weights)
    # Unit 10: cells 1 and 2 used (sum 3), the NaN cell left out; weight used 2 of 4.
    # Unit 20: its one cell used. The cell with code 0 belongs to no unit.
    assert out.codes.tolist() == [10, 20]
    assert out.total.tolist() == [3.0, 4.0]
    assert out.cells.tolist() == [2, 1]
    assert out.coverage.tolist() == [0.5, 1.0]


def test_unobserved_is_left_out_not_counted_as_dark():
    out = zonal.unit_sums(np.array([np.nan, np.nan]), np.array([10, 10]))
    assert out.total.tolist() == [0.0] and out.cells.tolist() == [0] and out.coverage.tolist() == [0.0]


def test_default_weights_give_share_of_cells():
    out = zonal.unit_sums(np.array([[1.0, np.nan], [1.0, 1.0]]), np.array([[3, 3], [3, 3]]))
    assert out.coverage.tolist() == [0.75]


def test_unit_sums_refuses_bad_input():
    with pytest.raises(ValueError, match="shapes differ"):
        zonal.unit_sums(np.zeros(3), np.zeros(2, dtype=int))
    # Same number of cells, different layout: must not be paired up silently.
    with pytest.raises(ValueError, match="shapes differ"):
        zonal.unit_sums(np.zeros((2, 3)), np.ones((3, 2), dtype=int))
    with pytest.raises(ValueError, match="weights"):
        zonal.unit_sums(np.zeros(2), np.array([1, 1]), np.array([1.0, -1.0]))
    with pytest.raises(TypeError, match="integers"):
        zonal.unit_sums(np.zeros(2), np.array([np.nan, 3.7]))
    with pytest.raises(ValueError, match="negative"):
        zonal.unit_sums(np.zeros(2), np.array([-5, 3]))


def test_weights_outside_every_unit_are_not_looked_at():
    # Sea cells have no usual light: NaN there must not stop the land.
    out = zonal.unit_sums(np.array([np.nan, 5.0]), np.array([0, 7]), np.array([np.nan, 5.0]))
    assert out.codes.tolist() == [7] and out.total.tolist() == [5.0] and out.coverage.tolist() == [1.0]


def test_unit_with_no_weight_has_zero_coverage():
    out = zonal.unit_sums(np.array([1.0, 2.0]), np.array([4, 4]), np.array([0.0, 0.0]))
    assert out.coverage.tolist() == [0.0] and out.total.tolist() == [3.0]


def test_empty_and_unitless_input_give_empty_float_results():
    for values, codes in ((np.array([]), np.array([], dtype=int)), (np.array([1.0, 2.0]), np.array([0, 0]))):
        out = zonal.unit_sums(values, codes)
        assert out.codes.size == 0 and out.total.dtype == np.float64 and out.cells.dtype == np.int64


def test_codes_must_be_whole_and_not_negative():
    grid = Grid(110.0, 0.0, 1.0, (1, 1))
    square = box(110.0, -1.0, 111.0, 0.0)
    with pytest.raises(TypeError):
        zonal.burn_units([(square, 5208.7)], grid)
    with pytest.raises(ValueError):
        zonal.burn_units([(square, -1)], grid)
    with pytest.raises(ValueError, match="negative"):
        zonal.to_level(np.array([-520801]), "district")
    with pytest.raises(TypeError):
        zonal.to_level(np.array([520801.0]), "district")


def test_large_codes_and_multipolygons_survive():
    from shapely.geometry import MultiPolygon

    grid = Grid(110.0, 0.0, 1.0, (1, 3))
    two_parts = MultiPolygon([box(110.0, -1.0, 111.0, 0.0), box(112.0, -1.0, 113.0, 0.0)])
    big = 2**40
    assert zonal.burn_units([(two_parts, big)], grid).tolist() == [[big, 0, big]]
    # A polygon wholly outside the grid burns nothing.
    assert zonal.burn_units([(box(150.0, 10.0, 151.0, 11.0), 9)], grid).tolist() == [[0, 0, 0]]
