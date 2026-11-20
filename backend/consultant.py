"""Raster rules choose the action. Grok writes the advisory from that packet only."""

import json
import os

import httpx

from .config import load_local_env

ALLOWED = {
    "inspect_plot", "request_soil_measurement", "defer_observation",
    "assign_drone", "return_to_base", "hold_for_operator",
}


def advise(packet):
    load_local_env()
    result = _template(packet)
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("AGRIFORGE_GROK") == "0":
        return result
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        return result
    try:
        sentences = _grok_sentences(packet, key, result["action"])
    except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError):
        result["grok_error"] = "Grok unavailable. Raster rules supplied the advisory."
        return result
    result["sentences"] = sentences
    result["speaker"] = "Grok"
    result["model_available"] = True
    result["model"] = os.environ.get("XAI_MODEL", "grok-4")
    return result


def _template(packet):
    quality_action = packet["action"]
    mission = packet.get("path_result", {})
    action = "defer_observation" if quality_action == "defer_observation" else "request_soil_measurement"
    crop = packet["cdl"]
    ndvi = packet["ndvi"]
    sentences = [
        {"layer": "Sentinel-2 L2A", "date": packet["scene_datetime"],
         "text": f"Sentinel-2 records mean NDVI {ndvi['mean']} and a within-field, same-CDL-class gap of {packet['anomaly_gap']}; this is an observation, not a diagnosis."},
        {"layer": "USDA NASS CDL", "date": str(crop["year"]),
         "text": f"USDA NASS CDL {crop['year']} labels the polygon majority {crop['name']} (code {crop['code']}); the annual class does not confirm the current crop."},
        {"layer": "USDA SSURGO", "date": packet["ssurgo"]["date"],
         "text": "SSURGO provides soil texture, organic matter and pH at the center of the box; organic matter is not a nitrate measurement."},
        {"layer": "NASA POWER", "date": packet["power"]["end"],
         "text": f"NASA POWER supplies regional weather for {packet['power']['start']} through {packet['power']['end']} with {packet['power']['missing_values']} missing values; its half-degree cell cannot explain one side of a field."},
        {"layer": "Findings packet / missing evidence", "date": packet["scene_datetime"],
         "text": "The findings packet lacks " + ", ".join(packet["missing_agronomic_fields"]) + "; request soil measurements and hold for the operator."},
    ]
    if mission:
        sentences.append({"layer": "Simulated AF-1 mission", "date": packet.get("filed_at"),
                          "text": f"The simulated AF-1 path returned {mission.get('status')} with {mission.get('samples', 0)} samples; these are simulated sampling locations, not new crop measurements."})
    return {"speaker": "Deterministic packet template", "model_available": False,
            "action": action, "sentences": sentences, "missing_agronomic_fields": packet["missing_agronomic_fields"],
            "alternative_explanations": packet["alternative_explanations"], "rate": None}


def _brief(packet, action):
    path = packet.get("path_result") or {}
    return {
        "polygon_id": packet.get("polygon_id"),
        "scene_datetime": packet.get("scene_datetime"),
        "raster_action": action,
        "ndvi": packet.get("ndvi"),
        "ndmi": packet.get("ndmi"),
        "anomaly_gap": packet.get("anomaly_gap"),
        "clear_pixel_fraction": packet.get("clear_pixel_fraction"),
        "scl_counts": packet.get("scl_counts"),
        "cdl": packet.get("cdl"),
        "power": packet.get("power"),
        "ssurgo": packet.get("ssurgo"),
        "missing_agronomic_fields": packet.get("missing_agronomic_fields"),
        "alternative_explanations": packet.get("alternative_explanations"),
        "simulated_mission": {k: path.get(k) for k in ("status", "samples", "distance_m", "battery_at_landing_pct")},
    }


def _grok_sentences(packet, key, action):
    model = os.environ.get("XAI_MODEL", "grok-4")
    prompt = {
        "role": "system",
        "content": (
            "You are the AgriForce field consultant on a mission console. The raster pipeline already "
            "computed the packet and chose raster_action. Write the advisory a flight director would read. "
            "Use only numbers and names present in the packet. Include the NDVI mean, the anomaly gap, "
            "the CDL crop name, the soil series, the POWER date range, the simulated mission status, "
            "and every missing agronomic field. Say NDVI is an observation, organic matter is not nitrate, "
            "and POWER cannot explain one side of a field. Do not invent measurements, yields, disease, "
            "or a fertilizer rate. Return JSON only: "
            "{\"sentences\":[{\"layer\":\"source name\",\"date\":\"from the packet\",\"text\":\"one full sentence\"}]}. "
            "Write 5 sentences. Each text stays under 280 characters."
        ),
    }
    user = {"role": "user", "content": json.dumps(_brief(packet, action))}
    response = httpx.post(
        "https://api.x.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "temperature": 0, "messages": [prompt, user]},
        timeout=30,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return _parse_sentences(content, action)


def _parse_sentences(content, action):
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    payload = json.loads(text)
    raw = payload["sentences"]
    if not isinstance(raw, list) or not 3 <= len(raw) <= 6:
        raise ValueError("Grok sentence count")
    sentences = []
    for item in raw:
        layer = str(item["layer"]).strip()[:80]
        date = str(item.get("date") or "")[:40]
        sentence = " ".join(str(item["text"]).split())
        if not layer or not sentence or len(sentence) > 320:
            raise ValueError("Grok sentence shape")
        lowered = sentence.lower()
        if "lb/ac" in lowered or "lbs/ac" in lowered or "fertilizer rate" in lowered:
            raise ValueError("Grok proposed a rate")
        sentences.append({"layer": layer, "date": date, "text": sentence})
    if action not in ALLOWED:
        raise ValueError("Raster action")
    return sentences
