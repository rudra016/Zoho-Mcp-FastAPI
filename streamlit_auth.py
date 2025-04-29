import streamlit as st
import requests
import json
import os
from urllib.parse import urlencode
from dotenv import load_dotenv
from pyngrok import ngrok

load_dotenv()

CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
AUTH_URL = "https://accounts.zoho.com/oauth/v2/auth"
TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
SCOPE = "ZohoCRM.settings.READ,ZohoCRM.modules.READ"

ngrok.set_auth_token(os.getenv("NGROK_AUTH_TOKEN"))
public_url = ngrok.connect(8000, bind_tls=True).public_url
callback_url = f"{public_url}/callback"

st.title("🔐 Zoho OAuth 2.0 Setup")

params = {
    "response_type": "code",
    "client_id": CLIENT_ID,
    "scope": SCOPE,
    "redirect_uri": callback_url,
    "access_type": "offline",
    "prompt": "consent"
}
auth_url = f"{AUTH_URL}?{urlencode(params)}"

st.markdown(f"Click below to authenticate Zoho and generate token:")
st.markdown(f"📢 Use this as your Authorized Redirect URI in Zoho: `{callback_url}`")

st.markdown(f"[🔗 Authenticate with Zoho]({auth_url})", unsafe_allow_html=True)


from fastapi import FastAPI, Request
import uvicorn
import threading

app = FastAPI()

@app.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    print(f"Received authorization code: {code}")
    st.success(f"Authorization code received: {code}")

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": callback_url,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    res = requests.post(TOKEN_URL, params=token_data)
    token_json = res.json()

    with open("token_store.json", "w") as f:
        json.dump(token_json, f, indent=2)

    st.success("✅ Token saved successfully! You can now open the Chat App.")
    return {"status": "token saved"}

def run_server():
    uvicorn.run(app, host="0.0.0.0", port=8000)

threading.Thread(target=run_server, daemon=True).start()
