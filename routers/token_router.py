import json
import os
from fastapi import APIRouter, Request, HTTPException

router = APIRouter()

# In-memory token storage
token_data_memory = None

# Optional: File backup path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(BASE_DIR, "token_store.json")


@router.post("/save-token")
async def save_token(request: Request):
    global token_data_memory

    try:
        token_data = await request.json()

        token_data_memory = token_data

       
        with open(TOKEN_PATH, "w") as f:
            json.dump(token_data, f, indent=2)

        return {"status": "Token saved successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/token")
async def get_token():
    global token_data_memory

    if token_data_memory:
        return token_data_memory

    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "r") as f:
            return json.load(f)

    raise HTTPException(status_code=404, detail="No token found")
