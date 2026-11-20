from datetime import date

import numpy as np
import pytest

from backend.config import DATA
from backend.fusion import load_json, normalized_difference, power_context, process_scene, within_class_gaps


def test_reflectance_offset_changes_ndvi():
    # A DN ratio silently misses the additive Collection 1 offset.
    red, nir = np.array([2000.]), np.array([4000.])
    actual = normalized_difference(nir*.0001-.1, red*.0001-.1)
    assert actual[0] == pytest.approx(.5)
    assert normalized_difference(nir, red)[0] != pytest.approx(.5)


def test_nonpositive_denominators_are_missing():
    result = normalized_difference(np.array([0., -.1, .2]), np.array([0., -.1, .1]))
    assert np.isnan(result[:2]).all()
    assert result[2] == pytest.approx(1/3)


def test_anomalies_use_other_pixels_of_same_class():
    values = np.array([[.1, .3, .4, .5, .5, .6, .7, .7, .8, .9,
                        .01, .02, .03, .04, .05, .06, .07, .08, .09, .10]])
    classes = np.array([[2]*10 + [24]*10])
    valid = np.ones(values.shape, bool)
    actual = within_class_gaps(values, classes, valid)
    for i in range(values.shape[1]):
        peers = values[valid & (classes == classes[0, i])].tolist()
        peers.remove(values[0, i])
        expected = max(0, float(np.quantile(peers, .2)) - values[0, i])
        assert actual[0, i] == pytest.approx(expected, abs=1e-7)


def test_power_retains_fill_values_as_missing_and_precedes_scene():
    raw = {"properties": {"parameter": {"PRECTOTCORR": {"20261117": -999, "20261118": 2},
                                           "T2M": {"20261117": 11, "20261118": -999}}}}
    result = power_context(raw, "2026-11-19T18:54:00Z")
    assert result["start"] == "2026-11-05"
    assert result["end"] == "2026-11-18"
    assert result["days"][-2]["rain_mm"] is None
    assert result["days"][-1]["temperature_c"] is None
    assert result["rain_mm"] == 2
    assert result["rain_days_present"] == 1
    assert result["missing_values"] == 26


@pytest.mark.skipif(not (DATA / 'clip_summary.json').exists(), reason="Local raster fixture is intentionally untracked")
def test_real_clip_mean_and_scene_mask():
    result = process_scene(load_json('sentinel2_item_20261111.json'), fixture=True)
    assert float(np.nanmean(result["ndvi"])) == pytest.approx(.30, abs=.01)
    assert np.isin(result["scl"][result["clear"]], [4,5]).all()
    assert np.isnan(result["ndvi"][~result["clear"]]).all()
