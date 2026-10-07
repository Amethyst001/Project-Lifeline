"""
Project Lifeline - Persistent Incident Store
Thread-safe store for citizen reports and multi-emergency dispatches.
Pre-seeds realistic operational Lagos incidents across all 5 sectors.
"""

import json
import time
import uuid
import logging
from pathlib import Path
from threading import Lock
from typing import Dict, List, Any, Optional

logger = logging.getLogger("IncidentStore")
INCIDENTS_FILE = Path(__file__).parent / "incidents.json"
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
        "description": "Rising floodwaters have stalled 4 SUVs near Chevron roundabout. Residents reporting waist-level water entering ground floor compounds.",
        "assigned_unit": "LASEMA Amphibious Rescue Unit 02",
        "created_at": "2026-10-07T12:15:30Z",
        "updated_at": "2026-10-07T12:30:10Z"
    },
    {
        "id": "INC-2026-0892",
        "service": "fire",
        "title": "Transformer Electrical Fire - Ilupeju Industrial Layout",
        "location": "Coker Road, Ilupeju Industrial Estate",
        "coordinates": [3.3650, 6.5510],
        "severity": "CRITICAL",
        "status": "DISPATCHED",
        "reported_by": "Emergency Hotline 767",
        "contact": "+234 802 *** 4410",
        "water_depth_cm": 0,
        "description": "High-voltage distribution transformer ignited with heavy black smoke spreading towards nearby plastic warehouse. Substation isolated.",
        "assigned_unit": "LAFIRE Engine 03 (Ilupeju Station)",
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
        "description": "3-car pileup during wet road conditions with two passengers trapped. LASAMBUS trauma ambulance mobilized.",
        "assigned_unit": "LASAMBUS ALS-01 & LASTMA Towing",
        "created_at": "2026-10-07T13:02:15Z",
        "updated_at": "2026-10-07T13:12:00Z"
    },
    {
        "id": "INC-2026-0894",
        "service": "crime",
        "title": "Armed Burglary in Progress - Victoria Island Commercial District",
        "location": "Ahmadu Bello Way, VI (Near Silverbird)",
        "coordinates": [3.4150, 6.4280],
        "severity": "WARNING",
        "status": "TRIAGED",
        "reported_by": "Private Security Control Center",
        "contact": "+234 818 *** 9901",
        "water_depth_cm": 35,
        "description": "Break-in attempt reported at banking annex; security guards pinned. RRS patrol vehicles rerouted via Ozumba Mbadiwe.",
        "assigned_unit": "RRS Rapid Patrol Team 08",
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
        "description": "Collapsed storm drain slab has created a 2-meter sinkhole on outer service lane, threatening morning commercial traffic.",
        "assigned_unit": "Lagos Public Works Corp (LSPWC)",
        "created_at": "2026-10-07T13:25:00Z",
        "updated_at": "2026-10-07T13:25:00Z"
    }
]

class IncidentStore:
    def __init__(self, filepath: Path = INCIDENTS_FILE):
        self.filepath = filepath
        self._ensure_file()

    def _ensure_file(self):
        with STORE_LOCK:
            if not self.filepath.exists():
                try:
                    with open(self.filepath, "w", encoding="utf-8") as f:
                        json.dump(SEED_INCIDENTS, f, indent=2)
                except Exception as e:
                    logger.error(f"Failed to create incidents store: {e}")

    def list_incidents(self, service: Optional[str] = None, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        self._ensure_file()
        with STORE_LOCK:
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    incidents = json.load(f)
            except Exception as e:
                logger.error(f"Failed to read incidents: {e}")
                incidents = SEED_INCIDENTS

        filtered = incidents
        if service and service.lower() not in ["all", "everything"]:
            svc = service.lower()
            filtered = [i for i in filtered if i.get("service", "").lower() == svc]
            
        if status and status.lower() not in ["all"]:
            st = status.upper()
            filtered = [i for i in filtered if i.get("status", "").upper() == st]

        # Sort reverse chronological by created_at
        filtered.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return filtered[:limit]

    def create_incident(self, data: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_file()
        incident_id = f"INC-2026-{uuid.uuid4().hex[:4].upper()}"
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        # Coordinate lookup default if not provided
        coords = data.get("coordinates")
        if not coords or len(coords) < 2:
            coords = [3.4200, 6.4500]  # Lagos Central

        new_incident = {
            "id": incident_id,
            "service": data.get("service", "flood").lower(),
            "title": data.get("title") or f"{data.get('service', 'Emergency').capitalize()} in {data.get('location', 'Lagos')}",
            "location": data.get("location", "Lagos Metropole"),
            "coordinates": coords,
            "severity": (data.get("severity") or "WARNING").upper(),
            "status": "TRIAGED",
            "reported_by": data.get("reported_by", "Citizen Direct Portal"),
            "contact": data.get("contact", "Anonymous"),
            "water_depth_cm": int(data.get("water_depth_cm") or (45 if data.get("service") == "flood" else 0)),
            "description": data.get("description", "Citizen emergency report lodged through Lifeline portal."),
            "assigned_unit": data.get("assigned_unit", "Standby Command Dispatch"),
            "created_at": now_iso,
            "updated_at": now_iso
        }

        with STORE_LOCK:
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    incidents = json.load(f)
            except Exception:
                incidents = []

            incidents.insert(0, new_incident)
            
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(incidents, f, indent=2)

        return new_incident

    def update_incident(self, incident_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self._ensure_file()
        updated_item = None
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        with STORE_LOCK:
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    incidents = json.load(f)
            except Exception as e:
                logger.error(f"Read error during update: {e}")
                return None

            for inc in incidents:
                if inc.get("id") == incident_id:
                    for k, v in updates.items():
                        if k not in ["id", "created_at"]:
                            inc[k] = v
                    inc["updated_at"] = now_iso
                    updated_item = inc
                    break

            if updated_item:
                with open(self.filepath, "w", encoding="utf-8") as f:
                    json.dump(incidents, f, indent=2)

        return updated_item

    def get_kpis(self) -> Dict[str, Any]:
        self._ensure_file()
        with STORE_LOCK:
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    incidents = json.load(f)
            except Exception:
                incidents = SEED_INCIDENTS

        active_count = len([i for i in incidents if i.get("status") in ["TRIAGED", "DISPATCHED", "ACTIVE"]])
        critical_count = len([i for i in incidents if i.get("severity") == "CRITICAL" and i.get("status") != "RESOLVED"])
        dispatched_units = len([i for i in incidents if i.get("status") == "DISPATCHED"])
        total_today = len(incidents)

        by_service = {
            "flood": 0, "fire": 0, "medical": 0, "crime": 0, "infrastructure": 0
        }
        for inc in incidents:
            svc = inc.get("service", "flood").lower()
            if svc in by_service:
                by_service[svc] += 1

        return {
            "active_incidents": active_count,
            "critical_sectors": critical_count,
            "units_dispatched": dispatched_units,
            "reports_today": total_today,
            "by_service": by_service
        }

# Global singleton
incident_store = IncidentStore()
