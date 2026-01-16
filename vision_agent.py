"""
Project Lifeline - Enhanced Vision Agent
Uses Gemini 2.5 Flash via the new google.genai package.
"""
import json
import os
from pathlib import Path
from datetime import datetime
from google import genai
from google.genai import types
from gemini_manager import key_manager

class VisionAgent:
    def __init__(self):
        self.model_purpose = "vision"
        self.previous_readings = {}
    
    def analyze_video_frame(self, video_path: str, location_id: str = "unknown") -> dict:
        """Analyze a video frame using Gemini Vision."""
        if not os.path.exists(video_path):
            return {"error": f"Video not found: {video_path}"}
        
        try:
            client, model_name, key = key_manager.get_model("vision")
            
            print(f"[Vision] Uploading video: {Path(video_path).name}...")
            
            # Upload file using new API
            with open(video_path, "rb") as f:
                video_bytes = f.read()
            
            prompt = self._build_enhanced_prompt(location_id)
            
            # Use inline data for video
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
            
            result = self._parse_response(response.text)
            result = self._add_temporal_analysis(result, location_id)
            
            water_level = result.get("visual_evidence", {}).get("water_level_cm", 0)
            self.previous_readings[location_id] = {
                "water_level_cm": water_level,
                "timestamp": datetime.now()
            }
            
            return result
            
        except Exception as e:
            print(f"[Vision] Error: {e}")
            return {"error": str(e), "source": "error"}
    
    def _build_enhanced_prompt(self, location_id: str) -> str:
        return f"""You are an AI Vision Agent for Lagos Flood Response.

LOCATION: {location_id}

ANALYZE THIS VIDEO FOR FLOOD AND WEATHER CONDITIONS.

## FIRST: Determine if there IS flooding
- Look for water on roads, submerged vehicles, people wading
- If NO flooding is visible, set water_level_cm to 0 and zone_status to "NORMAL"
- Be honest - not every video shows flooding

## DETECT PRECIPITATION STATUS
- Is it currently raining? (Look for rain drops, wet surfaces, umbrellas)
- Is rain the likely source of any flooding?
- Active rain means flooding may worsen

## ESTIMATE WATER DEPTH (if flooding present)
Use human-scale references:
- Ankle = 15cm, Knee = 40cm, Waist = 80cm, Chest = 110cm
- Car wheel = 30cm, Car door = 60cm, Car hood = 100cm

OUTPUT JSON ONLY:
{{
    "meta_data": {{
        "timestamp": "{datetime.now().strftime('%H:%M:%S')}",
        "location_id": "{location_id}",
        "source_type": "<crowdsourced_mobile|cctv|drone|news_broadcast>",
        "confidence_score": <0.0-1.0>
    }},
    "weather_conditions": {{
        "is_raining": <true|false>,
        "rain_intensity": "<none|light|moderate|heavy>",
        "visibility": "<clear|reduced|poor>",
        "precipitation_notes": "<describe what you see regarding rain/weather>"
    }},
    "flood_assessment": {{
        "flooding_detected": <true|false>,
        "water_level_cm": <0-200>,
        "reference_landmark": "<what you used to estimate, or 'N/A' if no flooding>",
        "flood_source": "<rain|drainage|lagoon|unknown|none>",
        "observations": "<describe flood conditions or state 'No flooding visible'>"
    }},
    "temporal_indicators": {{
        "water_movement": "<none|static|slow_flow|fast_current>",
        "trend_observed": "<RISING|STABLE|RECEDING|NOT_APPLICABLE>"
    }},
    "logistics_decision": {{
        "zone_status": "<NORMAL|WARNING|CRITICAL|FLOODED>",
        "passable_assets": ["<list>"],
        "blocked_assets": ["<list>"],
        "recommended_asset": "<TRUCK|OKADA|CANOE>",
        "action_trigger": "<MONITOR|ALERT|SWAP_ASSET|EVACUATE>"
    }}
}}

RULES:
- NORMAL: No flooding or water < 10cm
- WARNING: Water 10-30cm
- CRITICAL: Water 30-60cm
- FLOODED: Water > 60cm
- Truck safe up to 40cm, Okada safe up to 20cm, Canoe needed for 40cm+"""

    def _parse_response(self, text: str) -> dict:
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        return {"raw_response": text}
    
    def _add_temporal_analysis(self, result: dict, location_id: str) -> dict:
        """Add temporal analysis - uses previous readings if available, otherwise infers from weather."""
        # Try to get water level from either old or new field names
        flood_data = result.get("flood_assessment", result.get("visual_evidence", {}))
        current_level = flood_data.get("water_level_cm", 0)
        
        if location_id in self.previous_readings:
            # Compare with previous reading
            prev = self.previous_readings[location_id]
            time_diff = (datetime.now() - prev["timestamp"]).total_seconds() / 60
            if time_diff > 0:
                level_change = current_level - prev["water_level_cm"]
                velocity = (level_change / time_diff) * 60
                trend = "RAPID_RISE" if velocity > 60 else ("RISING" if level_change > 5 else ("RECEDING" if level_change < -5 else "STABLE"))
                result["temporal_analysis"] = {
                    "comparison_frame": f"T-minus-{int(time_diff)}_mins",
                    "level_change_cm": f"{'+' if level_change >= 0 else ''}{level_change}",
                    "velocity_cm_per_hour": round(velocity, 1),
                    "trend": trend
                }
        else:
            # SINGLE-SHOT INFERENCE: Infer trend from weather conditions
            weather = result.get("weather_conditions", {})
            rain_intensity = weather.get("rain_intensity", "none")
            is_raining = weather.get("is_raining", False)
            flooding_detected = flood_data.get("flooding_detected", current_level > 10)
            
            # Inference logic
            if is_raining and rain_intensity in ["heavy", "moderate"] and flooding_detected:
                inferred_trend = "RISING_RAPIDLY" if rain_intensity == "heavy" else "RISING"
            elif is_raining and flooding_detected:
                inferred_trend = "RISING"
            elif not is_raining and flooding_detected:
                inferred_trend = "STABLE"  # Rain stopped but water still there
            elif not flooding_detected:
                inferred_trend = "NOT_APPLICABLE"
            else:
                inferred_trend = "UNKNOWN"
            
            result["temporal_analysis"] = {
                "comparison_frame": "SINGLE_SHOT_INFERENCE",
                "inferred_from": f"rain_intensity={rain_intensity}, flooding={flooding_detected}",
                "trend": inferred_trend
            }
        
        return result


if __name__ == "__main__":
    agent = VisionAgent()
    print("Vision Agent ready. Use api_server.py to run the full system.")
