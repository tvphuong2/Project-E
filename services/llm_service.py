import os
from typing import Dict, List, Optional
import requests

class LLMClient:
    def __init__(self, api_key: Optional[str]=None, model: str="gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _post(self, payload):
        # Uses Chat Completions API format for broad compatibility
        url = "https://api.openai.com/v1/chat/completions"
        r = requests.post(url, headers=self._headers(), json=payload, timeout=60)
        r.raise_for_status()
        return r.json()

    def normalize_text(self, text: str) -> str:
        if not self.api_key:
            return text  # fallback handled elsewhere
        prompt = (
            "Normalize this English text for dictation comparison: "
            "expand contractions (I'm->I am, we've->we have, 'em->them, etc.), "
            "spell out numbers in words, remove special symbols, keep only commas and periods, "
            "use lowercase, collapse whitespace. Return ONLY the normalized text."
            f"TEXT:{text}"
        )
        payload = {"model": self.model, "messages": [{"role":"user","content": prompt}], "temperature": 0}
        try:
            data = self._post(payload)
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return text

    def describe_word(self, word: str) -> Dict:
        if not self.api_key:
            return {"pos": "", "meaning_vi": "", "usage": "", "phonetic": ""}

        prompt = (
            "For the English vocabulary word below, return a compact JSON object ONLY with keys: "
            "pos (part of speech), meaning_vi (Vietnamese meaning), usage (1 short example sentence), phonetic (IPA). "
            "Do not include any commentary. Word: " + word
        )

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}  # ép trả JSON
        }

        data = self._post(payload)
        content = data["choices"][0]["message"]["content"].strip()

        import json as _json
        obj = _json.loads(content)

        return {
            "pos": obj.get("pos", ""),
            "meaning_vi": obj.get("meaning_vi", ""),
            "usage": obj.get("usage", ""),
            "phonetic": obj.get("phonetic", "")
        }

    def generate_similar_or_confusables(self, word: str) -> List[str]:
        if not self.api_key:
            return []
        prompt = (
            "List 3-6 English words that are commonly confused with or sound similar to: "
            f"{word}. Respond as a comma-separated list only."
        )
        payload = {"model": self.model, "messages":[{"role":"user","content":prompt}], "temperature":0.4}

        data = self._post(payload)
        content = data["choices"][0]["message"]["content"].strip()
        parts = [p.strip().strip(",.") for p in content.split(",")]
        return [p for p in parts if p and p.lower()!=word.lower()][:6]
