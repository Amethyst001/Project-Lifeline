"""
Gemini API Key Manager with Rotation and Rate Limit Handling.
Uses the new google.genai package.
"""
from google import genai
from google.genai import types
import time
import threading
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class KeyStatus(Enum):
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    EXHAUSTED = "exhausted"
    ERROR = "error"

@dataclass
class APIKey:
    key: str
    index: int
    status: KeyStatus = KeyStatus.AVAILABLE
    last_used: float = 0
    error_count: int = 0
    cooldown_until: float = 0

class GeminiKeyManager:
    """
    Manages multiple Gemini API keys with automatic rotation.
    """
    
    def __init__(self, api_keys: list[str]):
        self.keys = [APIKey(key=k, index=i) for i, k in enumerate(api_keys)]
        self.current_index = 0
        self.lock = threading.Lock()
        self.clients = {}  # Cache clients per key
        
        # Model configurations - Using Gemini 3 for hackathon
        self.models = {
            "orchestrator": "gemini-3-flash-preview",
            "vision": "gemini-3-flash-preview",
            "fallback": "gemini-3-flash-preview",
            "creative": "gemini-3-flash-preview",
            "pro": "gemini-3-pro-preview"
        }
    
    def get_next_key(self) -> Optional[APIKey]:
        """Get the next available API key using round-robin."""
        with self.lock:
            current_time = time.time()
            attempts = 0
            
            while attempts < len(self.keys):
                key = self.keys[self.current_index]
                self.current_index = (self.current_index + 1) % len(self.keys)
                
                if key.status == KeyStatus.AVAILABLE:
                    return key
                
                if key.status == KeyStatus.RATE_LIMITED:
                    if current_time > key.cooldown_until:
                        key.status = KeyStatus.AVAILABLE
                        key.error_count = 0
                        return key
                
                attempts += 1
            
            return None
    
    def get_client(self, key: APIKey) -> genai.Client:
        """Get or create a client for the given key."""
        if key.index not in self.clients:
            self.clients[key.index] = genai.Client(api_key=key.key)
        return self.clients[key.index]
    
    def mark_rate_limited(self, key: APIKey, cooldown_seconds: int = 60):
        with self.lock:
            key.status = KeyStatus.RATE_LIMITED
            key.cooldown_until = time.time() + cooldown_seconds
            key.error_count += 1
    
    def mark_error(self, key: APIKey):
        with self.lock:
            key.error_count += 1
            if key.error_count >= 3:
                key.status = KeyStatus.ERROR
    
    def mark_success(self, key: APIKey):
        with self.lock:
            key.last_used = time.time()
            key.error_count = 0
    
    def get_model(self, purpose: str = "orchestrator") -> tuple:
        """Get a client and model name for the given purpose."""
        key = self.get_next_key()
        if not key:
            raise Exception("All API keys exhausted or rate limited")
        
        client = self.get_client(key)
        model_name = self.models.get(purpose, self.models["fallback"])
        
        return client, model_name, key
    
    def call_with_retry(self, purpose: str, prompt: str, max_retries: int = 3, **kwargs) -> Optional[str]:
        """Make an API call with automatic key rotation on failure."""
        for attempt in range(max_retries):
            try:
                client, model_name, key = self.get_model(purpose)
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(**kwargs) if kwargs else None
                )
                
                self.mark_success(key)
                return response.text
                
            except Exception as e:
                error_str = str(e).lower()
                
                if "quota" in error_str or "rate" in error_str or "429" in error_str:
                    self.mark_rate_limited(key, cooldown_seconds=60)
                elif "resource" in error_str or "exhausted" in error_str:
                    self.mark_rate_limited(key, cooldown_seconds=300)
                else:
                    self.mark_error(key)
                    print(f"[ERROR] {e}")
                
                time.sleep(1)
        
        return None
    
    def get_status(self) -> dict:
        return {f"key_{k.index + 1}": {"status": k.status.value, "error_count": k.error_count} for k in self.keys}


# Load API keys from environment variable (comma-separated)
import os

def _load_keys():
    """Load API keys from environment variable."""
    env_keys = os.environ.get("GOOGLE_API_KEY", "")
    if not env_keys:
        print("[WARNING] No GOOGLE_API_KEY found in environment")
        return []
    
    # Support single key or comma-separated multiple keys
    keys = [k.strip() for k in env_keys.split(",") if k.strip()]
    return keys

API_KEYS = _load_keys()

if API_KEYS:
    key_manager = GeminiKeyManager(API_KEYS)
else:
    key_manager = None
    print("[ERROR] No API keys configured. Set GOOGLE_API_KEY environment variable.")


# Convenience functions
def call_orchestrator(prompt: str, **kwargs):
    if not key_manager:
        return None
    return key_manager.call_with_retry("orchestrator", prompt, **kwargs)

def call_vision(prompt: str, **kwargs):
    if not key_manager:
        return None
    return key_manager.call_with_retry("vision", prompt, **kwargs)


if __name__ == "__main__":
    if key_manager:
        print("Testing Gemini API...")
        response = call_orchestrator("Reply with just: OK")
        print(f"Response: {response}")
    else:
        print("Set GOOGLE_API_KEY to test")
