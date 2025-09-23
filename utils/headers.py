from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BASE_DIR / 'config'
USER_AGENT_FILE = CONFIG_DIR / 'user_agent_pc.txt'
COOKIE_FILE = CONFIG_DIR / 'cookie.json'


class HeadersBuilder:
    def __init__(self, default_headers: Optional[Dict[str, str]] = None) -> None:
        self.default_headers = default_headers or {}
        self._user_agents = None

    def _load_user_agents(self) -> list[str]:
        if self._user_agents is None:
            if not USER_AGENT_FILE.exists():
                return ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"]
            self._user_agents = [ua.strip() for ua in USER_AGENT_FILE.read_text(encoding='utf-8').splitlines() if ua.strip()]
        return self._user_agents

    def build(self, overrides: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "user-agent": random.choice(self._load_user_agents()),
            "sec-ch-ua-platform": '"Windows"',
            "upgrade-insecure-requests": "1",
        }
        headers.update(self.default_headers)
        if overrides:
            headers.update(overrides)
        return headers


def save_cookies(cookies: Dict) -> None:
    COOKIE_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding='utf-8')


def load_cookies() -> Dict:
    if COOKIE_FILE.exists():
        try:
            data = json.loads(COOKIE_FILE.read_text(encoding='utf-8'))
            # If cookie file contains Playwright storage state, normalize to name->value
            if isinstance(data, dict) and isinstance(data.get('cookies'), list):
                try:
                    return {c['name']: c.get('value', '') for c in data['cookies'] if isinstance(c, dict) and 'name' in c}
                except Exception:
                    return {}
            return data
        except Exception:
            return {}
    return {}
