"""
BhoomiRakshak - Sensor simulator
Simulates ESP32 nodes sending tilt/vibration/battery data.
Replace this with real ESP32 HTTP POST ingestion (see /api/ingest in app.py)
once hardware is ready - the rest of the pipeline stays identical.
"""
import random
import time
import math

# Per-node simulation state
_state = {
    "N1": {"base_tilt": 0.2, "drift": 0.0, "battery": 4.1, "event_active": False},
    "N2": {"base_tilt": 0.3, "drift": 0.0, "battery": 4.0, "event_active": False},
}

_tick = 0


def trigger_event(node_id, correlated=True):
    """Manually trigger a simulated deformation event on a node (for demo button)."""
    if node_id in _state:
        _state[node_id]["event_active"] = True
    if correlated:
        for other_id in _state:
            if other_id != node_id:
                _state[other_id]["event_active"] = "minor"


def reset_events():
    for s in _state.values():
        s["drift"] = 0.0
        s["event_active"] = False


def generate_reading(node_id):
    global _tick
    s = _state[node_id]

    # Normal small noise around baseline
    noise_tilt = random.uniform(-0.05, 0.05)
    noise_vib = abs(random.gauss(0, 0.3))

    # If an event is active, drift increases tilt progressively
    if s["event_active"] == True:
        s["drift"] += random.uniform(0.05, 0.15)
    elif s["event_active"] == "minor":
        s["drift"] += random.uniform(0.01, 0.03)
    else:
        # slow natural decay back toward 0 drift
        s["drift"] = max(0.0, s["drift"] - 0.01)

    tilt_x = s["base_tilt"] + s["drift"] + noise_tilt
    tilt_y = s["base_tilt"] * 0.6 + s["drift"] * 0.4 + noise_tilt

    vibration = noise_vib + (2.0 if s["event_active"] else 0.0)

    # Battery slowly drains, "recharges" a bit each cycle to simulate solar input
    s["battery"] += random.uniform(-0.01, 0.012)
    s["battery"] = max(3.0, min(4.2, s["battery"]))

    _tick += 1

    return {
        "node_id": node_id,
        "tilt_x": round(tilt_x, 3),
        "tilt_y": round(tilt_y, 3),
        "vibration": round(vibration, 3),
        "battery": round(s["battery"], 2),
    }


def generate_all():
    return [generate_reading(nid) for nid in _state.keys()]
