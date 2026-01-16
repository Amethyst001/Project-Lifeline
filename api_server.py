"""
Project Lifeline - Flask API Server
Connects the Vision Agent to the Dashboard UI.
"""
# Load environment variables from .env file FIRST
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request
from flask_cors import CORS
from vision_agent import VisionAgent
from hierarchical_analyzer import HierarchicalAnalyzer
import json
from pathlib import Path

app = Flask(__name__)
CORS(app)  # Allow frontend to call API

# Initialize agents
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


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "agent": "ready"})


@app.route('/api/analyze/<zone_id>', methods=['GET'])
def analyze_zone(zone_id):
    """Analyze a specific zone using its assigned video."""
    if zone_id not in ZONE_VIDEOS:
        return jsonify({"error": f"Unknown zone: {zone_id}"}), 404
    
    # Use first video for the zone (or could randomize)
    video_path = ZONE_VIDEOS[zone_id][0]
    
    if not Path(video_path).exists():
        return jsonify({"error": f"Video not found: {video_path}"}), 404
    
    result = vision_agent.analyze_video_frame(video_path, zone_id)
    return jsonify(result)


@app.route('/api/analyze/all', methods=['GET'])
def analyze_all_zones():
    """Analyze all zones and return combined results."""
    results = {}
    for zone_id in ZONE_VIDEOS:
        video_path = ZONE_VIDEOS[zone_id][0]
        if Path(video_path).exists():
            results[zone_id] = vision_agent.analyze_video_frame(video_path, zone_id)
        else:
            results[zone_id] = {"error": "Video not found"}
    return jsonify(results)


@app.route('/api/analyze/video', methods=['POST'])
def analyze_custom_video():
    """Analyze a specific video file."""
    data = request.get_json()
    video_path = data.get('video_path')
    location_id = data.get('location_id', 'custom')
    
    if not video_path or not Path(video_path).exists():
        return jsonify({"error": "Video not found"}), 404
    
    result = vision_agent.analyze_video_frame(video_path, location_id)
    return jsonify(result)


@app.route('/api/analyze/hierarchical/<zone_id>', methods=['GET'])
def hierarchical_analyze(zone_id):
    """Use hierarchical (audio-first) analysis for a zone."""
    if zone_id not in ZONE_VIDEOS:
        return jsonify({"error": f"Unknown zone: {zone_id}"}), 404
    
    video_path = ZONE_VIDEOS[zone_id][0]
    if not Path(video_path).exists():
        return jsonify({"error": f"Video not found"}), 404
    
    result = hierarchical_agent.hierarchical_analysis(video_path)
    return jsonify(result)


@app.route('/api/zones', methods=['GET'])
def get_zones():
    """Get zone configuration."""
    return jsonify({
        "zones": list(ZONE_VIDEOS.keys()),
        "videos_per_zone": {k: len(v) for k, v in ZONE_VIDEOS.items()}
    })


if __name__ == '__main__':
    print("=" * 50)
    print("PROJECT LIFELINE - API SERVER")
    print("=" * 50)
    print("Endpoints:")
    print("  GET  /api/health           - Health check")
    print("  GET  /api/zones            - List zones")
    print("  GET  /api/analyze/<zone>   - Analyze zone")
    print("  GET  /api/analyze/all      - Analyze all zones")
    print("  POST /api/analyze/video    - Analyze custom video")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)
