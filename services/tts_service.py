import os, random
from typing import Optional
import requests

class TTSClient:
    """Simple wrapper around OpenAI Text-to-Speech API.

    If api_key is missing, synthesize_to_file will return False
    without performing network calls."""
    def __init__(self, api_key: Optional[str]=None, model: str="gpt-4o-mini-tts"):
        self.api_key = api_key
        self.model = model
        self.voices = ["alloy", "verse", "lumen", "orion"]

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def synthesize_to_file(self, text: str, out_path: str) -> bool:
        if not self.api_key:
            return False
        voice = random.choice(self.voices)
        payload = {"model": self.model, "voice": voice, "input": text}
        url = "https://api.openai.com/v1/audio/speech"
        try:
            r = requests.post(url, headers=self._headers(), json=payload, timeout=60)
            r.raise_for_status()
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(r.content)
            return True
        except Exception:
            return False
