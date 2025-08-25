import os
import random
from typing import Optional

import requests

class TTSService:
    """Generate speech audio for words using OpenAI's TTS API."""

    def __init__(self, api_key: Optional[str], model: str = "gpt-4o-mini-tts"):
        self.api_key = api_key
        self.model = model
        # voice options from OpenAI documentation
        self.voices = ["alloy", "verse", "spark", "gala", "harvest"]

    def synthesize(self, text: str, out_path: str) -> Optional[str]:
        """Synthesize speech for ``text`` and save to ``out_path``. Returns the path or None."""
        if not self.api_key:
            return None
        voice = random.choice(self.voices)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": text,
            "voice": voice,
            "format": "mp3",
        }
        url = "https://api.openai.com/v1/audio/speech"
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)
            r.raise_for_status()
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(r.content)
            return out_path
        except Exception:
            return None
