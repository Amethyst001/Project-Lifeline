"""
Project Lifeline - Unified Multi-Emergency GIS & Command API Server
Integrates:
- Geospatial Intelligence & Hydrology DEM Engine (Copernicus 90m DEM, CARTO, Mapbox/OSRM Routing)
- Dynamic Flood-Avoidance Emergency Vehicle Routing
- Cross-Process SQLite WAL Incident & Audit Timeline Store
- Sovereign Multilingual N-ATLAS (5 languages: EN, YO, PCM, HA, IG)
- Live Open-Meteo Weather & Coastal Surge Telemetry
- Computer Vision Agent (Gemini 3 Multimodal)
- Termii Sovereign Telecom Broadcasting
"""

import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, request, Response
from flask_cors import CORS

from vision_agent import VisionAgent
from hierarchical_analyzer import HierarchicalAnalyzer
from weather_service import get_live_weather, get_48h_forecast
from geojson_data import get_geojson_by_service
from incident_store import incident_store
from broadcast_service import broadcast_service
from natlas_service import natlas_service
from gis_engine import gis_engine

logger = logging.getLogger("LifelineServer")
logging.basicConfig(level=logging.INFO)

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Initialize AI agents
vision_agent = VisionAgent()
hierarchical_agent = HierarchicalAnalyzer()

# Video paths by zone
ZONE_VIDEOS = {
    "lekki": [
        "test_videos_merged/lekki_vgc_flood.mp4",
        "test_videos_merged/lekki_downpour_flood.mp4",
        "test_videos_merged/lekki_vi_houses_destroyed.mp4",
        "test_videos_merged/ajah_flood.mp4"
    ],
    "vi": [
        "test_videos_merged/vi_ahmadu_bello_way.mp4",
        "test_videos_merged/vi_canoes_after_rain.mp4",
        "test_videos_merged/vi_flooded_island_brt.mp4"
    ],
    "ikoyi": [
        "test_videos_merged/banana_island_drone.mp4",
        "test_videos_merged/ikoyi_bourdillon_flood.mp4"
    ],
    "third_mainland": [
        "test_videos_merged/third_mainland_bridge_inspection.mp4",
        "test_videos_merged/third_mainland_oworo_flooded.mp4",
        "test_videos_merged/third_mainland_water_rises.mp4"
    ]
}


@app.route('/')
def index():
    """Serve the main command workstation HTML."""
    return app.send_static_file('index.html')


@app.route('/api/health', methods=['GET'])
def health():
    caps = gis_engine.get_capabilities()
    return jsonify({
        "status": "operational",
        "platform": "Project Lifeline - Lagos ESC v3.0 (GIS Production)",
        "subsystems": {
            "vision_agent": caps["vision_ai"],
            "weather_engine": "connected",
            "incident_store": "sqlite_wal_active",
            "gis_dem_engine": caps["dem_engine"]["provider"],
            "gis_routing_engine": caps["routing_engine"]["provider"],
            "gis_spatial_sql": caps["spatial_sql_engine"]["provider"],
            "natlas_sovereign": "online",
            "termii_gateway": caps["telecom_gateway"]
        },
        "gis_capabilities": caps
    })


# --- GEOSPATIAL INTELLIGENCE, DEM HYDROLOGY & ROUTING ---

@app.route('/api/gis/config', methods=['GET'])
def gis_config():
    """Return GIS provider capabilities and safe client configuration."""
    return jsonify(gis_engine.get_capabilities())


@app.route('/api/gis/elevation', methods=['GET'])
def gis_elevation():
    """Analyze 3x3 Copernicus 90m DEM grid, slope %, runoff vector, and ponding risk."""
    try:
        lon = float(request.args.get('lon', 3.4723))
        lat = float(request.args.get('lat', 6.4480))
    except ValueError:
        return jsonify({"error": "Invalid lon/lat parameters"}), 400

    result = gis_engine.analyze_elevation_and_runoff(lon, lat)
    return jsonify(result)


