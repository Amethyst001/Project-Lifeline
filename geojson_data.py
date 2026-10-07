"""
Project Lifeline - Lagos State Multi-Emergency Infrastructure GeoJSON
Contains geo-referenced assets and tactical monitoring zones across:
1. Flood & Hydrology Nodes
2. Lagos State Fire Service (LAFIRE)
3. Lagos State Ambulance Service & Trauma Centers (LASAMBUS / Hospitals)
4. Lagos State Police Command & Rapid Response Squad (RRS)
5. Critical Infrastructure & Drainage Basins
"""

LAGOS_SERVICES_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        # --- FLOOD RISK CORRIDORS ---
        {
            "type": "Feature",
            "id": "flood_lekki",
            "geometry": {"type": "Point", "coordinates": [3.4723, 6.4480]},
            "properties": {
                "name": "Lekki Phase 1 / VGC Corridor",
                "category": "flood",
                "severity": "CRITICAL",
                "water_cm": 65,
                "dispatch_asset": "Rescue Amphibian / Canoe",
                "description": "System 63 canal backflow impacting Admiralty Way & Chevron roundabout.",
                "video_id": "lekki",
                "has_video": True
            }
        },
        {
            "type": "Feature",
            "id": "flood_vi",
            "geometry": {"type": "Point", "coordinates": [3.4150, 6.4280]},
            "properties": {
                "name": "Victoria Island (Ahmadu Bello Way)",
                "category": "flood",
                "severity": "WARNING",
                "water_cm": 35,
                "dispatch_asset": "High-Clearance Heavy Truck",
                "description": "Atlantic tidal surge runoff overflowing coastal drainage culverts.",
                "video_id": "vi",
                "has_video": True
            }
        },
        {
            "type": "Feature",
            "id": "flood_ikoyi",
            "geometry": {"type": "Point", "coordinates": [3.4320, 6.4530]},
            "properties": {
                "name": "Ikoyi (Bourdillon & Banana Island)",
                "category": "flood",
                "severity": "NORMAL",
                "water_cm": 12,
                "dispatch_asset": "Commercial Patrol Vehicle",
                "description": "Sub-surface drainage pumps operating at normal nominal capacity.",
                "video_id": "ikoyi",
                "has_video": True
            }
        },
        {
            "type": "Feature",
            "id": "flood_third_mainland",
            "geometry": {"type": "Point", "coordinates": [3.3950, 6.4720]},
            "properties": {
                "name": "Third Mainland Bridge (Oworo - Adeniji)",
                "category": "flood",
                "severity": "NORMAL",
                "water_cm": 5,
                "dispatch_asset": "Rapid Response Motorcycle / Okada",
                "description": "Lagoon clearance nominal; expansion joint sensors report zero ponding.",
                "video_id": "third_mainland",
                "has_video": True
            }
        },
        {
            "type": "Feature",
            "id": "flood_ajah",
            "geometry": {"type": "Point", "coordinates": [3.5680, 6.4670]},
            "properties": {
                "name": "Ajah - Abraham Adesanya Junction",
                "category": "flood",
                "severity": "WARNING",
                "water_cm": 42,
                "dispatch_asset": "Drainage Suction Tanker",
                "description": "Low-lying basin flooding along Expressway feeder roads.",
                "video_id": "lekki",
                "has_video": False
            }
        },

        # --- FIRE SERVICE (LAFIRE STATIONS) ---
        {
            "type": "Feature",
            "id": "fire_alausa",
            "geometry": {"type": "Point", "coordinates": [3.3590, 6.6180]},
            "properties": {
                "name": "Lagos State Fire Service HQ (Alausa)",
                "category": "fire",
                "severity": "NORMAL",
                "units_available": 6,
                "dispatch_asset": "Heavy Pumper Engine 01",
                "description": "Central state command with foam tender and 30m aerial turntable ladder.",
                "contact": "767 / 112"
            }
        },
        {
            "type": "Feature",
            "id": "fire_lekki",
            "geometry": {"type": "Point", "coordinates": [3.4680, 6.4420]},
            "properties": {
                "name": "LAFIRE Station Lekki Phase 1",
                "category": "fire",
                "severity": "NORMAL",
                "units_available": 3,
                "dispatch_asset": "Water Tender Tanker (10,000L)",
                "description": "Primary peninsula coverage from Toll Gate to Eleko axis.",
                "contact": "08033235891"
            }
        },
        {
            "type": "Feature",
            "id": "fire_marina",
            "geometry": {"type": "Point", "coordinates": [3.3880, 6.4520]},
            "properties": {
                "name": "LAFIRE Marina & Central Island Station",
                "category": "fire",
                "severity": "WARNING",
                "units_available": 2,
                "dispatch_asset": "Rapid Intervention Vehicle",
                "description": "High-density commercial sector response unit covering Balogun & Marina.",
                "contact": "08033235892"
            }
        },
        {
            "type": "Feature",
            "id": "fire_ilupeju",
            "geometry": {"type": "Point", "coordinates": [3.3650, 6.5510]},
            "properties": {
                "name": "LAFIRE Ilupeju Industrial Station",
                "category": "fire",
                "severity": "NORMAL",
                "units_available": 4,
                "dispatch_asset": "Chemical Hazmat Tender",
                "description": "Equipped for industrial chemical, factory, and warehouse blazes.",
                "contact": "08033235893"
            }
        },

        # --- MEDICAL & TRAUMA (LASAMBUS / HOSPITALS) ---
        {
            "type": "Feature",
            "id": "med_lasuth",
            "geometry": {"type": "Point", "coordinates": [3.3510, 6.5920]},
            "properties": {
                "name": "LASUTH Ikeja (Level-1 Trauma Center)",
                "category": "medical",
                "severity": "NORMAL",
                "beds_available": 24,
                "dispatch_asset": "LASAMBUS Advanced Life Support (ALS-01)",
                "description": "Tertiary referral surgical trauma center with helipad access.",
                "contact": "0800-LASAMBUS"
            }
        },
        {
            "type": "Feature",
            "id": "med_gbagada",
            "geometry": {"type": "Point", "coordinates": [3.3860, 6.5560]},
            "properties": {
                "name": "Gbagada General Hospital & Burns Center",
                "category": "medical",
                "severity": "NORMAL",
                "beds_available": 18,
                "dispatch_asset": "LASAMBUS Rapid Ambulance 04",
                "description": "Specialized burns and trauma resuscitation unit on Gbagada Expressway.",
                "contact": "0800-LASAMBUS"
            }
        },
        {
            "type": "Feature",
            "id": "med_broad_st",
            "geometry": {"type": "Point", "coordinates": [3.3910, 6.4530]},
            "properties": {
                "name": "General Hospital Lagos (Broad Street)",
                "category": "medical",
                "severity": "WARNING",
                "beds_available": 9,
                "dispatch_asset": "Emergency Resuscitation Team",
                "description": "Island primary acute admission and emergency department.",
                "contact": "01-2630011"
            }
        },
        {
            "type": "Feature",
            "id": "med_lekki",
            "geometry": {"type": "Point", "coordinates": [3.4910, 6.4380]},
            "properties": {
                "name": "Lekki Emergency & Trauma Post",
                "category": "medical",
                "severity": "NORMAL",
                "beds_available": 14,
                "dispatch_asset": "Mobile Intensive Care Ambulance",
                "description": "Rapid triage center for maritime, coastal, and highway casualties.",
                "contact": "0800-LASAMBUS"
            }
        },

        # --- CRIME & SECURITY (LAGOS POLICE / RRS) ---
        {
            "type": "Feature",
            "id": "sec_rrs_alausa",
            "geometry": {"type": "Point", "coordinates": [3.3570, 6.6210]},
            "properties": {
                "name": "Rapid Response Squad (RRS HQ Alausa)",
                "category": "crime",
                "severity": "NORMAL",
                "patrols_active": 42,
                "dispatch_asset": "Tactical Armored Patrol / Gunboat Link",
                "description": "High-mobility tactical interdiction team operating 24/7 across bridges and arteries.",
                "contact": "09053950347"
            }
        },
        {
            "type": "Feature",
            "id": "sec_maroko",
            "geometry": {"type": "Point", "coordinates": [3.4540, 6.4360]},
            "properties": {
                "name": "Maroko Police Division (Lekki / Oniru)",
                "category": "crime",
                "severity": "WARNING",
                "patrols_active": 8,
                "dispatch_asset": "Highway Patrol Unit 12",
                "description": "Covers Lekki Toll Gate, coastal corridor, and Victoria Island border.",
                "contact": "08065154338"
            }
        },
        {
            "type": "Feature",
            "id": "sec_lion_bldg",
            "geometry": {"type": "Point", "coordinates": [3.3980, 6.4520]},
            "properties": {
                "name": "Lion Building Police Area A Command",
                "category": "crime",
                "severity": "NORMAL",
                "patrols_active": 15,
                "dispatch_asset": "Rapid Response Cruiser",
                "description": "Lagos Island central enforcement covering banks, markets, and jetties.",
                "contact": "08033011052"
            }
        },

        # --- INFRASTRUCTURE & LIFELINES ---
        {
            "type": "Feature",
            "id": "infra_3mb_choke",
            "geometry": {"type": "Point", "coordinates": [3.4020, 6.4850]},
            "properties": {
                "name": "Third Mainland Bridge Structural Span",
                "category": "infrastructure",
                "severity": "NORMAL",
                "integrity_index": "98%",
                "dispatch_asset": "LASTMA Traffic & Towing Heavy Crane",
                "description": "11.8 km arterial connector monitored for deck ponding and load stress.",
                "contact": "LASTMA 0800-LASTMA"
            }
        },
        {
            "type": "Feature",
            "id": "infra_eko_bridge",
            "geometry": {"type": "Point", "coordinates": [3.3760, 6.4670]},
            "properties": {
                "name": "Eko Bridge & Costain Interchange",
                "category": "infrastructure",
                "severity": "NORMAL",
                "integrity_index": "95%",
                "dispatch_asset": "Structural Engineering Response Unit",
                "description": "Critical mainland-island conduit with real-time expansion joint monitoring.",
                "contact": "Federal Ministry of Works"
            }
        },
        {
            "type": "Feature",
            "id": "infra_system_63",
            "geometry": {"type": "Point", "coordinates": [3.4610, 6.4470]},
            "properties": {
                "name": "System 63 Primary Drainage Canal (Lekki)",
                "category": "infrastructure",
                "severity": "CRITICAL",
                "integrity_index": "58% (Siltation Blockage)",
                "dispatch_asset": "Emergency Swamp Buggy / Excavator",
                "description": "Canal siltation causing upstream backup during high-tide discharge.",
                "contact": "Lagos Ministry of Environment"
            }
        }
    ]
}

def get_geojson_by_service(service: str = None) -> dict:
    """Return all features or filter by category (flood, fire, medical, crime, infrastructure)."""
    if not service or service.lower() in ["all", "everything"]:
        return LAGOS_SERVICES_GEOJSON
    
    svc = service.lower()
    filtered_features = [
        f for f in LAGOS_SERVICES_GEOJSON["features"]
        if f.get("properties", {}).get("category") == svc
    ]
    return {
        "type": "FeatureCollection",
        "features": filtered_features
    }
