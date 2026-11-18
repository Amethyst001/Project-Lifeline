"""
Project Lifeline - Production SQLite WAL Incident & Dispatch Store
Cross-process ACID safe across multiple Gunicorn workers.
Automatically migrates legacy incidents.json records and maintains:
- Operational Incidents with GIS elevation, population exposure, and road routing telemetry
- Immutable Dispatch & Audit Event Timeline (incident_events)
- RFC 7946 GeoJSON & CSV Operational Export Generators
"""

import csv
import io
import json
import time
import uuid
import sqlite3
import logging
from pathlib import Path
from threading import Lock
from typing import Dict, List, Any, Optional

logger = logging.getLogger("IncidentStore")

DB_PATH = Path(__file__).parent / "lifeline.db"
LEGACY_JSON_PATH = Path(__file__).parent / "incidents.json"
STORE_LOCK = Lock()

# Pre-seeded operational incidents representing live Lagos reality
SEED_INCIDENTS = [
    {
        "id": "INC-2026-0891",
        "service": "flood",
        "title": "Severe Flash Flood - Admiralty Way / Lekki Phase 1",
        "location": "Admiralty Way, Lekki Phase 1",
        "coordinates": [3.4723, 6.4480],
        "severity": "CRITICAL",
        "status": "DISPATCHED",
        "reported_by": "Citizen WhatsApp Gateway",
        "contact": "+234 803 *** 1928",
        "water_depth_cm": 65,
        "elevation_m": 4.0,
        "exposed_population": 26800,
        "description": "Rising floodwaters have stalled 4 SUVs near Chevron roundabout. Residents reporting waist-level water entering ground floor compounds.",
        "assigned_unit": "Water Tender Tanker (10,000L)",
        "station_id": "fire_lekki",
        "route_distance_km": 0.92,
        "route_eta_min": 2.4,
        "flood_detour": 0,
        "created_at": "2026-10-07T12:15:30Z",
        "updated_at": "2026-10-07T12:30:10Z"
    },
    {
        "id": "INC-2026-0892",
        "service": "fire",
        "title": "Transformer Electrical Fire - Ilupeju Industrial Layout",
        "location": "Coker Road, Ilupeju Industrial Estate",
        "coordinates": [3.3605, 6.5485],
        "severity": "CRITICAL",
        "status": "DISPATCHED",
        "reported_by": "Emergency Hotline 767",
        "contact": "+234 802 *** 4410",
        "water_depth_cm": 0,
        "elevation_m": 22.0,
        "exposed_population": 41200,
        "description": "High-voltage distribution transformer ignited with heavy black smoke spreading towards nearby plastic warehouse. Substation isolated.",
        "assigned_unit": "Chemical Hazmat Tender (LAFIRE Ilupeju)",
        "station_id": "fire_ilupeju",
        "route_distance_km": 0.85,
        "route_eta_min": 2.1,
        "flood_detour": 0,
        "created_at": "2026-10-07T12:45:00Z",
        "updated_at": "2026-10-07T12:55:20Z"
    },
    {
        "id": "INC-2026-0893",
        "service": "medical",
        "title": "Multiple Vehicle Collision - Third Mainland Bridge (Adeniji Descent)",
        "location": "Third Mainland Bridge, Adeniji Adele Exit",
        "coordinates": [3.3950, 6.4720],
        "severity": "CRITICAL",
        "status": "DISPATCHED",
        "reported_by": "LASTMA Patrol Drone",
        "contact": "+234 800 *** LASTMA",
        "water_depth_cm": 5,
        "elevation_m": 9.0,
        "exposed_population": 18400,
        "description": "3-car pileup during wet road conditions with two passengers trapped. LASAMBUS trauma ambulance mobilized.",
        "assigned_unit": "Emergency Resuscitation Team (Broad St)",
        "station_id": "med_broad_st",
        "route_distance_km": 3.15,
        "route_eta_min": 4.8,
        "flood_detour": 0,
        "created_at": "2026-10-07T13:02:15Z",
        "updated_at": "2026-10-07T13:12:00Z"
    },
    {
        "id": "INC-2026-0894",
        "service": "crime",
        "title": "Armed Burglary Interdiction - Victoria Island Commercial District",
        "location": "Ahmadu Bello Way, VI (Near Silverbird)",
        "coordinates": [3.4150, 6.4280],
        "severity": "WARNING",
        "status": "TRIAGED",
        "reported_by": "Private Security Control Center",
        "contact": "+234 818 *** 9901",
        "water_depth_cm": 35,
        "elevation_m": 3.0,
        "exposed_population": 29500,
        "description": "Break-in attempt reported at banking annex; security guards pinned. RRS patrol vehicles rerouted via Ozumba Mbadiwe to bypass coastal ponding.",
        "assigned_unit": "Rapid Response Cruiser (Lion Bldg)",
        "station_id": "sec_lion_bldg",
        "route_distance_km": 4.40,
        "route_eta_min": 6.2,
        "flood_detour": 1,
        "created_at": "2026-10-07T13:18:40Z",
        "updated_at": "2026-10-07T13:22:00Z"
    },
    {
        "id": "INC-2026-0895",
        "service": "infrastructure",
        "title": "Drainage Culvert Collapse - Abraham Adesanya Roundabout",
        "location": "Lekki-Epe Expressway, Ajah",
        "coordinates": [3.5680, 6.4670],
        "severity": "WARNING",
        "status": "TRIAGED",
        "reported_by": "Civic Web Portal",
        "contact": "+234 809 *** 3345",
        "water_depth_cm": 42,
        "elevation_m": 4.5,
        "exposed_population": 34900,
        "description": "Collapsed storm drain slab has created a 2-meter sinkhole on outer service lane, threatening commercial corridor traffic.",
        "assigned_unit": "Emergency Swamp Buggy / Excavator",
        "station_id": "infra_system_63",
        "route_distance_km": 12.80,
        "route_eta_min": 16.5,
        "flood_detour": 1,
        "created_at": "2026-10-07T13:25:00Z",
        "updated_at": "2026-10-07T13:25:00Z"
    }
]


class IncidentStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self):
        with STORE_LOCK:
            for attempt in range(5):
                try:
                    with self._get_conn() as conn:
                        conn.execute("PRAGMA journal_mode=WAL;")
                        break
                except sqlite3.OperationalError:
                    time.sleep(0.15 * (attempt + 1))
            with self._get_conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS incidents (
                        id TEXT PRIMARY KEY,
                        service TEXT NOT NULL,
                        title TEXT NOT NULL,
                        location TEXT NOT NULL,
                        lon REAL NOT NULL,
                        lat REAL NOT NULL,
                        severity TEXT NOT NULL,
                        status TEXT NOT NULL,
                        reported_by TEXT,
                        contact TEXT,
                        water_depth_cm INTEGER DEFAULT 0,
                        elevation_m REAL,
                        exposed_population INTEGER,
                        description TEXT,
                        assigned_unit TEXT,
                        station_id TEXT,
                        route_distance_km REAL,
                        route_eta_min REAL,
                        flood_detour INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS incident_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        incident_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        actor TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        metadata_json TEXT,
                        timestamp TEXT NOT NULL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_service ON incidents(service);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_events_inc_id ON incident_events(incident_id);")

                count = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
                if count == 0:
                    initial_items = SEED_INCIDENTS
                    if LEGACY_JSON_PATH.exists():
                        try:
                            with open(LEGACY_JSON_PATH, "r", encoding="utf-8") as f:
                                loaded = json.load(f)
                                if isinstance(loaded, list) and len(loaded) > 0:
                                    # Merge defaults onto legacy records
                                    seed_map = {s["id"]: s for s in SEED_INCIDENTS}
                                    merged = []
                                    for item in loaded:
                                        base = dict(seed_map.get(item.get("id"), {}))
                                        base.update(item)
                                        merged.append(base)
                                    initial_items = merged
                        except Exception as e:
                            logger.warning(f"Legacy JSON import fallback: {e}")

                    for inc in initial_items:
                        coords = inc.get("coordinates", [3.4200, 6.4500])
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO incidents (
                                id, service, title, location, lon, lat, severity, status,
                                reported_by, contact, water_depth_cm, elevation_m, exposed_population,
                                description, assigned_unit, station_id, route_distance_km,
                                route_eta_min, flood_detour, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                inc["id"],
                                inc.get("service", "flood").lower(),
                                inc.get("title", "Emergency Incident"),
                                inc.get("location", "Lagos"),
                                float(coords[0]),
                                float(coords[1]),
                                inc.get("severity", "WARNING").upper(),
                                inc.get("status", "TRIAGED").upper(),
                                inc.get("reported_by", "Citizen Portal"),
                                inc.get("contact", "Anonymous"),
                                int(inc.get("water_depth_cm", 0)),
                                inc.get("elevation_m"),
                                inc.get("exposed_population"),
                                inc.get("description", ""),
                                inc.get("assigned_unit", "Standby Command Dispatch"),
                                inc.get("station_id"),
                                inc.get("route_distance_km"),
                                inc.get("route_eta_min"),
                                1 if inc.get("flood_detour") else 0,
                                inc.get("created_at", "2026-10-07T12:00:00Z"),
                                inc.get("updated_at", "2026-10-07T12:00:00Z")
                            )
                        )
                        conn.execute(
                            """
                            INSERT INTO incident_events (incident_id, event_type, actor, summary, metadata_json, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                inc["id"],
                                "INITIALIZED",
                                inc.get("reported_by", "Lagos ESC"),
                                f"Incident registered ({inc.get('severity', 'WARNING')}) — Unit: {inc.get('assigned_unit', 'Standby')}",
                                json.dumps({"status": inc.get("status", "TRIAGED")}),
                                inc.get("created_at", "2026-10-07T12:00:00Z")
                            )
                        )
                conn.commit()

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["coordinates"] = [d["lon"], d["lat"]]
        d["flood_detour"] = bool(d.get("flood_detour", 0))
        return d

    def list_incidents(
        self,
        service: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM incidents WHERE 1=1"
        params: List[Any] = []

        if service and service.lower() not in ["all", "everything"]:
            query += " AND LOWER(service) = ?"
            params.append(service.lower())

        if status and status.lower() not in ["all", "everything"]:
            if status.upper() == "ACTIVE_ONLY":
                query += " AND UPPER(status) != 'RESOLVED'"
            else:
                query += " AND UPPER(status) = ?"
                params.append(status.upper())

        if search and search.strip():
            q = f"%{search.strip().lower()}%"
            query += " AND (LOWER(title) LIKE ? OR LOWER(location) LIKE ? OR LOWER(id) LIKE ? OR LOWER(description) LIKE ?)"
            params.extend([q, q, q, q])

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
            if not row:
                return None
            inc = self._row_to_dict(row)
            ev_rows = conn.execute(
                "SELECT * FROM incident_events WHERE incident_id = ? ORDER BY id DESC LIMIT 30",
                (incident_id,)
            ).fetchall()
            events = []
            for er in ev_rows:
                ed = dict(er)
                if ed.get("metadata_json"):
                    try:
                        ed["metadata"] = json.loads(ed["metadata_json"])
                    except Exception:
                        ed["metadata"] = {}
                events.append(ed)
            inc["events"] = events
            return inc

    def log_event(
        self,
        incident_id: str,
        event_type: str,
        summary: str,
        actor: str = "Lagos ESC",
        metadata: Optional[Dict[str, Any]] = None
    ):
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with STORE_LOCK:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO incident_events (incident_id, event_type, actor, summary, metadata_json, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (incident_id, event_type, actor, summary, json.dumps(metadata or {}), now_iso)
                )
                conn.commit()

    def create_incident(self, data: Dict[str, Any]) -> Dict[str, Any]:
        incident_id = f"INC-2026-{uuid.uuid4().hex[:4].upper()}"
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        coords = data.get("coordinates")
        if not coords or len(coords) < 2:
            coords = [3.4200, 6.4500]

        svc = (data.get("service") or "flood").lower()
        loc = data.get("location") or "Lagos Metropole"
        sev = (data.get("severity") or "WARNING").upper()
        st = (data.get("status") or "TRIAGED").upper()
        unit = data.get("assigned_unit") or "Standby Command Dispatch"

        with STORE_LOCK:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO incidents (
                        id, service, title, location, lon, lat, severity, status,
                        reported_by, contact, water_depth_cm, elevation_m, exposed_population,
                        description, assigned_unit, station_id, route_distance_km,
                        route_eta_min, flood_detour, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        incident_id,
                        svc,
                        data.get("title") or f"{svc.capitalize()} Incident - {loc}",
                        loc,
                        float(coords[0]),
                        float(coords[1]),
                        sev,
                        st,
                        data.get("reported_by", "Citizen Emergency Portal"),
                        data.get("contact", "Anonymous"),
                        int(data.get("water_depth_cm") if data.get("water_depth_cm") is not None else (45 if svc == "flood" else 0)),
                        data.get("elevation_m"),
                        data.get("exposed_population"),
                        data.get("description", "Citizen emergency report lodged through Lifeline portal."),
                        unit,
                        data.get("station_id"),
                        data.get("route_distance_km"),
                        data.get("route_eta_min"),
                        1 if data.get("flood_detour") else 0,
                        now_iso,
                        now_iso
                    )
                )
                conn.execute(
                    """
                    INSERT INTO incident_events (incident_id, event_type, actor, summary, metadata_json, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        incident_id,
                        "CREATED",
                        data.get("reported_by", "Citizen Portal"),
                        f"Distress report logged at {loc} ({sev}). Nearest unit: {unit}",
                        json.dumps({"coordinates": coords, "service": svc}),
                        now_iso
                    )
                )
                conn.commit()

        return self.get_incident(incident_id)

    def update_incident(
        self,
        incident_id: str,
        updates: Dict[str, Any],
        actor: str = "ESC Operator",
        event_summary: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        allowed_cols = {
            "service", "title", "location", "lon", "lat", "severity", "status",
            "water_depth_cm", "elevation_m", "exposed_population", "description",
            "assigned_unit", "station_id", "route_distance_km", "route_eta_min", "flood_detour"
        }

        if "coordinates" in updates and isinstance(updates["coordinates"], list) and len(updates["coordinates"]) >= 2:
            updates["lon"] = float(updates["coordinates"][0])
            updates["lat"] = float(updates["coordinates"][1])

        set_clauses = []
        params = []
        for k, v in updates.items():
            if k in allowed_cols:
                if k == "flood_detour":
                    v = 1 if v else 0
                elif k in ["status", "severity"] and isinstance(v, str):
                    v = v.upper()
                set_clauses.append(f"{k} = ?")
                params.append(v)

        if not set_clauses:
            return self.get_incident(incident_id)

        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        set_clauses.append("updated_at = ?")
        params.append(now_iso)
        params.append(incident_id)

        with STORE_LOCK:
            with self._get_conn() as conn:
                cur = conn.execute(
                    f"UPDATE incidents SET {', '.join(set_clauses)} WHERE id = ?",
                    params
                )
                if cur.rowcount == 0:
                    return None

                summary = event_summary or (
                    f"Status updated to {updates['status'].upper()}"
                    if "status" in updates
                    else f"Incident parameters updated ({', '.join(k for k in updates if k in allowed_cols)})"
                )
                conn.execute(
                    """
                    INSERT INTO incident_events (incident_id, event_type, actor, summary, metadata_json, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        incident_id,
                        "UNIT_DISPATCHED" if updates.get("status") == "DISPATCHED" else "STATUS_CHANGE",
                        actor,
                        summary,
                        json.dumps({k: v for k, v in updates.items() if k in allowed_cols}),
                        now_iso
                    )
                )
                conn.commit()

        return self.get_incident(incident_id)

    def get_kpis(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM incidents").fetchall()
            incidents = [dict(r) for r in rows]

        active_items = [i for i in incidents if i.get("status") != "RESOLVED"]
        active_count = len(active_items)
        critical_count = len([i for i in active_items if i.get("severity") == "CRITICAL"])
        dispatched_units = len([i for i in active_items if i.get("status") in ["DISPATCHED", "EN_ROUTE", "ON_SCENE"]])
        resolved_count = len([i for i in incidents if i.get("status") == "RESOLVED"])
        total_today = len(incidents)

        etas = [float(i["route_eta_min"]) for i in active_items if i.get("route_eta_min") is not None]
        avg_eta = round(sum(etas) / len(etas), 1) if etas else 4.5

        total_exposed = sum(int(i.get("exposed_population") or 0) for i in active_items)

        by_service = {"flood": 0, "fire": 0, "medical": 0, "crime": 0, "infrastructure": 0}
        by_status = {"TRIAGED": 0, "DISPATCHED": 0, "ON_SCENE": 0, "RESOLVED": 0}

        for inc in incidents:
            svc = (inc.get("service") or "flood").lower()
            st = (inc.get("status") or "TRIAGED").upper()
            if svc in by_service and st != "RESOLVED":
                by_service[svc] += 1
            if st in by_status:
                by_status[st] += 1

        return {
            "active_incidents": active_count,
            "critical_sectors": critical_count,
            "units_dispatched": dispatched_units,
            "resolved_incidents": resolved_count,
            "reports_today": total_today,
            "avg_eta_min": avg_eta,
            "total_exposed_population": total_exposed,
            "by_service": by_service,
            "by_status": by_status
        }

    def export_geojson(self, service: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        items = self.list_incidents(service=service, status=status, limit=500)
        features = []
        for inc in items:
            props = {k: v for k, v in inc.items() if k not in ["coordinates", "lon", "lat"]}
            features.append({
                "type": "Feature",
                "id": inc["id"],
                "geometry": {
                    "type": "Point",
                    "coordinates": [inc["lon"], inc["lat"]]
                },
                "properties": props
            })
        return {
            "type": "FeatureCollection",
            "metadata": {
                "generator": "Project Lifeline - Lagos State Emergency Command",
                "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "feature_count": len(features)
            },
            "features": features
        }

    def export_csv(self, service: Optional[str] = None, status: Optional[str] = None) -> str:
        items = self.list_incidents(service=service, status=status, limit=500)
        buf = io.StringIO()
        fields = [
            "id", "service", "severity", "status", "title", "location",
            "lat", "lon", "elevation_m", "water_depth_cm", "exposed_population",
            "assigned_unit", "route_distance_km", "route_eta_min", "flood_detour",
            "reported_by", "contact", "created_at", "updated_at"
        ]
        writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for inc in items:
            writer.writerow(inc)
        return buf.getvalue()


# Global singleton
incident_store = IncidentStore()