@app.route('/api/gis/route', methods=['GET'])
def gis_route():
    """Compute turn-by-turn emergency responder route with dynamic flood hazard avoidance."""
    try:
        dest_lon = float(request.args.get('dest_lon', 3.4723))
        dest_lat = float(request.args.get('dest_lat', 6.4480))
        orig_lon = float(request.args['origin_lon']) if request.args.get('origin_lon') else None
        orig_lat = float(request.args['origin_lat']) if request.args.get('origin_lat') else None
    except ValueError:
        return jsonify({"error": "Invalid coordinate parameters"}), 400

    service = request.args.get('service', 'flood')
    avoid_floods = request.args.get('avoid_floods', 'true').lower() != 'false'
    active_incs = incident_store.list_incidents(status='ACTIVE_ONLY', limit=100)

    route_data = gis_engine.compute_emergency_route(
        dest_lon=dest_lon,
        dest_lat=dest_lat,
        service=service,
        origin_lon=orig_lon,
        origin_lat=orig_lat,
        avoid_floods=avoid_floods,
        active_incidents=active_incs
    )
    return jsonify(route_data)


@app.route('/api/gis/exposure', methods=['GET'])
def gis_exposure():
    """Calculate spatial buffer population exposure and nearby emergency facility join."""
    try:
        lon = float(request.args.get('lon', 3.4723))
        lat = float(request.args.get('lat', 6.4480))
        radius_m = float(request.args.get('radius_m', 1000.0))
    except ValueError:
        return jsonify({"error": "Invalid numeric parameters"}), 400

    exposure = gis_engine.analyze_spatial_exposure(lon, lat, radius_m=radius_m)
    return jsonify(exposure)


@app.route('/api/gis/probe', methods=['GET'])
def gis_spatial_probe():
    """
    Unified Spatial Intelligence Probe for interactive map click inspection:
    Combines reverse geocoding + DEM elevation/runoff + 1km population exposure + responder route.
    """
    try:
        lon = float(request.args.get('lon', 3.4723))
        lat = float(request.args.get('lat', 6.4480))
        radius_m = float(request.args.get('radius_m', 1000.0))
    except ValueError:
        return jsonify({"error": "Invalid coordinates"}), 400

    service = request.args.get('service', 'flood')
    if service in ['all', 'everything']:
        service = 'flood'

    active_incs = incident_store.list_incidents(status='ACTIVE_ONLY', limit=100)
    place = gis_engine.reverse_geocode_lagos(lon, lat)
    dem = gis_engine.analyze_elevation_and_runoff(lon, lat)
    exposure = gis_engine.analyze_spatial_exposure(lon, lat, radius_m=radius_m)
    route = gis_engine.compute_emergency_route(
        dest_lon=lon,
        dest_lat=lat,
        service=service,
        avoid_floods=True,
        active_incidents=active_incs
    )

    return jsonify({
        "coordinates": [round(lon, 6), round(lat, 6)],
        "place": place,
        "dem": dem,
        "exposure": exposure,
        "route": route
    })


@app.route('/api/gis/risk-zones', methods=['GET'])
def gis_risk_zones():
    """Return GeoJSON of DEM runoff vectors and active incident spatial exposure buffers."""
    active_incs = incident_store.list_incidents(status='ACTIVE_ONLY', limit=100)
    return jsonify(gis_engine.build_risk_surface_geojson(active_incidents=active_incs))


@app.route('/api/gis/geocode', methods=['GET'])
def gis_geocode():
    """Forward geocode a Lagos street or landmark."""
    q = request.args.get('q', '').strip()
    return jsonify(gis_engine.geocode_lagos(q))


