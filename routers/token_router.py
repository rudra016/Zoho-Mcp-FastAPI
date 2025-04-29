import json
import os
from fastapi import APIRouter

router = APIRouter()

# Build absolute path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(BASE_DIR, "token_store.json")

@router.get("/token")
async def get_token():
    if not os.path.exists(TOKEN_PATH):
        return {"error": "No token found"}
    
    with open(TOKEN_PATH, "r") as f:
        token_data = json.load(f)
    
    return token_data
