"""Explicitly simulated inspection. Geometry and energy are checked independently."""
import heapq
import math

import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely import transform
from shapely.ops import nearest_points, unary_union

from .config import DEPOT

TO_METERS = Transformer.from_crs(4326, 32610, always_xy=True).transform
TO_LONLAT = Transformer.from_crs(32610, 4326, always_xy=True).transform
RESERVE = 25.0
METERS_PER_PERCENT = 80.0
SPEED = 8.0


def project(geometry):
    return transform(shape(geometry), TO_METERS, interleaved=False)


def geographic(geometry):
    return mapping(transform(geometry, TO_LONLAT, interleaved=False))


def largest_polygon(geometry):
    if geometry.geom_type == "Polygon":
        return geometry
    pieces = [p for p in getattr(geometry, "geoms", []) if p.geom_type == "Polygon"]
    if not pieces:
        raise ValueError("No navigable field area remains")
    return max(pieces, key=lambda p: p.area)


def exclusion_for(field):
    polygon = largest_polygon(project(field["geometry"]))
    minx, miny, maxx, maxy = polygon.bounds
    # Authored northwest wedge. Never represented as an observed feature.
    wedge = Polygon([(minx - 1, maxy + 1), (minx + (maxx-minx)*.47, maxy + 1),
                     (minx - 1, maxy - (maxy-miny)*.47)])
    return polygon.intersection(wedge)


def visibility_route(start, end, area):
    """Shortest polyline in a simple polygon including boundary vertices/holes."""
    start, end = tuple(start), tuple(end)
    allowed = area.buffer(.02)
    if allowed.covers(LineString([start, end])):
        return [start, end]
    nodes = [start, end, *list(area.exterior.coords)[:-1]]
    for ring in area.interiors:
        nodes.extend(list(ring.coords)[:-1])
    edges = [[] for _ in nodes]
    for i, a in enumerate(nodes):
        for j in range(i + 1, len(nodes)):
            b = nodes[j]
            if allowed.covers(LineString([a, b])):
                distance = math.dist(a, b)
                edges[i].append((j, distance))
                edges[j].append((i, distance))
    queue, costs, previous = [(0, 0)], {0: 0}, {}
    while queue:
        cost, node = heapq.heappop(queue)
        if cost > costs[node]:
            continue
        if node == 1:
            chain = [1]
            while chain[-1] != 0:
                chain.append(previous[chain[-1]])
            return [nodes[i] for i in reversed(chain)]
        for neighbor, distance in edges[node]:
            total = cost + distance
            if total < costs.get(neighbor, math.inf):
                costs[neighbor], previous[neighbor] = total, node
                heapq.heappush(queue, (total, neighbor))
    raise ValueError("No within-field connector exists")


def line_length(path):
    return sum(math.dist(a, b) for a, b in zip(path, path[1:]))


def densify(path, step=10):
    out = [tuple(path[0])]
    for a, b in zip(path, path[1:]):
        n = max(1, math.ceil(math.dist(a, b) / step))
        out.extend((a[0] + (b[0]-a[0])*i/n, a[1] + (b[1]-a[1])*i/n) for i in range(1, n+1))
    return out


def verify_track(trace, allowed, exclusion):
    """Checks every complete segment, rather than only the waypoint positions."""
    geofence = exclusion_count = 0
    minimum_battery = 100.0
    for record in trace:
        minimum_battery = min(minimum_battery, record["battery_pct"])
    for a, b in zip(trace, trace[1:]):
        line = LineString([TO_METERS(*a["position"]), TO_METERS(*b["position"])])
        if not allowed.buffer(.05).covers(line):
            geofence += 1
        if exclusion is not None and not exclusion.is_empty and line.intersects(exclusion.buffer(-.05)):
            exclusion_count += 1
    return {"geofence_violations": geofence, "exclusion_violations": exclusion_count,
            "battery_reserve_violations": int(minimum_battery < RESERVE - .05),
            "checker": "Independent full-segment geometry and linear-energy check; not formal flight certification"}