@app.route('/api/gis/reverse', methods=['GET'])
def gis_reverse():
    """Reverse geocode WGS84 coordinates in Lagos."""
    try:
        lon = float(request.args.get('lon', 3.4500))
        lat = float(request.args.get('lat', 6.4450))
    except ValueError:
        return jsonify({"error": "Invalid coordinates"}), 400
    return jsonify(gis_engine.reverse_geocode_lagos(lon, lat))


# --- WEATHER & HYDROLOGY TELEMETRY ---

@app.route('/api/weather/live', methods=['GET'])
def weather_live():
    """Live Open-Meteo precipitation, wind, humidity and Atlantic surge index."""
    force = request.args.get('refresh', 'false').lower() == 'true'
    telemetry = get_live_weather(force_refresh=force)
    return jsonify(telemetry)


@app.route('/api/weather/forecast', methods=['GET'])
def weather_forecast():
    """48-hour rainfall projection profile for flood risk prediction."""
    forecast = get_48h_forecast()
    return jsonify({"forecast": forecast})


# --- GEOJSON MESH & SECTORS ---

@app.route('/api/zones/geojson', methods=['GET'])
def get_geojson_mesh():
    """Returns Lagos emergency GeoJSON filtered by service type."""
    service = request.args.get('service', 'all')
    geojson = get_geojson_by_service(service)
    return jsonify(geojson)


@app.route('/api/kpis', methods=['GET'])
def get_command_kpis():
    """Command KPIs combining SQLite incident store and live Open-Meteo hydrology."""
    kpis = incident_store.get_kpis()
    weather = get_live_weather()
    kpis["rainfall_mm"] = weather.get("precipitation_mm", 0.0)
    kpis["flood_risk_score"] = weather.get("flood_risk_score", "MODERATE")
    kpis["tide_surge_m"] = weather.get("atlantic_tide_surge_m", 0.5)
    return jsonify(kpis)


# --- INCIDENT MANAGEMENT, TACTICAL DISPATCH & EXPORTS ---

@app.route('/api/incidents', methods=['GET'])
def list_incidents():
    """Retrieve operational incidents, filterable by service, status, and search query."""
    service = request.args.get('service')
    status = request.args.get('status')
    search = request.args.get('q')
    limit = int(request.args.get('limit', 100))
    items = incident_store.list_incidents(service=service, status=status, search=search, limit=limit)
    return jsonify(items)


@app.route('/api/incidents/export', methods=['GET'])
def export_incidents():
    """Export operational incidents as RFC 7946 GeoJSON or CSV for GIS/MDA analysis."""
    fmt = request.args.get('format', 'geojson').lower()
    service = request.args.get('service')
    status = request.args.get('status')

    if fmt == 'csv':
        csv_body = incident_store.export_csv(service=service, status=status)
        return Response(
            csv_body,
            mimetype='text/csv',
            headers={"Content-Disposition": "attachment; filename=lifeline_lagos_incidents.csv"}
        )

    geojson_obj = incident_store.export_geojson(service=service, status=status)
    return Response(
        json.dumps(geojson_obj, indent=2),
        mimetype='application/geo+json',
        headers={"Content-Disposition": "attachment; filename=lifeline_lagos_incidents.geojson"}
    )


@app.route('/api/incidents/<incident_id>', methods=['GET'])
def get_incident_detail(incident_id):
    """Retrieve single incident with full immutable audit event timeline."""
    inc = incident_store.get_incident(incident_id)
    if not inc:
        return jsonify({"error": "Incident not found"}), 404
    return jsonify(inc)


@app.route('/api/incidents/<incident_id>/update', methods=['POST'])
def update_incident(incident_id):
    """Operator action to update status, severity, or assigned unit."""
    data = request.get_json() or {}
    actor = data.pop('actor', 'ESC Operator')
    note = data.pop('note', None)
    updated = incident_store.update_incident(incident_id, data, actor=actor, event_summary=note)
    if not updated:
        return jsonify({"error": "Incident not found"}), 404
    return jsonify(updated)


