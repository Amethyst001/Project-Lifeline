"""
Project Lifeline - Hierarchical Video Analyzer
Uses the "Ear & Eye" architecture:
- Pass 1 (Audio): Scan for distress signals (cheap, fast)
- Pass 2 (Visual): Deep analysis at critical timestamps only
"""
import json
import os
from pathlib import Path
from datetime import datetime
from google import genai
from google.genai import types
from gemini_manager import key_manager


class HierarchicalAnalyzer:
    """
    Two-phase analysis for efficient video processing.
    Audio first to find critical moments, then visual deep-dive.
    """
    
    def __init__(self):
        self.distress_keywords = [
            "ewoo", "yepa", "jesus", "help", "water", "flood",
            "danger", "careful", "abeg", "save"
        ]
    
    def analyze_audio_first(self, video_path: str) -> dict:
        """
        Pass 1: Listen for distress signals.
        Returns timestamps of critical audio events.
        """
        if not os.path.exists(video_path):
            return {"error": f"Video not found: {video_path}"}
        
        try:
            client, model_name, key = key_manager.get_model("vision")
            
            print(f"[AUDIO] Scanning: {Path(video_path).name}...")
            
            with open(video_path, "rb") as f:
                video_bytes = f.read()
            
            prompt = """You are an Audio Analyst for Lagos Flood Emergency Response.

TASK: Listen to this video's audio track and identify critical moments.

DISTRESS TRIGGERS TO DETECT:
1. Screams or shouts of "Ewoo!", "Yepa!", "Jesus!", "Help!", "Abeg!"
2. Sudden loud splashing sounds
3. Panic in voices (rapid speech, high pitch)
4. Children crying
5. Sirens or emergency signals
6. Heavy rain + wind sounds (indicates severity)

ALSO NOTE:
- General crowd noise level (calm vs panicked)
- Any mentions of water level, flooding, or danger
- Sounds of vehicles struggling through water

OUTPUT JSON ONLY:
{
    "audio_clarity": "<clear|moderate|poor|no_audio>",
    "overall_mood": "<calm|concerned|panicked|chaotic>",
    "distress_events": [
        {
            "timestamp_approx": "<start of video, middle, end, or seconds if detectable>",
            "type": "<scream|splash|cry|siren|mention>",
            "description": "<what you heard>",
            "severity": "<low|medium|high|critical>"
        }
    ],
    "flood_audio_indicators": {
        "water_sounds": <true|false>,
        "heavy_rain": <true|false>,
        "traffic_struggle": <true|false>
    },
    "priority_for_visual": "<high|medium|low>",
    "reasoning": "<why this priority level>"
}"""

            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Content(
                        parts=[
                            types.Part.from_bytes(data=video_bytes, mime_type="video/mp4"),
                            types.Part.from_text(text=prompt)
                        ]
                    )
                ]
            )
            
            key_manager.mark_success(key)
            return self._parse_response(response.text)
            
        except Exception as e:
            print(f"[AUDIO] Error: {e}")
            return {"error": str(e)}
    
    def analyze_visual_deep(self, video_path: str, focus_areas: list = None) -> dict:
        """
        Pass 2: Deep visual analysis at critical moments.
        Only called when audio indicates high priority.
        """
        if not os.path.exists(video_path):
            return {"error": f"Video not found: {video_path}"}
        
        try:
            client, model_name, key = key_manager.get_model("vision")
            
            print(f"[VISUAL] Deep analysis: {Path(video_path).name}...")
            
            with open(video_path, "rb") as f:
                video_bytes = f.read()
            
            focus_context = ""
            if focus_areas:
                focus_context = f"\nFOCUS AREAS FROM AUDIO: {json.dumps(focus_areas)}"
            
            prompt = f"""You are a Visual Analyst for Lagos Flood Emergency Response.
{focus_context}

TASK: Analyze this video for flood logistics decisions.

ESTIMATE WATER DEPTH using references:
- Ankle = 15cm, Knee = 40cm, Waist = 80cm, Chest = 110cm
- Car wheel = 30cm, Car door = 60cm, Car hood = 100cm

DETECT:
1. People in water (especially distress)
2. Vehicles stuck or struggling
3. Infrastructure damage (roads, bridges)
4. Current/flow direction and speed
5. Debris movement

OUTPUT JSON ONLY:
{{
    "meta_data": {{
        "timestamp": "{datetime.now().strftime('%H:%M:%S')}",
        "source_type": "<crowdsourced_mobile|cctv|drone>",
        "confidence_score": <0.0-1.0>
    }},
    "visual_evidence": {{
        "water_level_cm": <0-200>,
        "reference_landmark": "<what you used to estimate>",
        "visibility": "<clear|moderate|poor>",
        "observations": "<describe key things you see>"
    }},
    "people_detection": {{
        "people_visible": <true|false>,
        "people_in_water": <true|false>,
        "distress_observed": <true|false>,
        "count_estimate": <number or null>
    }},
    "temporal_indicators": {{
        "water_movement": "<static|slow_flow|fast_current>",
        "debris_visible": <true|false>,
        "trend": "<RISING|STABLE|RECEDING|UNKNOWN>"
    }},
    "logistics_decision": {{
        "zone_status": "<NORMAL|WARNING|CRITICAL|FLOODED>",
        "recommended_asset": "<TRUCK|OKADA|CANOE>",
        "action_trigger": "<MONITOR|ALERT|SWAP_ASSET|RESCUE>",
        "urgency_level": "<routine|elevated|urgent|emergency>"
    }}
}}

ASSET RULES:
- TRUCK: Water <= 40cm only
- OKADA: Water <= 20cm, OR traffic heavy + dry roads
- CANOE: Water >= 40cm required"""

            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Content(
                        parts=[
                            types.Part.from_bytes(data=video_bytes, mime_type="video/mp4"),
                            types.Part.from_text(text=prompt)
                        ]
                    )
                ]
            )
            
            key_manager.mark_success(key)
            return self._parse_response(response.text)
            
        except Exception as e:
            print(f"[VISUAL] Error: {e}")
            return {"error": str(e)}
    
    def hierarchical_analysis(self, video_path: str) -> dict:
        """
        Full hierarchical analysis: Audio first, then Visual if needed.
        Saves API calls by only doing deep visual when audio indicates priority.
        """
        result = {
            "video": Path(video_path).name,
            "analysis_type": "hierarchical",
            "phases": {}
        }
        
        # Phase 1: Audio scan
        print("\n=== PHASE 1: AUDIO SCAN ===")
        audio_result = self.analyze_audio_first(video_path)
        result["phases"]["audio"] = audio_result
        
        # Determine if visual deep-dive is needed
        priority = audio_result.get("priority_for_visual", "medium")
        distress_events = audio_result.get("distress_events", [])
        
        if priority in ["high", "critical"] or len(distress_events) > 0:
            # Phase 2: Visual deep-dive
            print("\n=== PHASE 2: VISUAL DEEP ANALYSIS ===")
            visual_result = self.analyze_visual_deep(
                video_path, 
                focus_areas=distress_events
            )
            result["phases"]["visual"] = visual_result
            result["final_decision"] = visual_result.get("logistics_decision", {})
        else:
            print("[SKIP] Audio indicates low priority. Skipping deep visual analysis.")
            result["phases"]["visual"] = {"skipped": True, "reason": "Low audio priority"}
            result["final_decision"] = {
                "zone_status": "NORMAL",
                "recommended_asset": "TRUCK",
                "action_trigger": "MONITOR",
                "urgency_level": "routine"
            }
        
        return result
    
    def _parse_response(self, text: str) -> dict:
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        return {"raw_response": text}


if __name__ == "__main__":
    analyzer = HierarchicalAnalyzer()
    
    # Test with a video if available
    test_dir = Path("test_videos_merged")
    if test_dir.exists():
        videos = list(test_dir.glob("*.mp4"))
        if videos:
            print(f"\n{'='*60}")
            print(f"HIERARCHICAL ANALYSIS: {videos[0].name}")
            print(f"{'='*60}")
            result = analyzer.hierarchical_analysis(str(videos[0]))
            print(json.dumps(result, indent=2, ensure_ascii=False))
