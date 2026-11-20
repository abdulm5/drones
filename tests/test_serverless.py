from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import main, sessions
from backend.config import DATA
from backend.fusion import fuse
from backend.policy import check_policy


@pytest.fixture(autouse=True)
def stable_signing_key(monkeypatch):
    monkeypatch.setenv("AGRIFORGE_SIGNING_KEY", "test-only-signing-key-with-at-least-32-bytes")


def test_session_survives_another_process_key(monkeypatch):
    token = sessions.seal("mission", {"mission_id": "test"})
    monkeypatch.setattr(sessions, "LOCAL_KEY", b"another-worker-local-key")
    assert sessions.unseal(token, "mission") == {"mission_id": "test"}


def test_sessions_expire_and_cannot_change_purpose(monkeypatch):
    monkeypatch.setattr(sessions.time, "time", lambda: 1000)
    token = sessions.seal("snapshot", {"x": 1}, ttl=10)
    with pytest.raises(sessions.SessionError):
        sessions.unseal(token, "gate")
    monkeypatch.setattr(sessions.time, "time", lambda: 1011)
    with pytest.raises(sessions.SessionError, match="expired"):
        sessions.unseal(token, "snapshot")


def test_modified_payload_or_signature_is_rejected():
    token = sessions.seal("gate", {"human_go": False})
    body, signature = token.split(".")
    for modified in ["A" + body[1:] + "." + signature, body + "." + "A" + signature[1:]]:
        with pytest.raises(sessions.SessionError):
            sessions.unseal(modified, "gate")


def test_hosted_runtime_requires_a_stable_private_key(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("AGRIFORGE_SIGNING_KEY")
    with pytest.raises(sessions.SessionError, match="Set AGRIFORGE_SIGNING_KEY") as error:
        sessions.seal("snapshot", {})
    assert error.value.status_code == 503
    assert TestClient(main.app).post('/api/fuse', json={}).status_code == 503


@pytest.fixture(scope="module")
def observation():
    if not (DATA / "clip_summary.json").exists():
        pytest.skip("Supplied local fixtures are intentionally not committed")
    return fuse(offline=True)


def cold_start(monkeypatch):
    monkeypatch.setattr(main, "snapshot", None)
    monkeypatch.setattr(main, "snapshot_at", 0)
    monkeypatch.setattr(main, "missions", {})
    monkeypatch.setattr(main, "tile_cache", {})


def test_entire_mission_flow_survives_cold_starts(observation, monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(main, "RUNTIME", tmp_path / "runtime")
    monkeypatch.setattr(main, "fuse", lambda offline=False: deepcopy(observation))
    cold_start(monkeypatch)
    client = TestClient(main.app)
    response = client.post('/api/fuse', json={})
    assert response.status_code == 200
    assert len(response.content) < 4_500_000
    fusion = response.json()
    field = fusion['fields'][0]
    assert fusion['ndvi_images'][field['id']].startswith('data:image/png;base64,')
    cold_start(monkeypatch)
    mission = client.post('/api/simulate', json={"snapshot_id": fusion['snapshot_id'],
        "snapshot_token": fusion['snapshot_token'], "field_id": field['id']}).json()
    assert mission['status'] == 'completed'
    assert (tmp_path/'runtime/AF-1.json').read_text().startswith('{"simulated": true')
    session = {"mission_id": mission['mission_id'], "mission_token": mission['mission_token']}
    cold_start(monkeypatch)
    findings = client.post('/api/findings', json=session)
    assert findings.status_code == 200
    assert findings.json()['polygon_id'] == field['id']
    cold_start(monkeypatch)
    advisory = client.post('/api/advice', json=session)
    assert advisory.json()['action'] == 'request_soil_measurement'
    cold_start(monkeypatch)
    decision = client.post('/api/gate', json=session | {"human_go": True}).json()
    assert decision['status'] == 'unknown'
    assert not decision['application_unlocked']
    cold_start(monkeypatch)
    assert client.post('/api/apply', json={"mission_id": mission['mission_id'],
        "gate_token": decision['gate_token']}).status_code == 403

    # Test-only approval: no such product is shipped in the policy catalog.
    allowed = {"state_fips": "06", "crop_cdl_code": field['packet']['cdl']['code'],
               "product_name": "synthetic test product", "status": "allowed",
               "authority": "test", "citation": "test"}
    monkeypatch.setattr(main, "check_policy", lambda state, crop, product, human:
        check_policy(state, crop, product, human, catalog=[allowed]))
    decision = client.post('/api/gate', json=session | {"human_go": True, "product_name": allowed['product_name']}).json()
    assert decision['application_unlocked']
    cold_start(monkeypatch)
    application = {"mission_id": mission['mission_id'], "gate_token": decision['gate_token']}
    assert client.post('/api/apply', json=application).json()['label'] == 'SIMULATED APPLICATION'
    allowed['status'] = 'prohibited'
    assert client.post('/api/apply', json=application).status_code == 403  # Current catalog wins over old approval.
    assert client.post('/api/apply', json=application | {"mission_id": "another-mission"}).status_code == 403
    assert client.post('/api/gate', json=session | {"mission_id": "another-mission"}).status_code == 403


def test_python_entrypoint_serves_the_backend():
    from deployment.observation_entry import app
    assert TestClient(app).get('/api/health').json()['ok']


def test_python_entrypoint_explains_startup_failure(monkeypatch):
    import deployment.observation_entry as entrypoint
    monkeypatch.setattr(entrypoint, '_backend', None)
    def missing_dependency(name):
        raise ModuleNotFoundError("test missing dependency")
    monkeypatch.setattr(entrypoint, 'import_module', missing_dependency)
    response = TestClient(entrypoint.app).get('/api/health')
    assert response.status_code == 503
    assert response.json()['code'] == 'API_STARTUP_FAILED'
    assert 'test missing dependency' in response.json()['detail']
