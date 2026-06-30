import hashlib, json, time
from pathlib import Path
import requests

CACHE_DIR = Path("cache")

def _key(url, params, suffix):
    raw = url + json.dumps(params or {}, sort_keys=True)
    return CACHE_DIR / (hashlib.sha1(raw.encode()).hexdigest() + suffix)

def get_json(url, params=None, headers=None, cache_key=None):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f = _key(cache_key or url, params, ".json")
    if f.exists():
        return json.loads(f.read_text())
    for attempt in range(3):
        r = requests.get(url, params=params, headers=headers, timeout=30)
        if r.status_code == 429:
            wait = 2 ** attempt
            time.sleep(wait)
            continue
        r.raise_for_status()
        data = r.json()
        f.write_text(json.dumps(data))
        return data
    r.raise_for_status()  # raise on final 429

def get_text(url, params=None, headers=None, cache_key=None):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f = _key(cache_key or url, params, ".txt")
    if f.exists():
        return f.read_text()
    r = requests.get(url, params=params, headers=headers, timeout=60)
    r.raise_for_status()
    f.write_text(r.text)
    return r.text
