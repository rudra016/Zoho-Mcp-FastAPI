import os
import redis
import json
from config.settings import REDIS_URL

r = redis.from_url(REDIS_URL)

TOKEN_KEY = "zoho_crm_token"

def save_token_to_redis(token_data: dict):
    r.set(TOKEN_KEY, json.dumps(token_data))

def load_token_from_redis() -> dict:
    token_json = r.get(TOKEN_KEY)
    if token_json:
        return json.loads(token_json)
    return None
