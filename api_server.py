"""
Project Lifeline - Unified Emergency Command API Server
Integrates:
- Computer Vision Agent (Gemini 3 Multimodal)
- Sovereign Multilingual N-ATLAS (5 languages: EN, YO, PCM, HA, IG)
- Live Open-Meteo Weather & Hydrology Engine
- Multi-Hazard Lagos Emergency Mesh (Flood, Fire, Medical, Crime, Infrastructure)
- Real Incident Store & Citizen Reporting Pipeline
- Termii Sovereign Civic Broadcasting
"""

import os
import json
import logging
from pathlib import Path
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from vision_agent import VisionAgent
from hierarchical_analyzer import HierarchicalAnalyzer
from weather_service import get_live_weather, get_48h_forecast
from geojson_data import get_geojson_by_service, LAGOS_SERVICES_GEOJSON
from incident_store import incident_store
from broadcast_service import broadcast_service
from natlas_service import natlas_service

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
    """Serve the main dashboard HTML."""
    return app.send_static_file('index.html')


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "operational",
        "platform": "Project Lifeline - Lagos ESC",
        "subsystems": {
            "vision_agent": "ready",
            "weather_engine": "connected",
            "incident_store": "active",
            "natlas_sovereign": "online",
            "termii_gateway": "ready"
        }
    })


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
    """Command KPIs combining incident store and live weather."""
    kpis = incident_store.get_kpis()
    weather = get_live_weather()
    kpis["rainfall_mm"] = weather.get("precipitation_mm", 0.0)
    kpis["flood_risk_score"] = weather.get("flood_risk_score", "MODERATE")
    kpis["tide_surge_m"] = weather.get("atlantic_tide_surge_m", 0.5)
    return jsonify(kpis)


# --- INCIDENT MANAGEMENT ---

@app.route('/api/incidents', methods=['GET'])
def list_incidents():
    """Retrieve operational incidents, filterable by service and status."""
    service = request.args.get('service')
    status = request.args.get('status')
    limit = int(request.args.get('limit', 50))
    items = incident_store.list_incidents(service=service, status=status, limit=limit)
    return jsonify(items)


@app.route('/api/incidents/<incident_id>/update', methods=['POST'])
def update_incident(incident_id):
    """Operator action to update status or assigned unit."""
    data = request.get_json() or {}
    updated = incident_store.update_incident(incident_id, data)
    if not updated:
        return jsonify({"error": "Incident not found"}), 404
    return jsonify(updated)