@app.route('/api/incidents/<incident_id>/dispatch', methods=['POST'])
def dispatch_incident_unit(incident_id):
    """
    Execute real tactical responder dispatch:
    1. Computes optimal road route from nearest station (avoiding active flood hazards)
    2. Updates incident status to DISPATCHED with assigned unit, station, distance, and ETA
    3. Records immutable dispatch event in audit log
    """
    inc = incident_store.get_incident(incident_id)
    if not inc:
        return jsonify({"error": "Incident not found"}), 404

    body = request.get_json() or {}
    lon, lat = inc["coordinates"]
    active_incs = incident_store.list_incidents(status='ACTIVE_ONLY', limit=100)

    route = gis_engine.compute_emergency_route(
        dest_lon=lon,
        dest_lat=lat,
        service=inc["service"],
        origin_lon=body.get("origin_lon"),
        origin_lat=body.get("origin_lat"),
        avoid_floods=True,
        active_incidents=active_incs
    )

    station = route["origin_station"]
    unit_name = body.get("assigned_unit") or f"{station['dispatch_asset']} ({station['name']})"
    detour_note = f" [Flood detour +{route['detour_delta_km']}km]" if route["flood_detour_applied"] else ""
    summary = (
        f"Dispatched {unit_name} via {route['provider']} — "
        f"{route['distance_km']} km, Priority ETA {route['emergency_eta_min']} min{detour_note}"
    )

    updated = incident_store.update_incident(
        incident_id,
        {
            "status": "DISPATCHED",
            "assigned_unit": unit_name,
            "station_id": station["id"],
            "route_distance_km": route["distance_km"],
            "route_eta_min": route["emergency_eta_min"],
            "flood_detour": route["flood_detour_applied"]
        },
        actor=body.get("actor", "ESC Dispatch Console"),
        event_summary=summary
    )

    return jsonify({
        "status": "dispatched",
        "incident": updated,
        "route": route
    })


