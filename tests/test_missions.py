from copy import deepcopy

import pytest
from shapely.geometry import LineString, Polygon

from backend.config import DATA, DEPOT
from backend.fusion import fuse
from backend.simulation import TO_LONLAT, simulate, verify_track, visibility_route


@pytest.fixture(scope="module")
def observation():
    if not (DATA / 'clip_summary.json').exists():
        pytest.skip("Local raster fixture is intentionally untracked")
    return fuse(offline=True)


@pytest.mark.parametrize("low,exclusion", [(False,False),(False,True),(True,False),(True,True)])
def test_all_fixture_fields_respect_reserve_and_full_segment_boundaries(observation, low, exclusion):
    for field in observation["fields"]:
        result = simulate(field, low_battery=low, exclusion_enabled=exclusion)
        if result["status"] == "deferred":
            continue
        assert result["simulated"] is True
        assert result["path"][-1] == pytest.approx(DEPOT)
        assert result["battery_at_landing_pct"] >= 25
        assert result["verification"]["geofence_violations"] == 0
        assert result["verification"]["exclusion_violations"] == 0
        assert result["verification"]["battery_reserve_violations"] == 0


def test_low_battery_changes_execution(observation):
    field = observation["fields"][0]
    normal = simulate(field)
    low = simulate(field, low_battery=True)
    assert normal["status"] == "completed"
    assert low["status"] == "returned_early"
    assert 0 < low["samples"] < normal["samples"]
    assert low["distance_m"] < normal["distance_m"]


def test_exclusion_changes_plan(observation):
    field = observation["fields"][0]
    clear = simulate(field, exclusion_enabled=False)
    excluded = simulate(field, exclusion_enabled=True)
    assert clear["path"] != excluded["path"]
    assert excluded["rejected_segments"]
    assert not clear["rejected_segments"]


@pytest.mark.parametrize("scenario", ["cloud", "stale"])
def test_observation_scenarios_defer_without_faking_observations(observation, scenario):
    field = observation["fields"][0]
    scene_time = field["packet"]["scene_datetime"]
    result = simulate(field, **{scenario: True})
    assert result["action"] == "defer_observation"
    assert result["trace"] == []
    assert field["packet"]["scene_datetime"] == scene_time


def test_concave_connector_does_not_cut_outside_field():
    area = Polygon([(0,0),(100,0),(100,100),(65,100),(65,35),(35,35),(35,100),(0,100)])
    path = visibility_route((10,90),(90,90),area)
    assert len(path) > 2
    assert area.buffer(.03).covers(LineString(path))


def test_checker_catches_segment_crossing_hole_and_exclusion():
    boundary = Polygon([(0,0),(100,0),(100,100),(0,100)], holes=[[(40,40),(60,40),(60,60),(40,60)]])
    exclusion = Polygon([(45,0),(55,0),(55,100),(45,100)])
    trace = [{"position": TO_LONLAT(x,y), "battery_pct": 30} for x,y in [(10,50),(90,50)]]
    result = verify_track(trace,boundary,exclusion)
    assert result["geofence_violations"] == 1
    assert result["exclusion_violations"] == 1
