import json
import os
from fastapi import APIRouter, Request, HTTPException
from services.redis_service import save_token_to_redis, load_token_from_redis

router = APIRouter()



@router.post("/save-token")
async def save_token(request: Request):
    try:
        token_data = await request.json()
        save_token_to_redis(token_data)
        return {"status": "Token saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/token")
async def get_token():
    token = load_token_from_redis()
    if token:
        return token
    else:
        raise HTTPException(status_code=404, detail="No token found")
