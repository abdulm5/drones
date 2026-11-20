"""A deterministic consultant consumes the findings packet and nothing else."""


def advise(packet):
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