def simulate(field, low_battery=False, exclusion_enabled=True, cloud=False, stale=False):
    packet = field["packet"]
    if cloud or stale or packet["action"] == "defer_observation":
        reason = "Authored cloud scenario: insufficient clear pixels" if cloud else (
            "Authored stale scenario: observation older than 30 days" if stale else "Observation quality gate")
        return {"simulated": True, "callsign": "AF-1", "status": "deferred", "action": "defer_observation",
                "reason": reason, "trace": [], "path": [], "samples": 0,
                "scenario": {"cloud": cloud, "stale": stale, "low_battery": low_battery,
                             "exclusion": exclusion_enabled}}
    field_area = largest_polygon(project(field["geometry"]))
    exclusion = exclusion_for(field) if exclusion_enabled else None
    navigable = field_area.buffer(-2)
    if exclusion is not None and not exclusion.is_empty:
        navigable = navigable.difference(exclusion.buffer(2))
    navigable = largest_polygon(navigable)
    depot = Point(TO_METERS(*DEPOT))
    entry = nearest_points(depot, navigable)[1]
    entry_xy = (entry.x, entry.y)
    transit = LineString([depot, entry])
    if exclusion is not None and not exclusion.is_empty and transit.intersects(exclusion):
        candidates = [Point(p) for p in navigable.exterior.coords
                      if not LineString([depot, Point(p)]).intersects(exclusion)]
        if not candidates:
            raise ValueError("Exclusion blocks all demo transit corridors")
        entry = min(candidates, key=lambda p: p.distance(depot))
        entry_xy = (entry.x, entry.y)
        transit = LineString([depot, entry])
    allowed = unary_union([field_area, transit.buffer(8), depot.buffer(8)])
    minx, miny, maxx, maxy = navigable.bounds
    targets, rejected = [], []
    direction = False
    for y in np.arange(miny + 3, maxy, 30):
        raw = LineString([(minx-1, y), (maxx+1, y)])
        clipped = raw.intersection(navigable)
        segments = [clipped] if clipped.geom_type == "LineString" else [g for g in getattr(clipped, "geoms", []) if g.geom_type == "LineString"]
        segments.sort(key=lambda line: line.bounds[0], reverse=direction)
        for segment in segments:
            coords = list(segment.coords)
            if segment.length > 2:
                targets.extend([coords[-1], coords[0]] if direction else [coords[0], coords[-1]])
        if exclusion is not None and not exclusion.is_empty:
            cut = raw.intersection(exclusion)
            if cut.geom_type == "LineString" and cut.length > 0:
                rejected.append(geographic(cut))
        direction = not direction
    planned = [entry_xy]
    for target in targets:
        planned.extend(visibility_route(planned[-1], target, navigable)[1:])
    if len(planned) < 2:
        raise ValueError("Field too small for a 30 m inspection grid")
    depot_xy = (depot.x, depot.y)
    outbound = densify([depot_xy, entry_xy])
    grid = densify(planned)
    launch_battery = 100.0
    if low_battery:
        launch_battery = min(95., RESERVE + 2 * transit.length / METERS_PER_PERCENT + 2.5)
    trace, traveled, samples = [], 0.0, 0
    def append(point, phase):
        nonlocal traveled, samples
        if trace:
            traveled += math.dist(TO_METERS(*trace[-1]["position"]), point)
        if phase == "inspection":
            samples += 1
        lon, lat = TO_LONLAT(*point)
        trace.append({"position": [lon, lat], "elapsed_s": round(traveled / SPEED, 2),
                      "distance_m": round(traveled, 2), "battery_pct": round(launch_battery-traveled/METERS_PER_PERCENT, 3),
                      "altitude_agl_m": 0 if phase == "landed" else 40, "ground_speed_mps": 0 if phase == "landed" else SPEED,
                      "payload_g": 0, "samples": samples, "phase": phase})
    if launch_battery - (2 * transit.length / METERS_PER_PERCENT) < RESERVE:
        raise ValueError("Launch denied: outbound and return cannot preserve reserve")
    for point in outbound:
        append(point, "outbound")
    aborted = False
    for point in grid[1:]:
        home = visibility_route(point, entry_xy, navigable) + [depot_xy]
        next_distance = math.dist(TO_METERS(*trace[-1]["position"]), point)
        remaining = launch_battery - (traveled + next_distance + line_length(home)) / METERS_PER_PERCENT
        if remaining < RESERVE + .2:
            aborted = True
            break
        append(point, "inspection")
    current = TO_METERS(*trace[-1]["position"])
    home = visibility_route(current, entry_xy, navigable) + [depot_xy]
    for point in densify(home)[1:]:
        append(point, "return_to_base")
    append(depot_xy, "landed")
    verification = verify_track(trace, allowed, exclusion)
    if any(verification[k] for k in ["geofence_violations", "exclusion_violations", "battery_reserve_violations"]):
        raise ValueError(f"Independent checker vetoed mission: {verification}")
    return {"simulated": True, "callsign": "AF-1", "status": "returned_early" if aborted else "completed",
            "action": "return_to_base" if aborted else "hold_for_operator", "trace": trace,
            "path": [t["position"] for t in trace], "inspection_grid": geographic(LineString(planned)),
            "rejected_segments": rejected, "exclusion": geographic(exclusion) if exclusion is not None else None,
            "transit_corridor": geographic(transit.buffer(8)), "allowed_geofence": geographic(allowed),
            "transit_note": "AUTHORED 16 m transit corridor connects the demo depot to the field; inspection turns remain inside the field.",
            "distance_m": round(traveled, 1), "duration_s": round(traveled / SPEED, 1), "samples": samples,
            "battery_at_launch_pct": round(launch_battery, 2), "battery_at_landing_pct": trace[-1]["battery_pct"],
            "reserve_pct": RESERVE, "lane_spacing_m": 30, "altitude_agl_m": 40,
            "energy_model": "Linear: 1% per 80 m, 8 m/s, no wind or turn penalty. Reserve 25% including return.",
            "verification": verification, "scenario": {"cloud": cloud, "stale": stale,
            "low_battery": low_battery, "exclusion": exclusion_enabled},
            "cold_vehicle": {"callsign": "AF-2", "status": "cold_on_pad", "reason": "One vehicle covers the inspection; AF-2 is not tasked."}}
