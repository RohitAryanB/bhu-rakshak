"""
BhoomiRakshak - Database layer
Handles SQLite schema creation and all read/write operations.
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "bhoomirakshak.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS nodes (
        node_id TEXT PRIMARY KEY,
        name TEXT,
        latitude REAL,
        longitude REAL,
        zone TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        node_id TEXT,
        timestamp TEXT,
        tilt_x REAL,
        tilt_y REAL,
        vibration REAL,
        battery REAL,
        FOREIGN KEY(node_id) REFERENCES nodes(node_id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS risk_status (
        node_id TEXT PRIMARY KEY,
        risk_level TEXT,
        anomaly_score REAL,
        rate_of_change REAL,
        last_updated TEXT,
        last_seen TEXT,
        FOREIGN KEY(node_id) REFERENCES nodes(node_id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        node_id TEXT,
        zone TEXT,
        risk_level TEXT,
        message TEXT,
        created_at TEXT,
        acknowledged INTEGER DEFAULT 0,
        note TEXT DEFAULT ''
    )
    """)

    conn.commit()

    # Seed default nodes (2-node prototype) if not present
    existing = c.execute("SELECT COUNT(*) as cnt FROM nodes").fetchone()["cnt"]
    if existing == 0:
        c.executemany(
            "INSERT INTO nodes (node_id, name, latitude, longitude, zone) VALUES (?,?,?,?,?)",
            [
                ("N1", "Node 1", 12.9716, 77.5946, "Zone A"),
                ("N2", "Node 2", 12.9720, 77.5950, "Zone A"),
            ],
        )
        c.executemany(
            "INSERT INTO risk_status (node_id, risk_level, anomaly_score, rate_of_change, last_updated, last_seen) VALUES (?,?,?,?,?,?)",
            [
                ("N1", "NORMAL", 0.0, 0.0, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
                ("N2", "NORMAL", 0.0, 0.0, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
            ],
        )
        conn.commit()

    conn.close()


def insert_reading(node_id, tilt_x, tilt_y, vibration, battery):
    conn = get_conn()
    c = conn.cursor()
    ts = datetime.utcnow().isoformat()
    c.execute(
        "INSERT INTO readings (node_id, timestamp, tilt_x, tilt_y, vibration, battery) VALUES (?,?,?,?,?,?)",
        (node_id, ts, tilt_x, tilt_y, vibration, battery),
    )
    c.execute(
        "UPDATE risk_status SET last_seen=? WHERE node_id=?", (ts, node_id)
    )
    conn.commit()
    conn.close()
    return ts


def get_recent_readings(node_id, limit=50):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM readings WHERE node_id=? ORDER BY id DESC LIMIT ?",
        (node_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_readings_range(node_id, start=None, end=None):
    conn = get_conn()
    q = "SELECT * FROM readings WHERE node_id=?"
    params = [node_id]
    if start:
        q += " AND timestamp>=?"
        params.append(start)
    if end:
        q += " AND timestamp<=?"
        params.append(end)
    q += " ORDER BY id ASC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_nodes():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM nodes").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_risk_status(node_id, risk_level, anomaly_score, rate_of_change):
    conn = get_conn()
    ts = datetime.utcnow().isoformat()
    conn.execute(
        """UPDATE risk_status SET risk_level=?, anomaly_score=?, rate_of_change=?, last_updated=?
           WHERE node_id=?""",
        (risk_level, anomaly_score, rate_of_change, ts, node_id),
    )
    conn.commit()
    conn.close()


def get_all_risk_status():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM risk_status").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_alert(node_id, zone, risk_level, message):
    conn = get_conn()
    conn.execute(
        "INSERT INTO alerts (node_id, zone, risk_level, message, created_at) VALUES (?,?,?,?,?)",
        (node_id, zone, risk_level, message, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_alerts(limit=50):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def acknowledge_alert(alert_id, note=""):
    conn = get_conn()
    conn.execute(
        "UPDATE alerts SET acknowledged=1, note=? WHERE id=?", (note, alert_id)
    )
    conn.commit()
    conn.close()


def has_recent_alert(node_id, risk_level, within_seconds=120):
    """Avoid spamming duplicate alerts for the same ongoing condition."""
    conn = get_conn()
    row = conn.execute(
        "SELECT created_at FROM alerts WHERE node_id=? AND risk_level=? ORDER BY id DESC LIMIT 1",
        (node_id, risk_level),
    ).fetchone()
    conn.close()
    if not row:
        return False
    last = datetime.fromisoformat(row["created_at"])
    return (datetime.utcnow() - last).total_seconds() < within_seconds
