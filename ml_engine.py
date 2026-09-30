"""
BhoomiRakshak - AI/ML engine
- Isolation Forest for anomaly detection on recent tilt/vibration trends
- Rule layer converts anomaly score + rate-of-change into risk levels
- Spatial correlation check across nodes (2-node version)
"""
import numpy as np
from sklearn.ensemble import IsolationForest
import database as db

RISK_LEVELS = ["NORMAL", "WATCH", "WARNING", "HIGH RISK"]

# Thresholds (tunable) - degrees per reading-cycle for rate of change
RATE_THRESHOLD_WATCH = 0.03
RATE_THRESHOLD_WARNING = 0.08
SPATIAL_CORR_THRESHOLD = 0.015  # minimal drift on neighbor to count as "correlated"


def _feature_matrix(readings):
    """Build [tilt_x, tilt_y, vibration] feature rows from recent readings."""
    return np.array([[r["tilt_x"], r["tilt_y"], r["vibration"]] for r in readings])


def compute_rate_of_change(readings):
    if len(readings) < 2:
        return 0.0
    tilts = [r["tilt_x"] for r in readings]
    # simple slope over the window (last - first) / number of steps
    return (tilts[-1] - tilts[0]) / max(1, len(tilts) - 1)


def detect_anomaly(readings):
    """Returns anomaly_score where lower/negative = more anomalous (Isolation Forest convention)."""
    if len(readings) < 8:
        return 0.0, False  # not enough data yet
    X = _feature_matrix(readings)
    model = IsolationForest(n_estimators=50, contamination=0.15, random_state=42)
    model.fit(X)
    scores = model.decision_function(X)
    preds = model.predict(X)
    latest_score = scores[-1]
    latest_is_anomaly = preds[-1] == -1
    return float(latest_score), bool(latest_is_anomaly)


def classify_risk(node_id, window=30):
    """Main entry point: pulls recent readings, runs anomaly detection + rules,
    checks spatial correlation with other nodes, updates DB, and raises alerts."""
    readings = db.get_recent_readings(node_id, limit=window)
    if not readings:
        return None

    anomaly_score, is_anomaly = detect_anomaly(readings)
    rate = compute_rate_of_change(readings)

    # Base rule-based classification
    if is_anomaly and rate > RATE_THRESHOLD_WARNING:
        level = "WARNING"
    elif is_anomaly or rate > RATE_THRESHOLD_WATCH:
        level = "WATCH"
    else:
        level = "NORMAL"

    # Spatial correlation check across other nodes (2-node logic)
    all_nodes = db.get_all_nodes()
    other_node_ids = [n["node_id"] for n in all_nodes if n["node_id"] != node_id]
    correlated = False
    for other_id in other_node_ids:
        other_readings = db.get_recent_readings(other_id, limit=window)
        if len(other_readings) >= 2:
            other_rate = compute_rate_of_change(other_readings)
            if other_rate > SPATIAL_CORR_THRESHOLD:
                correlated = True

    if level == "WARNING" and correlated:
        level = "HIGH RISK"

    db.update_risk_status(node_id, level, anomaly_score, rate)

    # Raise an alert if WARNING or HIGH RISK and not already recently alerted
    if level in ("WARNING", "HIGH RISK") and not db.has_recent_alert(node_id, level):
        node_info = next((n for n in all_nodes if n["node_id"] == node_id), {})
        zone = node_info.get("zone", "Unknown Zone")
        if level == "HIGH RISK":
            msg = (f"HIGH RISK: Increasing deformation on {node_id} ({zone}), "
                   f"with correlated movement on neighboring node(s). Field inspection recommended.")
        else:
            msg = (f"WARNING: Persistent abnormal ground deformation trend detected on {node_id} "
                   f"({zone}). Monitor closely.")
        db.create_alert(node_id, zone, level, msg)

    return {
        "node_id": node_id,
        "risk_level": level,
        "anomaly_score": round(anomaly_score, 3),
        "rate_of_change": round(rate, 4),
        "correlated": correlated,
    }


def classify_all():
    nodes = db.get_all_nodes()
    return [classify_risk(n["node_id"]) for n in nodes]
