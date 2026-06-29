"""
Upstash Redis cache helper using HTTP REST API.
No SDK needed — pure urllib so it works in Vercel serverless.
"""
import os
import json
import urllib.request
import urllib.parse

def _redis_url():
    return os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")

def _redis_token():
    return os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")

def _request(path, method="GET", body=None):
    url = _redis_url() + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bearer {_redis_token()}",
            "Content-Type": "application/json",
        },
        method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"Redis error: {e}")
        return None

def cache_get(key):
    """Return cached value string or None."""
    res = _request(f"/get/{urllib.parse.quote(key, safe='')}")
    if res and res.get("result"):
        return res["result"]
    return None

def cache_set(key, value, ttl_seconds=7200):
    """Store value with TTL. Returns True on success."""
    # Upstash REST: SET key value EX ttl
    encoded_key = urllib.parse.quote(key, safe='')
    encoded_val = urllib.parse.quote(value, safe='')
    res = _request(f"/set/{encoded_key}/{encoded_val}/ex/{ttl_seconds}")
    return res and res.get("result") == "OK"

def cache_available():
    """Check if Redis is configured."""
    return bool(_redis_url() and _redis_token())