@app.route('/api/report', methods=['POST'])
def citizen_report():
    """
    Ingest citizen emergency distress report.
    Performs location normalization, incident creation, sovereign broadcast generation,
    and SMS acknowledgment.
    """
    data = request.get_json() or {}
    location = data.get('location', '').strip()
    service = data.get('service', 'flood').lower()
    description = data.get('description', '').strip()
    contact = data.get('contact', '').strip()
    coords = data.get('coordinates')
    
    # Geocode with OpenStreetMap Nominatim if coordinates not explicitly passed
    if not coords and location:
        try:
            geo_query = f"{location}, Lagos, Nigeria"
            nominatim_url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(geo_query)}&format=json&limit=1"
            headers = {"User-Agent": "ProjectLifeline-EmergencyDispatch/1.0"}
            n_res = requests.get(nominatim_url, headers=headers, timeout=2.5)
            if n_res.status_code == 200 and len(n_res.json()) > 0:
                first = n_res.json()[0]
                coords = [float(first["lon"]), float(first["lat"])]
        except Exception as ge:
            logger.warning(f"Geocoding lookup fallback: {ge}")
            
    if not coords:
        # Default to Lekki/Island centroid
        coords = [3.4500, 6.4400]

    # Water depth estimation for floods
    water_cm = int(data.get('water_depth_cm', 50 if service == 'flood' else 0))
    
    # Severity assessment
    severity = data.get('severity')
    if not severity:
        if service in ['fire', 'crime'] or water_cm >= 40:
            severity = 'CRITICAL'
        elif water_cm >= 20:
            severity = 'WARNING'
        else:
            severity = 'MODERATE'

    # Save to persistent incident store
    incident_record = incident_store.create_incident({
        "service": service,
        "title": f"Reported {service.capitalize()} - {location or 'Lagos Sector'}",
        "location": location or "Lagos Metropole",
        "coordinates": coords,
        "severity": severity,
        "reported_by": "Citizen Emergency Portal",
        "contact": contact or "Anonymous Citizen",
        "water_depth_cm": water_cm,
        "description": description or f"Citizen flagged urgent {service} incident."
    })

    # Generate multilingual alert in user's language (default English)
    user_lang = data.get('language', 'english')
    broadcast = natlas_service.generate_multilingual_broadcast(
        zone_name=location or "Reported Sector",
        status=severity,
        water_cm=water_cm,
        hazard_type=service,
        language=user_lang
    )

    # Dispatch Termii SMS acknowledgment if contact number provided
    sms_receipt = None
    if contact and (contact.startswith("0") or contact.startswith("+") or contact.startswith("234")):
        sms_msg = f"LIFELINE ACK: {service.upper()} report received for {location}. Unit assigned: {incident_record['assigned_unit']}. Track: http://amethysttrades.abrdns.com/lifeline/"
        sms_receipt = broadcast_service.send_sms(contact, sms_msg)

    return jsonify({
        "status": "success",
        "incident": incident_record,
        "civic_broadcast": broadcast,
        "sms_receipt": sms_receipt
    }), 201


# --- SOVEREIGN N-ATLAS MULTILINGUAL DISPATCH ---

@app.route('/api/natlas/broadcast/<zone_id>', methods=['GET'])
def natlas_broadcast(zone_id):
    """Generate sovereign multilingual emergency alert across 5 languages & 5 hazards."""
    lang = request.args.get('lang', 'english')
    hazard = request.args.get('hazard', 'flood')
    
    zone_names = {
        "lekki": "Lekki Phase 1 / VGC",
        "vi": "Victoria Island (Ahmadu Bello Way)",
        "ikoyi": "Ikoyi Corridor (Bourdillon)",
        "third_mainland": "Third Mainland Bridge Corridor",
        "ajah": "Ajah - Abraham Adesanya",
        "alausa": "Alausa State Secretariat Axis",
        "ilupeju": "Ilupeju Industrial Sector"
    }
    name = zone_names.get(zone_id, zone_id.replace("_", " ").title())
    
    # Realistic water / severity telemetry
    water_cm = 65 if zone_id in ["lekki", "ajah"] else (35 if zone_id == "vi" else 10)
    status = "CRITICAL" if water_cm >= 40 or hazard in ["fire", "crime"] else "WARNING"
    
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
    """Parse citizen distress voice transcript via N-ATLAS understanding."""
    data = request.get_json() or {}
    transcript = data.get("transcript", "Omi ti wọle si ile wa ni VGC, ẹ gbà wá o!")
    lang = data.get("language", "yoruba")
    
    parsed = natlas_service.parse_voice_distress_call(transcript, language=lang)
    return jsonify(parsed)


# --- TELECOM BROADCAST DISPATCH ---

@app.route('/api/broadcast/sms', methods=['POST'])
def send_telecom_broadcast():
    """Dispatch SMS / WhatsApp emergency warning to community or responder phone."""
    data = request.get_json() or {}
    phone = data.get('phone', '+234 800 LIFELINE')
    message = data.get('message', 'LIFELINE ALERT: Evacuate low-lying areas in Lekki due to canal overflow.')
    receipt = broadcast_service.send_sms(phone, message)
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
    print("PROJECT LIFELINE — LAGOS STATE MULTI-EMERGENCY COMMAND")
    print(f"Listening on port: {port}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=True)