@app.route('/api/report', methods=['POST'])
def citizen_report():
    """
    Ingest citizen or operator emergency distress report.
    Performs Lagos-bounded geocoding, Copernicus DEM elevation lookup, 1km population exposure,
    nearest responder road routing, N-ATLAS multilingual broadcast synthesis, and Termii SMS ACK.
    """
    data = request.get_json() or {}
    location = data.get('location', '').strip()
    service = data.get('service', 'flood').lower()
    description = data.get('description', '').strip()
    contact = data.get('contact', '').strip()
    coords = data.get('coordinates')

    if coords and isinstance(coords, list) and len(coords) >= 2:
        lon, lat = float(coords[0]), float(coords[1])
        if not location:
            location = gis_engine.reverse_geocode_lagos(lon, lat)["location"]
    else:
        geo = gis_engine.geocode_lagos(location or "Lekki Phase 1")
        lon, lat = geo["coordinates"]
        if not location:
            location = geo["display_name"]

    # Enrich with live DEM elevation & spatial exposure
    dem = gis_engine.analyze_elevation_and_runoff(lon, lat)
    exposure = gis_engine.analyze_spatial_exposure(lon, lat, radius_m=1000.0)

    # Water depth estimation for floods
    default_water = max(35, dem["predicted_ponding_cm"]) if service == 'flood' else 0
    water_cm = int(data.get('water_depth_cm') if data.get('water_depth_cm') is not None else default_water)

    # Severity assessment
    severity = data.get('severity')
    if not severity:
        if service in ['fire', 'crime'] or water_cm >= 40 or dem["hydro_risk_level"] == "CRITICAL":
            severity = 'CRITICAL'
        elif water_cm >= 20 or service == 'medical':
            severity = 'WARNING'
        else:
            severity = 'NORMAL'

    # Pre-compute nearest responder road route & ETA
    active_incs = incident_store.list_incidents(status='ACTIVE_ONLY', limit=100)
    route = gis_engine.compute_emergency_route(
        dest_lon=lon,
        dest_lat=lat,
        service=service,
        avoid_floods=True,
        active_incidents=active_incs
    )
    station = route["origin_station"]
    assigned_unit = f"{station['dispatch_asset']} ({station['name']})"

    incident_record = incident_store.create_incident({
        "service": service,
        "title": data.get("title") or f"Reported {service.capitalize()} - {location}",
        "location": location,
        "coordinates": [lon, lat],
        "severity": severity,
        "status": "TRIAGED",
        "reported_by": data.get("reported_by") or "Citizen Emergency Portal",
        "contact": contact or "Anonymous Citizen",
        "water_depth_cm": water_cm,
        "elevation_m": dem["elevation_m"],
        "exposed_population": exposure["exposed_population"],
        "description": description or f"Urgent {service} distress report filed for {location}.",
        "assigned_unit": assigned_unit,
        "station_id": station["id"],
        "route_distance_km": route["distance_km"],
        "route_eta_min": route["emergency_eta_min"],
        "flood_detour": route["flood_detour_applied"]
    })

    user_lang = data.get('language', 'english')
    broadcast = natlas_service.generate_multilingual_broadcast(
        zone_name=location,
        status=severity,
        water_cm=water_cm,
        hazard_type=service,
        language=user_lang
    )

    sms_receipt = None
    if contact and (contact.startswith("0") or contact.startswith("+") or contact.startswith("234")):
        sms_msg = (
            f"LIFELINE ACK [{incident_record['id']}]: {service.upper()} report logged at {location}. "
            f"Nearest unit: {station['dispatch_asset']} (ETA {route['emergency_eta_min']}m). "
            f"Track: https://lifeline.ktnamethyst.me/"
        )
        sms_receipt = broadcast_service.send_sms(contact, sms_msg)
        incident_store.log_event(
            incident_record["id"],
            "SMS_BROADCAST",
            f"SMS confirmation dispatched to {sms_receipt.get('destination')}",
            actor="Termii Gateway",
            metadata=sms_receipt
        )

    return jsonify({
        "status": "success",
        "incident": incident_store.get_incident(incident_record["id"]),
        "dem": dem,
        "exposure": exposure,
        "route": route,
        "civic_broadcast": broadcast,
        "sms_receipt": sms_receipt
    }), 201


# --- SOVEREIGN N-ATLAS MULTILINGUAL DISPATCH ---

@app.route('/api/natlas/broadcast/<zone_id>', methods=['GET'])
def natlas_broadcast(zone_id):
    """Generate sovereign multilingual emergency alert across 5 languages & 5 hazards."""
    lang = request.args.get('lang', 'english')
    hazard = request.args.get('hazard', 'flood')
    custom_zone = request.args.get('zone_name', '').strip()
    custom_water = request.args.get('water_cm')
    custom_severity = request.args.get('severity')

    zone_names = {
        "lekki": "Lekki Phase 1 / VGC",
        "vi": "Victoria Island (Ahmadu Bello Way)",
        "ikoyi": "Ikoyi Corridor (Bourdillon)",
        "third_mainland": "Third Mainland Bridge Corridor",
        "ajah": "Ajah - Abraham Adesanya",
        "alausa": "Alausa State Secretariat Axis",
        "ilupeju": "Ilupeju Industrial Sector"
    }
    name = custom_zone or zone_names.get(zone_id, zone_id.replace("_", " ").title())

    if custom_water is not None:
        try:
            water_cm = int(custom_water)
        except ValueError:
            water_cm = 45
    else:
        water_cm = 65 if zone_id in ["lekki", "ajah"] else (35 if zone_id == "vi" else 10)

    status = custom_severity or ("CRITICAL" if water_cm >= 40 or hazard in ["fire", "crime"] else "WARNING")

    alert = natlas_service.generate_multilingual_broadcast(
        zone_name=name,
        status=status,
        water_cm=water_cm,
        hazard_type=hazard,
        language=lang
    )
    return jsonify(alert)


