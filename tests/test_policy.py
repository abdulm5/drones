from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.policy import check_policy


def row(status="allowed", state="06", crop=2):
    # Synthetic catalog used only in tests; never shipped as real product eligibility.
    return {"state_fips": state, "crop_cdl_code": crop, "product_name": "test-only product",
            "status": status, "authority": "test fixture", "citation": "test fixture"}


@pytest.mark.parametrize("state,crop,product", [("06",24,"test-only product"),("15",2,"test-only product"),("06",2,"absent product")])
def test_unknown_combinations_veto_human_go(state,crop,product):
    result = check_policy(state,crop,product,True,catalog=[row()])
    assert result["status"] == "unknown"
    assert not result["application_unlocked"]


@pytest.mark.parametrize("status,human,expected", [("allowed",False,False),("allowed",True,True),
    ("restricted",False,False),("restricted",True,True),("prohibited",True,False),("invalid",True,False)])
def test_independent_gates(status,human,expected):
    result = check_policy("06",2,"test-only product",human,catalog=[row(status)])
    assert result["application_unlocked"] is expected


def test_prohibition_wins_conflicting_rows():
    result = check_policy("06",2,"test-only product",True,catalog=[row(),row("prohibited")])
    assert not result["application_unlocked"]


def test_real_catalog_has_no_unverified_allowed_products():
    for state in ["06","15"]:
        result = check_policy(state,2,"Lorsban Advanced",True)
        assert result["status"] == "prohibited"
        assert result["row"]["citation"].startswith("https://")


def test_api_cannot_apply_without_both_gates(monkeypatch):
    client = TestClient(main.app)
    record = {"result": {"status": "completed", "path": [], "trace": []},
              "packet": {"state_fips": "06", "cdl": {"code": 2}}, "gate": None}
    monkeypatch.setattr(main,"missions",{"demo":record})
    assert client.post('/apply',json={"mission_id":"demo"}).status_code == 403
    approved = client.post('/gate',json={"mission_id":"demo","human_go":True}).json()
    assert not approved["application_unlocked"]
    assert client.post('/apply',json={"mission_id":"demo"}).status_code == 403
    denied = client.post('/gate',json={"mission_id":"demo","human_go":True,"product_name":"Lorsban Advanced"}).json()
    assert denied["status"] == "prohibited"
    before = deepcopy(record["gate"])
    test = client.post('/gate',json={"mission_id":"demo","human_go":True,"product_name":"Lorsban Advanced","state_override":"15"}).json()
    assert test["simulated_policy_test"]
    assert test["field_state_fips"] == "06"
    assert record["gate"] == before
    assert client.post('/apply',json={"mission_id":"demo"}).status_code == 403


def test_synthetic_allowed_row_unlocks_only_completed_mission(monkeypatch):
    record = {"result": {"status": "completed", "path": [[1,2],[1,3]], "trace": []},
              "packet": {"state_fips": "06", "cdl": {"code": 2}}, "gate": None}
    monkeypatch.setattr(main,"missions",{"demo":record})
    monkeypatch.setattr(main,"check_policy",lambda state,crop,product,human: check_policy(state,crop,product,human,catalog=[row()]))
    client = TestClient(main.app)
    client.post('/gate',json={"mission_id":"demo","human_go":True,"product_name":"test-only product"})
    result=client.post('/apply',json={"mission_id":"demo"})
    assert result.status_code == 200
    assert result.json()["label"] == "SIMULATED APPLICATION"
    record["result"]["status"] = "returned_early"
    assert client.post('/apply',json={"mission_id":"demo"}).status_code == 403


def test_simulate_requires_current_snapshot(monkeypatch):
    monkeypatch.setattr(main, "snapshot", {"snapshot_id":"current","fields":[]})
    result=TestClient(main.app).post('/simulate',json={"snapshot_id":"old","field_id":"DWR-1"})
    assert result.status_code == 409
