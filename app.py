"""
BhoomiRakshak - AI-Enabled Wireless Surface Sensor Network
Main Flask application.

Run: python app.py
Then open http://localhost:5000
"""
import threading
import time
import io
import csv
from datetime import datetime, timedelta

from flask import Flask, jsonify, request, render_template, Response

import database as db
import simulator
import ml_engine

app = Flask(__name__)

SIMULATE = True          # Set False once real ESP32 nodes POST to /api/ingest
CYCLE_SECONDS = 3         # how often simulated nodes produce a reading
ML_CYCLE_SECONDS = 6      # how often the AI risk engine re-evaluates


# ---------------------------------------------------------------------------
# Background loops (simulate hardware + run AI engine periodically)
# ---------------------------------------------------------------------------
def simulation_loop():
    while True:
        if SIMULATE:
            for reading in simulator.generate_all():
                db.insert_reading(
                    reading["node_id"], reading["tilt_x"], reading["tilt_y"],
                    reading["vibration"], reading["battery"]
                )
        time.sleep(CYCLE_SECONDS)


def ml_loop():
    while True:
        time.sleep(ML_CYCLE_SECONDS)
        try:
            ml_engine.classify_all()
        except Exception as e:
            print("ML loop error:", e)


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------
@app.route("/")
def dashboard():
    return render_template("dashboard.html")


# ---------------------------------------------------------------------------
# API: live status for dashboard polling
# ---------------------------------------------------------------------------
@app.route("/api/status")
def api_status():
    nodes = db.get_all_nodes()
    risk = {r["node_id"]: r for r in db.get_all_risk_status()}
    result = []
    now = datetime.utcnow()

    for n in nodes:
        node_id = n["node_id"]
        r = risk.get(node_id, {})
        recent = db.get_recent_readings(node_id, limit=1)
        latest = recent[-1] if recent else {}

        # Determine if node is "offline" (no data in last 30s)
        online = True
        if r.get("last_seen"):
            last_seen = datetime.fromisoformat(r["last_seen"])
            online = (now - last_seen).total_seconds() < 30

        result.append({
            "node_id": node_id,
            "name": n["name"],
            "zone": n["zone"],
            "latitude": n["latitude"],
            "longitude": n["longitude"],
            "risk_level": r.get("risk_level", "NORMAL"),
            "anomaly_score": r.get("anomaly_score", 0),
            "rate_of_change": r.get("rate_of_change", 0),
            "tilt_x": latest.get("tilt_x"),
            "tilt_y": latest.get("tilt_y"),
            "vibration": latest.get("vibration"),
            "battery": latest.get("battery"),
            "online": online,
            "last_seen": r.get("last_seen"),
        })
    return jsonify(result)


@app.route("/api/history/<node_id>")
def api_history(node_id):
    limit = int(request.args.get("limit", 50))
    readings = db.get_recent_readings(node_id, limit=limit)
    return jsonify(readings)


@app.route("/api/alerts")
def api_alerts():
    limit = int(request.args.get("limit", 50))
    return jsonify(db.get_alerts(limit=limit))


@app.route("/api/alerts/<int:alert_id>/acknowledge", methods=["POST"])
def api_acknowledge(alert_id):
    note = request.json.get("note", "") if request.is_json else ""
    db.acknowledge_alert(alert_id, note)
    return jsonify({"status": "ok"})


@app.route("/api/export/<node_id>")
def api_export(node_id):
    """Export historical readings as CSV for a given node."""
    readings = db.get_readings_range(node_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["node_id", "timestamp", "tilt_x", "tilt_y", "vibration", "battery"])
    for r in readings:
        writer.writerow([r["node_id"], r["timestamp"], r["tilt_x"], r["tilt_y"], r["vibration"], r["battery"]])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={node_id}_readings.csv"}
    )


# ---------------------------------------------------------------------------
# API: real hardware ingestion endpoint (use this once ESP32 nodes are ready)
# ---------------------------------------------------------------------------
@app.route("/api/ingest", methods=["POST"])
def api_ingest():
    """
    Real ESP32 nodes POST JSON here:
    {"node_id": "N1", "tilt_x": 1.2, "tilt_y": 0.8, "vibration": 0.3, "battery": 3.95}
    """
    data = request.get_json(force=True)
    required = ["node_id", "tilt_x", "tilt_y", "vibration", "battery"]
    if not all(k in data for k in required):
        return jsonify({"error": "missing fields"}), 400

    db.insert_reading(data["node_id"], data["tilt_x"], data["tilt_y"],
                       data["vibration"], data["battery"])
    return jsonify({"status": "received"}), 200


# ---------------------------------------------------------------------------
# Demo controls (simulate a deformation event for presentation purposes)
# ---------------------------------------------------------------------------
@app.route("/api/demo/trigger/<node_id>", methods=["POST"])
def api_demo_trigger(node_id):
    correlated = request.json.get("correlated", True) if request.is_json else True
    simulator.trigger_event(node_id, correlated=correlated)
    return jsonify({"status": "event triggered", "node": node_id})


@app.route("/api/demo/reset", methods=["POST"])
def api_demo_reset():
    simulator.reset_events()
    return jsonify({"status": "reset"})


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    db.init_db()
    threading.Thread(target=simulation_loop, daemon=True).start()
    threading.Thread(target=ml_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
