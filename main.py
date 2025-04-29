from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.chat_router import router as chat_router
from routers.token_router import router as token_router

app = FastAPI(title="Zoho CRM LangGraph MCP Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


app.include_router(chat_router)
app.include_router(token_router)