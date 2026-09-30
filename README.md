# BhoomiRakshak — Mine Subsidence Early Warning System

## Run it
1. Install dependencies:
   pip install -r requirements.txt

2. Start the server:
   python app.py

3. Open in browser:
   http://localhost:5000

## What it does
- Simulates 2 sensor nodes (N1, N2) sending tilt/vibration/battery data every 3s
- Isolation Forest detects anomalies; a rule layer classifies risk (NORMAL/WATCH/WARNING/HIGH RISK)
- Checks spatial correlation between nodes before escalating to HIGH RISK
- Live dashboard: node cards, trend chart, zone map, alert log, CSV export
- Demo buttons let you trigger a simulated deformation event without real hardware

## Connecting real ESP32 hardware later
Point your ESP32 HTTP POST requests at:
  POST http://<this-server-ip>:5000/api/ingest
  Body: {"node_id": "N1", "tilt_x": 1.2, "tilt_y": 0.8, "vibration": 0.3, "battery": 3.95}

Then set SIMULATE = False in app.py to stop the simulator and rely only on real data.

## Files
- app.py            Flask server, API routes, background loops
- database.py       SQLite schema + queries
- simulator.py      Simulated sensor data generator (swap for real ESP32 later)
- ml_engine.py       Isolation Forest + risk classification + spatial correlation
- templates/         Dashboard HTML
- static/            CSS + JS for the dashboard