@app.route('/api/natlas/distress', methods=['POST'])
def natlas_distress():
    """Parse citizen distress voice/text transcript via N-ATLAS entity extraction."""
    data = request.get_json() or {}
    transcript = data.get("transcript", "Omi ti wọle si ile wa ni VGC, ẹ gbà wá o!")
    lang = data.get("language", "yoruba")

    parsed = natlas_service.parse_voice_distress_call(transcript, language=lang)
    return jsonify(parsed)


# --- TELECOM BROADCAST DISPATCH ---

@app.route('/api/broadcast/sms', methods=['POST'])
def send_telecom_broadcast():
    """Dispatch SMS emergency warning to community relay or specified responder phone."""
    data = request.get_json() or {}
    phone = data.get('phone', '+234 800 LIFELINE')
    message = data.get('message', 'LIFELINE ALERT: Evacuate low-lying areas in Lekki due to canal overflow.')
    incident_id = data.get('incident_id')

    receipt = broadcast_service.send_sms(phone, message)
    if incident_id:
        incident_store.log_event(
            incident_id,
            "SMS_BROADCAST",
            f"Civic alert transmitted via {receipt.get('provider')} ({receipt.get('message_id')})",
            actor="ESC Broadcast",
            metadata=receipt
        )
    return jsonify(receipt)


# --- COMPUTER VISION AGENT (GEMINI 3 MULTIMODAL) ---

@app.route('/api/zones', methods=['GET'])
def get_zones():
    """Get zone camera configuration."""
    return jsonify({
        "zones": list(ZONE_VIDEOS.keys()),
        "videos_per_zone": {k: len(v) for k, v in ZONE_VIDEOS.items()}
    })


@app.route('/api/analyze/<zone_id>', methods=['GET'])
def analyze_zone(zone_id):
    """Analyze a specific zone using its assigned camera video."""
    if zone_id not in ZONE_VIDEOS:
        return jsonify({"error": f"Unknown zone: {zone_id}"}), 404

    video_path = ZONE_VIDEOS[zone_id][0]
    if not Path(video_path).exists():
        return jsonify({"error": f"Video not found: {video_path}"}), 404

    result = vision_agent.analyze_video_frame(video_path, zone_id)
    inc_id = request.args.get('incident_id')
    if inc_id and "error" not in result:
        depth = result.get("flood_assessment", {}).get("water_level_cm", 0)
        incident_store.log_event(
            inc_id,
            "VISION_AUDIT",
            f"Gemini 3 Multimodal Vision verified water depth at {depth}cm ({zone_id})",
            actor="Gemini 3 Vision"
        )
    return jsonify(result)


@app.route('/api/analyze/all', methods=['GET'])
def analyze_all_zones():
    """Analyze all monitored zones simultaneously."""
    results = {}
    for zone_id in ZONE_VIDEOS:
        video_path = ZONE_VIDEOS[zone_id][0]
        if Path(video_path).exists():
            results[zone_id] = vision_agent.analyze_video_frame(video_path, zone_id)
        else:
            results[zone_id] = {"error": "Video not found"}
    return jsonify(results)


@app.route('/api/analyze/hierarchical/<zone_id>', methods=['GET'])
def hierarchical_analyze(zone_id):
    """Use hierarchical (audio-first) analysis for a zone."""
    if zone_id not in ZONE_VIDEOS:
        return jsonify({"error": f"Unknown zone: {zone_id}"}), 404

    video_path = ZONE_VIDEOS[zone_id][0]
    if not Path(video_path).exists():
        return jsonify({"error": f"Video not found: {video_path}"}), 404

    result = hierarchical_agent.hierarchical_analysis(video_path)
    return jsonify(result)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 60)
    print("PROJECT LIFELINE — LAGOS STATE MULTI-EMERGENCY GIS COMMAND")
    print(f"Listening on port: {port}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=True)
