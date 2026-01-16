"""
Project Lifeline - Orchestrator
Uses Gemini 2.5 Flash for autonomous logistics coordination.
Implements Thought Signatures for state persistence across the mission loop.
"""
import time
import json
import hashlib
from vision_agent import VisionAgent
from asset_manager import get_asset_manager
from gemini_manager import key_manager

class Orchestrator:
    def __init__(self):
        self.model_purpose = "orchestrator"
        self.vision_agent = VisionAgent()
        self.assets = {
            "logistics_1": get_asset_manager()["Truck"]("logistics_1", "Mainland Depot")
        }
        self.thought_history = []
        self.last_thought_signature = "init_state_000"
        self.mission_log = []
    
    def run_mission_loop(self, duration_minutes: int = 120, step_minutes: int = 15, video_path: str = None):
        """
        Runs the full monitoring loop for the flood duration.
        
        Args:
            duration_minutes: Total mission duration
            step_minutes: Interval between checks
            video_path: Optional video for real analysis
        """
        print(f"{'='*60}")
        print(f"OPERATION LIFELINE - STARTING")
        print(f"Duration: {duration_minutes}m | Interval: {step_minutes}m")
        print(f"{'='*60}")
        
        for minute in range(0, duration_minutes + 1, step_minutes):
            print(f"\n--- T+{minute} MINUTES ---")
            self.monitor_phase(minute, video_path)
            time.sleep(0.5)
        
        print(f"\n{'='*60}")
        print("MISSION COMPLETE")
        self._print_summary()
    
    def monitor_phase(self, minute: int, video_path: str = None):
        """Execute one cycle of the Monitor-Predict-Plan-Execute-Verify loop."""
        
        # 1. MONITOR via Vision Agent
        vision_data = self.vision_agent.analyze_sequence(minute, video_path)
        water_level = vision_data.get("water_level_estimate_cm", vision_data.get("raw_level", 0))
        status = vision_data.get("bridge_status", "UNKNOWN")
        print(f"[MONITOR] Bridge: {status} | Water: {water_level}cm | Velocity: {vision_data.get('velocity_of_rise', 'N/A')}")
        
        # 2. PREDICT & PLAN (Call Gemini with Thought Signature)
        decision, new_signature = self._call_gemini_brain(vision_data, self.last_thought_signature)
        self.last_thought_signature = new_signature
        print(f"[THINK] Signature: {new_signature[:20]}...")
        
        # 3. EXECUTE
        if decision["action"] == "SWAP_ASSET":
            self.execute_swap(decision["target_asset"], decision["new_type"])
            self.mission_log.append({
                "minute": minute,
                "action": "SWAP",
                "from": "Truck",
                "to": decision["new_type"],
                "reason": decision["reasoning"]
            })
        else:
            print(f"[PLAN] {decision['reasoning']}")
        
        # 4. VERIFY
        self.verify_assets(water_level)
    
    def _call_gemini_brain(self, vision_data: dict, previous_signature: str) -> tuple[dict, str]:
        """
        Call Gemini for decision making with Thought Signatures.
        
        Thought Signature: A hash representing the accumulated state/context
        of the agent's reasoning chain. Passed between calls to maintain continuity.
        """
        water_level = vision_data.get("water_level_estimate_cm", vision_data.get("raw_level", 0))
        current_asset = self.assets["logistics_1"]
        asset_type = current_asset.type
        
        # Build context with thought signature
        context = {
            "previous_thought_signature": previous_signature,
            "water_level_cm": water_level,
            "bridge_status": vision_data.get("bridge_status"),
            "velocity": vision_data.get("velocity_of_rise"),
            "current_asset": asset_type,
            "asset_constraints": {
                "Truck": {"max_depth_cm": 40},
                "Okada": {"max_depth_cm": 20},
                "Canoe": {"min_depth_cm": 30}
            }
        }
        
        prompt = f"""You are an autonomous logistics coordinator for Lagos flood response.

CONTEXT (JSON):
{json.dumps(context, indent=2)}

THOUGHT SIGNATURE: {previous_signature}
This signature represents your previous reasoning state. Use it to maintain continuity.

DECISION REQUIRED:
Based on the water level and current asset, decide:
1. MAINTAIN - Keep current asset if conditions are safe
2. SWAP_ASSET - Switch to a different vehicle if current one cannot operate

RULES:
- Truck FAILS if water > 40cm
- Okada FAILS if water > 20cm
- Canoe REQUIRES water >= 30cm to operate
- Always prioritize delivery continuity

OUTPUT (JSON only, no markdown):
{{
    "action": "MAINTAIN" or "SWAP_ASSET",
    "target_asset": "logistics_1" or null,
    "new_type": "Canoe" or "Okada" or "Truck" or null,
    "reasoning": "<brief explanation>",
    "confidence": <0.0 to 1.0>
}}"""

        try:
            model, key = key_manager.get_model("orchestrator")
            response = model.generate_content(prompt)
            key_manager.mark_success(key)
            
            # Parse response
            result = self._parse_decision(response.text)
            
            # Generate new thought signature (hash of context + decision)
            sig_input = json.dumps(context) + json.dumps(result) + previous_signature
            new_signature = hashlib.sha256(sig_input.encode()).hexdigest()[:16]
            
            self.thought_history.append({
                "signature": new_signature,
                "decision": result,
                "water_level": water_level
            })
            
            return result, new_signature
            
        except Exception as e:
            print(f"[BRAIN] API Error: {e} - Using fallback logic")
            return self._fallback_decision(water_level, asset_type, previous_signature)
    
    def _parse_decision(self, text: str) -> dict:
        """Parse Gemini response into decision dict."""
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        # Fallback if parsing fails
        return {
            "action": "MAINTAIN",
            "reasoning": "Parse error - maintaining current state",
            "target_asset": None,
            "new_type": None
        }
    
    def _fallback_decision(self, water_level: int, asset_type: str, previous_signature: str) -> tuple[dict, str]:
        """Fallback decision logic when API fails."""
        new_signature = f"fallback_{hash(str(water_level) + previous_signature)}"
        
        if water_level >= 40 and asset_type == "TRUCK":
            return {
                "action": "SWAP_ASSET",
                "target_asset": "logistics_1",
                "new_type": "Canoe",
                "reasoning": f"Water {water_level}cm exceeds Truck limit (40cm). Switching to Canoe."
            }, new_signature
        
        return {
            "action": "MAINTAIN",
            "reasoning": f"Conditions acceptable for {asset_type}.",
            "target_asset": None,
            "new_type": None
        }, new_signature
    
    def execute_swap(self, asset_id: str, new_type_str: str):
        """Execute asset swap."""
        print(f"[ACTION] Swapping {asset_id} to {new_type_str.upper()}...")
        current_loc = self.assets[asset_id].current_location
        new_class = get_asset_manager()[new_type_str]
        self.assets[asset_id] = new_class(asset_id, current_loc)
        print(f"[SUCCESS] {asset_id} is now a {new_type_str}. Physics updated.")
    
    def verify_assets(self, water_depth_cm: int):
        """Verify all assets can operate at current water level."""
        water_depth_m = water_depth_cm / 100.0
        for asset_id, asset in self.assets.items():
            if asset.can_traverse(water_depth_m):
                print(f"[VERIFY] ✓ {asset_id} ({asset.type}) operational at {water_depth_cm}cm")
            else:
                print(f"[VERIFY] ✗ {asset_id} ({asset.type}) CANNOT operate at {water_depth_cm}cm!")
    
    def _print_summary(self):
        """Print mission summary."""
        print(f"\nMission Log: {len(self.mission_log)} actions taken")
        for log in self.mission_log:
            print(f"  T+{log['minute']}m: {log['action']} {log.get('from', '')} -> {log.get('to', '')}")
        print(f"\nThought Chain: {len(self.thought_history)} decisions")
        print(f"Final Signature: {self.last_thought_signature}")


if __name__ == "__main__":
    orchestrator = Orchestrator()
    orchestrator.run_mission_loop(duration_minutes=60, step_minutes=15)
