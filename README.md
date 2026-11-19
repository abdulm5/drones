# drones

AGRIFORGE — a satellite-guided precision-agriculture drone prototype.

## Planned demo

1. Fetch usable satellite imagery for an agricultural area.
2. Identify vegetation anomalies and show imagery age and quality.
3. Plan drone inspections with battery and exclusion-zone constraints.
4. Check mission feasibility and animate simulated execution.
5. Report observations and missing evidence for the next action.

Satellite anomalies are observations, not diagnoses. Drone execution and treatment workflows are simulated; treatment proposals require supporting agronomic evidence and operator approval.

## Repository layout

- `src/` — imagery processing, mission planning, verification, and simulation.
- `docs/` — architecture, research, and demo notes.
- `data/` — local datasets and caches (ignored by Git).

## Status

Initial scaffold. No application, dependencies, or training pipeline has been implemented yet.
