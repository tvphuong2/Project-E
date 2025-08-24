from typing import Optional
import requests

class ImageFetcher:
    def __init__(self, api_key: Optional[str] = None, cx: Optional[str] = None):
        self.api_key = api_key
        self.cx = cx

    def fetch(self, query: str) -> Optional[str]:
        if not (self.api_key and self.cx):
            return None
        # thêm từ khóa "icon" vào query
        query_with_icon = f"{query} icon"
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.cx,
            "searchType": "image",
            "q": query_with_icon,
            "num": 1
        }
        try:
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
            items = data.get("items", [])
            if items:
                return items[0].get("link")
            return None
        except Exception:
            return None
