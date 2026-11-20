"""Run with: .venv/bin/uvicorn backend.main:app --port 8000"""
from copy import deepcopy
import base64
from datetime import datetime, timezone
import json
import logging
import math
import os
from threading import Lock
from time import monotonic
from typing import Literal
from uuid import uuid4

import httpx

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .config import BBOX, CENTER, DEPOT, ROOT, RUNTIME
from .consultant import advise
from .fusion import fuse
from .policy import CATALOG, check_policy
from .simulation import simulate
from .sessions import MAX_TOKEN_SIZE, SessionError, seal, signing_key, unseal

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="AGRIFORGE", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
snapshot = None
snapshot_at = 0
fusion_lock = Lock()
missions = {}
tile_cache = {}


@app.exception_handler(SessionError)
def session_error(request, error):
    return JSONResponse(status_code=error.status_code, content={"detail": str(error)})


class FuseRequest(BaseModel):
    refresh: bool = False


class SimulateRequest(BaseModel):
    snapshot_id: str
    snapshot_token: str | None = Field(default=None, max_length=MAX_TOKEN_SIZE)
    field_id: str
    low_battery: bool = False
    cloud: bool = False
    stale: bool = False
    exclusion: bool = True


class GateRequest(BaseModel):
    mission_id: str
    mission_token: str | None = Field(default=None, max_length=MAX_TOKEN_SIZE)
    human_go: bool = False
    product_name: str = Field(default="", max_length=150)
    state_override: Literal["15"] | None = None


class ApplyRequest(BaseModel):
    mission_id: str
    gate_token: str | None = Field(default=None, max_length=MAX_TOKEN_SIZE)


class MissionRequest(BaseModel):
    mission_id: str
    mission_token: str = Field(max_length=MAX_TOKEN_SIZE)


def mission_or_404(mission_id, token=None):
    if token:
        decoded = unseal(token, "mission")
        if decoded.get("mission_id") != mission_id:
            raise HTTPException(403, "Mission does not match its signed session")
        return {"result": decoded["result"], "packet": decoded["packet"], "gate": None}
    if mission_id not in missions:
        raise HTTPException(404, "Mission not found; dispatch an inspection first")
    return missions[mission_id]


@app.get("/health")
def health():
    return {"ok": True, "service": "AGRIFORGE", "simulated": True}


@app.post("/fuse")
def fused(request: FuseRequest = FuseRequest()):
    global snapshot, snapshot_at
    signing_key()  # Fail clearly before network work if the hosted key is missing.
    with fusion_lock:
        if snapshot is None or request.refresh or monotonic() - snapshot_at > 300:
            try:
                result = fuse(offline=os.environ.get("AGRIFORGE_OFFLINE") == "1")
            except FileNotFoundError as exc:
                raise HTTPException(503, "Five Points fixtures are missing. See docs/datasets.md and set AGRIFORGE_DATA.") from exc
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            result["snapshot_id"] = str(uuid4())
            snapshot, snapshot_at = result, monotonic()
        aerial = dict(snapshot["aerial"])
        if aerial["mode"] == "NAIP":
            image_token = seal("aerial", {"item_id": aerial["item_id"]})
            aerial["url"] = f"/api/aerial/tiles/{{z}}/{{x}}/{{y}}.png?image_token={image_token}"
        def image_url(content):
            return "data:image/png;base64," + base64.b64encode(content).decode("ascii")
        return {k: v for k, v in snapshot.items() if k not in ["ndvi_png", "ndvi_fields", "aerial"]} | {
            "aerial": aerial,
            "snapshot_token": seal("snapshot", {"snapshot_id": snapshot["snapshot_id"], "fields": snapshot["fields"]}),
            "ndvi_images": {key: image_url(value) for key, value in snapshot["ndvi_fields"].items()},
            "site": {"name": "UC West Side Research & Extension Center", "place": "Five Points, Fresno County, CA",
                     "center": CENTER, "bbox": BBOX, "state_fips": "06", "depot": DEPOT,
                     "depot_note": "AUTHORED demo depot; not surveyed"},
            "policy_catalog": json.loads(CATALOG.read_text()),
            "ndvi_url": image_url(snapshot["ndvi_png"])}


@app.get("/ndvi.png")
def ndvi(snapshot_id: str, field_id: str | None = None):
    if snapshot is None or snapshot["snapshot_id"] != snapshot_id:
        raise HTTPException(409, "Observation changed; refresh the field evidence")
    if field_id and field_id not in snapshot["ndvi_fields"]:
        raise HTTPException(404, "Unknown field measurement")
    content = snapshot["ndvi_fields"][field_id] if field_id else snapshot["ndvi_png"]
    return Response(content, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.get("/api/aerial/tiles/{z}/{x}/{y}.png")
@app.get("/aerial/tiles/{z}/{x}/{y}.png")
def aerial_tile(z: int, x: int, y: int, snapshot_id: str | None = None, image_token: str | None = None):
    if image_token:
        item_id = unseal(image_token, "aerial")["item_id"]
    elif snapshot is not None and snapshot["snapshot_id"] == snapshot_id and snapshot["aerial"]["mode"] == "NAIP":
        item_id = snapshot["aerial"]["item_id"]
    else:
        raise HTTPException(409, "NAIP observation changed or is unavailable")
    if not 13 <= z <= 20 or not (0 <= x < 2**z and 0 <= y < 2**z):
        raise HTTPException(422, "NAIP tiles are limited to the demo region at zoom 13–20")
    def tile(lon, lat):
        return ((lon+180)/360*2**z, (1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*2**z)
    west, south = tile(BBOX[0], BBOX[1])
    east, north = tile(BBOX[2], BBOX[3])
    if x < math.floor(west) or x > math.floor(east) or y < math.floor(north) or y > math.floor(south):
        raise HTTPException(404, "Tile outside Five Points")
    key = (item_id, z, x, y)
    if key not in tile_cache:
        params = [("collection", "naip"), ("item", item_id),
                  ("assets", "image"), ("bidx", "1"), ("bidx", "2"), ("bidx", "3"), ("rescale", "0,255")]
        try:
            response = httpx.get(f"https://planetarycomputer.microsoft.com/api/data/v1/item/tiles/WebMercatorQuad/{z}/{x}/{y}.png",
                                 params=params, timeout=15)
            response.raise_for_status()
            if "image/png" not in response.headers.get("content-type", "") or len(response.content) > 2_000_000:
                raise ValueError("Unexpected imagery response")
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(502, "NAIP tile service unavailable; World Imagery fallback") from exc
        if len(tile_cache) >= 96:
            tile_cache.pop(next(iter(tile_cache)))
        tile_cache[key] = response.content
    return Response(tile_cache[key], media_type="image/png", headers={"Cache-Control": "public, max-age=300"})


@app.post("/simulate")
def simulation(request: SimulateRequest):
    observation = unseal(request.snapshot_token, "snapshot") if request.snapshot_token else snapshot
    if observation is None or request.snapshot_id != observation["snapshot_id"]:
        raise HTTPException(409, "Observation changed; refresh before dispatch")
    field = next((f for f in observation["fields"] if f["id"] == request.field_id), None)
    if field is None:
        raise HTTPException(404, "Unknown DWR polygon")
    try:
        result = simulate(field, low_battery=request.low_battery, cloud=request.cloud,
                          stale=request.stale, exclusion_enabled=request.exclusion)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    mission_id = str(uuid4())
    result["mission_id"] = mission_id
    packet = deepcopy(field["packet"])
    packet["path_result"] = {k: v for k, v in result.items() if k not in ["trace", "path", "inspection_grid"]}
    packet["filed_at"] = datetime.now(timezone.utc).isoformat()
    packet["simulated"] = True
    if result["status"] == "deferred":
        packet["action"] = "defer_observation"
    missions[mission_id] = {"result": result, "packet": packet, "gate": None}
    runtime = RUNTIME
    runtime.mkdir(parents=True, exist_ok=True)
    last = result["trace"][-1] if result["trace"] else {"position": DEPOT, "battery_pct": 100,
            "altitude_agl_m": 0, "ground_speed_mps": 0, "payload_g": 0}
    # State, not a flight log: the first line explicitly identifies the simulation.
    state = {"simulated": True, "callsign": "AF-1", "reserve_pct": 25,
             "status": result["status"], "mission_id": mission_id, **last}
    (runtime / "AF-1.json").write_text(json.dumps(state) + "\n")
    if len(missions) > 100:
        del missions[next(iter(missions))]
    return result | {"mission_token": seal("mission", {"mission_id": mission_id, "result": result, "packet": packet})}


@app.get("/missions/{mission_id}/findings")
def findings(mission_id: str):
    return mission_or_404(mission_id)["packet"]


@app.get("/missions/{mission_id}/advice")
def advice(mission_id: str):
    return advise(mission_or_404(mission_id)["packet"])


@app.post("/api/findings")
@app.post("/findings")
def signed_findings(request: MissionRequest):
    return mission_or_404(request.mission_id, request.mission_token)["packet"]


@app.post("/api/advice")
@app.post("/advice")
def signed_advice(request: MissionRequest):
    return advise(mission_or_404(request.mission_id, request.mission_token)["packet"])


def evaluate_gate(mission, human_go, product_name, state_override=None):
    packet = mission["packet"]
    state = state_override or packet["state_fips"]
    result = check_policy(state, packet["cdl"]["code"], product_name, human_go)
    result["simulated_policy_test"] = state_override is not None
    result["field_state_fips"] = packet["state_fips"]
    if mission["result"]["status"] != "completed":
        result["application_unlocked"] = False
        result["mission_veto"] = "A complete inspection is required before application playback."
    return result


@app.post("/gate")
def gate(request: GateRequest):
    mission = mission_or_404(request.mission_id, request.mission_token)
    result = evaluate_gate(mission, request.human_go, request.product_name, request.state_override)
    # Always recheck at application time; never trust a browser unlock flag.
    if request.state_override is None:
        mission["gate"] = request.model_dump()
        result["gate_token"] = seal("gate", {"mission_id": request.mission_id,
            "mission": {"result": mission["result"], "packet": mission["packet"]},
            "human_go": request.human_go, "product_name": request.product_name})
    return result


@app.post("/apply")
def application(request: ApplyRequest):
    if request.gate_token:
        decision = unseal(request.gate_token, "gate")
        if decision.get("mission_id") != request.mission_id:
            raise HTTPException(403, "Approval does not match this mission")
        mission = decision["mission"]
        result = evaluate_gate(mission, decision["human_go"], decision["product_name"])
    else:
        mission = mission_or_404(request.mission_id)
        if not mission["gate"]:
            raise HTTPException(403, "Human and policy gates have not passed")
        result = gate(GateRequest(**mission["gate"]))
    if not result["application_unlocked"]:
        raise HTTPException(403, result.get("mission_veto", result["reason"]))
    return {"simulated": True, "label": "SIMULATED APPLICATION", "mission_id": request.mission_id,
            "path": mission["result"]["path"], "trace": mission["result"]["trace"],
            "policy": result, "product_name": result["product_name"], "rate": None}


# Production build can be served by the same Python process (no CORS/proxy needed).
@app.get("/")
def index():
    if not (ROOT / "dist/index.html").exists():
        raise HTTPException(503, "Run npm run build, or open the Vite preview on port 5173")
    return FileResponse(ROOT / "dist/index.html")


@app.get("/api/{path:path}")
def api_get(path: str, snapshot_id: str | None = None, field_id: str | None = None):
    if path == "ndvi.png" and snapshot_id:
        return ndvi(snapshot_id, field_id)
    if path.startswith("missions/"):
        parts = path.split("/")
        if len(parts) == 3:
            if parts[2] == "findings":
                return findings(parts[1])
            if parts[2] == "advice":
                return advice(parts[1])
    if path == "health":
        return health()
    raise HTTPException(404)


@app.post("/api/fuse")
def api_fuse(request: FuseRequest = FuseRequest()):
    return fused(request)


@app.post("/api/simulate")
def api_simulate(request: SimulateRequest):
    return simulation(request)


@app.post("/api/gate")
def api_gate(request: GateRequest):
    return gate(request)


@app.post("/api/apply")
def api_apply(request: ApplyRequest):
    return application(request)


@app.get("/{path:path}")
def static_file(path: str):
    candidate = (ROOT / "dist" / path).resolve()
    if not candidate.is_relative_to((ROOT / "dist").resolve()) or not candidate.is_file():
        raise HTTPException(404)
    return FileResponse(candidate)
